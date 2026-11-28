"""One verified renewal checkout preserves each original cohort and receipt."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from core.communications.models import MessageDelivery
from core.communications.services import claim
from core.membership_batch_records import MembershipRenewalBatch, MembershipRenewalBatchPart
from core.membership_batch_renewals import confirm, queue_confirmation, review
from core.membership_records import MembershipPurchase
from core.membership_renewals import remaining_places
from core.models import FinancialPosting, MembershipPricing, PaymentOperation
from tests import test_membership_renewals as fixtures
from tests.test_membership_initial_credit import SETTINGS
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CombinedRenewalTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipRenewalTests.setUp
    buy = fixtures.MembershipRenewalTests.buy
    prior = fixtures.MembershipRenewalTests.prior
    follow = fixtures.MembershipRenewalTests.follow
    follow_values = fixtures.MembershipRenewalTests.follow_values

    def family(self):
        self.first = self.prior(places=2)
        self.second = self.prior(kind="unlimited", places=1)
        self.rows = [
            dict(prior_id=self.first.pk, places=1, months=1, billing="prepaid"),
            dict(prior_id=self.second.pk, places=1, months=1, billing="prepaid"),
        ]
        self.key = uuid.uuid4()
        return self.rows

    def review(self, **changes):
        return review(
            **(
                dict(actor=self.staff, customer=self.customer, rows=self.rows, tender="cash")
                | changes
            )
        )

    def confirm(self, **changes):
        values = dict(
            actor=self.staff,
            customer=self.customer,
            rows=self.rows,
            tender="cash",
            request_key=self.key,
            reviewed=changes.get("reviewed") or self.review()["fingerprint"],
            accepted=True,
            verified_received=True,
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
                MembershipRenewalBatch,
            )
        )

    def test_preview_does_not_create_purchase_receipt_or_committed_places(self):
        self.family()
        before = self.facts()
        data = self.review()
        self.assertEqual(data["amount"], "57.98")
        self.assertEqual(
            [r["offer"]["starts_on"] for r in data["lines"]], ["2028-01-31", "2028-01-31"]
        )
        self.assertEqual(before, self.facts())
        self.assertEqual(remaining_places(self.first), 2)

    def test_two_types_one_received_total_separate_terms_and_single_confirmation(self):
        self.family()
        before = self.facts()
        with (
            patch("core.payments.operations.Gateway") as provider,
            patch("core.payments.setup.Gateway") as storage,
        ):
            batch = self.confirm()
        parts = list(batch.parts.select_related("purchase__membership").order_by("position"))
        self.assertEqual(batch.amount, Decimal("57.98"))
        self.assertEqual([p.purchase.membership.kind for p in parts], ["subscription", "unlimited"])
        self.assertEqual(
            [p.purchase.origin.prior_id for p in parts], [self.first.pk, self.second.pk]
        )
        self.assertTrue(
            all(p.purchase.installments.first().quote["processing_fee"] == "0.00" for p in parts)
        )
        self.assertEqual(tuple(n - o for n, o in zip(self.facts(), before)), (2, 2, 2, 1, 1))
        msg = batch.messages.get().message
        self.assertIn("$57.98 was received", msg.text_body)
        self.assertIn("Subscription Membership", msg.text_body)
        self.assertIn("Unlimited Membership", msg.text_body)
        self.assertEqual(msg.kind, "membership_renewal")
        self.assertFalse(
            MessageDelivery.objects.filter(
                dedupe_key__in=[f"membership-confirmation:{p.purchase.pk}" for p in parts]
            ).exists()
        )
        provider.assert_not_called()
        storage.assert_not_called()
        connection.check_constraints()

    def test_same_source_may_renew_two_places_with_different_types(self):
        self.family()
        self.rows[1] |= dict(prior_id=self.first.pk, kind="unlimited")
        batch = self.confirm(tender="check", reviewed=self.review(tender="check")["fingerprint"])
        self.assertEqual(remaining_places(self.first), 0)
        self.assertEqual(remaining_places(self.second), 1)
        self.assertEqual(batch.parts.count(), 2)
        self.assertEqual(
            {p.purchase.membership.kind for p in batch.parts.all()}, {"subscription", "unlimited"}
        )
        connection.check_constraints()

    def test_total_same_source_selection_cannot_exceed_remaining_places(self):
        self.family()
        self.rows[0]["places"] = 2
        self.rows[1]["prior_id"] = self.first.pk
        before = self.facts()
        with self.assertRaisesMessage(ValidationError, "combined selection"):
            self.review()
        self.assertEqual(self.facts(), before)

    def test_duplicate_confirm_returns_original_after_capacity_has_been_committed(self):
        self.family()
        reviewed = self.review()["fingerprint"]
        batch = self.confirm(reviewed=reviewed)
        before = self.facts()
        again = self.confirm(reviewed=reviewed)
        self.assertEqual(batch.pk, again.pk)
        self.assertEqual(before, self.facts())

    def test_acceptance_and_actual_receipt_must_be_explicit_true(self):
        self.family()
        before = self.facts()
        for changed in [
            dict(accepted=False),
            dict(verified_received=False),
            dict(accepted=1),
            dict(verified_received=1),
        ]:
            with self.subTest(changed=changed), self.assertRaises(ValidationError):
                self.confirm(**changed)
        self.assertEqual(before, self.facts())

    def test_other_tenders_cannot_be_reported_as_received_in_combined_checkout(self):
        self.family()
        for tender in ["card", "zelle", "gift_card", "split"]:
            with self.subTest(tender=tender), self.assertRaises(ValidationError):
                self.review(tender=tender)

    def test_price_change_requires_a_new_whole_checkout_review(self):
        self.family()
        reviewed = self.review()["fingerprint"]
        before = self.facts()
        MembershipPricing.objects.create(subscription="20.00", unlimited="44.00", actor=self.owner)
        with self.assertRaisesMessage(ValidationError, "changed"):
            self.confirm(reviewed=reviewed)
        self.assertEqual(before, self.facts())

    def test_customer_contact_change_requires_review(self):
        self.family()
        reviewed = self.review()["fingerprint"]
        before = self.facts()
        type(self.customer).objects.filter(pk=self.customer.pk).update(
            email="changed@example.invalid"
        )
        with self.assertRaisesMessage(ValidationError, "changed"):
            self.confirm(reviewed=reviewed)
        self.assertEqual(before, self.facts())

    def test_second_purchase_error_rolls_back_every_new_receipt_and_confirmation(self):
        self.family()
        before = self.facts()
        from core.membership_sales import purchase

        calls = []

        def create(**values):
            calls.append(values)
            if len(calls) == 2:
                raise ValidationError("Simulated second renewal issue")
            return purchase(**values)

        with (
            patch("core.membership_batch_renewals.purchase", side_effect=create),
            self.assertRaisesMessage(ValidationError, "second renewal"),
        ):
            self.confirm()
        self.assertEqual(before, self.facts())
        self.assertEqual(remaining_places(self.first), 2)

    def test_monthly_rows_keep_their_separate_saved_card_schedules(self):
        self.family()
        for row in self.rows:
            row |= dict(months=3, billing="monthly", method_id=str(self.method.pk))
        data = self.review()
        batch = self.confirm(reviewed=data["fingerprint"])
        self.assertEqual(batch.amount, Decimal("57.98"))
        for part in batch.parts.select_related("purchase__billing_state"):
            self.assertEqual(part.purchase.installments.count(), 3)
            self.assertEqual(part.purchase.billing_state.mandate.method_id, self.method.pk)
        self.assertEqual(batch.messages.count(), 1)
        self.assertEqual(
            batch.messages.get().message.text_body.count("next scheduled membership payment"), 2
        )
        connection.check_constraints()

    def test_monthly_card_must_be_current_and_owned_by_the_customer(self):
        self.family()
        self.rows[0] |= dict(billing="monthly", method_id=str(uuid.uuid4()))
        with self.assertRaisesMessage(ValidationError, "current saved card"):
            self.review()

    def test_other_customer_cohort_is_rejected_before_any_checkout_write(self):
        self.family()
        from core.models import Customer

        other = Customer.objects.create(
            last_name="Other", phone="2025550188", email="other@example.invalid"
        )
        with self.assertRaisesMessage(ValidationError, "belonging to this customer"):
            self.review(customer=other)

    def test_group_message_checks_every_cohorts_funding_before_claim(self):
        self.family()
        batch = self.confirm()
        message = batch.messages.get().message
        second = batch.parts.order_by("position").last().purchase
        with patch(
            "core.membership_funding.member_needs_review",
            side_effect=lambda member: member.pk == second.pk,
        ):
            self.assertIsNone(claim(message.pk))
        message.refresh_from_db()
        self.assertEqual((message.state, message.code), ("cancelled", "membership_batch_changed"))

    def test_contact_change_queues_one_current_combined_message_and_preserves_history(self):
        self.family()
        batch = self.confirm()
        old = batch.messages.get().message
        type(self.customer).objects.filter(pk=self.customer.pk).update(email="new@example.invalid")
        self.assertIsNone(claim(old.pk))
        old.refresh_from_db()
        self.assertEqual(old.state, "cancelled")
        new = batch.messages.exclude(message=old).get().message
        self.assertEqual(new.recipient, "new@example.invalid")
        self.assertEqual(new.text_body.count("Begins:"), 2)
        self.assertEqual(queue_confirmation(batch).pk, new.pk)
        self.assertEqual(batch.messages.count(), 2)
        connection.check_constraints()

    def test_runtime_role_can_confirm_but_cannot_update_checkout_facts(self):
        self.family()
        with self.runtime_role():
            batch = self.confirm()
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE core_membershiprenewalbatch SET amount=1 WHERE id=%s", [batch.pk]
                    )
            connection.check_constraints()

    def test_direct_mismatched_part_cannot_commit_as_extra_received_money(self):
        self.family()
        batch = self.confirm()
        part = batch.parts.first()
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipRenewalBatchPart.objects.create(
                batch=batch,
                position=3,
                prior=self.first,
                purchase_id=uuid.uuid4(),
                amount="1.00",
                facts=part.facts,
            )
            connection.check_constraints()

    def test_preview_rejects_unreviewed_keys_and_nonmembership_identifiers(self):
        self.family()
        for row in [dict(prior_id=True), dict(prior_id=self.first.pk, paid_visit_id=1)]:
            with self.subTest(row=row), self.assertRaises(ValidationError):
                self.review(rows=[row])

    def test_staff_without_collection_authority_cannot_confirm_or_review(self):
        self.family()
        self.staff.user_permissions.clear()
        self.staff.groups.clear()
        from django.contrib.auth import get_user_model

        actor = get_user_model().objects.get(pk=self.staff.pk)
        with self.assertRaises(PermissionDenied):
            self.review(actor=actor)

    def test_paused_email_keeps_existing_received_money_and_prepared_history(self):
        self.family()
        batch = self.confirm()
        before = self.facts()
        with override_settings(BOOKING_EMAIL_ENABLED=False):
            self.assertIsNone(queue_confirmation(batch))
            with self.assertRaises(ValidationError):
                self.confirm(request_key=uuid.uuid4())
        self.assertEqual(self.facts(), before)
        self.assertEqual(batch.parts.count(), 2)
        self.assertEqual(PaymentOperation.objects.count(), 4)
        self.assertEqual(batch.messages.count(), 1)
        self.assertTrue(batch.facts["terms_accepted"])
        self.assertTrue(batch.facts["verified_received"])
        connection.check_constraints()

    def test_zero_value_renewal_is_not_presented_as_a_received_cash_allocation(self):
        self.family()
        MembershipPricing.objects.create(subscription="0.00", unlimited="39.99", actor=self.owner)
        before = self.facts()
        with self.assertRaisesMessage(ValidationError, "positive received payment"):
            self.review()
        self.assertEqual(before, self.facts())
