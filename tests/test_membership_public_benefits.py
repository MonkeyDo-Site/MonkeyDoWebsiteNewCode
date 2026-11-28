"""Private receipt actions reserve benefits, never attendance, cards or money."""

import copy
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core import membership_public_benefits as benefits
from core.communications.models import MessageDelivery
from core.membership_records import MembershipBenefitBatch
from core.models import (
    AuditEvent,
    BookingQuote,
    Customer,
    FinancialPosting,
    PaymentOperation,
)
from core.payments.comped import set_price
from core.public_booking import profile_proof, review_quote, submit_booking
from core.public_booking_views import SESSION_KEY
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


class AvailableBenefitFixtures(InitialCreditFixtures):
    def available(self, *, release=True):
        self.member(kind="unlimited")
        self.first = self.booking()
        self.flow_data = self.ready()
        self.play = submit_booking(self.flow_data)
        self.flow_data.update(stage="done", booking_id=self.play.pk)
        if release:
            self.act(self.first, dict(method="card", charge_fee=False), kind="cancellation")
        return self.play

    def accepted(self):
        return dict(
            flow=self.flow_data,
            request_key=uuid.uuid4(),
            reviewed_hash=benefits.review(flow=self.flow_data)["fingerprint"],
            confirmed=True,
        )

    def browser(self, client=None):
        client = client or self.client
        session = client.session
        session[SESSION_KEY] = self.flow_data
        session.save()
        return client


