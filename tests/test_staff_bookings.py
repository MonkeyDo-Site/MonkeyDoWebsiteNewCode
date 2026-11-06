import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.booking_management import (
    create_test_booking,
    edit_test_booking,
    move_test_booking,
    release_test_booking,
)
from core.models import AuditEvent, Booking, BookingQuote, Customer, PricingPolicy, Session
from tests.helpers import verified_owner_login
from tests.test_customers import staff_user
from tests.test_owner_accounts import STORAGES


class StaffBookingTests(TestCase):
    def setUp(self):
        self.staff = staff_user()
        self.owner = staff_user("owner", owner=True)
        self.customer = Customer.objects.create(
            last_name="Test Family", phone="2025550100", email="test@example.invalid"
        )
        start = timezone.now() + timedelta(days=3)
        self.session = Session.objects.create(
            starts_at=start,
            ends_at=start + timedelta(minutes=75),
            public=False,
            supervised_capacity=3,
        )
        self.target = Session.objects.create(
            starts_at=start + timedelta(days=1),
            ends_at=start + timedelta(days=1, minutes=75),
            public=False,
            supervised_capacity=3,
        )
        self.key = uuid.uuid4()

    def create(self, **kwargs):
        args = dict(
            actor=self.staff,
            customer=self.customer,
            session_id=self.session.pk,
            children=2,
            adults=2,
            creation_key=self.key,
        )
        args.update(kwargs)
        return create_test_booking(**args)

    def test_creation_stores_snapshot_and_pending_status_not_payment(self):
        booking = self.create()
        self.assertTrue(booking.setup_pending)
        self.assertEqual(booking.status_label, "Setup pending")
        self.assertEqual(booking.quotes.get().snapshot["total"], "38.43")
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.get(action="booking.test_created").actor, self.staff)

    def test_repeat_submission_is_idempotent_but_changed_payload_rejected(self):
        first = self.create()
        second = self.create()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(BookingQuote.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.create(children=3)

    def test_changed_future_prices_do_not_reprice_edits_or_rescheduling(self):
        booking = self.create()
        old = booking.quotes.get()
        PricingPolicy.objects.create(child_price=Decimal("99.00"), tax_rate=Decimal("0.01"))
        edit_test_booking(
            actor=self.staff,
            booking_id=booking.pk,
            version=1,
            children=3,
            adults=2,
            babies=0,
            socks=0,
            expected_method="cash",
        )
        booking.refresh_from_db()
        self.assertEqual(booking.quotes.first().snapshot["subtotal"], "50.00")
        self.assertEqual(booking.quotes.first().policy_id, old.policy_id)
        quote_count = booking.quotes.count()
        move_test_booking(
            actor=self.staff, booking_id=booking.pk, version=2, session_id=self.target.pk
        )
        self.assertEqual(booking.quotes.count(), quote_count)
        old.refresh_from_db()
        self.assertEqual(old.snapshot["subtotal"], "35.00")

    def test_capacity_rejection_and_owner_override_audit(self):
        with self.assertRaises(ValidationError):
            self.create(children=36)
        with self.assertRaises(ValidationError):
            self.create(children=36, override_capacity=True)
        booking = self.create(actor=self.owner, children=36, override_capacity=True)
        self.assertEqual(booking.children, 36)
        self.assertTrue(
            AuditEvent.objects.get(action="booking.test_created").changes["capacity_override"]
        )

    def test_failed_move_preserves_original_capacity_and_price(self):
        booking = self.create()
        Booking.objects.create(customer=self.customer, session=self.target, children=35, adults=1)
        with self.assertRaises(ValidationError):
            move_test_booking(
                actor=self.staff, booking_id=booking.pk, version=1, session_id=self.target.pk
            )
        booking.refresh_from_db()
        self.assertEqual(booking.session_id, self.session.pk)
        self.assertEqual(booking.edit_version, 1)
        self.assertEqual(booking.quotes.count(), 1)

    def test_successful_move_audits_old_new_and_no_quote_change(self):
        booking = self.create()
        move_test_booking(
            actor=self.staff, booking_id=booking.pk, version=1, session_id=self.target.pk
        )
        booking.refresh_from_db()
        self.assertEqual(booking.session_id, self.target.pk)
        event = AuditEvent.objects.get(action="booking.timing_changed")
        self.assertEqual(event.changes["before"]["session_id"], self.session.pk)
        self.assertEqual(event.changes["after"]["session_id"], self.target.pk)

    def test_failed_quote_or_audit_rolls_back_entire_booking(self):
        with patch(
            "core.booking_management.BookingQuote.objects.create",
            side_effect=RuntimeError("failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action="booking.test_created").exists())

    def test_confirmed_booking_cannot_use_pending_test_editor_or_release(self):
        booking = self.create()
        booking.setup_pending = False
        booking.save()
        with self.assertRaises(ValidationError):
            release_test_booking(actor=self.staff, booking_id=booking.pk, version=1)
        with self.assertRaises(ValidationError):
            edit_test_booking(
                actor=self.staff,
                booking_id=booking.pk,
                version=1,
                children=1,
                adults=1,
                babies=0,
                socks=0,
                expected_method="card",
            )

    def test_release_frees_hold_without_charging_or_waiving_customer_fees(self):
        booking = self.create()
        release_test_booking(actor=self.staff, booking_id=booking.pk, version=1)
        booking.refresh_from_db()
        self.assertEqual(booking.status_label, "Released test reservation")
        self.assertFalse(
            AuditEvent.objects.get(action="booking.test_released").changes["fee_processed"]
        )
        self.assertEqual(booking.quotes.count(), 1)

    def test_stale_edits_rejected(self):
        booking = self.create()
        move_test_booking(
            actor=self.staff, booking_id=booking.pk, version=1, session_id=self.target.pk
        )
        with self.assertRaises(ValidationError):
            edit_test_booking(
                actor=self.staff,
                booking_id=booking.pk,
                version=1,
                children=1,
                adults=1,
                babies=0,
                socks=0,
                expected_method="card",
            )

    def test_supervised_end_cutoff_and_closed_party_never_overridden(self):
        self.session.kind = "party"
        self.session.save()
        with self.assertRaises(ValidationError):
            self.create(actor=self.owner, override_capacity=True)
        self.session.kind = "ordinary"
        self.session.save()
        with patch("django.utils.timezone.now", return_value=self.session.starts_at):
            with self.assertRaises(ValidationError):
                self.create(children=2, adults=0, supervised=True)
            self.assertTrue(self.create().setup_pending)

    def test_quote_sql_and_model_mutation_rejected(self):
        quote = self.create().quotes.get()
        with self.assertRaises(ValidationError):
            quote.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_bookingquote SET revision = 99 WHERE id = %s", [quote.pk]
                )


@override_settings(STORAGES=STORAGES)
class StaffBookingPageTests(TestCase):
    setUp = StaffBookingTests.setUp
    create = StaffBookingTests.create

    def test_browser_form_roundtrip_and_quote_not_client_supplied(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            "/staff/bookings/new/",
            {
                "customer": self.customer.pk,
                "session": self.session.pk,
                "children": 2,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "expected_method": "card",
                "creation_key": str(self.key),
                "total": "0.01",
            },
        )
        booking = Booking.objects.get()
        self.assertRedirects(response, f"/staff/bookings/{booking.pk}/")
        self.assertEqual(booking.quotes.get().snapshot["total"], "32.94")
        self.assertContains(self.client.get(response.url), "Setup pending")
        self.assertContains(self.client.get(response.url), "$32.94")

    def test_owner_pricing_creates_new_version_staff_denied(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/staff/pricing/").status_code, 403)
        verified_owner_login(self.client, self.owner)
        response = self.client.post(
            "/staff/pricing/",
            {
                "child_price": "16",
                "extra_adult_price": "5",
                "minimum_admission": "15",
                "supervised_price": "18.99",
                "sock_price": "1.99",
                "tax_percent": "6.60",
                "fee_percent": "3.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PricingPolicy.objects.first().child_price, Decimal("16"))

    def test_booking_release_is_post_only(self):
        booking = self.create()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(f"/staff/bookings/{booking.pk}/release/").status_code, 405)

    def test_missing_booking_permission_is_enforced_by_view_and_service(self):
        from django.contrib.auth import get_user_model
        from django.core.exceptions import PermissionDenied

        restricted = get_user_model().objects.create_user(username="restricted", is_staff=True)
        self.client.force_login(restricted)
        self.assertEqual(self.client.get("/staff/bookings/").status_code, 403)
        self.assertEqual(self.client.post("/staff/bookings/new/", {}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.create(actor=restricted)
        self.assertFalse(Booking.objects.exists())

    def test_booking_writes_require_csrf(self):
        from django.test import Client

        booking = self.create()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(
            client.post(f"/staff/bookings/{booking.pk}/release/", {"version": 1}).status_code, 403
        )
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
