"""A first card remainder never spends original visit funds before its result."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from core.customer_credit import applied
from core.customer_credit_records import VisitMembershipConversion
from core.membership_paid_visit_pending import complete, stop, stop_facts
from core.membership_paid_visit_records import MembershipPaidVisitIntent, MembershipPaidVisitRelease
from core.membership_payments import payment_review
from core.membership_sales import installment_paid, membership_status, offer, purchase
from core.models import DurableJob, MembershipDraft, PaymentOperation
from core.payments.invoices import received, total
from core.payments.ledger import record_result, request_operation
from core.payments.operations import begin_dispatch
from tests import test_membership_paid_visit as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitCardTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PaidVisitPurchaseTests.prepare

    def buy_card(self, **changes):
        self.prepare(card=True, expected_method="card", **changes)
        data = offer(**self.options)
        self.reviewed = data
        self.key = uuid.uuid4()
        self.member = purchase(
            **self.options,
            request_key=self.key,
            reviewed=data["fingerprint"],
            accepted=True,
            method_id=self.method.pk,
        )
        self.intent = MembershipPaidVisitIntent.objects.get(purchase=self.member)
        self.operation = self.intent.operation
        return self.member

    def approve(self):
        self.assertIsNotNone(begin_dispatch(self.operation.pk))
        record_result(
            operation_id=self.operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="441901",
        )

    def test_review_prices_only_the_new_card_remainder(self):
        self.prepare(card=True, expected_method="card")
        data = offer(**self.options)
        self.assertEqual(data["paid_visit"]["applied"], "16.02")
        self.assertEqual(data["first_payment_total"], "2.03")
        self.assertEqual(data["installments"][0]["quote"]["processing_fee"], "0.06")
        self.assertEqual(data["installments"][1]["quote"]["total"], "18.53")
        self.assertFalse(MembershipPaidVisitIntent.objects.exists())
        self.assertEqual(received(self.original), Decimal("16.47"))

    def test_pending_purchase_has_one_bounded_request_and_no_credit_or_benefits(self):
        with self.runtime_role():
            self.buy_card()
        self.assertEqual(self.operation.amount, Decimal("2.03"))
        self.assertEqual(self.operation.state, "ready")
        self.assertEqual(membership_status(self.member), "pending")
        self.assertEqual(received(self.member.installments.first().invoice.sale), 0)
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertFalse(self.visit.membership_benefits.exists())
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertEqual(
            DurableJob.objects.filter(
                kind="payment_dispatch", reference=str(self.operation.pk)
            ).count(),
            1,
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS core_paid_visit_card_complete IMMEDIATE")

    def test_known_card_receipt_commits_before_a_separate_atomic_completion(self):
        self.buy_card()
        self.approve()
        first = self.member.installments.first()
        self.assertEqual(received(first.invoice.sale), Decimal("2.03"))
        self.assertFalse(installment_paid(first))
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(
            DurableJob.objects.filter(
                kind="membership_paid_visit", reference=str(self.intent.pk)
            ).count(),
            1,
        )
        with self.runtime_role():
            released = complete(self.intent.pk)
        self.assertEqual(released.kind, "completed")
        self.assertEqual(total(self.original), Decimal(".45"))
        self.assertEqual(applied(first.invoice.sale), Decimal("16.02"))
        self.assertEqual(received(first.invoice.sale), Decimal("2.03"))
        self.assertTrue(installment_paid(first))
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(complete(self.intent.pk).pk, released.pk)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS core_paid_visit_card_complete IMMEDIATE")

    def test_unknown_outcome_retains_source_and_blocks_owner_stop_and_generic_collection(self):
        self.buy_card()
        begin_dispatch(self.operation.pk)
        record_result(operation_id=self.operation.pk, state="unknown", source="provider")
        self.assertFalse(stop_facts(self.intent)["allowed"])
        with self.assertRaises(ValidationError):
            stop(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=uuid.uuid4(),
                reviewed=stop_facts(self.intent)["fingerprint"],
                reason="Review unknown outcome",
            )
        with self.assertRaisesMessage(ValidationError, "paid-visit application"):
            payment_review(
                actor=self.staff,
                member_id=self.member.pk,
                installment_id=self.member.installments.first().pk,
                tender="cash",
            )
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertFalse(MembershipPaidVisitRelease.objects.exists())
        self.assertEqual(received(self.original), Decimal("16.47"))

    def test_original_source_refund_and_another_conversion_are_blocked(self):
        self.buy_card()
        original = self.original.operations.get()
        with self.assertRaisesMessage(ValidationError, "reserved"):
            request_operation(
                actor=self.owner,
                sale_id=self.original.pk,
                request_key=uuid.uuid4(),
                tender="card",
                kind="refund",
                purpose="correction",
                original_id=original.pk,
                method_id=original.method_id,
                allocation=original.allocation,
            )
        with self.assertRaisesMessage(ValidationError, "reserved"):
            offer(**self.options)
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_owner_can_stop_an_unattempted_request_without_refund_or_releasing_unknowns(self):
        self.buy_card()
        facts = stop_facts(self.intent)
        release = stop(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=facts["fingerprint"],
            reason="Customer chose to keep this visit",
        )
        self.assertEqual(release.kind, "stopped")
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.state, "cancelled")
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS core_paid_visit_card_complete IMMEDIATE")

    def test_late_completion_failure_does_not_roll_back_known_card_money_or_release_source(self):
        self.buy_card()
        self.approve()
        with (
            patch(
                "core.membership_paid_visit.queue_confirmation",
                side_effect=ValidationError("fictional late failure"),
            ),
            self.assertRaises(ValidationError),
        ):
            complete(self.intent.pk)
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.state, "succeeded")
        self.assertEqual(received(self.member.installments.first().invoice.sale), Decimal("2.03"))
        self.assertFalse(MembershipPaidVisitRelease.objects.exists())
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(total(self.original), Decimal("16.47"))
        from core.models import OwnerNotice

        self.assertTrue(
            OwnerNotice.objects.filter(
                details__kind="paid_visit_membership", reviewed_at__isnull=True
            ).exists()
        )
        complete(self.intent.pk)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertFalse(
            OwnerNotice.objects.filter(
                details__kind="paid_visit_membership", reviewed_at__isnull=True
            ).exists()
        )

    def test_expired_unattempted_dispatch_cancels_only_request_and_keeps_source_reserved(self):
        self.buy_card()
        with patch(
            "django.utils.timezone.now", return_value=self.intent.expires_at + timedelta(minutes=1)
        ):
            self.assertIsNone(begin_dispatch(self.operation.pk))
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.state, "cancelled")
        self.assertFalse(MembershipPaidVisitRelease.objects.exists())
        self.assertFalse(VisitMembershipConversion.objects.exists())

    def test_deferred_guard_refuses_purchase_without_its_durable_intent(self):
        self.prepare(card=True, expected_method="card")
        data = offer(**self.options)
        with self.assertRaisesMessage(DatabaseError, "durable reservation"), transaction.atomic():
            with patch("core.membership_paid_visit_pending.create"):
                purchase(
                    **self.options,
                    request_key=uuid.uuid4(),
                    reviewed=data["fingerprint"],
                    accepted=True,
                    method_id=self.method.pk,
                )
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS core_paid_visit_card_complete IMMEDIATE")
        self.assertFalse(MembershipDraft.objects.exists())

    def test_full_source_credit_needs_no_zero_card_request(self):
        self.buy_card(children=2, adults=2)
        self.assertIsNone(self.operation)
        self.assertEqual(
            MembershipPaidVisitRelease.objects.get(intent=self.intent).kind, "completed"
        )
        self.assertFalse(self.member.installments.first().invoice.sale.operations.exists())
        self.assertTrue(installment_paid(self.member.installments.first()))
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 2)

    def test_decline_notice_disappears_only_after_explicit_safe_owner_stop(self):
        from core.models import OwnerNotice

        self.buy_card()
        begin_dispatch(self.operation.pk)
        record_result(
            operation_id=self.operation.pk,
            state="declined",
            source="provider",
            provider_reference="441903",
        )
        self.assertTrue(
            OwnerNotice.objects.filter(
                details__kind="paid_visit_membership", reviewed_at__isnull=True
            ).exists()
        )
        facts = stop_facts(self.intent)
        stop(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=facts["fingerprint"],
            reason="Keep original visit",
        )
        self.assertFalse(
            OwnerNotice.objects.filter(
                details__kind="paid_visit_membership", reviewed_at__isnull=True
            ).exists()
        )
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertFalse(VisitMembershipConversion.objects.exists())

    def test_raw_source_refund_is_refused_by_the_database_guard(self):
        self.buy_card()
        original = self.original.operations.get()
        with self.assertRaisesMessage(DatabaseError, "reserved"), transaction.atomic():
            PaymentOperation.objects.create(
                request_key=uuid.uuid4(),
                fingerprint="f" * 64,
                sale=self.original,
                kind="refund",
                purpose="correction",
                tender="card",
                amount=original.amount,
                original=original,
                method=original.method,
                allocation=original.allocation,
                actor=self.owner,
            )
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_generic_credit_cannot_fund_the_unresolved_reserved_invoice(self):
        from core.customer_credit import review
        from core.customer_credit_records import CustomerCreditApplication

        self.buy_card()
        first = self.member.installments.first()
        with self.assertRaisesMessage(ValidationError, "paid-visit application"):
            review(actor=self.staff, member_id=self.member.pk, installment_id=first.pk, value="1")
        with (
            self.assertRaisesMessage(DatabaseError, "Conditional paid visit"),
            transaction.atomic(),
        ):
            CustomerCreditApplication.objects.create(
                id=uuid.uuid4(),
                customer=self.customer,
                sale=first.invoice.sale,
                amount="1",
                fingerprint="f" * 64,
                details={},
                actor=self.staff,
            )
        self.assertFalse(installment_paid(first))

    def test_deferred_completion_requires_actual_benefit_usage(self):
        self.buy_card()
        self.approve()
        with self.assertRaisesMessage(DatabaseError, "actual benefit use"), transaction.atomic():
            with patch("core.membership_conversion.use_benefits"):
                complete(self.intent.pk)
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS core_paid_visit_card_complete IMMEDIATE")
        self.assertFalse(MembershipPaidVisitRelease.objects.exists())
        self.assertEqual(received(self.member.installments.first().invoice.sale), Decimal("2.03"))

    def test_unknown_dispatch_is_never_posted_again(self):
        from core.payments.operations import execute

        self.buy_card()
        begin_dispatch(self.operation.pk)
        record_result(operation_id=self.operation.pk, state="unknown", source="provider")
        with patch("core.payments.operations.Gateway") as gateway:
            execute(self.operation.pk)
        gateway.return_value.charge.assert_not_called()
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_accepted_card_price_survives_later_membership_price_changes(self):
        from core.models import MembershipPricing

        self.buy_card()
        MembershipPricing.objects.create(subscription="25", unlimited="49.99", actor=self.owner)
        self.approve()
        complete(self.intent.pk)
        first = self.member.installments.first()
        self.assertEqual(first.quote["total"], "18.05")
        self.assertEqual(received(first.invoice.sale), Decimal("2.03"))
        self.assertTrue(installment_paid(first))

    def test_prepaid_remainder_has_its_own_card_fee_and_no_future_installments(self):
        self.buy_card(billing="prepaid")
        self.assertEqual(self.operation.amount, Decimal("39.09"))
        self.approve()
        complete(self.intent.pk)
        self.assertEqual(self.member.installments.count(), 1)
        self.assertTrue(installment_paid(self.member.installments.first()))
        self.assertEqual(applied(self.member.installments.first().invoice.sale), Decimal("16.02"))

    def test_staff_page_and_explicit_owner_stop_preserve_same_page_navigation(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.buy_card()
        verified_owner_login(self.client, self.owner)
        url = reverse("membership_overview", args=[self.member.pk])
        page = self.client.get(url)
        self.assertContains(page, "Original visit funds reserved")
        self.assertContains(page, "$2.03")
        self.assertNotContains(page, 'value="payment_confirm"')
        source = self.client.get(reverse("booking_detail", args=[self.visit.pk]))
        self.assertContains(source, "Open membership application")
        self.assertNotContains(source, "Apply today's visit toward a membership purchase")
        response = self.client.post(
            url,
            dict(
                action="paid_visit_stop",
                request_key=str(uuid.uuid4()),
                reviewed=stop_facts(self.intent)["fingerprint"],
                reason="Keep original paid visit",
            ),
        )
        self.assertRedirects(response, url)
        self.assertContains(self.client.get(url), "Visit application stopped")
        self.assertFalse(VisitMembershipConversion.objects.exists())

    def future_card(self):
        from core.membership_payments import change_card
        from core.models import PaymentMethod

        replacement = PaymentMethod.objects.create(
            customer=self.customer,
            provider_customer=self.method.provider_customer,
            provider_method="synthetic_future_method_" + uuid.uuid4().hex[:12],
            environment="sandbox",
            brand="Visa",
            last_four="6789",
            reusable=True,
            consent_version=self.method.consent_version,
            consent_at=self.method.consent_at,
        )
        change_card(
            actor=self.staff,
            member_id=self.member.pk,
            method_id=replacement.pk,
            revision=self.member.billing_state.revision,
            request_key=uuid.uuid4(),
            accepted=True,
        )
        return replacement

    def test_future_card_change_leaves_original_remainder_request_on_its_accepted_card(self):
        self.buy_card()
        original = self.operation.method_id
        replacement = self.future_card()
        dispatched = begin_dispatch(self.operation.pk)
        self.assertIsNotNone(dispatched)
        self.assertEqual(dispatched.method_id, original)
        self.assertEqual(dispatched.amount, Decimal("2.03"))
        record_result(
            operation_id=self.operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="441906",
        )
        complete(self.intent.pk)
        self.member.billing_state.refresh_from_db()
        self.assertEqual(self.member.billing_state.mandate.method_id, replacement.pk)
        self.assertTrue(installment_paid(self.member.installments.first()))
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_known_original_card_result_can_complete_after_a_future_card_change(self):
        self.buy_card()
        self.approve()
        original = self.operation.method_id
        replacement = self.future_card()
        complete(self.intent.pk)
        self.operation.refresh_from_db()
        self.member.billing_state.refresh_from_db()
        self.assertEqual(self.operation.method_id, original)
        self.assertEqual(self.member.billing_state.mandate.method_id, replacement.pk)
        self.assertEqual(received(self.member.installments.first().invoice.sale), Decimal("2.03"))
        self.assertEqual(applied(self.member.installments.first().invoice.sale), Decimal("16.02"))
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_continue_post_after_worker_completion_returns_saved_result_without_another_payment(
        self,
    ):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.buy_card()
        self.approve()
        complete(self.intent.pk)
        verified_owner_login(self.client, self.owner)
        url = reverse("membership_overview", args=[self.member.pk])
        response = self.client.post(url, dict(action="paid_visit_complete"))
        self.assertRedirects(response, url)
        self.assertContains(self.client.get(url), "Return to converted visit")
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)

    def test_stale_continue_post_after_owner_stop_does_not_claim_visit_was_applied(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.buy_card()
        facts = stop_facts(self.intent)
        stop(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=facts["fingerprint"],
            reason="Keep the original paid visit",
        )
        verified_owner_login(self.client, self.owner)
        url = reverse("membership_overview", args=[self.member.pk])
        response = self.client.post(url, dict(action="paid_visit_complete"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "original visit was not transferred")
        self.assertNotContains(response, "The paid visit was applied.")
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertEqual(PaymentOperation.objects.count(), 2)
