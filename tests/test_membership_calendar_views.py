"""The existing membership page reviews and saves its corrected dates once."""

from datetime import date

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from core.membership_calendar_records import MembershipCalendarCorrection
from core.models import PaymentOperation
from tests import test_membership_calendar_changes as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS


@override_settings(**SETTINGS)
class MembershipCalendarViewTests(TestCase):
    setUp = fixtures.MembershipCalendarCorrectionTests.setUp
    buy = fixtures.MembershipCalendarCorrectionTests.buy
    prepaid = fixtures.MembershipCalendarCorrectionTests.prepaid

    def prepare(self, staff=False):
        self.prepaid()
        self.actor = self.staff if staff else self.owner
        verified_owner_login(self.client, self.actor)
        self.url = reverse("membership_overview", args=[self.member.pk])
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        form = page.context["calendar_form"]
        return {
            field.html_name: str(field.value()) for field in form if field.value() is not None
        } | {
            "calendar-starts_on": "2027-11-05",
            "calendar-reason": "Customer confirmed the intended dates.",
            "calendar-send_confirmation": "no",
        }

    def test_review_and_confirm_stay_on_the_existing_membership_with_no_payment(self):
        data = self.prepare()
        before = PaymentOperation.objects.count()
        reply = self.client.post(self.url, data | dict(action="calendar_review", format="json"))
        self.assertEqual(reply.status_code, 200, reply.content)
        self.assertIn("Feb 4, 2028", reply.json()["html"])
        self.assertFalse(MembershipCalendarCorrection.objects.exists())
        saved = self.client.post(
            self.url,
            data
            | {
                "action": "calendar_confirm",
                "calendar-reviewed": reply.json()["fingerprint"],
                "calendar-customer_confirmed": "on",
            },
        )
        self.assertRedirects(saved, self.url)
        page = self.client.get(self.url)
        self.assertEqual(page.context["root"].starts_on, date(2027, 11, 5))
        self.assertEqual(page.context["member"].pk, self.member.pk)
        self.assertContains(page, "Membership date history")
        self.assertEqual(PaymentOperation.objects.count(), before)

    def test_staff_date_editor_does_not_require_payment_collection_permission(self):
        data = self.prepare(staff=True)
        permission = Permission.objects.get(
            codename="collect_payment", content_type__app_label="core"
        )
        for group in self.staff.groups.all():
            group.permissions.remove(permission)
        self.staff.user_permissions.remove(permission)
        verified_owner_login(self.client, self.staff)
        self.assertFalse(
            type(self.staff).objects.get(pk=self.staff.pk).has_perm("core.collect_payment")
        )
        reply = self.client.post(self.url, data | dict(action="calendar_review", format="json"))
        self.assertEqual(reply.status_code, 200, reply.content)
        saved = self.client.post(
            self.url,
            data
            | {
                "action": "calendar_confirm",
                "calendar-reviewed": reply.json()["fingerprint"],
                "calendar-customer_confirmed": "on",
            },
        )
        self.assertEqual(saved.status_code, 302)
        self.assertEqual(MembershipCalendarCorrection.objects.get().actor_id, self.staff.pk)

    def test_readonly_history_survives_sales_pause_and_stale_post_fails_clearly(self):
        data = self.prepare()
        reply = self.client.post(self.url, data | dict(action="calendar_review", format="json"))
        self.client.post(
            self.url,
            data
            | {
                "action": "calendar_confirm",
                "calendar-reviewed": reply.json()["fingerprint"],
                "calendar-customer_confirmed": "on",
            },
        )
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            page = self.client.get(self.url)
            self.assertContains(page, "Membership date history")
            self.assertNotContains(page, "Membership drafts")
            self.assertNotContains(page, "data-calendar-correction")
            response = self.client.post(
                self.url, data | dict(action="calendar_review", format="json")
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MembershipCalendarCorrection.objects.count(), 1)

    def test_customer_summary_keeps_membership_until_corrected_expiry(self):
        from datetime import datetime
        from unittest.mock import patch
        from zoneinfo import ZoneInfo

        self.prepare()
        from core.membership_calendar_changes import confirm, review

        values = self.inputs
        confirm(
            **values,
            request_key=self.date_key,
            reviewed=review(**values)["fingerprint"],
            customer_confirmed=True,
        )
        with patch(
            "django.utils.timezone.now",
            return_value=datetime(2028, 2, 2, 12, tzinfo=ZoneInfo("America/New_York")),
        ):
            verified_owner_login(self.client, self.actor)
            page = self.client.get(reverse("customer_detail", args=[self.customer.pk]))
        self.assertEqual(len(page.context["purchased_memberships"]), 1)
        self.assertContains(page, "Feb 4, 2028")
