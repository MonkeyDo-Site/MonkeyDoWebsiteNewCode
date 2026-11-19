"""Financial facts, exact-cent allocation and guarded operations (no provider calls)."""

import uuid
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.booking_management import create_test_booking
from core.models import (
    AuditEvent,
    Booking,
    FinancialLine,
    FinancialPosting,
    FinancialSale,
    PaymentMethod,
    PaymentOperation,
)
from core.payments.amounts import COMPONENTS, ZERO, allocate, amount
from core.payments.ledger import (
    accept_booking_sale,
    full_allocation,
    record_manual,
    record_result,
    request_operation,
)
from tests import test_scheduling as scheduling_fixtures


@override_settings(PAYMENT_SANDBOX_ENABLED=True)
class PaymentLedgerTests(TestCase):
    setUp = scheduling_fixtures.SchedulingTests.setUp
    create = scheduling_fixtures.SchedulingTests.create

    def sale(self, method="card", socks=0):
        booking = create_test_booking(
            actor=self.owner,
            customer=self.customer,
            session_id=self.create().pk,
            children=1,
            adults=1,
            babies=0,
            socks=socks,
            expected_method=method,
            creation_key=uuid.uuid4(),
        )
        Booking.objects.filter(pk=booking.pk).update(workflow="integrated_v1")
        self.booking = Booking.objects.get(pk=booking.pk)
        self.method = PaymentMethod.objects.create(
            customer=self.customer,
            booking=booking,
            provider_customer="12",
            provider_method=str(uuid.uuid4().int)[:10],
            brand="Visa",
            last_four="1234",
            consent_version="MD-PAYMENT-2026-01",
            consent_at=timezone.now(),
        )
        return accept_booking_sale(
            actor=self.owner,
            booking_id=booking.pk,
            quote_id=booking.quotes.first().pk,
            creation_key=uuid.uuid4(),
        )

    def operation(self, sale, **changes):
        data = dict(
            actor=self.owner,
            sale_id=sale.pk,
            request_key=uuid.uuid4(),
            tender="card",
            allocation=full_allocation(sale),
            method_id=self.method.pk,
        )
        return request_operation(**(data | changes))

    def test_quotes_never_become_received_money_just_by_being_accepted(self):
        sale = self.sale()
        self.assertEqual(sale.total, Decimal("16.47"))
        self.assertEqual(sale.lines.get().item_tax, Decimal(".99"))
        self.assertEqual(sale.lines.get().fee_tax, Decimal(".03"))
        self.assertFalse(FinancialPosting.objects.exists())
        operation = self.operation(sale)
        self.assertEqual(operation.state, "ready")
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertEqual(self.booking.attendance, "")

    def test_legacy_test_bookings_and_disabled_integration_cannot_create_sales(self):
        self.sale()
        Booking.objects.filter(pk=self.booking.pk).update(workflow="legacy_test")
        with self.assertRaises(ValidationError):
            accept_booking_sale(
                actor=self.owner,
                booking_id=self.booking.pk,
                quote_id=self.booking.quotes.first().pk,
                creation_key=uuid.uuid4(),
            )
        with override_settings(PAYMENT_SANDBOX_ENABLED=False):
            with self.assertRaises(ValidationError):
                self.operation(FinancialSale.objects.get())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_success_is_posted_once_with_original_line_components(self):
        sale = self.sale()
        operation = self.operation(sale)
        for _ in range(2):
            record_result(
                operation_id=operation.pk,
                state="succeeded",
                source="provider",
                provider_reference="451",
            )
        self.assertEqual(FinancialPosting.objects.count(), 1)
        posting = FinancialPosting.objects.get()
        self.assertEqual(sum((getattr(posting, k) for k in COMPONENTS), ZERO), Decimal("16.47"))
        self.assertEqual(posting.operation.kind, "receipt")
        self.assertEqual(AuditEvent.objects.filter(action="payment.result_recorded").count(), 1)
        with self.assertRaises(ValidationError):
            record_result(operation_id=operation.pk, state="declined", source="provider")

    def test_unknown_reserves_the_amount_and_never_counts_as_a_receipt(self):
        sale = self.sale()
        operation = self.operation(sale)
        record_result(
            operation_id=operation.pk, state="unknown", source="provider", code="transport_unknown"
        )
        self.assertFalse(FinancialPosting.objects.exists())
        with self.assertRaises(ValidationError):
            self.operation(sale)
        operation.refresh_from_db()
        self.assertTrue(operation.reconciliation_required)

    def test_same_request_key_is_idempotent_but_changed_request_is_rejected(self):
        sale = self.sale()
        key = uuid.uuid4()
        first = self.operation(sale, request_key=key)
        self.assertEqual(self.operation(sale, request_key=key).pk, first.pk)
        changed = full_allocation(sale)
        changed[0]["net"] = "14.00"
        with self.assertRaises(ValidationError):
            self.operation(sale, request_key=key, allocation=changed)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_split_failure_preserves_actual_receipt_and_unpaid_card_portion(self):
        sale = self.sale()
        cash = full_allocation(sale)
        cash[0].update(net="5.00", fee="0.00", item_tax=".33", fee_tax="0.00")
        first = self.operation(sale, tender="cash", method_id=None, allocation=cash)
        record_manual(actor=self.owner, operation_id=first.pk, received=True)
        remainder = full_allocation(sale)
        for key in COMPONENTS:
            remainder[0][key] = str(amount(remainder[0][key]) - amount(cash[0][key]))
        second = self.operation(sale, allocation=remainder)
        record_result(operation_id=second.pk, state="declined", source="provider")
        self.assertEqual(FinancialPosting.objects.count(), 1)
        self.assertEqual(FinancialPosting.objects.get().net, Decimal("5"))
        self.assertEqual(second.amount, Decimal("11.14"))

    def test_refund_uses_original_components_and_can_follow_method_removal(self):
        sale = self.sale()
        first = self.operation(sale)
        record_result(
            operation_id=first.pk, state="succeeded", source="provider", provider_reference="44"
        )
        self.method.state = "removed"
        self.method.provider_method = None
        self.method.save()
        refund = full_allocation(sale)
        refund[0]["fee"] = "0.00"
        second = self.operation(sale, original_id=first.pk, kind="refund", allocation=refund)
        self.assertEqual(second.amount, Decimal("16.02"))
        record_result(
            operation_id=second.pk, state="succeeded", source="provider", provider_reference="45"
        )
        self.assertEqual(first.postings.get().fee, Decimal(".45"))
        self.assertEqual(second.postings.get().fee_tax, Decimal(".03"))
        self.assertEqual(second.postings.get().fee, Decimal("0"))
        with self.assertRaises(ValidationError):
            self.operation(sale, original_id=first.pk, kind="refund", allocation=refund)

    def test_staff_payment_and_owner_refund_permissions_are_distinct(self):
        sale = self.sale("cash")
        with self.assertRaises(PermissionDenied):
            self.operation(sale, actor=self.staff, tender="cash", method_id=None)
        self.staff.user_permissions.add(Permission.objects.get(codename="collect_payment"))
        self.staff = type(self.staff).objects.get(pk=self.staff.pk)
        operation = self.operation(sale, actor=self.staff, tender="cash", method_id=None)
        record_manual(actor=self.staff, operation_id=operation.pk, received=True)
        with self.assertRaises(PermissionDenied):
            self.operation(
                sale,
                actor=self.staff,
                tender="cash",
                method_id=None,
                original_id=operation.pk,
                kind="refund",
            )
        refund = self.operation(
            sale, tender="cash", method_id=None, original_id=operation.pk, kind="refund"
        )
        with self.assertRaises(PermissionDenied):
            record_manual(actor=self.staff, operation_id=refund.pk, received=True)

    def test_cross_customer_or_booking_method_and_foreign_line_are_rejected(self):
        sale = self.sale()
        self.method.customer = None
        self.method.save()
        with self.assertRaises(PaymentMethod.DoesNotExist):
            self.operation(sale)
        bad = full_allocation(sale)
        bad[0]["line"] = str(uuid.uuid4())
        with self.assertRaises(ValidationError):
            self.operation(sale, allocation=bad)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_cash_cannot_collect_credit_card_fee_and_receipt_needs_actual_confirmation(self):
        sale = self.sale()
        with self.assertRaises(ValidationError):
            self.operation(sale, tender="cash", method_id=None)
        cash = full_allocation(sale)
        cash[0].update(fee="0.00", fee_tax="0.00")
        operation = self.operation(sale, tender="cash", method_id=None, allocation=cash)
        with self.assertRaises(ValidationError):
            record_manual(actor=self.owner, operation_id=operation.pk, received=False)
        self.assertFalse(FinancialPosting.objects.exists())

    def test_mixed_tax_classification_preserves_accepted_fee_and_tax_totals(self):
        sale = self.sale(socks=3)
        self.assertEqual(sum((x.net for x in sale.lines.all()), ZERO), sale.subtotal)
        self.assertEqual(sum((x.fee for x in sale.lines.all()), ZERO), sale.processing_fee)
        self.assertEqual(
            sum((x.item_tax + x.fee_tax for x in sale.lines.all()), ZERO), sale.sales_tax
        )
        socks = sale.lines.get(category="socks")
        self.assertEqual(socks.item_tax + socks.fee_tax, ZERO)
        self.assertEqual(sale.lines.exclude(category="socks").get().fee, Decimal(".45"))

    def test_financial_facts_and_operation_identity_are_protected_in_database(self):
        sale = self.sale()
        operation = self.operation(sale)
        with self.assertRaises(ValidationError):
            FinancialLine.objects.filter(sale=sale).update(net=0)
        for statement, params in [
            ("UPDATE core_financialsale SET total=0 WHERE id=%s", [sale.pk]),
            ("DELETE FROM core_financialline WHERE sale_id=%s", [sale.pk]),
            ("UPDATE core_paymentoperation SET amount=1 WHERE id=%s", [operation.pk]),
            ("DELETE FROM core_paymentoperation WHERE id=%s", [operation.pk]),
        ]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(statement, params)
        self.assertEqual(FinancialSale.objects.get().total, Decimal("16.47"))

    def test_exact_amounts_reject_rounding_float_negative_and_nonfinite_values(self):
        for value in (1.1, True, "NaN", "Infinity", "-1", ".001"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                amount(value)
        self.assertEqual(allocate(".01", ["1", "1", "1"]), [Decimal(".01"), ZERO, ZERO])
        self.assertEqual(sum(allocate(".05", ["1", "2", "3"]), ZERO), Decimal(".05"))
        with self.assertRaises(ValidationError):
            allocate("1", ["0", "0"])
