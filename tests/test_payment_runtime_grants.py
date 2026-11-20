"""Payment confirmations must work with staging's append-only financial grants."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from core.management.commands import reviewed_booking_completion_schema as schema
from core.models import (
    Booking,
    FinancialLine,
    FinancialLineAdjustment,
    FinancialPosting,
    FinancialSale,
    PaymentOperation,
    PricingPolicy,
)
from core.payments import remainders
from core.payments.checkout import confirm, preview
from core.payments.corrections import record_correction
from core.payments.invoices import received
from core.payments.ledger import full_allocation, record_result, request_operation
from core.payments.operations import execute
from tests import test_booking_checkout as fixtures
from tests import test_payment_ledger as ledger_fixtures


class RuntimeRoleMixin:
    @contextmanager
    def runtime_role(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL runtime grants")
        role = "mdo_pay_" + uuid.uuid4().hex[:10]
        backup = "mdo_back_" + uuid.uuid4().hex[:10]
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
            cursor.execute(f'CREATE ROLE "{backup}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
            cursor.execute(
                f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO "{role}"'
            )
            cursor.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{role}"')
        with (
            patch.object(schema, "RUNTIME_ROLE", role),
            patch.object(schema, "BACKUP_ROLE", backup),
        ):
            schema.grant_runtime_access()
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'SET ROLE "{role}"')
                cursor.execute(
                    "SELECT has_table_privilege(current_user,'core_financialsale','UPDATE')"
                )
                self.assertFalse(cursor.fetchone()[0])
            yield role
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                for name in (role, backup):
                    cursor.execute(f'DROP OWNED BY "{name}"')
                    cursor.execute(f'DROP ROLE "{name}"')


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class PaymentRuntimeGrantTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.CheckoutTests.setUp
    create = fixtures.CheckoutTests.create
    flow = fixtures.CheckoutTests.flow
    card = fixtures.CheckoutTests.card
    save_card = fixtures.CheckoutTests.save_card
    gateway = fixtures.CheckoutTests.gateway
    ready = fixtures.CheckoutTests.ready
    booking = fixtures.CheckoutTests.booking
    arrival_inputs = fixtures.CheckoutTests.arrival_inputs
    act = fixtures.CheckoutTests.act

    def test_reviewed_card_confirmation_queues_once_without_financial_update_permission(self):
        booking = self.booking()
        data = self.arrival_inputs(booking)
        reviewed = preview(actor=self.owner, booking_id=booking.pk, kind="arrival", data=data)
        key = uuid.uuid4()
        with self.runtime_role(), patch("core.payments.gateway.Gateway.request") as provider:
            result = confirm(
                actor=self.owner,
                booking_id=booking.pk,
                kind="arrival",
                data=data,
                request_key=key,
                reviewed_hash=reviewed[-1],
                confirmed=True,
            )
            repeated = confirm(
                actor=self.owner,
                booking_id=booking.pk,
                kind="arrival",
                data=data,
                request_key=key,
                reviewed_hash=reviewed[-1],
                confirmed=True,
            )
            self.assertEqual(result.pk, repeated.pk)
            provider.assert_not_called()
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.get().state, "ready")
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertEqual(Booking.objects.get(pk=booking.pk).attendance, "arrived")
        operation = PaymentOperation.objects.get()
        with self.runtime_role(), patch("core.payments.operations.Gateway") as provider:
            provider.return_value.charge.return_value = {
                "status_code": "A",
                "reference_number": 451,
            }
            provider.return_value.transaction.return_value = {
                "id": 451,
                "amount_details": {"amount": operation.amount},
                "transaction_details": {"type": "charge"},
                "status_details": {"status": "captured"},
                "custom_fields": {
                    "custom1": str(operation.pk),
                    "custom2": "monkeydo:sandbox",
                },
            }
            self.assertEqual(execute(operation.pk).state, "succeeded")
            self.assertEqual(execute(operation.pk).state, "succeeded")
            self.assertEqual(provider.return_value.charge.call_count, 1)
            self.assertEqual(received(result.sale), operation.amount)
        self.assertEqual(FinancialPosting.objects.count(), 1)

    def test_cash_arrival_and_owner_correction_leave_financial_facts_append_only(self):
        booking = self.booking()
        with self.runtime_role(), patch("core.payments.gateway.Gateway.request") as provider:
            result = self.act(booking, self.arrival_inputs(booking, method="cash"))
            original = result.sale.operations.get()
            correction = record_correction(
                actor=self.owner,
                original_id=original.pk,
                kind="refund",
                allocation=original.allocation,
                request_key=uuid.uuid4(),
                confirmed=True,
            )
            self.assertEqual(correction.state, "succeeded")
            self.assertEqual(received(result.sale), Decimal("0"))
            for statement in (
                "UPDATE core_financialsale SET total=total WHERE id=%s",
                "DELETE FROM core_financialsale WHERE id=%s",
            ):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(statement, [result.sale.pk])
            provider.assert_not_called()
        self.assertEqual(FinancialPosting.objects.count(), 2)

    def test_noncard_remainder_appends_adjustment_without_updating_the_original_sale(self):
        booking = self.booking()
        with self.runtime_role(), patch("core.payments.gateway.Gateway.request") as provider:
            initial = self.act(booking, self.arrival_inputs(booking))
            original = initial.sale.operations.get()
            record_result(
                operation_id=original.pk,
                state="declined",
                source="provider",
                code="synthetic_decline",
            )
            _, _, _, digest, _ = remainders.preview(
                actor=self.staff, booking_id=booking.pk, method="cash", context="arrival"
            )
            remaining = remainders.confirm(
                actor=self.staff,
                booking_id=booking.pk,
                method="cash",
                context="arrival",
                request_key=uuid.uuid4(),
                reviewed_hash=digest,
                confirmed=True,
            )
            self.assertEqual(received(remaining.sale), Decimal("15.99"))
            self.assertEqual(remaining.sale.total, Decimal("16.47"))
            self.assertTrue(FinancialLineAdjustment.objects.exists())
            provider.assert_not_called()

    def test_verified_card_refund_import_locks_only_the_mutable_operation(self):
        booking = self.booking()
        with self.runtime_role():
            initial = self.act(booking, self.arrival_inputs(booking))
            original = initial.sale.operations.get()
            record_result(
                operation_id=original.pk,
                state="succeeded",
                source="provider",
                provider_reference="451",
            )
            with patch("core.payments.corrections.Gateway") as provider:
                provider.return_value.transaction.return_value = {
                    "id": 452,
                    "amount_details": {"amount": "15.99"},
                    "transaction_details": {"type": "credit", "reference_number": 451},
                    "status_details": {"status": "settled"},
                    "created_at": "2026-11-19T15:00:00-05:00",
                }
                correction = record_correction(
                    actor=self.owner,
                    original_id=original.pk,
                    kind="refund",
                    allocation=[dict(original.allocation[0], fee="0.00", fee_tax="0.00")],
                    request_key=uuid.uuid4(),
                    provider_reference="452",
                    confirmed=True,
                )
                provider.return_value.refund.assert_not_called()
                provider.return_value.void.assert_not_called()
                provider.return_value.charge.assert_not_called()
            self.assertEqual(correction.state, "succeeded")
            self.assertEqual(received(initial.sale), Decimal(".48"))


@override_settings(PAYMENT_SANDBOX_ENABLED=True)
class PaymentAllocationConcurrencyTests(RuntimeRoleMixin, TransactionTestCase):
    create = ledger_fixtures.PaymentLedgerTests.create
    sale = ledger_fixtures.PaymentLedgerTests.sale

    def setUp(self):
        ledger_fixtures.PaymentLedgerTests.setUp(self)
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def compete(self, sale):
        gate = Barrier(2)
        allocation = full_allocation(sale)
        with self.runtime_role() as role:

            def reserve():
                close_old_connections()
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute(f'SET LOCAL ROLE "{role}"')
                            cursor.execute("SET LOCAL lock_timeout='10s'")
                            cursor.execute("SET LOCAL statement_timeout='15s'")
                        gate.wait(timeout=10)
                        request_operation(
                            actor=self.owner,
                            sale_id=sale.pk,
                            request_key=uuid.uuid4(),
                            tender="cash",
                            allocation=allocation,
                        )
                    return "reserved"
                except ValidationError:
                    return "blocked"
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(reserve) for _ in range(2)]
                results = [future.result(timeout=20) for future in futures]
        self.assertCountEqual(results, ["reserved", "blocked"])
        self.assertEqual(PaymentOperation.objects.filter(sale=sale).count(), 1)
        self.assertFalse(FinancialPosting.objects.exists())

    def test_concurrent_booking_allocations_reserve_the_sale_only_once(self):
        self.compete(self.sale(method="cash"))

    def test_concurrent_allocations_without_a_booking_still_reserve_only_once(self):
        source = self.sale(method="cash")
        fields = {
            field.attname: getattr(source, field.attname)
            for field in source._meta.concrete_fields
            if field.name
            not in {"id", "creation_key", "fingerprint", "booking", "quote", "created_at"}
        }
        standalone = FinancialSale.objects.create(
            **fields, creation_key=uuid.uuid4(), fingerprint="standalone-allocation-check"
        )
        for line in source.lines.all():
            FinancialLine.objects.create(
                sale=standalone,
                **{
                    field.attname: getattr(line, field.attname)
                    for field in line._meta.concrete_fields
                    if field.name not in {"id", "sale"}
                },
            )
        self.compete(standalone)
