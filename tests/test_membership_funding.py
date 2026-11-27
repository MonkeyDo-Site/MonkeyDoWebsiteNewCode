"""Provider-return evidence blocks new work without rewriting accepted facts."""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.communications.services import deliver
from core.customer_credit import review as credit_review
from core.membership_cancellations import review as cancellation_review
from core.membership_funding import member_needs_review, sale_needs_review
from core.membership_payments import collect_installment, payment_review
from core.membership_renewals import renewal_details
from core.membership_reporting import reporting_members
from core.membership_reservations import payment_current
from core.membership_sales import installment_paid, membership_status
from core.models import FinancialPosting, PaymentEvent, PaymentFollowup, ProviderObservation
from core.payments.corrections import record_correction
from core.payments.invoices import received
from core.payments.ledger import record_result
from core.payments.operations import execute
from tests import test_membership_reservations as reservations
from tests import test_membership_sales as fixtures
from tests.test_membership_renewals import clock
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class MembershipFundingTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    booking = reservations.MembershipReservationTests.booking
    quote = reservations.MembershipReservationTests.quote
    assign = reservations.MembershipReservationTests.assign

    def succeed(self, member):
        original = fixtures.MembershipPurchaseTests.succeed(self, member)
        original.refresh_from_db()
        return original

    def report_return(self, original, *, reference="999", status="external_credit", value="1.00"):
        ProviderObservation.objects.create(
            operation=original,
            fingerprint=uuid.uuid4().hex,
            provider_reference=reference,
            provider_status=status,
            amount=value,
        )
        PaymentEvent.objects.create(
            operation=original,
            state=original.state,
            source="provider",
            code="external_correction_review",
        )

    def test_direct_return_pauses_benefits_and_renewal_without_repricing_saved_bookings(self):
        member = self.buy(billing="prepaid")
        original = self.succeed(member)
        existing = self.booking()
        quote = self.quote(existing)
        self.assign(existing, quote=quote)
        waiting = self.booking(date(2027, 11, 2))
        waiting_quote = self.quote(waiting)
        snapshot = quote.snapshot
        assignments = list(existing.membership_benefits.values_list("pk", "current__status"))
        self.report_return(original)

        self.assertFalse(installment_paid(member.installments.first()))
        self.assertFalse(payment_current(member))
        self.assertEqual(membership_status(member), "review")
        self.assertEqual(reporting_members().get(pk=member.pk).report_status, "review")
        with self.assertRaisesMessage(ValidationError, "original membership payment"):
            renewal_details(member)
        with self.assertRaises(ValidationError):
            self.assign(waiting, quote=waiting_quote)
        self.assertEqual(
            list(existing.membership_benefits.values_list("pk", "current__status")), assignments
        )
        quote.refresh_from_db()
        self.assertEqual(quote.snapshot, snapshot)
        self.assertEqual(received(original.sale), Decimal("111.18"))
        self.assertEqual(FinancialPosting.objects.count(), 1)
        self.assertEqual(self.quote(waiting).snapshot["lines"][0]["unit_price"], "15.00")

    def test_return_on_earlier_installment_blocks_later_receipt_and_credit_allocation(self):
        member = self.buy()
        original = self.succeed(member)
        later = member.installments.get(number=2)
        self.report_return(original)
        with clock(date(2027, 11, 30)):
            for tender in ("card", "cash", "check", "zelle"):
                with (
                    self.subTest(tender=tender),
                    self.assertRaisesMessage(ValidationError, "source needs owner reconciliation"),
                ):
                    payment_review(
                        actor=self.staff,
                        member_id=member.pk,
                        installment_id=later.pk,
                        tender=tender,
                    )
            with self.assertRaisesMessage(ValidationError, "source needs owner reconciliation"):
                credit_review(actor=self.staff, member_id=member.pk, installment_id=later.pk)
        self.assertFalse(hasattr(later, "invoice"))
        self.assertEqual(member.installments.first().invoice.sale.operations.count(), 1)

    def test_late_return_cancels_queued_later_charge_before_provider_dispatch(self):
        member = self.buy()
        original = self.succeed(member)
        later = member.installments.get(number=2)
        with clock(date(2027, 11, 30)):
            values = dict(
                actor=self.staff, member_id=member.pk, installment_id=later.pk, tender="card"
            )
            quote = payment_review(**values)
            queued = collect_installment(
                **values, reviewed=quote["fingerprint"], request_key=uuid.uuid4(), confirmed=True
            )
            self.report_return(original)
            with self.runtime_role(), patch("core.payments.operations.Gateway") as gateway:
                self.assertEqual(execute(queued.operation_id).state, "cancelled")
                gateway.return_value.charge.assert_not_called()
                gateway.return_value.transaction.assert_not_called()
        self.assertEqual(FinancialPosting.objects.count(), 1)
        self.assertEqual(received(original.sale), original.amount)

    def test_contradictory_return_on_declined_original_blocks_an_already_queued_retry(self):
        member = self.buy()
        item = member.installments.first()
        original = item.invoice.sale.operations.get()
        record_result(operation_id=original.pk, state="declined", source="provider")
        values = dict(actor=self.staff, member_id=member.pk, installment_id=item.pk, tender="card")
        quote = payment_review(**values)
        retry = collect_installment(
            **values, reviewed=quote["fingerprint"], request_key=uuid.uuid4(), confirmed=True
        )
        self.report_return(original, status="returned", value=str(original.amount))
        self.assertEqual(membership_status(member), "review")
        self.assertEqual(reporting_members().get(pk=member.pk).report_status, "review")
        with self.assertRaisesMessage(ValidationError, "return that still needs recording"):
            cancellation_review(actor=self.owner, member_id=member.pk)
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertEqual(execute(retry.operation_id).state, "cancelled")
            gateway.return_value.charge.assert_not_called()
            gateway.return_value.transaction.assert_not_called()
        self.assertFalse(FinancialPosting.objects.exists())

    def test_recorded_return_clears_review_without_claiming_the_short_installment_is_paid(self):
        member = self.buy()
        original = self.succeed(member)
        self.report_return(original)
        row = original.allocation[0] | dict(net="1.00", fee="0.00", item_tax="0.00", fee_tax="0.00")
        evidence = dict(
            id="999",
            amount_details=dict(amount="1.00"),
            transaction_details=dict(type="credit", reference_number=original.provider_reference),
            status_details=dict(status="settled"),
        )
        with patch("core.payments.corrections.Gateway") as gateway:
            gateway.return_value.transaction.return_value = evidence
            record_correction(
                actor=self.owner,
                original_id=original.pk,
                kind="refund",
                allocation=[row],
                provider_reference="999",
                request_key=uuid.uuid4(),
                confirmed=True,
            )
            gateway.return_value.refund.assert_not_called()
            gateway.return_value.void.assert_not_called()
        self.assertFalse(member_needs_review(member))
        self.assertFalse(payment_current(member))
        self.assertEqual(membership_status(member), "pending")
        self.assertEqual(reporting_members().get(pk=member.pk).report_status, "pending")
        self.report_return(original)  # Re-observing the same completed refund is already covered.
        self.assertFalse(sale_needs_review(original.sale))
        self.report_return(original, reference="1000")
        self.assertTrue(member_needs_review(member))
        self.assertEqual(received(original.sale), Decimal("36.06"))

    def test_resolved_flag_without_unrecorded_return_restores_normal_eligibility(self):
        member = self.buy()
        original = self.succeed(member)
        PaymentEvent.objects.create(
            operation=original,
            state="succeeded",
            source="provider",
            code="external_correction_review",
        )
        followup = PaymentFollowup.objects.create(operation=original, plan="owner_review")
        self.assertTrue(member_needs_review(member))
        followup.resolved_at = timezone.now()
        followup.save(update_fields=["resolved_at"])
        original.refresh_from_db()
        self.assertFalse(member_needs_review(member))
        self.assertTrue(payment_current(member))
        self.assertEqual(membership_status(member), "active")

    def test_an_unrelated_cohort_does_not_lose_benefits(self):
        held = self.buy()
        original = self.succeed(held)
        self.key = uuid.uuid4()
        other = self.buy(expected_method="cash", verified_received=True)
        self.report_return(original)
        self.assertFalse(member_needs_review(other))
        self.assertTrue(payment_current(other))
        self.assertEqual(reporting_members().get(pk=other.pk).report_status, "active")

    def test_a_late_source_return_stops_an_unsent_purchase_confirmation(self):
        member = self.buy()
        original = self.succeed(member)
        message = MessageDelivery.objects.get(kind="membership_confirmation", membership=member)
        self.report_return(original)
        with patch("core.communications.services.send") as send:
            self.assertEqual(deliver(message.pk).state, "cancelled")
            send.assert_not_called()
        message.refresh_from_db()
        self.assertEqual(message.code, "membership_funding_review")
        self.assertIn("Your payment of $37.06 was received.", message.text_body)

    def test_overview_shows_recorded_funds_and_review_without_a_zero_dollar_collection(self):
        member = self.buy(billing="prepaid")
        original = self.succeed(member)
        self.report_return(original)
        self.client.force_login(self.staff)
        response = self.client.get(f"/staff/memberships/purchased/{member.pk}/")
        self.assertContains(response, "Recorded money received")
        self.assertContains(response, "Owner reconciliation required")
        self.assertContains(response, "Benefits are currently unavailable.")
        self.assertContains(response, "Owner review")
        self.assertNotContains(response, "Paid in full")
        self.assertNotContains(response, "Confirm membership payment")
        self.assertNotContains(response, "Renew membership</a>")
        with clock(date(2028, 2, 1)):
            self.client.force_login(self.staff)
            expired = self.client.get(f"/staff/memberships/purchased/{member.pk}/")
        self.assertContains(expired, "Expired")
        self.assertContains(expired, "Recorded money received")
        self.assertContains(expired, "Owner reconciliation required")
        self.assertNotContains(expired, "Paid in full")
        self.assertNotContains(expired, "Confirm membership payment")
