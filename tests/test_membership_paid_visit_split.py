"""A partial receipt and exact card remainder never spend the original visit twice."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings

from core.customer_credit import applied
from core.customer_credit_records import VisitMembershipConversion
from core.membership_paid_visit_pending import complete, stop_facts
from core.membership_paid_visit_split import (
    card_review,
    confirm_split,
    record_received,
    request_card,
    review,
)
from core.membership_paid_visit_split_records import MembershipPaidVisitSplit
from core.membership_sales import installment_paid
from core.models import PaymentOperation
from core.payments.invoices import received, total
from core.payments.ledger import record_result
from core.payments.operations import begin_dispatch
from tests import test_membership_paid_visit_recovery as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitSplitTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PaidVisitRecoveryTests.prepare
    buy_card = fixtures.PaidVisitRecoveryTests.buy_card
    decline = fixtures.PaidVisitRecoveryTests.decline
    setup_decline = fixtures.PaidVisitRecoveryTests.setup_decline

    def prepare_split(self):
        self.setup_decline()
        self.split_key = uuid.uuid4()
        self.split_values = dict(
            actor=self.staff,
            intent_id=self.intent.pk,
            manual_amount="0.97",
            tender="cash",
            method_id=self.method.pk,
        )
        self.split_quote = review(**self.split_values)

    def receive(self, **changes):
        values = self.split_values | dict(
            request_key=self.split_key,
            reviewed=self.split_quote["fingerprint"],
            verified_received=True,
            card_authorized=True,
        )
        return record_received(**(values | changes))

    def confirm(self, **changes):
        values = self.split_values | dict(
            request_key=self.split_key,
            reviewed=self.split_quote["fingerprint"],
            verified_received=True,
            card_authorized=True,
        )
        return confirm_split(**(values | changes))

    def test_preview_excludes_original_funds_and_only_fees_the_remaining_card_principal(self):
        self.prepare_split()
        self.assertEqual(
            {
                key: self.split_quote[key]
                for key in (
                    "manual_net",
                    "card_net",
                    "card_fee",
                    "card_total",
                    "fee_removed",
                    "new_payment",
                    "member_total_after",
                )
            },
            dict(
                manual_net="0.97",
                card_net="1.00",
                card_fee="0.03",
                card_total="1.03",
                fee_removed="0.03",
                new_payment="2.00",
                member_total_after="18.02",
            ),
        )
        self.assertFalse(MembershipPaidVisitSplit.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertFalse(VisitMembershipConversion.objects.exists())

    def test_received_portion_is_known_while_card_is_pending_and_source_remains_reserved(self):
        self.prepare_split()
        with patch("core.payments.operations.Gateway") as gateway, self.runtime_role():
            split, card, problem = self.confirm()
        self.assertEqual(problem, "")
        self.assertEqual(split.operation.amount, Decimal("0.97"))
        self.assertEqual(split.operation.state, "succeeded")
        self.assertEqual((card.operation.amount, card.operation.state), (Decimal("1.03"), "ready"))
        sale = self.member.installments.first().invoice.sale
        self.assertEqual((total(sale), received(sale)), (Decimal("18.02"), Decimal("0.97")))
        self.assertEqual(
            (total(self.original), received(self.original)), (Decimal("16.47"), Decimal("16.47"))
        )
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertFalse(self.member.benefit_assignments.exists())
        self.assertFalse(stop_facts(self.intent)["allowed"])
        gateway.assert_not_called()
        connection.check_constraints()

    def test_known_card_completes_same_purchase_using_each_source_once(self):
        self.prepare_split()
        split, card, problem = self.confirm()
        self.assertFalse(problem)
        self.assertIsNotNone(begin_dispatch(card.operation.pk))
        record_result(
            operation_id=card.operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="991303",
        )
        first = self.member.installments.first()
        self.assertEqual(received(first.invoice.sale), Decimal("2.00"))
        with self.runtime_role():
            release = complete(self.intent.pk)
        self.assertEqual(release.kind, "completed")
        self.assertTrue(installment_paid(first))
        self.assertEqual(applied(first.invoice.sale), Decimal("16.02"))
        self.assertEqual(total(first.invoice.sale), Decimal("18.02"))
        self.assertEqual(total(self.original), Decimal("0.45"))
        self.assertEqual(received(self.original), Decimal("16.47"))
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 4)
        self.assertEqual(self.confirm()[0].pk, split.pk)
        self.assertEqual(complete(self.intent.pk).pk, release.pk)
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)
        connection.check_constraints()

    def test_local_card_preparation_failure_keeps_receipt_and_can_be_explicitly_resumed(self):
        self.prepare_split()
        with patch(
            "core.membership_paid_visit_split.request_card",
            side_effect=ValidationError("Preparation interrupted"),
        ):
            split, card, problem = self.confirm()
        self.assertIsNone(card)
        self.assertIn("Do not record this receipt again", problem)
        self.assertEqual(received(self.member.installments.first().invoice.sale), Decimal("0.97"))
        self.assertEqual(split.card_attempts.count(), 0)
        data = card_review(actor=self.staff, split_id=split.pk, method_id=self.method.pk)
        card = request_card(
            actor=self.staff,
            split_id=split.pk,
            method_id=self.method.pk,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            confirmed=True,
        )
        self.assertEqual(card.operation.amount, Decimal("1.03"))
        self.assertEqual(MembershipPaidVisitSplit.objects.count(), 1)
        self.assertEqual(
            PaymentOperation.objects.filter(tender="cash", sale_id=card.operation.sale_id).count(),
            1,
        )
        connection.check_constraints()

    def test_known_failure_retries_only_card_remainder_without_recording_receipt_again(self):
        self.prepare_split()
        split, card, _ = self.confirm()
        self.decline(card.operation)
        data = card_review(actor=self.staff, split_id=split.pk, method_id=self.method.pk)
        next_card = request_card(
            actor=self.staff,
            split_id=split.pk,
            method_id=self.method.pk,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            confirmed=True,
        )
        self.assertEqual(next_card.sequence, 2)
        self.assertEqual(next_card.operation.amount, Decimal("1.03"))
        self.assertEqual(next_card.previous_id, card.operation.pk)
        self.assertEqual(split.operation.amount, Decimal("0.97"))
        connection.check_constraints()

    def test_unknown_card_blocks_new_request_alternative_receipt_and_stop(self):
        self.prepare_split()
        split, card, _ = self.confirm()
        self.assertIsNotNone(begin_dispatch(card.operation.pk))
        record_result(operation_id=card.operation.pk, state="unknown", source="provider")
        with self.assertRaises(ValidationError):
            card_review(actor=self.staff, split_id=split.pk, method_id=self.method.pk)
        with self.assertRaises(ValidationError):
            self.receive(request_key=uuid.uuid4())
        self.assertFalse(stop_facts(self.intent)["allowed"])
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_invalid_or_unverified_split_creates_no_new_money(self):
        self.prepare_split()
        for changes in (
            dict(manual_amount="0.00"),
            dict(manual_amount="1.97"),
            dict(manual_amount="5.00"),
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                review(**(self.split_values | changes))
        for changes in (
            dict(verified_received=False),
            dict(card_authorized=False),
            dict(reviewed="stale"),
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.receive(**changes)
        self.assertFalse(MembershipPaidVisitSplit.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_small_card_balance_has_no_fabricated_minimum_or_unused_processing_fee(self):
        self.prepare_split()
        values = self.split_values | dict(manual_amount="1.96")
        quote = review(**values)
        self.assertEqual(
            (quote["card_net"], quote["card_fee"], quote["card_total"], quote["fee_removed"]),
            ("0.01", "0.00", "0.01", "0.06"),
        )
        split, card, problem = confirm_split(
            **values,
            request_key=self.split_key,
            reviewed=quote["fingerprint"],
            verified_received=True,
            card_authorized=True,
        )
        self.assertFalse(problem)
        self.assertEqual(card.operation.amount, Decimal("0.01"))
        self.assertEqual(total(self.member.installments.first().invoice.sale), Decimal("17.99"))
        self.assertEqual(split.operation.amount, Decimal("1.96"))
        connection.check_constraints()

    def test_zelle_preserves_actual_bank_date_and_sender_in_shared_payment_evidence(self):
        from datetime import timedelta

        from core.membership_sales import today
        from core.payment_receipt_evidence import receipt_evidence

        self.prepare_split()
        bank_date = today() - timedelta(days=2)
        values = self.split_values | dict(
            tender="zelle", received_on=bank_date, sender_name="D. Greenfeld"
        )
        quote = review(**values)
        split = record_received(
            **values,
            request_key=self.split_key,
            reviewed=quote["fingerprint"],
            verified_received=True,
            card_authorized=True,
        )
        evidence = receipt_evidence([split.operation])[split.operation.pk]
        self.assertEqual(evidence["origin"], "Received partial payment")
        self.assertEqual(evidence["received_on"], bank_date)
        self.assertEqual(evidence["sender"], "D. Greenfeld")
        self.assertFalse(evidence["earlier"])
        connection.check_constraints()

    def test_old_full_card_and_manual_replacement_routes_cannot_collect_after_partial_receipt(self):
        from core.membership_paid_visit_manual import review as full_manual_review
        from core.membership_paid_visit_recovery import review as full_card_review

        self.prepare_split()
        self.receive()
        with self.assertRaises(ValidationError):
            full_manual_review(actor=self.staff, intent_id=self.intent.pk)
        with self.assertRaises(ValidationError):
            full_card_review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def cancel_split(self, refund="0.00"):
        from core.membership_cancellations import cancel
        from core.membership_cancellations import review as cancellation_review

        values = dict(
            actor=self.owner, member_id=self.member.pk, timing="immediate", refund_amount=refund
        )
        quote = cancellation_review(**values)
        saved = cancel(
            **values,
            reviewed=quote["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Owner cancelled membership and retained the original paid visit",
            early_override=True,
            send_confirmation=False,
        )
        self.member.billing_state.refresh_from_db()
        self.intent.refresh_from_db()
        return saved

    def release_split_source(self):
        from core.membership_paid_visit_cancellation import release as release_source
        from core.membership_paid_visit_cancellation import review as release_review

        quote = release_review(actor=self.owner, intent=self.intent)
        release_source(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=quote["fingerprint"],
            reason="Keep the original visit and the owner's selected membership refund",
            confirmed=True,
        )
        return quote

    def test_cancel_before_card_payment_keeps_chosen_cash_and_removes_only_uncollected_amounts(
        self,
    ):
        self.prepare_split()
        split, card, _ = self.confirm()
        self.cancel_split()
        card.operation.refresh_from_db()
        self.assertEqual(card.operation.state, "cancelled")
        quote = self.release_split_source()
        self.assertEqual(
            (quote["received"], quote["retained"], quote["retained_fee"]), ("0.97", "0.97", "0.00")
        )
        self.assertEqual(
            (quote["uncollected"], quote["uncollected_principal"], quote["uncollected_card_fee"]),
            ("17.05", "17.02", "0.03"),
        )
        self.assertEqual(
            (total(split.operation.sale), received(split.operation.sale)),
            (Decimal("0.97"), Decimal("0.97")),
        )
        self.assertEqual(
            (total(self.original), received(self.original)), (Decimal("16.47"), Decimal("16.47"))
        )
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertFalse(self.member.benefit_assignments.exists())
        connection.check_constraints()

    def test_cancel_after_known_card_payment_keeps_actual_fee_and_releases_only_original_funds(
        self,
    ):
        self.prepare_split()
        split, card, _ = self.confirm()
        begin_dispatch(card.operation.pk)
        record_result(
            operation_id=card.operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="991304",
        )
        self.cancel_split()
        quote = self.release_split_source()
        self.assertEqual(
            (quote["received"], quote["retained"], quote["retained_fee"]), ("2.00", "2.00", "0.03")
        )
        self.assertEqual((quote["uncollected"], quote["uncollected_card_fee"]), ("16.02", "0.00"))
        self.assertEqual(
            (total(split.operation.sale), received(split.operation.sale)),
            (Decimal("2.00"), Decimal("2.00")),
        )
        self.assertEqual(total(self.original), Decimal("16.47"))
        connection.check_constraints()

    def test_partial_cancellation_refund_retains_only_the_owners_chosen_cash_balance(self):
        from core.membership_cancellations import request_refund

        self.prepare_split()
        split, _, _ = self.confirm()
        cancelled = self.cancel_split(refund="0.47")
        refund = cancelled.refund_plans.get()
        request_refund(
            actor=self.owner,
            plan_id=refund.pk,
            request_key=uuid.uuid4(),
            confirmed=True,
            manual_returned=True,
        )
        quote = self.release_split_source()
        self.assertEqual(
            (quote["received"], quote["returned"], quote["retained"], quote["retained_fee"]),
            ("0.97", "0.47", "0.50", "0.00"),
        )
        self.assertEqual(
            (total(split.operation.sale), received(split.operation.sale)),
            (Decimal("0.50"), Decimal("0.50")),
        )
        self.assertEqual(received(self.original), Decimal("16.47"))
        connection.check_constraints()

    def test_database_refuses_an_old_full_amount_disguised_as_a_remaining_card_request(self):
        from datetime import timedelta

        from django.db import DatabaseError, transaction
        from django.utils import timezone

        from core.membership_paid_visit_split_records import MembershipPaidVisitSplitCard
        from core.payments.ledger import fingerprint

        self.prepare_split()
        split, card, _ = self.confirm()
        self.decline(card.operation)
        data = card_review(actor=self.staff, split_id=split.pk, method_id=self.method.pk)
        data["amount"] = "2.03"
        data["allocation"] = self.operation.allocation
        data["fingerprint"] = fingerprint(
            {key: value for key, value in data.items() if key != "fingerprint"}
        )
        with (
            self.assertRaisesMessage(DatabaseError, "Remaining card payment requires"),
            transaction.atomic(),
        ):
            MembershipPaidVisitSplitCard.objects.create(
                id=uuid.uuid4(),
                split=split,
                sequence=2,
                previous=card.operation,
                operation_id=uuid.uuid4(),
                method=self.method,
                actor=self.staff,
                review=data,
                fingerprint=data["fingerprint"],
                expires_at=timezone.now() + timedelta(minutes=30),
            )
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_database_refuses_removing_the_card_fee_that_still_belongs_to_the_remainder(self):
        from django.db import DatabaseError, transaction

        from core.models import FinancialLineAdjustment

        self.prepare_split()
        split, _, _ = self.confirm()
        with (
            self.assertRaisesMessage(DatabaseError, "Unused membership card fee"),
            transaction.atomic(),
        ):
            FinancialLineAdjustment.objects.create(
                request_key=uuid.uuid4(),
                line_id=split.facts["line"],
                reason="tender_change",
                fee="-0.06",
                actor=self.owner,
            )
        self.assertEqual(total(split.operation.sale), Decimal("18.02"))

    def test_split_evidence_cannot_be_rewritten(self):
        from django.db import DatabaseError, transaction

        self.prepare_split()
        split, _, _ = self.confirm()
        with self.assertRaises(ValidationError):
            split.save()
        with self.assertRaises(ValidationError):
            MembershipPaidVisitSplit.objects.filter(pk=split.pk).update(facts={})
        from django.db import connection

        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_membershippaidvisitsplit SET facts = %s WHERE id = %s",
                ["{}", split.pk],
            )
        self.assertEqual(received(split.operation.sale), Decimal("0.97"))
