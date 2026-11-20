"""A changed tender removes only uncharged fees, preserving original receipts/history."""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import FinancialLineAdjustment, FinancialPosting, PricingPolicy
from core.payments.invoices import received, remove_unpaid_card_fee, total
from core.payments.ledger import full_allocation, record_manual, record_result
from tests import test_payment_ledger as fixtures


@override_settings(PAYMENT_SANDBOX_ENABLED=True)
class InvoiceAdjustmentTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create
    sale = fixtures.PaymentLedgerTests.sale
    operation = fixtures.PaymentLedgerTests.operation

    def test_failed_card_changed_to_cash_removes_unpaid_fee_not_original_facts(self):
        sale = self.sale()
        operation = self.operation(sale)
        record_result(operation_id=operation.pk, state="declined", source="provider")
        key = uuid.uuid4()
        remove_unpaid_card_fee(actor=self.staff, sale_id=sale.pk, request_key=key)
        remove_unpaid_card_fee(actor=self.staff, sale_id=sale.pk, request_key=key)
        self.assertEqual(FinancialLineAdjustment.objects.count(), 1)
        self.assertEqual(total(sale), Decimal("15.99"))
        cash = self.operation(sale, tender="cash", method_id=None)
        record_manual(actor=self.staff, operation_id=cash.pk, received=True)
        self.assertEqual(received(sale), Decimal("15.99"))
        self.assertEqual(FinancialPosting.objects.get().fee, Decimal("0"))
        sale.refresh_from_db()
        self.assertEqual(sale.total, Decimal("16.47"))
        self.assertEqual(operation.amount, Decimal("16.47"))

    def test_unknown_card_outcome_blocks_tender_change_and_received_fee_is_never_removed(self):
        sale = self.sale()
        operation = self.operation(sale)
        record_result(operation_id=operation.pk, state="unknown", source="provider")
        with self.assertRaises(ValidationError):
            remove_unpaid_card_fee(actor=self.staff, sale_id=sale.pk, request_key=uuid.uuid4())
        record_result(
            operation_id=operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="451",
        )
        remove_unpaid_card_fee(actor=self.staff, sale_id=sale.pk, request_key=uuid.uuid4())
        self.assertEqual(total(sale), Decimal("16.47"))
        self.assertEqual(received(sale), Decimal("16.47"))
        self.assertFalse(FinancialLineAdjustment.objects.exists())

    def test_combined_tax_rounding_is_recomputed_when_unused_card_fee_is_removed(self):
        PricingPolicy.objects.create(child_price=Decimal("1.99"))
        sale = self.sale()
        self.assertEqual(sale.subtotal, Decimal("1.99"))
        operation = self.operation(sale)
        record_result(operation_id=operation.pk, state="declined", source="provider")
        remove_unpaid_card_fee(actor=self.staff, sale_id=sale.pk, request_key=uuid.uuid4())
        self.assertEqual(total(sale), Decimal("2.12"))
        allocation = full_allocation(sale)
        self.assertEqual(allocation[0]["item_tax"], "0.13")
        self.assertEqual(allocation[0]["fee_tax"], "0.00")
