"""Scheduled collection planning observes settled history and never spends money."""

import io
import json
import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.membership_collection_plan import installment_plan, review_due
from core.membership_payments import collect_installment, payment_review
from core.membership_renewals import renewal_details
from core.models import (
    AuditEvent,
    DurableJob,
    FinancialPosting,
    MembershipInvoice,
    MembershipPricing,
    PaymentOperation,
    PricingPolicy,
)
from core.payments.ledger import record_result
from tests import test_customer_credit as credit_fixtures
from tests import test_membership_funding as funding_fixtures
from tests import test_membership_sales as fixtures
from tests.test_owner_accounts import STORAGES

SETTINGS = dict(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)


@override_settings(**SETTINGS)
class MembershipCollectionPlanTests(TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed
    report_return = funding_fixtures.MembershipFundingTests.report_return

    def funded(self):
        member = self.buy()
        self.succeed(member)
        return member, member.installments.get(number=2)

    def counts(self):
        return tuple(
            model.objects.count()
            for model in (
                MembershipInvoice,
                PaymentOperation,
                FinancialPosting,
                DurableJob,
                AuditEvent,
            )
        )

    def test_due_plan_uses_accepted_price_card_and_calendar_without_creating_work(self):
        member, item = self.funded()
        before = self.counts()
        with patch("core.payments.gateway.Gateway") as gateway:
            data = installment_plan(item.pk, on=item.due_on)
            self.assertEqual(data["status"], "ready_for_scheduling")
            self.assertEqual(data["principal_due"], "35.98")
            self.assertEqual(data["card_fee"], "1.08")
            self.assertEqual(data["card_total"], "37.06")
            self.assertEqual(data["method"], str(self.method.pk))
            self.assertEqual(data["mandate"], str(member.billing_state.mandate_id))
            self.assertEqual(installment_plan(item.pk, on=item.due_on), data)
            gateway.assert_not_called()
        self.assertEqual(self.counts(), before)

    def test_unpaid_first_payment_blocks_the_later_distinct_installment(self):
        member = self.buy()
        first = member.installments.first().invoice.sale.operations.get()
        record_result(
            operation_id=first.pk, state="declined", source="provider", provider_reference="87001"
        )
        item = member.installments.get(number=2)
        data = installment_plan(item.pk, on=item.due_on)
        self.assertEqual(data["status"], "review")
        self.assertIn("previous_unpaid", data["reasons"])
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_a_missed_date_needs_explicit_review_and_never_backfills_automatically(self):
        _, item = self.funded()
        data = installment_plan(item.pk, on=item.due_on + timedelta(days=1))
        self.assertIn("past_due_review", data["reasons"])
        self.assertEqual(data["status"], "review")
        self.assertEqual(MembershipInvoice.objects.count(), 1)

    def test_future_first_purchase_and_ended_terms_are_outside_current_scheduling(self):
        member, item = self.funded()
        self.assertIn(
            "not_due", installment_plan(item.pk, on=item.due_on - timedelta(days=1))["reasons"]
        )
        self.assertIn(
            "initial_purchase",
            installment_plan(member.installments.first().pk, on=item.due_on)["reasons"],
        )
        ended = installment_plan(item.pk, on=member.membership.ends_on + timedelta(days=1))
        self.assertIn("term_ended", ended["reasons"])
        self.assertFalse(ended["status"] == "ready_for_scheduling")

    def test_existing_payment_review_or_known_decline_cannot_be_requeued(self):
        member, item = self.funded()
        with patch("core.membership_payments.today", return_value=item.due_on):
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
        record_result(
            operation_id=action.operation_id,
            state="declined",
            source="provider",
            provider_reference="87002",
        )
        before = self.counts()
        data = installment_plan(item.pk, on=item.due_on)
        self.assertIn("existing_invoice", data["reasons"])
        self.assertEqual(data["status"], "review")
        self.assertEqual(self.counts(), before)

    def test_paid_installment_has_zero_remaining_card_or_credit_amount(self):
        member, item = self.funded()
        with patch("core.membership_payments.today", return_value=item.due_on):
            data = payment_review(
                actor=self.staff, member_id=member.pk, installment_id=item.pk, tender="cash"
            )

            collect_installment(
                actor=self.staff,
                member_id=member.pk,
                installment_id=item.pk,
                tender="cash",
                reviewed=data["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
                verified_received=True,
            )
        data = installment_plan(item.pk, on=item.due_on)
        self.assertEqual(data["status"], "paid")
        self.assertEqual(data["card_total"], "0.00")
        self.assertEqual(data["credit_to_apply"], "0.00")

    def test_cancelled_cycle_and_unavailable_card_require_review(self):
        member, item = self.funded()
        billing = member.billing_state
        billing.stopped_on = item.cycle.starts_on
        billing.save(update_fields=["stopped_on"])
        self.method.state = "removed"
        self.method.save(update_fields=["state"])
        data = installment_plan(item.pk, on=item.due_on)
        self.assertIn("cancelled_cycle", data["reasons"])
        self.assertIn("card_unavailable", data["reasons"])

    def test_new_pricing_does_not_rewrite_the_accepted_installment(self):
        _, item = self.funded()
        MembershipPricing.objects.create(subscription="25.00", unlimited="55.00", actor=self.owner)
        PricingPolicy.objects.create(card_fee_rate="0.08")
        self.assertEqual(installment_plan(item.pk, on=item.due_on)["card_total"], "37.06")

    def test_reported_return_of_prior_funding_blocks_new_collection(self):
        member, item = self.funded()
        self.report_return(member.installments.first().invoice.sale.operations.get())
        data = installment_plan(item.pk, on=item.due_on)
        self.assertIn("funding_review", data["reasons"])
        self.assertIn("previous_unpaid", data["reasons"])
        self.assertEqual(data["status"], "review")

    def test_parent_arrears_remain_guarded_without_assuming_the_pending_policy(self):
        parent, _ = self.funded()
        self.key = uuid.uuid4()
        child = self.buy(
            operation="renewal",
            prior_id=parent.pk,
            starts_on=renewal_details(parent)["starts_on"],
            months=3,
        )
        record_result(
            operation_id=child.installments.first().invoice.sale.operations.get().pk,
            state="succeeded",
            source="provider",
            provider_reference="87003",
        )
        item = child.installments.get(number=2)
        data = installment_plan(item.pk, on=item.due_on)
        self.assertIn("parent_review", data["reasons"])
        self.assertEqual(data["status"], "review")

    def test_due_date_is_new_york_date_and_command_is_read_only(self):
        _, item = self.funded()
        with patch(
            "django.utils.timezone.now",
            return_value=datetime(2027, 11, 30, 4, 30, tzinfo=dt_timezone.utc),
        ):
            self.assertEqual(review_due()["rows"], [])
        before = self.counts()
        with patch(
            "django.utils.timezone.now",
            return_value=datetime(2027, 11, 30, 5, 30, tzinfo=dt_timezone.utc),
        ):
            output = io.StringIO()
            call_command("preview_membership_installments", stdout=output)
            data = json.loads(output.getvalue())
            self.assertTrue(data["read_only"])
            self.assertEqual(data["date"], "2027-11-30")
            self.assertEqual(data["ready"], 1)
        self.assertEqual(self.counts(), before)

    def test_input_and_feature_gates_cannot_create_payment_work(self):
        _, item = self.funded()
        with self.assertRaises(ValidationError):
            installment_plan(item.pk, on=datetime.now())
        for limit in (0, 101, True):
            with self.assertRaises(ValidationError):
                review_due(limit=limit)
        with self.assertRaises(CommandError):
            call_command("preview_membership_installments", limit=0)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False), self.assertRaises(ValidationError):
            review_due()


@override_settings(**SETTINGS)
class MembershipCollectionCreditPlanTests(TestCase):
    setUp = credit_fixtures.CustomerCreditTests.setUp
    flow = credit_fixtures.CustomerCreditTests.flow
    card = credit_fixtures.CustomerCreditTests.card
    save_card = credit_fixtures.CustomerCreditTests.save_card
    booking = credit_fixtures.CustomerCreditTests.booking
    arrival_inputs = credit_fixtures.CustomerCreditTests.arrival_inputs
    create = credit_fixtures.CustomerCreditTests.create
    gateway = credit_fixtures.CustomerCreditTests.gateway
    ready = credit_fixtures.CustomerCreditTests.ready
    member = credit_fixtures.CustomerCreditTests.member
    act = credit_fixtures.CustomerCreditTests.act
    paid_visit = credit_fixtures.CustomerCreditTests.paid_visit
    conversion = credit_fixtures.CustomerCreditTests.conversion
    external_return = credit_fixtures.CustomerCreditTests.external_return

    def test_backed_credit_reduces_only_new_principal_and_its_fee_without_spending(self):
        from core.customer_credit import balance
        from core.customer_credit_records import CustomerCreditApplication

        _, _, member, _ = self.conversion(card=True)
        item = member.installments.get(number=2)
        data = installment_plan(item.pk, on=item.due_on)
        self.assertEqual(data["status"], "ready_for_scheduling")
        self.assertEqual(data["credit_available"], "16.02")
        self.assertEqual(data["credit_to_apply"], "16.02")
        self.assertEqual(data["remaining_principal"], "1.97")
        self.assertEqual(data["card_fee"], "0.06")
        self.assertEqual(data["card_total"], "2.03")
        self.assertEqual(str(balance(self.customer.pk)), "16.02")
        self.assertFalse(CustomerCreditApplication.objects.exists())

    def test_credit_can_cover_the_whole_principal_without_a_card_fee(self):
        from core.customer_credit import balance

        _, _, member, _ = self.conversion(adults=2)
        item = member.installments.get(number=2)
        before = balance(self.customer.pk)
        self.assertGreater(before, 17)
        data = installment_plan(item.pk, on=item.due_on)
        self.assertEqual(data["credit_to_apply"], "17.99")
        self.assertEqual(data["card_fee"], "0.00")
        self.assertEqual(data["card_total"], "0.00")
        self.assertEqual(balance(self.customer.pk), before)

    def test_held_credit_cannot_be_silently_skipped_for_a_larger_card_charge(self):
        _, sale, member, _ = self.conversion(card=True)
        self.external_return(sale.operations.get())
        item = member.installments.get(number=2)
        data = installment_plan(item.pk, on=item.due_on)
        self.assertEqual(data["held_credit"], "16.02")
        self.assertEqual(data["credit_to_apply"], "0.00")
        self.assertIn("held_credit", data["reasons"])
        self.assertEqual(data["status"], "review")

    def test_full_backed_credit_needs_no_active_card_for_this_installment(self):
        _, _, member, _ = self.conversion(adults=2)
        card = member.billing_state.mandate.method
        card.state = "removed"
        card.save(update_fields=["state"])
        item = member.installments.get(number=2)
        data = installment_plan(item.pk, on=item.due_on)
        self.assertEqual(data["card_total"], "0.00")
        self.assertEqual(data["status"], "ready_for_scheduling")
