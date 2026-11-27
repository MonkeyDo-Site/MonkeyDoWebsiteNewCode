"""App-managed scheduled scope uses the existing one-POST ledger boundary."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase, override_settings

from core.communications.models import MessageDelivery
from core.membership_collection_authority import prepare_claim
from core.membership_collections import schedule_installment
from core.membership_notices import payment_notices
from core.membership_payments import collect_installment, payment_review
from core.membership_records import MembershipCollectionClaim, MembershipInvoice
from core.membership_sales import invoice_for
from core.models import (
    AuditEvent,
    DurableJob,
    FinancialPosting,
    MembershipCardMandate,
    PaymentOperation,
)
from core.payments.gateway import Gateway, ProviderFailure
from core.payments.jobs import run_one
from core.payments.ledger import full_allocation, request_operation
from core.payments.operations import execute
from tests import test_customer_credit_corrections as corrections
from tests import test_membership_collection_authority as authority_fixtures
from tests import test_membership_collection_plan as planner
from tests import test_membership_sales as fixtures
from tests.test_membership_renewals import clock
from tests.test_payment_runtime_grants import RuntimeRoleMixin

SETTINGS = planner.SETTINGS | {"MEMBERSHIP_COLLECTIONS_ENABLED": True}


@override_settings(**SETTINGS)
class MembershipCollectionTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed
    funded = planner.MembershipCollectionPlanTests.funded
    report_return = planner.MembershipCollectionPlanTests.report_return

    def queued(self):
        member, item = self.funded()
        with clock(item.due_on):
            operation = schedule_installment(item.pk).operation
        return member, item, operation

    def approved(self, gateway, operation):
        gateway.return_value.charge.return_value = {"status_code": "A", "reference_number": 97771}
        gateway.return_value.transaction.return_value = {
            "id": 97771,
            "amount_details": {"amount": str(operation.amount)},
            "transaction_details": {"type": "charge"},
            "status_details": {"status": "captured"},
            "custom_fields": {"custom1": str(operation.pk), "custom2": "monkeydo:sandbox"},
        }

    def test_runtime_preparation_queues_once_without_posting_or_provider_io(self):
        _, item = self.funded()
        emails = MessageDelivery.objects.count()
        postings = FinancialPosting.objects.count()
        with (
            clock(item.due_on),
            self.runtime_role(),
            patch("core.payments.operations.Gateway") as provider,
        ):
            op = schedule_installment(item.pk).operation
            self.assertEqual(schedule_installment(item.pk).operation.pk, op.pk)
            provider.assert_not_called()
        self.assertIsNone(op.actor_id)
        self.assertEqual(str(op.amount), "37.06")
        self.assertEqual(op.state, "ready")
        self.assertEqual(op.events.get(state="ready").source, "worker")
        self.assertEqual(op.sale_id, MembershipInvoice.objects.get(installment=item).sale_id)
        self.assertEqual(
            DurableJob.objects.filter(reference=str(op.pk), kind="payment_dispatch").count(), 1
        )
        self.assertEqual(
            AuditEvent.objects.filter(action="membership.collection_queued").count(), 1
        )
        self.assertEqual(MessageDelivery.objects.count(), emails)
        self.assertEqual(FinancialPosting.objects.count(), postings)

    def test_confirmed_dispatch_is_one_post_one_receipt_without_monthly_customer_email(self):
        _, item, op = self.queued()
        before = MessageDelivery.objects.count()
        postings = FinancialPosting.objects.count()
        with (
            clock(item.due_on),
            self.runtime_role(),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            self.approved(gateway, op)
            self.assertEqual(execute(op.pk).state, "succeeded")
            self.assertEqual(execute(op.pk).state, "succeeded")
            self.assertEqual(schedule_installment(item.pk).operation.pk, op.pk)
            self.assertEqual(gateway.return_value.charge.call_count, 1)
        self.assertEqual(FinancialPosting.objects.count(), postings + 1)
        self.assertEqual(MessageDelivery.objects.count(), before)

    def test_gateway_uses_documented_installment_flags_without_provider_recurring_schedule(self):
        _, _, op = self.queued()
        with patch.object(Gateway, "request", return_value={}) as request:
            Gateway().charge(op)
        args = request.call_args.args
        self.assertEqual(args[:2], ("POST", "transactions/charge"))
        flags = args[2]["transaction_flags"]
        self.assertTrue(flags["is_installment"])
        self.assertFalse(flags["is_recurring"])
        self.assertFalse(flags["is_customer_initiated"])
        self.assertFalse(args[2]["ignore_duplicates"])

    def test_decline_is_never_requeued_and_has_owner_followup(self):
        _, item, op = self.queued()
        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.return_value = {
                "status_code": "D",
                "reference_number": 97771,
            }
            self.assertEqual(execute(op.pk).state, "declined")
            self.assertEqual(execute(op.pk).state, "declined")
            self.assertEqual(schedule_installment(item.pk).operation.pk, op.pk)
            self.assertEqual(gateway.return_value.charge.call_count, 1)
        op.refresh_from_db()
        self.assertIsNone(op.followup.resolved_at)
        self.assertEqual(op.followup.plan, "owner_review")
        self.assertFalse(
            MessageDelivery.objects.filter(membership_id=item.purchase_id)
            .exclude(kind="membership_confirmation")
            .exists()
        )

    def test_uncertain_post_is_never_repeated(self):
        _, item, op = self.queued()
        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.side_effect = ProviderFailure()
            self.assertEqual(execute(op.pk).state, "unknown")
            self.assertEqual(execute(op.pk).state, "unknown")
            self.assertEqual(schedule_installment(item.pk).operation.pk, op.pk)
            self.assertEqual(gateway.return_value.charge.call_count, 1)
        self.assertEqual(op.sale.operations.count(), 1)

    def test_interrupted_worker_marks_unknown_and_blocks_job_without_post(self):
        _, item, op = self.queued()
        DurableJob.objects.exclude(reference=str(op.pk)).update(state="done")
        op.state = "sending"
        op.save(update_fields=["state"])
        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            self.assertTrue(run_one())
            gateway.assert_not_called()
            self.assertEqual(schedule_installment(item.pk).operation.pk, op.pk)
        op.refresh_from_db()
        self.assertEqual(op.state, "unknown")
        self.assertEqual(DurableJob.objects.get(reference=str(op.pk)).state, "blocked")

    def test_expired_unattempted_scope_is_cancelled_and_owner_can_collect_explicitly(self):
        member, item, op = self.queued()
        with (
            clock(item.due_on + timedelta(days=1)),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            self.assertEqual(execute(op.pk).state, "cancelled")
            gateway.return_value.charge.assert_not_called()
            self.assertEqual(schedule_installment(item.pk).operation.pk, op.pk)
            notice = next(row for row in payment_notices() if row.pk == item.pk)
            self.assertEqual(notice.issue_label, "Installment due")
            data = payment_review(
                actor=self.staff, member_id=member.pk, installment_id=item.pk, tender="card"
            )
            action = collect_installment(
                actor=self.staff,
                member_id=member.pk,
                installment_id=item.pk,
                tender="card",
                reviewed=data["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
            )
            self.assertNotEqual(action.operation_id, op.pk)
            self.assertEqual(action.operation.state, "ready")

    def test_changed_mandate_cannot_silently_collect_using_the_new_card(self):
        member, item, op = self.queued()
        replacement = MembershipCardMandate.objects.create(
            purchase=member, method=self.method, text="New consent", actor=self.staff
        )
        billing = member.billing_state
        billing.mandate, billing.revision = replacement, billing.revision + 1
        billing.save(update_fields=["mandate", "revision"])
        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            self.assertEqual(execute(op.pk).state, "cancelled")
            gateway.return_value.charge.assert_not_called()
        self.assertEqual(op.sale.operations.count(), 1)

    def test_former_staff_deactivation_does_not_invalidate_accepted_customer_installments(self):
        _, item, op = self.queued()
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            self.approved(gateway, op)
            self.assertEqual(execute(op.pk).state, "succeeded")
        self.assertIsNone(op.actor_id)

    def test_previous_funding_return_or_flag_off_stops_before_post(self):
        member, item, op = self.queued()
        self.report_return(member.installments.first().invoice.sale.operations.get())
        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            self.assertEqual(execute(op.pk).state, "cancelled")
            gateway.return_value.charge.assert_not_called()
        with (
            clock(item.due_on),
            override_settings(MEMBERSHIP_COLLECTIONS_ENABLED=False),
            self.assertRaises(PermissionDenied),
        ):
            schedule_installment(item.pk)

    def test_system_scope_cannot_authorize_other_installments_or_payment_types(self):
        member, item = self.funded()
        with clock(item.due_on):
            claim = prepare_claim(item.pk)
            with self.assertRaises(PermissionDenied):
                invoice_for(
                    member.installments.first(), actor=None, tender="card", scheduled_claim=claim
                )
            invoice = invoice_for(item, actor=None, tender="card", scheduled_claim=claim)
            values = dict(
                actor=None,
                sale_id=invoice.sale_id,
                request_key=claim.payment_key,
                tender="card",
                purpose="member_installment",
                method_id=self.method.pk,
                allocation=full_allocation(invoice.sale),
                scheduled_membership_claim=claim,
            )
            for changes in (
                {"request_key": uuid.uuid4()},
                {"purpose": "member_purchase"},
                {"kind": "refund"},
                {"tender": "cash"},
                {"actor": self.staff},
                {"public_membership_authority": "not-a-proof"},
                {"allocation": [values["allocation"][0] | {"net": "1.00"}]},
            ):
                with self.subTest(changes=changes), self.assertRaises(PermissionDenied):
                    request_operation(**(values | changes))
            self.assertEqual(invoice.sale.operations.count(), 0)

    def test_queue_failure_rolls_back_claim_invoice_payment_and_audit_together(self):
        _, item = self.funded()
        before = (
            MembershipInvoice.objects.count(),
            PaymentOperation.objects.count(),
            AuditEvent.objects.count(),
        )
        with (
            clock(item.due_on),
            patch(
                "core.membership_collections.enqueue",
                side_effect=ValidationError("Local test queue fault"),
            ),
            self.assertRaises(ValidationError),
        ):
            schedule_installment(item.pk)
        self.assertFalse(MembershipCollectionClaim.objects.exists())
        self.assertEqual(
            (
                MembershipInvoice.objects.count(),
                PaymentOperation.objects.count(),
                AuditEvent.objects.count(),
            ),
            before,
        )

    def test_existing_manual_review_never_becomes_an_automatic_attempt(self):
        member, item = self.funded()
        with clock(item.due_on):
            invoice_for(item, actor=self.staff, tender="card")
            with self.assertRaises(ValidationError):
                schedule_installment(item.pk)
        self.assertFalse(MembershipCollectionClaim.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)


@override_settings(**SETTINGS)
class MembershipCollectionCreditGuardTests(RuntimeRoleMixin, TestCase):
    setUp = authority_fixtures.MembershipCollectionCreditAuthorityTests.setUp
    flow = authority_fixtures.MembershipCollectionCreditAuthorityTests.flow
    card = authority_fixtures.MembershipCollectionCreditAuthorityTests.card
    save_card = authority_fixtures.MembershipCollectionCreditAuthorityTests.save_card
    booking = authority_fixtures.MembershipCollectionCreditAuthorityTests.booking
    arrival_inputs = authority_fixtures.MembershipCollectionCreditAuthorityTests.arrival_inputs
    create = authority_fixtures.MembershipCollectionCreditAuthorityTests.create
    gateway = authority_fixtures.MembershipCollectionCreditAuthorityTests.gateway
    ready = authority_fixtures.MembershipCollectionCreditAuthorityTests.ready
    member = authority_fixtures.MembershipCollectionCreditAuthorityTests.member
    act = authority_fixtures.MembershipCollectionCreditAuthorityTests.act
    paid_visit = authority_fixtures.MembershipCollectionCreditAuthorityTests.paid_visit
    conversion = authority_fixtures.MembershipCollectionCreditAuthorityTests.conversion
    correction = corrections.CreditFixtures.correction

    def test_backed_credit_reduces_the_card_amount_under_runtime_permissions(self):
        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        with clock(item.due_on), self.runtime_role():
            result = schedule_installment(item.pk)
        self.assertEqual(str(result.operation.amount), "2.03")
        self.assertEqual(str(result.credit_application.amount), "16.02")

    def test_credit_restored_before_dispatch_stops_the_older_full_card_amount(self):
        _, _, member, _ = self.conversion(card=True)
        removed = self.correction("16.02")
        item = member.installments.get(number=2)
        with clock(item.due_on):
            op = schedule_installment(item.pk).operation
            self.assertEqual(str(op.amount), "18.53")
            self.correction("1.00", kind="restore", original=removed)
            with patch("core.payments.operations.Gateway") as gateway:
                self.assertEqual(execute(op.pk).state, "cancelled")
                gateway.return_value.charge.assert_not_called()
        self.assertEqual(op.sale.operations.count(), 1)


@override_settings(**SETTINGS)
class MembershipCollectionRaceTests(TransactionTestCase):
    setUp = authority_fixtures.MembershipCollectionClaimRaceTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed
    funded = planner.MembershipCollectionPlanTests.funded
    approved = MembershipCollectionTests.approved

    def test_overlapping_schedulers_queue_one_invoice_payment_and_job(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL customer/request lock integration")
        _, item = self.funded()
        ready = Barrier(2)

        def run():
            close_old_connections()
            try:
                ready.wait(timeout=10)
                return schedule_installment(item.pk).operation.pk
            finally:
                connections.close_all()

        with clock(item.due_on), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run), pool.submit(run)]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipCollectionClaim.objects.count(), 1)
        self.assertEqual(MembershipInvoice.objects.filter(installment=item).count(), 1)
        self.assertEqual(PaymentOperation.objects.filter(pk__in=results).count(), 1)
        self.assertEqual(
            DurableJob.objects.filter(reference=str(results[0]), kind="payment_dispatch").count(), 1
        )

    def test_second_dispatcher_observes_sending_and_never_posts_again(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL dispatch-lock integration")
        _, item = self.funded()
        entered, release = Event(), Event()

        def run(operation_id):
            close_old_connections()
            try:
                return execute(operation_id).state
            finally:
                connections.close_all()

        def charge(operation):
            entered.set()
            if not release.wait(timeout=10):
                raise AssertionError("The second dispatcher never finished its read.")
            return {"status_code": "A", "reference_number": 97771}

        with clock(item.due_on), patch("core.payments.operations.Gateway") as gateway:
            op = schedule_installment(item.pk).operation
            self.approved(gateway, op)
            gateway.return_value.charge.side_effect = charge
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(run, op.pk)
                try:
                    self.assertTrue(entered.wait(timeout=10))
                    self.assertEqual(pool.submit(run, op.pk).result(timeout=10), "sending")
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=10), "succeeded")
            self.assertEqual(gateway.return_value.charge.call_count, 1)
        self.assertEqual(FinancialPosting.objects.filter(operation=op).count(), 1)
