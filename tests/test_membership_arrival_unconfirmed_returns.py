"""Returning known visit funds never guesses a membership card outcome."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core import membership_arrival_funds as funds
from core import membership_arrival_recovery as recovery
from core.communications.models import MessageDelivery
from core.membership_arrival_pending import complete, status_data
from core.membership_arrival_receipts import summary
from core.membership_arrival_returns import review
from core.membership_records import (
    MembershipArrivalReceiptApplication,
    MembershipArrivalReceiptReturn,
)
from core.models import AuditEvent, PaymentOperation
from core.payments.invoices import received
from core.payments.operations import begin_dispatch
from tests import test_membership_arrival_returns as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class UnconfirmedVisitReturnTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PendingReturnTests.prepare
    start = fixtures.PendingReturnTests.start
    mixed = fixtures.PendingReturnTests.mixed
    accept = fixtures.PendingReturnTests.accept
    result = fixtures.PendingReturnTests.result
    paid = fixtures.PendingReturnTests.paid
    give_back = fixtures.PendingReturnTests.give_back
    owner_finish = fixtures.PendingReturnTests.owner_finish

    def unresolved(self, state="unknown"):
        self.mixed()
        self.accept()
        if state == "sending":
            self.assertEqual(begin_dispatch(self.intent.operation_id).state, "sending")
        elif state != "ready":
            self.result(state)
        self.intent.refresh_from_db()
        self.cash = self.intent.visit_receipts.get(tender="cash")

    def pause(self):
        state = funds.pause(actor=self.owner, intent_id=self.intent.pk)
        self.intent.refresh_from_db()
        return state

    def test_unknown_membership_requires_explicit_owner_pause_before_visit_return(self):
        self.unresolved()
        with self.assertRaisesMessage(ValidationError, "Start an owner review"):
            review(actor=self.owner, receipt_id=self.cash.pk)
        with self.assertRaises(ValidationError):
            recovery.begin_review(actor=self.owner, intent_id=self.intent.pk)
        with self.runtime_role():
            self.pause()
            returned = self.give_back()
        self.intent.operation.refresh_from_db()
        self.assertEqual(self.intent.operation.state, "unknown")
        self.assertEqual(self.intent.operation.provider_reference, "441094")
        self.assertEqual(received(self.intent.operation.sale), Decimal("15"))
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))
        self.assertEqual(returned.amount, Decimal("2"))
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())
        self.assertEqual(complete(self.intent.pk).code, "owner_review_requested")
        self.intent.refresh_from_db()
        self.assertIn("payment outcome is still unconfirmed", status_data(self.intent)["message"])
        self.assertFalse(self.play.checkouts.exists())
        self.assertFalse(
            MessageDelivery.objects.filter(
                kind__in=("membership_confirmation", "membership_visit_confirmation")
            ).exists()
        )

    def test_unknown_first_outcome_remains_separate_after_all_four_visit_tenders_returned(self):
        self.unresolved()
        self.pause()
        for source in self.intent.visit_receipts.all():
            self.give_back(source, str(source.amount))
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 4)
        self.assertEqual(summary(self.intent)["total"], 0)
        self.assertEqual(summary(self.intent)["returned"], Decimal("7"))
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())
        self.assertFalse(self.intent.purchase.cancellations.exists())
        self.intent.operation.refresh_from_db()
        self.assertEqual(self.intent.operation.state, "unknown")
        self.assertFalse(status_data(self.intent)["can_continue"])
        with self.assertRaises(ValidationError):
            recovery.authorize(self.owner, self.intent, reviewing=True)

    def test_owner_pause_and_recording_do_not_cancel_a_sending_payment_or_call_provider(self):
        self.unresolved("sending")
        with patch("core.payments.operations.Gateway") as provider, self.runtime_role():
            self.pause()
            self.give_back()
            provider.assert_not_called()
        self.intent.operation.refresh_from_db()
        self.assertEqual(self.intent.operation.state, "sending")
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertFalse(self.play.checkouts.exists())

    def test_unstarted_card_must_be_reviewed_on_its_own_payment_before_visit_return(self):
        self.unresolved("ready")
        revision = self.intent.progress.revision
        with self.assertRaisesMessage(ValidationError, "It has not been sent"):
            self.pause()
        self.intent.progress.refresh_from_db()
        self.intent.operation.refresh_from_db()
        self.assertEqual(self.intent.progress.revision, revision)
        self.assertEqual(self.intent.operation.state, "ready")
        self.assertFalse(MembershipArrivalReceiptReturn.objects.exists())
        self.assertFalse(
            AuditEvent.objects.filter(action="membership.arrival_funds_review_started").exists()
        )

    def test_later_known_funding_does_not_resume_visit_without_fresh_owner_confirmation(self):
        self.unresolved()
        self.pause()
        self.give_back()
        self.result()
        self.assertEqual(complete(self.intent.pk).code, "owner_review_requested")
        self.assertFalse(self.play.checkouts.exists())
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())
        with self.runtime_role():
            arrival = self.owner_finish()
        self.assertEqual(arrival.sale.operations.get(tender="card").amount, Decimal("11.32"))
        self.assertEqual(MembershipArrivalReceiptApplication.objects.count(), 4)
        self.assertEqual(self.cash.application.operation.amount, Decimal("1"))
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 8)

    def test_pause_is_idempotent_and_ordinary_staff_cannot_pause_or_return(self):
        self.unresolved()
        with self.assertRaises(PermissionDenied):
            funds.pause(actor=self.staff, intent_id=self.intent.pk)
        first = self.pause()
        second = self.pause()
        self.assertEqual(first.revision, second.revision)
        self.assertEqual(
            AuditEvent.objects.filter(action="membership.arrival_funds_review_started").count(), 1
        )
        with self.assertRaises(PermissionDenied):
            review(actor=self.staff, receipt_id=self.cash.pk)

    def test_owner_uses_the_same_pending_page_without_arrival_or_stop_authority(self):
        self.unresolved()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        self.assertContains(page, "Review unused visit funds")
        self.assertNotContains(page, "Record completed return")
        self.assertNotContains(page, "Stop this arrival; keep booking")
        self.assertEqual(
            self.client.post(
                url, dict(start_funds_review="1", funds_review_intent=str(self.intent.pk))
            ).status_code,
            302,
        )
        page = self.client.get(url)
        self.assertContains(page, "Record completed return")
        self.assertContains(page, "Reconcile the existing membership payment")
        self.assertNotContains(page, "Stop this arrival; keep booking")
        values = page.context["return_form"].initial | dict(
            receipt=str(self.cash.pk),
            amount="2",
            completed_on=str(self.cash.received_on),
            verified_returned="on",
            record_visit_return="1",
        )
        self.assertEqual(self.client.post(url, values).status_code, 302)
        page = self.client.get(url)
        self.assertContains(page, "$5.00")
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.assertFalse(self.play.checkouts.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_stale_funds_pause_cannot_target_another_pending_intent(self):
        self.unresolved()
        verified_owner_login(self.client, self.owner)
        response = self.client.post(
            reverse("booking_arrival", args=[self.play.pk]),
            dict(start_funds_review="1", funds_review_intent=str(uuid.uuid4())),
        )
        self.assertEqual(response.status_code, 302)
        self.intent.progress.refresh_from_db()
        self.assertNotEqual(self.intent.progress.code, "owner_review_requested")
        self.assertFalse(
            AuditEvent.objects.filter(action="membership.arrival_funds_review_started").exists()
        )

    def test_membership_cancellation_and_its_refund_due_are_not_visit_fund_returns(self):
        from core.membership_cancellations import cancel, plan_paid
        from core.membership_cancellations import review as cancellation_review
        from core.membership_records import MembershipRefundPlan

        self.unresolved("ready")
        values = dict(
            actor=self.owner,
            member_id=self.intent.purchase_id,
            timing="immediate",
            refund_amount="15",
        )
        current = cancellation_review(**values)
        cancel(
            **values,
            reviewed=current["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Owner cancelled this purchase before its first card was sent",
            early_override=True,
            send_confirmation=False,
        )
        self.intent.refresh_from_db()
        self.intent.operation.refresh_from_db()
        self.assertEqual(self.intent.operation.state, "cancelled")
        self.pause()
        self.give_back()
        plans = list(MembershipRefundPlan.objects.all())
        self.assertEqual(sum((p.amount - plan_paid(p) for p in plans), Decimal("0")), Decimal("15"))
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())
        self.assertIn("membership cancellation", status_data(self.intent)["message"])
        self.assertFalse(self.play.checkouts.exists())

    def test_original_booking_bank_funds_are_not_returned_with_new_visit_receipts(self):
        from core.payments.models import ZelleRefund
        from core.payments.zelle import facts, record_receipt

        self.mixed()
        record_receipt(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            value="25",
            sender_name="Fictional prior transfer",
            verified=True,
        )
        self.input.update(member_recorded_zelle="20", member_check_amount="0")
        # Prior booking Zelle is already a verified receipt; only genuinely new
        # cash/check/gift receipts belong to this conditional visit plan.
        self.input["split"].pop("zelle")
        self.input["split"]["cash"] = "4"
        self.accept()
        self.result("unknown")
        self.cash = self.intent.visit_receipts.get(tender="cash")
        self.pause()
        for source in self.intent.visit_receipts.all():
            self.give_back(source, str(source.amount))
        self.assertEqual(facts(self.play)["available"], Decimal("5"))
        self.assertEqual(len(facts(self.play)["receipts"]), 1)
        self.assertFalse(ZelleRefund.objects.exists())
        self.assertEqual(summary(self.intent)["returned"], Decimal("7"))
        self.assertFalse(self.play.checkouts.exists())

    def test_repeated_unknown_outcome_return_is_one_fact_and_terminal_arrivals_refuse_pause(self):
        self.unresolved()
        self.pause()
        key = uuid.uuid4()
        digest = review(actor=self.owner, receipt_id=self.cash.pk)["fingerprint"]
        first = self.give_back(key=key)
        replay = self.give_back(key=key, reviewed_hash=digest)
        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.play.attendance = "cancelled"
        self.play.save(update_fields=["attendance"])
        with self.assertRaisesMessage(ValidationError, "arrival has already ended"):
            self.pause()
