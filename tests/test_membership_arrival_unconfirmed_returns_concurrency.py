"""Owner unused-fund review serializes with first-payment outcomes and arrival."""

from decimal import Decimal

from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings

from core.membership_arrival_pending import complete
from core.membership_arrival_receipts import summary
from core.membership_records import (
    MembershipArrivalReceiptApplication,
    MembershipArrivalReceiptReturn,
)
from core.models import Booking, PaymentOperation
from tests import test_customer_credit_concurrency as setup_fixtures
from tests import test_membership_arrival_returns_concurrency as races
from tests import test_membership_arrival_unconfirmed_returns as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class UnconfirmedVisitReturnRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = setup_fixtures.CustomerCreditRaceTests.setUp
    overlap = races.PendingVisitReturnRaceTests.overlap
    return_options = races.PendingVisitReturnRaceTests.return_options
    prepare = fixtures.UnconfirmedVisitReturnTests.prepare
    start = fixtures.UnconfirmedVisitReturnTests.start
    mixed = fixtures.UnconfirmedVisitReturnTests.mixed
    accept = fixtures.UnconfirmedVisitReturnTests.accept
    result = fixtures.UnconfirmedVisitReturnTests.result
    unresolved = fixtures.UnconfirmedVisitReturnTests.unresolved
    pause = fixtures.UnconfirmedVisitReturnTests.pause
    give_back = fixtures.UnconfirmedVisitReturnTests.give_back

    def test_distinct_unknown_payment_returns_cannot_overdraw_the_visit_receipt(self):
        import uuid

        from core.membership_arrival_returns import record

        self.unresolved()
        self.pause()
        options = self.return_options()
        a, b = self.overlap(
            lambda: record(**options).pk,
            lambda: record(**(options | dict(request_key=uuid.uuid4()))).pk,
        )
        self.assertEqual(sorted([a[0], b[0]]), ["blocked", "ok"])
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))
        self.assertEqual(PaymentOperation.objects.get(pk=self.intent.operation_id).state, "unknown")
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_late_success_and_actual_visit_return_both_preserve_owner_pause(self):
        from core.membership_arrival_returns import record

        self.unresolved()
        self.pause()
        options = self.return_options()

        def payment():
            self.result()
            return complete(self.intent.pk).code

        a, b = self.overlap(lambda: record(**options).pk, payment)
        self.assertEqual((a[0], b[0]), ("ok", "ok"))
        self.assertEqual(b[1], "owner_review_requested")
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(Booking.objects.get(pk=self.play.pk).attendance, "")

    def test_owner_pause_and_funded_continuation_cannot_leave_a_partly_arrived_booking(self):
        self.unresolved()

        def payment_and_arrival():
            self.result()
            return complete(self.intent.pk).status

        a, b = self.overlap(lambda: self.pause().status, payment_and_arrival)
        self.assertEqual(b[0], "ok")
        booking = Booking.objects.get(pk=self.play.pk)
        if a[0] == "ok":
            self.assertEqual((a[1], b[1], booking.attendance), ("review", "review", ""))
            self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())
            self.assertEqual(PaymentOperation.objects.count(), 3)
        else:
            self.assertEqual((b[1], booking.attendance), ("completed", "arrived"))
            self.assertEqual(MembershipArrivalReceiptApplication.objects.count(), 4)
            self.assertEqual(PaymentOperation.objects.count(), 8)
        close_old_connections()
