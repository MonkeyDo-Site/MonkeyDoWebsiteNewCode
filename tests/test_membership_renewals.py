"""Renewal/addition cohorts preserve original terms and prevent duplicate places."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from core.membership_records import MembershipOrigin
from core.membership_renewals import remaining_places, renewal_details
from core.membership_sales import membership_status, offer, purchase
from core.models import FinancialSale, MembershipPricing
from tests import test_membership_sales as fixtures
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin


def clock(day):
    return patch(
        "django.utils.timezone.now",
        return_value=datetime.combine(
            day, datetime.min.time(), ZoneInfo("America/New_York")
        ).replace(hour=12),
    )


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
)
class MembershipRenewalTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed

    def prior(self, **values):
        self.key = uuid.uuid4()
        return self.buy(billing="prepaid", expected_method="cash", verified_received=True, **values)

    def follow_values(self, prior, *, operation="renewal", **changes):
        starts = (
            renewal_details(prior)["starts_on"] if operation == "renewal" else date(2027, 10, 31)
        )
        return (
            dict(
                actor=self.staff,
                customer=self.customer,
                kind=prior.membership.kind,
                places=1,
                months=1 if operation == "renewal" else 3,
                billing="prepaid",
                starts_on=starts,
                expected_method="cash",
                operation=operation,
                prior_id=prior.pk,
            )
            | changes
        )

    def follow(self, prior, *, key=None, **changes):
        values = self.follow_values(prior, **changes)
        return purchase(
            **values,
            request_key=key or uuid.uuid4(),
            reviewed=offer(**values)["fingerprint"],
            accepted=True,
            verified_received=True,
            method_id=self.method.pk
            if values["expected_method"] == "card" or values["billing"] == "monthly"
            else None,
        )

    def test_early_renewal_starts_day_after_expiry_and_preserves_original_prices_and_history(self):
        prior = self.prior()
        old = prior.membership
        saved = [item.quote for item in prior.installments.all()]
        MembershipPricing.objects.create(subscription="20.00", unlimited="45.00", actor=self.owner)
        renewed = self.follow(prior)
        self.assertNotEqual(renewed.pk, prior.pk)
        self.assertEqual(renewed.membership.starts_on, old.ends_on.replace(day=31))
        self.assertEqual(renewed.membership.starts_on, date(2028, 1, 31))
        self.assertEqual(renewed.membership.ends_on, date(2028, 2, 29))
        self.assertEqual(renewed.membership.unit_price, Decimal("20"))
        self.assertEqual(renewed.purpose, "renewal")
        self.assertEqual(renewed.origin.prior_id, prior.pk)
        self.assertEqual(membership_status(renewed), "scheduled")
        old.refresh_from_db()
        self.assertEqual(old.unit_price, Decimal("17.99"))
        self.assertEqual([item.quote for item in prior.installments.all()], saved)
        self.assertEqual(old.cycles.count(), 3)
        self.assertNotIn(
            "Membership cannot be cancelled during the initial three month term", renewed.terms_text
        )

    def test_seven_day_grace_boundary_and_no_backdated_benefits(self):
        with clock(date(2027, 9, 6)):
            prior = self.prior(starts_on=date(2027, 9, 6))
        self.assertEqual(prior.membership.ends_on, date(2027, 12, 5))
        for day, minimum in [(6, 1), (10, 1), (12, 1), (13, 3)]:
            with self.subTest(day=day), clock(date(2027, 12, day)):
                details = renewal_details(prior)
                self.assertEqual(details["starts_on"], date(2027, 12, day))
                self.assertEqual(details["minimum_months"], minimum)
                if day == 13:
                    with self.assertRaises(ValidationError):
                        offer(**self.follow_values(prior))
        with clock(date(2027, 12, 10)):
            renewed = self.follow(prior)
            self.assertEqual(renewed.membership.starts_on, date(2027, 12, 10))
            self.assertEqual(renewed.installments.get().due_on, date(2027, 12, 10))
            from core.membership_reservations import places_for

            self.assertEqual(
                places_for(self.customer.pk, appointment_on=date(2027, 12, 8), children=1), []
            )

    def test_partial_renewal_limits_remaining_places_and_replay_does_not_reserve_twice(self):
        prior = self.prior()
        key = uuid.uuid4()
        renewed = self.follow(prior, key=key)
        self.assertEqual(remaining_places(prior), 1)
        original = renewed.fingerprint
        replay = purchase(
            **self.follow_values(prior),
            request_key=key,
            reviewed=original,
            accepted=True,
            verified_received=True,
        )
        self.assertEqual(replay.pk, renewed.pk)
        self.assertEqual(remaining_places(prior), 1)
        self.follow(prior)
        self.assertEqual(remaining_places(prior), 0)
        before = FinancialSale.objects.count()
        with self.assertRaises(ValidationError):
            self.follow(prior)
        self.assertEqual(FinancialSale.objects.count(), before)

    def test_stale_renewal_place_count_is_rejected_before_collecting(self):
        prior = self.prior()
        values = self.follow_values(prior)
        reviewed = offer(**values)["fingerprint"]
        self.follow(prior)
        before = FinancialSale.objects.count()
        with self.assertRaisesMessage(ValidationError, "membership or price changed"):
            purchase(
                **values,
                request_key=uuid.uuid4(),
                reviewed=reviewed,
                accepted=True,
                verified_received=True,
            )
        self.assertEqual(FinancialSale.objects.count(), before)

    def test_additional_places_have_their_own_three_month_commitment_and_dates(self):
        prior = self.prior()
        with self.assertRaises(ValidationError):
            self.follow(prior, operation="addition", months=2)
        added = self.follow(
            prior, operation="addition", kind="unlimited", places=3, starts_on=date(2027, 11, 15)
        )
        self.assertEqual(added.membership.starts_on, date(2027, 11, 15))
        self.assertEqual(added.membership.ends_on, date(2028, 2, 14))
        self.assertEqual(added.origin.operation, "addition")
        self.assertEqual(remaining_places(prior), 2)
        self.assertEqual(prior.membership.ends_on, date(2028, 1, 30))

    def test_type_conversion_waits_for_original_expiry(self):
        prior = self.prior()
        converted = self.follow(prior, kind="unlimited")
        self.assertEqual(converted.membership.kind, "unlimited")
        self.assertEqual(converted.membership.starts_on, date(2028, 1, 31))
        with self.assertRaises(ValidationError):
            self.follow(prior, starts_on=date(2027, 10, 31))

    def test_unpaid_original_cannot_obtain_a_short_renewal(self):
        prior = self.buy()
        with self.assertRaises(ValidationError):
            renewal_details(prior)
        self.assertFalse(MembershipOrigin.objects.exists())

    def test_original_from_another_customer_cannot_supply_a_renewal_exception(self):
        from core.models import Customer

        prior = self.prior()
        other = Customer.objects.create(
            last_name="Other", phone="2025550102", email="other@example.invalid"
        )
        with self.assertRaises(ValidationError):
            offer(**self.follow_values(prior, customer=other))
        with self.assertRaises(ValidationError):
            offer(**self.follow_values(prior, operation="purchase", months=1))
        self.assertFalse(MembershipOrigin.objects.exists())

    def test_owner_may_override_new_addition_minimum_but_staff_cannot(self):
        prior = self.prior()
        with self.assertRaises(PermissionDenied):
            self.follow(prior, operation="addition", months=1, minimum_override=True)
        added = self.follow(
            prior, actor=self.owner, operation="addition", months=1, minimum_override=True
        )
        self.assertEqual(added.membership.months, 1)
        self.assertEqual(added.origin.minimum_months, 3)
        self.assertIn("owner has approved", added.terms_text)

    def test_existing_membership_card_can_be_reaccepted_without_enabling_future_visit_use(self):
        prior = self.buy()
        self.succeed(prior)
        self.method.reusable = False
        self.method.save(update_fields=["reusable"])
        renewed = self.follow(prior, billing="monthly", expected_method="card")
        self.assertEqual(renewed.billing_state.mandate.method_id, self.method.pk)
        self.assertEqual(membership_status(renewed), "pending")
        self.method.refresh_from_db()
        self.assertFalse(self.method.reusable)

    def test_runtime_grants_can_create_follow_on_facts_and_origin_cannot_be_rewritten(self):
        prior = self.prior()
        with self.runtime_role():
            renewed = self.follow(prior)
        origin = renewed.origin
        with self.assertRaises(ValidationError):
            origin.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_membershiporigin SET places=0 WHERE purchase_id=%s", [renewed.pk]
                )

    def test_completed_membership_setup_is_not_abandoned_when_its_browser_flow_expires(self):
        from core.payments.methods import expire_unused_setups
        from tests import test_payment_setup as setup_fixtures

        flow = setup_fixtures.CardSetupTests.flow(self)
        with patch("core.payments.setup.Gateway") as provider:
            provider.return_value.create_customer.return_value = {"id": 12}
            provider.return_value.save_card.return_value = {"id": 123}
            provider.return_value.method.return_value = setup_fixtures.CardSetupTests.card(self)
            setup = setup_fixtures.CardSetupTests.save_card(self, flow, retain=True)
        values = self.values | dict(billing="prepaid", places=1)
        member = purchase(
            **values,
            request_key=uuid.uuid4(),
            reviewed=offer(**values)["fingerprint"],
            accepted=True,
            method_id=setup.method_id,
        )
        self.succeed(member)
        with clock(date(2027, 11, 1)):
            self.assertEqual(expire_unused_setups(), 0)
        setup.method.refresh_from_db()
        self.assertTrue(setup.method.reusable)

    def test_unwanted_card_is_queued_after_all_required_renewal_payments_are_settled(self):
        from core.membership_sales import invoice_for
        from core.models import DurableJob
        from core.payments.ledger import full_allocation, record_result, request_operation
        from core.payments.methods import expire_membership_sources, retire_future_use

        prior = self.prior()
        renewed = self.follow(prior, expected_method="card", billing="monthly", months=3)
        self.succeed(renewed)
        retire_future_use(actor=self.staff, method_id=self.method.pk)
        self.assertEqual(expire_membership_sources(), 0)
        for installment in renewed.installments.filter(number__gt=1):
            with clock(installment.due_on):
                invoice = invoice_for(installment, actor=self.staff, tender="card")
                operation = request_operation(
                    actor=self.staff,
                    sale_id=invoice.sale_id,
                    request_key=uuid.uuid4(),
                    tender="card",
                    allocation=full_allocation(invoice.sale),
                    method_id=self.method.pk,
                    purpose="member_installment",
                )
                record_result(
                    operation_id=operation.pk,
                    state="succeeded",
                    source="provider",
                    provider_reference=str(6000 + installment.number),
                )
        self.assertEqual(expire_membership_sources(), 1)
        self.assertTrue(
            DurableJob.objects.filter(kind="method_remove", reference=str(self.method.pk)).exists()
        )

    def test_end_cycle_cancellation_uses_benefit_start_not_earlier_short_month_charge_date(self):
        from core.membership_reservations import payment_current
        from core.payments.methods import outstanding

        prior = self.buy(expected_method="cash", verified_received=True)
        billing = prior.billing_state
        billing.stopped_on = date(2027, 12, 1)
        billing.save(update_fields=["stopped_on"])
        with clock(date(2027, 11, 30)):
            self.assertTrue(payment_current(prior))
            self.assertFalse(outstanding(self.method))
