"""Fifth-batch booking paths, bounded copy changes and same-session recovery."""

from django.test import TestCase, override_settings

from core.customers import public_duplicate_email_message
from core.models import Booking, Customer, OwnerNotice
from core.public_booking import customer_from_flow
from tests import test_public_booking as fixtures
from tests.test_owner_accounts import STORAGES


@override_settings(CUSTOMER_TEST_BOOKING=True, STORAGES=STORAGES)
class FifthBookingTests(TestCase):
    setUp = fixtures.PublicBookingTests.setUp
    begin = fixtures.PublicBookingTests.begin
    confirm = fixtures.PublicBookingTests.confirm

    @property
    def flow(self):
        return self.client.session["customer_test_booking"]

    def post(self, data):
        return self.client.post("/book/details/", data, follow=True)

    def customers(self):
        self.original = Customer.objects.create(
            last_name="Greenfeld", phone="2025550100", email="greenfeld@example.invalid"
        )
        self.other = Customer.objects.create(
            last_name="Braun", phone="2025550101", email="braun@example.invalid"
        )

    def match(self, route):
        if route == "retry":
            self.begin("2025550191", "yes")
            return self.post({"phone": self.original.phone})
        self.begin(self.original.phone, route)
        return self.client.get("/book/details/")

    def assert_clean_contact(self, response):
        self.assertContains(response, "Your details")
        self.assertNotContains(response, "You can continue below")
        self.assertNotContains(response, "No customer was found")

    def test_initial_phone_entry_has_no_redundant_restart(self):
        self.client.post(f"/book/start/{self.slot.pk}/")
        response = self.client.get("/book/details/")
        self.assertNotContains(response, "Start again / try another phone number")
        response = self.post({"visited": "no", "phone": "20255501911"})
        self.assertEqual(self.flow["stage"], "phone")
        self.assertNotContains(response, "Start again / try another phone number")
        self.assert_clean_contact(self.post({"visited": "no", "phone": "2025550191"}))
        self.assertFalse(Customer.objects.exists())

    def test_retry_inline_new_customer_action_uses_the_already_checked_phone(self):
        self.begin("2025550191", "yes")
        response = self.client.get("/book/details/")
        self.assertContains(response, "You can try another number below,")
        self.assertContains(response, 'form="customer-booking-form" name="continue_new"')
        self.assertContains(
            response, 'value="1" formnovalidate>continue as a new customer</button>', html=False
        )
        self.assertEqual(response.content.decode().count('name="continue_new"'), 1)
        # This action must not validate or adopt an unfinished replacement number.
        self.assert_clean_contact(self.post({"continue_new": "1", "phone": "unfinished"}))
        self.assertEqual(self.flow["phone"], "2025550191")
        self.assertEqual(self.flow["session_id"], self.slot.pk)
        self.assertFalse(Customer.objects.exists())

    def test_second_unmatched_number_shows_its_own_notice_until_contact_errors(self):
        self.customers()
        self.begin("2025550191", "yes")
        response = self.post({"phone": "2025550192"})
        self.assertContains(response, "No customer was found with 202-555-0192.")
        self.assertContains(response, "You can continue below as a new customer")
        self.assertNotContains(response, "2025550191")
        response = self.post({"last_name": "New", "email": self.other.email})
        self.assert_clean_contact(response)
        self.assertContains(response, "booked with this email before")
        self.assertEqual(self.flow["phone"], "2025550192")
        self.assertNotIn("proof", self.flow)
        self.assertEqual(Customer.objects.count(), 2)

    def test_current_phone_headers_distinguish_yes_no_and_retry_without_email_link(self):
        self.customers()
        for route in ("yes", "no", "retry"):
            with self.subTest(route=route):
                response = self.match(route)
                self.assertContains(response, "We found a customer profile")
                self.assertContains(response, "last name or email address")
                self.assertContains(response, 'name="email"')
                self.assertNotContains(response, "Find my customer details by email")
                if route == "no":
                    self.assertContains(response, "Looks like you've been to MonkeyDo in the past.")
                else:
                    self.assertNotContains(response, "Looks like you've been")
                response = self.post({"last_name": "Unrelated", "email": "missing@example.invalid"})
                self.assertContains(response, "We found a customer profile")
                self.assertEqual(self.flow["stage"], "name")
                self.assertNotIn("proof", self.flow)
                self.assertNotContains(response, self.original.last_name)

    def test_current_email_verifies_yes_no_and_retry_without_mutating_contacts(self):
        self.customers()
        for route in ("yes", "no", "retry"):
            with self.subTest(route=route):
                self.match(route)
                response = self.post({"email": self.original.email.upper()})
                self.assertEqual(customer_from_flow(self.flow).pk, self.original.pk)
                self.assertContains(response, "That email address matches our records.")
                self.assertNotContains(response, "We found a customer profile")
                self.assertNotContains(response, "Looks like you've been")
        self.assertEqual(Customer.objects.count(), 2)
        self.assertFalse(OwnerNotice.objects.exists())
        self.assertFalse(Booking.objects.exists())

    def test_no_and_retry_partial_names_still_require_confirmation(self):
        self.customers()
        for route in ("no", "retry"):
            self.match(route)
            response = self.post({"last_name": "Greenfield"})
            self.assertEqual(self.flow["stage"], "name_confirm")
            self.assertContains(response, "Is this your family?")
            self.assertNotIn("proof", self.flow)
            self.post({})
            self.assertEqual(customer_from_flow(self.flow).pk, self.original.pk)
        self.original.refresh_from_db()
        self.assertEqual(self.original.last_name, "Greenfeld")

    def test_expanded_both_fields_conflict_requires_proof_before_other_phone_or_booking(self):
        self.customers()
        for route in ("no", "retry"):
            with self.subTest(route=route):
                self.match(route)
                response = self.post(
                    {"last_name": self.original.last_name, "email": self.other.email}
                )
                self.assertEqual(self.flow["stage"], "profile_choice")
                self.assertNotContains(response, self.other.phone)
                self.assertNotIn("proof", self.flow)
                response = self.post({"profile_action": "other", "customer_id": self.other.pk})
                self.assertNotContains(response, self.other.phone)
                response = self.post(
                    {"profile_action": "verify_other", "last_name": self.other.last_name}
                )
                self.assertContains(response, "Continue with this email address")
                self.post({"profile_action": "other"})
                self.assertEqual(customer_from_flow(self.flow).pk, self.other.pk)
                self.post(
                    {
                        "play_type": "open",
                        "children": 1,
                        "adults": 1,
                        "babies": 0,
                        "socks": 0,
                        "expected_method": "cash",
                    }
                )
                self.assertEqual(self.confirm().status_code, 302)
        self.assertEqual(OwnerNotice.objects.count(), 2)
        self.assertEqual(
            list(Booking.objects.values_list("customer_id", flat=True)),
            [self.other.pk, self.other.pk],
        )
        self.original.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.original.phone, "2025550100")
        self.assertEqual(self.other.phone, "2025550101")

    def test_expanded_email_first_conflicts_require_profile_confirmation(self):
        self.customers()
        for route in ("no", "retry"):
            for entered, message in (
                (self.original.last_name, "matches customer name"),
                (self.other.last_name, "We found customer Braun"),
                ("Unrelated", "doesn&#x27;t match either customer profile"),
            ):
                with self.subTest(route=route, entered=entered):
                    self.match(route)
                    response = self.post({"email": self.other.email})
                    self.assertEqual(self.flow["stage"], "conflict_name")
                    self.assertNotContains(response, self.other.phone)
                    response = self.post({"last_name": entered})
                    self.assertContains(response, message)
                    self.assertNotIn("proof", self.flow)
                    self.assertEqual(
                        self.flow["stage"],
                        "recovered_confirm" if entered == self.other.last_name else "conflict_stop",
                    )
        self.assertEqual(OwnerNotice.objects.count(), 6)
        self.assertFalse(Booking.objects.exists())

    def test_previous_phone_confirmation_is_not_replaced_by_new_verification(self):
        self.customers()
        self.original.previous_phone = "2025550177"
        self.original.save()
        self.begin(self.original.previous_phone, "no")
        response = self.client.get("/book/details/")
        self.assertEqual(self.flow["stage"], "previous")
        self.assertContains(response, "Is this your current phone number?")
        self.assertNotContains(response, 'name="email"')
        self.post({"confirm_phone": "yes"})
        self.assertEqual(customer_from_flow(self.flow).pk, self.original.pk)

    def test_only_failed_unmatched_phone_lookup_loses_its_initial_intro(self):
        self.customers()
        self.begin("2025550191", "yes")
        response = self.client.get("/book/recover/", follow=True)
        self.assertContains(response, "You can try finding your customer profile")
        response = self.post({"email": "missing@example.invalid"})
        self.assertContains(response, "Find your customer details")
        self.assertContains(response, "We couldn&#x27;t match those details.")
        self.assertNotContains(response, "You can try finding your customer profile")
        self.assertNotContains(response, self.original.last_name)
        self.assertNotContains(response, self.original.phone)
        self.assertNotIn("proof", self.flow)
        self.assertNotContains(
            self.client.get("/book/details/"), "You can try finding your customer profile"
        )

    def test_no_name_failed_email_retry_keeps_initial_context_but_not_after_failure(self):
        self.customers()
        self.match("no")
        response = self.post({"last_name": "Unrelated"})
        self.assertContains(response, "We couldn't match the name ‘Unrelated’ with phone number")
        response = self.post({"email": "missing@example.invalid"})
        self.assertContains(response, "Find your customer details")
        self.assertNotContains(response, "You can try finding your customer profile")
        self.assertNotContains(response, "We couldn't match the name ‘Unrelated’")
        response = self.post({"email": self.original.email})
        self.assertContains(response, "That email address matches our records.")
        self.assertNotContains(response, "Find your customer details")
        self.assertNotIn("referral_source", response.context["form"].fields)

    def test_both_public_duplicate_email_screens_link_to_same_session_phone_entry(self):
        self.customers()
        self.original.email = ""
        self.original.save()
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    self.match("no")
                    self.post({"last_name": self.original.last_name})
                    data = {"email": self.other.email}
                else:
                    self.begin("2025550191", "no")
                    data = {"last_name": "New", "email": self.other.email}
                response = self.post(data)
                self.assertContains(
                    response,
                    '<a href="/book/details/?restart=1">go back</a>',
                    html=True,
                )
                self.assertNotContains(response, "We can remove this email address")
                self.assertNotContains(response, "You can continue below")
                response = self.client.get("/book/details/?restart=1", follow=True)
                self.assertEqual(self.flow["stage"], "phone")
                self.assertEqual(self.flow["session_id"], self.slot.pk)
                for field in (
                    "phone",
                    "candidate",
                    "proof",
                    "contact",
                    "contact_email",
                    "other_proof",
                ):
                    self.assertNotIn(field, self.flow)
                self.assertContains(response, "Have you visited MonkeyDo before?")
        self.assertEqual(Customer.objects.count(), 2)
        self.assertFalse(Booking.objects.exists())

    def test_rich_duplicate_email_error_escapes_customer_controlled_text(self):
        rendered = str(
            public_duplicate_email_message("test@example.invalid", "<img src=x onerror=alert(1)>")
        )
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn('<a href="/book/details/?restart=1">', rendered)
