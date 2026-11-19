import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from core.customers import save_comment
from core.memberships import create_draft, current_draft, edit_draft
from core.models import Booking, Session
from tests import test_public_booking as public_tests
from tests import test_scheduling as scheduling_tests
from tests.test_owner_accounts import STORAGES


@override_settings(STORAGES=STORAGES)
class MembershipRevisionTests(TestCase):
    setUp = scheduling_tests.SchedulingTests.setUp

    def draft(self, **kwargs):
        return create_draft(
            actor=self.staff,
            customer=self.customer,
            kind="subscription",
            places=1,
            months=3,
            billing="monthly",
            starts_on=scheduling_tests.NOW.date(),
            expected_method="cash",
            creation_key=uuid.uuid4(),
            **kwargs,
        )

    def edit(self, root, **kwargs):
        current = current_draft(root)
        data = {
            key: getattr(current, key)
            for key in ("kind", "places", "months", "billing", "starts_on", "expected_method")
        }
        return edit_draft(
            actor=self.staff,
            draft_id=root.pk,
            version=current.version_number,
            submission_key=uuid.uuid4(),
            **(data | kwargs),
        )

    def test_edit_keeps_id_original_cycles_prices_and_all_previous_versions(self):
        root = self.draft()
        original = list(root.cycles.values_list("starts_on", "ends_on", "quote"))
        second = self.edit(root, places=2, months=4, billing="prepaid")
        self.assertEqual(second.pk, root.pk)
        self.assertEqual(second.snapshot["term_subtotal"], "143.92")
        self.assertEqual(second.version_number, 2)
        third = self.edit(root, kind="unlimited")
        self.assertEqual(third.pk, root.pk)
        self.assertEqual(third.snapshot["term_subtotal"], "319.92")
        root.refresh_from_db()
        self.assertEqual(root.places, 1)
        self.assertEqual(list(root.cycles.values_list("starts_on", "ends_on", "quote")), original)
        self.assertEqual(root.revisions.count(), 2)
        self.assertEqual(current_draft(root).version_number, 3)

    def test_saved_versions_can_be_viewed_without_changing_the_latest_membership(self):
        root = self.draft()
        self.edit(root, places=4)
        self.client.force_login(self.staff)
        response = self.client.get(f"/staff/memberships/{root.pk}/?revision=1")
        self.assertEqual(response.context["draft"].places, 1)
        self.assertContains(response, "This previously saved version is read only")
        self.assertNotContains(response, ">Edit membership</a>")
        self.assertEqual(current_draft(root).places, 4)

    def test_stale_and_idempotent_edit_submissions(self):
        root = self.draft()
        args = dict(
            actor=self.staff,
            draft_id=root.pk,
            version=1,
            submission_key=uuid.uuid4(),
            kind="subscription",
            places=2,
            months=3,
            billing="monthly",
            starts_on=root.starts_on,
            expected_method="cash",
        )
        first = edit_draft(**args)
        again = edit_draft(**args)
        self.assertEqual(first.version_number, again.version_number)
        self.assertEqual(root.revisions.count(), 1)
        with self.assertRaises(ValidationError):
            edit_draft(**(args | {"submission_key": uuid.uuid4()}))
        with self.assertRaises(ValidationError):
            edit_draft(**(args | {"places": 4}))

    def test_owner_short_term_exception_cannot_be_forged_by_staff(self):
        root = self.draft()
        args = dict(
            draft_id=root.pk,
            version=1,
            submission_key=uuid.uuid4(),
            kind="subscription",
            places=1,
            months=1,
            billing="monthly",
            starts_on=root.starts_on,
            expected_method="cash",
            minimum_override=True,
        )
        with self.assertRaises(PermissionDenied):
            edit_draft(actor=self.staff, **args)
        edit_draft(actor=self.owner, **args)
        # Staff may retain an already-approved exception while changing the payment plan.
        result = self.edit(root, expected_method="card")
        self.assertEqual(result.months, 1)
        with self.assertRaises(ValidationError):
            self.edit(root, months=2)

    def test_audit_failure_rolls_back_revision(self):
        root = self.draft()
        with patch(
            "core.memberships.AuditEvent.objects.create", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                self.edit(root, months=4)
        self.assertFalse(root.revisions.exists())

    def test_revisions_have_model_and_sql_immutability_guards(self):
        root = self.draft()
        self.edit(root, months=4)
        row = root.revisions.get()
        with self.assertRaises(ValidationError):
            row.save()
        with self.assertRaises(ValidationError):
            root.revisions.update(number=3)
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_membershipdraftrevision SET number=3 WHERE id=%s", [row.pk]
                )

    def test_table_customer_card_and_edit_screen_show_latest_version_and_linked_id(self):
        root = self.draft()
        self.edit(root, kind="unlimited", places=2)
        self.client.force_login(self.staff)
        response = self.client.get("/staff/memberships/")
        self.assertContains(response, "<table")
        self.assertContains(response, f'href="/staff/memberships/{root.pk}/">#M{root.pk}</a>')
        self.assertContains(response, "Unlimited")
        response = self.client.get(f"/staff/customers/{self.customer.pk}/")
        self.assertContains(response, "Unlimited")
        response = self.client.get(f"/staff/memberships/{root.pk}/edit/")
        self.assertEqual(response.context["form"].initial["version"], 2)
        args = {
            "version": 2,
            "submission_key": str(uuid.uuid4()),
            "kind": "unlimited",
            "places": 3,
            "months": 3,
            "billing": "monthly",
            "starts_on": root.starts_on.isoformat(),
            "expected_method": "cash",
        }
        response = self.client.post(f"/staff/memberships/{root.pk}/edit/", args)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(current_draft(root).places, 3)


