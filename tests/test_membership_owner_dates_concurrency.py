"""Owner date exceptions serialize with bookings and retain their typed authority."""

import uuid
from datetime import date

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.membership_calendar_changes import confirm, owner_dates_available, review, root_for
from core.membership_calendar_records import MembershipCalendarCorrection
from core.membership_reservations import reserve
from tests import test_membership_calendar_concurrency as fixtures
from tests import test_membership_owner_dates as owner
from tests.test_membership_initial_credit import SETTINGS
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class OwnerDateRaceTests(owner.OwnerDateFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = fixtures.CalendarCorrectionRaceTests.setUp
    race = fixtures.CalendarCorrectionRaceTests.race
    booking = fixtures.CalendarCorrectionRaceTests.booking
    quote = fixtures.CalendarCorrectionRaceTests.quote

    def attempt(self, key, data):
        return confirm(
            **self.owner_values(),
            request_key=key,
            reviewed=data["fingerprint"],
            customer_confirmed=True,
            owner_approved=True,
        )

    def test_same_owner_request_commits_once(self):
        self.prepaid()
        with self.at(date(2027, 11, 1)):
            data = review(**self.owner_values())
            results = self.race(
                lambda: self.attempt(self.date_key, data), lambda: self.attempt(self.date_key, data)
            )
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipCalendarCorrection.objects.count(), 1)

    def test_distinct_owner_requests_cannot_share_a_stale_review(self):
        self.prepaid()
        with self.at(date(2027, 11, 1)):
            data = review(**self.owner_values())
            results = self.race(
                lambda: self.attempt(self.date_key, data), lambda: self.attempt(uuid.uuid4(), data)
            )
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(MembershipCalendarCorrection.objects.count(), 1)

    def test_conflicting_booking_and_owner_exception_cannot_both_commit(self):
        self.prepaid()
        booking = self.booking(day=date(2027, 11, 2), children=1)
        quote = self.quote(booking)

        def booking_action():
            rows = reserve(
                actor=self.staff,
                booking_id=booking.pk,
                quote_id=quote.pk,
                request_key=uuid.uuid4(),
            )
            return rows[0] if rows else None

        with self.at(date(2027, 11, 1)):
            data = review(**self.owner_values())
            result = self.race(lambda: self.attempt(self.date_key, data), booking_action)
        self.assertEqual(sum(value is not None for value in result), 1)
        if MembershipCalendarCorrection.objects.exists():
            self.assertFalse(self.member.benefit_assignments.exists())
        else:
            self.assertTrue(self.member.benefit_assignments.exists())
            self.assertEqual(root_for(self.member).starts_on, date(2027, 10, 31))

    def test_recorded_owner_exception_refuses_authority_reversal(self):
        self.prepaid()
        with self.at(date(2027, 11, 1)):
            saved = self.save_owner()
        with self.assertRaisesMessage(RuntimeError, "cannot be reversed"), transaction.atomic():
            MigrationExecutor(connection).migrate([("core", "0094_paid_visit_split_remainder")])
        self.assertEqual(MembershipCalendarCorrection.objects.get().pk, saved.pk)
        self.assertTrue(owner_dates_available())

    def test_unused_authority_reversal_preserves_ordinary_calendar_history_and_restores_scope(self):
        self.prepaid()
        try:
            MigrationExecutor(connection).migrate([("core", "0094_paid_visit_split_remainder")])
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_get_functiondef('monkeydo_calendar_correction_scope()'::regprocedure)"
                )
                original = cursor.fetchone()[0]
            self.assertFalse(owner_dates_available())
            MigrationExecutor(connection).migrate(
                [("core", "0096_credit_funded_membership_renewals")]
            )
            data = review(**self.inputs)
            normal = confirm(
                **self.inputs,
                request_key=self.date_key,
                reviewed=data["fingerprint"],
                customer_confirmed=True,
            )
            MigrationExecutor(connection).migrate([("core", "0094_paid_visit_split_remainder")])
            self.assertEqual(MembershipCalendarCorrection.objects.get().pk, normal.pk)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_get_functiondef('monkeydo_calendar_correction_scope()'::regprocedure)"
                )
                self.assertEqual(cursor.fetchone()[0], original)
            with self.at(date(2027, 11, 1)), self.assertRaisesMessage(ValidationError, "upgrade"):
                review(**self.owner_values(starts_on=date(2027, 10, 30)))
        finally:
            MigrationExecutor(connection).migrate(
                [("core", "0096_credit_funded_membership_renewals")]
            )
        self.date_key = uuid.uuid4()
        with self.at(date(2027, 11, 1)):
            self.save_owner(starts_on=date(2027, 10, 30))
        self.assertEqual(MembershipCalendarCorrection.objects.count(), 2)
