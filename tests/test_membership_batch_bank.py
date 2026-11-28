"""One verified bank transfer funds separately accepted renewal allocations once."""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.membership_batch_records import MembershipRenewalBatch, MembershipRenewalBatchBank
from core.membership_batch_renewals import confirm, review
from core.membership_exports import payment_rows
from core.membership_records import MembershipPurchase
from core.models import FinancialPosting, PaymentOperation
from core.payment_receipt_evidence import receipt_evidence
from tests import test_membership_batch_renewals as fixtures
from tests import test_membership_batch_views as views
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CombinedRenewalBankTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.CombinedRenewalTests.setUp
    buy = fixtures.CombinedRenewalTests.buy
    prior = fixtures.CombinedRenewalTests.prior
    family = fixtures.CombinedRenewalTests.family
    facts = fixtures.CombinedRenewalTests.facts
    review = fixtures.CombinedRenewalTests.review

    def bank_values(self):
        return dict(
            actor=self.staff,
            customer=self.customer,
            rows=self.rows,
            tender="zelle",
            bank_received_on=date(2027, 10, 29),
            bank_sender="D. Greenfeld",
        )

    def receive(self, **changes):
        values = self.bank_values() | changes
        return confirm(
            **values,
            request_key=self.key,
            reviewed=review(**values)["fingerprint"],
            accepted=True,
            verified_received=True,
        )

    def operations(self, batch):
        return PaymentOperation.objects.filter(
            sale__membership_invoice__installment__purchase__request_key__in=batch.parts.values(
                "purchase_id"
            )
        ).select_related("sale__membership_invoice__installment__purchase")

    def test_bank_review_is_read_only_and_normalizes_actual_receipt_metadata(self):
        self.family()
        before = self.facts()
        data = review(**(self.bank_values() | dict(bank_sender=" D. Greenfeld ")))
        self.assertEqual(data["bank"], dict(received_on="2027-10-29", sender="D. Greenfeld"))
        self.assertEqual(data["amount"], "57.98")
        self.assertEqual(data["received_on"], "2027-10-29")
        self.assertEqual(self.facts(), before)
        self.assertFalse(MembershipRenewalBatchBank.objects.exists())

    def test_one_source_two_allocations_preserve_earlier_bank_date_without_extra_posting(self):
        self.family()
        before = (PaymentOperation.objects.count(), FinancialPosting.objects.count())
        with patch("core.payments.operations.Gateway") as gateway:
            batch = self.receive()
        source = MembershipRenewalBatchBank.objects.get()
        self.assertEqual((source.pk, source.amount), (batch.pk, Decimal("57.98")))
        operations = list(self.operations(batch))
        self.assertEqual(sorted(str(op.amount) for op in operations), ["17.99", "39.99"])
        self.assertTrue(all(op.tender == "zelle" and op.state == "succeeded" for op in operations))
        self.assertTrue(all(op.manual_received_on == date(2027, 10, 29) for op in operations))
        self.assertEqual(PaymentOperation.objects.count(), before[0] + 2)
        self.assertEqual(FinancialPosting.objects.count(), before[1] + 2)
        self.assertEqual(batch.messages.count(), 1)
        for part in batch.parts.all():
            self.assertEqual(part.purchase.origin.purchased_on, date(2027, 10, 31))
        gateway.assert_not_called()
        connection.check_constraints()

    def test_monthly_future_cards_remain_distinct_from_the_received_transfer(self):
        self.family()
        self.rows[0] |= dict(billing="monthly", months=2, method_id=str(self.method.pk))
        batch = self.receive()
        member = batch.parts.order_by("position").first().purchase
        self.assertEqual(member.billing_state.mandate.method_id, self.method.pk)
        self.assertEqual(member.installments.count(), 2)
        self.assertEqual(member.installments.order_by("number").last().quote["total"], "18.53")
        self.assertEqual(self.operations(batch).count(), 2)
        connection.check_constraints()

    def test_invalid_sender_or_future_receipt_date_create_no_bank_or_membership(self):
        self.family()
        before = self.facts()
        for changed in [
            dict(bank_sender=""),
            dict(bank_sender="   "),
            dict(bank_sender="x" * 161),
            dict(bank_received_on=date(2027, 11, 1)),
        ]:
            with self.subTest(changed=changed), self.assertRaises(ValidationError):
                review(**(self.bank_values() | changed))
        self.assertEqual(self.facts(), before)
        self.assertFalse(MembershipRenewalBatchBank.objects.exists())

    def test_changed_bank_details_require_review_before_any_receipt(self):
        self.family()
        values = self.bank_values()
        reviewed = review(**values)["fingerprint"]
        before = self.facts()
        for changed in [
            dict(bank_sender="Another sender"),
            dict(bank_received_on=date(2027, 10, 30)),
        ]:
            with (
                self.subTest(changed=changed),
                self.assertRaisesMessage(ValidationError, "changed"),
            ):
                confirm(
                    **(values | changed),
                    request_key=self.key,
                    reviewed=reviewed,
                    accepted=True,
                    verified_received=True,
                )
        self.assertEqual(self.facts(), before)

    def test_bank_receipt_verification_and_terms_are_both_required(self):
        self.family()
        values = self.bank_values()
        for accepted, verified in [(False, True), (True, False), (True, 1)]:
            with (
                self.subTest(accepted=accepted, verified=verified),
                self.assertRaises(ValidationError),
            ):
                confirm(
                    **values,
                    request_key=self.key,
                    reviewed=review(**values)["fingerprint"],
                    accepted=accepted,
                    verified_received=verified,
                )
        self.assertFalse(MembershipRenewalBatch.objects.exists())

    def test_second_renewal_failure_rolls_back_source_and_all_allocations(self):
        self.family()
        before = self.facts()
        from core.membership_sales import purchase

        calls = []

        def buy(**values):
            calls.append(values)
            if len(calls) == 2:
                raise ValidationError("Synthetic second renewal failure")
            return purchase(**values)

        with (
            patch("core.membership_batch_renewals.purchase", side_effect=buy),
            self.assertRaises(ValidationError),
        ):
            self.receive()
        self.assertEqual(self.facts(), before)
        self.assertFalse(MembershipRenewalBatchBank.objects.exists())

    def test_replay_returns_one_original_source_and_unchanged_allocations(self):
        self.family()
        values = self.bank_values()
        reviewed = review(**values)["fingerprint"]
        batch = self.receive()
        before = self.facts()
        repeated = confirm(
            **values,
            request_key=self.key,
            reviewed=reviewed,
            accepted=True,
            verified_received=True,
        )
        self.assertEqual(repeated.pk, batch.pk)
        self.assertEqual(self.facts(), before)
        self.assertEqual(MembershipRenewalBatchBank.objects.count(), 1)

    def test_runtime_grants_allow_source_insert_without_update_or_delete(self):
        self.family()
        with self.runtime_role():
            batch = self.receive()
            connection.check_constraints()
            for sql in [
                "UPDATE core_membershiprenewalbatchbank SET sender='changed' WHERE batch_id=%s",
                "DELETE FROM core_membershiprenewalbatchbank WHERE batch_id=%s",
            ]:
                with (
                    self.assertRaises(DatabaseError),
                    transaction.atomic(),
                    connection.cursor() as cursor,
                ):
                    cursor.execute(sql, [batch.pk])

    def test_even_schema_owner_cannot_rewrite_or_delete_a_verified_source(self):
        self.family()
        batch = self.receive()
        for sql in [
            "UPDATE core_membershiprenewalbatchbank SET amount=1 WHERE batch_id=%s",
            "DELETE FROM core_membershiprenewalbatchbank WHERE batch_id=%s",
        ]:
            with (
                self.assertRaises(DatabaseError),
                transaction.atomic(),
                connection.cursor() as cursor,
            ):
                cursor.execute(sql, [batch.pk])

    def test_direct_bank_source_cannot_be_added_to_a_cash_checkout(self):
        self.family()
        batch = fixtures.CombinedRenewalTests.confirm(self)
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipRenewalBatchBank.objects.create(
                batch=batch, amount=batch.amount, received_on=batch.received_on, sender="Unrelated"
            )
            connection.check_constraints()

    def test_mismatched_source_amount_cannot_back_accepted_allocations(self):
        self.family()
        create = MembershipRenewalBatchBank.objects.create

        def wrong(**values):
            return create(**(values | dict(amount="1.00")))

        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            patch.object(MembershipRenewalBatchBank.objects, "create", side_effect=wrong),
        ):
            self.receive()
            connection.check_constraints()
        self.assertFalse(MembershipRenewalBatchBank.objects.exists())

    def test_zelle_allocations_cannot_commit_without_the_shared_source(self):
        self.family()
        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            patch.object(MembershipRenewalBatchBank.objects, "create", return_value=None),
        ):
            self.receive()
            connection.check_constraints()
        self.assertFalse(MembershipRenewalBatch.objects.exists())

    def test_payment_history_identifies_one_shared_source_and_separate_allocated_money(self):
        self.family()
        batch = self.receive()
        evidence = receipt_evidence(list(self.operations(batch)))
        self.assertEqual(len(evidence), 2)
        for item in evidence.values():
            self.assertEqual(item["shared_bank_receipt"], str(batch.pk))
            self.assertEqual(item["shared_bank_total"], Decimal("57.98"))
            self.assertEqual(item["sender"], "D. Greenfeld")
            self.assertFalse(item["earlier"])
            self.assertNotIn("receipt_id", item)
        rows = list(
            payment_rows(
                MembershipPurchase.objects.filter(request_key__in=batch.parts.values("purchase_id"))
            )
        )
        exported = [dict(zip(rows[0], row, strict=True)) for row in rows[1:]]
        self.assertEqual(
            sum((row["recorded_total"] for row in exported), Decimal("0")), Decimal("57.98")
        )
        self.assertEqual(
            {row["shared_bank_receipt_reference"] for row in exported}, {str(batch.pk)}
        )
        self.assertTrue(
            all(row["shared_bank_total_reference_only"] == Decimal("57.98") for row in exported)
        )
        verified_owner_login(self.client, self.owner)
        page = self.client.get(reverse("payment_detail", args=[self.operations(batch).first().pk]))
        self.assertContains(page, "allocated from one verified $57.98 transfer")
        self.assertContains(page, "D. Greenfeld")

    def test_refunding_one_allocation_preserves_the_other_and_original_bank_evidence(self):
        from core.membership_cancellations import cancel, request_refund
        from core.membership_cancellations import review as review_cancellation
        from core.payments.invoices import received

        self.family()
        batch = self.receive()
        parts = list(batch.parts.order_by("position"))
        data = review_cancellation(
            actor=self.owner,
            member_id=parts[0].purchase.pk,
            timing="immediate",
            refund_amount="17.99",
        )
        stopped = cancel(
            actor=self.owner,
            member_id=parts[0].purchase.pk,
            timing="immediate",
            refund_amount="17.99",
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            reason="Owner reviewed the original allocated bank receipt.",
            early_override=True,
            send_confirmation=False,
        )
        plan = stopped.refund_plans.get()
        with patch("core.payments.operations.Gateway") as gateway:
            attempt = request_refund(
                actor=self.owner,
                plan_id=plan.pk,
                request_key=uuid.uuid4(),
                confirmed=True,
                manual_returned=True,
            )
        attempt.operation.refresh_from_db()
        self.assertEqual(attempt.operation.tender, "zelle")
        self.assertEqual(attempt.operation.state, "succeeded")
        self.assertEqual(received(plan.original.sale), Decimal("0.00"))
        other_sale = parts[1].purchase.installments.first().invoice.sale
        self.assertEqual(received(other_sale), Decimal("39.99"))
        batch.bank_receipt.refresh_from_db()
        self.assertEqual(batch.bank_receipt.amount, Decimal("57.98"))
        self.assertEqual(batch.bank_receipt.sender, "D. Greenfeld")
        self.assertEqual(MembershipRenewalBatchBank.objects.count(), 1)
        gateway.assert_not_called()
        connection.check_constraints()

    def test_same_page_bank_review_confirm_and_readonly_history(self):
        data = views.CombinedRenewalViewTests.prepare(self)
        data |= dict(tender="zelle", bank_received_on="2027-10-29", bank_sender="D. Greenfeld")
        before = self.facts()
        reviewed = self.client.post(self.url, data | dict(format="json"))
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertEqual(self.facts(), before)
        response = self.client.post(
            self.url,
            data
            | dict(
                action="confirm",
                reviewed=reviewed.json()["fingerprint"],
                accepted="on",
                verified_received="on",
            ),
        )
        self.assertEqual(response.status_code, 302)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            page = self.client.get(response.url)
        self.assertContains(page, "One verified bank transfer")
        self.assertContains(page, "Oct 29, 2027")
        self.assertContains(page, "D. Greenfeld")
        self.assertEqual(MembershipRenewalBatchBank.objects.count(), 1)
