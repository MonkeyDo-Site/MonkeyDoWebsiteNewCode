"""Renewal choices preserve the existing combined booking and hold."""

from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.membership_records import MembershipRenewalPrompt
from core.models import Booking, BookingCapacityHold, Customer, Session
from core.payments import staff_create
from tests import test_single_page_staff_booking as staff_fixtures
from tests.test_membership_booking_prompts import SETTINGS, PromptFixtures
from tests.test_membership_renewals import clock


@override_settings(**SETTINGS)
class BookingRenewalViewTests(PromptFixtures, TestCase):
    draft = staff_fixtures.SinglePageStaffBookingTests.draft
    post = staff_fixtures.SinglePageStaffBookingTests.post

    def setUp(self):
        PromptFixtures.setUp(self)
        self.member = self.prior()
        timer = clock(self.member.membership.ends_on - timedelta(days=5))
        timer.start()
        self.addCleanup(timer.stop)
        self.play = Session.objects.create(
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=3, minutes=15),
            public=True,
            play_mode="both",
            supervised_capacity=5,
        )

    def saved_staff(self):
        return self.client.session[staff_create.KEY][self.key]

    def prepare_staff(self):
        self.draft(session=self.play)
        preview = self.post(children=2, socks=1)
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertIn("Renew your membership", preview.json()["membership_html"])
        flow = self.saved_staff()
        return flow, self.row(flow, source="staff", actor=self.staff)

    def test_staff_choice_changes_no_counts_waivers_booking_or_thirty_minute_hold(self):
        flow, row = self.prepare_staff()
        hold = BookingCapacityHold.objects.get()
        before = hold.expires_at
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=2)):
            response = self.client.post(
                reverse("staff_membership_choice", args=[self.key]),
                dict(decision=row["token"] + ".not_now"),
                HTTP_ACCEPT="application/json",
            )
        self.assertEqual(response.status_code, 200, response.content)
        hold.refresh_from_db()
        self.assertEqual(hold.expires_at, before)
        self.assertEqual(hold.children, 2)
        self.assertEqual(self.saved_staff(), flow)
        self.assertFalse(Booking.objects.exists())
        page = self.client.get(reverse("booking_create"), dict(draft=self.key))
        self.assertNotContains(page, "Renew your membership")
        for label in (
            "Visit payment details",
            "Waiver details",
            "Payment details",
            "Confirm booking",
        ):
            self.assertContains(page, label)

    def test_staff_private_draft_and_csrf_are_required(self):
        _, row = self.prepare_staff()
        url = reverse("staff_membership_choice", args=[self.key])
        data = dict(decision=row["token"] + ".not_now")
        csrf = Client(enforce_csrf_checks=True)
        csrf.cookies = self.client.cookies
        self.assertEqual(csrf.post(url, data).status_code, 403)
        missing = Client()
        missing.force_login(self.staff)
        self.assertEqual(missing.post(url, data).status_code, 400)
        self.assertFalse(MembershipRenewalPrompt.objects.exists())

    def test_changing_selected_customer_rejects_old_customer_choice(self):
        _, row = self.prepare_staff()
        other = Customer.objects.create(
            last_name="Different", phone="2025550199", email="other@example.invalid"
        )
        self.assertEqual(self.post(customer=other.pk).status_code, 200)
        response = self.client.post(
            reverse("staff_membership_choice", args=[self.key]),
            dict(decision=row["token"] + ".not_now"),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MembershipRenewalPrompt.objects.exists())
        self.assertEqual(BookingCapacityHold.objects.get().customer_id, other.pk)

    def public(self):
        flow = self.flow()
        flow["session_id"] = self.play.pk
        flow["details"] = dict(
            children=2, adults=1, babies=0, socks=1, supervised=False, expected_method="cash"
        )
        session = self.client.session
        session["customer_test_booking"] = flow
        session.save()
        return flow

    def test_public_page_and_live_estimate_show_choices_without_changing_the_flow(self):
        flow = self.public()
        response = self.client.get(reverse("customer_booking"))
        self.assertContains(response, "Email me later")
        self.assertContains(response, "9 a.m. New York time")
        self.assertContains(response, 'form="membership-renewal-actions"')
        self.assertFalse(MembershipRenewalPrompt.objects.exists())
        data = dict(
            play_type="open", children=2, adults=1, babies=0, socks=1, expected_method="cash"
        )
        estimate = self.client.post(reverse("customer_live_estimate"), data)
        self.assertEqual(estimate.status_code, 200, estimate.content)
        self.assertIn("Renew your membership", estimate.json()["membership_html"])
        self.assertEqual(self.client.session["customer_test_booking"], flow)
        self.assertFalse(BookingCapacityHold.objects.exists())

    def test_native_choice_preserves_public_data_and_expired_flow_cannot_record_a_choice(self):
        flow = self.public()
        row = self.row(flow)
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            failed = self.client.post(
                reverse("public_membership_choice"), dict(decision=row["token"] + ".not_now")
            )
        self.assertEqual(failed.status_code, 400)
        self.assertFalse(MembershipRenewalPrompt.objects.exists())
        response = self.client.post(
            reverse("public_membership_choice"), dict(decision=row["token"] + ".not_now")
        )
        self.assertContains(response, "You can continue your booking")
        self.assertEqual(self.client.session["customer_test_booking"], flow)
        self.assertFalse(Booking.objects.exists())
