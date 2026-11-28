import csv
import io
import uuid
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.account_forms import StaffAccountForm
from core.membership_cancellations import cancel
from core.membership_cancellations import review as cancellation_review
from core.membership_reporting import filtered_members, reporting_members
from core.membership_sales import membership_status
from core.models import AuditEvent, FinancialPosting, PaymentOperation
from tests import test_customer_credit_corrections as credit_fixtures
from tests import test_membership_sales as fixtures
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES

SETTINGS = dict(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake",
)


@override_settings(**SETTINGS)
class MembershipReportingTests(TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    succeed = fixtures.MembershipPurchaseTests.succeed

    def buy(self, **changes):
        self.key = uuid.uuid4()
        return fixtures.MembershipPurchaseTests.buy(self, **changes)

    def ids(self, params):
        records, form, _ = filtered_members(params)
        self.assertTrue(form.is_valid(), form.errors)
        return set(records.values_list("pk", flat=True))

    def csv(self, report="memberships", **filters):
        response = self.client.post(
            reverse("active_memberships"), dict(action="export", report=report, **filters)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        content = b"".join(response.streaming_content).decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(content)))

    def test_status_query_matches_actual_eligibility_across_calendar_and_collection_states(self):
        pending = self.buy()
        active = self.buy(expected_method="cash", verified_received=True)
        future = self.buy(
            expected_method="cash", verified_received=True, starts_on=date(2027, 11, 2)
        )
        complimentary = self.buy(actor=self.owner, comped=True, months=1, send_confirmation=False)
        for on in (date(2027, 10, 31), date(2027, 11, 30), date(2027, 12, 1), date(2028, 2, 1)):
            for row in reporting_members(on=on):
                self.assertEqual(row.report_status, membership_status(row, on=on), (row.pk, on))
        self.assertEqual(self.ids({"status": "pending"}), {pending.pk})
        self.assertEqual(self.ids({"status": "scheduled"}), {future.pk})
        self.assertEqual(self.ids({"status": "active"}), {active.pk, complimentary.pk})
        with CaptureQueriesContext(connection) as queries:
            list(reporting_members())
        self.assertLessEqual(len(queries), 4)

    def test_effective_cancellation_end_is_filtered_without_rewriting_original_term(self):
        member = self.buy(expected_method="cash", verified_received=True)
        data = cancellation_review(
            actor=self.owner, member_id=member.pk, timing="end_cycle", refund_amount="0.00"
        )
        cancel(
            actor=self.owner,
            member_id=member.pk,
            timing="end_cycle",
            refund_amount="0.00",
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Reviewed.",
            early_override=True,
            send_confirmation=False,
        )
        member.refresh_from_db()
        row = reporting_members().get(pk=member.pk)
        self.assertEqual(row.effective_ends_on, date(2027, 11, 30))
        self.assertEqual(member.membership.ends_on, date(2028, 1, 30))
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=26)):
            self.assertIn(member.pk, self.ids({"expiry": "soon"}))
        self.assertIn(
            member.pk,
            self.ids({"expiry": "custom", "ends_from": "2027-11-30", "ends_to": "2027-11-30"}),
        )
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=32)):
            row = reporting_members().get(pk=member.pk)
            self.assertEqual(row.report_status, membership_status(row))
            self.assertEqual(row.report_status, "cancelled")

    def test_search_typo_phone_membership_customer_type_and_invalid_ranges(self):
        member = self.buy()
        self.assertIn(member.pk, self.ids({"q": "(202) 555-0100"}))
        self.assertIn(member.pk, self.ids({"q": "family@example.invalid"}))
        self.assertIn(member.pk, self.ids({"q": "#" + member.membership_number}))
        self.assertIn(
            member.pk, self.ids({"customer": str(self.customer.pk), "kind": "subscription"})
        )
        self.assertNotIn(member.pk, self.ids({"kind": "unlimited"}))
        self.client.force_login(self.staff)
        page = self.client.get(reverse("active_memberships"), {"q": "Grenfeld"})
        self.assertContains(page, "Possible Last Name match")
        for params in (
            {"ends_from": "2027-11-30", "ends_to": "2027-10-31"},
            {"ends_from": "yesterday"},
            {"status": "invented"},
            {"customer": "bad"},
        ):
            records, form, _ = filtered_members(params)
            self.assertFalse(form.is_valid())
            self.assertFalse(records.exists())

    def test_export_all_matching_pages_and_safe_contact_cells_with_exact_audit(self):
        for _ in range(12):
            self.buy(expected_method="cash", verified_received=True)
        self.customer.last_name = '=HYPERLINK("https://example.invalid","Family")'
        self.customer.save(update_fields=["last_name"])
        verified_owner_login(self.client, self.owner)
        rows = self.csv(kind="subscription", status="active", per_page="10")
        self.assertEqual(len(rows), 12)
        self.assertTrue(rows[0]["last_name"].startswith("'="))
        event = AuditEvent.objects.get(action="membership.export_prepared")
        self.assertEqual(event.changes["rows"], 12)
        self.assertNotIn("csrfmiddlewaretoken", event.changes["filters"])
        self.assertEqual(event.changes["filters"], {"kind": "subscription", "status": "active"})
        self.assertContains(self.client.get(reverse("membership_export_history")), "12 rows")
        self.assertContains(self.client.get(reverse("membership_export_history")), "Status: Active")

    def test_payment_export_preserves_pending_amount_and_actual_receipts_separately(self):
        pending = self.buy()
        paid = self.buy(expected_method="cash", verified_received=True)
        count = FinancialPosting.objects.count(), PaymentOperation.objects.count()
        verified_owner_login(self.client, self.owner)
        rows = self.csv("payments")
        self.assertEqual(len(rows), 2)
        requested = next(row for row in rows if row["membership"] == pending.membership_number)
        received = next(row for row in rows if row["membership"] == paid.membership_number)
        self.assertEqual(requested["requested_amount"], "37.06")
        self.assertEqual(requested["recorded_total"], "0.00")
        self.assertEqual(received["recorded_total"], "35.98")
        self.assertEqual(received["recorded_processing_fee"], "0.00")
        self.assertEqual(received["environment"], "sandbox")
        self.assertEqual(
            count, (FinancialPosting.objects.count(), PaymentOperation.objects.count())
        )
        self.assertNotIn("provider_customer", received)

    def test_export_requires_explicit_permission_and_owner_only_history_and_csrf(self):
        self.buy()
        self.client.force_login(self.staff)
        url = reverse("active_memberships")
        values = dict(action="export", report="memberships")
        self.assertNotContains(self.client.get(url), "Export filtered memberships")
        self.assertEqual(self.client.post(url, values).status_code, 403)
        self.staff.user_permissions.add(
            Permission.objects.get(codename="export_membership_records")
        )
        self.client.force_login(self.staff)
        self.assertEqual(len(self.csv()), 1)
        self.assertEqual(self.client.get(reverse("membership_export_history")).status_code, 403)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.staff)
        self.assertEqual(csrf.post(url, values).status_code, 403)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertEqual(self.client.post(url, values).status_code, 404)

    def test_normal_staff_powers_are_assignable_but_exports_are_not_default(self):
        form = StaffAccountForm()
        available = set(form.fields["permissions"].queryset.values_list("codename", flat=True))
        defaults = set(form.initial["permissions"].values_list("codename", flat=True))
        self.assertTrue(
            {"view_membershippurchase", "add_membershippurchase", "change_membershippurchase"}
            <= defaults
        )
        self.assertIn("export_membership_records", available)
        self.assertNotIn("export_membership_records", defaults)
        self.assertNotIn("review_payment", available)

    def test_report_specific_permissions_and_invalid_filters_do_not_export(self):
        self.buy()
        viewer = get_user_model().objects.create_user(username="membership-exporter", is_staff=True)
        viewer.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core",
                codename__in=[
                    "view_customer",
                    "view_membershippurchase",
                    "export_membership_records",
                ],
            )
        )
        self.client.force_login(viewer)
        url = reverse("active_memberships")
        for report in ("payments", "benefits", "unknown"):
            self.assertEqual(
                self.client.post(url, dict(action="export", report=report)).status_code, 403
            )
        invalid = self.client.post(
            url, dict(action="export", report="memberships", ends_from="bad")
        )
        self.assertContains(invalid, "Enter a valid date")
        self.assertFalse(AuditEvent.objects.filter(action="membership.export_prepared").exists())


