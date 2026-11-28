"""Committed calendar changes serialize with reservations and preserve schema history."""

import uuid
from datetime import date

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.membership_calendar_changes import confirm, review, root_for
from core.membership_calendar_records import MembershipCalendarCorrection
from core.membership_records import MembershipBenefitAssignment
from core.membership_reservations import reserve
from core.models import MembershipPricing, PricingPolicy
from tests import test_membership_calendar_changes as fixtures
from tests import test_membership_cancellations as races
from tests import test_membership_reservations as reservations
from tests.test_membership_initial_credit import SETTINGS
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CalendarCorrectionRaceTests(RuntimeRoleMixin, TransactionTestCase):
    buy = fixtures.MembershipCalendarCorrectionTests.buy
    prepaid = fixtures.MembershipCalendarCorrectionTests.prepaid
    correct = fixtures.MembershipCalendarCorrectionTests.correct
    race = races.MembershipCancellationRaceTests.race
    booking = reservations.MembershipReservationTests.booking
    quote = reservations.MembershipReservationTests.quote

    def setUp(self):
        fixtures.MembershipCalendarCorrectionTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create()
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def attempt(self, *, key, reviewed):
        return confirm(**self.inputs, request_key=key, reviewed=reviewed, customer_confirmed=True)

    def test_same_correction_request_is_committed_once(self):
        self.prepaid()
        fingerprint = review(**self.inputs)["fingerprint"]
        results = self.race(
            lambda: self.attempt(key=self.date_key, reviewed=fingerprint),
            lambda: self.attempt(key=self.date_key, reviewed=fingerprint),
        )
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipCalendarCorrection.objects.count(), 1)

    def test_distinct_requests_cannot_both_use_the_previous_calendar(self):
        self.prepaid()
        fingerprint = review(**self.inputs)["fingerprint"]
        results = self.race(
            lambda: self.attempt(key=self.date_key, reviewed=fingerprint),
            lambda: self.attempt(key=uuid.uuid4(), reviewed=fingerprint),
        )
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(MembershipCalendarCorrection.objects.count(), 1)

    def test_reservation_and_calendar_change_cannot_both_use_conflicting_dates(self):
        self.prepaid()
        booking = self.booking(day=date(2027, 11, 2))
        quote = self.quote(booking)
        fingerprint = review(**self.inputs)["fingerprint"]

        def booking_action():
            return reserve(
                actor=self.staff, booking_id=booking.pk, quote_id=quote.pk, request_key=uuid.uuid4()
            )[0]

        results = self.race(
            lambda: self.attempt(key=self.date_key, reviewed=fingerprint), booking_action
        )
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(
            MembershipCalendarCorrection.objects.count()
            + MembershipBenefitAssignment.objects.count(),
            1,
        )

    def test_runtime_grants_allow_audited_correction_with_readable_history(self):
        self.prepaid()
        with self.runtime_role():
            correction = self.correct()
            self.assertEqual(root_for(self.member).starts_on, date(2027, 11, 5))
        self.assertEqual(MembershipCalendarCorrection.objects.get().pk, correction.pk)

    def test_used_schema_cannot_be_reversed(self):
        self.prepaid()
        correction = self.correct()
        with self.assertRaisesMessage(RuntimeError, "cannot be reversed"), transaction.atomic():
            MigrationExecutor(connection).migrate([("core", "0092_combined_renewal_bank_receipt")])
        self.assertEqual(MembershipCalendarCorrection.objects.get().pk, correction.pk)

    def test_unused_schema_reverses_and_reapplies_without_losing_original_purchase(self):
        self.prepaid()
        try:
            MigrationExecutor(connection).migrate([("core", "0092_combined_renewal_bank_receipt")])
            self.assertNotIn(
                "core_membershipcalendarcorrection", connection.introspection.table_names()
            )
            self.assertEqual(root_for(self.member).starts_on, date(2027, 10, 31))
            with self.assertRaisesMessage(ValidationError, "calendar upgrade"):
                review(**self.inputs)
        finally:
            MigrationExecutor(connection).migrate(
                [("core", "0093_membership_calendar_corrections")]
            )
        self.correct()
        self.assertEqual(root_for(self.member).starts_on, date(2027, 11, 5))