@override_settings(STORAGES=STORAGES)
class EstimateAndFilterTests(TestCase):
    setUp = scheduling_tests.SchedulingTests.setUp
    create = scheduling_tests.SchedulingTests.create
    reserve = scheduling_tests.SchedulingTests.reserve

    def test_estimate_endpoint_is_read_only_csrf_protected_and_confirmation_binds_values(self):
        booking = self.reserve(self.create())
        self.client.force_login(self.staff)
        data = {
            "session": booking.session_id,
            "children": 2,
            "adults": 1,
            "babies": 0,
            "socks": 0,
            "supervised": "",
            "expected_method": "cash",
            "version": 1,
        }
        response = self.client.post(f"/staff/bookings/{booking.pk}/estimate/", data)
        self.assertEqual(response.status_code, 200)
        estimate = response.json()
        booking.refresh_from_db()
        self.assertEqual(booking.children, 1)
        self.assertEqual(booking.quotes.count(), 1)
        response = self.client.post(
            f"/staff/bookings/{booking.pk}/edit/",
            data | {"children": 3, "estimate_token": estimate["token"]},
        )
        self.assertTrue(response.context["show_payment_reminder"])
        booking.refresh_from_db()
        self.assertEqual(booking.children, 1)
        from django.test import Client

        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.staff)
        self.assertEqual(
            secure.post(f"/staff/bookings/{booking.pk}/estimate/", data).status_code, 403
        )

    def test_multiple_session_selection_and_no_selection_includes_all(self):
        first = self.create()
        second = self.create(
            starts_at=first.starts_at + timedelta(hours=3),
            ends_at=first.ends_at + timedelta(hours=3),
        )
        third = self.create(
            starts_at=first.starts_at + timedelta(hours=6),
            ends_at=first.ends_at + timedelta(hours=6),
        )
        for session in (first, second, third):
            self.reserve(session)
        self.client.force_login(self.staff)
        for path, choices in (
            ("/staff/today/", [str(first.pk), str(second.pk)]),
            ("/staff/bookings/", ["11:00", "14:00"]),
        ):
            response = self.client.get(path, {"session": choices})
            self.assertEqual(len(response.context["bookings"]), 2)
            self.assertEqual(len(self.client.get(path).context["bookings"]), 3)
        response = self.client.get("/staff/bookings/")
        self.assertNotContains(response, "Session totals below")

    def test_staff_duplicate_email_error_links_to_the_existing_customer(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            "/staff/customers/new/",
            {"last_name": "New", "phone": "2025550170", "email": self.customer.email},
        )
        self.assertContains(response, "already assigned to another customer")
        self.assertContains(response, f'href="/staff/customers/{self.customer.pk}/"')
        self.assertNotContains(response, "Please go back to the booking page")

    def test_legacy_empty_session_filter_still_means_all_sessions(self):
        session = self.create()
        self.reserve(session)
        self.client.force_login(self.staff)
        response = self.client.get("/staff/bookings/", {"session": ""})
        self.assertEqual(len(response.context["bookings"]), 1)

    def test_added_comment_has_no_before_but_edited_comment_has_both(self):
        comment = save_comment(actor=self.staff, customer_id=self.customer.pk, body="Original text")
        self.client.force_login(self.staff)
        path = f"/staff/customers/{self.customer.pk}/history/"
        self.assertNotContains(self.client.get(path), "Before:")
        save_comment(
            actor=self.staff,
            customer_id=self.customer.pk,
            comment_id=comment.pk,
            revision=1,
            body="Revised text",
        )
        response = self.client.get(path)
        self.assertContains(response, "Before:")
        self.assertContains(response, "After:")


