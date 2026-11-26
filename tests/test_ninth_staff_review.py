"""Ninth batch: truthful previews, recoverable arrival drafts and audited staff decisions."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.booking_comments import save as save_comment
from core.booking_forms import PricingPolicyForm
from core.models import (
    AuditEvent,
    Booking,
    BookingCheckout,
    CustomerComment,
    FinancialPosting,
    PaymentOperation,
    PricingPolicy,
)
from core.payments.checkout import preview
from core.payments.invoices import received
from core.payments.staff_setup import session_key
from tests import test_booking_checkout as fixtures
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="synthetic",
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_synthetic",
    STORAGES=STORAGES,
)
class NinthStaffTests(TestCase):
    setUp = fixtures.CheckoutTests.setUp
    create = fixtures.CheckoutTests.create
    flow = fixtures.CheckoutTests.flow
    card = fixtures.CheckoutTests.card
    save_card = fixtures.CheckoutTests.save_card
    gateway = fixtures.CheckoutTests.gateway
    ready = fixtures.CheckoutTests.ready
    booking = fixtures.CheckoutTests.booking
    arrival_inputs = fixtures.CheckoutTests.arrival_inputs
    act = fixtures.CheckoutTests.act

    def page(self, booking):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("booking_arrival", args=[booking.pk]))
        self.assertEqual(response.status_code, 200)
        self.draft = response.context["arrival_draft"]
        return {
            "arrival_draft": self.draft,
            "request_key": str(response.context["form"]["request_key"].value()),
            "version": booking.edit_version,
            "children": booking.children,
            "adults": booking.adults,
            "babies": booking.babies,
            "socks": booking.socks,
            "method": "cash",
            "waiver_confirmed": "",
            "reviewed_hash": "",
        }

    def live(self, booking, values):
        return self.client.post(
            reverse("booking_arrival", args=[booking.pk]), values, HTTP_ACCEPT="application/json"
        )

    def test_live_price_updates_before_waiver_answer_without_writes(self):
        b = self.booking()
        values = self.page(b)
        response = self.live(b, values | {"children": 3})
        self.assertEqual(response.status_code, 200)
        self.assertIn("3 × $15.00", response.json()["html"])
        self.assertTrue(response.json()["hash"])
        self.assertFalse(response.json()["can_confirm"])
        self.assertTrue(response.json()["waiver"]["mismatch"])
        b.refresh_from_db()
        self.assertEqual(b.children, 1)
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(BookingCheckout.objects.exists())

    def test_rejected_initial_capacity_renders_validation_instead_of_500(self):
        b = self.booking()
        b.session.child_capacity = 0
        b.session.supervised_capacity = 0
        b.session.save()
        self.page(b)
        response = self.client.get(reverse("booking_arrival", args=[b.pk]))
        self.assertContains(response, "Actual attendees exceed the session capacity")
        self.assertFalse(PaymentOperation.objects.exists())

    def test_invalid_count_cannot_crash_preview_or_restore(self):
        b = self.booking()
        values = self.page(b)
        response = self.live(b, values | {"children": "not a number"})
        self.assertEqual(response.status_code, 400)
        response = self.client.get(reverse("booking_arrival", args=[b.pk]), {"draft": self.draft})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_price_updates_without_gift_verification_but_confirmation_stays_disabled(self):
        b = self.booking()
        values = self.page(b)
        response = self.live(b, values | {"method": "gift_card", "waiver_confirmed": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["can_confirm"])
        response = self.live(
            b,
            values | {"method": "gift_card", "waiver_confirmed": "yes", "gift_card_verified": "on"},
        )
        self.assertTrue(response.json()["can_confirm"])

    def test_specific_required_waiver_error_on_final_submission(self):
        b = self.booking()
        values = self.page(b)
        response = self.live(b, values | {"confirm_review": "1"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("The waiver confirmation field is required.", str(response.json()))
        self.assertFalse(PaymentOperation.objects.exists())

    def test_waiver_count_requires_explicit_acknowledgment_and_records_it(self):
        b = self.booking()
        data = self.arrival_inputs(b, children=3, method="cash")
        with self.assertRaisesMessage(ValidationError, "Do you want to go ahead?"):
            preview(actor=self.staff, booking_id=b.pk, kind="arrival", data=data)
        data["waiver_mismatch_accepted"] = True
        checkout = self.act(b, data)
        self.assertTrue(checkout.details["waiver_mismatch_accepted"])
        self.assertEqual(checkout.details["waiver_review"]["recorded_minors"], 1)
        self.assertEqual(checkout.details["waiver_review"]["attending_minors"], 3)
        event = AuditEvent.objects.get(action="booking.arrival_confirmed")
        self.assertEqual(event.actor, self.staff)
        self.assertTrue(event.changes["waiver_mismatch_accepted"])

    def test_acknowledgment_does_not_replace_staff_yes(self):
        b = self.booking()
        data = self.arrival_inputs(b, waiver_confirmed=False, waiver_mismatch_accepted=True)
        with self.assertRaisesMessage(ValidationError, "waiver confirmation field"):
            self.act(b, data)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_draft_round_trip_preserves_counts_split_and_waiver_selection(self):
        b = self.booking()
        values = self.page(b)
        posted = values | {
            "children": 3,
            "method": "split",
            "cash_amount": "12.34",
            "waiver_confirmed": "yes",
            "waiver_mismatch_accepted": "yes",
            "continue_to": "card",
        }
        response = self.client.post(reverse("booking_arrival", args=[b.pk]), posted)
        self.assertRedirects(
            response,
            reverse("booking_card_change", args=[b.pk]) + "?draft=" + self.draft,
            fetch_redirect_response=False,
        )
        response = self.client.get(reverse("booking_arrival", args=[b.pk]), {"draft": self.draft})
        form = response.context["form"]
        self.assertEqual(form.initial["children"], "3")
        self.assertEqual(form.initial["cash_amount"], "12.34")
        self.assertEqual(form.initial["waiver_confirmed"], "yes")
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertTrue(response.context["arrival_paper_form"].initial["request_key"])

    def test_draft_cannot_be_used_for_another_booking_or_changed_version(self):
        b = self.booking()
        values = self.page(b)
        other = Booking.objects.create(
            customer=b.customer,
            session=b.session,
            workflow="integrated_v1",
            setup_pending=False,
            children=1,
            adults=1,
        )
        response = self.live(other, values)
        self.assertEqual(response.status_code, 409)
        b.edit_version += 1
        b.save()
        response = self.live(b, values)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_multiple_noncard_tenders_cover_total_without_card_operation(self):
        b = self.booking()
        data = self.arrival_inputs(
            b, method="split", split={"gift_card": "10.00", "cash": "5.99"}, gift_card_verified=True
        )
        checkout = self.act(b, data)
        self.assertEqual(checkout.sale.processing_fee, Decimal("0.00"))
        self.assertEqual(
            set(checkout.sale.operations.values_list("tender", flat=True)), {"cash", "gift_card"}
        )
        self.assertEqual(received(checkout.sale), Decimal("15.99"))

    def test_partial_split_has_one_card_balance_and_excess_is_rejected(self):
        b = self.booking()
        data = self.arrival_inputs(
            b, method="split", split={"gift_card": "10.00"}, gift_card_verified=True
        )
        reviewed = preview(actor=self.staff, booking_id=b.pk, kind="arrival", data=data)
        self.assertEqual([part["tender"] for part in reviewed[3]], ["gift_card", "card"])
        with self.assertRaises(ValidationError):
            preview(
                actor=self.staff,
                booking_id=b.pk,
                kind="arrival",
                data=data | {"split": {"cash": "10.00", "check": "10.00"}},
            )
        self.assertFalse(PaymentOperation.objects.exists())

    def test_overallocation_returns_current_noncard_total_with_no_confirm_hash(self):
        b = self.booking()
        values = self.page(b)
        response = self.live(
            b, values | {"method": "split", "cash_amount": "10.00", "check_amount": "10.00"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["noncard_total"], "15.99")
        self.assertEqual(response.json()["hash"], "")
        self.assertFalse(PaymentOperation.objects.exists())

    def test_status_get_never_dispatches_and_does_not_report_pending_as_received(self):
        b = self.booking()
        checkout = self.act(b, self.arrival_inputs(b))
        self.client.force_login(self.staff)
        url = reverse("booking_arrival_status", args=[b.pk, checkout.pk])
        with patch("core.payments.gateway.Gateway.charge") as charge:
            for _ in range(2):
                response = self.client.get(url)
                self.assertEqual(response.json()["state"], "processing")
                self.assertEqual(response.json()["received"], "0.00")
            charge.assert_not_called()
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertFalse(FinancialPosting.objects.exists())

    def test_final_ajax_is_single_explicit_action_and_has_status_url(self):
        b = self.booking()
        values = self.page(b) | {"waiver_confirmed": "yes"}
        reviewed = self.live(b, values).json()
        response = self.live(b, values | {"reviewed_hash": reviewed["hash"], "confirm_review": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["confirmed"])
        self.assertIn("/arrival/status/", response.json()["status_url"])
        self.assertEqual(BookingCheckout.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        b.refresh_from_db()
        self.assertEqual(b.attendance, "arrived")

    def test_unchanged_percentage_fields_save_and_significant_extra_precision_fails(self):
        policy = PricingPolicy.objects.first()
        values = {name: str(getattr(policy, name)) for name in PricingPolicyForm.Meta.fields}
        form = PricingPolicyForm(
            values | {"tax_percent": "6.6000", "fee_percent": "3.0000"}, policy=policy
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.tax_rate, Decimal(".066"))
        self.assertFalse(
            PricingPolicyForm(
                values | {"tax_percent": "6.6001", "fee_percent": "3"}, policy=policy
            ).is_valid()
        )

    def test_public_prices_follow_new_policy_but_existing_quote_stays_original(self):
        b = self.booking()
        original = b.quotes.first().snapshot
        PricingPolicy.objects.create(
            child_price="17",
            extra_adult_price="7",
            supervised_price="21.50",
            minimum_admission="17",
            sock_price="2.50",
        )
        response = self.client.get(reverse("about"))
        self.assertContains(response, "$17 per child")
        self.assertContains(response, "$7 each")
        self.assertEqual(b.quotes.first().snapshot, original)
        from core.payments.policy import displayed_cancellation

        self.assertIn("$17 or $21.5", displayed_cancellation()[0])
        self.assertIn("$15 or $18.99", displayed_cancellation({"staff_booking": b.pk})[0])

    def test_booking_comment_scope_history_and_stale_edit(self):
        b = self.booking()
        comment = save_comment(
            actor=self.owner, booking_id=b.pk, body="Bring an extra towel. Call 732-555-0147."
        )
        self.assertEqual(comment.booking, b)
        self.assertEqual(comment.search_digits, "7325550147")
        save_comment(
            actor=self.owner,
            booking_id=b.pk,
            comment_id=comment.pk,
            body="Updated towel note",
            revision=1,
        )
        with self.assertRaises(ValidationError):
            save_comment(
                actor=self.owner, booking_id=b.pk, comment_id=comment.pk, body="Stale", revision=1
            )
        self.assertEqual(
            AuditEvent.objects.filter(action__startswith="booking.comment_").count(), 2
        )
        self.assertEqual(CustomerComment.objects.get(pk=comment.pk).body, "Updated towel note")

    def test_booking_comments_are_searchable_and_not_customer_general_comments(self):
        b = self.booking()
        save_comment(actor=self.owner, booking_id=b.pk, body="UniqueBookingNote 732-555-0123")
        verified_owner_login(self.client, self.owner)
        response = self.client.get(reverse("bookings"), {"q": "UniqueBookingNote"})
        self.assertContains(response, b.customer.last_name)
        response = self.client.get(
            reverse("booking_detail", args=[b.pk]), {"comment_q": "7325550123"}
        )
        self.assertContains(response, "UniqueBookingNote")
        response = self.client.get(reverse("customer_detail", args=[b.customer_id]))
        self.assertNotContains(response, "UniqueBookingNote")

    def test_customer_comment_endpoint_cannot_edit_booking_comment(self):
        b = self.booking()
        comment = save_comment(actor=self.owner, booking_id=b.pk, body="Booking only")
        verified_owner_login(self.client, self.owner)
        response = self.client.get(reverse("comment_edit", args=[b.customer_id, comment.pk]))
        self.assertEqual(response.status_code, 404)

    def test_staff_replacement_requires_yes_no_and_returns_to_same_draft(self):
        from core.payments.policy import VERSION

        b = self.booking()
        values = self.page(b) | {"children": 4, "waiver_confirmed": "yes", "continue_to": "card"}
        self.client.post(reverse("booking_arrival", args=[b.pk]), values)
        url = reverse("booking_card_change", args=[b.pk]) + "?draft=" + self.draft
        response = self.client.get(url)
        self.assertContains(response, "Save and use this card")
        self.assertNotContains(response, "Use this reviewed card")
        flow = self.client.session[session_key(b.pk)]
        payload = {
            "wizard_key": flow["key"],
            "wizard_stage": flow["stage"],
            "policy_version": VERSION,
            "request_key": str(uuid.uuid4()),
            "nonce": "nonce-NinthCard",
            "expiry_month": 12,
            "expiry_year": 2035,
            "agree_payment": True,
            "agree_cancellation": True,
        }
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            gateway.return_value.save_card.return_value = {"id": 124}
            gateway.return_value.method.return_value = self.card() | {"id": 124, "last4": "4321"}
            response = self.client.post(
                reverse("staff_card_setup", args=[b.pk]), payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 400)
            gateway.return_value.save_card.assert_not_called()
            response = self.client.post(
                reverse("staff_card_setup", args=[b.pk]),
                payload | {"retention_choice": "no"},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
        response = self.client.post(
            url,
            {
                "wizard_key": flow["key"],
                "payment_consent": response.json()["consent_id"],
                "confirm": "1",
            },
        )
        self.assertRedirects(
            response,
            reverse("booking_arrival", args=[b.pk]) + "?draft=" + self.draft,
            fetch_redirect_response=False,
        )
        b.refresh_from_db()
        self.assertEqual(b.card_agreement.method.last_four, "4321")
        self.assertEqual(b.attendance, "")
        self.assertFalse(PaymentOperation.objects.exists())

    def test_staff_waiver_returns_to_preserved_arrival_without_a_public_completion_page(self):
        from tests.test_waivers import MemoryEvidence

        b = self.booking()
        values = self.page(b) | {"children": 4, "waiver_confirmed": "yes", "continue_to": "waiver"}
        response = self.client.post(reverse("booking_arrival", args=[b.pk]), values)
        url = response.url
        self.assertIn("/waiver/sign/", url)
        page = self.client.get(url)
        initial = page.context["form"].initial
        payload = {
            **initial,
            "signer_name": "Second Parent",
            "relationship": "Parent",
            "minors": "Additional Child",
            "adult_accepted": "on",
            "waiver_accepted": "on",
            "electronic_accepted": "on",
        }
        with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
            response = self.client.post(url, payload)
        self.assertRedirects(
            response,
            reverse("booking_arrival", args=[b.pk]) + "?draft=" + self.draft,
            fetch_redirect_response=False,
        )
        restored = self.client.get(response.url)
        self.assertEqual(restored.context["form"].initial["children"], "4")
        self.assertContains(restored, "Additional Child")
        self.assertFalse(PaymentOperation.objects.exists())

    def test_comment_permission_is_required_even_when_booking_is_visible(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission

        b = self.booking()
        comment = save_comment(actor=self.owner, booking_id=b.pk, body="PrivateBookingComment")
        limited = get_user_model().objects.create_user(username="limited-comments", is_staff=True)
        limited.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core", codename__in=["view_booking", "view_customer"]
            )
        )
        with self.assertRaises(PermissionDenied):
            save_comment(actor=limited, booking_id=b.pk, body="Not permitted")
        self.client.force_login(limited)
        response = self.client.get(reverse("booking_detail", args=[b.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "PrivateBookingComment")
        self.assertEqual(CustomerComment.objects.get(pk=comment.pk).body, "PrivateBookingComment")


class NinthMinorNameTests(SimpleTestCase):
    def test_electronic_and_paper_waivers_reject_blank_minor_names(self):
        from core.waivers.forms import NamedPaperWaiverForm, SignatureForm

        for form_type in (SignatureForm, NamedPaperWaiverForm):
            for relationship in ("", "Parent", "Legal guardian"):
                form = form_type(
                    {
                        "request_key": uuid.uuid4(),
                        "version": "review",
                        "text_hash": "a" * 64,
                        "signed_on": "2026-11-25",
                        "paper_signed": True,
                        "signer_name": "Test Parent",
                        "relationship": relationship,
                        "minors": "   ",
                        "adult_accepted": True,
                        "waiver_accepted": True,
                        "electronic_accepted": True,
                    }
                )
                self.assertFalse(form.is_valid())
                self.assertIn("minors", form.errors)

    def test_parent_first_names_and_guardian_full_names_remain_distinct(self):
        from core.waivers.forms import SignatureForm

        values = {
            "request_key": uuid.uuid4(),
            "version": "review",
            "text_hash": "a" * 64,
            "signer_name": "Test Parent",
            "relationship": "Parent",
            "minors": "Yanky\nYoely",
            "adult_accepted": True,
            "waiver_accepted": True,
            "electronic_accepted": True,
        }
        self.assertTrue(SignatureForm(values).is_valid())
        self.assertFalse(SignatureForm(values | {"relationship": "Legal guardian"}).is_valid())
        self.assertTrue(
            SignatureForm(
                values
                | {"relationship": "Legal guardian", "minors": "Yanky Greenfeld\nYoely Greenfeld"}
            ).is_valid()
        )
