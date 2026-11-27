"""Arrival credit pays an invoice without pretending money was received again."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.customer_credit import applied, balance
from core.customer_credit_records import CustomerCreditAllocation, CustomerCreditApplication
from core.models import BookingCheckout, FinancialPosting, PaymentOperation
from core.payments.checkout import confirm, preview, summary
from core.payments.invoices import received, settled, total
from core.payments.ledger import record_result
from core.payments.operations import begin_dispatch
from core.payments.remainders import confirm as confirm_remaining
from core.payments.remainders import preview as preview_remaining
from core.payments.zelle import record_receipt
from core.public_booking import review_quote, submit_booking
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class VisitCreditTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    def prepare(self, *, value="10.00", method="card", supervised=False, socks=0):
        self.original, self.original_sale, self.member_record, _ = self.conversion(card=True)
        if supervised:
            flow = self.ready()
            flow["details"].update(supervised=True, adults=0)
            flow["quote"] = review_quote(flow, flow["details"])
            self.play = submit_booking(flow)
            self.flow_data = flow
        else:
            original_ready = self.ready

            def save_flow():
                self.flow_data = original_ready()
                return self.flow_data

            with patch.object(self, "ready", side_effect=save_flow):
                self.play = self.booking(children=2)
        self.inputs = self.arrival_inputs(self.play, method=method, visit_credit=value, socks=socks)
        self.options = dict(
            actor=self.staff, booking_id=self.play.pk, kind="arrival", data=self.inputs
        )
        self.key = uuid.uuid4()
        return preview(**self.options)

    def complete(self, *, reviewed=None, **changes):
        return confirm(
            **(self.options | changes),
            request_key=self.key,
            reviewed_hash=reviewed or preview(**(self.options | changes))[-1],
            confirmed=True,
        )

    def test_partial_credit_conserves_source_money_and_charges_only_its_card_remainder_once(self):
        data = self.prepare()
        self.assertEqual(data[2]["total"], "16.17")
        self.assertEqual(data[4]["credit"]["amount"], "10.00")
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        self.assertFalse(CustomerCreditApplication.objects.exists())
        with self.runtime_role():
            record = self.complete()
            self.assertEqual(self.complete(reviewed=record.fingerprint).pk, record.pk)
        self.assertEqual(PaymentOperation.objects.count(), before[0] + 1)
        self.assertEqual(FinancialPosting.objects.count(), before[1])
        self.assertEqual(applied(record.sale), Decimal("10.00"))
        self.assertEqual(received(record.sale), 0)
        self.assertEqual(balance(self.customer.pk), Decimal("6.02"))
        self.assertEqual(CustomerCreditApplication.objects.get().booking_checkout_id, record.pk)
        card = record.sale.operations.get()
        self.play.card_agreement.refresh_from_db()
        self.assertIsNone(self.play.card_agreement.resolved_at)
        self.assertEqual((card.tender, card.amount), ("card", Decimal("6.17")))
        self.assertEqual(received(self.original_sale), Decimal("16.47"))
        self.assertEqual(total(self.original_sale), Decimal("0.45"))
        self.assertEqual(settled(self.original_sale), Decimal("0.45"))
        self.assertEqual(
            sum(
                Decimal(row["item_tax"])
                for row in CustomerCreditAllocation.objects.get().allocation
            ),
            Decimal("0.62"),
        )
        record_result(
            operation_id=card.pk, state="succeeded", source="provider", provider_reference="441083"
        )
        self.assertEqual(received(record.sale), Decimal("6.17"))
        self.assertEqual(settled(record.sale), Decimal("16.17"))
        self.assertEqual(summary(self.play)["due"], 0)
        self.play.card_agreement.refresh_from_db()
        self.assertIsNotNone(self.play.card_agreement.resolved_at)

    def test_full_credit_does_not_create_a_receipt_or_require_an_active_card(self):
        self.prepare(value="15.99")
        method = self.play.card_agreement.method
        method.state = "inactive"
        method.save(update_fields=["state"])
        count = PaymentOperation.objects.count()
        record = self.complete()
        self.assertFalse(record.sale.operations.exists())
        self.assertEqual(PaymentOperation.objects.count(), count)
        self.assertEqual(received(record.sale), 0)
        self.assertEqual(settled(record.sale), Decimal("15.99"))
        self.assertEqual(balance(self.customer.pk), Decimal("0.03"))
        self.play.card_agreement.refresh_from_db()
        self.assertIsNotNone(self.play.card_agreement.resolved_at)

    def test_cash_remainder_is_actual_new_money_separate_from_credit(self):
        from core.payments.methods import outstanding

        self.prepare(method="cash")
        record = self.complete()
        self.assertEqual(applied(record.sale), 10)
        self.assertEqual(received(record.sale), Decimal("5.99"))
        self.assertEqual(record.sale.operations.get().tender, "cash")
        self.assertEqual(summary(self.play)["total_received"], Decimal("5.99"))
        self.play.card_agreement.refresh_from_db()
        self.assertIsNotNone(self.play.card_agreement.resolved_at)
        self.assertFalse(outstanding(self.play.card_agreement.method))
        self.assertTrue(outstanding(self.member_record.billing_state.mandate.method))

    def test_supervised_credit_preserves_ordinary_free_quota_and_fees_only_card_remainder(self):
        from core.membership_reservations import summary_for

        self.prepare(supervised=True)
        before = summary_for(self.member_record)["available"]
        record = self.complete()
        self.assertEqual(total(record.sale), Decimal("15.34"))
        self.assertEqual(record.sale.operations.get().amount, Decimal("5.34"))
        self.assertEqual(applied(record.sale), 10)
        self.assertEqual(summary_for(self.member_record)["available"], before)

    def test_credit_includes_nontaxable_socks_without_creating_another_receipt(self):
        self.prepare(socks=1, method="cash")
        record = self.complete()
        self.assertEqual(total(record.sale), Decimal("17.98"))
        self.assertEqual(received(record.sale), Decimal("7.98"))
        self.assertEqual(applied(record.sale), 10)
        self.assertEqual(record.sale.lines.get(category="socks").item_tax, 0)

    def test_new_gift_or_bank_remainder_requires_its_own_verified_actual_receipt(self):
        self.prepare(method="gift_card")
        with self.assertRaisesMessage(ValidationError, "physical gift card"):
            self.complete()
        self.inputs.update(
            method="split", split={"zelle": "5.99"}, zelle_sender="Fictional visit sender"
        )
        with self.assertRaisesMessage(ValidationError, "business bank account"):
            self.complete()
        self.inputs["zelle_verified"] = True
        record = self.complete()
        self.assertEqual(record.sale.operations.get().tender, "zelle")
        self.assertEqual(received(record.sale), Decimal("5.99"))

    def test_full_credit_does_not_claim_a_gift_receipt_when_that_method_has_no_remainder(self):
        self.prepare(method="gift_card", value="15.99")
        record = self.complete()
        self.assertFalse(record.sale.operations.exists())
        self.assertEqual(summary(self.play)["status"], "Covered by customer credit")

    def test_existing_bank_receipt_applies_before_credit_without_another_incoming_transfer(self):
        self.prepare(value="5.99")
        record_receipt(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            value="10.00",
            sender_name="Fictional visit sender",
            verified=True,
        )
        record = self.complete()
        self.assertEqual(applied(record.sale), Decimal("5.99"))
        self.assertEqual(record.sale.operations.count(), 1)
        self.assertTrue(hasattr(record.sale.operations.get(), "zelle_application"))
        self.assertEqual(received(record.sale), Decimal("10.00"))
        self.assertEqual(settled(record.sale), Decimal("15.99"))

    def test_excess_credit_or_changed_source_cannot_save_arrival(self):
        old = self.prepare()[-1]
        self.inputs["visit_credit"] = "16.03"
        with self.assertRaises(ValidationError):
            self.complete()
        self.inputs["visit_credit"] = "10.00"
        from core.customer_credit_corrections import correct
        from core.customer_credit_corrections import review as review_correction

        facts = review_correction(
            actor=self.owner,
            customer_id=self.customer.pk,
            kind="remove",
            value="1.00",
        )
        correct(
            actor=self.owner,
            customer_id=self.customer.pk,
            kind="remove",
            value="1.00",
            reason="Fictional correction",
            request_key=uuid.uuid4(),
            reviewed=facts["fingerprint"],
            confirmed=True,
        )
        with self.assertRaisesMessage(ValidationError, "changed"):
            self.complete(reviewed=old)
        self.play.refresh_from_db()
        self.assertEqual(self.play.attendance, "")

    def test_unknown_result_blocks_another_collection_and_source_hold_stops_unstarted_dispatch(
        self,
    ):
        self.prepare()
        record = self.complete()
        card = record.sale.operations.get()
        self.external_return(self.original_sale.operations.get(kind="receipt"))
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertIsNone(begin_dispatch(card.pk))
            gateway.assert_not_called()
        card.refresh_from_db()
        self.assertEqual(card.state, "cancelled")
        with self.assertRaisesMessage(ValidationError, "source"):
            preview_remaining(actor=self.staff, booking_id=self.play.pk, method="cash")

    def test_declined_remainder_resolves_only_unpaid_amount_and_removes_unused_card_fee(self):
        self.prepare()
        record = self.complete()
        card = record.sale.operations.get()
        record_result(
            operation_id=card.pk, state="declined", source="provider", provider_reference="441084"
        )
        options = dict(actor=self.staff, booking_id=self.play.pk, method="cash", context="arrival")
        proposed = preview_remaining(**options)
        self.assertEqual(proposed[2]["amount"], "5.99")
        confirm_remaining(
            **options,
            request_key=uuid.uuid4(),
            reviewed_hash=proposed[3],
            confirmed=True,
        )
        self.assertEqual(applied(record.sale), 10)
        self.assertEqual(received(record.sale), Decimal("5.99"))
        self.assertEqual(total(record.sale), Decimal("15.99"))

    def test_late_failure_rolls_back_credit_usage_and_arrival(self):
        self.prepare()
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with (
            patch("core.payments.checkout.enqueue", side_effect=ValidationError("late failure")),
            self.assertRaisesMessage(ValidationError, "late failure"),
        ):
            self.complete()
        self.play.refresh_from_db()
        self.assertEqual(self.play.attendance, "")
        self.assertFalse(CustomerCreditApplication.objects.exists())
        self.assertEqual(balance(self.customer.pk), Decimal("16.02"))
        self.assertEqual(
            (PaymentOperation.objects.count(), FinancialPosting.objects.count()), before
        )

    def test_visit_applications_and_allocations_are_immutable_and_uniquely_bound_to_arrival(self):
        self.prepare()
        record = self.complete()
        application = CustomerCreditApplication.objects.get()
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_customercreditapplication SET amount=1 WHERE id=%s", [application.pk]
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            CustomerCreditApplication.objects.create(
                id=uuid.uuid4(),
                booking_checkout=record,
                customer=self.customer,
                sale=record.sale,
                amount="10.00",
                actor=self.staff,
                fingerprint="duplicate",
                details=application.details,
            )
        self.assertEqual(BookingCheckout.objects.filter(booking=self.play).count(), 1)

    def test_sql_guard_rejects_tax_or_processing_fee_outside_accepted_components(self):
        self.prepare()
        create = CustomerCreditAllocation.objects.create
        for values in (
            {"net": "0.00", "fee": "0.00", "item_tax": "10.00", "fee_tax": "0.00"},
            {"net": "9.50", "fee": "0.01", "item_tax": "0.50", "fee_tax": "0.00"},
            {"net": "9.999", "fee": "0.00", "item_tax": "0.001", "fee_tax": "0.00"},
        ):

            def invalid(**kwargs):
                kwargs["allocation"] = [kwargs["allocation"][-1] | values]
                return create(**kwargs)

            with (
                self.subTest(values=values),
                patch(
                    "core.visit_credit.CustomerCreditAllocation.objects.create", side_effect=invalid
                ),
                self.assertRaises(DatabaseError),
            ):
                self.complete()
        self.assertFalse(CustomerCreditApplication.objects.exists())
        self.assertEqual(balance(self.customer.pk), Decimal("16.02"))

    def test_same_page_review_confirmation_status_and_customer_history_show_credit_separately(self):
        self.prepare(value="15.99", method="gift_card")
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        initial = self.client.get(url)
        values = self.inputs | {
            "waiver_confirmed": "yes",
            "request_key": str(self.key),
            "version": self.play.edit_version,
            "arrival_draft": initial.context["arrival_draft"],
        }
        excess = self.client.post(
            url, values | {"visit_credit": "100.00", "children": 3}, HTTP_ACCEPT="application/json"
        )
        self.assertEqual(excess.status_code, 400)
        self.assertEqual(excess.json()["credit_available"], "16.02")
        self.assertEqual(excess.json()["noncard_total"], "31.98")
        self.assertFalse(excess.json()["can_confirm"])
        self.assertFalse(CustomerCreditApplication.objects.exists())
        proposed = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(proposed.status_code, 200, proposed.content)
        self.assertTrue(proposed.json()["can_confirm"])
        self.assertEqual(proposed.json()["credit_available"], "16.02")
        self.assertIn("apply $15.99 credit", proposed.json()["label"])
        self.assertIn("Existing customer credit to apply", proposed.json()["html"])
        final = self.client.post(
            url,
            values | {"confirm_review": "1", "reviewed_hash": proposed.json()["hash"]},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(final.status_code, 200, final.content)
        status = self.client.get(final.json()["status_url"]).json()
        self.assertEqual(status["received"], "0.00")
        self.assertEqual(status["credit_applied"], "15.99")
        self.assertIn("no new payment", status["message"])
        detail = self.client.get(reverse("booking_detail", args=[self.play.pk]))
        self.assertContains(detail, "Existing customer credit applied: $15.99")
        self.assertContains(detail, "Total received: $0.00")
        customer = self.client.get(reverse("customer_detail", args=[self.customer.pk]))
        self.assertContains(customer, f"Visit #{self.play.pk}")
        from core.public_booking_views import SESSION_KEY

        public = Client()
        session = public.session
        session[SESSION_KEY] = self.flow_data | {"stage": "done", "booking_id": self.play.pk}
        session.save()
        receipt = public.get(reverse("customer_booking_receipt"))
        self.assertContains(receipt, "Existing customer credit applied: $15.99")
        self.assertContains(receipt, "No remaining visit payment is due.")
        self.assertContains(receipt, "Reviewed visit total")
        self.assertNotContains(receipt, "Your payment will be processed upon arrival")

    def test_credit_draft_survives_card_navigation_without_spending_funds(self):
        self.prepare()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        initial = self.client.get(url)
        token = initial.context["arrival_draft"]
        values = self.inputs | {"arrival_draft": token, "continue_to": "card"}
        response = self.client.post(url, values)
        self.assertEqual(response.status_code, 302)
        resumed = self.client.get(url, {"draft": token})
        self.assertEqual(resumed.context["form"]["visit_credit"].value(), "10.00")
        self.assertFalse(CustomerCreditApplication.objects.exists())

    def test_held_or_disabled_feature_credit_cannot_be_spent(self):
        self.prepare()
        with override_settings(MEMBERSHIP_SALES_ENABLED=False), self.assertRaises(ValidationError):
            self.complete()
        self.external_return(self.original_sale.operations.get(kind="receipt"))
        with self.assertRaises(ValidationError):
            self.complete()
        self.assertFalse(CustomerCreditApplication.objects.exists())

    def test_booking_cashier_can_redeem_existing_funds_without_membership_sale_permission(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission

        self.prepare(value="15.99")
        clerk = get_user_model().objects.create_user(username="credit-cashier", is_staff=True)
        clerk.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core",
                codename__in=["view_booking", "change_booking", "view_customer", "collect_payment"],
            )
        )
        self.assertFalse(clerk.has_perm("core.add_membershippurchase"))
        self.options["actor"] = clerk
        with self.runtime_role():
            record = self.complete()
        self.assertEqual(record.actor_id, clerk.pk)
        self.assertEqual(applied(record.sale), Decimal("15.99"))

    def test_cancellation_fee_and_combined_new_purchase_cannot_silently_consume_admission_credit(
        self,
    ):
        self.prepare()
        for change in ({"children": 1}, {"member_add": True}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.complete(data=self.inputs | change)
        with self.assertRaises(ValidationError):
            preview(
                **(
                    self.options
                    | {"kind": "cancellation", "data": self.inputs | {"charge_fee": True}}
                )
            )
        self.assertFalse(CustomerCreditApplication.objects.exists())
        self.assertEqual(balance(self.customer.pk), Decimal("16.02"))

    def test_unknown_card_remainder_cannot_repeat_or_be_replaced_by_cash(self):
        self.prepare()
        record = self.complete()
        card = record.sale.operations.get()
        record_result(operation_id=card.pk, state="unknown", source="provider")
        with self.assertRaisesMessage(ValidationError, "uncertain"):
            preview_remaining(actor=self.staff, booking_id=self.play.pk, method="cash")
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertIsNone(begin_dispatch(card.pk))
            gateway.assert_not_called()
        self.assertEqual(self.complete(reviewed=record.fingerprint).pk, record.pk)
        self.assertEqual(record.sale.operations.count(), 1)
