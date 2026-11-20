"""Owner recovery resumes unsent work, never a possibly dispatched financial request."""

import uuid
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from core.models import DurableJob
from core.payments.job_review import recover
from core.payments.jobs import enqueue
from core.payments.ledger import record_result
from tests import test_payment_ledger as fixtures


@override_settings(PAYMENT_SANDBOX_ENABLED=True)
class JobRecoveryTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create
    sale = fixtures.PaymentLedgerTests.sale
    operation = fixtures.PaymentLedgerTests.operation

    def test_only_unsent_original_operation_can_be_resumed(self):
        operation = self.operation(self.sale())
        job = enqueue(
            kind="payment_dispatch", reference=operation.pk, key="dispatch:" + str(operation.pk)
        )
        DurableJob.objects.filter(pk=job.pk).update(state="blocked")
        with patch("core.payments.operations.Gateway") as gateway:
            recover(actor=self.owner, job_id=job.pk, action="resume", confirmed=True)
            gateway.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.state, "queued")
        record_result(
            operation_id=operation.pk,
            state="unknown",
            source="worker",
            code="synthetic_interruption",
        )
        DurableJob.objects.filter(pk=job.pk).update(state="blocked")
        with self.assertRaises(ValidationError):
            recover(actor=self.owner, job_id=job.pk, action="resume", confirmed=True)
        job.refresh_from_db()
        self.assertEqual(job.state, "blocked")

    def test_staff_cannot_resume_background_work(self):
        operation = self.operation(self.sale())
        job = enqueue(kind="payment_dispatch", reference=operation.pk, key=str(uuid.uuid4()))
        DurableJob.objects.filter(pk=job.pk).update(state="blocked")
        with self.assertRaises(PermissionDenied):
            recover(actor=self.staff, job_id=job.pk, action="resume", confirmed=True)
