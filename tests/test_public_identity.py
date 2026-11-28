"""A membership checkout can use the approved matching without a play session."""

import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase

from core import public_identity
from core.models import Booking, Customer, PaymentOperation, Session
from core.public_booking import customer_from_flow


class PublicIdentityTests(TestCase):
    def setUp(self):
        self.flow = {"key": str(uuid.uuid4()), "stage": "phone"}

    def advance(self, **data):
        kwargs = {"phone": self.flow["phone"]} if self.flow["stage"] in {"contact", "email"} else {}
        form = public_identity.form_type(self.flow)(data, **kwargs)
        self.assertTrue(form.is_valid(), form.errors)
        return public_identity.advance(self.flow, form, post=data)

    def test_new_contact_remains_provisional_without_creating_visit_or_payment(self):
        self.advance(phone="2025550191", visited="no")
        self.advance(last_name="Greenfeld", email="new@example.invalid", referral_source="Friend")
        self.assertEqual(self.flow["stage"], "details")
        self.assertEqual(self.flow["contact"]["email"], "new@example.invalid")
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(Session.objects.exists())
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_same_surname_conflict_keeps_explicit_profile_choice_and_scoped_proof(self):
        original = Customer.objects.create(
            last_name="Greenfeld", phone="2025550100", email="original@example.invalid"
        )
        other = Customer.objects.create(
            last_name="Greenfeld", phone="2025550101", email="other@example.invalid"
        )
        self.advance(phone=original.phone, visited="yes")
        self.advance(last_name=original.last_name, email=other.email)
        self.assertEqual(self.flow["stage"], "profile_choice")
        self.assertNotIn("proof", self.flow)
        wrong = self.advance(profile_action="original", email=other.email)
        self.assertTrue(wrong.display)
        self.assertNotIn("proof", self.flow)
        self.advance(profile_action="other")
        self.assertEqual(customer_from_flow(self.flow).pk, other.pk)
        with self.assertRaises(ValidationError):
            customer_from_flow(self.flow | {"key": str(uuid.uuid4())})
        self.assertEqual(Customer.objects.count(), 2)
        self.assertFalse(Booking.objects.exists())

    def test_previous_phone_confirmation_rechecks_customer_revision(self):
        customer = Customer.objects.create(
            last_name="Greenfeld",
            phone="2025550100",
            previous_phone="2025550102",
            email="original@example.invalid",
        )
        self.advance(phone=customer.previous_phone, visited="yes")
        self.assertEqual(self.flow["stage"], "previous")
        customer.revision += 1
        customer.save()
        with self.assertRaisesMessage(ValidationError, "Customer details changed"):
            self.advance(confirm_phone="yes")
        self.assertNotIn("proof", self.flow)

    def test_unmatched_phone_email_recovery_requires_name_then_confirmation(self):
        customer = Customer.objects.create(
            last_name="Greenfeld", phone="2025550100", email="original@example.invalid"
        )
        self.advance(phone="2025550191", visited="yes")
        self.flow["stage"] = "email_lookup"
        self.advance(email=customer.email)
        self.assertEqual(self.flow["stage"], "recovered_name")
        self.assertNotIn("proof", self.flow)
        self.advance(last_name=customer.last_name)
        self.assertEqual(self.flow["stage"], "recovered_confirm")
        self.assertNotIn("proof", self.flow)
        self.advance()
        self.assertEqual(customer_from_flow(self.flow).pk, customer.pk)
        self.assertFalse(Session.objects.exists())
