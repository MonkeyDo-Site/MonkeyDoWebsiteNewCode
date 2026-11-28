"""Existing recorded credit funds a new purchase before requesting its balance."""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.availability import NEW_YORK
from core.customer_credit import applied, balance
from core.customer_credit_records import CustomerCreditApplication
from core.membership_payments import collect_installment, payment_review
from core.membership_records import MembershipPurchase
from core.membership_sales import membership_status, offer, purchase
from core.models import FinancialPosting, PaymentOperation
from core.payments.invoices import received, settled, total
from core.payments.ledger import record_result
from tests import test_customer_credit as fixtures
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin

SETTINGS = dict(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake",
)


class InitialCreditFixtures:
    setUp = fixtures.CustomerCreditTests.setUp
    flow = fixtures.CustomerCreditTests.flow
    card = fixtures.CustomerCreditTests.card
    save_card = fixtures.CustomerCreditTests.save_card
    booking = fixtures.CustomerCreditTests.booking
    arrival_inputs = fixtures.CustomerCreditTests.arrival_inputs
    create = fixtures.CustomerCreditTests.create
    gateway = fixtures.CustomerCreditTests.gateway
    ready = fixtures.CustomerCreditTests.ready
    member = fixtures.CustomerCreditTests.member
    act = fixtures.CustomerCreditTests.act
    conversion = fixtures.CustomerCreditTests.conversion
    paid_visit = fixtures.CustomerCreditTests.paid_visit
    external_return = fixtures.CustomerCreditTests.external_return

    def values(self, *, credit="16.02", **changes):
        return (
            dict(
                actor=self.staff,
                customer=self.customer,
                kind="subscription",
                places=1,
                months=3,
                billing="monthly",
                starts_on=timezone.localdate(timezone=NEW_YORK),
                expected_method="card",
                credit_amount=credit,
            )
            | changes
        )

    def buy(self, values, *, key=None, reviewed=None, verified=False, method=None):
        return purchase(
            **values,
            request_key=key or uuid.uuid4(),
            reviewed=reviewed or offer(**values)["fingerprint"],
            accepted=True,
            method_id=method.pk if method else None,
            verified_received=verified,
        )