@override_settings(**SETTINGS)
class MembershipReportingCreditTests(credit_fixtures.CreditFixtures, TestCase):
    def test_credit_funding_and_source_hold_have_same_status_in_reports_and_overview(self):
        from core.customer_credit import apply, review

        _, source, member, _ = self.conversion(card=True)
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            values = self.due(member)
            data = review(**values)
            apply(**values, reviewed=data["fingerprint"], request_key=uuid.uuid4(), confirmed=True)
            row = reporting_members().get(pk=member.pk)
            self.assertEqual(row.report_status, membership_status(row))
            self.assertEqual(row.report_status, "overdue")
            self.external_return(source.operations.get())
            row = reporting_members().get(pk=member.pk)
            self.assertEqual(row.report_status, membership_status(row))
            self.assertEqual(row.report_status, "review")

    def test_benefit_export_retains_reserved_used_and_released_evidence(self):
        _, _, member, _ = self.conversion()
        verified_owner_login(self.client, self.owner)
        response = self.client.post(
            reverse("active_memberships"),
            dict(action="export", report="benefits", customer=self.customer.pk),
        )
        self.assertEqual(response.status_code, 200)
        content = b"".join(response.streaming_content).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["event_state"] for row in rows}, {"reserved", "used"})
        self.assertEqual(rows[0]["membership"], member.membership_number)
        self.assertEqual(rows[0]["current_state"], "used")
        self.assertEqual(rows[0]["admission_price"], "0.00")
        from core.membership_reservations import finish

        finish(
            actor=self.owner,
            booking_id=int(rows[0]["booking"]),
            request_key=uuid.uuid4(),
            action="released",
            reason="owner_correction",
        )
        response = self.client.post(
            reverse("active_memberships"),
            dict(action="export", report="benefits", customer=self.customer.pk),
        )
        changed = list(
            csv.DictReader(io.StringIO(b"".join(response.streaming_content).decode("utf-8-sig")))
        )
        self.assertEqual(len(changed), 3)
        self.assertEqual({row["event_state"] for row in changed}, {"reserved", "used", "released"})
        self.assertEqual({row["current_state"] for row in changed}, {"released"})
