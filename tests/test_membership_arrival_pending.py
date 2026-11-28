"""The original accepted arrival follows confirmed membership funding only."""

import copy
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.availability import occupancy
from core.communications.models import MessageDelivery
from core.membership_arrival import confirm, review
from core.membership_arrival_pending import complete
from core.membership_records import MembershipArrivalCheckout, MembershipArrivalIntent
from core.membership_sales import membership_status
from core.models import BookingCapacityHold, DurableJob, PaymentOperation
from core.payments.checkout import preview as arrival_preview
from core.payments.ledger import record_result
from core.payments.operations import execute
from tests import test_membership_arrival as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PendingMembershipArrivalTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.CombinedMembershipArrivalTests.prepare
    web_data = fixtures.CombinedMembershipArrivalTests.web_data

    def begin(self, **changes):
        self.play = self.prepare(method="card", **changes)
        self.options["method_id"] = self.play.card_agreement.method_id
        self.accepted = review(**self.options)
        with self.runtime_role():
            self.intent = confirm(
                **self.options,
                request_key=self.key,
                reviewed_hash=self.accepted["fingerprint"],
                confirmed=True,
                accepted=True,
                verified_received=False,
            )
        return self.intent

    def pay_first(self):
        return record_result(
            operation_id=self.intent.operation_id,
            state="succeeded",
            source="provider",
            provider_reference="991",
        )

    def test_acceptance_commits_only_first_charge_and_holds_extra_attendees(self):
        intent = self.begin()
        self.play.refresh_from_db()
        self.assertIsInstance(intent, MembershipArrivalIntent)
        self.assertEqual(self.play.attendance, "")
        self.assertEqual(membership_status(intent.purchase), "pending")
        self.assertEqual(intent.operation.amount, Decimal("37.06"))
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertFalse(self.play.membership_benefits.exists())
        hold = BookingCapacityHold.objects.get(pk=intent.hold_key)
        self.assertEqual(hold.adults, 1)
        self.assertEqual(hold.children, 0)
        self.assertEqual(hold.expires_at, intent.accepted_at + timedelta(minutes=30))
        self.assertEqual(occupancy(self.play.session)[:2], (3, 2))
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )

    def test_confirmed_first_payment_queues_continuation_not_visit_charge_in_callback(self):
        intent = self.begin()
        self.pay_first()
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(DurableJob.objects.filter(kind="membership_arrival").count(), 1)
        self.play.refresh_from_db()
        self.assertEqual(self.play.attendance, "")
        from core.payments.jobs import run_one

        job = DurableJob.objects.get(kind="membership_arrival")
        DurableJob.objects.exclude(pk=job.pk).update(
            available_at=timezone.now() + timedelta(days=1)
        )
        with self.runtime_role():
            self.assertTrue(run_one())
        job.refresh_from_db()
        intent.progress.refresh_from_db()
        self.assertEqual(job.state, "done")
        self.assertEqual(intent.progress.status, "completed")
        self.play.refresh_from_db()
        self.assertEqual(self.play.attendance, "arrived")
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        second = record.checkout.sale.operations.get()
        self.assertEqual(second.amount, Decimal("16.47"))
        self.assertEqual(second.state, "ready")
        self.assertFalse(BookingCapacityHold.objects.filter(pk=intent.hold_key).exists())
        self.assertEqual(self.play.membership_benefits.filter(current__status="used").count(), 2)
        self.assertEqual(complete(intent.pk).status, "completed")
        self.assertEqual(PaymentOperation.objects.count(), 2)
        record_result(
            operation_id=second.pk, state="succeeded", source="provider", provider_reference="992"
        )
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )

    def test_blocked_unsent_first_payment_is_shown_as_needing_review(self):
        intent = self.begin()
        DurableJob.objects.filter(
            kind="payment_dispatch", reference=str(intent.operation_id)
        ).update(state="blocked")
        from core.membership_arrival_pending import status_data

        result = status_data(intent)
        self.assertEqual(result["state"], "review")
        self.assertIn("has not been sent", result["message"])
        self.assertFalse(result["can_continue"])
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_prepaid_card_membership_with_fully_included_visit_needs_no_visit_charge(self):
        intent = self.begin(children=1, places=1, billing="prepaid")
        self.assertEqual(intent.operation.amount, Decimal("55.59"))
        self.pay_first()
        self.assertEqual(complete(intent.pk).status, "completed")
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        self.assertIsNone(record.checkout.sale_id)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(self.play.membership_benefits.filter(current__status="used").count(), 1)
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("Membership—full selected term: $53.97", message.text_body)
        self.assertIn("Credit-card processing fee: $1.62", message.text_body)
        self.assertIn("New payment received: $55.59", message.text_body)

    def test_unknown_first_result_does_not_schedule_arrival_or_repeat_card_post(self):
        intent = self.begin()
        record_result(operation_id=intent.operation_id, state="unknown", source="provider")
        self.assertFalse(DurableJob.objects.filter(kind="membership_arrival").exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertEqual(execute(intent.operation_id).state, "unknown")
            gateway.return_value.charge.assert_not_called()
        with self.assertRaisesMessage(ValidationError, "already in progress"):
            arrival_preview(
                actor=self.staff, booking_id=self.play.pk, kind="arrival", data=self.input
            )

    def test_extra_reservation_expires_without_extending_from_poll_or_duplicate(self):
        intent = self.begin()
        before = intent.expires_at
        again = confirm(
            **self.options,
            request_key=self.key,
            reviewed_hash=self.accepted["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=False,
        )
        self.assertEqual(again.pk, intent.pk)
        self.assertEqual(again.expires_at, before)
        self.pay_first()
        with patch("django.utils.timezone.now", return_value=before + timedelta(seconds=1)):
            self.assertEqual(occupancy(self.play.session)[:2], (3, 1))
            result = complete(intent.pk)
        self.assertEqual(result.status, "review")
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.play.refresh_from_db()
        self.assertFalse(self.play.attendance)

    def test_stale_booking_prevents_first_dispatch_and_flags_review(self):
        intent = self.begin()
        from core.models import Booking

        Booking.objects.filter(pk=self.play.pk).update(edit_version=self.play.edit_version + 1)
        with patch("core.payments.operations.Gateway") as gateway:
            execute(intent.operation_id)
            gateway.return_value.charge.assert_not_called()
        intent.operation.refresh_from_db()
        self.assertEqual(intent.operation.state, "cancelled")
        intent.progress.refresh_from_db()
        self.assertEqual(intent.progress.status, "review")

    def test_stale_session_after_paid_membership_never_requests_visit_charge(self):
        intent = self.begin()
        self.pay_first()
        from core.models import Session

        Session.objects.filter(pk=self.play.session_id).update(
            ends_at=self.play.session.ends_at + timedelta(minutes=5)
        )
        self.assertEqual(complete(intent.pk).status, "review")
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(membership_status(intent.purchase), "active")

    def test_deactivated_staff_cannot_complete_new_financial_action(self):
        intent = self.begin()
        self.pay_first()
        type(self.staff).objects.filter(pk=self.staff.pk).update(is_active=False)
        self.assertEqual(complete(intent.pk).status, "review")
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_accepted_pending_evidence_cannot_be_changed_in_database(self):
        intent = self.begin()
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_membershiparrivalintent SET fingerprint='invalid' WHERE id=%s",
                [intent.pk],
            )

    def test_database_rejects_intent_with_a_different_accepted_first_charge(self):
        original = MembershipArrivalIntent.objects.create

        def changed_amount(**values):
            values["facts"] = copy.deepcopy(values["facts"])
            values["facts"]["review"]["membership_due"] = "1.00"
            return original(**values)

        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            patch(
                "core.membership_arrival_pending.MembershipArrivalIntent.objects.create",
                side_effect=changed_amount,
            ),
        ):
            self.begin()
        self.assertEqual(MembershipArrivalIntent.objects.count(), 0)
        self.assertEqual(PaymentOperation.objects.count(), 0)

    def test_successful_dispatch_requests_membership_amount_only(self):
        intent = self.begin()
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.return_value = {
                "status_code": "A",
                "reference_number": "991",
            }
            gateway.return_value.transaction.return_value = {
                "id": 991,
                "amount_details": {"amount": "37.06"},
                "status_details": {"status": "captured"},
                "transaction_details": {"type": "charge"},
                "custom_fields": {
                    "custom1": str(intent.operation_id),
                    "custom2": "monkeydo:sandbox",
                },
            }
            result = execute(intent.operation_id)
            self.assertEqual(result.state, "succeeded")
            self.assertEqual(gateway.return_value.charge.call_count, 1)
            self.assertEqual(gateway.return_value.charge.call_args.args[0].amount, Decimal("37.06"))
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertFalse(self.play.membership_benefits.exists())

    def test_paid_confirmation_combines_both_card_fees_without_hiding_one_in_principal(self):
        intent = self.begin()
        self.pay_first()
        complete(intent.pk)
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        second = record.checkout.sale.operations.get()
        record_result(
            operation_id=second.pk, state="succeeded", source="provider", provider_reference="992"
        )
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("Membership—first month: $35.98", message.text_body)
        self.assertIn("Credit-card processing fee: $1.53", message.text_body)
        self.assertIn("New payment received: $53.53", message.text_body)

    def test_explicit_cash_repairs_first_decline_without_rebuying_membership(self):
        from core.membership_payments import collect_installment, payment_review

        intent = self.begin()
        record_result(operation_id=intent.operation_id, state="declined", source="provider")
        first = intent.purchase.installments.first()
        values = dict(
            actor=self.staff, member_id=intent.purchase_id, installment_id=first.pk, tender="cash"
        )
        accepted = payment_review(**values)
        collect_installment(
            **values,
            request_key=uuid.uuid4(),
            reviewed=accepted["fingerprint"],
            confirmed=True,
            verified_received=True,
        )
        self.assertEqual(complete(intent.pk).status, "completed")
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        second = record.checkout.sale.operations.get()
        record_result(
            operation_id=second.pk, state="succeeded", source="provider", provider_reference="992"
        )
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("Membership—first month: $35.98", message.text_body)
        self.assertIn("Credit-card processing fee: $0.45", message.text_body)
        self.assertIn("New payment received: $52.45", message.text_body)

    def test_one_page_acceptance_and_read_only_pending_status_preserve_the_request(self):
        self.play = self.prepare(method="card")
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        initial = self.client.get(url)
        values = self.web_data(self.play) | {"arrival_draft": initial.context["arrival_draft"]}
        accepted = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(accepted.status_code, 200, accepted.content)
        data = values | {"reviewed_hash": accepted.json()["hash"], "confirm_review": "1"}
        response = self.client.post(url, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["accepted"])
        intent = MembershipArrivalIntent.objects.get()
        self.assertEqual(
            self.client.post(url, data, HTTP_ACCEPT="application/json").json()["status_url"],
            response.json()["status_url"],
        )
        before = PaymentOperation.objects.count(), intent.expires_at
        page = self.client.get(url)
        self.assertContains(page, "Membership and arrival")
        self.assertContains(page, "37.06")
        status = self.client.get(response.json()["status_url"]).json()
        self.assertEqual(status["state"], "processing")
        self.assertIn("visit card payment has not been requested", status["message"])
        self.assertEqual(status["membership_received"], "0.00")
        intent.refresh_from_db()
        self.assertEqual(before, (PaymentOperation.objects.count(), intent.expires_at))

    def test_sales_pause_keeps_existing_pending_arrival_guard(self):
        intent = self.begin()
        from core.membership_arrival_pending import status_data

        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            with self.assertRaisesMessage(ValidationError, "already in progress"):
                arrival_preview(
                    actor=self.staff, booking_id=self.play.pk, kind="arrival", data=self.input
                )
            self.assertEqual(status_data(intent)["state"], "review")
            with patch("core.payments.operations.Gateway") as gateway:
                with self.assertRaises(ValidationError):
                    execute(intent.operation_id)
                gateway.return_value.charge.assert_not_called()
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.play.refresh_from_db()
        self.assertEqual(self.play.attendance, "")

    def test_missing_earlier_schema_does_not_query_pending_table(self):
        from core.membership_arrival_pending import active_for_booking

        with (
            override_settings(MEMBERSHIP_SALES_ENABLED=False),
            patch("core.membership_schema.available", return_value=False),
            patch.object(
                MembershipArrivalIntent.objects,
                "filter",
                side_effect=AssertionError("Pending table must not be read"),
            ),
        ):
            self.assertIsNone(active_for_booking(123))

    def test_explicit_recheck_of_unchanged_approved_arrival_reuses_original_purchase(self):
        intent = self.begin()
        self.pay_first()
        DurableJob.objects.filter(kind="membership_arrival").update(
            state="blocked", code="review_required"
        )
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        self.assertTrue(page.context["may_continue"])
        self.client.post(url, {"continue_approved": "1"})
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(MembershipArrivalIntent.objects.count(), 1)
        self.assertEqual(MembershipArrivalCheckout.objects.count(), 1)
        self.assertEqual(complete(intent.pk).status, "completed")

    def test_additional_signed_coverage_does_not_discard_still_valid_accepted_waivers(self):
        intent = self.begin()
        self.pay_first()
        from core.membership_sales import today
        from core.waivers.paper import record

        record(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            signer_name="Another Parent",
            relationship="Parent",
            minors=["Additional Child"],
            signed_on=today(),
            paper_signed=True,
        )
        self.assertEqual(complete(intent.pk).status, "completed")
        saved = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        self.assertGreater(
            saved.checkout.details["waiver_review"]["recorded_minors"],
            intent.facts["review"]["arrival"]["waiver_review"]["recorded_minors"],
        )

    def test_removed_accepted_waiver_prevents_dependent_visit_charge(self):
        intent = self.begin()
        self.pay_first()
        with patch("core.membership_arrival_pending.waivers", return_value=[]):
            self.assertEqual(complete(intent.pk).status, "review")
        self.assertEqual(PaymentOperation.objects.count(), 1)
