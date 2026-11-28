"""Cancellation/refund outcomes remain distinct from owner intent and estimates."""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.membership_cancellations import cancel, notices, plan_paid, request_refund, review
from core.membership_records import (
    MembershipCancellation,
    MembershipRefundAttempt,
    MembershipRefundPlan,
)
from core.membership_reservations import payment_current
from core.membership_sales import installment_paid, membership_status
from core.models import (
    DurableJob,
    FinancialLineAdjustment,
    FinancialPosting,
    OwnerNotice,
    PaymentEvent,
    PaymentFollowup,
    PaymentOperation,
    ProviderObservation,
)
from core.payments.gateway import ProviderFailure
from core.payments.invoices import received, total
from core.payments.ledger import record_result, request_operation
from core.payments.operations import begin_dispatch, execute
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
    RESEND_API_KEY="fake-not-sent",
)
class MembershipCancellationTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed

    def prepaid(self, card=False, **changes):
        member = self.buy(
            billing="prepaid",
            expected_method="card" if card else "cash",
            verified_received=not card,
            **changes,
        )
        if card:
            self.succeed(member)
        return member

    def inspect(self, member, **changes):
        return review(actor=self.owner, member_id=member.pk, **changes)

    def end(self, member, *, key=None, timing="immediate", refund_amount="0.00", **changes):
        data = self.inspect(member, timing=timing, refund_amount=refund_amount)
        return cancel(
            **(
                dict(
                    actor=self.owner,
                    member_id=member.pk,
                    timing=timing,
                    refund_amount=refund_amount,
                    reviewed=data["fingerprint"],
                    request_key=key or uuid.uuid4(),
                    reason="Customer requested cancellation; owner reviewed the term and funds.",
                    early_override=True,
                    send_confirmation=True,
                )
                | changes
            )
        )

    def test_review_is_read_only_and_recommendation_excludes_the_original_fee(self):
        member = self.prepaid(card=True)
        before = (
            PaymentOperation.objects.count(),
            FinancialPosting.objects.count(),
            DurableJob.objects.count(),
        )
        data = self.inspect(member, timing="immediate")
        self.assertEqual(data["money_received"], "111.18")
        self.assertEqual(data["suggested_refund"], "107.94")
        self.assertEqual(data["original_fees"], "3.24")
        self.assertEqual(
            before,
            (
                PaymentOperation.objects.count(),
                FinancialPosting.objects.count(),
                DurableJob.objects.count(),
            ),
        )
        self.assertFalse(MembershipCancellation.objects.exists())
        self.assertFalse(MembershipRefundPlan.objects.exists())

    def test_owner_early_commitment_reason_and_explicit_email_choices_are_required(self):
        member = self.prepaid()
        data = self.inspect(member, timing="immediate", refund_amount="0.00")
        values = dict(
            actor=self.owner,
            member_id=member.pk,
            timing="immediate",
            refund_amount="0.00",
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Customer requested cancellation.",
            early_override=True,
            send_confirmation=False,
        )
        for changes, error in (
            ({"actor": self.staff}, PermissionDenied),
            ({"early_override": False}, ValidationError),
            ({"reason": ""}, ValidationError),
            ({"send_confirmation": None}, ValidationError),
        ):
            with self.subTest(changes=changes), self.assertRaises(error):
                cancel(**(values | changes))
        self.assertFalse(MembershipCancellation.objects.exists())

    def test_pending_unstarted_purchase_cancels_queued_charge_without_claiming_a_refund(self):
        member = self.buy(starts_on=date(2027, 11, 1))
        original = member.installments.first().invoice.sale.operations.get()
        record = self.end(member, refund_amount="0.00")
        original.refresh_from_db()
        self.assertEqual(original.state, "cancelled")
        self.assertIsNone(begin_dispatch(original.pk))
        self.assertFalse(record.refund_plans.exists())
        self.assertFalse(FinancialPosting.objects.exists())
        member.billing_state.refresh_from_db()
        self.assertEqual(membership_status(member), "cancelled")
        self.assertIn(
            "cancelled before its start date",
            MessageDelivery.objects.get(kind="membership_cancellation").text_body,
        )

    def test_unknown_or_sending_outcome_blocks_cancellation_before_any_change(self):
        member = self.buy()
        original = member.installments.first().invoice.sale.operations.get()
        record_result(operation_id=original.pk, state="unknown", source="provider")
        with self.assertRaises(ValidationError):
            self.end(member)
        self.assertFalse(MembershipCancellation.objects.exists())
        member.billing_state.refresh_from_db()
        self.assertIsNone(member.billing_state.stopped_on)

    def test_refund_due_reserves_only_actual_net_and_does_not_count_as_returned_money(self):
        member = self.prepaid(card=True)
        record = self.end(member, refund_amount="100.00")
        plan = record.refund_plans.get()
        self.assertEqual(plan.amount, Decimal("100.00"))
        self.assertEqual(plan_paid(plan), Decimal("0.00"))
        self.assertEqual(received(plan.original.sale), Decimal("111.18"))
        self.assertEqual(len(notices()["refunds"]), 1)
        self.assertFalse(FinancialLineAdjustment.objects.exists())
        self.assertIn(
            "not yet been confirmed as returned",
            MessageDelivery.objects.get(kind="membership_cancellation").text_body,
        )
        self.assertNotIn(
            "nonrefundable", MessageDelivery.objects.get(kind="membership_cancellation").text_body
        )

    def test_manual_return_needs_confirmation_and_adjusts_invoice_with_actual_funds_once(self):
        member = self.prepaid()
        record = self.end(member, refund_amount="20.00")
        plan = record.refund_plans.get()
        with self.assertRaises(ValidationError):
            request_refund(
                actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
            )
        key = uuid.uuid4()
        attempt = request_refund(
            actor=self.owner, plan_id=plan.pk, request_key=key, confirmed=True, manual_returned=True
        )
        self.assertEqual(
            request_refund(
                actor=self.owner,
                plan_id=plan.pk,
                request_key=key,
                confirmed=True,
                manual_returned=True,
            ).pk,
            attempt.pk,
        )
        self.assertEqual(plan_paid(plan), Decimal("20.00"))
        self.assertEqual(received(plan.original.sale), Decimal("87.94"))
        self.assertEqual(total(plan.original.sale), Decimal("87.94"))
        self.assertEqual(FinancialLineAdjustment.objects.get().net, Decimal("-20.00"))
        self.assertFalse(notices()["refunds"])
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_cancellation", state="queued").count(),
            1,
        )
        self.assertFalse(MessageDelivery.objects.filter(kind="membership_refund").exists())

    def test_current_cycle_stays_paid_after_owner_refund_and_benefits_last_to_effective_end(self):
        member = self.buy(expected_method="cash", verified_received=True)
        record = self.end(
            member,
            timing="end_cycle",
            refund_amount="20.00",
            refund_now=True,
            manual_refunds_confirmed=True,
        )
        member.billing_state.refresh_from_db()
        self.assertEqual(record.stopped_on, date(2027, 12, 1))
        self.assertTrue(installment_paid(member.installments.first()))
        self.assertTrue(payment_current(member))
        self.assertEqual(membership_status(member), "active")
        self.assertEqual(plan_paid(record.refund_plans.get()), Decimal("20.00"))
        text = MessageDelivery.objects.get(kind="membership_cancellation").text_body
        self.assertIn("A refund of $20.00 has been processed.", text)
        self.assertIn("remaining eligible membership benefits", text)
        with clock(date(2027, 12, 1)):
            self.assertEqual(membership_status(member), "cancelled")

    def test_card_refund_queues_once_and_only_confirmed_provider_outcome_changes_funds(self):
        member = self.prepaid(card=True)
        record = self.end(member, refund_amount="50.00", refund_now=True)
        plan = record.refund_plans.get()
        attempt = plan.attempts.get()
        self.assertEqual(attempt.operation.state, "ready")
        self.assertEqual(received(plan.original.sale), Decimal("111.18"))
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.refund.return_value = {
                "status_code": "A",
                "reference_number": 90002,
            }
            gateway.return_value.transaction.return_value = dict(
                id=90002,
                amount_details={"amount": "50.00"},
                transaction_details={
                    "type": "credit",
                    "reference_number": int(plan.original.provider_reference),
                },
                status_details={"status": "settled"},
                created_at=timezone.now().isoformat(),
            )
            result = execute(attempt.operation_id)
            execute(attempt.operation_id)
            gateway.return_value.refund.assert_called_once()
            gateway.return_value.charge.assert_not_called()
            gateway.return_value.void.assert_not_called()
        self.assertEqual(result.state, "succeeded")
        self.assertEqual(plan_paid(plan), Decimal("50.00"))
        self.assertEqual(received(plan.original.sale), Decimal("61.18"))
        self.assertEqual(total(plan.original.sale), Decimal("61.18"))
        adjustment = FinancialLineAdjustment.objects.get()
        self.assertEqual(adjustment.fee, Decimal("0.00"))
        self.assertEqual(adjustment.item_tax, Decimal("0.00"))
        self.assertEqual(adjustment.fee_tax, Decimal("0.00"))
        self.assertFalse(notices()["refunds"])

    def test_unknown_refund_blocks_replacement_without_repeating_provider_post(self):
        member = self.prepaid(card=True)
        record = self.end(member, refund_amount="50.00")
        plan = record.refund_plans.get()
        first = request_refund(
            actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
        )
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.refund.side_effect = ProviderFailure()
            self.assertEqual(execute(first.operation_id).state, "unknown")
            execute(first.operation_id)
            gateway.return_value.refund.assert_called_once()
        with self.assertRaises(ValidationError):
            request_refund(
                actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
            )
        self.assertEqual(plan.attempts.count(), 1)
        self.assertEqual(plan_paid(plan), Decimal("0.00"))
        self.assertEqual(len(notices()["refunds"]), 1)
        self.assertFalse(FinancialLineAdjustment.objects.exists())

    def test_definitive_refund_decline_allows_only_a_new_explicit_owner_attempt(self):
        member = self.prepaid(card=True)
        plan = self.end(member, refund_amount="25.00").refund_plans.get()
        first = request_refund(
            actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
        )
        record_result(operation_id=first.operation_id, state="declined", source="provider")
        self.assertEqual(plan.attempts.count(), 1)
        second = request_refund(
            actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
        )
        self.assertNotEqual(second.pk, first.pk)
        self.assertEqual(plan.attempts.count(), 2)
        self.assertEqual(plan_paid(plan), Decimal("0.00"))
        with self.assertRaises(ValidationError):
            request_refund(
                actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
            )

    def test_other_correction_cannot_refund_reserved_cancellation_funds(self):
        member = self.prepaid(card=True)
        plan = self.end(member, refund_amount="100.00").refund_plans.get()
        with self.assertRaises(ValidationError):
            request_operation(
                actor=self.owner,
                sale_id=plan.original.sale_id,
                request_key=uuid.uuid4(),
                tender="card",
                kind="refund",
                original_id=plan.original_id,
                method_id=plan.original.method_id,
                allocation=plan.allocation,
                purpose="correction",
            )
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())
        self.assertEqual(plan_paid(plan), Decimal("0.00"))

    def test_refund_cannot_exceed_actual_money_or_include_original_processing_fee(self):
        member = self.prepaid(card=True)
        with self.assertRaises(ValidationError):
            self.inspect(member, timing="immediate", refund_amount="111.18")
        self.assertFalse(MembershipCancellation.objects.exists())
        with self.assertRaises(ValidationError):
            self.inspect(member, timing="immediate", refund_amount="107.95")

    def test_stale_review_and_changed_replay_cannot_duplicate_cancellation_or_refund(self):
        member = self.prepaid()
        values = self.inspect(member, timing="immediate", refund_amount="20.00")
        key = uuid.uuid4()
        common = dict(
            actor=self.owner,
            member_id=member.pk,
            timing="immediate",
            refund_amount="20.00",
            reviewed=values["fingerprint"],
            request_key=key,
            reason="Requested by customer.",
            early_override=True,
            send_confirmation=False,
        )
        with self.assertRaises(ValidationError):
            cancel(**(common | {"reviewed": "stale"}))
        first = cancel(**common)
        self.assertEqual(cancel(**common).pk, first.pk)
        with self.assertRaises(ValidationError):
            cancel(**(common | {"reason": "Different request."}))
        self.assertEqual(MembershipCancellation.objects.count(), 1)
        self.assertEqual(MembershipRefundPlan.objects.count(), 1)

    def test_future_date_does_not_claim_remaining_benefits_before_the_membership_begins(self):
        member = self.prepaid(starts_on=date(2028, 1, 1))
        self.end(member, timing="end_cycle", refund_amount="0.00")
        text = MessageDelivery.objects.get(kind="membership_cancellation").text_body
        self.assertIn("before its start date", text)
        self.assertNotIn("continue using", text)

    def test_initial_commitment_end_allows_normal_cancellation_and_preserves_old_unpaid_dues(self):
        member = self.buy(months=6, expected_method="cash", verified_received=True)
        with clock(date(2028, 1, 20)):
            data = self.inspect(member, timing="end_cycle", refund_amount="0.00")
            self.assertFalse(data["requires_early_override"])
            record = self.end(
                member, timing="end_cycle", refund_amount="0.00", early_override=False
            )
            self.assertEqual(record.stopped_on, date(2028, 1, 31))
            from core.membership_notices import payment_notices

            self.assertEqual({item.number for item in payment_notices()}, {2, 3})

    def test_short_month_charge_for_next_cycle_stops_without_erasing_the_current_cycle(self):
        from core.membership_payments import collect_installment, payment_review

        with clock(date(2027, 1, 31)):
            member = self.buy(
                starts_on=date(2027, 1, 31), expected_method="cash", verified_received=True
            )
        with clock(date(2027, 2, 28)):
            item = member.installments.get(number=2)
            data = payment_review(
                actor=self.staff, member_id=member.pk, installment_id=item.pk, tender="card"
            )
            action = collect_installment(
                actor=self.staff,
                member_id=member.pk,
                installment_id=item.pk,
                tender="card",
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                confirmed=True,
            )
            record = self.end(member, timing="end_cycle", refund_amount="0.00")
            self.assertEqual(record.stopped_on, date(2027, 3, 1))
            action.operation.refresh_from_db()
            self.assertEqual(action.operation.state, "cancelled")
            self.assertIsNone(begin_dispatch(action.operation_id))
            member.billing_state.refresh_from_db()
            self.assertEqual(membership_status(member), "active")
            from core.membership_notices import payment_notices

            self.assertFalse(payment_notices())

    def test_owner_manual_confirmation_is_required_before_combined_cancel_and_return(self):
        member = self.prepaid()
        with self.assertRaises(ValidationError):
            self.end(member, refund_amount="20.00", refund_now=True)
        self.assertFalse(MembershipCancellation.objects.exists())
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())

    def test_runtime_cancel_refund_and_adjustment_history_are_immutable(self):
        member = self.prepaid()
        with self.runtime_role():
            record = self.end(
                member, refund_amount="20.00", refund_now=True, manual_refunds_confirmed=True
            )
        for table in (
            "core_membershipcancellation",
            "core_membershiprefundplan",
            "core_membershiprefundattempt",
        ):
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(f"DELETE FROM {table}")
        self.assertEqual(plan_paid(record.refund_plans.get()), Decimal("20.00"))
        self.assertEqual(MembershipRefundAttempt.objects.count(), 1)

    def test_feature_and_recovery_gates_prevent_new_financial_mutations(self):
        member = self.prepaid()
        with override_settings(MEMBERSHIP_SALES_ENABLED=False), self.assertRaises(ValidationError):
            self.end(member)
        with override_settings(RECOVERY_HOLD=True), self.assertRaises(ValidationError):
            self.end(member)
        self.assertFalse(MembershipCancellation.objects.exists())

    def test_partial_manual_returns_leave_the_remaining_refund_due_until_actually_returned(self):
        member = self.prepaid()
        plan = self.end(member, refund_amount="20.00").refund_plans.get()
        request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
            refund_amount="5.00",
        )
        self.assertEqual(plan_paid(plan), Decimal("5.00"))
        self.assertEqual(notices()["refunds"][0].remaining, Decimal("15.00"))
        with self.assertRaises(ValidationError):
            request_refund(
                actor=self.owner,
                plan_id=plan.pk,
                request_key=uuid.uuid4(),
                confirmed=True,
                manual_returned=True,
                refund_amount="15.01",
            )
        request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
            refund_amount="15.00",
        )
        self.assertEqual(plan_paid(plan), Decimal("20.00"))
        self.assertFalse(notices()["refunds"])
        self.assertEqual(received(plan.original.sale), Decimal("87.94"))
        self.assertEqual(total(plan.original.sale), Decimal("87.94"))

    def test_unsent_cancellation_email_refreshes_actual_refunds_without_rewriting_old_snapshot(
        self,
    ):
        from core.communications.services import claim

        member = self.prepaid()
        plan = self.end(member, refund_amount="20.00").refund_plans.get()
        old = MessageDelivery.objects.get(kind="membership_cancellation")
        old_body = old.text_body
        request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
            refund_amount="5.00",
        )
        old.refresh_from_db()
        self.assertEqual(old.state, "cancelled")
        self.assertEqual(old.text_body, old_body)
        current = MessageDelivery.objects.get(kind="membership_cancellation", state="queued")
        self.assertIn("A refund of $5.00 has been processed.", current.text_body)
        self.assertIn("A refund of $15.00 is due.", current.text_body)
        self.assertIsNone(claim(old.pk))
        self.assertIsNotNone(claim(current.pk))
        count = MessageDelivery.objects.filter(kind="membership_cancellation").count()
        request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
        )
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_cancellation").count(), count
        )

    def test_paused_email_does_not_block_actual_refund_and_claim_refreshes_before_delivery(self):
        from core.communications.services import claim

        member = self.prepaid(card=True)
        plan = self.end(member, refund_amount="20.00").refund_plans.get()
        old = MessageDelivery.objects.get(kind="membership_cancellation", state="queued")
        attempt = request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
        )
        with override_settings(BOOKING_EMAIL_ENABLED=False):
            record_result(
                operation_id=attempt.operation_id,
                state="succeeded",
                source="provider",
                provider_reference="1441914",
            )
        self.assertEqual(plan_paid(plan), Decimal("20.00"))
        self.assertIsNone(claim(old.pk))
        current = MessageDelivery.objects.get(kind="membership_cancellation", state="queued")
        self.assertIn("A refund of $20.00 has been processed.", current.text_body)
        self.assertNotIn("is due", current.text_body)

    def reported_refund(self, original, reference="1441914", value="5.00"):
        ProviderObservation.objects.create(
            operation=original,
            fingerprint=str(uuid.uuid4()),
            provider_reference=reference,
            provider_status="external_credit",
            amount=value,
        )
        PaymentEvent.objects.get_or_create(
            operation=original,
            state="succeeded",
            source="provider",
            code="external_correction_review",
        )
        PaymentFollowup.objects.update_or_create(
            operation=original, defaults=dict(plan="owner_review", resolved_at=None)
        )
        return OwnerNotice.objects.create(
            customer=self.customer,
            subject="Provider refund needs recording",
            details=dict(kind="payment_correction", operation_id=str(original.pk)),
        )

    def refund_evidence(self, original, reference="1441914", value="5.00"):
        return dict(
            id=reference,
            amount_details=dict(amount=value),
            transaction_details=dict(type="credit", reference_number=original.provider_reference),
            status_details=dict(status="settled"),
            created_at="2027-10-31T13:00:00-04:00",
        )

    def test_known_external_return_blocks_cancellation_review_and_outgoing_refund(self):
        member = self.prepaid(card=True)
        original = member.installments.first().invoice.sale.operations.get()
        self.reported_refund(original)
        with self.assertRaisesMessage(ValidationError, "still needs recording"):
            self.inspect(member)
        self.assertFalse(MembershipCancellation.objects.exists())

    def test_collecting_earlier_dues_after_cancellation_does_not_send_a_purchase_confirmation(self):
        from core.membership_payments import collect_installment, payment_review

        member = self.buy()
        self.end(member, timing="end_cycle", send_confirmation=False)
        item = member.installments.first()
        values = dict(actor=self.owner, member_id=member.pk, installment_id=item.pk, tender="cash")
        reviewed = payment_review(**values)
        result = collect_installment(
            **values,
            reviewed=reviewed["fingerprint"],
            request_key=uuid.uuid4(),
            confirmed=True,
            verified_received=True,
        )
        result.operation.refresh_from_db()
        self.assertEqual(result.operation.state, "succeeded")
        self.assertFalse(MessageDelivery.objects.filter(kind__startswith="membership_").exists())

    def test_late_external_return_stops_queued_post_and_can_be_imported_once_against_plan(self):
        member = self.prepaid(card=True)
        plan = self.end(member, refund_amount="20.00").refund_plans.get()
        queued = request_refund(
            actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
        )
        notice = self.reported_refund(plan.original)
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertEqual(execute(queued.operation_id).state, "cancelled")
            gateway.return_value.refund.assert_not_called()
        with self.assertRaisesMessage(ValidationError, "already reported a return"):
            request_refund(
                actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
            )
        data = dict(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            refund_amount="5.00",
            completed_provider_reference="1441914",
        )
        with patch("core.payments.corrections.Gateway") as gateway:
            gateway.return_value.transaction.return_value = self.refund_evidence(plan.original)
            imported = request_refund(**data)
            self.assertEqual(request_refund(**data).pk, imported.pk)
            gateway.return_value.transaction.assert_called_once_with("1441914")
            gateway.return_value.refund.assert_not_called()
            gateway.return_value.void.assert_not_called()
            with self.assertRaises(ValidationError):
                request_refund(**(data | dict(request_key=uuid.uuid4())))
        self.assertEqual(imported.operation.state, "succeeded")
        self.assertEqual(plan_paid(plan), Decimal("5.00"))
        self.assertEqual(notices()["refunds"][0].remaining, Decimal("15.00"))
        self.assertEqual(total(plan.original.sale), Decimal("106.18"))
        notice.refresh_from_db()
        self.assertIsNotNone(notice.reviewed_at)
        self.assertIsNotNone(PaymentFollowup.objects.get(operation=plan.original).resolved_at)
        requested = request_refund(
            actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
        )
        self.assertEqual(requested.operation.amount, Decimal("15.00"))

    def test_import_rejects_wrong_amount_parent_and_unsettled_outcome_without_posting(self):
        member = self.prepaid(card=True)
        plan = self.end(member, refund_amount="20.00").refund_plans.get()
        evidence = self.refund_evidence(plan.original)
        for invalid in (
            evidence | dict(amount_details=dict(amount="6.00")),
            evidence | dict(transaction_details=dict(type="credit", reference_number="9999")),
            evidence | dict(status_details=dict(status="pending")),
        ):
            with patch("core.payments.corrections.Gateway") as gateway:
                gateway.return_value.transaction.return_value = invalid
                with self.assertRaises((ProviderFailure, ValidationError)):
                    request_refund(
                        actor=self.owner,
                        plan_id=plan.pk,
                        request_key=uuid.uuid4(),
                        confirmed=True,
                        refund_amount="5.00",
                        completed_provider_reference="1441914",
                    )
                gateway.return_value.refund.assert_not_called()
        self.assertEqual(plan.attempts.count(), 0)
        self.assertEqual(plan_paid(plan), Decimal("0.00"))

    def test_partial_import_does_not_clear_a_different_unrecorded_return(self):
        member = self.prepaid(card=True)
        plan = self.end(member, refund_amount="20.00").refund_plans.get()
        self.reported_refund(plan.original)
        self.reported_refund(plan.original, reference="1441915", value="3.00")
        with patch("core.payments.corrections.Gateway") as gateway:
            gateway.return_value.transaction.return_value = self.refund_evidence(plan.original)
            request_refund(
                actor=self.owner,
                plan_id=plan.pk,
                request_key=uuid.uuid4(),
                confirmed=True,
                refund_amount="5.00",
                completed_provider_reference="1441914",
            )
        self.assertIsNone(PaymentFollowup.objects.get(operation=plan.original).resolved_at)
        with self.assertRaises(ValidationError):
            request_refund(
                actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
            )

    def test_credit_notifications_distinguish_recorded_refunds_and_reopen_for_new_external_money(
        self,
    ):
        from core.payments.webhooks import flag_external_credit

        member = self.prepaid(card=True)
        plan = self.end(member, refund_amount="20.00").refund_plans.get()
        attempt = request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            refund_amount="5.00",
        )
        record_result(
            operation_id=attempt.operation_id,
            state="succeeded",
            source="provider",
            provider_reference="1441914",
        )

        def notify(reference, value):
            with patch("core.payments.gateway.Gateway") as gateway:
                gateway.return_value.transaction.return_value = self.refund_evidence(
                    plan.original, reference, value
                )
                flag_external_credit(
                    SimpleNamespace(
                        provider_reference=reference,
                        facts=dict(original_reference=plan.original.provider_reference),
                    )
                )

        notify("1441914", "5.00")
        self.assertFalse(OwnerNotice.objects.filter(details__kind="payment_correction").exists())
        notify("1441915", "3.00")
        self.assertIsNone(PaymentFollowup.objects.get(operation=plan.original).resolved_at)
        with patch("core.payments.corrections.Gateway") as gateway:
            gateway.return_value.transaction.return_value = self.refund_evidence(
                plan.original, "1441915", "3.00"
            )
            request_refund(
                actor=self.owner,
                plan_id=plan.pk,
                request_key=uuid.uuid4(),
                confirmed=True,
                refund_amount="3.00",
                completed_provider_reference="1441915",
            )
        self.assertIsNotNone(PaymentFollowup.objects.get(operation=plan.original).resolved_at)
        notify("1441916", "2.00")
        notify("1441916", "2.00")
        self.assertIsNone(PaymentFollowup.objects.get(operation=plan.original).resolved_at)
        self.assertEqual(
            OwnerNotice.objects.filter(
                details__kind="payment_correction", reviewed_at__isnull=True
            ).count(),
            1,
        )

    def test_reconciled_existing_unknown_refund_clears_its_original_external_alert(self):
        member = self.prepaid(card=True)
        plan = self.end(member, refund_amount="20.00").refund_plans.get()
        attempt = request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            refund_amount="5.00",
        )
        record_result(
            operation_id=attempt.operation_id,
            state="unknown",
            source="provider",
            provider_reference="1441914",
        )
        notice = self.reported_refund(plan.original)
        record_result(
            operation_id=attempt.operation_id,
            state="succeeded",
            source="provider",
            provider_reference="1441914",
        )
        notice.refresh_from_db()
        self.assertIsNotNone(notice.reviewed_at)
        self.assertIsNotNone(PaymentFollowup.objects.get(operation=plan.original).resolved_at)
        self.assertEqual(plan_paid(plan), Decimal("5.00"))


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
class MembershipCancellationRaceTests(TransactionTestCase):
    buy = MembershipCancellationTests.buy
    succeed = MembershipCancellationTests.succeed
    prepaid = MembershipCancellationTests.prepaid
    inspect = MembershipCancellationTests.inspect
    end = MembershipCancellationTests.end

    def setUp(self):
        from core.models import MembershipPricing, PricingPolicy

        MembershipCancellationTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create(
                subscription="17.99", unlimited="39.99", actor=self.owner
            )
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def race(self, first, second):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL financial concurrency")
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections, connections

        barrier = Barrier(2)

        def attempt(call):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET LOCAL lock_timeout='10s'")
                        result = call()
                        return result.pk if result else None
                except ValidationError:
                    return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(attempt, (first, second)))

    def cancellation(self, member, refund="0.00"):
        data = self.inspect(member, timing="immediate", refund_amount=refund)
        values = dict(
            actor=self.owner,
            member_id=member.pk,
            timing="immediate",
            refund_amount=refund,
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Owner reviewed cancellation.",
            early_override=True,
            send_confirmation=False,
        )
        return lambda: cancel(**values)

    def test_cancel_and_dispatch_cannot_both_win_for_the_same_unstarted_charge(self):
        member = self.buy()
        original = member.installments.first().invoice.sale.operations.get()
        results = self.race(self.cancellation(member), lambda: begin_dispatch(original.pk))
        original.refresh_from_db()
        if MembershipCancellation.objects.exists():
            self.assertEqual(original.state, "cancelled")
            self.assertIsNone(results[1])
        else:
            self.assertEqual(original.state, "sending")
            self.assertIsNone(results[0])
        self.assertFalse(FinancialPosting.objects.exists())

    def test_two_owner_refund_requests_reserve_one_operation(self):
        member = self.prepaid(card=True)
        plan = self.end(member, refund_amount="50.00", send_confirmation=False).refund_plans.get()

        def request():
            return request_refund(
                actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
            )

        results = self.race(request, request)
        self.assertEqual(results.count(None), 1)
        self.assertEqual(MembershipRefundAttempt.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.filter(kind="refund").count(), 1)
        self.assertEqual(plan_paid(plan), Decimal("0.00"))

    def test_generic_correction_and_cancellation_cannot_reserve_the_same_money(self):
        member = self.prepaid(card=True)
        original = member.installments.first().invoice.sale.operations.get()
        allocation = [
            dict(
                line=original.allocation[0]["line"],
                net="40.00",
                fee="0.00",
                item_tax="0.00",
                fee_tax="0.00",
            )
        ]

        def correction():
            return request_operation(
                actor=self.owner,
                sale_id=original.sale_id,
                request_key=uuid.uuid4(),
                tender="card",
                kind="refund",
                original_id=original.pk,
                method_id=original.method_id,
                allocation=allocation,
                purpose="correction",
            )

        results = self.race(self.cancellation(member, "100.00"), correction)
        self.assertEqual(results.count(None), 1)
        self.assertNotEqual(
            MembershipCancellation.objects.exists(),
            PaymentOperation.objects.filter(kind="refund").exists(),
        )
        self.assertEqual(received(original.sale), Decimal("111.18"))
