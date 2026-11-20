"""Already performed refunds/voids are imported once with exact linked money facts."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from core.models import FinancialPosting, PaymentOperation
from core.payments.corrections import record_correction
from core.payments.gateway import ProviderFailure
from core.payments.invoices import received
from core.payments.ledger import record_result
from tests import test_payment_ledger as fixtures


@override_settings(PAYMENT_SANDBOX_ENABLED=True)
class CorrectionTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create
    sale = fixtures.PaymentLedgerTests.sale
    operation = fixtures.PaymentLedgerTests.operation

    def paid(self):
        operation = self.operation(self.sale())
        record_result(
            operation_id=operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="451",
        )
        operation.refresh_from_db()
        return operation

    def refund_evidence(self, **changes):
        return {
            "id": 452,
            "amount_details": {"amount": "15.99"},
            "transaction_details": {"type": "credit", "reference_number": 451},
            "status_details": {"status": "settled"},
            "created_at": "2026-11-19T15:00:00-05:00",
        } | changes

    def test_import_refund_preserves_retained_fee_and_never_sends_a_post(self):
        original = self.paid()
        allocation = [dict(original.allocation[0], fee="0.00", fee_tax="0.00")]
        key = uuid.uuid4()
        with patch("core.payments.corrections.Gateway") as gateway:
            gateway.return_value.transaction.return_value = self.refund_evidence()
            result = record_correction(
                actor=self.owner,
                original_id=original.pk,
                kind="refund",
                allocation=allocation,
                request_key=key,
                provider_reference="452",
                confirmed=True,
            )
            again = record_correction(
                actor=self.owner,
                original_id=original.pk,
                kind="refund",
                allocation=allocation,
                request_key=key,
                provider_reference="452",
                confirmed=True,
            )
            self.assertEqual(result.pk, again.pk)
            gateway.return_value.refund.assert_not_called()
            gateway.return_value.void.assert_not_called()
        self.assertEqual(received(original.sale), Decimal(".48"))
        self.assertEqual(result.postings.get().occurred_at.isoformat(), "2026-11-19T20:00:00+00:00")
        self.assertEqual(FinancialPosting.objects.count(), 2)

    def test_wrong_parent_or_amount_cannot_leave_a_reserved_or_paid_correction(self):
        original = self.paid()
        for evidence in [
            self.refund_evidence(transaction_details={"type": "credit", "reference_number": 999}),
            self.refund_evidence(amount_details={"amount": "99.00"}),
        ]:
            with patch("core.payments.corrections.Gateway") as gateway:
                gateway.return_value.transaction.return_value = evidence
                with self.assertRaises((ProviderFailure, ValidationError)):
                    record_correction(
                        actor=self.owner,
                        original_id=original.pk,
                        kind="refund",
                        allocation=original.allocation,
                        request_key=uuid.uuid4(),
                        provider_reference="452",
                        confirmed=True,
                    )
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(FinancialPosting.objects.count(), 1)

    def test_new_submission_key_cannot_import_same_provider_refund_twice(self):
        original = self.paid()
        allocation = [dict(original.allocation[0], fee="0.00", fee_tax="0.00")]
        with patch("core.payments.corrections.Gateway") as gateway:
            gateway.return_value.transaction.return_value = self.refund_evidence()
            args = dict(
                actor=self.owner,
                original_id=original.pk,
                kind="refund",
                allocation=allocation,
                provider_reference="452",
                confirmed=True,
            )
            record_correction(**args, request_key=uuid.uuid4())
            with self.assertRaises(ValidationError):
                record_correction(**args, request_key=uuid.uuid4())
        self.assertEqual(PaymentOperation.objects.filter(kind="refund").count(), 1)

    def test_staff_cannot_import_an_external_refund(self):
        original = self.paid()
        with (
            patch("core.payments.corrections.Gateway") as gateway,
            self.assertRaises(PermissionDenied),
        ):
            record_correction(
                actor=self.staff,
                original_id=original.pk,
                kind="refund",
                allocation=original.allocation,
                request_key=uuid.uuid4(),
                provider_reference="452",
                confirmed=True,
            )
        gateway.assert_not_called()
