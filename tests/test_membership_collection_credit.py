"""Automatic credit uses conserved existing money and only its uncharged fee."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from core.communications.models import MessageDelivery
from core.customer_credit import balance
from core.customer_credit_records import CustomerCreditAllocation, CustomerCreditApplication
from core.membership_collection_authority import prepare_claim
from core.membership_collection_credit import apply_scheduled_credit
from core.membership_collections import schedule_installment
from core.membership_conversion import convert
from core.membership_conversion import review as conversion_review
from core.membership_payments import collect_installment, payment_review
from core.membership_records import MembershipCollectionClaim, MembershipInvoice
from core.membership_sales import installment_paid, invoice_for
from core.models import (
    Customer,
    DurableJob,
    FinancialLineAdjustment,
    FinancialPosting,
    PaymentOperation,
)
from core.payments.invoices import received, settled, total
from core.payments.ledger import record_result
from core.payments.operations import execute
from tests import test_customer_credit_concurrency as credit_races
from tests import test_membership_collections as collections
from tests.test_customer_credit_corrections import CreditFixtures
from tests.test_membership_renewals import clock
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**collections.SETTINGS)
class ScheduledCreditTests(CreditFixtures, RuntimeRoleMixin, TestCase):
    approved = collections.MembershipCollectionTests.approved

    def test_accountant_example_applies_existing_funds_and_collects_only_two_dollars_three_cents(
        self,
    ):
        _, original, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        source_money = received(original)
        emails = MessageDelivery.objects.count()
        with clock(item.due_on), self.runtime_role():
            result = schedule_installment(item.pk)
            self.assertEqual(str(result.credit_application.amount), "16.02")
            self.assertIsNone(result.credit_application.actor_id)
            self.assertEqual(result.credit_application.scheduled_claim_id, result.claim.pk)
            self.assertEqual(str(result.operation.amount), "2.03")
            self.assertEqual(str(result.operation.allocation[0]["net"]), "1.97")
            self.assertEqual(str(result.operation.allocation[0]["fee"]), "0.06")
            self.assertEqual(received(result.invoice.sale), 0)
            self.assertEqual(settled(result.invoice.sale), Decimal("16.02"))
            self.assertEqual(total(result.invoice.sale), Decimal("18.05"))
            delta = FinancialLineAdjustment.objects.get(scheduled_claim=result.claim)
            self.assertEqual(delta.fee, Decimal("-0.48"))
            with patch("core.payments.operations.Gateway") as gateway:
                self.approved(gateway, result.operation)
                self.assertEqual(execute(result.operation.pk).state, "succeeded")
                self.assertEqual(execute(result.operation.pk).state, "succeeded")
                self.assertEqual(gateway.return_value.charge.call_count, 1)
        self.assertEqual(received(original), source_money)
        self.assertEqual(received(result.invoice.sale), Decimal("2.03"))
        self.assertEqual(settled(result.invoice.sale), Decimal("18.05"))
        self.assertEqual(balance(self.customer.pk), 0)
        self.assertEqual(MessageDelivery.objects.count(), emails)

    def test_full_credit_creates_no_charge_receipt_job_or_success_email(self):
        _, _, member, _ = self.conversion(adults=2)
        item = member.installments.get(number=2)
        before = (
            PaymentOperation.objects.count(),
            FinancialPosting.objects.count(),
            DurableJob.objects.count(),
            MessageDelivery.objects.count(),
        )
        available = balance(self.customer.pk)
        with (
            clock(item.due_on),
            self.runtime_role(),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            result = schedule_installment(item.pk)
            self.assertIsNone(result.operation)
            self.assertTrue(installment_paid(result.invoice.installment))
            self.assertEqual(total(result.invoice.sale), Decimal("17.99"))
            self.assertEqual(received(result.invoice.sale), 0)
            self.assertEqual(settled(result.invoice.sale), Decimal("17.99"))
            gateway.assert_not_called()
        self.assertEqual(balance(self.customer.pk), available - Decimal("17.99"))
        self.assertEqual(
            (
                PaymentOperation.objects.count(),
                FinancialPosting.objects.count(),
                DurableJob.objects.count(),
                MessageDelivery.objects.count(),
            ),
            before,
        )

    def test_declined_card_remainder_can_be_explicitly_resolved_with_cash(self):
        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        with clock(item.due_on):
            result = schedule_installment(item.pk)
            record_result(
                operation_id=result.operation.pk,
                state="declined",
                source="provider",
                provider_reference="97771",
            )
            reviewed = payment_review(
                actor=self.staff, member_id=member.pk, installment_id=item.pk, tender="cash"
            )
            self.assertEqual(reviewed["total"], "1.97")
            action = collect_installment(
                actor=self.staff,
                member_id=member.pk,
                installment_id=item.pk,
                tender="cash",
                reviewed=reviewed["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
                verified_received=True,
            )
            self.assertEqual(str(action.operation.amount), "1.97")
            self.assertEqual(schedule_installment(item.pk).operation.pk, result.operation.pk)
        self.assertEqual(received(result.invoice.sale), Decimal("1.97"))
        self.assertEqual(settled(result.invoice.sale), Decimal("17.99"))
        self.assertEqual(total(result.invoice.sale), Decimal("17.99"))
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)

    def test_one_cent_credit_may_leave_the_same_rounded_fee_without_an_adjustment(self):
        _, _, member, _ = self.conversion(card=True)
        self.correction("16.01")
        item = member.installments.get(number=2)
        with clock(item.due_on):
            result = schedule_installment(item.pk)
        self.assertEqual(result.credit_application.amount, Decimal("0.01"))
        self.assertEqual(result.operation.amount, Decimal("18.52"))
        self.assertEqual(result.operation.allocation[0]["fee"], "0.54")
        self.assertFalse(
            FinancialLineAdjustment.objects.filter(scheduled_claim=result.claim).exists()
        )

    def test_split_receipt_sources_are_applied_in_their_original_order(self):
        booking = self.booking(children=2)
        visit = self.act(
            booking, self.arrival_inputs(booking, method="split", split={"cash": "10.00"})
        )
        card = visit.sale.operations.get(tender="card")
        record_result(
            operation_id=card.pk, state="succeeded", source="provider", provider_reference="451"
        )
        member = self.member(places=1, billing="monthly")
        quote = conversion_review(actor=self.staff, booking_id=booking.pk, member_id=member.pk)
        conversion = convert(
            actor=self.staff,
            booking_id=booking.pk,
            member_id=member.pk,
            reviewed=quote["fingerprint"],
            request_key=uuid.uuid4(),
            confirmed=True,
        )
        self.assertEqual(conversion.credits.count(), 2)
        item = member.installments.get(number=2)
        with clock(item.due_on):
            result = schedule_installment(item.pk)
        self.assertEqual(result.credit_application.allocations.count(), 2)
        allocations = {
            str(row.issue_id): row.amount for row in result.credit_application.allocations.all()
        }
        left = result.credit_application.amount
        for source in result.claim.details["credit_sources"]:
            used = min(left, Decimal(source["remaining"]))
            if used:
                self.assertEqual(allocations[source["id"]], used)
            left -= used
        self.assertEqual(left, 0)

    def test_full_credit_needs_no_active_card_and_readback_never_spends_again(self):
        _, _, member, _ = self.conversion(adults=2)
        method = member.billing_state.mandate.method
        method.state = "removed"
        method.save(update_fields=["state"])
        item = member.installments.get(number=2)
        with clock(item.due_on):
            result = schedule_installment(item.pk)
        remaining = balance(self.customer.pk)
        with (
            clock(item.due_on + timedelta(days=1)),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            again = schedule_installment(item.pk)
            self.assertEqual(again.credit_application.pk, result.credit_application.pk)
            self.assertIsNone(again.operation)
            gateway.assert_not_called()
        self.assertEqual(balance(self.customer.pk), remaining)
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)

    def test_credit_source_return_before_scheduling_creates_no_new_facts(self):
        _, original, member, _ = self.conversion(card=True)
        self.external_return(original.operations.get())
        item = member.installments.get(number=2)
        before = MembershipInvoice.objects.count(), PaymentOperation.objects.count()
        with clock(item.due_on), self.assertRaises(ValidationError):
            schedule_installment(item.pk)
        self.assertFalse(CustomerCreditApplication.objects.exists())
        self.assertFalse(MembershipCollectionClaim.objects.exists())
        self.assertEqual(
            (MembershipInvoice.objects.count(), PaymentOperation.objects.count()), before
        )

    def test_fully_spent_source_return_stops_the_card_remainder_before_post(self):
        _, original, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        with clock(item.due_on):
            result = schedule_installment(item.pk)
            self.assertEqual(balance(self.customer.pk), 0)
            self.external_return(original.operations.get())
            with patch("core.payments.operations.Gateway") as gateway:
                self.assertEqual(execute(result.operation.pk).state, "cancelled")
                gateway.return_value.charge.assert_not_called()
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)
        self.assertEqual(result.credit_application.amount, Decimal("16.02"))
        self.assertFalse(installment_paid(result.invoice.installment))

    def test_queue_fault_rolls_back_the_credit_fee_claim_invoice_and_card_request(self):
        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        before = (
            MembershipInvoice.objects.count(),
            PaymentOperation.objects.count(),
            FinancialPosting.objects.count(),
        )
        available = balance(self.customer.pk)
        with (
            clock(item.due_on),
            patch(
                "core.membership_collections.enqueue",
                side_effect=ValidationError("Local queue fault"),
            ),
            self.assertRaises(ValidationError),
        ):
            schedule_installment(item.pk)
        self.assertEqual(balance(self.customer.pk), available)
        self.assertFalse(CustomerCreditApplication.objects.exists())
        self.assertFalse(
            FinancialLineAdjustment.objects.filter(scheduled_claim__isnull=False).exists()
        )
        self.assertFalse(MembershipCollectionClaim.objects.exists())
        self.assertEqual(
            (
                MembershipInvoice.objects.count(),
                PaymentOperation.objects.count(),
                FinancialPosting.objects.count(),
            ),
            before,
        )

    def test_sql_system_actor_requires_exact_claim_customer_key_amount_and_fee_reason(self):
        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        other = Customer.objects.create(
            last_name="Other", phone="2025550123", email="other-scope@example.invalid"
        )
        with clock(item.due_on), self.runtime_role():
            claim = prepare_claim(item.pk)
            invoice = invoice_for(item, actor=None, tender="card", scheduled_claim=claim)
            values = dict(
                id=claim.credit_key,
                customer=self.customer,
                sale=invoice.sale,
                amount="16.02",
                fingerprint=claim.fingerprint,
                details=claim.details,
                actor=None,
                scheduled_claim=claim,
            )
            for changes in (
                {"id": uuid.uuid4()},
                {"customer": other},
                {"amount": "1.00"},
                {"scheduled_claim": None},
                {"actor": self.staff},
                {"fingerprint": "wrong"},
            ):
                with (
                    self.subTest(changes=changes),
                    self.assertRaises(DatabaseError),
                    transaction.atomic(),
                ):
                    CustomerCreditApplication.objects.create(**(values | changes))
            for changes in (
                {"reason": "owner_price"},
                {"fee": "0.48"},
                {"net": "-1.00"},
                {"scheduled_claim": None},
                {"request_key": uuid.uuid4()},
            ):
                fee = dict(
                    request_key=claim.credit_key,
                    line=invoice.sale.lines.get(),
                    reason="credit_application",
                    fee="-0.48",
                    actor=None,
                    scheduled_claim=claim,
                )
                with (
                    self.subTest(changes=changes),
                    self.assertRaises(DatabaseError),
                    transaction.atomic(),
                ):
                    FinancialLineAdjustment.objects.create(**(fee | changes))
            application = apply_scheduled_credit(claim)
            with (
                self.assertRaises(DatabaseError),
                transaction.atomic(),
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "UPDATE core_customercreditapplication SET amount=1 WHERE id=%s",
                    [application.pk],
                )
        self.assertEqual(
            CustomerCreditAllocation.objects.filter(application=application).count(), 1
        )

    def test_system_credit_cannot_be_reapplied_or_borrow_another_invoice(self):
        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        with clock(item.due_on):
            result = schedule_installment(item.pk)
            with self.assertRaises(ValidationError):
                apply_scheduled_credit(result.claim)
            again = schedule_installment(item.pk)
            self.assertEqual(again.credit_application.pk, result.credit_application.pk)
            self.assertEqual(again.operation.pk, result.operation.pk)
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)

    def test_sql_cancellation_boundary_rejects_a_prepared_claim_even_without_revision_change(self):
        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        with clock(item.due_on):
            claim = prepare_claim(item.pk)
            invoice = invoice_for(item, actor=None, tender="card", scheduled_claim=claim)
            billing = member.billing_state
            billing.stopped_on = item.cycle.starts_on
            billing.save(update_fields=["stopped_on"])
            with self.assertRaises(DatabaseError), transaction.atomic():
                CustomerCreditApplication.objects.create(
                    id=claim.credit_key,
                    customer=self.customer,
                    sale=invoice.sale,
                    amount="16.02",
                    fingerprint=claim.fingerprint,
                    details=claim.details,
                    actor=None,
                    scheduled_claim=claim,
                )
            with self.assertRaises(DatabaseError), transaction.atomic():
                FinancialLineAdjustment.objects.create(
                    request_key=claim.credit_key,
                    line=invoice.sale.lines.get(),
                    reason="credit_application",
                    fee="-0.48",
                    actor=None,
                    scheduled_claim=claim,
                )

    def test_new_credit_after_allocation_cannot_silently_change_the_queued_card_amount(self):
        _, _, member, _ = self.conversion(card=True)
        removed = self.correction("1.00")
        item = member.installments.get(number=2)
        with clock(item.due_on):
            result = schedule_installment(item.pk)
            self.assertEqual(str(result.operation.amount), "3.06")
            self.correction("1.00", kind="restore", original=removed)
            with patch("core.payments.operations.Gateway") as gateway:
                self.assertEqual(execute(result.operation.pk).state, "cancelled")
                gateway.return_value.charge.assert_not_called()
        self.assertEqual(result.credit_application.amount, Decimal("15.02"))
        self.assertEqual(balance(self.customer.pk), Decimal("1.00"))


@override_settings(**collections.SETTINGS)
class ScheduledCreditRaceTests(CreditFixtures, TransactionTestCase):
    setUp = credit_races.CustomerCreditRaceTests.setUp
    race = credit_races.CustomerCreditRaceTests.race

    def test_two_schedulers_share_one_credit_application_and_request(self):
        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        with clock(item.due_on):
            results = self.race(
                lambda: schedule_installment(item.pk).credit_application,
                lambda: schedule_installment(item.pk).credit_application,
            )
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)
        self.assertEqual(item.invoice.sale.operations.count(), 1)
        self.assertEqual(balance(self.customer.pk), 0)

    def test_competing_membership_installments_cannot_spend_the_same_credit(self):
        from core.membership_sales import offer, purchase

        _, _, first, _ = self.conversion(card=True)
        values = dict(
            actor=self.staff,
            customer=self.customer,
            kind="subscription",
            places=1,
            months=3,
            billing="monthly",
            starts_on=first.membership.starts_on,
            expected_method="cash",
        )
        second = purchase(
            **values,
            request_key=uuid.uuid4(),
            reviewed=offer(**values)["fingerprint"],
            accepted=True,
            verified_received=True,
            method_id=first.billing_state.mandate.method_id,
        )
        a, b = first.installments.get(number=2), second.installments.get(number=2)
        with clock(a.due_on):
            results = self.race(
                lambda: schedule_installment(a.pk).claim, lambda: schedule_installment(b.pk).claim
            )
        self.assertTrue(all(results))
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)
        self.assertEqual(CustomerCreditApplication.objects.get().amount, Decimal("16.02"))
        operations = PaymentOperation.objects.filter(
            sale__membership_invoice__installment__in=[a, b]
        )
        self.assertEqual(operations.count(), 2)
        self.assertEqual(sum(row.amount for row in operations), Decimal("20.56"))
        self.assertEqual(balance(self.customer.pk), 0)

    def test_owner_correction_and_collection_preserve_the_source_budget(self):
        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        with clock(item.due_on):
            results = self.race(
                lambda: self.correction("1.00"),
                lambda: schedule_installment(item.pk).credit_application,
            )
        self.assertIsNotNone(results[1])
        application = CustomerCreditApplication.objects.get()
        self.assertIn(application.amount, [Decimal("15.02"), Decimal("16.02")])
        self.assertEqual(balance(self.customer.pk), 0)
        self.assertEqual(item.invoice.sale.operations.count(), 1)

    def test_migration_reverse_refuses_to_remove_accepted_system_credit_facts(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.db.migrations.recorder import MigrationRecorder

        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        with clock(item.due_on):
            result = schedule_installment(item.pk)
        with (
            self.assertRaisesMessage(RuntimeError, "Scheduled credit facts prevent removing"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0073_scheduled_membership_claims")])
        result.credit_application.refresh_from_db()
        self.assertEqual(result.credit_application.amount, Decimal("16.02"))
        self.assertIn(
            ("core", "0074_scheduled_membership_credit_authority"),
            MigrationRecorder(connection).applied_migrations(),
        )
