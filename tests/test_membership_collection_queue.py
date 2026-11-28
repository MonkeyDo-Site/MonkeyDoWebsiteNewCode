"""Daily producer and leased preparation cannot become repeated financial POSTs."""

import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import DatabaseError, close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.membership_collection_queue import KIND, key, prepare_due, process
from core.membership_payments import collect_installment, payment_review
from core.membership_records import MembershipCollectionClaim, MembershipInvoice
from core.membership_sales import invoice_for
from core.models import DurableJob, FinancialPosting, PaymentOperation
from core.payments.job_review import disposition, recover
from core.payments.jobs import enqueue, run_one
from core.payments.ledger import record_result
from tests import test_membership_collection_authority as authority
from tests import test_membership_collection_plan as planner
from tests import test_membership_collections as collections
from tests import test_membership_sales as fixtures
from tests.helpers import verified_owner_login
from tests.test_customer_credit_corrections import CreditFixtures
from tests.test_membership_renewals import clock
from tests.test_payment_runtime_grants import RuntimeRoleMixin


def isolate_preparation():
    DurableJob.objects.exclude(kind=KIND).update(state="done")


@override_settings(**collections.SETTINGS)
class ScheduledQueueTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed
    funded = planner.MembershipCollectionPlanTests.funded
    approved = collections.MembershipCollectionTests.approved

    def queued(self, item):
        isolate_preparation()
        prepare_due()
        return DurableJob.objects.get(key=key(item.pk))

    def test_bounded_idempotent_producer_creates_only_jobs_under_runtime_permissions(self):
        _, item = self.funded()
        before = (
            MembershipInvoice.objects.count(),
            PaymentOperation.objects.count(),
            FinancialPosting.objects.count(),
        )
        with (
            clock(item.due_on),
            self.runtime_role(),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            self.assertEqual(prepare_due()["queued"], 1)
            self.assertEqual(prepare_due()["queued"], 0)
            gateway.assert_not_called()
        self.assertEqual(DurableJob.objects.filter(kind=KIND).count(), 1)
        self.assertFalse(MembershipCollectionClaim.objects.exists())
        self.assertEqual(
            (
                MembershipInvoice.objects.count(),
                PaymentOperation.objects.count(),
                FinancialPosting.objects.count(),
            ),
            before,
        )

    def test_preparation_then_dispatch_produces_one_request_and_one_provider_post(self):
        _, item = self.funded()
        with (
            clock(item.due_on),
            self.runtime_role(),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            job = self.queued(item)
            self.assertTrue(run_one())
            gateway.assert_not_called()
            job.refresh_from_db()
            self.assertEqual(job.state, "done")
            operation = item.invoice.sale.operations.get()
            self.assertEqual(operation.state, "ready")
            self.approved(gateway, operation)
            self.assertTrue(run_one())
            operation.refresh_from_db()
            self.assertEqual(operation.state, "succeeded")
            self.assertEqual(prepare_due()["queued"], 0)
            self.assertFalse(run_one())
            self.assertEqual(gateway.return_value.charge.call_count, 1)

    def test_blocked_first_candidate_cannot_starve_the_next_membership(self):
        failed = self.buy()
        record_result(
            operation_id=failed.installments.first().invoice.sale.operations.get().pk,
            state="declined",
            source="provider",
        )
        self.key = uuid.uuid4()
        _, good = self.funded()
        with clock(good.due_on), patch("core.payments.operations.Gateway") as gateway:
            isolate_preparation()
            self.assertEqual(prepare_due(limit=1)["queued"], 1)
            self.assertTrue(run_one())
            blocked = DurableJob.objects.get(kind=KIND)
            self.assertEqual(blocked.state, "blocked")
            self.assertEqual(prepare_due(limit=1)["queued"], 1)
            self.assertTrue(run_one())
            gateway.assert_not_called()
        self.assertTrue(MembershipInvoice.objects.filter(installment=good).exists())
        self.assertFalse(
            MembershipInvoice.objects.filter(installment=failed.installments.get(number=2)).exists()
        )

    def test_missed_date_never_creates_an_automatic_catch_up_request(self):
        _, item = self.funded()
        with clock(item.due_on):
            job = self.queued(item)
        with (
            clock(item.due_on + timedelta(days=1)),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            self.assertEqual(prepare_due()["queued"], 0)
            self.assertTrue(run_one())
            job.refresh_from_db()
            self.assertEqual(job.state, "blocked")
            action, explanation = disposition(job)
            self.assertEqual(action, "resolve")
            self.assertIn("scheduled date has passed", explanation)
            with self.assertRaises(ValidationError):
                recover(actor=self.owner, job_id=job.pk, action="resume", confirmed=True)
            gateway.assert_not_called()
        self.assertFalse(MembershipInvoice.objects.filter(installment=item).exists())

    def test_initial_future_cancelled_and_manually_reviewed_installments_are_not_candidates(self):
        member, item = self.funded()
        self.key = uuid.uuid4()
        cancelled = self.buy()
        record_result(
            operation_id=cancelled.installments.first().invoice.sale.operations.get().pk,
            state="succeeded",
            source="provider",
            provider_reference="1441914",
        )
        stopped_item = cancelled.installments.get(number=2)
        billing = cancelled.billing_state
        billing.stopped_on = stopped_item.cycle.starts_on
        billing.save(update_fields=["stopped_on"])
        with clock(member.membership.starts_on):
            self.assertEqual(prepare_due()["queued"], 0)
        with clock(item.due_on):
            invoice_for(item, actor=self.staff, tender="card")
            self.assertEqual(prepare_due()["queued"], 0)
        self.assertFalse(DurableJob.objects.filter(kind=KIND).exists())

    def test_new_york_date_controls_production_instead_of_utc_midnight(self):
        _, item = self.funded()
        self.assertEqual(item.due_on.isoformat(), "2027-11-30")
        with patch(
            "django.utils.timezone.now",
            return_value=datetime(2027, 11, 30, 4, 30, tzinfo=dt_timezone.utc),
        ):
            self.assertEqual(prepare_due()["queued"], 0)
        with patch(
            "django.utils.timezone.now",
            return_value=datetime(2027, 11, 30, 5, 30, tzinfo=dt_timezone.utc),
        ):
            self.assertEqual(prepare_due()["queued"], 1)

    def test_flags_and_recovery_hold_stop_preparation_without_new_financial_facts(self):
        _, item = self.funded()
        with clock(item.due_on):
            for values in (
                {"MEMBERSHIP_COLLECTIONS_ENABLED": False},
                {"MEMBERSHIP_SALES_ENABLED": False},
            ):
                with override_settings(**values):
                    self.assertFalse(prepare_due()["enabled"])
            with override_settings(RECOVERY_HOLD=True), self.assertRaises(ValidationError):
                prepare_due()
            for limit in (0, 101, True):
                with self.assertRaises(ValidationError):
                    prepare_due(limit=limit)
        self.assertFalse(DurableJob.objects.filter(kind=KIND).exists())
        self.assertFalse(MembershipCollectionClaim.objects.exists())

    def test_changed_flag_or_forged_job_identity_cannot_request_payment(self):
        _, item = self.funded()
        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            isolate_preparation()
            bad = enqueue(kind=KIND, reference=item.pk, key="untrusted-schedule")
            self.assertTrue(run_one())
            bad.refresh_from_db()
            self.assertEqual(bad.state, "blocked")
            job = self.queued(item)
            with override_settings(MEMBERSHIP_COLLECTIONS_ENABLED=False):
                self.assertTrue(run_one())
            job.refresh_from_db()
            self.assertEqual(job.state, "blocked")
            gateway.assert_not_called()
        self.assertFalse(MembershipCollectionClaim.objects.exists())

    def test_interrupted_preparation_lease_reads_existing_request_without_repeating_it(self):
        _, item = self.funded()
        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            job = self.queued(item)
            result = process(job)
            DurableJob.objects.filter(reference=str(result.operation.pk)).update(
                available_at=timezone.now() + timedelta(hours=1)
            )
            job.state, job.lease_until = "running", timezone.now() - timedelta(minutes=1)
            job.save(update_fields=["state", "lease_until"])
            self.assertTrue(run_one())
            gateway.assert_not_called()
            job.refresh_from_db()
            self.assertEqual(job.state, "done")
        self.assertEqual(item.invoice.sale.operations.count(), 1)
        self.assertEqual(MembershipCollectionClaim.objects.count(), 1)

    def test_a_job_created_before_its_scheduled_day_is_not_financial_authority(self):
        _, item = self.funded()
        isolate_preparation()
        with clock(item.due_on - timedelta(days=1)):
            job = enqueue(kind=KIND, reference=item.pk, key=key(item.pk))
        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            self.assertTrue(run_one())
            gateway.assert_not_called()
            job.refresh_from_db()
            self.assertEqual(job.state, "blocked")
        self.assertFalse(MembershipCollectionClaim.objects.exists())

    def test_owner_can_resume_current_unattempted_preparation_after_resolving_prior_dues(self):
        member = self.buy()
        first = member.installments.first()
        record_result(
            operation_id=first.invoice.sale.operations.get().pk, state="declined", source="provider"
        )
        item = member.installments.get(number=2)
        with clock(item.due_on):
            job = self.queued(item)
            self.assertTrue(run_one())
            job.refresh_from_db()
            self.assertIsNone(disposition(job)[0])
            data = payment_review(
                actor=self.staff, member_id=member.pk, installment_id=first.pk, tender="cash"
            )
            collect_installment(
                actor=self.staff,
                member_id=member.pk,
                installment_id=first.pk,
                tender="cash",
                reviewed=data["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
                verified_received=True,
            )
            self.assertEqual(disposition(job)[0], "resume")
            with self.assertRaises(PermissionDenied):
                recover(actor=self.staff, job_id=job.pk, action="resume", confirmed=True)
            recover(actor=self.owner, job_id=job.pk, action="resume", confirmed=True)
            isolate_preparation()
            self.assertTrue(run_one())
        self.assertEqual(item.invoice.sale.operations.count(), 1)

    def test_owner_review_links_directly_to_membership_without_creating_financial_work(self):
        _, item = self.funded()
        with clock(item.due_on):
            job = self.queued(item)
            job.state = "blocked"
            job.save(update_fields=["state"])
            before = MembershipInvoice.objects.count(), PaymentOperation.objects.count()
            verified_owner_login(self.client, self.owner)
            response = self.client.get(reverse("background_job", args=[job.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, reverse("membership_overview", args=[item.purchase_id]))
            self.assertContains(response, "No charge has been requested yet")
            self.assertEqual(
                (MembershipInvoice.objects.count(), PaymentOperation.objects.count()), before
            )

    def test_command_producer_failure_does_not_suppress_existing_jobs_or_leak_error_text(self):
        out, err = io.StringIO(), io.StringIO()
        with (
            patch("core.management.commands.run_payment_jobs.expire_unused_setups"),
            patch("core.management.commands.run_payment_jobs.expire_membership_sources"),
            patch(
                "core.membership_collection_queue.prepare_due",
                side_effect=DatabaseError("private-source-marker"),
            ) as producer,
            patch("core.membership_renewal_notices.prepare_due"),
            patch("core.membership_prompt_emails.prepare_due"),
            patch(
                "core.management.commands.run_payment_jobs.run_one", return_value=False
            ) as worker,
        ):
            call_command("run_payment_jobs", limit=1, stdout=out, stderr=err)
        producer.assert_called_once_with(limit=1)
        worker.assert_called_once()
        self.assertIn("needs review", err.getvalue())
        self.assertNotIn("private-source-marker", err.getvalue())

    def test_command_does_not_enable_scheduling_when_the_collection_switch_is_off(self):
        with (
            override_settings(MEMBERSHIP_COLLECTIONS_ENABLED=False),
            patch("core.management.commands.run_payment_jobs.expire_unused_setups"),
            patch("core.management.commands.run_payment_jobs.expire_membership_sources"),
            patch("core.membership_collection_queue.prepare_due") as producer,
            patch("core.membership_renewal_notices.prepare_due"),
            patch("core.membership_prompt_emails.prepare_due"),
            patch(
                "core.management.commands.run_payment_jobs.run_one", return_value=False
            ) as worker,
        ):
            call_command("run_payment_jobs", limit=1, stdout=io.StringIO())
        producer.assert_not_called()
        worker.assert_called_once()


@override_settings(**collections.SETTINGS)
class ScheduledCreditQueueTests(CreditFixtures, RuntimeRoleMixin, TestCase):
    def test_full_credit_owner_review_does_not_describe_a_zero_dollar_card_request(self):
        _, _, member, _ = self.conversion(adults=2)
        item = member.installments.get(number=2)
        with clock(item.due_on):
            prepare_due()
            job = DurableJob.objects.get(key=key(item.pk))
            job.state = "blocked"
            job.save(update_fields=["state"])
            action, explanation = disposition(job)
            self.assertEqual(action, "resume")
            self.assertIn("No card charge will be requested", explanation)
            self.assertFalse(MembershipInvoice.objects.filter(installment=item).exists())

    def test_full_credit_preparation_finishes_without_a_card_job_or_new_posting(self):
        _, _, member, _ = self.conversion(adults=2)
        item = member.installments.get(number=2)
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with (
            clock(item.due_on),
            self.runtime_role(),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            isolate_preparation()
            self.assertEqual(prepare_due()["queued"], 1)
            self.assertTrue(run_one())
            self.assertFalse(run_one())
            gateway.assert_not_called()
        self.assertEqual(
            (PaymentOperation.objects.count(), FinancialPosting.objects.count()), before
        )
        self.assertEqual(DurableJob.objects.get(key=key(item.pk)).state, "done")


@override_settings(**collections.SETTINGS)
class ScheduledProducerRaceTests(TransactionTestCase):
    setUp = authority.MembershipCollectionClaimRaceTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed
    funded = planner.MembershipCollectionPlanTests.funded

    def test_overlapping_producers_create_one_preparation_job(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL stable request-lock integration")
        _, item = self.funded()
        ready = Barrier(2)

        def run():
            close_old_connections()
            try:
                ready.wait(timeout=10)
                return prepare_due(limit=1)
            finally:
                connections.close_all()

        with clock(item.due_on), ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=20) for future in [pool.submit(run), pool.submit(run)]]
        self.assertEqual(sum(row["queued"] for row in results), 1)
        self.assertEqual(DurableJob.objects.filter(kind=KIND).count(), 1)
        self.assertFalse(MembershipCollectionClaim.objects.exists())
