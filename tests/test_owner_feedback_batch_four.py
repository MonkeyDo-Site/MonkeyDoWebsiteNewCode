"""Fourth-batch verification branches, public play controls and bounded staff paging."""

import uuid
from datetime import timedelta

from django.test import Client, TestCase, override_settings

from core.models import AuditEvent, Booking, Customer, OwnerNotice, Session
from core.public_booking import customer_from_flow
from tests import test_memberships as membership_fixtures
from tests import test_public_booking as public_fixtures
from tests.helpers import verified_owner_login
from tests.test_customers import staff_user
from tests.test_owner_accounts import STORAGES


@override_settings(CUSTOMER_TEST_BOOKING=True, STORAGES=STORAGES)
class FourthMatchingTests(TestCase):
    begin = public_fixtures.PublicBookingTests.begin
    confirm = public_fixtures.PublicBookingTests.confirm

    def setUp(self):
        public_fixtures.PublicBookingTests.setUp(self)
        self.original = Customer.objects.create(
            last_name="Greenfeld", phone="2025550100", email="greenfeld@example.invalid"
        )
        self.other = Customer.objects.create(
            last_name="Braun", phone="2025550101", email="braun@example.invalid"
        )

    @property
    def flow(self):
        return self.client.session["customer_test_booking"]

    def post(self, data, **kwargs):
        return self.client.post("/book/details/", data, follow=True, **kwargs)

    def email_first_conflict(self, visited="yes"):
        self.begin(self.original.phone, visited)
        if visited == "no":
            self.client.get("/book/recover/")
        response = self.post({"email": self.other.email})
        self.assertEqual(self.flow["stage"], "conflict_name")
        self.assertNotContains(response, self.other.phone)
        return response

    def both_fields_conflict(self):
        self.begin(self.original.phone, "yes")
        response = self.post({"last_name": self.original.last_name, "email": self.other.email})
        self.assertEqual(self.flow["stage"], "profile_choice")
        self.assertNotIn("proof", self.flow)
        return response

    def test_two_fields_are_limited_to_returning_current_phone_entry(self):
        self.begin(self.original.phone, "yes")
        self.assertContains(self.client.get("/book/details/"), 'name="email"')
        self.begin(self.original.phone, "no")
        self.assertNotContains(self.client.get("/book/details/"), 'name="email"')
        self.original.previous_phone = "2025550177"
        self.original.save()
        self.begin(self.original.previous_phone, "yes")
        response = self.client.get("/book/details/")
        self.assertContains(response, "Is this your current phone number?")
        self.assertNotContains(response, 'name="email"')

    def test_name_email_and_both_success_use_the_right_existing_profile_and_copy(self):
        cases = [
            ({"last_name": self.original.last_name}, "That name matches our records."),
            ({"email": self.original.email.upper()}, "That email address matches our records."),
            (
                {"last_name": self.original.last_name, "email": self.original.email},
                "That name and email address match our records.",
            ),
            (
                {"last_name": "Unrelated", "email": self.original.email},
                "That email address matches our records.",
            ),
            (
                {"last_name": self.original.last_name, "email": "unassigned@example.invalid"},
                "That name matches our records.",
            ),
        ]
        for data, message in cases:
            with self.subTest(data=data):
                self.begin(self.original.phone, "yes")
                response = self.post(data)
                self.assertContains(response, message)
                self.assertEqual(customer_from_flow(self.flow).pk, self.original.pk)
                self.assertEqual(self.flow["stage"], "details")
        self.assertEqual(Customer.objects.count(), 2)
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(OwnerNotice.objects.exists())

    def test_blank_and_two_unmatched_values_stay_on_the_two_field_screen(self):
        self.begin(self.original.phone, "yes")
        self.assertContains(self.post({}), "Enter your last name or email address.")
        response = self.post({"last_name": "Unrelated", "email": "unassigned@example.invalid"})
        self.assertEqual(self.flow["stage"], "name")
        self.assertNotIn("proof", self.flow)
        self.assertContains(response, 'name="last_name"')
        self.assertContains(response, 'name="email"')
        self.assertNotContains(response, self.original.last_name)
        self.assertNotContains(response, self.other.phone)

    def test_name_first_email_retry_has_exact_context_then_suppresses_outdated_intro(self):
        self.begin(self.original.phone, "yes")
        response = self.post({"last_name": "Unrelated"})
        self.assertContains(
            response, "We couldn't match the name ‘Unrelated’ with phone number ‘2025550100’."
        )
        self.assertNotContains(response, 'name="last_name"')
        response = self.post({"email": "missing@example.invalid"})
        self.assertNotContains(response, "You can try finding your customer profile")
        self.assertContains(response, "missing@example.invalid")
        self.assertContains(response, "Please try again or call/text 848-238-5147 for assistance.")
        response = self.post({"email": self.original.email})
        self.assertContains(response, "That email address matches our records.")
        self.assertEqual(customer_from_flow(self.flow).pk, self.original.pk)

    def test_email_first_name_retry_and_partial_confirmation_keep_original_spelling(self):
        self.begin(self.original.phone, "yes")
        response = self.post({"email": "missing@example.invalid"})
        self.assertEqual(self.flow["stage"], "name_retry")
        self.assertContains(
            response, "You can try finding your customer profile by entering your name."
        )
        self.assertContains(response, 'name="last_name"')
        self.assertNotContains(response, 'name="email"')
        response = self.post({"last_name": "Unrelated"})
        self.assertNotContains(response, "You can try finding your customer profile")
        self.assertContains(response, "Unrelated")
        response = self.post({"last_name": "Greenfield"})
        self.assertEqual(self.flow["stage"], "name_confirm")
        self.assertContains(response, "Is this you?")
        self.assertNotIn("proof", self.flow)
        self.post({})
        self.assertEqual(customer_from_flow(self.flow).pk, self.original.pk)
        self.original.refresh_from_db()
        self.assertEqual(self.original.last_name, "Greenfeld")

    def test_email_first_conflict_all_three_name_results_never_reveal_other_phone(self):
        for visited in ("yes", "no"):
            for entered, expected in (
                (self.original.last_name, "matches customer name"),
                (self.other.last_name, "Please start again with the phone number"),
                ("Unrelated", "doesn&#x27;t match either customer profile"),
            ):
                with self.subTest(visited=visited, entered=entered):
                    self.email_first_conflict(visited)
                    response = self.post({"last_name": entered})
                    self.assertContains(response, expected)
                    self.assertNotContains(response, self.other.phone)
                    self.assertNotIn("proof", self.flow)
                    self.assertEqual(self.flow["stage"], "conflict_stop")
        self.assertEqual(Customer.objects.count(), 2)
        self.assertFalse(Booking.objects.exists())
        self.assertEqual(OwnerNotice.objects.count(), 6)
        self.original.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.original.phone, "2025550100")
        self.assertEqual(self.other.phone, "2025550101")

    def test_email_first_matching_name_does_not_enable_profile_choice_via_forged_action(self):
        self.email_first_conflict()
        response = self.post(
            {
                "last_name": self.other.last_name,
                "profile_action": "other",
                "customer_id": self.other.pk,
            }
        )
        self.assertNotContains(response, self.other.phone)
        self.assertEqual(self.flow["stage"], "conflict_stop")
        self.assertNotIn("proof", self.flow)
        self.post({})
        self.assertEqual(self.flow["stage"], "phone")
        self.assertEqual(self.flow["session_id"], self.slot.pk)

    def test_name_and_email_together_conflict_hides_phone_until_other_name_verified(self):
        response = self.both_fields_conflict()
        self.assertNotContains(response, self.other.phone)
        response = self.post({"profile_action": "other"})
        self.assertNotIn("proof", self.flow)
        self.assertNotContains(response, self.other.phone)
        response = self.post({"profile_action": "verify_other", "last_name": "Unrelated"})
        self.assertNotContains(response, self.other.phone)
        response = self.post({"profile_action": "verify_other", "last_name": self.other.last_name})
        self.assertContains(response, f"Proceed using phone {self.other.phone}")
        self.assertNotIn("proof", self.flow)
        self.post({"profile_action": "other"})
        self.assertEqual(customer_from_flow(self.flow).pk, self.other.pk)
        self.assertEqual(self.flow["phone"], self.other.phone)
        self.assertEqual(OwnerNotice.objects.count(), 1)
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
        self.assertEqual(Booking.objects.get().customer_id, self.other.pk)
        self.original.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.original.phone, "2025550100")
        self.assertEqual(self.other.phone, "2025550101")
        self.assertEqual(Customer.objects.count(), 2)

    def test_verified_original_can_continue_using_its_existing_email_without_contact_change(self):
        self.both_fields_conflict()
        response = self.post({"profile_action": "original", "email": "unassigned@example.invalid"})
        self.assertNotIn("proof", self.flow)
        self.assertNotContains(response, self.other.phone)
        response = self.post({"profile_action": "original", "email": self.original.email})
        self.assertContains(response, "That name and email address match our records.")
        self.assertEqual(customer_from_flow(self.flow).pk, self.original.pk)
        self.original.refresh_from_db()
        self.assertEqual(self.original.email, "greenfeld@example.invalid")

    def test_already_entered_name_is_reused_when_it_also_matches_the_other_profile(self):
        self.other.last_name = self.original.last_name
        self.other.save()
        self.begin(self.original.phone, "yes")
        response = self.post({"last_name": self.original.last_name, "email": self.other.email})
        self.assertContains(response, f"Proceed using phone {self.other.phone}")
        self.assertIn("other_proof", self.flow)
        self.assertNotIn("proof", self.flow)

    def test_other_possible_name_requires_confirmation_before_disclosing_phone(self):
        self.both_fields_conflict()
        response = self.post({"profile_action": "verify_other", "last_name": "Brawn"})
        self.assertContains(response, "Is this your family?")
        self.assertNotContains(response, self.other.phone)
        response = self.post({"profile_action": "confirm_other"})
        self.assertContains(response, self.other.phone)
        self.assertNotIn("proof", self.flow)

    def test_changed_other_profile_invalidates_verified_choice(self):
        self.both_fields_conflict()
        self.post({"profile_action": "verify_other", "last_name": self.other.last_name})
        self.other.revision += 1
        self.other.save(update_fields=["revision"])
        response = self.post({"profile_action": "other"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("proof", self.flow)
        self.assertNotContains(response, self.other.phone, status_code=400)

    def test_conflict_notice_is_persistent_owner_only_and_not_repeated_for_retries(self):
        self.both_fields_conflict()
        for _ in range(2):
            self.post({"profile_action": "verify_other", "last_name": "Unrelated"})
        self.assertEqual(OwnerNotice.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(action="customer.public_profile_conflict").count(), 1
        )
        staff = Client()
        staff.force_login(staff_user())
        self.assertNotContains(
            staff.get("/staff/dashboard/"), "Customer verification details match different profiles"
        )
        owner = staff_user("owner", owner=True)
        verified_owner_login(staff, owner)
        response = staff.get("/staff/dashboard/")
        self.assertContains(response, "Customer verification details match different profiles")
        self.assertContains(response, f"/staff/customers/{self.other.pk}/")
        self.assertContains(response, "No customer phone number was changed.")
        notice = OwnerNotice.objects.get()
        regular = Client()
        regular.force_login(self.staff if hasattr(self, "staff") else staff_user("reviewer"))
        self.assertEqual(regular.post(f"/staff/notices/{notice.pk}/review/").status_code, 403)
        self.assertEqual(staff.post(f"/staff/notices/{notice.pk}/review/").status_code, 302)
        notice.refresh_from_db()
        self.assertIsNotNone(notice.reviewed_at)
        self.assertTrue(
            AuditEvent.objects.filter(action="customer.profile_conflict_reviewed").exists()
        )

    def test_blank_referral_and_stale_other_tab_do_not_lose_new_customer_step(self):
        self.begin("2025550191", "no")
        old = dict(self.flow)
        response = self.post(
            {
                "last_name": "New Family",
                "email": "new@example.invalid",
                "referral_source": "",
                "wizard_key": old["key"],
                "wizard_stage": "contact",
            }
        )
        self.assertEqual(self.flow["stage"], "details")
        self.assertContains(response, "Your details are ready")
        self.assertFalse(Customer.objects.filter(phone="2025550191").exists())
        response = self.post(
            {
                "last_name": "New Family",
                "email": "new@example.invalid",
                "wizard_key": old["key"],
                "wizard_stage": "contact",
            }
        )
        self.assertContains(response, "Your booking changed in another tab or an earlier step")
        self.assertNotContains(response, "This field is required.")
        self.assertEqual(self.flow["stage"], "details")
        self.begin("2025550192", "no")
        response = self.post(
            {
                "last_name": "New Family",
                "email": "new@example.invalid",
                "wizard_key": old["key"],
                "wizard_stage": "contact",
            }
        )
        self.assertContains(response, "Your booking changed in another tab or an earlier step")
        self.assertNotContains(response, "This field is required.")
        self.assertEqual(self.flow["stage"], "contact")

    def test_stale_page_retains_a_usable_review_confirmation(self):
        self.begin(self.original.phone, "yes")
        self.post({"email": self.original.email})
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
        flow = self.flow
        response = self.post(
            {"wizard_key": flow["key"], "wizard_stage": "name", "last_name": "Greenfeld"}
        )
        self.assertContains(response, "Your booking changed in another tab or an earlier step")
        self.assertContains(response, 'name="flow_key" value="' + flow["key"] + '"')
        self.assertEqual(self.flow["quote"], flow["quote"])
        self.assertEqual(self.confirm().status_code, 302)
        self.assertEqual(Booking.objects.get().customer_id, self.original.pk)

    def test_unavailable_play_is_visible_disabled_and_server_side_submission_is_rejected(self):
        self.slot.play_mode = "accompanied"
        self.slot.save()
        self.begin(self.original.phone, "yes")
        response = self.post({"email": self.original.email})
        self.assertContains(response, "Supervised Play (not available for this session)")
        self.assertContains(response, "disabled")
        self.assertContains(
            response, 'name="play_type" value="open" required id="id_play_type_0" checked'
        )
        response = self.post(
            {
                "play_type": "supervised",
                "children": 1,
                "adults": 0,
                "babies": 0,
                "socks": 0,
                "expected_method": "cash",
            }
        )
        self.assertContains(response, "This play type is not available for this session.")
        self.assertEqual(self.flow["stage"], "details")
        self.assertFalse(Booking.objects.exists())

    def test_supervised_only_defaults_to_supervised_and_zero_counts_and_updates_estimate(self):
        self.slot.play_mode = "supervised"
        self.slot.save()
        self.begin(self.original.phone, "yes")
        response = self.post({"email": self.original.email})
        self.assertContains(response, "Open Play (not available for this session)")
        self.assertContains(response, 'name="adults" value="0"')
        self.assertContains(response, 'name="babies" value="0"')
        self.assertContains(response, "$18.99")
        self.assertNotContains(response, "Check the booking page to see which sessions offer it.")
        self.assertNotContains(response, "For supervised play, enter only")
        estimate = self.client.post(
            "/book/estimate/",
            {
                "play_type": "supervised",
                "children": 2,
                "adults": 0,
                "babies": 0,
                "socks": 0,
                "expected_method": "card",
            },
        )
        self.assertEqual(estimate.status_code, 200)
        self.assertIn("$37.98", estimate.json()["html"])
        self.assertNotIn("processing fee", estimate.json()["html"])
        invalid = self.client.post(
            "/book/estimate/",
            {
                "play_type": "supervised",
                "children": 1,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "expected_method": "cash",
            },
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(Booking.objects.exists())


@override_settings(STORAGES=STORAGES)
class FourthPagingTests(TestCase):
    def setUp(self):
        public_fixtures.PublicBookingTests.setUp(self)
        self.staff = staff_user()
        self.client.force_login(self.staff)
        self.customer = Customer.objects.create(
            last_name="Paging Family", phone="2025550180", email="pages@example.invalid"
        )
        second = Session.objects.create(
            starts_at=self.slot.starts_at + timedelta(hours=2),
            ends_at=self.slot.ends_at + timedelta(hours=2),
            public=True,
        )
        self.slots = [self.slot, second]
        Booking.objects.bulk_create(
            [
                Booking(customer=self.customer, session=self.slots[i % 2], children=1, adults=1)
                for i in range(32)
            ]
        )

    def test_bookings_paging_preserves_multiple_filters_and_has_bounded_sizes(self):
        response = self.client.get(
            "/staff/bookings/",
            {
                "per_page": "10",
                "page": "2",
                "q": "Paging",
                "status": ["pending", "cancelled"],
                "play": ["open", "supervised"],
            },
        )
        page = response.context["bookings"]
        self.assertEqual(len(page), 10)
        self.assertEqual(page.paginator.count, 32)
        self.assertEqual(page.number, 2)
        self.assertContains(response, "Rows per page")
        self.assertContains(response, 'aria-current="page">2')
        self.assertIn("status=pending&status=cancelled", page.filter_query)
        self.assertIn("play=open&play=supervised", page.filter_query)
        self.assertNotIn("page=2", page.filter_query)
        for value in ("0", "-1", "999999", "invalid"):
            fallback = self.client.get("/staff/bookings/", {"per_page": value})
            self.assertEqual(fallback.context["bookings"].page_size, 25)
        self.assertEqual(
            self.client.get("/staff/bookings/", {"per_page": "10", "page": "9999"})
            .context["bookings"]
            .number,
            4,
        )

    def test_today_paging_keeps_all_matching_and_session_totals(self):
        response = self.client.get("/staff/today/", {"per_page": "10", "page": "2"})
        self.assertEqual(len(response.context["bookings"]), 10)
        self.assertEqual(response.context["matching_count"], 32)
        self.assertEqual(sum(row["bookings"] for row in response.context["session_overview"]), 32)
        self.assertEqual(sum(row["children"] for row in response.context["session_overview"]), 32)
        self.assertContains(response, "32 matching bookings.")
        self.assertContains(response, "Rows per page")

    def test_customer_paging_and_type_filter_combine_with_default_all(self):
        Customer.objects.bulk_create(
            [
                Customer(
                    last_name=f"Family {i:02}",
                    phone=f"2025551{i:03}",
                    customer_type="school" if i % 2 else "family",
                )
                for i in range(30)
            ]
        )
        response = self.client.get(
            "/staff/customers/", {"per_page": "10", "page": "2", "q": "Family", "type": "school"}
        )
        self.assertEqual(len(response.context["customers"]), 5)
        self.assertEqual(response.context["customers"].paginator.count, 15)
        self.assertIn("type=school", response.context["customers"].filter_query)
        self.assertEqual(self.client.get("/staff/customers/").context["customer_type"], "")


@override_settings(STORAGES=STORAGES)
class FourthMembershipPagingTests(TestCase):
    setUp = membership_fixtures.MembershipDraftTests.setUp
    create = membership_fixtures.MembershipDraftTests.create

    def test_membership_root_rows_paginate_and_preserve_customer_filter(self):
        for _ in range(12):
            self.create(creation_key=uuid.uuid4())
        self.client.force_login(self.staff)
        response = self.client.get(
            "/staff/memberships/", {"per_page": "10", "page": "2", "customer": self.customer.pk}
        )
        page = response.context["drafts"]
        self.assertEqual(len(page), 2)
        self.assertEqual(page.paginator.count, 12)
        self.assertIn(f"customer={self.customer.pk}", page.filter_query)
        self.assertContains(response, "Rows per page")
