import copy
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings

from core.models import AuditEvent, Booking, BookingQuote, Customer, PricingPolicy, Session
from core.public_booking import submit_booking
from tests.test_customers import staff_user
from tests.test_owner_accounts import STORAGES


@override_settings(CUSTOMER_TEST_BOOKING=True, STORAGES=STORAGES)
class PublicBookingTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 8, 14, tzinfo=dt_timezone.utc)
        timer = patch("django.utils.timezone.now", return_value=self.now)
        timer.start()
        self.addCleanup(timer.stop)
        self.slot = Session.objects.create(
            starts_at=self.now + timedelta(hours=2),
            ends_at=self.now + timedelta(hours=3, minutes=15),
            public=True,
            play_mode="both",
            supervised_capacity=5,
        )

    def begin(self, phone="2025550191", visited="no"):
        self.assertEqual(self.client.post(f"/book/start/{self.slot.pk}/").status_code, 302)
        return self.client.post("/book/details/", {"phone": phone, "visited": visited})

    def new_review(self, **updates):
        self.begin()
        self.client.post(
            "/book/details/", {"last_name": "Sample Family", "email": "sample@example.invalid"}
        )
        data = {
            "play_type": "open",
            "children": 2,
            "adults": 1,
            "babies": 0,
            "socks": 0,
            "expected_method": "card",
            "referral_source": "Sample referral",
        }
        data.update(updates)
        return self.client.post("/book/details/", data)

    def confirm(self):
        flow = self.client.session["customer_test_booking"]
        return self.client.post(
            "/book/details/", {"flow_key": flow["key"], "acknowledge_test": "on"}
        )

    def test_new_booking_is_pending_audited_and_visible_to_authorized_staff(self):
        self.new_review()
        self.assertEqual(self.confirm().status_code, 302)
        booking = Booking.objects.get()
        self.assertTrue(booking.setup_pending)
        self.assertEqual(booking.source, "customer_test")
        self.assertIsNone(booking.creation_actor)
        self.assertEqual(booking.quotes.get().snapshot["total"], "32.94")
        self.assertIsNone(booking.quotes.get().actor)
        self.assertEqual(booking.customer.customer_type, "family")
        self.assertEqual(booking.referral_source, "Sample referral")
        self.assertEqual(
            AuditEvent.objects.filter(action="booking.customer_test_created").count(), 1
        )
        self.assertContains(self.client.get("/book/receipt/"), "Setup pending")
        self.assertContains(self.client.get("/book/receipt/"), "no email has been sent")
        operator = Client()
        operator.force_login(staff_user())
        self.assertContains(operator.get(f"/staff/bookings/{booking.pk}/"), "Customer test booking")
        self.assertEqual(self.confirm().status_code, 302)
        self.assertEqual(Booking.objects.count(), 1)

    def test_lookup_requires_last_name_before_association_or_email_disclosure(self):
        customer = Customer.objects.create(
            last_name="PrivateFamily", phone="2025550100", email="private@example.invalid"
        )
        self.begin(customer.phone, "yes")
        response = self.client.get("/book/details/")
        self.assertNotContains(response, customer.email)
        self.assertNotContains(response, customer.last_name)
        response = self.client.post("/book/details/", {"last_name": "Wrong"})
        self.assertContains(response, "The last name you entered", status_code=400)
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "blocked")

    def test_new_customer_choice_cannot_bypass_current_phone_verification(self):
        c = Customer.objects.create(
            last_name="O’Name", phone="2025550100", email="family@example.invalid"
        )
        self.begin(c.phone, "no")
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "name")
        self.client.post("/book/details/", {"last_name": " o’name "})
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "details")

    def test_previous_phone_requires_only_confirmation_and_discloses_approved_current_phone(self):
        c = Customer.objects.create(
            last_name="Prior",
            phone="2025550100",
            previous_phone="2025550101",
            email="prior@example.invalid",
        )
        self.begin(c.previous_phone, "yes")
        self.assertContains(self.client.get("/book/details/"), c.phone)
        self.assertNotContains(self.client.get("/book/details/"), c.email)
        self.client.post("/book/details/", {"confirm_phone": "yes"})
        response = self.client.get("/book/details/")
        self.assertContains(response, c.email)
        self.assertNotContains(response, "That name matches our records")

    def test_quote_only_creates_no_customer_or_capacity_hold(self):
        self.new_review()
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertContains(self.client.get("/book/details/"), "32.94")

    def test_price_change_returns_to_review_and_rolls_back_new_customer(self):
        self.new_review()
        PricingPolicy.objects.create(child_price=Decimal("25.00"))
        response = self.confirm()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "details")

    def test_full_session_or_closed_calendar_cannot_be_reserved_from_old_review(self):
        self.new_review()
        self.slot.closed = True
        self.slot.save()
        self.assertEqual(self.confirm().status_code, 400)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(Booking.objects.count(), 0)

    def test_receipt_and_staff_access_are_not_granted_to_another_browser(self):
        self.new_review()
        self.confirm()
        stranger = Client()
        self.assertEqual(stranger.get("/book/receipt/").status_code, 404)
        self.assertEqual(stranger.get("/staff/bookings/").status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get("/staff/bookings/").status_code, 302)

    def test_replayed_service_call_is_idempotent_and_changed_flow_rejected(self):
        self.new_review()
        flow = copy.deepcopy(self.client.session["customer_test_booking"])
        first = submit_booking(flow)
        second = submit_booking(flow)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(BookingQuote.objects.count(), 1)
        changed = copy.deepcopy(flow)
        changed["details"]["children"] = 3
        with self.assertRaises(ValidationError):
            submit_booking(changed)

    def test_hidden_future_or_saturday_session_and_expired_flow_blocked(self):
        self.slot.public = False
        self.slot.save()
        self.assertEqual(self.client.post(f"/book/start/{self.slot.pk}/").status_code, 400)
        self.slot.public = True
        self.slot.save()
        self.begin()
        flow = self.client.session["customer_test_booking"]
        flow["expires"] = self.now.timestamp() - 1
        state = self.client.session
        state["customer_test_booking"] = flow
        state.save()
        self.assertEqual(self.client.get("/book/details/").status_code, 400)

    def test_supervised_and_online_sock_limits_enforced(self):
        self.assertEqual(self.new_review(play_type="supervised", adults=1).status_code, 200)
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "details")
        response = self.client.post(
            "/book/details/",
            {
                "play_type": "supervised",
                "children": 2,
                "adults": 0,
                "babies": 0,
                "socks": 36,
                "expected_method": "cash",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 0)
        self.client.post(
            "/book/details/",
            {
                "play_type": "supervised",
                "children": 2,
                "adults": 0,
                "babies": 0,
                "socks": 1,
                "expected_method": "cash",
            },
        )
        self.assertEqual(self.confirm().status_code, 302)
        self.assertTrue(Booking.objects.get().supervised)
        self.assertEqual(Booking.objects.get().quotes.get().snapshot["processing_fee"], "0.00")

    def test_csrf_is_required_and_feature_off_has_no_customer_write_endpoint(self):
        self.assertEqual(
            Client(enforce_csrf_checks=True).post(f"/book/start/{self.slot.pk}/").status_code, 403
        )
        with override_settings(CUSTOMER_TEST_BOOKING=False):
            self.assertEqual(self.client.post(f"/book/start/{self.slot.pk}/").status_code, 404)
            self.assertEqual(self.client.get("/book/details/").status_code, 404)

    def test_customer_contact_changes_in_staff_workspace_invalidate_verified_flow(self):
        c = Customer.objects.create(
            last_name="Change", phone="2025550100", email="change@example.invalid"
        )
        self.begin(c.phone)
        self.client.post("/book/details/", {"last_name": "Change"})
        c.revision += 1
        c.save()
        self.assertEqual(self.client.get("/book/details/").status_code, 400)

    def test_submitted_client_fields_cannot_override_reviewed_booking(self):
        self.new_review()
        flow = self.client.session["customer_test_booking"]
        response = self.client.post(
            "/book/details/",
            {
                "flow_key": flow["key"],
                "acknowledge_test": "on",
                "children": 0,
                "customer_id": 999999,
                "total": "0.00",
                "capacity_override": "on",
                "setup_pending": "false",
                "source": "staff",
            },
        )
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get()
        self.assertEqual(booking.children, 2)
        self.assertTrue(booking.setup_pending)
        self.assertEqual(booking.source, "customer_test")
        self.assertEqual(booking.quotes.get().snapshot["total"], "32.94")

    def test_review_revision_preserves_details_and_receipt_reflects_release(self):
        self.new_review(socks=2, referral_source="Fictional friend")
        flow = self.client.session["customer_test_booking"]
        self.assertEqual(
            self.client.post("/book/revise/", {"flow_key": flow["key"]}).status_code, 302
        )
        form = self.client.get("/book/details/").context["form"]
        self.assertEqual(form.initial["socks"], 2)
        self.assertEqual(form.initial["referral_source"], "Fictional friend")
        self.client.post(
            "/book/details/",
            {
                "play_type": "open",
                "children": 1,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "expected_method": "cash",
            },
        )
        self.confirm()
        Booking.objects.update(attendance="cancelled")
        response = self.client.get("/book/receipt/")
        self.assertContains(response, "Cancelled")
        self.assertContains(response, "This test booking has been cancelled")

    @override_settings(APP_ENV="staging", DESIGN_REVIEW_ONLY=False)
    def test_shared_staging_gate_lands_on_home_and_does_not_grant_staff_access(self):
        from django.contrib.auth.hashers import make_password
        from django.utils import timezone

        from core.models import SiteSettings

        SiteSettings.objects.create(
            staging_password_hash=make_password("Fictional-preview-2026!"),
            staging_password_changed_at=timezone.now(),
        )
        self.assertRedirects(
            self.client.get("/"), "/staging/access/", fetch_redirect_response=False
        )
        response = self.client.post("/staging/access/", {"password": "Fictional-preview-2026!"})
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        home = self.client.get("/")
        self.assertContains(home, "Every little monkey needs a")
        self.assertContains(home, 'href="/book/"')
        self.assertNotContains(home, 'href="/staff/')
        self.assertEqual(home.headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertContains(self.client.get("/book/"), f"/book/start/{self.slot.pk}/")
        self.assertEqual(self.client.get("/staff/bookings/").status_code, 302)
        self.assertEqual(self.client.get("/01-home.html").status_code, 404)