@override_settings(**SETTINGS)
class InitialMembershipCreditTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    def test_card_charge_is_only_remaining_principal_plus_its_own_fee(self):
        _, original, prior, _ = self.conversion(card=True)
        values = self.values()
        before = FinancialPosting.objects.count()
        data = offer(**values)
        self.assertEqual(data["first_payment_total"], "2.03")
        self.assertEqual(data["installments"][0]["quote"]["processing_fee"], "0.06")
        self.assertEqual(data["installments"][1]["quote"]["total"], "18.53")
        key = uuid.uuid4()
        with self.runtime_role():
            member = self.buy(
                values,
                key=key,
                reviewed=data["fingerprint"],
                method=prior.billing_state.mandate.method,
            )
            repeated = self.buy(
                values,
                key=key,
                reviewed=data["fingerprint"],
                method=prior.billing_state.mandate.method,
            )
        self.assertEqual(member.pk, repeated.pk)
        sale = member.installments.first().invoice.sale
        operation = sale.operations.get()
        self.assertEqual(operation.amount, Decimal("2.03"))
        self.assertEqual(operation.allocation[0]["net"], "1.97")
        self.assertEqual(operation.allocation[0]["fee"], "0.06")
        self.assertEqual(applied(sale), Decimal("16.02"))
        self.assertEqual(received(sale), 0)
        self.assertEqual(membership_status(member), "pending")
        self.assertEqual(FinancialPosting.objects.count(), before)
        record_result(
            operation_id=operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="852",
        )
        self.assertEqual(membership_status(member), "active")
        self.assertEqual(received(sale), Decimal("2.03"))
        self.assertEqual(settled(sale), total(sale))
        self.assertEqual(total(sale), Decimal("18.05"))
        self.assertEqual(received(original), Decimal("16.47"))
        self.assertEqual(total(original), Decimal("0.45"))
        self.assertEqual(balance(self.customer.pk), 0)

    def test_cash_credit_funding_never_adds_a_card_fee_or_records_credit_as_cash(self):
        _, _, prior, _ = self.conversion()
        values = self.values(credit="15.99", expected_method="cash")
        data = offer(**values)
        self.assertEqual(data["first_payment_total"], "2.00")
        self.assertEqual(data["installments"][0]["quote"]["processing_fee"], "0.00")
        with self.assertRaisesMessage(ValidationError, "actually received"):
            self.buy(values, method=prior.billing_state.mandate.method)
        member = self.buy(values, method=prior.billing_state.mandate.method, verified=True)
        sale = member.installments.first().invoice.sale
        self.assertEqual(received(sale), Decimal("2.00"))
        self.assertEqual(sale.operations.get().tender, "cash")
        self.assertEqual(applied(sale), Decimal("15.99"))
        self.assertEqual(total(sale), Decimal("17.99"))
        self.assertEqual(membership_status(member), "active")

    def test_credit_covering_first_month_still_requires_a_future_card_mandate(self):
        _, _, prior, _ = self.conversion(children=2, adults=2)
        values = self.values(credit="17.99", expected_method="cash")
        self.assertEqual(offer(**values)["first_payment_total"], "0.00")
        with self.assertRaisesMessage(ValidationError, "current saved card"):
            self.buy(values)
        member = self.buy(values, method=prior.billing_state.mandate.method)
        sale = member.installments.first().invoice.sale
        self.assertFalse(sale.operations.exists())
        self.assertEqual(received(sale), 0)
        self.assertEqual(applied(sale), Decimal("17.99"))
        self.assertEqual(membership_status(member), "active")
        self.assertEqual(balance(self.customer.pk), Decimal("19.32"))

    def test_prepaid_fully_funded_purchase_needs_no_card_or_zero_dollar_receipt(self):
        self.conversion(children=5, adults=2)
        values = self.values(credit="53.97", billing="prepaid")
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        member = self.buy(values)
        self.assertIsNone(member.billing_state.mandate_id)
        self.assertEqual(membership_status(member), "active")
        self.assertEqual(
            (PaymentOperation.objects.count(), FinancialPosting.objects.count()), before
        )
        self.assertEqual(applied(member.installments.first().invoice.sale), Decimal("53.97"))
        self.assertEqual(balance(self.customer.pk), Decimal("31.31"))

    def test_credit_is_due_at_purchase_even_for_a_future_membership_start(self):
        _, _, prior, _ = self.conversion(children=2, adults=2)
        values = self.values(
            credit="17.99", starts_on=timezone.localdate(timezone=NEW_YORK) + timedelta(days=14)
        )
        member = self.buy(values, method=prior.billing_state.mandate.method)
        self.assertEqual(member.installments.first().due_on, timezone.localdate(timezone=NEW_YORK))
        self.assertEqual(membership_status(member), "scheduled")

    def test_ordinary_decline_waits_for_explicit_retry_without_applying_credit_again(self):
        _, _, prior, _ = self.conversion(card=True)
        member = self.buy(self.values(), method=prior.billing_state.mandate.method)
        item = member.installments.first()
        original = item.invoice.sale.operations.get()
        record_result(operation_id=original.pk, state="declined", source="provider")
        count = CustomerCreditApplication.objects.count()
        values = dict(actor=self.staff, member_id=member.pk, installment_id=item.pk, tender="card")
        data = payment_review(**values)
        self.assertEqual(data["total"], "2.03")
        action = collect_installment(
            **values, request_key=uuid.uuid4(), reviewed=data["fingerprint"], confirmed=True
        )
        self.assertEqual(action.operation.amount, Decimal("2.03"))
        self.assertEqual(CustomerCreditApplication.objects.count(), count)
        self.assertEqual(applied(item.invoice.sale), Decimal("16.02"))

    def test_stale_or_reported_source_credit_cannot_create_a_partial_purchase(self):
        _, source, prior, _ = self.conversion(card=True)
        values = self.values()
        data = offer(**values)
        before = MembershipPurchase.objects.count(), PaymentOperation.objects.count()
        self.external_return(source.operations.get())
        with self.assertRaises(ValidationError):
            self.buy(
                values, reviewed=data["fingerprint"], method=prior.billing_state.mandate.method
            )
        self.assertEqual(
            (MembershipPurchase.objects.count(), PaymentOperation.objects.count()), before
        )

    def test_zero_selection_keeps_the_original_offer_fingerprint_and_credit_is_bounded(self):
        self.conversion(card=True)
        values = self.values()
        without = values.copy()
        without.pop("credit_amount")
        self.assertEqual(
            offer(**without)["fingerprint"],
            offer(**(values | dict(credit_amount="0.00")))["fingerprint"],
        )
        for amount in ("-1.00", "16.03"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                offer(**(values | dict(credit_amount=amount)))
