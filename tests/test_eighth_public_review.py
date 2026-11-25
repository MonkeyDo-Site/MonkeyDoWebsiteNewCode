"""Eighth review: confirmation boundaries, legacy recovery and reusable presentation."""

from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.booking_navigation import CHECKPOINTS
from core.communications.content import booking_confirmation, session_subject, zelle_instructions
from core.models import Booking, FinancialPosting, MessageDelivery, PaymentSetup
from core.payments.setup_views import card_context
from core.public_booking import review_quote, submit_booking
from core.public_booking_views import SESSION_KEY, DetailsForm
from core.templatetags.booking_display import count_words, phone_display
from tests import test_sixth_booking_review as fixtures


class PublicDisplayTests(SimpleTestCase):
    def test_time_ranges_share_meridiem_only_when_both_endpoints_match(self):
        from django.template import Context, Template

        from core.date_display import display_time_range

        ny = ZoneInfo("America/New_York")
        for start_hour, start_minute, end_hour, end_minute, expected in (
            (9, 0, 10, 15, "9:00–10:15 AM"),
            (14, 30, 15, 45, "2:30–3:45 PM"),
            (11, 30, 12, 45, "11:30 AM–12:45 PM"),
            (0, 0, 1, 15, "12:00–1:15 AM"),
        ):
            with self.subTest(expected=expected):
                start = datetime(2026, 11, 26, start_hour, start_minute, tzinfo=ny)
                end = start.replace(hour=end_hour, minute=end_minute)
                # Stored UTC and template rendering must use the same NY meridiem.
                start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
                self.assertEqual(display_time_range(start, end), expected)
                self.assertEqual(
                    Template("{{ start|time_range:end }}").render(
                        Context({"start": start, "end": end})
                    ),
                    expected,
                )

    def test_counts_and_phone_format_never_rewrite_values(self):
        for count in (0, 1, 2):
            self.assertEqual(
                count_words(count, "child"), f"{count} {'child' if count == 1 else 'children'}"
            )
            self.assertEqual(
                count_words(count, "adult"), f"{count} {'adult' if count == 1 else 'adults'}"
            )
            self.assertEqual(
                count_words(count, "baby"), f"{count} {'baby' if count == 1 else 'babies'}"
            )
            self.assertEqual(
                count_words(count, "socks"), f"{count} {'pair' if count == 1 else 'pairs'} of socks"
            )
        for number in ("7325550147", "17325550147", "732-555-0147"):
            self.assertEqual(phone_display(number), "732-555-0147")


