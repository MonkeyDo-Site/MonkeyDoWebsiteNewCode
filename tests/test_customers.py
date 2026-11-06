from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.customers import correct_previous_phone, create_customer, save_comment, update_customer
from core.models import AuditEvent, Booking, Customer, CustomerComment, Session


def staff_user(username="staff", owner=False):
    user = get_user_model().objects.create_user(
        username=username, is_staff=True, is_superuser=owner
    )
    call_command("configure_staff_group", stdout=StringIO())
    user.groups.add(Group.objects.get(name="MonkeyDo Staff"))
    return user


class CustomerServiceTests(TestCase):
    def setUp(self):
        self.staff = staff_user()
        self.owner = staff_user("owner", owner=True)
        self.customer = create_customer(
            actor=self.staff,
            last_name="Test Family",
            phone="(202) 555-0100",
            email="first@example.invalid",
        )

    def update(self, **values):
        data = dict(
            actor=self.staff,
            customer_id=self.customer.pk,
            revision=self.customer.revision,
            last_name=self.customer.last_name,
            phone=self.customer.phone,
            email=self.customer.email,
        )
        data.update(values)
        self.customer = update_customer(**data)
        return self.customer

    def test_creation_normalizes_and_audits_without_first_name(self):
        self.assertEqual(self.customer.phone, "2025550100")
        self.assertEqual(self.customer.customer_type, "family")
        self.assertTrue(
            AuditEvent.objects.filter(
                action="customer.created", record_id=str(self.customer.pk)
            ).exists()
        )

    def test_reject_duplicate_current_or_previous_phone(self):
        self.update(phone="2025550101", move_previous_phone="yes")
        for phone in ("2025550100", "2025550101"):
            with self.subTest(phone=phone), self.assertRaises(ValidationError):
                create_customer(
                    actor=self.staff,
                    last_name="Duplicate",
                    phone=phone,
                    email="duplicate@example.invalid",
                )
        self.assertEqual(Customer.objects.count(), 1)

    def test_phone_change_requires_explicit_yes_no(self):
        with self.assertRaises(ValidationError):
            self.update(phone="2025550101")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.phone, "2025550100")

    def test_yes_moves_current_and_no_preserves_previous(self):
        self.update(phone="2025550101", move_previous_phone="yes")
        self.assertEqual(self.customer.previous_phone, "2025550100")
        self.update(phone="2025550102", move_previous_phone="no")
        self.assertEqual(self.customer.previous_phone, "2025550100")
        self.assertFalse(CustomerComment.objects.exists())

    def test_previous_phone_return_obeys_no_and_supports_yes_swap(self):
        self.update(phone="2025550101", move_previous_phone="yes")
        self.update(phone="2025550100", move_previous_phone="no")
        self.assertEqual(self.customer.previous_phone, "2025550100")
        self.update(phone="2025550101", move_previous_phone="yes")
        self.update(phone="2025550100", move_previous_phone="yes")
        self.assertEqual(self.customer.previous_phone, "2025550101")

    def test_owner_resolves_previous_number_before_reuse(self):
        self.update(phone="2025550101", move_previous_phone="yes")
        with self.assertRaises(PermissionDenied):
            correct_previous_phone(
                actor=self.staff,
                customer_id=self.customer.pk,
                revision=self.customer.revision,
                phone="",
            )
        corrected = correct_previous_phone(
            actor=self.owner,
            customer_id=self.customer.pk,
            revision=self.customer.revision,
            phone="",
        )
        self.assertEqual(corrected.previous_phone, "")
        other = create_customer(
            actor=self.staff,
            last_name="New holder",
            phone="2025550100",
            email="new@example.invalid",
        )
        self.assertNotEqual(other.pk, self.customer.pk)

    def test_email_history_archives_only_displaced_previous_value(self):
        self.update(email="second@example.invalid")
        self.assertEqual(self.customer.previous_email, "first@example.invalid")
        self.assertFalse(CustomerComment.objects.exists())
        self.update(email="third@example.invalid")
        self.assertEqual(self.customer.previous_email, "second@example.invalid")
        archived = CustomerComment.objects.get()
        self.assertTrue(archived.system_generated)
        self.assertIn("first@example.invalid", archived.body)
        self.assertEqual(archived.author, self.staff)

    def test_staff_cannot_change_type_but_owner_can(self):
        with self.assertRaises(PermissionDenied):
            self.update(customer_type="day_camp")
        self.update(actor=self.owner, customer_type="day_camp")
        self.assertEqual(self.customer.customer_type, "day_camp")

    def test_stale_revision_rejected_without_overwriting(self):
        original = self.customer.revision
        self.update(last_name="Corrected")
        with self.assertRaises(ValidationError):
            self.update(revision=original, last_name="Stale change")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.last_name, "Corrected")

    def test_failed_audit_rolls_back_customer_and_contact_history(self):
        self.update(email="second@example.invalid")
        with patch("core.customers.audit", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                self.update(email="third@example.invalid")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "second@example.invalid")
        self.assertFalse(CustomerComment.objects.exists())

    def test_comment_edits_preserve_author_and_full_audit(self):
        comment = save_comment(
            actor=self.staff, customer_id=self.customer.pk, body="Call (202) 555-0199"
        )
        self.assertEqual(comment.search_digits, "2025550199")
        edited = save_comment(
            actor=self.owner,
            customer_id=self.customer.pk,
            comment_id=comment.pk,
            revision=1,
            body="Corrected note",
        )
        self.assertEqual(edited.author, self.staff)
        self.assertEqual(edited.revision, 2)
        event = AuditEvent.objects.get(action="customer.comment_updated")
        self.assertEqual(event.changes["before"], "Call (202) 555-0199")
        with self.assertRaises(ValidationError):
            save_comment(
                actor=self.staff,
                customer_id=self.customer.pk,
                comment_id=comment.pk,
                revision=1,
                body="Outdated note",
            )

    def test_archived_email_comment_is_not_editable(self):
        self.update(email="second@example.invalid")
        self.update(email="third@example.invalid")
        comment = CustomerComment.objects.get()
        with self.assertRaises(ValidationError):
            save_comment(
                actor=self.owner,
                customer_id=self.customer.pk,
                comment_id=comment.pk,
                revision=1,
                body="Erase history",
            )

    def test_phone_letters_not_silently_removed(self):
        with self.assertRaises(ValidationError):
            self.update(phone="202CALL5550101", move_previous_phone="yes")


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class CustomerPageTests(TestCase):
    def setUp(self):
        self.staff = staff_user()
        self.owner = staff_user("owner", owner=True)
        self.customer = create_customer(
            actor=self.staff,
            last_name="Test Family",
            phone="2025550100",
            email="family@example.invalid",
        )
        self.client.force_login(self.staff)

    def test_customer_creation_and_contact_form_roundtrip(self):
        response = self.client.post(
            "/staff/customers/new/",
            {
                "last_name": "Another",
                "phone": "+1 (202) 555-0101",
                "email": "other@example.invalid",
            },
        )
        other = Customer.objects.get(last_name="Another")
        self.assertRedirects(response, f"/staff/customers/{other.pk}/")
        response = self.client.post(
            f"/staff/customers/{other.pk}/edit/",
            {
                "last_name": "Another",
                "phone": "2025550102",
                "email": other.email,
                "revision": other.revision,
                "move_previous_phone": "yes",
            },
        )
        self.assertRedirects(response, f"/staff/customers/{other.pk}/")
        other.refresh_from_db()
        self.assertEqual(other.previous_phone, "2025550101")

    def test_search_labels_current_phone_and_punctuated_comment_matches(self):
        save_comment(actor=self.staff, customer_id=self.customer.pk, body="Director (202) 555-0199")
        response = self.client.get("/staff/customers/", {"q": "(202) 555-0199"})
        self.assertContains(response, "Matched: Comment")
        response = self.client.get("/staff/customers/", {"q": "+1 (202) 555-0100"})
        self.assertContains(response, "Matched: Current phone")

    def test_all_customer_routes_require_permissions(self):
        self.client.logout()
        self.assertEqual(self.client.get("/staff/customers/").status_code, 302)
        denied = get_user_model().objects.create_user(username="denied", is_staff=True)
        self.client.force_login(denied)
        for url in (
            "/staff/customers/",
            "/staff/customers/new/",
            f"/staff/customers/{self.customer.pk}/",
            f"/staff/customers/{self.customer.pk}/edit/",
            f"/staff/customers/{self.customer.pk}/history/",
        ):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_staff_forged_customer_type_cannot_change_type(self):
        response = self.client.post(
            f"/staff/customers/{self.customer.pk}/edit/",
            {
                "last_name": "Test Family",
                "phone": self.customer.phone,
                "email": self.customer.email,
                "revision": self.customer.revision,
                "customer_type": "day_camp",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.customer_type, "family")

    def test_previous_number_correction_is_owner_only(self):
        self.assertEqual(
            self.client.get(f"/staff/customers/{self.customer.pk}/previous-phone/").status_code, 403
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(f"/staff/customers/{self.customer.pk}/previous-phone/").status_code, 200
        )

    def test_comments_escape_html_and_edit_history_is_accessible(self):
        save_comment(
            actor=self.staff, customer_id=self.customer.pk, body='<script>alert("test")</script>'
        )
        response = self.client.get(f"/staff/customers/{self.customer.pk}/")
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;")
        self.assertContains(
            self.client.get(f"/staff/customers/{self.customer.pk}/history/"),
            "Comment added",
        )

    def test_no_booking_counts_and_multiple_today_bookings(self):
        response = self.client.get(f"/staff/customers/{self.customer.pk}/")
        self.assertContains(response, "Other bookings: 0 upcoming · 0 previous")
        start = timezone.localtime().replace(hour=11, minute=30, second=0, microsecond=0)
        for offset in (0, 1):
            session = Session.objects.create(
                starts_at=start + timedelta(minutes=offset), ends_at=start + timedelta(minutes=75)
            )
            Booking.objects.create(customer=self.customer, session=session, children=1, adults=1)
        response = self.client.get(f"/staff/customers/{self.customer.pk}/")
        self.assertContains(response, "View 1 more booking today")

    def test_customer_change_requires_csrf(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.staff)
        self.assertEqual(
            protected.post("/staff/customers/new/", {"last_name": "Blocked"}).status_code, 403
        )

    def test_comment_cannot_be_edited_through_another_customer(self):
        other = create_customer(
            actor=self.staff, last_name="Other", phone="2025550101", email="other@example.invalid"
        )
        comment = save_comment(actor=self.staff, customer_id=other.pk, body="Private comment")
        self.assertEqual(
            self.client.get(
                f"/staff/customers/{self.customer.pk}/comments/{comment.pk}/"
            ).status_code,
            404,
        )

    def test_unicode_search_does_not_raise_numeric_conversion_error(self):
        create_customer(
            actor=self.staff,
            last_name="² Family",
            phone="2025550109",
            email="unicode@example.invalid",
        )
        self.assertContains(self.client.get("/staff/customers/", {"q": "²"}), "² Family")

    def test_comment_permission_also_protects_search_edit_and_audit_history(self):
        comment = save_comment(
            actor=self.staff, customer_id=self.customer.pk, body="Sensitive staff note"
        )
        limited = get_user_model().objects.create_user(username="limited", is_staff=True)
        limited.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core",
                codename__in=["view_customer", "view_customer_history", "change_customercomment"],
            )
        )
        self.client.force_login(limited)
        self.assertNotContains(
            self.client.get(f"/staff/customers/{self.customer.pk}/"), "Sensitive staff note"
        )
        self.assertNotContains(
            self.client.get(f"/staff/customers/{self.customer.pk}/history/"), "Sensitive staff note"
        )
        self.assertNotContains(
            self.client.get("/staff/customers/", {"q": "Sensitive staff note"}), "Test Family"
        )
        self.assertEqual(
            self.client.get(
                f"/staff/customers/{self.customer.pk}/comments/{comment.pk}/"
            ).status_code,
            403,
        )

    def test_database_rejects_unnormalized_phone_and_invalid_revision(self):
        for changes in ({"phone": "202555010"}, {"previous_phone": "bad"}, {"revision": 0}):
            with (
                self.subTest(changes=changes),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                Customer.objects.filter(pk=self.customer.pk).update(**changes)

    def test_customer_view_does_not_bypass_booking_permission(self):
        limited = get_user_model().objects.create_user(username="customer-only", is_staff=True)
        limited.user_permissions.add(
            Permission.objects.get(content_type__app_label="core", codename="view_customer")
        )
        self.client.force_login(limited)
        response = self.client.get(f"/staff/customers/{self.customer.pk}/")
        self.assertContains(response, "Booking access is not enabled for this account.")
        self.assertNotContains(response, "Other bookings:")
