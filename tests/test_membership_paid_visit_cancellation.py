"""Original visit money is separate from a cancelled first membership payment."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.customer_credit_records import CustomerCreditApplication, VisitMembershipConversion
from core.membership_cancellations import cancel, plan_paid, request_refund
from core.membership_cancellations import review as cancellation_review
from core.membership_paid_visit_cancellation import release, review
from core.membership_paid_visit_pending import complete, stop_facts
from core.membership_paid_visit_records import (
    MembershipPaidVisitCancellation,
    MembershipPaidVisitRelease,
)
from core.membership_paid_visit_recovery import request as recover
from core.membership_paid_visit_recovery import review as recovery_review
from core.membership_sales import membership_status
from core.models import FinancialLineAdjustment, OwnerNotice, PaymentMethod, PaymentOperation
from core.payments.invoices import received, total
from core.payments.ledger import record_result
from core.payments.operations import begin_dispatch
from tests import test_membership_paid_visit_card as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitCancellationTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PaidVisitCardTests.prepare
    buy_card = fixtures.PaidVisitCardTests.buy_card

    def funded(self, *, recovery=False):
        self.buy_card()
        if recovery:
            begin_dispatch(self.operation.pk)
            record_result(operation_id=self.operation.pk, state="declined", source="provider")
            self.other = PaymentMethod.objects.create(
                customer=self.member.customer,
                provider_customer=self.method.provider_customer,
                provider_method="synthetic-cancel-card-6789",
                environment="sandbox",
                brand="Visa",
                last_four="6789",
                reusable=True,
                consent_version=self.method.consent_version,
                consent_at=self.method.consent_at,
            )
            data = recovery_review(
                actor=self.staff, intent_id=self.intent.pk, method_id=self.other.pk
            )
            self.operation = recover(
                actor=self.staff,
                intent_id=self.intent.pk,
                method_id=self.other.pk,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                confirmed=True,
            ).operation
        self.assertIsNotNone(begin_dispatch(self.operation.pk))
        record_result(
            operation_id=self.operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="993001",
        )

    def cancelled(self, *, refund="1.97", timing="immediate", recovery=False):
        self.funded(recovery=recovery)
        options = dict(
            actor=self.owner, member_id=self.member.pk, timing=timing, refund_amount=refund
        )
        data = cancellation_review(**options)
        self.cancellation = cancel(
            **options,
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Customer keeps the original visit and cancels membership",
            early_override=True,
            send_confirmation=False,
        )
        self.member.billing_state.refresh_from_db()

    def return_funds(self, *, amount=None, unknown=False):
        plan = self.cancellation.refund_plans.get()
        attempt = request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            refund_amount=amount,
        )
        self.assertIsNotNone(begin_dispatch(attempt.operation.pk))
        record_result(
            operation_id=attempt.operation.pk,
            state="unknown" if unknown else "succeeded",
            source="provider",
            provider_reference="" if unknown else "993002",
        )
        return attempt

    def finish(self, **changes):
        from core.membership_paid_visit_pending import locked

        with transaction.atomic():
            data = review(actor=self.owner, intent=locked(self.intent.pk))
        options = dict(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            reason="Keep the paid visit and its original receipt",
            confirmed=True,
        )
        options.update(changes)
        return release(**options)

    def test_effective_cancel_and_recorded_return_release_only_uncollected_source(self):
        self.cancelled()
        self.return_funds()
        first = self.member.installments.first()
        self.assertEqual(total(first.invoice.sale), Decimal("16.08"))
        self.assertEqual(received(first.invoice.sale), Decimal(".06"))
        self.assertFalse(stop_facts(self.intent)["allowed"])
        before = PaymentOperation.objects.count()
        with self.runtime_role():
            result = self.finish()
        self.assertEqual(result.cancellation_id, self.cancellation.pk)
        self.assertEqual(result.facts["uncollected"], "16.02")
        self.assertEqual(result.facts["returned"], "1.97")
        self.assertEqual(result.facts["retained_fee"], "0.06")
        self.assertEqual(total(first.invoice.sale), Decimal(".06"))
        self.assertEqual(received(first.invoice.sale), Decimal(".06"))
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertEqual(received(self.original), Decimal("16.47"))
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertFalse(CustomerCreditApplication.objects.exists())
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertFalse(self.visit.membership_benefits.exists())
        self.assertEqual(membership_status(self.member), "cancelled")
        self.assertEqual(complete(self.intent.pk).kind, "stopped")
        self.assertFalse(
            OwnerNotice.objects.filter(
                details__kind="paid_visit_membership", reviewed_at__isnull=True
            ).exists()
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_due_and_unknown_refunds_cannot_release_the_original_visit(self):
        self.cancelled()
        for unknown in (False, True):
            if unknown:
                self.return_funds(unknown=True)
            with self.subTest(unknown=unknown), self.assertRaises(ValidationError):
                self.finish()
        self.assertFalse(MembershipPaidVisitRelease.objects.exists())
        self.assertFalse(
            FinancialLineAdjustment.objects.filter(reason="membership_uncollected").exists()
        )
        self.assertEqual(total(self.original), Decimal("16.47"))

    def test_owner_refund_choice_can_retain_principal_without_inventing_another_refund(self):
        self.cancelled(refund="1.00")
        self.return_funds()
        result = self.finish()
        self.assertEqual(result.facts["retained"], "1.03")
        self.assertEqual(result.facts["retained_principal"], "0.97")
        self.assertEqual(total(self.member.installments.first().invoice.sale), Decimal("1.03"))
        self.assertEqual(plan_paid(self.cancellation.refund_plans.get()), Decimal("1.00"))

    def test_no_refund_owner_choice_retains_only_actual_new_money(self):
        self.cancelled(refund="0")
        result = self.finish()
        self.assertEqual(result.facts["retained"], "2.03")
        self.assertEqual(result.facts["uncollected"], "16.02")
        self.assertEqual(total(self.member.installments.first().invoice.sale), Decimal("2.03"))
        self.assertFalse(self.cancellation.refund_plans.exists())

    def test_known_funds_without_cancellation_and_future_cancellation_are_guarded(self):
        self.funded()
        with self.assertRaises(ValidationError):
            self.finish()
        options = dict(
            actor=self.owner, member_id=self.member.pk, timing="end_cycle", refund_amount="0"
        )
        data = cancellation_review(**options)
        cancel(
            **options,
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            reason="End later",
            early_override=True,
            send_confirmation=False,
        )
        with self.assertRaisesMessage(ValidationError, "not effective yet"):
            self.finish()

    def test_recovery_refund_keeps_actual_new_card_and_future_card_separate(self):
        self.cancelled(recovery=True)
        plan = self.cancellation.refund_plans.get()
        self.assertEqual(plan.original.method_id, self.other.pk)
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)
        attempt = self.return_funds()
        self.assertEqual(attempt.operation.method_id, self.other.pk)
        self.finish()
        self.assertEqual(total(self.original), Decimal("16.47"))

    def test_replay_preserves_one_adjustment_and_rejects_changed_authority(self):
        self.cancelled()
        self.return_funds()
        result = self.finish()
        self.assertEqual(
            release(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=result.request_key,
                reviewed=result.facts["reviewed_hash"],
                reason=result.reason,
                confirmed=True,
            ).pk,
            result.pk,
        )
        for changes in (dict(confirmed=False), dict(reason="Another reason"), dict(reviewed="old")):
            args = dict(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=result.request_key,
                reviewed=result.facts["reviewed_hash"],
                reason=result.reason,
                confirmed=True,
            )
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                release(**args)
        self.assertEqual(
            FinancialLineAdjustment.objects.filter(reason="membership_uncollected").count(), 1
        )

    def test_stale_source_review_is_refused_without_another_financial_fact(self):
        from core.membership_paid_visit_pending import locked
        from core.models import Booking

        self.cancelled()
        self.return_funds()
        with transaction.atomic():
            data = review(actor=self.owner, intent=locked(self.intent.pk))
        Booking.objects.filter(pk=self.visit.pk).update(edit_version=self.visit.edit_version + 1)
        with self.assertRaisesMessage(ValidationError, "changed"):
            release(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                reason="Keep visit",
                confirmed=True,
            )
        self.assertFalse(MembershipPaidVisitCancellation.objects.exists())

    def test_staff_cannot_release_or_cancel_the_uncollected_amount(self):
        self.cancelled()
        self.return_funds()
        with self.assertRaises(PermissionDenied):
            self.finish(actor=self.staff)

    def test_sql_refuses_untyped_release_of_retained_membership_money(self):
        self.cancelled()
        self.return_funds()
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipPaidVisitRelease.objects.create(
                intent=self.intent,
                request_key=uuid.uuid4(),
                kind="stopped",
                actor=self.owner,
                reason="Cannot bypass the retained fee scope",
            )

    def test_missing_uncollected_adjustment_cannot_commit(self):
        self.cancelled()
        self.return_funds()
        with self.assertRaises(DatabaseError), transaction.atomic():
            with patch("core.models.FinancialLineAdjustment.objects.create"):
                self.finish()
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertFalse(MembershipPaidVisitCancellation.objects.exists())
        self.assertFalse(MembershipPaidVisitRelease.objects.exists())

    def test_writeoff_failure_rolls_back_release_but_preserves_actual_return_for_retry(self):
        self.cancelled()
        self.return_funds()
        count = PaymentOperation.objects.count()
        with patch(
            "core.models.FinancialLineAdjustment.objects.create",
            side_effect=RuntimeError("local writeoff failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.finish()
        self.assertFalse(MembershipPaidVisitRelease.objects.exists())
        self.assertEqual(received(self.member.installments.first().invoice.sale), Decimal(".06"))
        self.finish()
        self.assertEqual(PaymentOperation.objects.count(), count)

    def test_owner_page_records_release_without_an_extra_screen_or_new_payment(self):
        from core.communications.models import MessageDelivery

        self.cancelled()
        verified_owner_login(self.client, self.owner)
        url = reverse("membership_overview", args=[self.member.pk])
        self.assertNotContains(self.client.get(url), 'value="paid_visit_cancelled_release"')
        self.return_funds()
        page = self.client.get(url)
        control = page.context["paid_visit_cancellation"]
        self.assertContains(page, "Release original visit funds")
        before = (PaymentOperation.objects.count(), MessageDelivery.objects.count())
        data = dict(
            action="paid_visit_cancelled_release",
            request_key=str(control["key"]),
            reviewed=control["reviewed"],
            reason="Keep original paid visit",
            confirm_release="yes",
        )
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertContains(self.client.get(url), "Uncollected membership amount cancelled")
        self.assertEqual(
            (PaymentOperation.objects.count(), MessageDelivery.objects.count()), before
        )

    def test_applied_credit_cancellation_policy_is_not_bypassed(self):
        self.funded()
        complete(self.intent.pk)
        with self.assertRaisesMessage(ValidationError, "applied customer credit"):
            cancellation_review(
                actor=self.owner, member_id=self.member.pk, timing="immediate", refund_amount="1.97"
            )
        self.assertFalse(MembershipPaidVisitCancellation.objects.exists())

    def test_original_source_can_support_a_separately_accepted_purchase_after_release(self):
        from core.membership_paid_visit_records import MembershipPaidVisitIntent
        from core.membership_sales import offer, purchase

        self.cancelled()
        self.return_funds()
        self.finish()
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
        data = offer(**self.options)
        other = purchase(
            **self.options,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            accepted=True,
            method_id=self.method.pk,
        )
        self.assertNotEqual(other.pk, self.member.pk)
        current = MembershipPaidVisitIntent.objects.get(purchase=other)
        begin_dispatch(current.operation_id)
        record_result(
            operation_id=current.operation_id,
            state="succeeded",
            source="provider",
            provider_reference="993003",
        )
        complete(current.pk)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(total(self.member.installments.first().invoice.sale), Decimal(".06"))
        self.assertEqual(total(self.original), Decimal(".45"))

    def test_cancellation_immediately_keeps_source_notice_until_release_without_a_worker(self):
        self.cancelled()
        notices = OwnerNotice.objects.filter(
            details__kind="paid_visit_membership", reviewed_at__isnull=True
        )
        self.assertEqual(notices.count(), 1)
        self.return_funds()
        self.assertEqual(notices.count(), 1)
        self.finish()
        self.assertEqual(notices.count(), 0)

    def test_service_and_sql_refuse_a_historical_refund_using_another_card(self):
        from django.utils import timezone

        from core.membership_paid_visit_pending import locked
        from core.membership_records import MembershipRefundAttempt

        self.cancelled(recovery=True)
        plan = self.cancellation.refund_plans.get()
        # Simulate invalid old evidence; no provider is called for this fixture.
        wrong = PaymentOperation.objects.create(
            request_key=uuid.uuid4(),
            fingerprint="a" * 64,
            sale=self.operation.sale,
            original=self.operation,
            actor=self.owner,
            tender="card",
            kind="refund",
            purpose="correction",
            method=self.method,
            amount=plan.amount,
            allocation=plan.allocation,
        )
        MembershipRefundAttempt.objects.create(
            id=uuid.uuid4(), plan=plan, operation=wrong, actor=self.owner, fingerprint="b" * 64
        )
        begin_dispatch(wrong.pk)
        record_result(
            operation_id=wrong.pk, state="succeeded", source="provider", provider_reference="993004"
        )
        with self.assertRaisesMessage(ValidationError, "separate payment correction"):
            self.finish()
        with (
            transaction.atomic(),
            patch("core.membership_paid_visit_cancellation.check_return_source"),
        ):
            facts = review(actor=self.owner, intent=locked(self.intent.pk))
        facts["reviewed_hash"] = facts["fingerprint"]
        facts["adjustment_key"] = str(uuid.uuid4())
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipPaidVisitCancellation.objects.create(
                release_id=self.intent.pk,
                cancellation=self.cancellation,
                actor=self.owner,
                request_key=uuid.uuid4(),
                facts=facts,
                reason="Invalid source must not close",
                fingerprint="c" * 64,
                created_at=timezone.now(),
            )
        self.assertFalse(MembershipPaidVisitCancellation.objects.exists())
