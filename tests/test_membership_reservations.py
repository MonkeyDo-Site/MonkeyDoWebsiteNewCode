"""Durable benefit allocation uses current paid cohorts and keeps released evidence."""

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from core.membership_records import (
    MembershipBenefitAssignment,
    MembershipBenefitBatch,
    MembershipBenefitEvent,
    MembershipBenefitState,
)
from core.membership_reservations import finish, quote_visit, reserve
from core.models import Booking, BookingQuote, CalendarDate, PricingPolicy, Session
from tests import test_membership_sales as fixtures
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
)
class MembershipReservationTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed

    def member(self, **values):
        self.key = uuid.uuid4()
        return self.buy(
            places=values.pop("places", 1),
            billing=values.pop("billing", "prepaid"),
            expected_method=values.pop("expected_method", "cash"),
            verified_received=True,
            **values,
        )

    def booking(self, day=date(2027, 11, 1), *, children=1, adults=2, customer=None, hour=13):
        start = datetime.combine(
            day, datetime.min.time(), ZoneInfo("America/New_York")
        ) + timedelta(hours=hour)
        session, _ = Session.objects.get_or_create(
            starts_at=start,
            defaults=dict(
                ends_at=start + timedelta(minutes=75),
                child_capacity=35,
                total_capacity=50,
                supervised_capacity=5,
                public=True,
            ),
        )
        return Booking.objects.create(
            customer=customer or self.customer,
            session=session,
            children=children,
            adults=adults,
            creation_actor=self.staff,
            workflow="integrated_v1",
            setup_pending=False,
            expected_method="cash",
        )

    def quote(self, booking):
        policy = PricingPolicy.objects.first()
        snapshot = quote_visit(
            policy,
            customer_id=booking.customer_id,
            appointment_on=booking.session.starts_at.date(),
            children=booking.children,
            adults=booking.adults,
            babies=booking.babies,
            socks=booking.socks,
            supervised=booking.supervised,
            expected_method=booking.expected_method,
            exclude_booking=booking.pk,
        )
        previous = booking.quotes.first()
        return BookingQuote.objects.create(
            booking=booking,
            policy=policy,
            revision=previous.revision + 1 if previous else 1,
            snapshot=snapshot,
            actor=self.staff,
        )

    def assign(self, booking, *, quote=None, key=None):
        quote = quote or self.quote(booking)
        return reserve(
            actor=self.staff,
            booking_id=booking.pk,
            quote_id=quote.pk,
            request_key=key or uuid.uuid4(),
        )

    def release(self, booking, *, action="released", reason="cancellation", key=None):
        return finish(
            actor=self.staff,
            booking_id=booking.pk,
            request_key=key or uuid.uuid4(),
            action=action,
            reason=reason,
        )

    def test_preview_is_read_only_and_two_subscription_visits_then_additional_price(self):
        self.member()
        first = self.booking()
        initial = self.quote(first)
        self.assertEqual(initial.snapshot["total"], "0.00")
        self.assertFalse(MembershipBenefitBatch.objects.exists())
        self.assign(first, quote=initial)
        second = self.booking(date(2027, 11, 2))
        self.assign(second)
        third = self.booking(date(2027, 11, 3))
        third_quote = self.quote(third)
        self.assertEqual(third_quote.snapshot["lines"][0]["unit_price"], "5.99")
        self.assign(third, quote=third_quote)
        self.assertEqual(
            MembershipBenefitAssignment.objects.filter(kind="subscription_free").count(), 2
        )
        self.assertEqual(
            MembershipBenefitAssignment.objects.filter(kind="subscription_additional").count(), 1
        )

    def test_two_places_never_cover_three_children_in_one_booking(self):
        self.member(places=2)
        booking = self.booking(children=3)
        items = self.assign(booking)
        self.assertEqual(len(items), 2)
        self.assertEqual(booking.quotes.first().snapshot["subtotal"], "15.00")
        self.assertEqual({item.place for item in items}, {1, 2})

    def test_unlimited_is_once_per_new_york_day_and_release_does_not_reprice_other_booking(self):
        self.member(kind="unlimited")
        first = self.booking()
        self.assign(first)
        second = self.booking()
        saved = self.quote(second)
        self.assertFalse(saved.snapshot["membership_benefits_applied"])
        self.release(first)
        self.assertFalse(
            BookingQuote.objects.get(pk=saved.pk).snapshot["membership_benefits_applied"]
        )
        refreshed = self.quote(second)
        self.assertTrue(refreshed.snapshot["membership_benefits_applied"])
        self.assign(second, quote=refreshed)
        next_day = self.booking(date(2027, 11, 2))
        self.assertTrue(self.quote(next_day).snapshot["membership_benefits_applied"])

    def test_stale_concurrent_preview_rejected_without_double_reserving(self):
        self.member(kind="unlimited")
        first, second = self.booking(), self.booking()
        q1, q2 = self.quote(first), self.quote(second)
        self.assign(first, quote=q1)
        with self.assertRaises(ValidationError):
            self.assign(second, quote=q2)
        self.assertEqual(MembershipBenefitAssignment.objects.count(), 1)
        self.assertEqual(MembershipBenefitBatch.objects.count(), 1)

    def test_arrival_consumes_reservation_and_no_show_releases_with_immutable_history(self):
        self.member()
        booking = self.booking()
        item = self.assign(booking)[0]
        self.release(booking, action="used", reason="arrival")
        self.assertEqual(MembershipBenefitState.objects.get(assignment=item).status, "used")
        self.release(booking, reason="no_show")
        self.assertEqual(
            list(item.events.order_by("pk").values_list("batch__action", flat=True)),
            ["reserved", "used", "released"],
        )
        self.assertEqual(MembershipBenefitState.objects.get(assignment=item).status, "released")
        self.assertEqual(self.quote(self.booking()).snapshot["total"], "0.00")

    def test_repeated_reservation_and_release_keys_are_idempotent(self):
        self.member()
        booking = self.booking()
        quote = self.quote(booking)
        key = uuid.uuid4()
        first = self.assign(booking, quote=quote, key=key)
        self.assertEqual(
            [x.pk for x in self.assign(booking, quote=quote, key=key)], [x.pk for x in first]
        )
        release_key = uuid.uuid4()
        self.release(booking, key=release_key)
        self.release(booking, key=release_key)
        self.assertEqual(MembershipBenefitEvent.objects.count(), 2)
        with self.assertRaises(ValidationError):
            self.release(booking, key=release_key, reason="no_show")

    def test_move_same_day_transfers_daily_benefit_and_preserves_original(self):
        self.member(kind="unlimited")
        booking = self.booking()
        original = self.assign(booking)[0]
        target = self.booking(hour=15)
        booking.session = target.session
        booking.save(update_fields=["session"])
        quote = self.quote(booking)
        updated = self.assign(booking, quote=quote)[0]
        self.assertNotEqual(original.pk, updated.pk)
        original.refresh_from_db()
        self.assertEqual(original.current.status, "released")
        self.assertEqual(updated.current.status, "reserved")
        self.assertEqual(MembershipBenefitEvent.objects.count(), 3)

    def test_future_month_can_be_reserved_before_installment_due_but_overdue_blocks_new_benefits(
        self,
    ):
        member = self.member(billing="monthly")
        future = self.booking(date(2027, 12, 2))
        self.assign(future)
        self.assertEqual(future.quotes.first().snapshot["total"], "0.00")
        with patch("core.membership_reservations.today", return_value=date(2027, 11, 30)):
            new = self.booking(date(2027, 12, 3))
            self.assertFalse(self.quote(new).snapshot["membership_benefits_applied"])
        self.assertEqual(future.quotes.count(), 1)
        self.assertEqual(future.membership_benefits.get().current.status, "reserved")
        self.assertEqual(member.installments.count(), 3)

    def test_chol_hamoed_excludes_unlimited_and_preserves_subscription_and_adult_allowance(self):
        self.member(kind="unlimited")
        self.member(kind="subscription")
        CalendarDate.objects.create(day=date(2027, 11, 1), chol_hamoed=True)
        booking = self.booking(children=2, adults=3)
        quote = self.quote(booking)
        items = self.assign(booking, quote=quote)
        self.assertEqual([item.kind for item in items], ["subscription_free"])
        self.assertEqual(quote.snapshot["membership_plan"]["free_adults"], 2)
        self.assertEqual(quote.snapshot["subtotal"], "20.00")

    def test_owner_price_and_complimentary_visits_do_not_consume_membership(self):
        from core.payments.models import BookingChargeState

        self.member()
        booking = self.booking()
        policy = PricingPolicy.objects.first()
        state = BookingChargeState.objects.create(booking=booking, special_subtotal="10.00")
        data = quote_visit(
            policy,
            customer_id=self.customer.pk,
            appointment_on=booking.session.starts_at.date(),
            children=1,
            adults=2,
            expected_method="cash",
            exclude_booking=booking.pk,
            special_admissions=state.special_subtotal,
        )
        quote = BookingQuote.objects.create(
            booking=booking, policy=policy, revision=1, snapshot=data, actor=self.owner
        )
        self.assertTrue(data["membership_plan"]["owner_price_review"])
        self.assertEqual(self.assign(booking, quote=quote), [])
        self.assertFalse(MembershipBenefitAssignment.objects.exists())

    def test_cross_customer_membership_snapshot_cannot_be_injected(self):
        from core.models import Customer

        self.member()
        original = self.booking()
        data = self.quote(original).snapshot
        other = Customer.objects.create(
            last_name="Other", phone="2025550102", email="other@example.invalid"
        )
        booking = self.booking(customer=other)
        quote = BookingQuote.objects.create(
            booking=booking,
            policy=PricingPolicy.objects.first(),
            revision=1,
            snapshot=data,
            actor=self.staff,
        )
        with self.assertRaises(ValidationError):
            self.assign(booking, quote=quote)
        self.assertFalse(MembershipBenefitAssignment.objects.exists())

    def test_runtime_grants_allow_reserve_consume_and_release_but_facts_cannot_be_edited(self):
        self.member()
        booking = self.booking()
        quote = self.quote(booking)
        with self.runtime_role():
            item = self.assign(booking, quote=quote)[0]
            self.release(booking, action="used", reason="arrival")
            self.release(booking)
        for obj in [item, item.reserved_by, item.events.first()]:
            with self.assertRaises(ValidationError):
                obj.save()
            table, column = obj._meta.db_table, obj._meta.pk.column
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {table} SET {column}={column} WHERE {column}=%s", [obj.pk]
                    )

    def test_projection_cannot_lie_about_immutable_evidence_or_restore_released_benefit(self):
        self.member()
        booking = self.booking()
        item = self.assign(booking)[0]
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipBenefitState.objects.filter(assignment=item).update(status="used")
        self.release(booking)
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipBenefitState.objects.filter(assignment=item).update(status="reserved")

    def test_actor_and_legacy_booking_boundaries(self):
        self.member()
        booking = self.booking()
        quote = self.quote(booking)
        with self.assertRaises(PermissionDenied):
            reserve(actor=None, booking_id=booking.pk, quote_id=quote.pk, request_key=uuid.uuid4())
        Booking.objects.filter(pk=booking.pk).update(workflow="legacy_test")
        with self.assertRaises(ValidationError):
            self.assign(booking, quote=quote)
        self.assertFalse(MembershipBenefitBatch.objects.exists())

    def test_summary_separates_available_reserved_and_used_without_losing_release_history(self):
        from core.membership_reservations import summary_for

        member = self.member()
        self.assertEqual(summary_for(member)["available"], 2)
        booking = self.booking()
        self.assign(booking)
        summary = summary_for(member)
        self.assertEqual((summary["available"], summary["reserved"], summary["used"]), (1, 1, 0))
        self.release(booking, action="used", reason="arrival")
        summary = summary_for(member)
        self.assertEqual((summary["available"], summary["reserved"], summary["used"]), (1, 0, 1))
        self.release(booking)
        self.assertEqual(summary_for(member)["available"], 2)
        self.assertEqual(booking.membership_benefits.get().events.count(), 3)

    def test_summary_keeps_unpaid_benefits_unavailable(self):
        from core.membership_reservations import summary_for

        member = self.buy()
        self.assertFalse(summary_for(member)["can_apply"])
        self.assertEqual(summary_for(member)["available"], 0)


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
)
class MembershipReservationRaceTests(TransactionTestCase):
    def setUp(self):
        fixtures.MembershipPurchaseTests.setUp(self)
        from core.models import MembershipPricing

        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create(
                subscription="17.99", unlimited="39.99", actor=self.owner
            )
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    buy = fixtures.MembershipPurchaseTests.buy
    member = MembershipReservationTests.member
    booking = MembershipReservationTests.booking
    quote = MembershipReservationTests.quote

    def race(self, *, kind, contenders, expected):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL advisory-lock integration")
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.contrib.auth import get_user_model
        from django.db import close_old_connections, connections

        self.member(kind=kind)
        pairs = []
        for _ in range(contenders):
            booking = self.booking()
            pairs.append((booking.pk, self.quote(booking).pk))
        barrier = Barrier(contenders)
        actor_id = self.staff.pk

        def attempt(pair):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET LOCAL lock_timeout='10s'")
                        reserve(
                            actor=actor,
                            booking_id=pair[0],
                            quote_id=pair[1],
                            request_key=uuid.uuid4(),
                        )
                    return "reserved"
                except ValidationError:
                    return "review_changed_benefits"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=contenders) as pool:
            results = list(pool.map(attempt, pairs))
        self.assertEqual(results.count("reserved"), expected, results)
        self.assertEqual(results.count("review_changed_benefits"), contenders - expected, results)
        self.assertEqual(MembershipBenefitAssignment.objects.count(), expected)
        self.assertEqual(MembershipBenefitState.objects.filter(status="reserved").count(), expected)

    def test_two_simultaneous_bookings_cannot_take_one_unlimited_daily_place(self):
        self.race(kind="unlimited", contenders=2, expected=1)

    def test_three_simultaneous_bookings_cannot_take_more_than_two_free_subscription_visits(self):
        self.race(kind="subscription", contenders=3, expected=2)
