"""Filtered financial exports include unused visit money without creating receipts."""

import csv
import io
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.membership_arrival_pending import complete
from core.membership_records import MembershipArrivalReceiptReturn
from core.membership_reporting import reporting_members
from core.membership_source_exports import source_event_rows, source_rows
from core.models import AuditEvent, FinancialPosting, PaymentOperation
from tests import test_membership_arrival_cancelled_closure as cancelled_fixtures
from tests import test_membership_arrival_returns as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class ArrivalFundExportTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PendingReturnTests.prepare
    start = fixtures.PendingReturnTests.start
    mixed = fixtures.PendingReturnTests.mixed
    accept = fixtures.PendingReturnTests.accept
    result = fixtures.PendingReturnTests.result
    paid = fixtures.PendingReturnTests.paid
    give_back = fixtures.PendingReturnTests.give_back
    owner_finish = fixtures.PendingReturnTests.owner_finish
    unresolved = cancelled_fixtures.CancelledMembershipClosureTests.unresolved
    cancelled = cancelled_fixtures.CancelledMembershipClosureTests.cancelled
    returned = cancelled_fixtures.CancelledMembershipClosureTests.returned
    stop = cancelled_fixtures.CancelledMembershipClosureTests.stop

    def export(self, report="arrival_funds", **filters):
        response = self.client.post(
            reverse("active_memberships"), dict(action="export", report=report, **filters)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("attachment", response["Content-Disposition"])
        return list(
            csv.DictReader(io.StringIO(b"".join(response.streaming_content).decode("utf-8-sig")))
        )

    def test_unknown_member_payment_retains_four_actual_sources_and_no_visit_application(self):
        self.mixed()
        self.accept()
        self.result("unknown")
        complete(self.intent.pk)
        verified_owner_login(self.client, self.owner)
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with patch("core.payments.operations.Gateway") as gateway:
            rows = self.export()
            gateway.assert_not_called()
        self.assertEqual(len(rows), 4)
        self.assertEqual({row["environment"] for row in rows}, {"sandbox"})
        self.assertEqual({row["currency"] for row in rows}, {"USD"})
        self.assertEqual({row["first_membership_payment_state"] for row in rows}, {"unknown"})
        self.assertEqual(sum(Decimal(r["money_originally_received"]) for r in rows), Decimal("7"))
        self.assertEqual(sum(Decimal(r["unapplied_source_balance"]) for r in rows), Decimal("7"))
        self.assertEqual({row["visit_application_transaction_id"] for row in rows}, {""})
        self.assertEqual(
            before, (PaymentOperation.objects.count(), FinancialPosting.objects.count())
        )

    def test_partial_actual_returns_and_later_invoice_application_are_not_money_twice(self):
        self.paid()
        self.give_back(value="1")
        self.give_back(value="1")
        self.owner_finish()
        verified_owner_login(self.client, self.owner)
        rows = self.export()
        cash = next(row for row in rows if row["tender"] == "cash")
        self.assertEqual(cash["money_originally_received"], "3.00")
        self.assertEqual(cash["unused_money_actually_returned"], "2.00")
        self.assertEqual(cash["original_money_applied_to_visit_invoice"], "1.00")
        self.assertEqual(cash["unapplied_source_balance"], "0.00")
        self.assertEqual({row["current_arrival_status"] for row in rows}, {"completed"})
        history = self.export("arrival_fund_events")
        self.assertEqual(len(history), 10)
        self.assertEqual(sum(Decimal(r["money_received"]) for r in history), Decimal("7"))
        self.assertEqual(
            sum(Decimal(r["unused_money_actually_returned"]) for r in history), Decimal("2")
        )
        self.assertEqual(
            sum(Decimal(r["original_money_applied_to_visit_invoice"]) for r in history),
            Decimal("5"),
        )
        self.assertEqual(len({r["event_id"] for r in history}), len(history))

    def test_source_and_return_events_retain_actual_dates_and_distinct_collecting_actors(self):
        self.paid()
        returned = self.give_back()
        verified_owner_login(self.client, self.owner)
        rows = self.export("arrival_fund_events")
        first = next(r for r in rows if r["tender"] == "cash" and r["event_kind"] == "receipt")
        out = next(r for r in rows if r["event_id"] == str(returned.pk))
        self.assertEqual(first["event_actor_id"], str(self.staff.pk))
        self.assertEqual(out["event_actor_id"], str(self.owner.pk))
        self.assertEqual(out["event_received_or_returned_on"], str(returned.completed_on))
        self.assertEqual(out["source_received_on"], str(self.cash.received_on))
        self.assertTrue(out["event_recorded_at_new_york"].endswith("-05:00"))
        self.assertEqual(out["money_received"], "0.00")
        zelle = next(r for r in rows if r["tender"] == "zelle")
        self.assertEqual(zelle["source_sender"], "Fictional visit sender")
        self.assertNotEqual(zelle["source_received_on"], first["source_received_on"])

    def test_stopped_cancelled_member_keeps_refund_separate_from_actual_visit_returns(self):
        self.returned()
        self.stop()
        verified_owner_login(self.client, self.owner)
        rows = self.export()
        self.assertEqual({r["current_arrival_status"] for r in rows}, {"stopped"})
        self.assertEqual(
            {r["separately_recorded_membership_cancellation_id"] for r in rows},
            {str(self.cancellation.pk)},
        )
        self.assertEqual(
            sum(Decimal(r["unused_money_actually_returned"]) for r in rows), Decimal("7")
        )
        self.assertEqual(sum(Decimal(r["unapplied_source_balance"]) for r in rows), 0)
        self.assertTrue(all(r["arrival_stopped_at_new_york"] for r in rows))
        self.assertFalse(any("membership_refund" in key for key in rows[0]))

    def test_filters_and_audit_rows_use_matching_memberships_and_ignore_pagination(self):
        self.paid()
        verified_owner_login(self.client, self.owner)
        self.assertEqual(len(self.export(customer=self.customer.pk, per_page="10")), 4)
        event = AuditEvent.objects.get(action="membership.export_prepared")
        self.assertEqual(event.changes["report"], "Arrival funds")
        self.assertEqual(event.changes["rows"], 4)
        self.assertEqual(event.changes["filters"], {"customer": str(self.customer.pk)})
        self.assertEqual(self.export(kind="unlimited"), [])
        self.assertEqual(AuditEvent.objects.filter(action="membership.export_prepared").count(), 2)

    def test_exported_contact_text_is_formula_safe_and_private_financial_evidence_is_excluded(self):
        self.paid()
        self.customer.last_name = "=Family()"
        self.customer.save(update_fields=["last_name"])
        verified_owner_login(self.client, self.owner)
        for report in ("arrival_funds", "arrival_fund_events"):
            rows = self.export(report)
            self.assertTrue(all(r["last_name"] == "'=Family()" for r in rows))
            for field in (
                "reason",
                "facts",
                "fingerprint",
                "card_token",
                "provider_customer",
                "waiver",
            ):
                self.assertNotIn(field, rows[0])

    def test_both_reports_require_booking_financial_and_explicit_export_permissions(self):
        self.paid()
        viewer = get_user_model().objects.create_user(username="source-exporter", is_staff=True)
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
        for codename in (None, "view_booking", "view_paymentoperation"):
            if codename:
                viewer.user_permissions.add(Permission.objects.get(codename=codename))
                self.client.force_login(viewer)
            for report in ("arrival_funds", "arrival_fund_events"):
                response = self.client.post(
                    reverse("active_memberships"), dict(action="export", report=report)
                )
                self.assertEqual(
                    response.status_code, 200 if codename == "view_paymentoperation" else 403
                )
                if response.status_code == 200:
                    b"".join(response.streaming_content)
        self.assertEqual(AuditEvent.objects.filter(action="membership.export_prepared").count(), 2)

    def test_summary_and_full_event_history_are_bounded_queries_and_read_only(self):
        self.paid()
        self.give_back()
        before = PaymentOperation.objects.count(), MembershipArrivalReceiptReturn.objects.count()
        records = reporting_members()
        for make in (source_rows, source_event_rows):
            with CaptureQueriesContext(connection) as queries:
                result = list(make(records))
            self.assertLessEqual(len(queries), 2, [q["sql"] for q in queries])
            self.assertGreater(len(result), 4)
        self.assertEqual(
            before,
            (PaymentOperation.objects.count(), MembershipArrivalReceiptReturn.objects.count()),
        )

    def test_failed_audit_does_not_return_a_download_or_change_money(self):
        self.paid()
        verified_owner_login(self.client, self.owner)
        count = PaymentOperation.objects.count()
        with (
            patch(
                "core.membership_exports.AuditEvent.objects.create",
                side_effect=RuntimeError("Fictional audit failure"),
            ),
            self.assertRaisesMessage(RuntimeError, "audit failure"),
        ):
            self.export()
        self.assertEqual(PaymentOperation.objects.count(), count)
        self.assertFalse(AuditEvent.objects.filter(action="membership.export_prepared").exists())
