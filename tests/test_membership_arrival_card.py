"""Credit-funded membership plus visit card preserves uncertain-payment recovery."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.customer_credit import applied
from core.customer_credit_records import CustomerCreditApplication
from core.membership_arrival import confirm, queue_confirmation, receipt_summary, review
from core.membership_sales import membership_status
from core.models import PaymentOperation
from core.payments import remainders
from core.payments.invoices import received
from core.payments.ledger import record_result
from core.payments.operations import execute, reconcile
from tests import test_membership_arrival as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CreditFundedCardArrivalTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.CombinedMembershipArrivalTests.prepare
    web_data = fixtures.CombinedMembershipArrivalTests.web_data

    def card_visit(self, *, submit=True):
        _, self.credit_source, _, _ = self.conversion(card=True, children=2, adults=2)
        self.play = self.prepare(children=4, places=1, method="card")
        self.options["selection"] = self.selection | {"credit_amount": "17.99"}
        self.accepted = review(**self.options)
        if not submit:
            return
        with self.runtime_role():
            record = confirm(
                **self.options,
                request_key=self.key,
                reviewed_hash=self.accepted["fingerprint"],
                confirmed=True,
                accepted=True,
                verified_received=False,
            )
        self.record = record
        self.operation = record.checkout.sale.operations.get(kind="receipt", tender="card")
        return record

    def final_result(self, state="succeeded"):
        return record_result(
            operation_id=self.operation.pk,
            state=state,
            source="provider",
            provider_reference="981" if state == "succeeded" else "",
        )

    def test_only_visit_is_charged_after_credit_settles_initial_membership(self):
        record = self.card_visit()
        first_sale = record.purchase.installments.first().invoice.sale
        self.assertEqual(applied(first_sale), Decimal("17.99"))
        self.assertEqual(received(first_sale), 0)
        self.assertFalse(first_sale.operations.exists())
        self.assertEqual(membership_status(record.purchase), "active")
        self.assertEqual(self.operation.amount, Decimal("16.47"))
        self.assertEqual(self.operation.state, "ready")
        self.assertEqual(receipt_summary(record)["new_received"], 0)
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )
        self.final_result()
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("New payment received: $16.47", message.text_body)
        self.assertIn("Existing customer credit applied to membership: $17.99", message.text_body)
        self.assertIn("Membership payment received: $0.00", message.text_body)
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("16.47"))
        self.assertEqual(
            received(self.credit_source), self.credit_source.operations.get(kind="receipt").amount
        )

    def test_unknown_outcome_never_repeats_post_or_sends_paid_confirmation(self):
        self.card_visit()
        self.final_result("unknown")
        before = PaymentOperation.objects.count(), CustomerCreditApplication.objects.count()
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertEqual(execute(self.operation.pk).state, "unknown")
            gateway.return_value.charge.assert_not_called()
        with self.assertRaisesMessage(ValidationError, "uncertain"):
            remainders.preview(actor=self.staff, booking_id=self.play.pk, method="cash")
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )
        self.assertEqual(
            before, (PaymentOperation.objects.count(), CustomerCreditApplication.objects.count())
        )
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.transaction.return_value = {
                "id": 981,
                "amount_details": {"amount": str(self.operation.amount)},
                "status_details": {"status": "captured"},
                "transaction_details": {"type": "charge"},
                "custom_fields": {"custom1": str(self.operation.pk), "custom2": "monkeydo:sandbox"},
            }
            result = reconcile(
                operation_id=self.operation.pk, actor=self.owner, provider_reference="981"
            )
            gateway.return_value.charge.assert_not_called()
        self.assertEqual(result.state, "succeeded")
        self.assertEqual(
            before, (PaymentOperation.objects.count(), CustomerCreditApplication.objects.count())
        )
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )

    def test_explicit_cash_after_decline_preserves_credit_and_uses_actual_lower_fee(self):
        self.card_visit()
        self.final_result("declined")
        applications = CustomerCreditApplication.objects.count()
        values = dict(actor=self.staff, booking_id=self.play.pk, method="cash", context="arrival")
        data = remainders.preview(**values)
        remaining = remainders.confirm(
            **values, request_key=uuid.uuid4(), reviewed_hash=data[3], confirmed=True
        )
        self.assertEqual(remaining.sale.operations.get(tender="cash").amount, Decimal("15.99"))
        self.assertEqual(CustomerCreditApplication.objects.count(), applications)
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("New payment received: $15.99", message.text_body)
        self.assertIn("Credit-card processing fee: $0.00", message.text_body)
        self.assertIn("Sales tax: $0.99", message.text_body)

    def test_positive_card_preview_is_read_only_and_credit_is_not_reapplied_on_replay(self):
        self.card_visit(submit=False)
        before = PaymentOperation.objects.count()
        positive = review(**(self.options | {"selection": self.selection}))
        self.assertEqual(positive["facts"]["membership_due"], "18.53")
        self.assertEqual(PaymentOperation.objects.count(), before)
        first = confirm(
            **self.options,
            request_key=self.key,
            reviewed_hash=self.accepted["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=False,
        )
        before = PaymentOperation.objects.count(), CustomerCreditApplication.objects.count()
        again = confirm(
            **self.options,
            request_key=self.key,
            reviewed_hash=self.accepted["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=False,
        )
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(
            before, (PaymentOperation.objects.count(), CustomerCreditApplication.objects.count())
        )

    def test_returned_credit_source_stops_dependent_visit_dispatch_and_new_collection(self):
        self.card_visit()
        self.external_return(self.credit_source.operations.get(kind="receipt"))
        with patch("core.payments.operations.Gateway") as gateway:
            execute(self.operation.pk)
            gateway.return_value.charge.assert_not_called()
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.state, "cancelled")
        self.assertEqual(self.operation.result_code, "changed_before_dispatch")
        with self.assertRaisesMessage(ValidationError, "funding needs owner reconciliation"):
            remainders.preview(actor=self.staff, booking_id=self.play.pk, method="cash")
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )

    def test_pending_status_and_booking_card_do_not_claim_cash_was_received(self):
        self.card_visit()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival_status", args=[self.play.pk, self.record.checkout_id])
        response = self.client.get(url).json()
        self.assertEqual(response["state"], "processing")
        self.assertNotIn("reviewed received payment was recorded", response["message"])
        self.final_result("unknown")
        self.assertEqual(self.client.get(url).json()["state"], "review")
        self.final_result()
        response = self.client.get(url).json()
        self.assertEqual(response["state"], "succeeded")
        self.assertEqual(response["received"], "16.47")
        page = self.client.get(reverse("booking_detail", args=[self.play.pk]))
        self.assertContains(page, "New payment received: $16.47")
        self.assertContains(page, "Existing credit applied to membership: $17.99")

    def test_unsent_combined_email_is_withdrawn_if_visit_funding_changes(self):
        self.card_visit()
        self.final_result()
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        from core.communications.services import claim

        self.external_return(self.operation)
        self.assertIsNone(claim(message.pk))
        message.refresh_from_db()
        self.assertEqual(message.state, "cancelled")
        self.assertEqual(message.code, "combined_payment_changed")

    def test_later_callbacks_do_not_rewrite_the_frozen_confirmation(self):
        self.card_visit()
        self.final_result()
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertEqual(queue_confirmation(self.record).pk, message.pk)
        self.final_result()
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )

    def test_earlier_schema_with_disabled_feature_does_not_read_combined_payment_tables(self):
        from core.membership_arrival import for_sale
        from core.membership_records import MembershipArrivalCheckout

        with (
            override_settings(MEMBERSHIP_SALES_ENABLED=False),
            patch("core.membership_schema.available", return_value=False),
            patch.object(
                MembershipArrivalCheckout.objects,
                "filter",
                side_effect=AssertionError("Combined table should not be read"),
            ),
        ):
            self.assertIsNone(for_sale(uuid.uuid4()))

    def test_contact_refresh_keeps_one_unsent_confirmation_and_can_return_to_prior_address(self):
        from core.communications.services import claim
        from core.models import Customer

        self.card_visit()
        self.final_result()
        original = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        Customer.objects.filter(pk=self.customer.pk).update(email="changed@example.invalid")
        self.assertIsNone(claim(original.pk))
        original.refresh_from_db()
        self.assertEqual(original.state, "cancelled")
        current = MessageDelivery.objects.get(kind="membership_visit_confirmation", state="queued")
        self.assertEqual(current.recipient, "changed@example.invalid")
        Customer.objects.filter(pk=self.customer.pk).update(email=original.recipient)
        self.assertIsNone(claim(current.pk))
        replacement = MessageDelivery.objects.get(
            kind="membership_visit_confirmation", state="queued"
        )
        self.assertEqual(replacement.recipient, original.recipient)
        self.assertNotEqual(replacement.pk, original.pk)

    def test_attempted_or_unknown_combined_email_never_prepares_another_message(self):
        from core.communications.services import claim

        self.card_visit()
        self.final_result()
        original = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        with override_settings(RESEND_API_KEY="fake-not-used-by-claim"):
            self.assertEqual(claim(original.pk).state, "sending")
            self.assertEqual(queue_confirmation(self.record).pk, original.pk)
            self.assertIsNone(claim(original.pk))
        original.refresh_from_db()
        self.assertEqual(original.state, "unknown")
        self.assertEqual(queue_confirmation(self.record).pk, original.pk)
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )

    def test_later_installment_does_not_count_as_new_money_in_original_combined_email(self):
        from core.communications.services import claim
        from core.date_display import display_date
        from core.membership_payments import collect_installment, payment_review

        self.card_visit()
        self.final_result()
        original = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        member = self.record.purchase
        item = member.installments.get(number=2)
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            values = dict(
                actor=self.staff, member_id=member.pk, installment_id=item.pk, tender="cash"
            )
            data = payment_review(**values)
            collect_installment(
                **values,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                confirmed=True,
                verified_received=True,
            )
            self.assertIsNone(claim(original.pk))
        original.refresh_from_db()
        self.assertEqual(original.state, "cancelled")
        refreshed = MessageDelivery.objects.get(
            kind="membership_visit_confirmation", state="queued"
        )
        self.assertIn("New payment received: $16.47", refreshed.text_body)
        self.assertIn("Membership payment received: $0.00", refreshed.text_body)
        third = member.installments.get(number=3)
        self.assertIn(
            f"Your next scheduled membership payment is ${third.quote['total']} on {display_date(third.due_on, 'F j, Y')}",
            refreshed.text_body,
        )

    def test_same_page_card_preview_requires_no_cash_receipt_acknowledgment(self):
        self.card_visit(submit=False)
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        initial = self.client.get(url)
        values = self.web_data(self.play) | {
            "arrival_draft": initial.context["arrival_draft"],
            "member_credit": "17.99",
        }
        values.pop("member_received")
        before = PaymentOperation.objects.count(), CustomerCreditApplication.objects.count()
        response = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["can_confirm"])
        self.assertIn("charge card $16.47", response.json()["label"])
        self.assertIn("Card to charge today", response.json()["html"])
        self.assertEqual(
            before, (PaymentOperation.objects.count(), CustomerCreditApplication.objects.count())
        )

    def test_complimentary_membership_keeps_visit_charge_and_owner_email_choice_separate(self):
        self.prepare(children=3, places=1, method="card")
        options = self.options | {
            "actor": self.owner,
            "selection": self.selection | {"comped": True},
            "method_id": None,
        }
        accepted = review(**options)
        record = confirm(
            **options,
            request_key=self.key,
            reviewed_hash=accepted["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=False,
            send_confirmation=False,
        )
        self.assertIsNone(record.purchase.billing_state.mandate_id)
        self.assertFalse(record.purchase.installments.exists())
        operation = record.checkout.sale.operations.get()
        self.assertEqual(operation.amount, Decimal("32.94"))
        record_result(
            operation_id=operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="984",
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("32.94"))
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )
