"""A corrected unused term keeps its stable membership and accepted evidence."""

import uuid
from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from core.membership_calendar_changes import confirm, cycle_on, review, root_for
from core.membership_calendar_records import MembershipCalendarCorrection, MembershipCalendarState
from core.membership_records import MembershipPurchase
from core.membership_reservations import places_for
from core.membership_sales import membership_status
from core.models import FinancialPosting, PaymentOperation
from tests import test_membership_sales as fixtures
from tests.test_membership_initial_credit import SETTINGS


@override_settings(**SETTINGS)
class MembershipCalendarCorrectionTests(TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed

    def prepaid(self):
        self.member = self.buy(billing="prepaid", expected_method="cash", verified_received=True)
        self.date_key = uuid.uuid4()
        self.inputs = dict(
            actor=self.staff,
            member_id=self.member.pk,
            starts_on=date(2027, 11, 5),
            reason="Corrected the start date confirmed by the customer.",
            send_confirmation=False,
        )
        return self.member

    def correct(self, **changed):
        values = self.inputs | changed
        return confirm(
            **values,
            request_key=self.date_key,
            reviewed=review(**values)["fingerprint"],
            customer_confirmed=True,
        )

    def evidence(self):
        self.member.membership.refresh_from_db()
        return dict(
            root=dict(self.member.membership.__dict__),
            cycles=list(self.member.membership.cycles.values()),
            terms=self.member.terms_text,
            fingerprint=self.member.fingerprint,
            payments=list(PaymentOperation.objects.values()),
            postings=list(FinancialPosting.objects.values()),
            purchases=MembershipPurchase.objects.count(),
        )

    def test_preview_creates_no_correction_or_financial_effect(self):
        self.prepaid()
        before = self.evidence()
        result = review(**self.inputs)
        self.assertEqual((result["starts_on"], result["ends_on"]), ("2027-11-05", "2028-02-04"))
        self.assertEqual(before, self.evidence())
        self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_save_keeps_original_calendar_terms_money_and_membership_number(self):
        self.prepaid()
        before = self.evidence()
        correction = self.correct()
        after = self.evidence()
        before["root"].pop("_state")
        after["root"].pop("_state")
        self.assertEqual(before, after)
        self.assertEqual(MembershipCalendarState.objects.get().purchase_id, self.member.pk)
        self.assertEqual(
            (root_for(self.member).starts_on, root_for(self.member).ends_on),
            (date(2027, 11, 5), date(2028, 2, 4)),
        )
        self.assertEqual(membership_status(self.member), "scheduled")
        self.assertEqual(correction.purchase_id, self.member.pk)
        connection.check_constraints()

    def test_only_corrected_benefit_period_is_eligible_and_original_cycle_id_is_reused(self):
        self.prepaid()
        self.correct()
        self.assertEqual(
            places_for(self.customer.pk, appointment_on=date(2027, 11, 2), children=2), []
        )
        offered = places_for(self.customer.pk, appointment_on=date(2027, 11, 6), children=2)
        self.assertEqual(len(offered), 2)
        self.assertEqual(offered[0].cycle_starts_on, date(2027, 11, 5))
        cycle = cycle_on(self.member, date(2027, 12, 6))
        self.assertEqual(cycle.pk, self.member.membership.cycles.get(number=2).pk)
        self.assertEqual(cycle.starts_on, date(2027, 12, 5))
        connection.check_constraints()

    def test_replay_returns_original_and_later_correction_preserves_both_versions(self):
        self.prepaid()
        original = review(**self.inputs)
        first = self.correct()
        again = confirm(
            **self.inputs,
            request_key=self.date_key,
            reviewed=original["fingerprint"],
            customer_confirmed=True,
        )
        self.assertEqual(first.pk, again.pk)
        self.date_key = uuid.uuid4()
        second = self.correct(starts_on=date(2027, 11, 10))
        self.assertEqual(second.previous_id, first.pk)
        self.assertEqual(second.before["starts_on"], "2027-11-05")
        self.assertEqual(
            (MembershipCalendarCorrection.objects.count(), MembershipPurchase.objects.count()),
            (2, 1),
        )
        connection.check_constraints()

    def test_customer_agreement_and_reason_are_required(self):
        self.prepaid()
        for changed in [
            dict(customer_confirmed=False),
            dict(customer_confirmed=1),
            dict(reason=""),
        ]:
            values = (
                self.inputs
                | dict(
                    request_key=self.date_key,
                    reviewed=review(**self.inputs)["fingerprint"],
                    customer_confirmed=True,
                )
                | changed
            )
            with self.subTest(changed=changed), self.assertRaises(ValidationError):
                confirm(**values)
        self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_existing_monthly_schedule_is_not_silently_moved(self):
        member = self.buy()
        self.succeed(member)
        with self.assertRaisesMessage(ValidationError, "payment-schedule"):
            review(actor=self.staff, member_id=member.pk, starts_on=date(2027, 11, 5))

    def test_database_rejects_forged_cycle_dates_even_when_json_and_typed_fields_match(self):
        self.prepaid()
        data = review(**self.inputs)
        data["cycles"][0]["ends_on"] = "2027-12-03"
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipCalendarCorrection.objects.create(
                id=self.date_key,
                purchase=self.member,
                version=1,
                starts_on=date(2027, 11, 5),
                ends_on=date(2028, 2, 4),
                before=data["before"],
                cycles=data["cycles"],
                facts=data,
                fingerprint=data["fingerprint"],
                reason=data["reason"],
                customer_confirmed=True,
                send_confirmation=False,
                actor=self.staff,
            )

    def test_explicit_email_choice_suppresses_old_dates_and_prepares_only_current_update(self):
        self.prepaid()
        old = self.member.messages.get()
        with patch("core.payments.operations.Gateway") as gateway:
            correction = self.correct(send_confirmation=True)
        old.refresh_from_db()
        self.assertEqual(old.state, "cancelled")
        updated = correction.messages.get().message
        self.assertIn("November 5, 2027", updated.text_body)
        self.assertIn("February 4, 2028", updated.text_body)
        self.assertNotIn("payment of", updated.text_body)
        self.assertEqual(updated.state, "queued")
        self.assertEqual(PaymentOperation.objects.count(), 1)
        gateway.assert_not_called()
        connection.check_constraints()

    def test_complimentary_correction_keeps_no_payment_and_same_membership(self):
        self.member = self.buy(
            actor=self.owner, comped=True, billing="prepaid", send_confirmation=False
        )
        self.date_key = uuid.uuid4()
        self.inputs = dict(
            actor=self.staff,
            member_id=self.member.pk,
            starts_on=date(2028, 1, 31),
            reason="Customer confirmed the later start.",
            send_confirmation=False,
        )
        self.correct()
        self.assertEqual(root_for(self.member).ends_on, date(2028, 4, 30))
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        connection.check_constraints()

    def test_short_month_calendars_keep_original_cycle_ids_and_budget(self):
        from core.membership_calendar_changes import cycles_for

        self.prepaid()
        original_ids = list(self.member.membership.cycles.values_list("pk", flat=True))
        self.correct(starts_on=date(2028, 1, 31))
        cycles = cycles_for(self.member)
        self.assertEqual([row.pk for row in cycles], original_ids)
        self.assertEqual(
            [(row.starts_on, row.ends_on) for row in cycles],
            [
                (date(2028, 1, 31), date(2028, 2, 29)),
                (date(2028, 3, 1), date(2028, 3, 30)),
                (date(2028, 3, 31), date(2028, 4, 30)),
            ],
        )
        connection.check_constraints()

    def test_corrected_booking_reservation_and_arrival_use_original_cycle(self):
        from core.membership_reservations import finish
        from tests.test_membership_reservations import MembershipReservationTests

        self.prepaid()
        self.correct()
        booking = MembershipReservationTests.booking(self, day=date(2028, 2, 2), children=1)
        quote = MembershipReservationTests.quote(self, booking)
        from core.membership_reservations import reserve

        assignment = reserve(
            actor=self.staff, booking_id=booking.pk, quote_id=quote.pk, request_key=uuid.uuid4()
        )[0]
        self.assertEqual(assignment.cycle_id, self.member.membership.cycles.get(number=3).pk)
        finish(
            actor=self.staff,
            booking_id=booking.pk,
            request_key=uuid.uuid4(),
            action="used",
            reason="arrival",
        )
        from core.membership_booking import require_paid_existing
        from core.membership_booking_exceptions import unavailable_memberships

        require_paid_existing(booking)
        self.assertEqual(unavailable_memberships(booking), [])
        assignment.refresh_from_db()
        self.assertEqual(assignment.current.status, "used")
        self.assertEqual(self.member.membership.cycles.get(number=1).starts_on, date(2027, 10, 31))
        with self.assertRaisesMessage(ValidationError, "used in a booking"):
            review(**(self.inputs | dict(starts_on=date(2027, 11, 10))))
        connection.check_constraints()

    def test_stale_customer_or_new_date_review_cannot_commit(self):
        from core.models import Customer

        self.prepaid()
        prior = review(**self.inputs)
        Customer.objects.filter(pk=self.customer.pk).update(revision=self.customer.revision + 1)
        with self.assertRaisesMessage(ValidationError, "changed"):
            confirm(
                **self.inputs,
                request_key=self.date_key,
                reviewed=prior["fingerprint"],
                customer_confirmed=True,
            )
        self.correct()
        self.date_key = uuid.uuid4()
        with self.assertRaisesMessage(ValidationError, "changed"):
            confirm(
                **(self.inputs | dict(starts_on=date(2027, 11, 10))),
                request_key=self.date_key,
                reviewed=prior["fingerprint"],
                customer_confirmed=True,
            )
        self.assertEqual(MembershipCalendarCorrection.objects.count(), 1)

    def test_past_unchanged_and_unfunded_terms_are_refused(self):
        self.prepaid()
        for start in (date(2027, 10, 30), self.member.membership.starts_on):
            with self.subTest(start=start), self.assertRaises(ValidationError):
                review(**(self.inputs | dict(starts_on=start)))
        self.key = uuid.uuid4()
        pending = self.buy(billing="prepaid")
        with self.assertRaisesMessage(ValidationError, "payment"):
            review(**(self.inputs | dict(member_id=pending.pk)))
        self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_current_reporting_renewal_notices_and_export_keep_original_dates(self):
        from core.membership_exports import membership_rows
        from core.membership_renewal_notices import candidates
        from core.membership_renewals import renewal_details
        from core.membership_reporting import reporting_members

        self.prepaid()
        self.correct()
        record = reporting_members(on=date(2027, 11, 2)).get(pk=self.member.pk)
        self.assertEqual(record.report_status, "scheduled")
        self.assertEqual(record.effective_ends_on, date(2028, 2, 4))
        renewal = renewal_details(self.member, on=date(2028, 2, 5))
        self.assertEqual(renewal["starts_on"], date(2028, 2, 5))
        rows = list(membership_rows(reporting_members()))
        exported = dict(zip(rows[0], rows[1], strict=True))
        self.assertEqual(exported["starts_on"], date(2027, 11, 5))
        self.assertEqual(exported["original_starts_on"], date(2027, 10, 31))
        self.assertEqual(exported["original_ends_on"], date(2028, 1, 30))
        with patch("core.membership_renewal_notices.today", return_value=date(2028, 1, 30)):
            self.assertEqual(
                [(member.pk, kind) for member, kind in candidates(limit=10)],
                [(self.member.pk, "expiry")],
            )

    def test_cancellation_suggestion_uses_corrected_unused_calendar(self):
        from core.membership_cancellations import review as cancel_review

        self.prepaid()
        self.correct()
        with patch("core.membership_cancellations.today", return_value=date(2027, 11, 2)):
            data = cancel_review(actor=self.owner, member_id=self.member.pk, timing="immediate")
        self.assertEqual(data["suggested_refund"], "107.94")
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_no_email_choice_keeps_original_unsent_body_as_cancelled_evidence(self):
        self.prepaid()
        original = self.member.messages.get()
        body = original.text_body
        correction = self.correct(send_confirmation=False)
        original.refresh_from_db()
        self.assertEqual((original.state, original.text_body), ("cancelled", body))
        self.assertFalse(correction.messages.exists())

    def test_changed_contact_has_one_scoped_current_update_and_inactive_actor_is_retained(self):
        from core.communications.services import claim
        from core.membership_calendar_emails import queue
        from core.models import Customer

        self.prepaid()
        correction = self.correct(send_confirmation=True)
        first = correction.messages.get().message
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        Customer.objects.filter(pk=self.customer.pk).update(
            email="current@example.invalid", revision=self.customer.revision + 1
        )
        with patch("core.communications.services.send") as send:
            self.assertIsNone(claim(first.pk))
            current = queue(correction)
        first.refresh_from_db()
        self.assertEqual(first.state, "cancelled")
        self.assertEqual(current.recipient, "current@example.invalid")
        self.assertEqual(current.actor_id, self.staff.pk)
        self.assertEqual(correction.messages.count(), 2)
        send.assert_not_called()
        connection.check_constraints()

    def test_attempted_unknown_update_is_preserved_and_never_automatically_retried(self):
        from django.utils import timezone

        from core.membership_calendar_emails import queue
        from core.models import Customer

        self.prepaid()
        correction = self.correct(send_confirmation=True)
        original = correction.messages.get().message
        original.state, original.dispatched_at = "unknown", timezone.now()
        original.save(update_fields=["state", "dispatched_at"])
        Customer.objects.filter(pk=self.customer.pk).update(email="current@example.invalid")
        self.assertIsNone(queue(correction))
        self.assertEqual(correction.messages.count(), 1)
        original.refresh_from_db()
        self.assertEqual(original.state, "unknown")

    def test_current_state_and_correction_fact_cannot_be_rewritten_or_removed(self):
        self.prepaid()
        correction = self.correct()
        with self.assertRaises(ValidationError):
            correction.save()
        for statement, params in [
            (
                "UPDATE core_membershipcalendarcorrection SET reason='different' WHERE id=%s",
                [correction.pk],
            ),
            ("DELETE FROM core_membershipcalendarstate WHERE purchase_id=%s", [self.member.pk]),
        ]:
            with (
                self.subTest(statement=statement),
                self.assertRaises(DatabaseError),
                transaction.atomic(),
            ):
                with connection.cursor() as cursor:
                    cursor.execute(statement, params)
        self.assertEqual(root_for(self.member).starts_on, date(2027, 11, 5))
        connection.check_constraints()
