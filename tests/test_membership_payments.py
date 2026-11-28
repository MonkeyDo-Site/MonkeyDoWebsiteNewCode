"""Explicit collection never retries uncertain outcomes or fabricates receipts."""

import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.membership_payments import change_card, collect_installment, payment_review
from core.membership_records import (
    MembershipBillingAction,
    MembershipInstallment,
    MembershipInvoice,
)
from core.membership_reservations import payment_current
from core.membership_sales import installment_paid
from core.models import (
    Customer,
    DurableJob,
    FinancialLineAdjustment,
    FinancialPosting,
    PaymentMethod,
    PaymentOperation,
)
from core.payments.invoices import received, total
from core.payments.ledger import record_result
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
)
class MembershipPaymentTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed

    def failed(self):
        member = self.buy()
        operation = member.installments.first().invoice.sale.operations.get()
        record_result(operation_id=operation.pk, state="declined", source="provider")
        return member, member.installments.first()

    def review(self, member, item, **values):
        return payment_review(
            actor=self.staff,
            member_id=member.pk,
            installment_id=item.pk,
            tender=values.pop("tender", "card"),
            **values,
        )

    def collect(self, member, item, *, tender="card", key=None, **values):
        return collect_installment(
            actor=self.staff,
            member_id=member.pk,
            installment_id=item.pk,
            tender=tender,
            request_key=key or uuid.uuid4(),
            confirmed=True,
            reviewed=self.review(member, item, tender=tender)["fingerprint"],
            **values,
        )

    def new_card(self, customer=None, **values):
        return PaymentMethod.objects.create(
            customer=customer or self.customer,
            provider_customer="12",
            provider_method="346",
            brand="Mastercard",
            last_four="4242",
            reusable=True,
            consent_at=timezone.now(),
            consent_version="MD-PAYMENT-2026-01",
            **values,
        )

    def test_review_is_read_only_and_failed_card_requires_explicit_confirmation(self):
        member, item = self.failed()
        before = PaymentOperation.objects.count(), DurableJob.objects.count()
        data = self.review(member, item)
        self.assertEqual(data["total"], "37.06")
        self.assertEqual((PaymentOperation.objects.count(), DurableJob.objects.count()), before)
        with self.assertRaises(ValidationError):
            collect_installment(
                actor=self.staff,
                member_id=member.pk,
                installment_id=item.pk,
                tender="card",
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
            )
        self.assertFalse(FinancialPosting.objects.exists())

    def test_manual_retry_queues_once_and_replay_survives_the_later_provider_outcome(self):
        member, item = self.failed()
        data = self.review(member, item)
        key = uuid.uuid4()
        kwargs = dict(
            actor=self.staff,
            member_id=member.pk,
            installment_id=item.pk,
            tender="card",
            request_key=key,
            confirmed=True,
            reviewed=data["fingerprint"],
        )
        action = collect_installment(**kwargs)
        self.assertEqual(action.operation.amount, Decimal("37.06"))
        self.assertEqual(action.operation.state, "ready")
        self.assertTrue(DurableJob.objects.filter(reference=str(action.operation_id)).exists())
        record_result(
            operation_id=action.operation_id,
            state="succeeded",
            source="provider",
            provider_reference="501",
        )
        self.assertEqual(collect_installment(**kwargs).pk, action.pk)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertTrue(installment_paid(item))
        self.assertEqual(MessageDelivery.objects.filter(kind="membership_confirmation").count(), 1)

    def test_ready_unknown_and_review_outcomes_block_replacement_card_and_manual_receipts(self):
        member = self.buy()
        item = member.installments.first()
        operation = item.invoice.sale.operations.get()
        for state in ("ready", "unknown", "action"):
            if state != "ready":
                record_result(operation_id=operation.pk, state=state, source="provider")
            for tender in ("card", "cash", "zelle"):
                with (
                    self.subTest(state=state, tender=tender),
                    self.assertRaisesMessage(ValidationError, "existing payment outcome"),
                ):
                    self.review(member, item, tender=tender)
        self.assertFalse(MembershipBillingAction.objects.exists())

    def test_failed_card_can_be_paid_cash_without_collecting_its_unused_fee(self):
        member, item = self.failed()
        original = item.invoice.sale
        self.assertEqual(self.review(member, item, tender="cash")["total"], "35.98")
        with self.assertRaisesMessage(ValidationError, "Verify the actual payment"):
            self.collect(member, item, tender="cash")
        action = self.collect(member, item, tender="cash", verified_received=True)
        action.operation.refresh_from_db()
        self.assertEqual(action.operation.state, "succeeded")
        self.assertEqual(received(original), Decimal("35.98"))
        self.assertEqual(total(original), Decimal("35.98"))
        original.refresh_from_db()
        self.assertEqual(original.total, Decimal("37.06"))
        self.assertEqual(FinancialLineAdjustment.objects.get().fee, Decimal("-1.08"))
        self.assertTrue(installment_paid(item))

    def test_future_installment_waits_and_later_manual_payment_does_not_send_customer_receipt(self):
        member = self.buy(expected_method="cash", verified_received=True)
        item = member.installments.get(number=2)
        with self.assertRaisesMessage(ValidationError, "not due yet"):
            self.review(member, item)
        self.assertEqual(MembershipInvoice.objects.count(), 1)
        before = MessageDelivery.objects.count()
        with clock(date(2027, 11, 30)):
            action = self.collect(member, item, tender="check", verified_received=True)
            self.assertEqual(action.operation.amount, Decimal("35.98"))
            self.assertTrue(payment_current(member))
        self.assertEqual(MessageDelivery.objects.count(), before)
        self.assertEqual(MembershipInvoice.objects.count(), 2)

    def test_short_month_stop_does_not_collect_a_cycle_starting_after_cancellation(self):
        member = self.buy(expected_method="cash", verified_received=True)
        billing = member.billing_state
        billing.stopped_on = date(2027, 12, 1)
        billing.save(update_fields=["stopped_on"])
        with clock(date(2027, 11, 30)), self.assertRaisesMessage(ValidationError, "cancelled part"):
            self.review(member, member.installments.get(number=2))

    def test_zelle_uses_actual_bank_date_and_other_methods_cannot_backdate(self):
        member, item = self.failed()
        day = date(2027, 10, 29)
        data = self.review(member, item, tender="zelle", received_on=day)
        action = collect_installment(
            actor=self.staff,
            member_id=member.pk,
            installment_id=item.pk,
            tender="zelle",
            received_on=day,
            request_key=uuid.uuid4(),
            confirmed=True,
            verified_received=True,
            reviewed=data["fingerprint"],
        )
        self.assertEqual(action.operation.manual_received_on, day)
        with self.assertRaisesMessage(ValidationError, "Zelle only"):
            self.review(member, item, tender="cash", received_on=day)

    def test_card_update_records_new_acceptance_without_retrying_and_stale_review_cannot_charge(
        self,
    ):
        member, item = self.failed()
        data = self.review(member, item)
        card = self.new_card()
        key = uuid.uuid4()
        kwargs = dict(
            actor=self.staff,
            member_id=member.pk,
            method_id=card.pk,
            revision=1,
            request_key=key,
            accepted=True,
        )
        action = change_card(**kwargs)
        self.assertEqual(change_card(**kwargs).pk, action.pk)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(member.mandates.count(), 2)
        member.billing_state.refresh_from_db()
        self.assertEqual(member.billing_state.mandate.method_id, card.pk)
        with self.assertRaisesMessage(ValidationError, "payment changed"):
            collect_installment(
                actor=self.staff,
                member_id=member.pk,
                installment_id=item.pk,
                tender="card",
                request_key=uuid.uuid4(),
                confirmed=True,
                reviewed=data["fingerprint"],
            )
        self.assertEqual(self.collect(member, item).operation.method_id, card.pk)

    def test_card_update_requires_acceptance_current_revision_and_customer_ownership(self):
        member, _ = self.failed()
        other = Customer.objects.create(last_name="Rosen", phone="2025550102")
        card = self.new_card(other)
        values = dict(
            actor=self.staff,
            member_id=member.pk,
            method_id=card.pk,
            revision=1,
            request_key=uuid.uuid4(),
        )
        with self.assertRaisesMessage(ValidationError, "must authorize"):
            change_card(**values)
        with self.assertRaisesMessage(ValidationError, "belonging to this customer"):
            change_card(**values, accepted=True)
        values.update(method_id=self.method.pk, revision=99)
        with self.assertRaisesMessage(ValidationError, "billing details changed"):
            change_card(**values, accepted=True)
        self.assertEqual(member.mandates.count(), 1)

    def test_mismatched_duplicate_key_and_cross_customer_installment_are_rejected(self):
        member, item = self.failed()
        key = uuid.uuid4()
        self.collect(member, item, key=key)
        with self.assertRaisesMessage(ValidationError, "different membership action"):
            collect_installment(
                actor=self.staff,
                member_id=member.pk,
                installment_id=item.pk,
                tender="cash",
                request_key=key,
                confirmed=True,
                reviewed="changed",
                verified_received=True,
            )
        self.key = uuid.uuid4()
        other = self.buy(
            customer=Customer.objects.create(last_name="Rosen", phone="2025550103"),
            expected_method="cash",
            billing="prepaid",
            verified_received=True,
        )
        with self.assertRaises(MembershipInstallment.DoesNotExist):
            self.review(member, other.installments.first())

    def test_permissions_recovery_hold_and_runtime_immutable_evidence(self):
        member, item = self.failed()
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.review(member, item)
        self.staff.is_active = True
        self.staff.save(update_fields=["is_active"])
        with override_settings(RECOVERY_HOLD=True), self.assertRaises(ValidationError):
            self.collect(member, item)
        with self.runtime_role():
            action = self.collect(member, item, tender="cash", verified_received=True)
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_membershipbillingaction SET kind='card_update' WHERE id=%s",
                    [action.pk],
                )

    def test_changing_back_to_card_restores_only_the_required_unpaid_processing_fee(self):
        from core.payments.invoices import remove_unpaid_card_fee

        member, item = self.failed()
        sale = item.invoice.sale
        remove_unpaid_card_fee(actor=self.staff, sale_id=sale.pk, request_key=uuid.uuid4())
        self.assertEqual(total(sale), Decimal("35.98"))
        action = self.collect(member, item)
        self.assertEqual(action.operation.amount, Decimal("37.06"))
        self.assertEqual(total(sale), Decimal("37.06"))
        self.assertEqual(FinancialLineAdjustment.objects.count(), 2)

    def test_partial_card_receipt_retains_its_fee_when_the_balance_is_paid_noncard(self):
        from core.payments.ledger import request_operation

        member, item = self.failed()
        sale = item.invoice.sale
        partial = request_operation(
            actor=self.staff,
            sale_id=sale.pk,
            request_key=uuid.uuid4(),
            tender="card",
            method_id=self.method.pk,
            purpose="member_purchase",
            allocation=[
                dict(
                    line=str(sale.lines.get().pk),
                    net="10.00",
                    fee="0.30",
                    item_tax="0.00",
                    fee_tax="0.00",
                )
            ],
        )
        record_result(
            operation_id=partial.pk, state="succeeded", source="provider", provider_reference="502"
        )
        self.assertEqual(self.review(member, item, tender="cash")["total"], "25.98")
        self.collect(member, item, tender="cash", verified_received=True)
        self.assertEqual(received(sale), Decimal("36.28"))
        self.assertEqual(total(sale), Decimal("36.28"))
        self.assertTrue(installment_paid(item))

    def test_payment_notices_track_unissued_dues_and_clear_after_recorded_settlement(self):
        from core.membership_notices import payment_notices

        member = self.buy(expected_method="cash", verified_received=True)
        self.assertFalse(payment_notices())
        with clock(date(2027, 11, 30)):
            notices = payment_notices()
            self.assertEqual(len(notices), 1)
            self.assertEqual(notices[0].number, 2)
            self.assertEqual(notices[0].remaining, Decimal("37.06"))
            self.collect(
                member, member.installments.get(number=2), tender="cash", verified_received=True
            )
            self.assertFalse(payment_notices())

    def test_decline_email_names_membership_and_notices_resolve_without_customer_failure_email(
        self,
    ):
        from core.membership_notices import payment_notices

        member, item = self.failed()
        owner_alert = MessageDelivery.objects.get(kind="payment_issue")
        self.assertIn(f"#{member.membership_number}", owner_alert.text_body)
        self.assertIn("Installment: 1", owner_alert.text_body)
        self.assertIn("not been cancelled or repriced", owner_alert.text_body)
        self.assertEqual(payment_notices()[0].issue_label, "Payment declined")
        self.collect(member, item, tender="cash", verified_received=True)
        self.assertFalse(payment_notices())
        self.assertFalse(
            item.invoice.sale.operations.filter(
                followup__resolved_at__isnull=True, state="declined"
            ).exists()
        )
        self.assertEqual(
            MessageDelivery.objects.exclude(
                kind__in=["payment_issue", "membership_confirmation"]
            ).count(),
            0,
        )

    def test_cancelled_short_month_payment_does_not_show_as_overdue_or_as_a_notice(self):
        from core.membership_notices import payment_notices
        from core.membership_sales import membership_status

        member = self.buy(expected_method="cash", verified_received=True)
        state = member.billing_state
        state.stopped_on = date(2027, 12, 1)
        state.save(update_fields=["stopped_on"])
        with clock(date(2027, 11, 30)):
            self.assertEqual(membership_status(member), "active")
            self.assertFalse(payment_notices())
