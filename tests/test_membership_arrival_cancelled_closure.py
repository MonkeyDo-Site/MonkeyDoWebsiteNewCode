"""A cancelled membership's refund remains separate from stopping its visit."""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core import membership_arrival_closure as closure
from core.communications.models import MessageDelivery
from core.membership_arrival_pending import active_for_booking, complete
from core.membership_cancellations import cancel, notices, plan_paid
from core.membership_cancellations import review as cancellation_review
from core.membership_records import MembershipArrivalClosure, MembershipRefundPlan
from core.models import PaymentOperation
from tests import test_membership_arrival_unconfirmed_returns as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CancelledMembershipClosureTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.UnconfirmedVisitReturnTests.prepare
    start = fixtures.UnconfirmedVisitReturnTests.start
    mixed = fixtures.UnconfirmedVisitReturnTests.mixed
    accept = fixtures.UnconfirmedVisitReturnTests.accept
    result = fixtures.UnconfirmedVisitReturnTests.result
    paid = fixtures.UnconfirmedVisitReturnTests.paid
    unresolved = fixtures.UnconfirmedVisitReturnTests.unresolved
    give_back = fixtures.UnconfirmedVisitReturnTests.give_back

    def cancelled(
        self, *, visit_funds=True, timing="immediate", refund="15", funded=False, send=False
    ):
        if visit_funds:
            self.unresolved("ready")
        else:
            self.start()
            self.accept()
        if funded:
            self.result()
        options = dict(
            actor=self.owner, member_id=self.intent.purchase_id, timing=timing, refund_amount=refund
        )
        current = cancellation_review(**options)
        self.cancellation = cancel(
            **options,
            reviewed=current["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Customer cancelled the membership before this visit",
            early_override=True,
            send_confirmation=send,
        )
        closure.begin_cancelled_review(actor=self.owner, intent_id=self.intent.pk)
        self.intent.refresh_from_db()

    def returned(self, **changes):
        self.cancelled(**changes)
        for source in self.intent.visit_receipts.all():
            self.give_back(source, str(source.amount))
        self.intent.refresh_from_db()

    def stop(self, **changes):
        _, digest = closure.review(actor=self.owner, intent=self.intent)
        return closure.stop(
            **(
                dict(
                    actor=self.owner,
                    intent_id=self.intent.pk,
                    request_key=uuid.uuid4(),
                    reviewed_hash=digest,
                    reason="Keep booking; handle membership refund on its own record",
                    confirmed=True,
                )
                | changes
            )
        )

    def test_owner_closes_only_arrival_and_membership_refund_stays_due(self):
        self.returned()
        before = PaymentOperation.objects.count()
        with self.runtime_role():
            record = self.stop()
        self.assertEqual(record.cancellation_id, self.cancellation.pk)
        self.assertEqual(record.facts["cancellation"]["refund_due"], "15.00")
        self.assertIsNone(active_for_booking(self.play.pk))
        self.assertEqual(complete(self.intent.pk).status, "stopped")
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertEqual(
            sum(
                (p.amount - plan_paid(p) for p in MembershipRefundPlan.objects.all()), Decimal("0")
            ),
            Decimal("15"),
        )
        self.assertTrue(notices()["refunds"])
        self.play.refresh_from_db()
        self.assertEqual((self.play.attendance, self.play.children, self.play.adults), ("", 3, 1))
        self.assertFalse(
            MessageDelivery.objects.filter(
                kind__in=["membership_confirmation", "membership_visit_confirmation"]
            ).exists()
        )

    def test_no_visit_receipts_still_allow_explicit_cancelled_arrival_review_and_stop(self):
        self.returned(visit_funds=False)
        self.assertFalse(self.intent.visit_receipts.exists())
        record = self.stop()
        self.assertEqual(record.cancellation_id, self.cancellation.pk)
        self.assertFalse(self.play.checkouts.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_visit_funds_must_be_returned_even_when_membership_was_cancelled(self):
        self.cancelled()
        with self.assertRaisesMessage(ValidationError, "Return and record all unused visit funds"):
            self.stop()
        self.assertFalse(MembershipArrivalClosure.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_end_cycle_cancellation_keeps_its_recorded_effective_date(self):
        self.returned(timing="end_cycle")
        record = self.stop()
        self.assertEqual(
            record.facts["cancellation"]["stopped_on"], self.cancellation.stopped_on.isoformat()
        )
        self.assertEqual(record.facts["cancellation"]["timing"], "end_cycle")
        self.assertEqual(record.cancellation_id, self.cancellation.pk)

    def test_cancelled_mode_is_available_on_same_pending_page_and_history_is_accurate(self):
        self.returned()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        self.assertContains(page, "Membership cancellation recorded")
        self.assertContains(page, "Membership refund due when reviewed:")
        self.assertContains(page, "$15.00")
        self.assertNotContains(page, "Keep the original booking and membership purchase.")
        data = page.context["stop_arrival_form"].initial | dict(
            reason="Keep booking and refund separately", confirmed="on"
        )
        response = self.client.post(
            reverse("booking_arrival_stop", args=[self.play.pk, self.intent.pk]), data
        )
        self.assertRedirects(response, reverse("booking_detail", args=[self.play.pk]))
        detail = self.client.get(response.url)
        self.assertContains(detail, "Membership cancellation was already recorded")
        self.assertContains(detail, "Membership refund due when arrival stopped: $15.00")
        self.assertContains(detail, "Unused visit funds returned:")
        self.assertFalse(self.play.checkouts.exists())

    def test_membership_cancellation_after_a_kept_review_requires_new_review(self):
        from tests import test_membership_arrival_closure as prior

        prior.ArrivalClosureTests.reconciled(self)
        _, digest = closure.review(actor=self.owner, intent=self.intent)
        options = dict(
            actor=self.owner,
            member_id=self.intent.purchase_id,
            timing="immediate",
            refund_amount="0",
        )
        current = cancellation_review(**options)
        cancel(
            **options,
            reviewed=current["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Cancellation was requested after the first review",
            early_override=True,
            send_confirmation=False,
        )
        self.intent.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "booking or received funds changed"):
            self.stop(reviewed_hash=digest)
        self.assertFalse(MembershipArrivalClosure.objects.exists())

    def test_pending_card_refund_keeps_its_operation_and_dashboard_liability(self):
        from unittest.mock import patch

        from core.membership_cancellations import request_refund

        self.returned(funded=True, refund="20")
        plan = self.cancellation.refund_plans.get(original__tender="card")
        attempt = request_refund(
            actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
        )
        self.assertEqual(attempt.operation.state, "ready")
        before = PaymentOperation.objects.count()
        with patch("core.payments.operations.Gateway") as provider, self.runtime_role():
            stopped = self.stop()
            provider.assert_not_called()
        attempt.operation.refresh_from_db()
        self.assertEqual(attempt.operation.state, "ready")
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertEqual(stopped.facts["cancellation"]["refund_due"], "20.00")
        self.assertTrue(notices()["refunds"])

    def test_later_actual_membership_refund_updates_its_liability_not_stopped_history(self):
        from core.membership_cancellations import request_refund

        self.returned()
        record = self.stop()
        plan = self.cancellation.refund_plans.get(original__tender="cash")
        request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
            refund_amount="2",
        )
        self.assertEqual(
            sum(
                (p.amount - plan_paid(p) for p in MembershipRefundPlan.objects.all()), Decimal("0")
            ),
            Decimal("13"),
        )
        record.refresh_from_db()
        self.assertEqual(record.facts["cancellation"]["refund_due"], "15.00")
        self.assertEqual(complete(self.intent.pk).status, "stopped")
        self.assertTrue(notices()["refunds"])

    def test_changed_refund_requires_a_fresh_stop_review(self):
        from core.membership_cancellations import request_refund

        self.returned()
        _, digest = closure.review(actor=self.owner, intent=self.intent)
        plan = self.cancellation.refund_plans.get(original__tender="cash")
        request_refund(
            actor=self.owner,
            plan_id=plan.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
            refund_amount="2",
        )
        with self.assertRaisesMessage(ValidationError, "booking or received funds changed"):
            self.stop(reviewed_hash=digest)
        self.assertFalse(MembershipArrivalClosure.objects.exists())
        record = self.stop()
        self.assertEqual(record.facts["cancellation"]["refund_due"], "13.00")

    def test_database_rejects_missing_or_wrong_cancellation_and_forged_refund_due(self):
        import copy

        from django.db import DatabaseError, transaction

        self.returned()
        facts, _ = closure.review(actor=self.owner, intent=self.intent)
        facts["reviewed_hash"] = "f" * 64
        forged = copy.deepcopy(facts)
        forged["cancellation"]["refund_due"] = "0.00"
        for changes in (
            dict(cancellation_id=None),
            dict(cancellation_id=uuid.uuid4()),
            dict(facts=forged),
        ):
            values = dict(
                intent=self.intent,
                cancellation=self.cancellation,
                request_key=uuid.uuid4(),
                reason="Owner reviewed closure",
                fingerprint="f" * 64,
                facts=facts,
                actor=self.owner,
            )
            if "cancellation_id" in changes:
                values.pop("cancellation")
            with (
                self.assertRaisesMessage(DatabaseError, "Stopped arrival does not match"),
                transaction.atomic(),
            ):
                MembershipArrivalClosure.objects.create(**(values | changes))
        self.assertFalse(MembershipArrivalClosure.objects.exists())

    def test_stopped_cancelled_review_tabs_and_duplicate_posts_return_to_current_booking(self):
        self.returned()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        values = self.client.get(url).context["stop_arrival_form"].initial | dict(
            reason="Keep booking with separate membership refund", confirmed="on"
        )
        stop = reverse("booking_arrival_stop", args=[self.play.pk, self.intent.pk])
        self.assertEqual(self.client.post(stop, values).status_code, 302)
        self.assertEqual(self.client.post(stop, values).status_code, 302)
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        for action, id_field in (
            ("start_funds_review", "funds_review_intent"),
            ("start_cancelled_arrival_review", "cancelled_review_intent"),
        ):
            result = self.client.post(url, {action: "1", id_field: str(self.intent.pk)})
            self.assertRedirects(result, reverse("booking_detail", args=[self.play.pk]))
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_original_cancellation_email_choice_is_not_changed_by_stopping_arrival(self):
        self.returned(send=True)
        before = MessageDelivery.objects.filter(kind="membership_cancellation").count()
        self.assertEqual(before, 1)
        self.stop()
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_cancellation").count(), before
        )
        self.assertFalse(
            MessageDelivery.objects.filter(
                kind__in=["membership_confirmation", "membership_visit_confirmation"]
            ).exists()
        )

    def test_unconfirmed_outgoing_refund_does_not_block_or_become_paid_when_arrival_stops(self):
        from unittest.mock import patch

        from core.membership_cancellations import request_refund
        from core.payments.ledger import record_result

        self.returned(funded=True, refund="20")
        plan = self.cancellation.refund_plans.get(original__tender="card")
        attempt = request_refund(
            actor=self.owner, plan_id=plan.pk, request_key=uuid.uuid4(), confirmed=True
        )
        record_result(operation_id=attempt.operation_id, state="unknown", source="provider")
        before = PaymentOperation.objects.count()
        with patch("core.payments.operations.Gateway") as provider, self.runtime_role():
            record = self.stop()
            provider.assert_not_called()
        attempt.operation.refresh_from_db()
        self.assertEqual(attempt.operation.state, "unknown")
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertEqual(record.facts["cancellation"]["refund_due"], "20.00")
        self.assertEqual(record.facts["cancellation"]["refund_paid"], "0.00")
        self.assertTrue(any(p["pending"] for p in record.facts["cancellation"]["refund_plans"]))
        self.assertTrue(notices()["refunds"])
        self.assertFalse(self.play.checkouts.exists())
