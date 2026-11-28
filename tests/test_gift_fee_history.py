"""The additive constraint preserves legacy evidence and blocks new ineligible receipts."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.models import FinancialPosting, PaymentOperation
from core.payments.ledger import record_manual, record_result, request_operation
from tests import test_customer_credit_concurrency as races
from tests import test_gift_fee_scope as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class GiftFeeHistoryTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    prepare = fixtures.GiftFeeScopeTests.prepare
    accepted = fixtures.GiftFeeScopeTests.accepted
    fee_allocation = fixtures.GiftFeeScopeTests.fee_allocation

    def legacy(self, *, paid=False):
        self.prepare()
        saved = self.accepted(method="card")
        card = saved.sale.operations.get(tender="card")
        record_result(
            operation_id=card.pk, state="declined", source="provider", provider_reference="448114"
        )
        try:
            MigrationExecutor(connection).migrate([("core", "0080_pending_visit_returns")])
            # Reproduce the old application only in this disposable test database.
            with patch("core.payments.ledger.check_receipt_tender"):
                original = request_operation(
                    actor=self.staff,
                    sale_id=saved.sale.pk,
                    tender="gift_card",
                    allocation=self.fee_allocation(saved.sale),
                    request_key=uuid.uuid4(),
                )
                if paid:
                    record_manual(actor=self.staff, operation_id=original.pk, received=True)
        finally:
            MigrationExecutor(connection).migrate([("core", "0084_paid_visit_purchase")])
        return saved, original

    def test_paid_legacy_gift_fee_evidence_is_preserved_and_duplicate_result_adds_nothing(self):
        saved, original = self.legacy(paid=True)
        original.refresh_from_db()
        self.assertEqual(original.state, "succeeded")
        before = FinancialPosting.objects.count(), PaymentOperation.objects.count()
        repeated = record_manual(actor=self.staff, operation_id=original.pk, received=True)
        self.assertEqual(original.pk, repeated.pk)
        self.assertEqual(
            (FinancialPosting.objects.count(), PaymentOperation.objects.count()), before
        )
        self.assertEqual(original.allocation, self.fee_allocation(saved.sale))
        with self.assertRaisesMessage(ValidationError, "Gift-card payments cannot cover"):
            request_operation(
                actor=self.staff,
                sale_id=saved.sale.pk,
                tender="gift_card",
                allocation=original.allocation,
                request_key=uuid.uuid4(),
            )

    def test_pending_legacy_gift_fee_cannot_be_promoted_but_can_be_cancelled_without_receipt(self):
        _, original = self.legacy()
        before = FinancialPosting.objects.count()
        with self.assertRaisesMessage(ValidationError, "Gift-card payments cannot cover"):
            record_manual(actor=self.staff, operation_id=original.pk, received=True)
        self.assertEqual(FinancialPosting.objects.count(), before)
        with (
            self.assertRaisesMessage(DatabaseError, "Gift-card payments cannot cover"),
            transaction.atomic(),
        ):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_paymentoperation SET state='succeeded' WHERE id=%s", [original.pk]
                )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_paymentoperation SET state='cancelled' WHERE id=%s", [original.pk]
            )
        original.refresh_from_db()
        self.assertEqual(original.state, "cancelled")
        self.assertEqual(FinancialPosting.objects.count(), before)

    def test_original_tender_owner_correction_of_legacy_receipt_is_not_blocked(self):
        saved, original = self.legacy(paid=True)
        corrected = request_operation(
            actor=self.owner,
            sale_id=saved.sale.pk,
            tender="gift_card",
            kind="refund",
            original_id=original.pk,
            allocation=original.allocation,
            request_key=uuid.uuid4(),
        )
        record_manual(actor=self.owner, operation_id=corrected.pk, received=True)
        corrected.refresh_from_db()
        self.assertEqual(
            (corrected.kind, corrected.state, corrected.amount),
            ("refund", "succeeded", Decimal("3")),
        )
        original.refresh_from_db()
        self.assertEqual(original.state, "succeeded")
        self.assertEqual(
            saved.sale.operations.filter(kind="receipt", tender="gift_card").count(), 1
        )

    def test_unused_constraint_reverses_and_restores_before_valid_gift_and_fee_collection(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0080_pending_visit_returns")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0084_paid_visit_purchase")])
        self.prepare()
        with self.runtime_role():
            saved = self.accepted()
        self.assertEqual(saved.sale.operations.get(tender="gift_card").amount, Decimal("15.99"))
        self.assertEqual(saved.sale.operations.get(tender="card").amount, Decimal("3.09"))
