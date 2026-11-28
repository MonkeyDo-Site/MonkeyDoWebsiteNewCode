"""Combined credit renewals conserve original paid funds and separate each cohort."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.communications.models import MessageDelivery
from core.customer_credit import applied, balance
from core.membership_batch_credit import confirm, review
from core.membership_batch_credit_records import MembershipCreditRenewalBatch
from core.membership_batch_renewals import group_for, group_for_message
from core.membership_records import MembershipPurchase
from core.models import FinancialPosting, PaymentOperation
from core.payments.invoices import received, settled, total
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


class CreditRenewalFixtures(InitialCreditFixtures):
    def family(self):
        self.booking_source, self.original_sale, self.converted_member, _ = self.conversion(
            children=6
        )
        self.first = self.member(places=2)
        self.second = self.member(kind="unlimited")
        self.rows = [
            dict(prior_id=self.first.pk, places=1, months=1, billing="prepaid"),
            dict(prior_id=self.second.pk, places=1, months=1, billing="prepaid"),
        ]
        self.key = uuid.uuid4()
        return self.rows

    def review_batch(self, **changes):
        return review(**(dict(actor=self.staff, customer=self.customer, rows=self.rows) | changes))

    def confirm_batch(self, **changes):
        values = dict(
            actor=self.staff,
            customer=self.customer,
            rows=self.rows,
            request_key=self.key,
            reviewed=changes.get("reviewed") or self.review_batch()["fingerprint"],
            accepted=True,
            credit_confirmed=True,
        )
        return confirm(**(values | changes))

    def facts(self):
        return tuple(
            model.objects.count()
            for model in (
                MembershipPurchase,
                PaymentOperation,
                FinancialPosting,
                MessageDelivery,
                MembershipCreditRenewalBatch,
            )
        )


@override_settings(**SETTINGS)
class CombinedCreditRenewalTests(CreditRenewalFixtures, RuntimeRoleMixin, TestCase):
    def test_preview_changes_no_facts_and_shows_credit_without_new_money(self):
        self.family()
        before = self.facts()
        data = self.review_batch()
        self.assertEqual(data["amount"], "57.98")
        self.assertEqual(data["new_money"], "0.00")
        self.assertEqual(data["available_before"], "95.94")
        self.assertEqual(data["available_after"], "37.96")
        self.assertEqual(before, self.facts())
        self.assertEqual(balance(self.customer.pk), Decimal("95.94"))

    def test_two_full_credit_renewals_preserve_original_receipt_and_one_shared_email(self):
        self.family()
        before = self.facts()
        original_received = received(self.original_sale)
        with self.runtime_role(), patch("core.payments.operations.Gateway") as gateway:
            batch = self.confirm_batch()
        self.assertEqual(tuple(a - b for a, b in zip(self.facts(), before)), (2, 0, 0, 1, 1))
        self.assertEqual(balance(self.customer.pk), Decimal("37.96"))
        self.assertEqual(received(self.original_sale), original_received)
        for part in batch.parts.all():
            sale = part.purchase.installments.first().invoice.sale
            self.assertEqual(applied(sale), part.amount)
            self.assertEqual(received(sale), 0)
            self.assertEqual(settled(sale), total(sale))
            self.assertFalse(sale.operations.exists())
            self.assertEqual(group_for(part.purchase).pk, batch.pk)
        msg = batch.messages.get().message
        self.assertEqual(group_for_message(msg).pk, batch.pk)
        self.assertIn("Existing customer credit of $57.98 was applied", msg.text_body)
        self.assertNotIn("$57.98 was received", msg.text_body)
        self.assertEqual(msg.state, "queued")
        gateway.assert_not_called()
        connection.check_constraints()

    def test_accepted_sources_change_between_children_but_business_terms_do_not(self):
        self.family()
        batch = self.confirm_batch()
        parts = list(batch.parts.order_by("position"))
        self.assertEqual(parts[0].funding_offer["credit"]["available"], "95.94")
        self.assertEqual(parts[1].funding_offer["credit"]["available"], "77.95")
        self.assertEqual(parts[1].facts["offer"]["credit"]["available"], "95.94")
        connection.check_constraints()

    def test_replay_does_not_consume_credit_twice(self):
        self.family()
        data = self.review_batch()
        batch = self.confirm_batch(reviewed=data["fingerprint"])
        before = self.facts()
        repeat = self.confirm_batch(reviewed=data["fingerprint"])
        self.assertEqual(repeat.pk, batch.pk)
        self.assertEqual(before, self.facts())
        self.assertEqual(balance(self.customer.pk), Decimal("37.96"))

    def test_credit_and_terms_must_be_explicit_true(self):
        self.family()
        before = self.facts()
        for change in (
            {"accepted": False},
            {"credit_confirmed": False},
            {"credit_confirmed": "true"},
        ):
            with (
                self.subTest(change=change),
                self.assertRaisesMessage(ValidationError, "authorize"),
            ):
                self.confirm_batch(**change)
        self.assertEqual(before, self.facts())

    def test_credit_cannot_cover_only_part_of_this_combined_checkout(self):
        self.family()
        self.rows[0]["months"] = 12
        with self.assertRaisesMessage(ValidationError, "currently available"):
            self.review_batch()
        self.assertFalse(MembershipCreditRenewalBatch.objects.exists())

    def test_failure_on_second_child_rolls_back_everything(self):
        self.family()
        before = self.facts()
        from core.membership_sales import purchase

        calls = []

        def fail_second(**values):
            calls.append(values)
            if len(calls) == 2:
                raise ValidationError("Fictional second child failure")
            return purchase(**values)

        with (
            patch("core.membership_batch_credit.purchase", side_effect=fail_second),
            self.assertRaisesMessage(ValidationError, "second child"),
        ):
            self.confirm_batch()
        self.assertEqual(before, self.facts())
        self.assertEqual(balance(self.customer.pk), Decimal("95.94"))

    def test_raw_incomplete_parent_cannot_commit(self):
        self.family()
        data = self.review_batch()
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipCreditRenewalBatch.objects.create(
                id=self.key,
                customer=self.customer,
                actor=self.staff,
                amount=data["amount"],
                fingerprint=data["fingerprint"],
                facts=data | {"terms_accepted": True, "credit_confirmed": True},
            )
            connection.check_constraints()

    def test_saved_receipt_and_membership_page_distinguish_applied_credit(self):
        self.family()
        batch = self.confirm_batch()
        verified_owner_login(self.client, self.owner)
        url = reverse("membership_renewals", args=[self.customer.pk])
        page = self.client.get(url, {"checkout": str(batch.pk)})
        self.assertContains(page, "Customer credit applied: $57.98")
        self.assertContains(page, "New money received: $0.00")
        self.assertNotContains(page, "Payment received:")
        part = batch.parts.first()
        page = self.client.get(reverse("membership_overview", args=[part.purchase.pk]))
        self.assertContains(page, "Open combined renewal credit")

    def test_monthly_future_mandate_is_separate_from_full_first_payment_credit(self):
        self.family()
        method = self.converted_member.billing_state.mandate.method
        self.rows[0] |= dict(billing="monthly", months=3, method_id=str(method.pk))
        before = self.facts()
        batch = self.confirm_batch()
        part = batch.parts.get(position=1)
        member = part.purchase
        self.assertEqual(member.billing_state.mandate.method_id, method.pk)
        items = list(member.installments.order_by("number"))
        self.assertEqual(items[0].quote["processing_fee"], "0.00")
        self.assertEqual(items[1].quote["total"], "18.53")
        self.assertFalse(hasattr(items[1], "invoice"))
        self.assertEqual(self.facts()[1:3], before[1:3])
        connection.check_constraints()

    def test_current_contact_and_revision_invalidate_previous_review(self):
        self.family()
        data = self.review_batch()
        type(self.customer).objects.filter(pk=self.customer.pk).update(
            email="current@example.invalid"
        )
        with self.assertRaisesMessage(ValidationError, "changed"):
            self.confirm_batch(reviewed=data["fingerprint"])
        self.assertFalse(MembershipCreditRenewalBatch.objects.exists())

    def test_removed_credit_requires_fresh_review_even_if_balance_still_covers_total(self):
        from core.customer_credit_corrections import correct
        from core.customer_credit_corrections import review as correction_review

        self.family()
        data = self.review_batch()
        values = dict(actor=self.owner, customer_id=self.customer.pk, kind="remove", value="1.00")
        changed = correction_review(**values)
        correct(
            **values,
            reviewed=changed["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Fictional adjustment",
            confirmed=True,
        )
        with self.assertRaisesMessage(ValidationError, "changed"):
            self.confirm_batch(reviewed=data["fingerprint"])
        self.assertEqual(balance(self.customer.pk), Decimal("94.94"))
        self.assertFalse(MembershipCreditRenewalBatch.objects.exists())

    def test_customer_credit_hold_is_respected_without_charging_another_source(self):
        self.family()
        with (
            patch("core.customer_credit.source_on_hold", return_value=True),
            self.assertRaisesMessage(ValidationError, "$0.00 is currently available"),
        ):
            self.review_batch()
        self.assertFalse(MembershipCreditRenewalBatch.objects.exists())

    def test_same_prior_can_split_credit_funded_places_between_membership_types(self):
        self.family()
        self.rows[1] |= dict(prior_id=self.first.pk, kind="unlimited")
        batch = self.confirm_batch()
        self.assertEqual(batch.parts.count(), 2)
        self.assertEqual({p.prior_id for p in batch.parts.all()}, {self.first.pk})
        connection.check_constraints()

    def test_combined_counts_still_cannot_exceed_prior_places(self):
        self.family()
        self.rows[0]["places"] = 2
        self.rows[1]["prior_id"] = self.first.pk
        with self.assertRaisesMessage(ValidationError, "combined selection"):
            self.review_batch()
        self.assertFalse(MembershipCreditRenewalBatch.objects.exists())

    def test_checkout_identity_cannot_change_actor_or_funding_kind(self):
        from core.membership_batch_renewals import confirm as manual_confirm

        self.family()
        data = self.review_batch()
        self.confirm_batch(reviewed=data["fingerprint"])
        before = self.facts()
        with self.assertRaisesMessage(ValidationError, "another reviewed"):
            self.confirm_batch(actor=self.owner, reviewed=data["fingerprint"])
        with self.assertRaisesMessage(ValidationError, "credit"):
            manual_confirm(
                actor=self.staff,
                customer=self.customer,
                rows=self.rows,
                tender="cash",
                request_key=self.key,
                reviewed=data["fingerprint"],
                accepted=True,
                verified_received=True,
            )
        self.assertEqual(before, self.facts())

    def test_saved_credit_facts_are_immutable_through_sql(self):
        self.family()
        batch = self.confirm_batch()
        connection.check_constraints()
        for table, pk in (
            ("core_membershipcreditrenewalbatch", str(batch.pk)),
            ("core_membershipcreditrenewalpart", batch.parts.first().pk),
            ("core_membershipcreditrenewalmessage", batch.messages.first().pk),
        ):
            with self.subTest(table=table), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(f"DELETE FROM {table} WHERE id=%s", [pk])

    def test_cross_customer_selection_is_refused(self):
        self.family()
        from core.models import Customer

        other = Customer.objects.create(
            last_name="Another", phone="2025550199", email="other@example.invalid"
        )
        with self.assertRaisesMessage(ValidationError, "this customer"):
            self.review_batch(customer=other)
        self.assertFalse(MembershipCreditRenewalBatch.objects.exists())

    def test_changed_historical_actor_does_not_prevent_current_contact_message_refresh(self):
        from core.communications.services import claim

        self.family()
        batch = self.confirm_batch()
        old = batch.messages.get().message
        # First validate the original checkout while its creator is active.
        connection.check_constraints()
        type(self.staff).objects.filter(pk=self.staff.pk).update(is_active=False)
        type(self.customer).objects.filter(pk=self.customer.pk).update(
            email="current@example.invalid"
        )
        self.assertIsNone(claim(old.pk))
        current = batch.messages.exclude(message=old).get().message
        self.assertEqual(current.recipient, "current@example.invalid")
        self.assertEqual(current.actor_id, self.staff.pk)
        self.assertIn("Existing customer credit", current.text_body)
        connection.check_constraints()

    def test_paused_sales_keep_saved_credit_receipt_readable(self):
        self.family()
        batch = self.confirm_batch()
        verified_owner_login(self.client, self.owner)
        url = reverse("membership_renewals", args=[self.customer.pk])
        with self.settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertContains(
                self.client.get(url, {"checkout": str(batch.pk)}), "New money received: $0.00"
            )
            self.assertEqual(self.client.post(url, {"tender": "credit"}).status_code, 404)

    def test_no_javascript_review_uses_credit_authorization_and_one_final_action(self):
        data = self.post_values()
        page = self.client.post(self.url, data)
        self.assertContains(page, "I authorize applying the customer credit shown")
        self.assertContains(page, "Apply $57.98 credit and renew")
        self.assertContains(page, "New money received")
        self.assertNotContains(page, "Total to record · credit")
        self.assertFalse(MembershipCreditRenewalBatch.objects.exists())

    def post_values(self):
        self.family()
        verified_owner_login(self.client, self.owner)
        self.url = reverse("membership_renewals", args=[self.customer.pk])
        data = {
            "renewals-TOTAL_FORMS": "2",
            "renewals-INITIAL_FORMS": "2",
            "renewals-MIN_NUM_FORMS": "0",
            "renewals-MAX_NUM_FORMS": "100",
            "request_key": str(self.key),
            "tender": "credit",
            "action": "review",
        }
        for i, row in enumerate(self.rows):
            data.update(
                {
                    f"renewals-{i}-{key}": str(value)
                    for key, value in (
                        row
                        | dict(
                            kind="subscription" if i == 0 else "unlimited", renew="on", method_id=""
                        )
                    ).items()
                }
            )
        return data

    def test_one_page_post_applies_reviewed_credit_and_redirects_to_saved_receipt(self):
        data = self.post_values()
        before = self.facts()
        response = self.client.post(self.url, data | {"format": "json"})
        self.assertEqual(response.status_code, 200, response.content)
        reviewed = response.json()
        self.assertIn("Apply $57.98 credit", reviewed["button"])
        self.assertEqual(before, self.facts())
        result = self.client.post(
            self.url,
            data
            | dict(
                action="confirm",
                reviewed=reviewed["fingerprint"],
                accepted="on",
                verified_received="on",
            ),
        )
        self.assertEqual(result.status_code, 302, result.content)
        self.assertContains(self.client.get(result.url), "Customer credit applied: $57.98")
        self.assertEqual(self.facts()[1:3], before[1:3])

    def test_deferred_graph_refuses_forged_accepted_terms_or_funding_offer(self):
        from copy import deepcopy

        from core.membership_batch_credit_records import MembershipCreditRenewalPart

        self.family()
        before = self.facts()
        create_part = MembershipCreditRenewalPart.objects.create

        def forged(**values):
            values["funding_offer"] = deepcopy(values["funding_offer"])
            values["funding_offer"]["terms"] += " Forged extra permission."
            return create_part(**values)

        with self.assertRaises(DatabaseError), transaction.atomic():
            with patch.object(MembershipCreditRenewalPart.objects, "create", side_effect=forged):
                self.confirm_batch()
            connection.check_constraints()
        self.assertEqual(self.facts(), before)
        self.assertEqual(balance(self.customer.pk), Decimal("95.94"))

    def test_deferred_graph_refuses_inflated_initial_credit_pool(self):
        from copy import deepcopy

        self.family()
        before = self.facts()
        create_batch = MembershipCreditRenewalBatch.objects.create

        def forged(**values):
            values["facts"] = deepcopy(values["facts"])
            values["facts"]["sources"][0]["remaining"] = "96.94"
            values["facts"]["available_before"] = "96.94"
            values["facts"]["available_after"] = "38.96"
            return create_batch(**values)

        with self.assertRaises(DatabaseError), transaction.atomic():
            with patch.object(MembershipCreditRenewalBatch.objects, "create", side_effect=forged):
                self.confirm_batch()
            connection.check_constraints()
        self.assertEqual(self.facts(), before)

    def test_missing_reviewed_schema_cannot_fall_back_to_receiving_cash(self):
        self.family()
        before = self.facts()
        with patch("core.membership_batch_credit.available", return_value=False):
            with self.assertRaisesMessage(ValidationError, "upgrade first"):
                self.confirm_batch(reviewed="f" * 64)
        self.assertEqual(self.facts(), before)