@override_settings(CUSTOMER_TEST_BOOKING=True, STORAGES=STORAGES)
class PublicResponseTests(TestCase):
    setUp = public_tests.PublicBookingTests.setUp
    begin = public_tests.PublicBookingTests.begin

    def test_open_only_shows_both_choices_with_supervised_disabled(self):
        Session.objects.filter(pk=self.slot.pk).update(
            play_mode="accompanied", supervised_capacity=0
        )
        self.begin()
        self.client.post(
            "/book/details/", {"last_name": "Family", "email": "family@example.invalid"}
        )
        response = self.client.get("/book/details/")
        self.assertContains(response, "Supervised Play (not available for this session)")
        self.assertNotContains(response, "For supervised play")
        self.assertContains(response, 'type="radio"', count=2)
        self.assertContains(response, "disabled")
        self.assertContains(response, "Credit Card – a 3% processing fee applies.")
        self.assertContains(response, "Grip socks are required")
        self.assertEqual(len(response.context["progress_steps"]), 4)

    def test_open_only_rejects_forged_supervised_choice_and_renders_a_usable_retry(self):
        Session.objects.filter(pk=self.slot.pk).update(
            play_mode="accompanied", supervised_capacity=0
        )
        self.begin()
        self.client.post(
            "/book/details/", {"last_name": "Family", "email": "family@example.invalid"}
        )
        response = self.client.post(
            "/book/details/",
            {
                "play_type": "supervised",
                "children": 1,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "expected_method": "cash",
            },
        )
        self.assertIn("play_type", response.context["form"].errors)
        self.assertContains(response, 'name="play_type" value="open"')
        self.assertFalse(Booking.objects.exists())

    def test_supervised_capacity_exhaustion_disables_supervised_option(self):
        customer = __import__("core.models", fromlist=["Customer"]).Customer.objects.create(
            last_name="Existing", phone="2025550120", email="existing@example.invalid"
        )
        Booking.objects.create(
            customer=customer, session=self.slot, children=5, adults=0, supervised=True
        )
        self.begin()
        self.client.post("/book/details/", {"last_name": "New", "email": "new@example.invalid"})
        response = self.client.get("/book/details/")
        self.assertContains(response, "Supervised Play (not available for this session)")
        self.assertNotContains(response, "For supervised play")
