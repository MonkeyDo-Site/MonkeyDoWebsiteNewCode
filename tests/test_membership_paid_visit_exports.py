"""Financial exports distinguish original funds, new money and converted credit."""

import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.membership_paid_visit_exports import paid_visit_rows
from core.membership_paid_visit_pending import complete, stop, stop_facts
from core.membership_reporting import reporting_members
from core.membership_sales import offer, purchase
from core.models import AuditEvent, FinancialPosting, PaymentOperation
from core.payments.ledger import record_result
from core.payments.operations import begin_dispatch
from tests import test_membership_paid_visit_manual as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitExportTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PaidVisitManualTests.prepare
    buy_card = fixtures.PaidVisitManualTests.buy_card
    decline = fixtures.PaidVisitManualTests.decline
    setup_decline = fixtures.PaidVisitManualTests.setup_decline
    prepare_manual = fixtures.PaidVisitManualTests.prepare_manual
    receive = fixtures.PaidVisitManualTests.receive
    cancel_received = fixtures.PaidVisitManualTests.cancel_received

    def export(self, report="paid_visit_events", **filters):
        response = self.client.post(
            reverse("active_memberships"), dict(action="export", report=report, **filters)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        return list(
            csv.DictReader(io.StringIO(b"".join(response.streaming_content).decode("utf-8-sig")))
        )

    def sums(self, rows):
        fields = (
            "original_visit_invoice_funds",
            "new_membership_money_received",
            "converted_credit_created",
            "converted_credit_applied_to_membership",
            "unused_card_fee_removed",
        )
        return tuple(sum((Decimal(row[key]) for row in rows), Decimal("0")) for key in fields)

    def test_unknown_remainder_shows_original_invoice_funds_without_new_money_or_credit(self):
        self.buy_card()
        begin_dispatch(self.operation.pk)
        record_result(operation_id=self.operation.pk, state="unknown", source="provider")
        verified_owner_login(self.client, self.owner)
        counts = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with patch("core.payments.operations.Gateway") as gateway:
            rows = self.export()
        gateway.assert_not_called()
        self.assertEqual(self.sums(rows), tuple(map(Decimal, ("16.47", "0", "0", "0", "0"))))
        member = next(row for row in rows if row["event_kind"] == "membership_transaction")
        self.assertEqual((member["state"], member["requested_amount"]), ("unknown", "2.03"))
        self.assertEqual(
            counts, (PaymentOperation.objects.count(), FinancialPosting.objects.count())
        )

    def test_known_receipt_then_conversion_never_turn_credit_into_more_money(self):
        self.prepare_manual()
        self.receive()
        verified_owner_login(self.client, self.owner)
        self.assertEqual(
            self.sums(self.export()), tuple(map(Decimal, ("16.47", "1.97", "0", "0", ".06")))
        )
        complete(self.intent.pk)
        rows = self.export()
        self.assertEqual(
            self.sums(rows), tuple(map(Decimal, ("16.47", "1.97", "16.02", "16.02", ".06")))
        )
        source = next(row for row in rows if row["event_kind"] == "visit_credit_created")
        self.assertEqual(
            (
                source["converted_principal"],
                source["reversed_item_tax"],
                source["reversed_fee_tax"],
            ),
            ("15.00", "0.99", "0.03"),
        )
        self.assertEqual(len({row["event_reference"] for row in rows}), len(rows))

    def test_original_invoice_is_not_repeated_for_a_stopped_then_replaced_purchase(self):
        self.setup_decline()
        facts = stop_facts(self.intent)
        stop(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=facts["fingerprint"],
            reason="Review a new purchase",
        )
        data = offer(**self.options)
        purchase(
            **self.options,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            accepted=True,
            method_id=self.method.pk,
        )
        verified_owner_login(self.client, self.owner)
        rows = self.export()
        self.assertEqual(self.sums(rows)[0], Decimal("16.47"))
        original = [row for row in rows if row["event_kind"] == "original_visit_transaction"]
        self.assertEqual(len(original), 1)
        self.assertEqual(len(original[0]["memberships"].split("; ")), 2)

    def test_zelle_bank_date_sender_and_cash_receipt_metadata_stay_distinct(self):
        self.prepare_manual()
        bank_date = timezone.localdate() - timedelta(days=1)
        receipt = self.receive(
            tender="zelle", sender_name="Fictional bank sender", received_on=bank_date
        )
        verified_owner_login(self.client, self.owner)
        rows = self.export("payments")
        row = next(row for row in rows if row["tender"] == "zelle")
        self.assertEqual(
            (row["manual_received_on"], row["recorded_sender"], row["receipt_origin"]),
            (str(bank_date), "Fictional bank sender", "Received replacement payment"),
        )
        page = self.client.get(reverse("payment_detail", args=[receipt.operation.pk]))
        self.assertContains(page, "Sender recorded from bank")
        self.assertContains(page, "Fictional bank sender")
        self.assertNotContains(page, "Refresh provider settlement status")
        pending = self.client.get(reverse("membership_overview", args=[self.member.pk]))
        self.assertContains(pending, "Recorded bank receipt date")
        self.assertContains(pending, "Fictional bank sender")
        history = self.export()
        new = next(row for row in history if row["tender"] == "zelle")
        self.assertEqual(
            (new["actual_receipt_or_return_on"], new["recorded_sender"]),
            (str(bank_date), "Fictional bank sender"),
        )

    def test_existing_membership_does_not_relabel_its_earlier_purchase_as_new_visit_money(self):
        booking, sale, member, converted = self.conversion(card=True)
        verified_owner_login(self.client, self.owner)
        rows = self.export()
        self.assertEqual(self.sums(rows)[0], Decimal("16.47"))
        self.assertEqual(self.sums(rows)[1], Decimal("0"))
        self.assertFalse(any(row["event_kind"] == "membership_transaction" for row in rows))
        self.assertEqual(self.sums(rows)[2], Decimal("16.02"))

    def test_filters_audit_and_formula_safe_bank_sender(self):
        self.prepare_manual()
        self.receive(tender="zelle", sender_name="=BANK()")
        verified_owner_login(self.client, self.owner)
        rows = self.export(customer=self.customer.pk, per_page="10")
        self.assertTrue(any(row["recorded_sender"] == "'=BANK()" for row in rows))
        audit = AuditEvent.objects.get(action="membership.export_prepared")
        self.assertEqual(audit.changes["report"], "Paid visit application history")
        self.assertEqual(audit.changes["rows"], len(rows))
        self.assertEqual(audit.changes["filters"], {"customer": str(self.customer.pk)})
        self.assertEqual(self.export(kind="unlimited"), [])

    def test_financial_export_requires_both_booking_and_payment_permissions(self):
        self.buy_card()
        user = get_user_model().objects.create_user(username="fund-history-exporter", is_staff=True)
        user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=[
                    "view_customer",
                    "view_membershippurchase",
                    "export_membership_records",
                ],
                content_type__app_label="core",
            )
        )
        self.client.force_login(user)
        for permission in (None, "view_booking", "view_paymentoperation"):
            if permission:
                user.user_permissions.add(Permission.objects.get(codename=permission))
                self.client.force_login(user)
            response = self.client.post(
                reverse("active_memberships"), dict(action="export", report="paid_visit_events")
            )
            self.assertEqual(
                response.status_code, 200 if permission == "view_paymentoperation" else 403
            )
            if response.status_code == 200:
                b"".join(response.streaming_content)

    def test_history_queries_are_batched_and_financial_facts_remain_read_only(self):
        self.prepare_manual()
        self.receive()
        complete(self.intent.pk)
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with self.runtime_role(), CaptureQueriesContext(connection) as queries:
            rows = list(paid_visit_rows(reporting_members()))
        self.assertLessEqual(len(queries), 22)
        self.assertGreater(len(rows), 5)
        self.assertEqual(
            before, (PaymentOperation.objects.count(), FinancialPosting.objects.count())
        )

    def test_recorded_refund_and_uncollected_writeoff_are_separate_from_original_money(self):
        from core.membership_cancellations import request_refund
        from core.membership_paid_visit_cancellation import release, review

        self.cancel_received()
        request_refund(
            actor=self.owner,
            plan_id=self.cancelled.refund_plans.get().pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
        )
        facts = review(actor=self.owner, intent=self.intent)
        release(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=facts["fingerprint"],
            reason="Return original funds to availability",
            confirmed=True,
        )
        verified_owner_login(self.client, self.owner)
        rows = self.export()
        self.assertEqual(self.sums(rows), tuple(map(Decimal, ("16.47", "1.97", "0", "0", ".06"))))
        self.assertEqual(
            sum(Decimal(row["new_membership_money_returned"]) for row in rows), Decimal("1.97")
        )
        self.assertEqual(
            sum(Decimal(row["uncollected_membership_amount_cancelled"]) for row in rows),
            Decimal("16.02"),
        )
        self.assertEqual(
            sum(Decimal(row["original_visit_money_returned"]) for row in rows), Decimal("0")
        )

    def test_a_failed_export_audit_does_not_send_a_download_or_change_finances(self):
        self.prepare_manual()
        self.receive()
        verified_owner_login(self.client, self.owner)
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with patch(
            "core.membership_exports.AuditEvent.objects.create",
            side_effect=RuntimeError("Audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.export()
        self.assertEqual(
            before, (PaymentOperation.objects.count(), FinancialPosting.objects.count())
        )

    def test_payment_page_handles_absent_later_receipt_tables_without_inventing_a_sender(self):
        self.prepare_manual()
        record = self.receive(tender="zelle", sender_name="Only in the later typed record")
        verified_owner_login(self.client, self.owner)
        names = connection.introspection.table_names()
        prior = [name for name in names if name != "core_membershippaidvisitmanualpayment"]
        with patch.object(connection.introspection, "table_names", return_value=prior):
            page = self.client.get(reverse("payment_detail", args=[record.operation.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Only in the later typed record")

    def test_source_and_new_fees_are_reported_independently_from_retained_credit(self):
        self.buy_card()
        begin_dispatch(self.operation.pk)
        record_result(
            operation_id=self.operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="996001",
        )
        complete(self.intent.pk)
        verified_owner_login(self.client, self.owner)
        rows = self.export()
        self.assertEqual(
            sum(Decimal(row["original_processing_fee_recorded"]) for row in rows), Decimal(".45")
        )
        self.assertEqual(
            sum(Decimal(row["original_processing_fee_retained"]) for row in rows), Decimal(".45")
        )
        self.assertEqual(
            sum(Decimal(row["new_membership_processing_fee_received"]) for row in rows),
            Decimal(".06"),
        )
        self.assertEqual(
            self.sums(rows), tuple(map(Decimal, ("16.47", "2.03", "16.02", "16.02", "0")))
        )

    def test_initial_received_split_retains_its_own_bank_evidence(self):
        from tests import test_membership_paid_visit_received_split as splits

        splits.PaidVisitReceivedSplitTests.options_for_split(self)
        splits.PaidVisitReceivedSplitTests.buy_split(self)
        verified_owner_login(self.client, self.owner)
        rows = self.export("payments")
        bank = next(row for row in rows if row["tender"] == "zelle")
        self.assertEqual(bank["recorded_sender"], "Fictional bank sender")
        self.assertEqual(bank["receipt_origin"], "Received first payment")
        history = self.export()
        self.assertEqual(
            self.sums(history), tuple(map(Decimal, ("16.47", "1.97", "16.02", "16.02", "0")))
        )


@override_settings(**SETTINGS)
class MembershipReceiptEvidenceTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    from tests import test_membership_arrival_zelle as zelle_fixtures
    from tests import test_membership_booking_zelle as bank_fixtures

    prepare = zelle_fixtures.SeparateMembershipZelleTests.prepare
    split_visit = zelle_fixtures.SeparateMembershipZelleTests.split_visit
    confirm_split = zelle_fixtures.SeparateMembershipZelleTests.confirm_split
    bank_transfer = zelle_fixtures.SeparateMembershipZelleTests.bank_transfer
    start = bank_fixtures.MembershipBookingZelleTests.start
    commit = bank_fixtures.MembershipBookingZelleTests.commit
    export = PaidVisitExportTests.export

    def test_separate_new_membership_zelle_retains_verified_sender_on_payment_page_and_export(self):
        self.bank_transfer()
        checkout = self.confirm_split(verified_received=False)
        operation = checkout.purchase.installments.first().invoice.sale.operations.get()
        verified_owner_login(self.client, self.owner)
        page = self.client.get(reverse("payment_detail", args=[operation.pk]))
        self.assertContains(page, "Fictional membership sender")
        bank = next(row for row in self.export("payments") if row["tender"] == "zelle")
        self.assertEqual(
            (bank["manual_received_on"], bank["recorded_sender"], bank["receipt_origin"]),
            (str(self.bank_day), "Fictional membership sender", "Received membership Zelle"),
        )

    def test_prior_booking_zelle_is_identified_as_earlier_money_with_original_bank_date(self):
        self.start()
        self.options["actor"] = self.owner
        self.commit()
        verified_owner_login(self.client, self.owner)
        bank = next(row for row in self.export("payments") if row["tender"] == "zelle")
        self.assertEqual(
            (bank["recorded_sender"], bank["receipt_origin"], bank["earlier_receipt_reference"]),
            ("Fictional original bank transfer", "Earlier receipt applied", str(self.bank.pk)),
        )
        operation = PaymentOperation.objects.get(pk=bank["transaction_id"])
        self.assertEqual(operation.actor_id, self.owner.pk)
        self.assertEqual(bank["earlier_receipt_recorded_by_id"], str(self.staff.pk))
        self.assertTrue(bank["earlier_receipt_recorded_at_new_york"])
        page = self.client.get(reverse("payment_detail", args=[operation.pk]))
        self.assertContains(page, "Earlier receipt applied to this invoice")
        self.assertContains(page, "Fictional original bank transfer")
