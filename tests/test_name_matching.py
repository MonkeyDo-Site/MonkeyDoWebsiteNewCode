from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from core.models import Booking, Customer
from core.name_matching import similar_name
from tests.test_owner_accounts import STORAGES
from tests.test_scheduling import SchedulingTests


class NameMatchingRulesTests(SimpleTestCase):
    def test_common_spelling_variants_and_short_name_limits(self):
        for left, right in [
            ("Greenfeld", "Greenfield"),
            ("Greenfeild", "Greenfield"),
            ("Brown", "Browne"),
            ("O’Name", "O'Name"),
            ("José", "Jose"),
        ]:
            self.assertTrue(similar_name(left, right), (left, right))
        for left, right in [("Li", "Lu"), ("Smith", "Jones"), ("PrivateFamily", "Wrong"), ("", "")]:
            self.assertFalse(similar_name(left, right), (left, right))


@override_settings(STORAGES=STORAGES)
class StaffNameSearchTests(TestCase):
    setUp = SchedulingTests.setUp
    create = SchedulingTests.create

    def test_staff_customer_and_booking_search_rank_exact_then_possible(self):
        exact = Customer.objects.create(
            last_name="Greenfield", phone="2025550190", email="exact@example.invalid"
        )
        possible = Customer.objects.create(
            last_name="Greenfeld", phone="2025550191", email="possible@example.invalid"
        )
        session = self.create()
        Booking.objects.create(customer=exact, session=session, children=1, adults=1)
        Booking.objects.create(customer=possible, session=session, children=1, adults=1)
        self.client.force_login(self.staff)
        response = self.client.get("/staff/customers/", {"q": "Greenfield"})
        self.assertEqual([c.pk for c in response.context["customers"]], [exact.pk, possible.pk])
        self.assertContains(response, "Possible Last Name match")
        response = self.client.get("/staff/bookings/", {"q": "Greenfield"})
        self.assertEqual(
            [b.customer_id for b in response.context["bookings"]], [exact.pk, possible.pk]
        )
        self.assertContains(response, "Possible name match")
        self.assertContains(response, '<table class="staff-table booking-table">')
        self.assertContains(response, "Open Play")
        self.assertContains(response, '<th scope="col">Booking ID</th>')
        self.assertNotContains(response, '<th scope="col">Open booking</th>')
        booking = Booking.objects.get(customer=exact)
        self.assertContains(response, f'href="/staff/bookings/{booking.pk}/">#{booking.pk}</a>')
        self.assertContains(
            self.client.get(f"/staff/bookings/{booking.pk}/"), f"Booking #{booking.pk}"
        )

    def test_partial_email_phone_and_no_permission_behavior_are_preserved(self):
        self.client.force_login(self.staff)
        for query in ("2025550122", "test@example.invalid", "Tes"):
            response = self.client.get("/staff/customers/", {"q": query})
            self.assertEqual([c.pk for c in response.context["customers"]], [self.customer.pk])
        blocked = get_user_model().objects.create_user(username="no-access", is_staff=True)
        self.client.force_login(blocked)
        for path in ("/staff/customers/", "/staff/bookings/"):
            self.assertEqual(self.client.get(path, {"q": "Greenfield"}).status_code, 403)
