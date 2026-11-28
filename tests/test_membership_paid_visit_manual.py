"""Received replacement money never collects reserved source funds or unused fees."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.customer_credit import applied
from core.customer_credit_records import VisitMembershipConversion
from core.membership_paid_visit_manual import record as receive_payment
from core.membership_paid_visit_manual import review
from core.membership_paid_visit_pending import complete
from core.membership_paid_visit_records import MembershipPaidVisitManualPayment
from core.membership_sales import installment_paid
from core.models import FinancialLineAdjustment, OwnerNotice, PaymentOperation
from core.payments.amounts import ZERO
from core.payments.invoices import received, total
from core.payments.ledger import request_operation
from tests import test_membership_paid_visit_recovery as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitManualTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PaidVisitRecoveryTests.prepare
    buy_card = fixtures.PaidVisitRecoveryTests.buy_card
    decline = fixtures.PaidVisitRecoveryTests.decline
    setup_decline = fixtures.PaidVisitRecoveryTests.setup_decline

    def prepare_manual(self):
        self.setup_decline()
        self.manual_key = uuid.uuid4()
        self.manual_data = review(actor=self.staff, intent_id=self.intent.pk)

    def receive(self, **changes):
        options = dict(
            actor=self.staff,
            intent_id=self.intent.pk,
            request_key=self.manual_key,
            reviewed=self.manual_data["fingerprint"],
            tender="cash",
            confirmed=True,
            verified_received=True,
        )
        options.update(changes)
        return receive_payment(**options)

    def test_known_cash_removes_only_unused_fee_and_applies_original_funds_once(self):
        self.prepare_manual()
        self.assertEqual(
            (self.manual_data["net"], self.manual_data["fee_removed"]), ("1.97", "0.06")
        )
        with patch("core.payments.operations.Gateway") as gateway, self.runtime_role():
            authority = self.receive()
        gateway.assert_not_called()
        first = self.member.installments.first()
        self.assertEqual(authority.operation.amount, Decimal("1.97"))
        self.assertEqual(authority.operation.tender, "cash")
        self.assertEqual(authority.operation.state, "succeeded")
        self.assertEqual(first.quote["processing_fee"], "0.06")
        self.assertEqual(
            (total(first.invoice.sale), received(first.invoice.sale)),
            (Decimal("17.99"), Decimal("1.97")),
        )
        self.assertEqual(
            (total(self.original), received(self.original)), (Decimal("16.47"), Decimal("16.47"))
        )
        self.assertFalse(VisitMembershipConversion.objects.exists())
        with self.runtime_role():
            release = complete(self.intent.pk)
        self.assertEqual(release.kind, "completed")
        self.assertTrue(installment_paid(first))
        self.assertEqual(applied(first.invoice.sale), Decimal("16.02"))
        self.assertEqual(total(self.original), Decimal("0.45"))
        self.assertEqual(received(self.original), Decimal("16.47"))
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(complete(self.intent.pk).pk, release.pk)
        self.assertEqual(self.receive().pk, authority.pk)
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_received_check_is_not_a_card_charge_and_can_be_replayed(self):
        self.prepare_manual()
        record = self.receive(tender="check")
        self.assertEqual(record.operation.tender, "check")
        self.assertEqual(self.receive(tender="check").pk, record.pk)
        self.assertEqual(MembershipPaidVisitManualPayment.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.receive(tender="cash")
        with self.assertRaises(ValidationError):
            self.receive(tender="check", request_key=uuid.uuid4())
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_zelle_records_actual_bank_date_and_sender(self):
        self.prepare_manual()
        earlier = timezone.localdate() - timedelta(days=1)
        record = self.receive(tender="zelle", sender_name="D. Test", received_on=earlier)
        self.assertEqual(record.operation.manual_received_on, earlier)
        self.assertEqual(record.facts["sender"], "D. Test")
        self.assertEqual(record.operation.amount, Decimal("1.97"))

    def test_physical_gift_card_requires_verified_receipt(self):
        self.prepare_manual()
        with self.assertRaises(ValidationError):
            self.receive(tender="gift_card", verified_received=False)
        self.assertFalse(MembershipPaidVisitManualPayment.objects.exists())
        record = self.receive(tender="gift_card")
        self.assertEqual(record.operation.tender, "gift_card")
        self.assertEqual(record.operation.amount, Decimal("1.97"))

    def test_local_completion_failure_keeps_known_cash_and_original_visit(self):
        self.prepare_manual()
        record = self.receive()
        with patch(
            "core.membership_paid_visit.complete_purchase",
            side_effect=ValidationError("Local conversion failed"),
        ):
            with self.assertRaises(ValidationError):
                complete(self.intent.pk)
        record.operation.refresh_from_db()
        self.assertEqual(record.operation.state, "succeeded")
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertTrue(
            OwnerNotice.objects.filter(
                details__kind="paid_visit_membership", reviewed_at__isnull=True
            ).exists()
        )
        complete(self.intent.pk)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_untyped_receipt_and_unused_fee_adjustment_are_refused(self):
        self.prepare_manual()
        sale = self.member.installments.first().invoice.sale
        line = sale.lines.get()
        with self.assertRaises(ValidationError):
            request_operation(
                actor=self.staff,
                sale_id=sale.pk,
                request_key=uuid.uuid4(),
                tender="cash",
                purpose="member_purchase",
                allocation=[
                    dict(line=str(line.pk), net="1.97", fee="0.00", item_tax="0.00", fee_tax="0.00")
                ],
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            FinancialLineAdjustment.objects.create(
                request_key=uuid.uuid4(),
                line=line,
                reason="tender_change",
                fee=Decimal("-0.06"),
                actor=self.owner,
            )

    def cancel_received(self, *, refund="1.97"):
        from core.membership_cancellations import cancel
        from core.membership_cancellations import review as cancellation_review

        self.prepare_manual()
        self.manual = self.receive()
        options = dict(
            actor=self.owner, member_id=self.member.pk, timing="immediate", refund_amount=refund
        )
        data = cancellation_review(**options)
        self.cancelled = cancel(
            **options,
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Keep original paid visit; cancel membership",
            early_override=True,
            send_confirmation=False,
        )
        self.member.billing_state.refresh_from_db()

    def test_cancelled_manual_receipt_is_returned_before_releasing_original_visit(self):
        from core.membership_cancellations import request_refund
        from core.membership_paid_visit_cancellation import release as release_source
        from core.membership_paid_visit_cancellation import review as release_review

        self.cancel_received()
        with self.assertRaises(ValidationError):
            release_review(actor=self.owner, intent=self.intent)
        plan = self.cancelled.refund_plans.get()
        attempt = request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
        )
        attempt.operation.refresh_from_db()
        self.assertEqual((attempt.operation.tender, attempt.operation.state), ("cash", "succeeded"))
        data = release_review(actor=self.owner, intent=self.intent)
        with self.runtime_role():
            release_source(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                reason="Cash returned; keep original visit",
                confirmed=True,
            )
        self.assertEqual(received(self.manual.operation.sale), ZERO)
        self.assertEqual(total(self.manual.operation.sale), ZERO)
        self.assertEqual(
            (total(self.original), received(self.original)), (Decimal("16.47"), Decimal("16.47"))
        )
        self.assertFalse(VisitMembershipConversion.objects.exists())
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_owner_can_retain_chosen_manual_amount_without_fake_refund_or_credit(self):
        from core.membership_paid_visit_cancellation import release as release_source
        from core.membership_paid_visit_cancellation import review as release_review

        self.cancel_received(refund="0.00")
        data = release_review(actor=self.owner, intent=self.intent)
        self.assertEqual(
            (data["retained"], data["retained_fee"], data["uncollected"]), ("1.97", "0.00", "16.02")
        )
        release_source(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            reason="Owner retains the chosen cash amount",
            confirmed=True,
        )
        self.assertEqual(
            (total(self.manual.operation.sale), received(self.manual.operation.sale)),
            (Decimal("1.97"), Decimal("1.97")),
        )
        self.assertFalse(self.cancelled.refund_plans.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(total(self.original), Decimal("16.47"))

    def test_uncertain_existing_card_cannot_be_replaced_with_manual_money(self):
        from core.payments.ledger import record_result
        from core.payments.operations import begin_dispatch

        self.buy_card()
        begin_dispatch(self.operation.pk)
        record_result(operation_id=self.operation.pk, state="unknown", source="provider")
        with self.assertRaises(ValidationError):
            review(actor=self.staff, intent_id=self.intent.pk)
        self.assertFalse(MembershipPaidVisitManualPayment.objects.exists())

    def test_unknown_new_card_storage_blocks_manual_alternative(self):
        from core.membership_card_setup import make_flow
        from core.membership_paid_visit_new_card import storage_review, terms
        from core.payments.gateway import ProviderFailure
        from core.payments.setup import exchange

        self.prepare_manual()
        _, data = storage_review(actor=self.staff, intent_id=self.intent.pk)
        flow = make_flow(
            actor=self.staff,
            customer=self.customer,
            request_key=uuid.uuid4(),
            offer=dict(
                operation="paid_visit_recovery",
                origin={"prior_id": self.member.pk},
                expected_method="card",
                fingerprint=data["fingerprint"],
                terms=terms(data),
            ),
        )
        flow["recovery_intent"] = str(self.intent.pk)
        flow["setup_key"] = str(uuid.uuid4())
        with patch("core.payments.setup.Gateway") as gateway:
            gateway.return_value.create_customer.return_value = {"id": 12}
            gateway.return_value.save_card.side_effect = ProviderFailure("unknown")
            exchange(
                actor=self.staff,
                flow=flow,
                request_key=flow["setup_key"],
                nonce="nonce-Synthetic",
                expiry_month=12,
                expiry_year=2035,
                retain=False,
                payment_accepted=True,
                cancellation_accepted=False,
            )
        with self.assertRaises(ValidationError):
            self.receive()
        self.assertFalse(MembershipPaidVisitManualPayment.objects.exists())

    def test_stale_review_or_another_actor_cannot_record_the_receipt(self):
        self.prepare_manual()
        with self.assertRaises(ValidationError):
            self.receive(actor=self.owner)
        with self.assertRaises(ValidationError):
            self.receive(reviewed="a" * 64)
        self.assertFalse(MembershipPaidVisitManualPayment.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_missing_unused_fee_adjustment_cannot_commit_a_partial_authority(self):
        self.prepare_manual()
        with self.assertRaises(DatabaseError), transaction.atomic():
            with patch("core.models.FinancialLineAdjustment.objects.create"):
                self.receive()
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertFalse(MembershipPaidVisitManualPayment.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_zelle_sender_and_actual_date_are_required_and_cash_cannot_be_backdated(self):
        self.prepare_manual()
        for values in [
            dict(tender="zelle"),
            dict(received_on=timezone.localdate() - timedelta(days=1)),
            dict(
                tender="zelle",
                sender_name="Test",
                received_on=timezone.localdate() + timedelta(days=1),
            ),
        ]:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.receive(**values)
        self.assertFalse(MembershipPaidVisitManualPayment.objects.exists())

    def test_same_page_records_one_payment_and_applies_visit_on_duplicate_submit(self):
        self.prepare_manual()
        verified_owner_login(self.client, self.staff)
        url = reverse("membership_overview", args=[self.member.pk])
        page = self.client.get(url)
        self.assertContains(page, "Record received payment instead")
        controls = page.context["paid_visit_manual"]
        post = dict(
            action="paid_visit_manual_receive",
            request_key=str(controls["key"]),
            reviewed=controls["reviewed"],
            tender="cash",
            confirmed="on",
            verified_received="on",
        )
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertEqual(self.client.post(url, post).status_code, 302)
            self.assertEqual(self.client.post(url, post).status_code, 302)
        gateway.assert_not_called()
        self.assertEqual(MembershipPaidVisitManualPayment.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertNotContains(self.client.get(url), "Record received payment instead")

    def test_same_page_failed_application_shows_known_receipt_without_card_retry(self):
        self.prepare_manual()
        verified_owner_login(self.client, self.staff)
        url = reverse("membership_overview", args=[self.member.pk])
        controls = self.client.get(url).context["paid_visit_manual"]
        with patch(
            "core.membership_paid_visit.complete_purchase",
            side_effect=ValidationError("Review source"),
        ):
            response = self.client.post(
                url,
                dict(
                    action="paid_visit_manual_receive",
                    request_key=str(controls["key"]),
                    reviewed=controls["reviewed"],
                    tender="check",
                    confirmed="on",
                    verified_received="on",
                ),
                follow=True,
            )
        self.assertContains(response, "Payment received and recorded")
        self.assertContains(response, "Replacement payment received")
        self.assertContains(response, "Open received payment · $1.97")
        self.assertNotContains(response, "Try a card payment again")
        self.assertNotContains(response, "Record received payment instead")
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertEqual(received(self.member.installments.first().invoice.sale), Decimal("1.97"))
        self.assertEqual(self.client.post(url, {"action": "paid_visit_complete"}).status_code, 302)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_no_manual_control_while_original_card_is_unattempted(self):
        self.buy_card()
        verified_owner_login(self.client, self.staff)
        response = self.client.get(reverse("membership_overview", args=[self.member.pk]))
        self.assertNotContains(response, "Record received payment instead")

    def test_partial_actual_cash_return_preserves_chosen_retained_money(self):
        from core.membership_cancellations import request_refund
        from core.membership_paid_visit_cancellation import release as release_source
        from core.membership_paid_visit_cancellation import review as release_review

        self.cancel_received(refund="0.97")
        attempt = request_refund(
            actor=self.owner,
            plan_id=self.cancelled.refund_plans.get().pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
        )
        attempt.operation.refresh_from_db()
        self.assertEqual(attempt.operation.amount, Decimal("0.97"))
        data = release_review(actor=self.owner, intent=self.intent)
        self.assertEqual(
            (data["retained"], data["retained_fee"], data["uncollected"]), ("1.00", "0.00", "16.02")
        )
        release_source(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            reason="Retain only the chosen amount",
            confirmed=True,
        )
        self.assertEqual(
            (total(self.manual.operation.sale), received(self.manual.operation.sale)),
            (Decimal("1.00"), Decimal("1.00")),
        )
        self.assertEqual(
            (total(self.original), received(self.original)), (Decimal("16.47"), Decimal("16.47"))
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_full_manual_refund_requires_cancellation_source_release_not_generic_stop(self):
        from core.membership_cancellations import request_refund
        from core.membership_paid_visit_pending import stop, stop_facts
        from core.membership_paid_visit_records import MembershipPaidVisitRelease

        self.cancel_received()
        request_refund(
            actor=self.owner,
            plan_id=self.cancelled.refund_plans.get().pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
        )
        data = stop_facts(self.intent)
        self.assertFalse(data["allowed"])
        with self.assertRaises(ValidationError):
            stop(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                reason="Cannot bypass cancellation writeoff",
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipPaidVisitRelease.objects.create(
                intent=self.intent,
                request_key=uuid.uuid4(),
                kind="stopped",
                actor=self.owner,
                reason="Bypass cancellation-source authority",
            )
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertFalse(MembershipPaidVisitRelease.objects.exists())
        verified_owner_login(self.client, self.owner)
        page = self.client.get(reverse("membership_overview", args=[self.member.pk]))
        self.assertNotContains(page, 'value="paid_visit_stop"')
        self.assertContains(page, 'value="paid_visit_cancelled_release"')
