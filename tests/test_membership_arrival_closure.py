import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from core import membership_arrival_closure as closure
from core.communications.models import MessageDelivery
from core.membership_arrival_pending import active_for_booking, complete, status_data
from core.membership_records import MembershipArrivalClosure
from core.models import Booking, PaymentOperation
from tests import test_membership_arrival_returns as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class ArrivalClosureTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PendingReturnTests.prepare
    start = fixtures.PendingReturnTests.start
    mixed = fixtures.PendingReturnTests.mixed
    accept = fixtures.PendingReturnTests.accept
    result = fixtures.PendingReturnTests.result
    paid = fixtures.PendingReturnTests.paid
    give_back = fixtures.PendingReturnTests.give_back

    def reconciled(self):
        self.paid()
        for source in self.intent.visit_receipts.all():
            self.give_back(source, str(source.amount))
        self.intent.refresh_from_db()

    def stop(self, key=None, **changes):
        facts, digest = closure.review(actor=self.owner, intent=self.intent)
        return closure.stop(
            **(
                dict(
                    actor=self.owner,
                    intent_id=self.intent.pk,
                    request_key=key or uuid.uuid4(),
                    reviewed_hash=digest,
                    reason="Customer will decide on a later arrival",
                    confirmed=True,
                )
                | changes
            )
        )

    def test_owner_keeps_purchase_and_booking_and_never_continues_the_old_arrival(self):
        self.reconciled()
        old_booking = Booking.objects.get(pk=self.play.pk)
        before = PaymentOperation.objects.count()
        with self.runtime_role():
            record = self.stop()
        self.assertEqual(record.intent_id, self.intent.pk)
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertIsNone(active_for_booking(self.play.pk))
        self.assertEqual(complete(self.intent.pk).status, "stopped")
        self.intent.refresh_from_db()
        self.assertEqual(status_data(self.intent)["state"], "stopped")
        self.play.refresh_from_db()
        self.assertEqual(
            (self.play.attendance, self.play.edit_version, self.play.children),
            ("", old_booking.edit_version, old_booking.children),
        )
        self.assertFalse(self.play.membership_benefits.exists())
        self.assertEqual(
            MessageDelivery.objects.filter(
                kind="membership_confirmation", membership=self.intent.purchase
            ).count(),
            1,
        )
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )
        self.assertEqual(Decimal(record.facts["membership_received"]), Decimal("36.61"))

    def test_all_original_visit_money_must_be_actually_returned_first(self):
        self.paid()
        with self.assertRaisesMessage(ValidationError, "Return and record all unused visit funds"):
            self.stop()
        self.assertFalse(MembershipArrivalClosure.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_same_request_replay_after_booking_changes_reuses_one_closure(self):
        self.reconciled()
        _, digest = closure.review(actor=self.owner, intent=self.intent)
        key = uuid.uuid4()
        first = self.stop(key)
        Booking.objects.filter(pk=self.play.pk).update(edit_version=self.play.edit_version + 1)
        replay = closure.stop(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=key,
            reviewed_hash=digest,
            reason=first.reason,
            confirmed=True,
        )
        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.filter(kind="membership_confirmation").count(), 1)

    def test_only_explicit_owner_review_can_stop_and_stale_bookings_are_refused(self):
        self.reconciled()
        with self.assertRaises(PermissionDenied):
            closure.review(actor=self.staff, intent=self.intent)
        _, digest = closure.review(actor=self.owner, intent=self.intent)
        with self.assertRaises(ValidationError):
            self.stop(confirmed=False)
        self.play.zelle_sender = "A changed booking detail"
        self.play.edit_version += 1
        self.play.save(update_fields=["zelle_sender", "edit_version"])
        self.intent = (
            type(self.intent).objects.select_related("purchase", "progress").get(pk=self.intent.pk)
        )
        with self.assertRaisesMessage(ValidationError, "booking or received funds changed"):
            self.stop(reviewed_hash=digest)
        self.assertFalse(MembershipArrivalClosure.objects.exists())

    def test_extra_attendee_hold_is_released_without_changing_original_places_or_future_terms(self):
        from core.availability import occupancy
        from core.membership_arrival_recovery import begin_review
        from core.models import BookingCapacityHold

        self.start()
        self.input["children"] = self.play.children + 2
        self.input["waiver_mismatch_accepted"] = True
        self.accept()
        self.result()
        begin_review(actor=self.owner, intent_id=self.intent.pk)
        self.intent.refresh_from_db()
        member = self.intent.purchase
        original = (member.membership.starts_on, member.membership.ends_on, member.terms_text)
        future = list(member.installments.values_list("number", "due_on", "quote"))
        self.assertEqual(BookingCapacityHold.objects.get(pk=self.intent.hold_key).children, 2)
        self.assertEqual(occupancy(self.play.session)[0], self.play.children + 2)
        self.stop()
        self.assertFalse(BookingCapacityHold.objects.filter(pk=self.intent.hold_key).exists())
        self.assertEqual(occupancy(self.play.session)[0], self.play.children)
        member.refresh_from_db()
        self.assertEqual(
            (member.membership.starts_on, member.membership.ends_on, member.terms_text), original
        )
        self.assertEqual(list(member.installments.values_list("number", "due_on", "quote")), future)
        self.assertFalse(self.play.checkouts.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_original_bank_remainder_is_kept_for_booking_after_membership_funding(self):
        from core.membership_arrival_recovery import begin_review
        from core.payments.zelle import facts, record_receipt

        self.start()
        record_receipt(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            value="25",
            sender_name="Fictional original Zelle",
            verified=True,
        )
        self.input.update(member_recorded_zelle="20", member_check_amount="0")
        self.accept()
        self.result()
        begin_review(actor=self.owner, intent_id=self.intent.pk)
        self.intent.refresh_from_db()
        self.stop()
        remaining = facts(self.play)
        self.assertEqual(remaining["available"], Decimal("5"))
        self.assertEqual(len(remaining["receipts"]), 1)
        self.assertFalse(self.play.checkouts.exists())
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())
        self.act(self.play, dict(charge_fee=False, send_email=False), kind="cancellation")
        self.play.refresh_from_db()
        self.assertEqual(facts(self.play)["refund_due"], Decimal("5"))
        self.assertEqual(facts(self.play)["refunded"], Decimal("0"))
        self.assertFalse(self.intent.purchase.cancellations.exists())

    def test_ended_review_and_old_private_draft_cannot_resume_as_new_arrival(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.reconciled()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url + "?review_pending=1")
        self.assertContains(page, "Stop this arrival; keep booking")
        draft = page.context["arrival_draft"]
        values = page.context["stop_arrival_form"].initial | dict(
            reason="Keep upcoming booking", confirmed="on"
        )
        stop_url = reverse("booking_arrival_stop", args=[self.play.pk, self.intent.pk])
        before = PaymentOperation.objects.count()
        self.assertRedirects(
            self.client.post(stop_url, values), reverse("booking_detail", args=[self.play.pk])
        )
        self.assertRedirects(
            self.client.get(url + "?review_pending=1"),
            reverse("booking_detail", args=[self.play.pk]),
        )
        old = self.client.post(
            url, dict(pending_review=str(self.intent.pk)), HTTP_ACCEPT="application/json"
        )
        self.assertEqual(old.status_code, 409)
        self.assertTrue(old.json()["arrival_ended"])
        self.assertNotIn(str(draft), self.client.session.get("arrival_review_drafts", {}))
        self.assertEqual(self.client.post(stop_url, values).status_code, 302)
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), before)
        detail = self.client.get(reverse("booking_detail", args=[self.play.pk]))
        self.assertContains(detail, "Stopped arrivals")
        self.assertContains(detail, "First membership payment received when stopped: $36.61")
        self.assertContains(detail, "Unused visit funds returned:")
        self.assertContains(detail, "Cash $3.00")
        self.assertContains(detail, "Gift card $1.00")
        self.assertNotContains(detail, "Visit total received")
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_cross_session_draft_and_old_review_never_reopen_a_stopped_intent(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.reconciled()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url + "?review_pending=1")
        token = page.context["arrival_draft"]
        # Stop through the service, preserving the other browser's private old draft.
        self.stop()
        self.assertRedirects(
            self.client.get(url + "?draft=" + str(token)),
            reverse("booking_detail", args=[self.play.pk]),
        )
        self.assertNotIn(str(token), self.client.session.get("arrival_review_drafts", {}))
        from core.membership_arrival_recovery import begin_review

        self.assertEqual(begin_review(actor=self.owner, intent_id=self.intent.pk).status, "stopped")
        self.assertIsNone(active_for_booking(self.play.pk))

    def test_missing_confirmation_and_wrong_booking_keep_stop_reason_without_any_fact(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.reconciled()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url + "?review_pending=1")
        values = page.context["stop_arrival_form"].initial | dict(
            reason="Retain reason, not confirmation"
        )
        response = self.client.post(
            reverse("booking_arrival_stop", args=[self.play.pk, self.intent.pk]), values
        )
        self.assertEqual(response.status_code, 302)
        fresh = self.client.get(response.url)
        self.assertEqual(fresh.context["stop_arrival_form"]["reason"].value(), values["reason"])
        self.assertFalse(fresh.context["stop_arrival_form"]["confirmed"].value())
        self.assertNotEqual(
            fresh.context["stop_arrival_form"]["request_key"].value(), values["request_key"]
        )
        wrong = self.client.post(
            reverse("booking_arrival_stop", args=[self.play.pk + 1000, self.intent.pk]),
            values | dict(confirmed="on"),
        )
        self.assertEqual(wrong.status_code, 404)
        self.assertFalse(MembershipArrivalClosure.objects.exists())

    def test_unknown_or_unpaid_membership_cannot_stop_and_no_confirmation_is_queued(self):
        self.start()
        self.accept()
        for state in ("ready", "unknown"):
            if state == "unknown":
                self.result(state)
            self.intent.refresh_from_db()
            with self.assertRaisesMessage(
                ValidationError, "Confirm the existing membership payment"
            ):
                closure.review(actor=self.owner, intent=self.intent)
        self.assertFalse(MembershipArrivalClosure.objects.exists())
        self.assertFalse(MessageDelivery.objects.filter(kind="membership_confirmation").exists())

    def test_database_scope_rejects_wrong_owner_version_funding_and_return_facts(self):
        from django.db import DatabaseError, transaction

        self.reconciled()
        facts, _ = closure.review(actor=self.owner, intent=self.intent)
        facts["reviewed_hash"] = "f" * 64
        for change in (
            dict(actor=self.staff),
            dict(reason=" "),
            dict(fingerprint="short"),
            dict(facts=facts | dict(booking_version=-1)),
            dict(facts=facts | dict(membership_received="10000.00")),
        ):
            options = (
                dict(
                    intent=self.intent,
                    request_key=uuid.uuid4(),
                    reason="Reviewed stop",
                    fingerprint="f" * 64,
                    facts=facts,
                    actor=self.owner,
                )
                | change
            )
            with (
                self.assertRaisesMessage(DatabaseError, "Stopped arrival does not match"),
                transaction.atomic(),
            ):
                MembershipArrivalClosure.objects.create(**options)
        self.assertFalse(MembershipArrivalClosure.objects.exists())

    def test_stopped_evidence_and_state_are_immutable_and_late_raw_resolution_is_blocked(self):
        from django.db import DatabaseError, connection, transaction

        from core.membership_records import MembershipArrivalResolution

        self.reconciled()
        self.stop()
        for sql, params, phrase in (
            (
                "UPDATE core_membershiparrivalclosure SET reason=%s WHERE intent_id=%s",
                ["changed", self.intent.pk],
                "immutable",
            ),
            (
                "DELETE FROM core_membershiparrivalclosure WHERE intent_id=%s",
                [self.intent.pk],
                "immutable",
            ),
            (
                "UPDATE core_membershiparrivalstate SET status='review',revision=revision+1 WHERE intent_id=%s",
                [self.intent.pk],
                "Invalid pending arrival transition",
            ),
        ):
            with (
                self.assertRaisesMessage(DatabaseError, phrase),
                transaction.atomic(),
                connection.cursor() as cursor,
            ):
                cursor.execute(sql, params)
        with (
            self.assertRaisesMessage(DatabaseError, "A stopped arrival cannot be completed"),
            transaction.atomic(),
        ):
            MembershipArrivalResolution.objects.create(
                intent=self.intent,
                request_key=uuid.uuid4(),
                fingerprint="f" * 64,
                reason="Late stale tab",
                actor=self.owner,
                checkout_id=uuid.uuid4(),
            )

    def test_raw_closure_requires_stopped_state_before_commit(self):
        from django.db import DatabaseError, connection, transaction

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL deferred scope")
        self.reconciled()
        facts, _ = closure.review(actor=self.owner, intent=self.intent)
        facts["reviewed_hash"] = "f" * 64
        with (
            self.assertRaisesMessage(DatabaseError, "terminal state and released extra capacity"),
            transaction.atomic(),
        ):
            MembershipArrivalClosure.objects.create(
                intent=self.intent,
                request_key=uuid.uuid4(),
                fingerprint="f" * 64,
                reason="Raw incomplete closure",
                actor=self.owner,
                facts=facts,
            )
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS core_pending_stop_link IMMEDIATE")
        self.assertFalse(MembershipArrivalClosure.objects.exists())

    def test_queued_original_continuation_is_a_noop_without_card_dispatch(self):
        from datetime import timedelta
        from unittest.mock import patch

        from django.utils import timezone

        from core.models import DurableJob
        from core.payments.jobs import run_one

        self.reconciled()
        old_job = DurableJob.objects.get(kind="membership_arrival")
        self.stop()
        DurableJob.objects.exclude(pk=old_job.pk).update(
            available_at=timezone.now() + timedelta(days=1)
        )
        before = PaymentOperation.objects.count()
        with patch("core.payments.operations.Gateway") as provider, self.runtime_role():
            self.assertTrue(run_one())
            provider.assert_not_called()
        old_job.refresh_from_db()
        self.assertEqual(old_job.state, "done")
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertFalse(self.play.checkouts.exists())

    def test_normal_booking_cancellation_stays_explicit_after_stop(self):
        from core.payments.checkout import confirm, preview

        self.reconciled()
        self.stop()
        self.play.refresh_from_db()
        data = dict(charge_fee=False, send_email=False)
        current = preview(actor=self.owner, booking_id=self.play.pk, kind="cancellation", data=data)
        result = confirm(
            actor=self.owner,
            booking_id=self.play.pk,
            kind="cancellation",
            data=data,
            request_key=uuid.uuid4(),
            reviewed_hash=current[-1],
            confirmed=True,
        )
        self.play.refresh_from_db()
        self.assertEqual(self.play.attendance, "cancelled")
        self.assertEqual(result.kind, "cancellation")
        self.assertIsNone(result.sale)
        self.assertFalse(self.intent.purchase.cancellations.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_stop_needs_csrf_and_owner_and_uses_a_separate_form(self):
        from django.test import Client
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.reconciled()
        client = Client(enforce_csrf_checks=True)
        verified_owner_login(client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = client.get(url + "?review_pending=1")
        values = page.context["stop_arrival_form"].initial | dict(
            reason="Keep original booking", confirmed="on"
        )
        endpoint = reverse("booking_arrival_stop", args=[self.play.pk, self.intent.pk])
        self.assertEqual(client.post(endpoint, values).status_code, 403)
        self.assertEqual(client.get(endpoint).status_code, 405)
        self.assertEqual(
            client.post(
                endpoint, values, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
            ).status_code,
            302,
        )
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(endpoint, values).status_code, 403)

    def test_paused_membership_sales_and_recovery_hold_refuse_stop_without_server_error(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.reconciled()
        verified_owner_login(self.client, self.owner)
        values = self.client.get(
            reverse("booking_arrival", args=[self.play.pk]) + "?review_pending=1"
        ).context["stop_arrival_form"].initial | dict(reason="Keep booking", confirmed="on")
        endpoint = reverse("booking_arrival_stop", args=[self.play.pk, self.intent.pk])
        for settings in (dict(MEMBERSHIP_SALES_ENABLED=False), dict(RECOVERY_HOLD=True)):
            with override_settings(**settings):
                self.assertEqual(self.client.post(endpoint, values).status_code, 302)
        self.assertFalse(MembershipArrivalClosure.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)