@override_settings(**SETTINGS)
class PublicBookingBenefitTests(AvailableBenefitFixtures, RuntimeRoleMixin, TestCase):
    def test_preview_is_read_only_and_confirmation_reserves_once_without_money_or_arrival(self):
        booking = self.available()
        original = booking.quotes.first()
        original_snapshot = copy.deepcopy(original.snapshot)
        flow_before = copy.deepcopy(self.flow_data)
        card_before = booking.card_agreement.consent_id, booking.card_agreement.method_id
        waiver_before = (
            booking.waiver_review.revision,
            list(booking.waiver_links.values_list("pk", flat=True)),
        )
        before = tuple(
            model.objects.count()
            for model in (
                BookingQuote,
                MembershipBenefitBatch,
                AuditEvent,
                PaymentOperation,
                FinancialPosting,
                MessageDelivery,
            )
        )
        reviewed = benefits.review(flow=self.flow_data)
        self.assertEqual(reviewed["previous"].snapshot["total"], "16.47")
        self.assertEqual(reviewed["quote"]["total"], "0.00")
        self.assertFalse(booking.membership_benefits.exists())
        self.assertEqual(
            before,
            tuple(
                model.objects.count()
                for model in (
                    BookingQuote,
                    MembershipBenefitBatch,
                    AuditEvent,
                    PaymentOperation,
                    FinancialPosting,
                    MessageDelivery,
                )
            ),
        )
        values = self.accepted()
        with self.runtime_role(), patch("core.payments.operations.Gateway") as gateway:
            saved = benefits.confirm(**values)
            self.assertEqual(benefits.confirm(**values).pk, saved.pk)
            gateway.assert_not_called()
        booking.refresh_from_db()
        original.refresh_from_db()
        self.assertEqual(original.snapshot, original_snapshot)
        self.assertEqual(booking.edit_version, 2)
        self.assertEqual(booking.attendance, "")
        self.assertFalse(booking.setup_pending)
        self.assertEqual(booking.membership_benefits.get().current.status, "reserved")
        self.assertEqual(
            (booking.card_agreement.consent_id, booking.card_agreement.method_id), card_before
        )
        self.assertEqual(
            (
                booking.waiver_review.revision,
                list(booking.waiver_links.values_list("pk", flat=True)),
            ),
            waiver_before,
        )
        self.assertEqual(self.flow_data, flow_before)
        self.assertEqual(
            before[-3:],
            tuple(
                model.objects.count()
                for model in (PaymentOperation, FinancialPosting, MessageDelivery)
            ),
        )
        audit = AuditEvent.objects.get(action="booking.membership_benefit_applied")
        self.assertIsNone(audit.actor_id)
        self.assertEqual(audit.changes["amount_due"], {"before": "$16.47", "after": "$0.00"})

    def test_no_available_benefit_or_false_confirmation_cannot_change_the_booking(self):
        booking = self.available(release=False)
        with self.assertRaisesMessage(ValidationError, "No additional"):
            benefits.review(flow=self.flow_data)
        self.act(self.first, dict(method="card", charge_fee=False), kind="cancellation")
        values = self.accepted()
        for value in (False, "yes", None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                benefits.confirm(**(values | {"confirmed": value}))
        self.assertEqual(booking.quotes.count(), 1)
        self.assertFalse(booking.membership_benefits.exists())

    def test_wrong_private_flow_profile_stage_and_expiry_are_rejected(self):
        self.available()
        other = Customer.objects.create(
            last_name="Other", phone="2025550187", email="other@example.invalid"
        )
        changes = [
            {"booking_id": self.first.pk},
            {"key": str(uuid.uuid4())},
            {"stage": "review"},
            {"workflow": "legacy_test"},
            {"staff_actor": self.staff.pk},
            {"expires": (timezone.now() - timedelta(seconds=1)).timestamp()},
            {"proof": "invalid"},
            {"proof": profile_proof(other, self.flow_data["key"])},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                benefits.review(flow=self.flow_data | change)
        self.assertEqual(self.play.quotes.count(), 1)
        self.assertFalse(self.play.membership_benefits.exists())

    def test_changed_customer_contact_invalidates_old_profile_proof_without_extending_deadline(
        self,
    ):
        self.available()
        expires = self.flow_data["expires"]
        self.customer.revision += 1
        self.customer.save(update_fields=["revision"])
        with self.assertRaises(ValidationError):
            benefits.confirm(
                flow=self.flow_data, request_key=uuid.uuid4(), reviewed_hash="old", confirmed=True
            )
        self.assertEqual(self.flow_data["expires"], expires)
        self.assertEqual(self.play.quotes.count(), 1)

    def test_new_customer_completed_flow_can_apply_a_later_purchased_membership(self):
        original_flow = self.flow
        with patch.object(self, "flow", side_effect=lambda: original_flow(new=True)):
            flow = self.ready()
        flow["details"]["adults"] = 3
        flow["quote"] = review_quote(flow, flow["details"])
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(flow, nonce="nonce-FreshAdultCount")
        flow["payment_consent"] = str(setup.consent_id)
        booking = submit_booking(flow)
        flow.update(stage="done", booking_id=booking.pk)
        self.customer = booking.customer
        self.member(kind="unlimited")
        reviewed = benefits.review(flow=flow)
        saved = benefits.confirm(
            flow=flow,
            request_key=uuid.uuid4(),
            reviewed_hash=reviewed["fingerprint"],
            confirmed=True,
        )
        self.assertEqual(saved.snapshot["total"], "5.49")
        self.assertFalse(any("cancelled" in row["label"] for row in reviewed["adjustment"]["rows"]))
        self.assertEqual(
            reviewed["adjustment"]["rows"][0]["label"], "Membership benefit adjustment"
        )
        self.assertEqual(reviewed["adjustment"]["rows"][0]["delta"], -20)
        self.assertEqual(booking.membership_benefits.get().current.status, "reserved")
        self.customer.revision += 1
        self.customer.save(update_fields=["revision"])
        with self.assertRaises(ValidationError):
            benefits.owned_booking(flow)

    def test_competing_booking_takes_benefit_then_old_review_cannot_reprice(self):
        booking = self.available()
        values = self.accepted()
        third = self.booking()
        self.assertEqual(third.quotes.first().snapshot["total"], "0.00")
        with self.assertRaises(ValidationError):
            benefits.confirm(**values)
        self.assertEqual(booking.quotes.first().snapshot["total"], "16.47")
        self.assertEqual(booking.quotes.count(), 1)

    def test_owner_price_and_attendance_changes_cannot_be_bypassed(self):
        booking = self.available()
        values = self.accepted()
        set_price(
            actor=self.owner,
            booking_id=booking.pk,
            version=1,
            comped=False,
            special_admissions="5.00",
        )
        with self.assertRaises(ValidationError):
            benefits.confirm(**values)
        self.assertFalse(booking.membership_benefits.exists())

    def test_started_arrival_blocks_later_customer_price_change(self):
        booking = self.available()
        values = self.accepted()
        self.act(booking, self.arrival_inputs(booking))
        count = booking.quotes.count()
        with self.assertRaises(ValidationError):
            benefits.confirm(**values)
        self.assertEqual(booking.quotes.count(), count)
        self.assertEqual(booking.quotes.first().snapshot["total"], "16.47")

    def test_advance_zelle_changes_require_review_and_never_become_another_receipt_or_refund(self):
        from core.booking_management import edit_test_booking
        from core.payments.zelle import facts, record_receipt

        booking = self.available()
        edit_test_booking(
            actor=self.staff,
            booking_id=booking.pk,
            version=booking.edit_version,
            children=booking.children,
            adults=booking.adults,
            babies=booking.babies,
            socks=booking.socks,
            expected_method="zelle",
            payment_reviewed=True,
        )
        booking.refresh_from_db()
        original_quotes = booking.quotes.count()
        values = self.accepted()
        record_receipt(
            actor=self.staff,
            booking_id=booking.pk,
            request_key=uuid.uuid4(),
            value="20.00",
            sender_name="Fictional parent",
            verified=True,
        )
        with self.assertRaisesMessage(ValidationError, "changed"):
            benefits.confirm(**values)
        self.assertEqual(booking.quotes.count(), original_quotes)
        self.browser()
        page = self.client.get(reverse("customer_booking_receipt"))
        self.assertContains(page, "Zelle already received: $20.00")
        self.assertContains(page, "Booking price estimate")
        self.assertNotContains(page, "Please send payment by Zelle")
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        saved = benefits.confirm(**self.accepted())
        self.assertEqual(saved.snapshot["total"], "0.00")
        self.assertEqual(facts(booking)["available"], 20)
        self.assertEqual(
            before, (PaymentOperation.objects.count(), FinancialPosting.objects.count())
        )

    def test_late_reservation_failure_rolls_back_price_revision_and_audit(self):
        booking = self.available()
        values = self.accepted()
        before = BookingQuote.objects.count(), AuditEvent.objects.count()
        with (
            patch(
                "core.membership_public_benefits.reserve",
                side_effect=ValidationError("late reservation fault"),
            ),
            self.assertRaises(ValidationError),
        ):
            benefits.confirm(**values)
        booking.refresh_from_db()
        self.assertEqual(booking.edit_version, 1)
        self.assertEqual(before, (BookingQuote.objects.count(), AuditEvent.objects.count()))
        self.assertFalse(booking.membership_benefits.exists())

    def test_existing_reservation_key_cannot_be_retargeted_and_quote_is_immutable(self):
        self.available()
        values = self.accepted()
        other = MembershipBenefitBatch.objects.filter(booking=self.first, action="reserved").get()
        with self.assertRaises(ValidationError):
            benefits.confirm(**(values | {"request_key": other.pk}))
        saved = benefits.confirm(**values)
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE core_bookingquote SET snapshot='{}' WHERE id=%s", [saved.pk])
        with self.assertRaises(ValidationError):
            benefits.confirm(**(values | {"reviewed_hash": "different"}))

    def test_native_receipt_review_csrf_confirmation_and_history_are_compact_and_scoped(self):
        booking = self.available()
        client = self.browser(Client(enforce_csrf_checks=True))
        url = reverse("customer_booking_receipt")
        page = client.get(url)
        self.assertContains(page, "Apply available Unlimited benefit")
        self.assertContains(page, "$16.47")
        self.assertContains(page, "Confirm updated price — $0.00")
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(booking.quotes.count(), 1)
        form = page.context["benefit_form"]
        values = {
            "request_key": str(form.initial["request_key"]),
            "reviewed_hash": form.initial["reviewed_hash"],
            "confirmed": "1",
            "children": "30",
            "expected_method": "cash",
        }
        self.assertEqual(client.post(url, values).status_code, 403)
        values["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
        response = client.post(url, values)
        self.assertEqual(response.status_code, 302)
        result = client.get(response.url)
        self.assertContains(result, "Your available Unlimited benefit has been applied")
        self.assertContains(result, "No admission payment is due at arrival")
        self.assertContains(result, "Original booking total")
        self.assertContains(result, "Membership benefit adjustment")
        self.assertNotContains(result, "Your pending test reservation is saved")
        self.assertNotContains(result, "data-available-membership-benefit")
        self.assertEqual(client.post(url, values).status_code, 302)
        booking.refresh_from_db()
        self.assertEqual((booking.children, booking.expected_method), (1, "card"))
        self.assertEqual(booking.quotes.count(), 2)
        self.assertEqual(Client().get(url).status_code, 404)
        self.client.force_login(self.staff)
        detail = self.client.get(reverse("booking_detail", args=[booking.pk]))
        self.assertContains(detail, "Available Unlimited benefit applied")
        self.assertContains(detail, "Booking price estimate")

    def test_stale_or_unconfirmed_http_request_requires_fresh_review(self):
        booking = self.available()
        client = self.browser()
        url = reverse("customer_booking_receipt")
        form = client.get(url).context["benefit_form"]
        stale = {
            "request_key": str(form.initial["request_key"]),
            "reviewed_hash": "old",
            "confirmed": "1",
        }
        result = client.post(url, stale)
        self.assertContains(result, "Review the current price")
        self.assertNotEqual(result.context["benefit_form"].initial["reviewed_hash"], "old")
        result = client.post(url, stale | {"confirmed": ""})
        self.assertContains(result, "Review the updated price and confirm")
        self.assertEqual(booking.quotes.count(), 1)

    def test_feature_and_recovery_flags_keep_receipt_read_only(self):
        self.available()
        client = self.browser()
        url = reverse("customer_booking_receipt")
        values = self.accepted()
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertNotContains(client.get(url), "data-available-membership-benefit")
            self.assertEqual(client.post(url, {}).status_code, 404)
            with self.assertRaises(ValidationError):
                benefits.confirm(**values)
        with override_settings(RECOVERY_HOLD=True), self.assertRaises(ValidationError):
            benefits.confirm(**values)
        self.assertEqual(self.play.quotes.count(), 1)
