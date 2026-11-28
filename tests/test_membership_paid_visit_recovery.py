"""Explicit replacement requests retain the original source and every attempt."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.customer_credit import applied
from core.customer_credit_records import VisitMembershipConversion
from core.membership_paid_visit_pending import complete, context, stop, stop_facts
from core.membership_paid_visit_records import MembershipPaidVisitRecovery
from core.membership_paid_visit_recovery import request as recover
from core.membership_paid_visit_recovery import review
from core.membership_sales import installment_paid
from core.models import PaymentMethod, PaymentOperation
from core.payments.invoices import received, total
from core.payments.ledger import record_result, request_operation
from core.payments.operations import begin_dispatch, execute
from tests import test_membership_paid_visit_card as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitRecoveryTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PaidVisitCardTests.prepare
    buy_card = fixtures.PaidVisitCardTests.buy_card

    def decline(self, operation=None):
        operation = operation or self.operation
        self.assertIsNotNone(begin_dispatch(operation.pk))
        record_result(operation_id=operation.pk, state="declined", source="provider")

    def setup_decline(self):
        self.buy_card()
        self.decline()
        self.key = uuid.uuid4()
        self.data = review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)

    def request(self, **changes):
        options = dict(
            actor=self.staff,
            intent_id=self.intent.pk,
            method_id=self.method.pk,
            request_key=self.key,
            reviewed=self.data["fingerprint"],
            confirmed=True,
        )
        options.update(changes)
        return recover(**options)

    def test_explicit_retry_has_exact_new_request_and_no_unfunded_conversion(self):
        self.setup_decline()
        with self.runtime_role():
            authority = self.request()
        self.assertEqual(authority.operation.amount, Decimal("2.03"))
        self.assertEqual(authority.operation.state, "ready")
        self.assertNotEqual(authority.operation.pk, self.operation.pk)
        self.assertEqual(authority.previous_id, self.operation.pk)
        self.assertEqual(authority.sequence, 1)
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertEqual(received(self.member.installments.first().invoice.sale), 0)
        self.assertEqual(PaymentOperation.objects.count(), 3)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_confirmed_retry_completes_same_purchase_and_uses_source_once(self):
        self.setup_decline()
        authority = self.request()
        op = authority.operation
        self.assertIsNotNone(begin_dispatch(op.pk))
        record_result(
            operation_id=op.pk, state="succeeded", source="provider", provider_reference="991301"
        )
        first = self.member.installments.first()
        self.assertEqual(received(first.invoice.sale), Decimal("2.03"))
        with self.runtime_role():
            release = complete(self.intent.pk)
        self.assertEqual(release.kind, "completed")
        self.assertTrue(installment_paid(first))
        self.assertEqual(applied(first.invoice.sale), Decimal("16.02"))
        self.assertEqual(total(self.original), Decimal(".45"))
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(complete(self.intent.pk).pk, release.pk)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_replay_and_changed_identity_do_not_create_another_request(self):
        self.setup_decline()
        authority = self.request()
        self.assertEqual(self.request().pk, authority.pk)
        for changes in (dict(confirmed=False), dict(reviewed="bad"), dict(actor=self.owner)):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.request(**changes)
        self.assertEqual(MembershipPaidVisitRecovery.objects.count(), 1)

    def test_ready_and_unknown_results_block_another_request_and_unknown_stop(self):
        self.setup_decline()
        authority = self.request()
        for state in ("ready", "unknown"):
            if state == "unknown":
                begin_dispatch(authority.operation.pk)
                record_result(operation_id=authority.operation.pk, state=state, source="provider")
            with self.subTest(state=state), self.assertRaises(ValidationError):
                review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)
        self.assertFalse(stop_facts(self.intent)["allowed"])
        with patch("core.payments.operations.Gateway") as gateway:
            execute(authority.operation.pk)
        gateway.return_value.charge.assert_not_called()
        gateway.return_value.refund.assert_not_called()
        gateway.return_value.void.assert_not_called()
        self.assertFalse(context(self.member)["can_complete"])
        self.assertEqual(total(self.original), Decimal("16.47"))

    def test_second_decline_allows_fresh_authority_but_rejects_old_review(self):
        self.setup_decline()
        first = self.request()
        self.decline(first.operation)
        with self.assertRaises(ValidationError):
            self.request(request_key=uuid.uuid4())
        self.key = uuid.uuid4()
        self.data = review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)
        second = self.request()
        self.assertEqual(second.sequence, 2)
        self.assertEqual(second.previous_id, first.operation.pk)
        self.assertEqual(PaymentOperation.objects.count(), 4)
        self.assertIsNotNone(begin_dispatch(second.operation.pk))
        record_result(
            operation_id=second.operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="991302",
        )
        complete(self.intent.pk)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_different_saved_card_does_not_change_future_billing_or_original_attempt(self):
        self.setup_decline()
        other = PaymentMethod.objects.create(
            customer=self.member.customer,
            reusable=True,
            environment="sandbox",
            state="active",
            provider_method="fictional-recovery-card",
            provider_customer=self.method.provider_customer,
            consent_version=self.method.consent_version,
            consent_at=self.method.consent_at,
            brand="Visa",
            last_four="6789",
        )
        data = review(actor=self.staff, intent_id=self.intent.pk, method_id=other.pk)
        authority = self.request(method_id=other.pk, reviewed=data["fingerprint"])
        self.assertEqual(authority.operation.method_id, other.pk)
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.method_id, self.method.pk)
        self.assertEqual(self.operation.state, "declined")

    def test_unknown_original_and_unverified_confirmation_cannot_be_bypassed(self):
        self.buy_card()
        begin_dispatch(self.operation.pk)
        record_result(operation_id=self.operation.pk, state="unknown", source="provider")
        with self.assertRaises(ValidationError):
            review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)
        self.assertFalse(MembershipPaidVisitRecovery.objects.exists())

    def test_fresh_retry_expiry_does_not_extend_or_release_original_source(self):
        self.setup_decline()
        authority = self.request()
        with patch(
            "core.membership_paid_visit_recovery.timezone.now",
            return_value=authority.expires_at + timedelta(seconds=1),
        ):
            self.assertIsNone(begin_dispatch(authority.operation.pk))
        authority.operation.refresh_from_db()
        self.assertEqual(authority.operation.state, "cancelled")
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertTrue(stop_facts(self.intent)["allowed"])

    def test_owner_stop_cancels_latest_ready_request_and_dispatch_cannot_resume_it(self):
        self.setup_decline()
        authority = self.request()
        stop(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=stop_facts(self.intent)["fingerprint"],
            reason="Keep paid visit",
        )
        authority.operation.refresh_from_db()
        self.assertEqual(authority.operation.state, "cancelled")
        self.assertIsNone(begin_dispatch(authority.operation.pk))
        with self.assertRaises(ValidationError):
            review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)
        self.assertEqual(total(self.original), Decimal("16.47"))

    def test_sql_blocks_unscoped_replacement_even_after_known_decline(self):
        self.setup_decline()
        with self.assertRaises(DatabaseError), transaction.atomic():
            PaymentOperation.objects.create(
                request_key=uuid.uuid4(),
                fingerprint="a" * 64,
                sale=self.operation.sale,
                kind="receipt",
                purpose="member_purchase",
                tender="card",
                method=self.method,
                actor=self.staff,
                amount=Decimal("2.03"),
                allocation=self.operation.allocation,
            )
        with self.assertRaises(ValidationError):
            request_operation(
                actor=self.staff,
                sale_id=self.operation.sale_id,
                request_key=uuid.uuid4(),
                tender="card",
                method_id=self.method.pk,
                purpose="member_purchase",
                allocation=self.operation.allocation,
            )

    def test_other_customer_card_and_missing_confirmation_are_rejected(self):
        self.setup_decline()
        with self.assertRaises(ValidationError):
            self.request(confirmed=False)
        with self.assertRaises(ValidationError):
            review(actor=self.staff, intent_id=self.intent.pk, method_id=uuid.uuid4())
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_same_page_form_requests_one_exact_remainder_and_replays_safely(self):
        self.setup_decline()
        verified_owner_login(self.client, self.staff)
        url = reverse("membership_overview", args=[self.member.pk])
        response = self.client.get(url)
        self.assertContains(response, "Try a card payment again")
        controls = response.context["paid_visit_recovery"]
        post = dict(
            action="paid_visit_card_recover",
            request_key=str(controls["key"]),
            card_choice=controls["choices"][0]["value"],
            confirmed="on",
        )
        self.assertEqual(self.client.post(url, post).status_code, 302)
        self.assertEqual(self.client.post(url, post).status_code, 302)
        self.assertEqual(MembershipPaidVisitRecovery.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertNotContains(self.client.get(url), "Try a card payment again")

    def test_expired_original_unattempted_request_needs_fresh_authority(self):
        self.buy_card()
        from django.utils import timezone

        later = self.intent.expires_at + timedelta(seconds=1)
        with patch("core.membership_paid_visit_pending.timezone.now", return_value=later):
            self.assertIsNone(begin_dispatch(self.operation.pk))
            self.key = uuid.uuid4()
            self.data = review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)
            authority = self.request()
            self.assertGreater(authority.expires_at, timezone.now())
            self.assertIsNotNone(begin_dispatch(authority.operation.pk))
        self.assertEqual(total(self.original), Decimal("16.47"))

    def test_deactivated_reviewed_card_cancels_before_post_without_releasing_source(self):
        self.setup_decline()
        authority = self.request()
        PaymentMethod.objects.filter(pk=self.method.pk).update(state="inactive")
        with patch("core.payments.operations.Gateway") as gateway:
            execute(authority.operation.pk)
        gateway.return_value.charge.assert_not_called()
        authority.operation.refresh_from_db()
        self.assertEqual(authority.operation.state, "cancelled")
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertFalse(VisitMembershipConversion.objects.exists())

    def test_authority_without_its_exact_ledger_operation_cannot_commit(self):
        self.setup_decline()
        key = uuid.uuid4()
        from django.utils import timezone

        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipPaidVisitRecovery.objects.create(
                id=key,
                intent=self.intent,
                previous=self.operation,
                operation_id=uuid.uuid4(),
                sequence=1,
                actor=self.staff,
                method=self.method,
                fingerprint=self.data["fingerprint"],
                review=self.data,
                expires_at=timezone.now() + timedelta(minutes=30),
            )
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertFalse(MembershipPaidVisitRecovery.objects.exists())

    def test_direct_ledger_call_requires_the_typed_immutable_authority(self):
        self.setup_decline()
        with self.assertRaises(PermissionDenied):
            request_operation(
                actor=self.staff,
                sale_id=self.operation.sale_id,
                request_key=uuid.uuid4(),
                tender="card",
                method_id=self.method.pk,
                purpose="member_purchase",
                allocation=self.operation.allocation,
                paid_visit_recovery={"intent": str(self.intent.pk)},
            )
        self.assertFalse(MembershipPaidVisitRecovery.objects.exists())

    def test_later_installment_dispatch_does_not_reuse_the_first_payment_recovery_scope(self):
        from core.membership_payments import collect_installment, payment_review
        from tests.test_membership_renewals import clock

        self.setup_decline()
        authority = self.request()
        begin_dispatch(authority.operation.pk)
        record_result(
            operation_id=authority.operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="991303",
        )
        complete(self.intent.pk)
        later = self.member.installments.get(number=2)
        with clock(later.due_on):
            data = payment_review(
                actor=self.staff, member_id=self.member.pk, installment_id=later.pk, tender="card"
            )
            action = collect_installment(
                actor=self.staff,
                member_id=self.member.pk,
                installment_id=later.pk,
                tender="card",
                reviewed=data["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
            )
            sending = begin_dispatch(action.operation.pk)
        self.assertIsNotNone(sending)
        self.assertEqual(sending.state, "sending")
        self.assertEqual(sending.amount, Decimal("18.53"))
        self.assertEqual(sending.method_id, self.method.pk)
        self.assertEqual(total(self.original), Decimal(".45"))
        self.assertEqual(applied(self.member.installments.first().invoice.sale), Decimal("16.02"))
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 1)

    def test_new_failure_after_a_historical_acknowledgment_creates_one_fresh_owner_notice(self):
        from django.utils import timezone

        from core.membership_paid_visit_pending import mark_review
        from core.models import OwnerNotice

        self.setup_decline()
        notices = OwnerNotice.objects.filter(details__kind="paid_visit_membership")
        # Older releases allowed generic acknowledgment without resolving funds.
        notices.update(reviewed_at=timezone.now(), reviewed_by=self.owner)
        authority = self.request()
        self.decline(authority.operation)
        mark_review(self.intent.pk)
        self.assertEqual(notices.count(), 2)
        self.assertEqual(notices.filter(reviewed_at__isnull=True).count(), 1)

    def test_dashboard_links_the_application_and_does_not_dismiss_unresolved_funds(self):
        from core.models import OwnerNotice

        self.setup_decline()
        notice = OwnerNotice.objects.get(details__kind="paid_visit_membership")
        verified_owner_login(self.client, self.owner)
        page = self.client.get(reverse("dashboard"))
        self.assertContains(
            page, reverse("membership_overview", args=[self.member.pk]) + "#paid-visit-application"
        )
        self.assertContains(page, "The paid visit stays unchanged")
        response = self.client.post(reverse("review_notice", args=[notice.pk]), follow=True)
        self.assertContains(response, "Complete or safely stop the paid-visit application")
        notice.refresh_from_db()
        self.assertIsNone(notice.reviewed_at)
        authority = self.request()
        begin_dispatch(authority.operation.pk)
        record_result(operation_id=authority.operation.pk, state="unknown", source="provider")
        self.client.post(reverse("review_notice", args=[notice.pk]))
        notice.refresh_from_db()
        self.assertIsNone(notice.reviewed_at)
        record_result(
            operation_id=authority.operation.pk,
            state="succeeded",
            source="reconcile",
            provider_reference="991304",
        )
        complete(self.intent.pk)
        notice.refresh_from_db()
        self.assertIsNotNone(notice.reviewed_at)
        self.assertNotContains(
            self.client.get(reverse("dashboard")), "Review paid visit and membership"
        )
