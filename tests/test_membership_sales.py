"""Accepted purchases use real ledger boundaries with no external provider calls."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.membership_records import MembershipInvoice, MembershipPurchase
from core.membership_sales import membership_status, offer, purchase
from core.models import (
    FinancialPosting,
    FinancialSale,
    MembershipDraft,
    MembershipPricing,
    PaymentMethod,
    PaymentOperation,
)
from core.payments.ledger import full_allocation, record_result, request_operation
from core.payments.methods import begin_removal, retire_future_use
from tests.test_customers import staff_user
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class MembershipPurchaseTests(RuntimeRoleMixin, TestCase):
    def setUp(self):
        clock = patch(
            "django.utils.timezone.now",
            return_value=datetime(2027, 10, 31, 12, tzinfo=ZoneInfo("America/New_York")),
        )
        clock.start()
        self.addCleanup(clock.stop)
        self.staff = staff_user()
        self.owner = staff_user("owner", owner=True)
        from core.models import Customer

        self.customer = Customer.objects.create(
            last_name="Greenfeld", phone="2025550100", email="family@example.invalid"
        )
        self.method = PaymentMethod.objects.create(
            customer=self.customer,
            provider_customer="12",
            provider_method="345",
            brand="Visa",
            last_four="1118",
            reusable=True,
            consent_version="MD-PAYMENT-2026-01",
            consent_at=timezone.now(),
        )
        self.values = dict(
            actor=self.staff,
            customer=self.customer,
            kind="subscription",
            places=2,
            months=3,
            billing="monthly",
            starts_on=date(2027, 10, 31),
            expected_method="card",
        )
        self.key = uuid.uuid4()

    def buy(self, *, accepted=True, verified_received=False, send_confirmation=None, **changes):
        values = self.values | changes
        reviewed = offer(**values)["fingerprint"]
        return purchase(
            **values,
            request_key=self.key,
            reviewed=reviewed,
            accepted=accepted,
            method_id=self.method.pk
            if not values.get("comped")
            and (values["billing"] == "monthly" or values["expected_method"] == "card")
            else None,
            verified_received=verified_received,
            send_confirmation=send_confirmation,
        )

    def succeed(self, member):
        op = member.installments.first().invoice.sale.operations.get()
        record_result(
            operation_id=op.pk, state="succeeded", source="provider", provider_reference="1441913"
        )
        return op

    def test_offer_is_read_only_and_preserves_fixed_term_calendar_and_nontaxable_fee(self):
        data = offer(**self.values)
        self.assertEqual(data["installments"][0]["quote"]["total"], "37.06")
        self.assertEqual(data["installments"][0]["quote"]["sales_tax"], "0.00")
        self.assertEqual(
            [r["due_on"] for r in data["installments"]], ["2027-10-31", "2027-11-30", "2027-12-31"]
        )
        self.assertEqual(data["cycles"][1]["starts_on"], date(2027, 12, 1))
        self.assertEqual(data["ends_on"], "2028-01-30")
        self.assertFalse(MembershipDraft.objects.exists())
        self.assertFalse(FinancialSale.objects.exists())

    def test_purchase_pending_until_provider_success_records_funds_once_and_one_confirmation(self):
        member = self.buy()
        self.assertEqual(membership_status(member), "pending")
        self.assertFalse(MessageDelivery.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertEqual(member.installments.count(), 3)
        self.assertEqual(MembershipInvoice.objects.count(), 1)
        op = self.succeed(member)
        self.assertEqual(membership_status(member), "active")
        record_result(
            operation_id=op.pk, state="succeeded", source="provider", provider_reference="1441913"
        )
        self.assertEqual(FinancialPosting.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.get().membership_id, member.pk)
        self.assertEqual(membership_status(member, on=date(2027, 11, 30)), "overdue")
        self.assertEqual(membership_status(member, on=date(2028, 1, 31)), "expired")

    def test_decline_or_unknown_never_activates_or_claims_payment(self):
        member = self.buy()
        op = member.installments.first().invoice.sale.operations.get()
        record_result(
            operation_id=op.pk, state="unknown", source="provider", code="transport_unknown"
        )
        self.assertEqual(membership_status(member), "pending")
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertFalse(MessageDelivery.objects.filter(kind="membership_confirmation").exists())
        with self.assertRaises(ValidationError):
            request_operation(
                actor=self.staff,
                sale_id=op.sale_id,
                request_key=uuid.uuid4(),
                tender="card",
                allocation=op.allocation,
                method_id=self.method.pk,
                purpose="member_purchase",
            )

    def test_prepaid_cash_requires_receipt_confirmation_and_has_no_future_collection(self):
        with self.assertRaises(ValidationError):
            self.buy(billing="prepaid", expected_method="cash")
        self.assertFalse(MembershipPurchase.objects.exists())
        member = self.buy(billing="prepaid", expected_method="cash", verified_received=True)
        self.assertEqual(member.installments.count(), 1)
        self.assertEqual(member.installments.get().invoice.sale.total, Decimal("107.94"))
        self.assertIsNone(member.billing_state.mandate)
        self.assertEqual(membership_status(member), "active")
        self.assertEqual(FinancialPosting.objects.get().net, Decimal("107.94"))
        self.assertEqual(FinancialPosting.objects.get().item_tax, Decimal("0"))

    def test_monthly_cash_initial_payment_keeps_card_for_future_installments(self):
        member = self.buy(expected_method="cash", verified_received=True)
        self.assertEqual(member.installments.get(number=1).quote["total"], "35.98")
        self.assertEqual(member.installments.get(number=2).quote["total"], "37.06")
        self.assertEqual(member.billing_state.mandate.method_id, self.method.pk)
        self.assertEqual(membership_status(member), "active")
        retire_future_use(actor=self.staff, method_id=self.method.pk)
        with self.assertRaises(ValidationError):
            begin_removal(self.method.pk)

    def test_exact_purchase_replay_does_not_duplicate_financial_or_email_records(self):
        member = self.buy()
        self.succeed(member)
        self.assertEqual(self.buy().pk, member.pk)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.filter(kind="membership_confirmation").count(), 1)
        with self.assertRaises(ValidationError):
            self.buy(places=3)

    def test_stale_quote_and_unaccepted_terms_create_nothing(self):
        reviewed = offer(**self.values)["fingerprint"]
        MembershipPricing.objects.create(subscription="20", unlimited="45", actor=self.owner)
        with self.assertRaises(ValidationError):
            purchase(
                **self.values,
                request_key=self.key,
                reviewed=reviewed,
                accepted=True,
                method_id=self.method.pk,
            )
        with self.assertRaises(ValidationError):
            self.buy(accepted=False)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(FinancialSale.objects.exists())

    def test_owner_exception_comped_requires_explicit_email_choice_and_has_no_receipt(self):
        with self.assertRaises(PermissionDenied):
            self.buy(comped=True, months=1)
        with self.assertRaises(ValidationError):
            self.buy(actor=self.owner, comped=True, months=1)
        member = self.buy(actor=self.owner, comped=True, months=1, send_confirmation=False)
        self.assertEqual(membership_status(member), "active")
        self.assertEqual(member.membership.months, 1)
        self.assertFalse(FinancialSale.objects.exists())
        self.assertFalse(MessageDelivery.objects.exists())

    def test_future_start_collects_now_but_benefits_are_scheduled(self):
        member = self.buy(starts_on=date(2027, 11, 15))
        self.assertEqual(str(member.installments.first().due_on), "2027-10-31")
        self.succeed(member)
        self.assertEqual(membership_status(member), "scheduled")
        self.assertEqual(membership_status(member, on=date(2027, 11, 15)), "active")

    def test_runtime_append_only_grants_allow_real_purchase_and_success(self):
        with self.runtime_role():
            member = self.buy()
            self.succeed(member)
            self.assertEqual(membership_status(member), "active")
        self.assertEqual(FinancialPosting.objects.count(), 1)

    def test_membership_facts_and_message_identity_cannot_be_rewritten(self):
        member = self.buy()
        self.succeed(member)
        for obj in [
            member,
            member.installments.first(),
            member.installments.first().invoice,
            member.billing_state.mandate,
        ]:
            with self.assertRaises(ValidationError):
                obj.save()
            table, column = obj._meta.db_table, obj._meta.pk.column
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {table} SET {column}={column} WHERE {column}=%s", [obj.pk]
                    )
        with self.assertRaises(DatabaseError), transaction.atomic():
            MessageDelivery.objects.filter(membership=member).update(membership=None)

    def test_feature_off_and_recovery_hold_block_all_sales(self):
        for settings in [{"MEMBERSHIP_SALES_ENABLED": False}, {"RECOVERY_HOLD": True}]:
            with override_settings(**settings), self.assertRaises(ValidationError):
                self.buy()
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_other_saved_card_cannot_bypass_accepted_mandate(self):
        member = self.buy()
        sale = member.installments.first().invoice.sale
        with self.assertRaises(ValidationError):
            request_operation(
                actor=self.staff,
                sale_id=sale.pk,
                request_key=uuid.uuid4(),
                tender="card",
                allocation=full_allocation(sale),
                method_id=uuid.uuid4(),
                purpose="member_purchase",
            )

    def test_fixed_term_gateway_flags_distinguish_purchase_and_later_installment(self):
        from core.membership_sales import invoice_for
        from core.payments.gateway import Gateway

        member = self.buy()
        first = member.installments.first().invoice.sale.operations.get()
        gateway = Gateway()
        with patch.object(gateway, "request", return_value={}) as request:
            gateway.charge(first)
        flags = request.call_args.args[2]["transaction_flags"]
        self.assertTrue(flags["is_installment"])
        self.assertTrue(flags["is_customer_initiated"])
        self.assertFalse(flags["is_recurring"])
        self.assertFalse(flags["card_present"])
        invoice = invoice_for(member.installments.get(number=2), actor=self.staff, tender="card")
        later = request_operation(
            actor=self.staff,
            sale_id=invoice.sale_id,
            request_key=uuid.uuid4(),
            tender="card",
            allocation=full_allocation(invoice.sale),
            method_id=self.method.pk,
            purpose="member_installment",
        )
        with patch.object(gateway, "request", return_value={}) as request:
            gateway.charge(later)
        flags = request.call_args.args[2]["transaction_flags"]
        self.assertTrue(flags["is_installment"])
        self.assertFalse(flags["is_customer_initiated"])
        self.assertFalse(flags["is_recurring"])

    def test_prepaid_gateway_request_is_not_a_recurring_or_installment_charge(self):
        from core.payments.gateway import Gateway

        member = self.buy(billing="prepaid")
        op = member.installments.get().invoice.sale.operations.get()
        gateway = Gateway()
        with patch.object(gateway, "request", return_value={}) as request:
            gateway.charge(op)
        flags = request.call_args.args[2]["transaction_flags"]
        self.assertFalse(flags["is_installment"])
        self.assertFalse(flags["is_recurring"])
        self.assertTrue(flags["is_customer_initiated"])

    def test_expired_term_does_not_release_card_needed_for_unpaid_installments(self):
        from core.payments.methods import outstanding

        member = self.buy()
        self.succeed(member)
        retire_future_use(actor=self.staff, method_id=self.method.pk)
        self.method.refresh_from_db()
        with patch("core.membership_sales.today", return_value=date(2028, 2, 1)):
            self.assertTrue(outstanding(self.method))
            with self.assertRaises(ValidationError):
                begin_removal(self.method.pk)

    def test_paid_prepaid_term_does_not_force_continuing_card_retention(self):
        from core.payments.methods import outstanding

        member = self.buy(billing="prepaid")
        self.succeed(member)
        retire_future_use(actor=self.staff, method_id=self.method.pk)
        self.method.refresh_from_db()
        self.assertFalse(outstanding(self.method))