@override_settings(**fixtures.SETTINGS)
class EighthPublicTests(TestCase):
    setUp = fixtures.SixthBookingTests.setUp
    create = fixtures.SixthBookingTests.create
    flow = fixtures.SixthBookingTests.flow
    ready = fixtures.SixthBookingTests.ready
    card = fixtures.SixthBookingTests.card
    save_card = fixtures.SixthBookingTests.save_card
    gateway = fixtures.SixthBookingTests.gateway
    bare_flow = fixtures.SixthBookingTests.bare_flow
    store = fixtures.SixthBookingTests.store

    def test_single_button_does_not_allow_booking_without_card_and_waiver(self):
        flow = self.bare_flow()
        flow["stage"] = "review"
        self.store(flow)
        response = self.client.get(reverse("customer_booking"))
        self.assertContains(response, "Confirm booking", count=1)
        self.assertNotContains(response, "Save card securely")
        self.assertContains(response, 'data-single-confirm="1"')
        self.assertContains(response, "processing-dots")
        self.assertContains(response, 'name="agree_cancellation" required')
        response = self.client.post(
            reverse("customer_booking"), {"flow_key": flow["key"], "acknowledge_test": "on"}
        )
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())

    def test_saved_card_can_confirm_once_without_admission_collection(self):
        flow = self.ready()
        flow["stage"] = "review"
        self.store(flow)
        from core.payments.setup import selected_consent

        page = self.client.get(reverse("customer_booking"))
        self.assertContains(page, f'value="{selected_consent(flow).method_id}" checked')
        self.assertNotContains(page, 'value="new" checked')
        self.assertContains(page, "Saved payment method ending in")
        values = {
            "flow_key": flow["key"],
            "payment_consent": flow["payment_consent"],
            "acknowledge_test": "on",
        }
        for _ in range(2):
            response = self.client.post(reverse("customer_booking"), values)
            self.assertEqual(response.status_code, 302)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.count(), 1)
        self.assertFalse(FinancialPosting.objects.exists())

    def test_stale_legacy_flow_returns_to_details_with_current_required_workflow(self):
        flow = self.bare_flow()
        flow.pop("workflow")
        flow["stage"] = "review"
        self.store(flow)
        response = self.client.get(reverse("customer_booking"))
        state = self.client.session[SESSION_KEY]
        self.assertEqual(state["workflow"], "integrated_v1")
        self.assertEqual(state["stage"], "details")
        self.assertEqual(state["details"], flow["details"])
        self.assertNotContains(response, "Save pending test reservation")
        self.assertNotIn("quote", state)
        self.assertFalse(Booking.objects.exists())

    def test_legacy_history_checkpoint_cannot_reopen_legacy_confirmation(self):
        flow = self.ready()
        current = deepcopy(flow)
        current["stage"] = "details"
        old = deepcopy(flow)
        old.pop("workflow")
        old["stage"] = "review"
        self.store(current)
        state = self.client.session
        state[CHECKPOINTS] = {"key": current["key"], "steps": {"review": old}}
        state.save()
        response = self.client.get(
            reverse("customer_booking"), {"step": "review", "flow": flow["key"]}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[SESSION_KEY]["workflow"], "integrated_v1")
        self.assertFalse(Booking.objects.exists())

    def test_direct_new_legacy_submission_is_rejected_when_completed_flow_is_enabled(self):
        flow = self.bare_flow()
        flow.pop("workflow")
        with self.assertRaisesMessage(ValidationError, "current waiver and card setup"):
            submit_booking(flow)
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(MessageDelivery.objects.exists())

    @override_settings(APP_ENV="staging", BOOKING_COMPLETION_ENABLED=False)
    def test_staging_without_completion_cannot_fall_back_to_pending_test_bookings(self):
        flow = self.bare_flow()
        from core.public_booking_views import wizard

        response = wizard(RequestFactory().get("/book/details/"))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"Save pending test reservation", response.content)
        # Service enforcement also protects against a direct legacy write.
        flow.pop("workflow")
        with self.assertRaises(ValidationError):
            submit_booking(flow)
        self.assertFalse(Booking.objects.exists())

    def test_public_details_keep_baby_only_visits_and_require_open_play_adult(self):
        flow = self.bare_flow()
        from core.models import Session

        slot = Session.objects.get(pk=flow["session_id"])
        values = dict(
            play_type="open", children=0, adults=1, babies=1, socks=0, expected_method="cash"
        )
        self.assertTrue(DetailsForm(values, session=slot).is_valid())
        self.assertFalse(DetailsForm(values | {"adults": 0}, session=slot).is_valid())
        self.assertEqual(DetailsForm(session=slot).fields["adults"].widget.attrs["min"], 1)

    def test_confirmation_subject_omits_year_reference_and_body_includes_end_time(self):
        flow = self.ready()
        booking = submit_booking(flow)
        subject = session_subject(booking)
        body = booking_confirmation(booking)
        self.assertIn(" - ", subject)
        self.assertNotIn(str(booking.session.starts_at.year), subject)
        self.assertNotIn(str(booking.reference), subject + body)
        self.assertNotIn("Monkey Do", subject + body)
        from core.date_display import display_date

        self.assertIn(display_date(booking.session.ends_at, "g:i A"), body)
        self.assertEqual(MessageDelivery.objects.get().subject, subject)

    def test_zelle_confirmation_reuses_email_instructions_and_correct_count_words(self):
        flow = self.ready()
        flow["details"]["expected_method"] = "zelle"
        flow["details"]["zelle_sender"] = "Test Sender"
        flow["details"]["socks"] = 1
        flow["quote"] = review_quote(flow, flow["details"])
        # A fresh explicit consent is needed after changing the selected tender.
        from core.payments.setup import choose_saved, selected_consent

        original = selected_consent(flow)
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            choice = choose_saved(
                flow=flow,
                method_id=original.method_id,
                payment_accepted=True,
                cancellation_accepted=True,
            )
        flow["payment_consent"] = str(choice.pk)
        booking = submit_booking(flow)
        flow.update(stage="done", booking_id=booking.pk)
        self.store(flow)
        response = self.client.get(reverse("customer_booking_receipt"))
        self.assertContains(response, zelle_instructions())
        self.assertContains(response, "1 child")
        self.assertContains(response, "1 adult")
        self.assertContains(response, "0 babies")
        self.assertContains(response, "1 pair of socks")
        self.assertIn(zelle_instructions(), booking_confirmation(booking))
        self.assertFalse(FinancialPosting.objects.exists())

    def test_older_pending_policy_requires_acceptance_without_recovering_old_consent(self):
        flow = self.ready()
        flow["payment_setup_key"] = str(PaymentSetup.objects.get().pk)
        with (
            patch("core.payments.policy.VERSION", "NEXT-POLICY"),
            patch("core.payments.setup.VERSION", "NEXT-POLICY"),
        ):
            context = card_context(flow)
        self.assertFalse(context["card_ready"])
        self.assertEqual(context["card_status_url"], "")
        self.assertNotEqual(str(context["card_setup_key"]), str(flow.get("payment_setup_key")))
        self.assertTrue(context["card_methods"].exists())
        self.assertFalse(Booking.objects.exists())

    def test_replacement_sentence_only_when_a_reusable_card_exists(self):
        flow = self.flow()
        self.assertFalse(card_context(flow)["card_has_saved"])
        flow = self.ready()
        self.assertFalse(card_context(flow)["card_has_saved"])
        from core.payments.setup import selected_consent

        method = selected_consent(flow).method
        method.reusable = True
        method.save(update_fields=["reusable"])
        self.assertTrue(card_context(flow)["card_has_saved"])
