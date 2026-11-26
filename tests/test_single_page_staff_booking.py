"""A private creation draft becomes one complete booking, only on final confirmation."""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.booking_management import create_test_booking
from core.models import (
    Booking,
    BookingCapacityHold,
    Customer,
    FinancialPosting,
    MessageDelivery,
    PaymentSetup,
    PricingPolicy,
)
from core.payments.policy import VERSION
from core.payments.staff_create import KEY
from core.waivers.models import PaperWaiver
from tests import test_payment_setup as fixtures
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(
    STORAGES=STORAGES,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake_sandbox",
)
class SinglePageStaffBookingTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.CardSetupTests.setUp
    create = fixtures.CardSetupTests.create
    card = fixtures.CardSetupTests.card
    gateway = fixtures.CardSetupTests.gateway

    def draft(self, owner=False, session=None):
        if owner:
            verified_owner_login(self.client, self.owner)
        else:
            self.client.force_login(self.staff)
        self.play = session or self.create()
        self.url = reverse("booking_create")
        response = self.client.get(
            self.url, {"customer": self.customer.pk, "session": self.play.pk}
        )
        self.assertEqual(response.status_code, 200)
        flow = response.context["flow"]
        self.key = flow["key"]
        self.values = {
            "draft": self.key,
            "creation_key": self.key,
            "wizard_key": self.key,
            "wizard_stage": "review",
            "customer": self.customer.pk,
            "session": self.play.pk,
            "session_date": self.play.starts_at.date(),
            "children": 1,
            "adults": 1,
            "babies": 0,
            "socks": 0,
            "expected_method": "cash",
            "price_mode": "standard",
            "waiver_type": "multiple",
            "confirm": "on",
        }
        return response

    def post(self, intent="preview", **changes):
        self.values.update(changes)
        return self.client.post(self.url, self.values | {"intent": intent})

    def save_card(self):
        response = self.post("prepare")
        self.assertEqual(response.status_code, 200, response.content)
        self.values["reviewed_hash"] = response.json()["reviewed_hash"]
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            response = self.client.post(
                reverse("staff_create_card", args=[self.key]),
                {
                    "wizard_key": self.key,
                    "wizard_stage": "review",
                    "policy_version": VERSION,
                    "request_key": str(uuid.uuid4()),
                    "nonce": "nonce-Synthetic",
                    "expiry_month": 12,
                    "expiry_year": 2035,
                    "retention_choice": "no",
                    "agree_payment": True,
                    "agree_cancellation": True,
                },
                content_type="application/json",
            )
            gateway.return_value.charge.assert_not_called()
            gateway.return_value.verify.assert_not_called()
        self.assertEqual(response.status_code, 200, response.content)
        self.values["payment_consent"] = response.json()["consent_id"]

    def test_page_retains_all_create_controls_and_initial_capacity_counts(self):
        response = self.draft(owner=True)
        for text in (
            "Visit payment details",
            "Custom price or complimentary",
            "Waiver details",
            "Record signed paper waiver",
            "Payment details",
            "Confirm booking",
            "Close this entire session to additional reservations",
            "override session capacity",
            "Children: 35 of 35 available",
            "Total: 50 of 50 available",
            "Supervised: 3 of 3 available",
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, "Save test reservation")
        self.assertNotContains(response, "data-save-card")
        self.assertFalse(Booking.objects.exists())

    def test_counts_reserve_places_and_update_estimate_without_confirming_booking(self):
        self.draft()
        first = self.post(children=3, socks=1).json()
        self.assertTrue(first["valid"])
        self.assertIn("$45.00", first["html"])
        self.assertIn("32 of 35", first["capacity"])
        self.assertEqual(BookingCapacityHold.objects.get().children, 3)
        self.assertTrue(first["hold"]["active"])
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(MessageDelivery.objects.exists())
        response = self.post(expected_method="zelle")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.post("prepare").status_code, 400)
        self.assertFalse(Booking.objects.exists())

    def test_card_and_final_confirmation_create_once_without_collecting_money(self):
        self.draft(session=self.create(child_capacity=1, supervised_capacity=1))
        self.save_card()
        self.assertFalse(Booking.objects.exists())
        response = self.post("confirm")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["confirmed"])
        booking = Booking.objects.get()
        self.assertFalse(booking.setup_pending)
        self.assertEqual(booking.card_agreement.method.customer, self.customer)
        self.assertEqual(MessageDelivery.objects.count(), 1)
        self.assertTrue(MessageDelivery.objects.get().unsigned_waiver)
        # The final slot is now occupied, but retrying the same final request is safe.
        self.assertEqual(self.post("confirm").json()["url"], response.json()["url"])
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.count(), 1)
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertFalse(BookingCapacityHold.objects.exists())

    def test_comped_skips_card_but_still_confirms_booking_and_closes_session(self):
        self.draft(owner=True)
        response = self.post("prepare", price_mode="comped", close_session="on", socks=2)
        self.assertEqual(response.status_code, 200, response.content)
        self.values["reviewed_hash"] = response.json()["reviewed_hash"]
        self.assertFalse(self.play.reservation_blocks.exists())
        with patch("core.payments.setup.Gateway") as gateway:
            response = self.post("confirm")
            gateway.assert_not_called()
        self.assertEqual(response.status_code, 200, response.content)
        booking = Booking.objects.get()
        self.assertEqual(booking.quotes.first().snapshot["total"], "0.00")
        self.assertTrue(booking.charge_state.comped)
        self.assertTrue(booking.session_blocks.filter(active=True).exists())
        self.assertFalse(hasattr(booking, "card_agreement"))
        self.assertFalse(PaymentSetup.objects.exists())

    def test_custom_admissions_keep_socks_separate_and_save_reviewed_total(self):
        self.draft(owner=True)
        self.values.update(price_mode="special", custom_admissions="20.00", socks=2)
        self.save_card()
        response = self.post("confirm")
        self.assertEqual(response.status_code, 200, response.content)
        booking = Booking.objects.get()
        lines = booking.quotes.first().snapshot["lines"]
        self.assertEqual(lines[0]["amount"], "20.00")
        self.assertEqual(lines[1]["amount"], "3.98")
        self.assertEqual(str(booking.charge_state.special_subtotal), "20.00")

    def test_nonowner_cannot_forge_complimentary_price_or_close_session(self):
        self.draft()
        self.assertEqual(self.post(price_mode="comped").status_code, 403)
        response = self.post(
            "prepare", price_mode="standard", close_session="on", override_capacity="on"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.save_card()
        self.assertEqual(self.post("confirm").status_code, 200)
        self.assertFalse(Booking.objects.get().session_blocks.exists())

    def test_capacity_rechecked_after_card_save_keeps_draft_without_booking(self):
        self.draft(session=self.create(child_capacity=1, supervised_capacity=1))
        self.save_card()
        # Simulate the owner taking a longer call, then another booking taking
        # the released places before the original call is confirmed.
        hold = BookingCapacityHold.objects.get(pk=self.key)
        BookingCapacityHold.objects.filter(pk=hold.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        create_test_booking(
            actor=self.staff,
            customer=self.customer,
            session_id=self.play.pk,
            children=1,
            adults=1,
            creation_key=uuid.uuid4(),
        )
        response = self.post("confirm")
        self.assertEqual(response.status_code, 400)
        self.assertIn("capacity", response.json()["error"])
        self.assertFalse(Booking.objects.filter(creation_key=self.key).exists())
        flow = self.client.session[KEY][self.key]
        self.assertEqual(flow["payment_consent"], self.values["payment_consent"])
        self.assertEqual(flow["fields"]["children"], "1")

    def test_hold_expires_after_thirty_minutes_without_background_renewal(self):
        from core.availability import occupancy

        self.draft()
        self.post(children=3, adults=2)
        hold = BookingCapacityHold.objects.get(pk=self.key)
        start = timezone.now()
        self.assertEqual(hold.expires_at, start + timedelta(minutes=30))
        with patch("django.utils.timezone.now", return_value=start + timedelta(minutes=29)):
            response = self.client.get(self.url, {"draft": self.key, "hold_status": "1"})
            self.assertTrue(response.json()["hold"]["active"])
            self.assertEqual(occupancy(self.play), (3, 2, 0))
            self.post(expected_method="check")
            hold.refresh_from_db()
            self.assertEqual(hold.expires_at, start + timedelta(minutes=30))
        with patch("django.utils.timezone.now", return_value=start + timedelta(minutes=31)):
            self.assertEqual(occupancy(self.play), (0, 0, 0))
            self.assertFalse(
                self.client.get(self.url, {"draft": self.key, "hold_status": "1"}).json()["hold"][
                    "active"
                ]
            )
            self.assertFalse(self.post().json()["hold"]["active"])
            self.assertTrue(self.post("renew").json()["hold"]["active"])
            self.assertEqual(occupancy(self.play), (3, 2, 0))

    def test_counts_and_session_change_replace_hold_instead_of_accumulating_it(self):
        from core.availability import occupancy

        self.draft()
        self.post(children=3)
        self.post(children=2)
        self.assertEqual(occupancy(self.play), (2, 1, 0))
        next_session = self.create(
            starts_at=self.play.starts_at + timedelta(hours=3),
            ends_at=self.play.ends_at + timedelta(hours=3),
        )
        self.post(session=next_session.pk)
        self.assertEqual(occupancy(self.play), (0, 0, 0))
        self.assertEqual(occupancy(next_session), (2, 1, 0))
        self.assertEqual(BookingCapacityHold.objects.count(), 1)

    def test_temporary_hold_blocks_competing_booking_until_expiry(self):
        from django.core.exceptions import ValidationError

        self.draft(session=self.create(child_capacity=1, supervised_capacity=1))
        self.post()
        values = dict(
            actor=self.staff,
            customer=self.customer,
            session_id=self.play.pk,
            children=1,
            adults=1,
            creation_key=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            create_test_booking(**values)
        BookingCapacityHold.objects.filter(pk=self.key).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertIsNotNone(create_test_booking(**values))

    def test_confirmed_booking_keeps_capacity_after_the_temporary_window(self):
        from core.availability import occupancy

        self.draft()
        self.save_card()
        self.post("confirm")
        start = timezone.now()
        with patch("django.utils.timezone.now", return_value=start + timedelta(minutes=31)):
            self.assertEqual(occupancy(self.play), (1, 1, 0))

    def test_invalid_waiver_rolls_back_confirmation_without_losing_reserved_places(self):
        from core.availability import occupancy

        self.draft()
        self.save_card()
        response = self.post("confirm", covered="on")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(occupancy(self.play), (1, 1, 0))
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(MessageDelivery.objects.exists())

    def test_owner_capacity_override_is_preserved(self):
        self.draft(owner=True, session=self.create(child_capacity=1, supervised_capacity=1))
        self.values.update(children=2, override_capacity="on")
        self.save_card()
        self.assertEqual(self.post("confirm").status_code, 200)
        self.assertEqual(Booking.objects.get().children, 2)

    def test_price_change_requires_new_review_before_final_commit(self):
        self.draft()
        self.save_card()
        PricingPolicy.objects.create(child_price="16.00")
        response = self.post("confirm")
        self.assertEqual(response.status_code, 400)
        self.assertIn("price changed", response.json()["error"])
        self.assertFalse(Booking.objects.exists())

    def test_named_paper_waiver_is_recorded_only_with_successful_confirmation(self):
        response = self.draft(owner=True)
        paper_key = str(response.context["paper_form"].initial["request_key"])
        self.values.update(
            {
                "paper-paper_signed": "on",
                "paper-request_key": paper_key,
                "paper-signed_on": timezone.localdate(),
                "paper-signer_name": "Devora Test",
                "paper-relationship": "Parent",
                "paper-minors": "Yanky",
                "covered": "on",
                "price_mode": "comped",
            }
        )
        response = self.post("prepare")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(PaperWaiver.objects.exists())
        self.values["reviewed_hash"] = response.json()["reviewed_hash"]
        response = self.post("confirm")
        self.assertEqual(response.status_code, 200, response.content)
        booking = Booking.objects.get()
        self.assertEqual(PaperWaiver.objects.get().minors, ["Yanky"])
        self.assertTrue(booking.waiver_review.coverage_confirmed)
        self.assertEqual(MessageDelivery.objects.get().kind, "booking_confirmation")

    def test_paper_requires_minor_names_and_guardian_last_names(self):
        response = self.draft(owner=True)
        self.values.update(
            {
                "price_mode": "comped",
                "paper-paper_signed": "on",
                "paper-request_key": str(response.context["paper_form"].initial["request_key"]),
                "paper-signed_on": timezone.localdate(),
                "paper-signer_name": "Devora Test",
                "paper-relationship": "Legal guardian",
                "paper-minors": "Yanky",
            }
        )
        self.assertEqual(self.post("prepare").status_code, 400)
        response = self.post("prepare", **{"paper-minors": ""})
        self.assertEqual(response.status_code, 400)
        self.assertIn("minors", str(response.json()["errors"]))
        self.assertFalse(Booking.objects.exists())

    def test_draft_is_private_and_expires_without_reserving_places(self):
        self.draft()
        other = Client()
        verified_owner_login(other, self.owner)
        self.assertEqual(other.get(self.url, {"draft": self.key}).status_code, 302)
        session = self.client.session
        session[KEY][self.key]["expires"] = (timezone.now() - timedelta(seconds=1)).timestamp()
        session.save()
        self.assertEqual(self.post().status_code, 400)
        self.assertFalse(Booking.objects.exists())

    def test_unknown_card_setup_blocks_changing_customer(self):
        self.draft()
        self.post()
        from core.payments.setup import flow_identity

        digest = flow_identity(self.client.session[KEY][self.key])[0]
        setup = PaymentSetup.objects.create(
            pk=uuid.uuid4(),
            flow_hash=digest,
            nonce_hash="a" * 64,
            state="unknown",
            customer=self.customer,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        other = Customer.objects.create(
            last_name="Other", phone="2025550103", email="other@example.invalid"
        )
        response = self.post(customer=other.pk)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("Resolve the existing card setup", response.json()["error"])
        self.assertEqual(PaymentSetup.objects.get(pk=setup.pk).state, "unknown")
        self.assertEqual(self.client.session[KEY][self.key]["customer_id"], self.customer.pk)

    def test_customer_change_clears_prior_consent(self):
        self.draft()
        self.save_card()
        other = Customer.objects.create(
            last_name="Other", phone="2025550103", email="other@example.invalid"
        )
        response = self.post(customer=other.pk)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["ready"])
        self.assertNotIn("payment_consent", self.client.session[KEY][self.key])
        self.assertFalse(Booking.objects.exists())

    def test_runtime_role_can_reserve_and_consume_hold_without_financial_updates(self):
        self.draft()
        with self.runtime_role():
            self.save_card()
            response = self.post("confirm")
            self.assertEqual(response.status_code, 200, response.content)
            self.assertFalse(BookingCapacityHold.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())


class StaffHoldConcurrencyTests(TransactionTestCase):
    setUp = fixtures.CardSetupTests.setUp
    create = fixtures.CardSetupTests.create

    def test_two_drafts_cannot_reserve_the_same_last_place(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.core.exceptions import ValidationError
        from django.db import close_old_connections, connection, connections

        from core.availability import occupancy
        from core.booking_holds import reserve

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL session locks")
        session = self.create(child_capacity=1, supervised_capacity=1)
        barrier = Barrier(2)

        def attempt():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                reserve(
                    key=uuid.uuid4(),
                    actor=self.staff,
                    customer=self.customer,
                    session=session,
                    children=1,
                    adults=1,
                    babies=0,
                    supervised=False,
                )
                return "reserved"
            except ValidationError:
                return "full"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(results, ["reserved", "full"])
        self.assertEqual(occupancy(session), (1, 1, 0))
