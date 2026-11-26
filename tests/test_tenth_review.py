"""Tenth document: recover verified profiles without guessing, and keep fee tenders explicit."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.booking_forms import PricingPolicyForm, TestBookingForm
from core.models import Booking, Customer, PaymentOperation, PricingPolicy
from core.payments.checkout import preview
from core.payments.checkout_views import ClosureForm
from core.payments.ledger import record_result
from core.pricing import booking_quote
from core.public_booking import customer_from_flow
from core.waivers.coverage_forms import CoverageConfirmationForm
from tests import test_ninth_staff_review as staff
from tests import test_owner_feedback_batch_five as public
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES


@override_settings(CUSTOMER_TEST_BOOKING=True, STORAGES=STORAGES)
class TenthRecoveryTests(TestCase):
    setUp = public.FifthBookingTests.setUp
    begin = public.FifthBookingTests.begin
    post = public.FifthBookingTests.post
    customers = public.FifthBookingTests.customers
    flow = public.FifthBookingTests.flow

    def lookup(self):
        self.customers()
        self.begin("2025550191", "yes")
        self.client.get(reverse("customer_email_recovery"))

    def test_unmatched_email_retry_finds_existing_profile_then_requires_name_and_confirmation(self):
        self.lookup()
        self.post({"email": "missing@example.invalid"})
        response = self.post({"email": self.other.email.upper()})
        self.assertEqual(self.flow["stage"], "recovered_name")
        self.assertNotContains(response, "202-555-0101")
        self.assertNotIn("proof", self.flow)
        self.post({"last_name": "Wrong"})
        self.assertEqual(self.flow["stage"], "recovered_name")
        response = self.post({"last_name": self.other.last_name})
        self.assertContains(response, "We found customer Braun")
        self.assertContains(response, "202-555-0101")
        self.assertEqual(self.flow["stage"], "recovered_confirm")
        self.assertNotIn("proof", self.flow)
        self.post({})
        self.assertEqual(customer_from_flow(self.flow).pk, self.other.pk)
        self.assertEqual(self.flow["phone"], self.other.phone)
        self.assertEqual(Customer.objects.count(), 2)
        self.assertFalse(Booking.objects.exists())

    def test_recovered_profile_cannot_confirm_after_record_changes(self):
        self.lookup()
        self.post({"email": self.other.email})
        self.post({"last_name": self.other.last_name})
        self.other.email = "new@example.invalid"
        self.other.revision += 1
        self.other.save()
        response = self.post({})
        self.assertContains(response, "Customer details changed", status_code=400)
        self.assertNotIn("proof", self.flow)
        self.assertFalse(Booking.objects.exists())

    def test_same_surname_keeps_both_choices_but_original_still_requires_its_email(self):
        self.customers()
        self.other.last_name = self.original.last_name
        self.other.save()
        self.begin(self.original.phone, "yes")
        response = self.post({"last_name": "Greenfeld", "email": self.other.email})
        self.assertContains(
            response, "Your phone number and email address belong to different customer profiles."
        )
        self.assertContains(response, "Continue with this phone number")
        self.assertContains(response, "Continue with this email address")
        self.post({"profile_action": "original", "email": self.other.email})
        self.assertNotIn("proof", self.flow)
        self.post({"profile_action": "original", "email": self.original.email})
        self.assertEqual(customer_from_flow(self.flow).pk, self.original.pk)

    def test_duplicate_new_contact_shows_entered_phone_and_session_preserving_restart(self):
        self.customers()
        self.begin("2025550191", "no")
        response = self.post({"last_name": "New", "email": self.other.email})
        self.assertContains(response, "booked with this email before")
        self.assertContains(response, "using 202-555-0191, with a different email")
        self.assertContains(response, "/book/details/?restart=1")
        self.assertEqual(Customer.objects.count(), 2)
        self.assertFalse(Booking.objects.exists())


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
class TenthStaffTests(TestCase):
    setUp = staff.NinthStaffTests.setUp
    create = staff.NinthStaffTests.create
    flow = staff.NinthStaffTests.flow
    card = staff.NinthStaffTests.card
    save_card = staff.NinthStaffTests.save_card
    gateway = staff.NinthStaffTests.gateway
    ready = staff.NinthStaffTests.ready
    booking = staff.NinthStaffTests.booking
    arrival_inputs = staff.NinthStaffTests.arrival_inputs
    act = staff.NinthStaffTests.act

    def test_gift_card_cannot_pay_cancellation_in_form_or_service(self):
        b = self.booking()
        values = self.arrival_inputs(
            b, method="gift_card", gift_card_verified=True, charge_fee=True
        )
        with self.assertRaisesMessage(ValidationError, "booking card or recorded Zelle"):
            preview(actor=self.staff, booking_id=b.pk, kind="cancellation", data=values)
        for kind in ("cancellation", "no_show"):
            form = ClosureForm(booking=b, kind=kind, owner=True)
            self.assertEqual(form.fields["method"].choices, [("card", "Charge card on file")])
            self.assertNotIn("gift_card_verified", form.fields)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_declined_booking_shows_both_retry_and_alternative_payment_actions(self):
        b = self.booking()
        checkout = self.act(b, self.arrival_inputs(b, method="card"))
        operation = checkout.sale.operations.get(tender="card")
        record_result(
            operation_id=operation.pk,
            state="declined",
            source="provider",
            provider_reference="12345",
        )
        verified_owner_login(self.client, self.owner)
        response = self.client.get(reverse("booking_detail", args=[b.pk]))
        self.assertContains(response, "Retry card")
        self.assertContains(response, "Review remaining payment")
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_remaining_fee_cannot_bypass_gift_card_restriction_after_decline(self):
        from core.payments.remainders import preview as remaining_preview

        b = self.booking()
        checkout = self.act(
            b, self.arrival_inputs(b, method="card", charge_fee=True), kind="cancellation"
        )
        operation = checkout.sale.operations.get(tender="card")
        record_result(
            operation_id=operation.pk,
            state="declined",
            source="provider",
            provider_reference="12346",
        )
        with self.assertRaisesMessage(ValidationError, "Gift cards cannot be used"):
            remaining_preview(actor=self.owner, booking_id=b.pk, method="gift_card")
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_new_pricing_versions_link_baby_and_adult_minimum_to_child_price(self):
        original = PricingPolicy.objects.first()
        old_minimum = original.minimum_admission
        form = PricingPolicyForm(
            {
                "child_price": "17",
                "extra_adult_price": "7",
                "supervised_price": "21.50",
                "sock_price": "1.99",
                "tax_percent": "6.6",
                "fee_percent": "3",
            },
            policy=original,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("minimum_admission", form.fields)
        policy = form.save()
        self.assertEqual(policy.minimum_admission, Decimal("17"))
        for babies in (0, 1):
            quote = booking_quote(
                policy, children=0, adults=1, babies=babies, expected_method="cash"
            )
            self.assertEqual(quote["subtotal"], "17.00")
        original.refresh_from_db()
        self.assertEqual(original.minimum_admission, old_minimum)

    def test_supervised_adult_error_is_attached_to_adult_field(self):
        b = self.booking()
        form = TestBookingForm(
            {
                "session": b.session_id,
                "session_date": b.session.starts_at.date(),
                "version": b.edit_version,
                "children": 2,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "supervised": "on",
                "expected_method": "cash",
            },
            booking=b,
            owner=True,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Cannot have adults in a supervised play visit.", form.errors["adults"])

    def test_waiver_confirmation_lists_yes_before_no(self):
        self.assertEqual(CoverageConfirmationForm.base_fields["coverage"].choices[0][0], "yes")
