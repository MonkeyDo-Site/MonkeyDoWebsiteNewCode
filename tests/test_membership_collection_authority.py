"""An accepted scheduled scope is immutable and does not become public permission."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from threading import Barrier
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from core.membership_collection_authority import authorize, prepare_claim
from core.membership_collection_plan import installment_plan
from core.membership_records import MembershipCollectionClaim
from core.membership_sales import authorize as authorize_sale
from core.membership_sales import invoice_for
from core.models import AuditEvent, MembershipCardMandate, MembershipInvoice, PaymentOperation
from tests import test_membership_collection_plan as planner
from tests import test_membership_sales as fixtures
from tests.test_membership_renewals import clock
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**(planner.SETTINGS | {"MEMBERSHIP_COLLECTIONS_ENABLED": True}))
class MembershipCollectionAuthorityTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed
    funded = planner.MembershipCollectionPlanTests.funded
    report_return = planner.MembershipCollectionPlanTests.report_return

    def test_one_runtime_claim_preserves_fixed_scope_without_creating_payment_or_invoice(self):
        member, item = self.funded()
        before = (PaymentOperation.objects.count(), MembershipInvoice.objects.count())
        with clock(item.due_on), self.runtime_role():
            claim = prepare_claim(item.pk)
            self.assertEqual(prepare_claim(item.pk).pk, claim.pk)
            self.assertEqual(authorize(claim).pk, claim.pk)
        self.assertEqual(claim.installment_id, item.pk)
        self.assertEqual(claim.mandate_id, member.billing_state.mandate_id)
        self.assertEqual(claim.details["card_total"], "37.06")
        self.assertEqual(claim.payment_key, uuid.uuid5(claim.pk, "payment"))
        self.assertEqual(claim.credit_key, uuid.uuid5(claim.pk, "credit"))
        self.assertEqual(MembershipCollectionClaim.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(action="membership.collection_claimed").count(), 1
        )
        self.assertEqual(
            (PaymentOperation.objects.count(), MembershipInvoice.objects.count()), before
        )

    def test_feature_off_and_non_due_or_first_payments_cannot_claim(self):
        member, item = self.funded()
        with (
            clock(item.due_on),
            override_settings(MEMBERSHIP_COLLECTIONS_ENABLED=False),
            self.assertRaises(PermissionDenied),
        ):
            prepare_claim(item.pk)
        for on in (item.due_on - timedelta(days=1), item.due_on + timedelta(days=1)):
            with clock(on), self.assertRaises(ValidationError):
                prepare_claim(item.pk)
        with clock(item.due_on), self.assertRaises(ValidationError):
            prepare_claim(member.installments.first().pk)
        self.assertFalse(MembershipCollectionClaim.objects.exists())

    def test_system_claim_is_not_a_public_or_staff_purchase_authority(self):
        _, item = self.funded()
        with clock(item.due_on):
            claim = prepare_claim(item.pk)
            with self.assertRaises(PermissionDenied):
                authorize_sale(None, authority=claim)
            with self.assertRaises(PermissionDenied):
                invoice_for(item, actor=None, tender="card", authority=claim)
            for value in (str(claim.pk), {"id": str(claim.pk)}, None):
                with self.subTest(value=value), self.assertRaises(PermissionDenied):
                    authorize(value)

    def test_changed_mandate_and_funding_need_fresh_review_without_rewriting_claim(self):
        member, item = self.funded()
        with clock(item.due_on):
            claim = prepare_claim(item.pk)
            replacement = MembershipCardMandate.objects.create(
                purchase=member, method=self.method, text="Accepted replacement", actor=self.staff
            )
            billing = member.billing_state
            billing.mandate = replacement
            billing.revision += 1
            billing.save(update_fields=["mandate", "revision"])
            with self.assertRaises(ValidationError):
                authorize(claim)
            claim.refresh_from_db()
            self.assertNotEqual(claim.mandate_id, replacement.pk)
        self.assertEqual(MembershipCollectionClaim.objects.count(), 1)

    def test_a_reported_return_blocks_an_already_prepared_scope(self):
        member, item = self.funded()
        with clock(item.due_on):
            claim = prepare_claim(item.pk)
            self.report_return(member.installments.first().invoice.sale.operations.get())
            with self.assertRaises(ValidationError):
                authorize(claim)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_staff_deactivation_does_not_rewrite_the_existing_customer_agreement(self):
        _, item = self.funded()
        with clock(item.due_on):
            claim = prepare_claim(item.pk)
            self.staff.is_active = False
            self.staff.save(update_fields=["is_active"])
            self.assertEqual(authorize(claim).pk, claim.pk)
        self.assertIsNone(AuditEvent.objects.get(action="membership.collection_claimed").actor_id)

    def test_expiry_uses_new_york_midnight_and_never_rolls_into_another_date(self):
        _, item = self.funded()
        with clock(item.due_on):
            claim = prepare_claim(item.pk)
        with clock(item.due_on + timedelta(days=1)), self.assertRaises(PermissionDenied):
            authorize(claim)
        self.assertEqual(MembershipCollectionClaim.objects.count(), 1)

    def test_spring_day_scope_has_twenty_three_real_hours(self):
        self.key = uuid.uuid4()
        member = self.buy(starts_on=date(2028, 2, 12))
        self.succeed(member)
        item = member.installments.get(number=2)
        self.assertEqual(item.due_on, date(2028, 3, 12))
        midnight = datetime.combine(item.due_on, datetime.min.time(), ZoneInfo("America/New_York"))
        with patch("django.utils.timezone.now", return_value=midnight):
            claim = prepare_claim(item.pk)
        self.assertEqual(
            (
                claim.expires_at.astimezone(dt_timezone.utc)
                - claim.created_at.astimezone(dt_timezone.utc)
            ).total_seconds(),
            23 * 3600,
        )

    def test_fall_day_scope_has_twenty_five_real_hours(self):
        self.key = uuid.uuid4()
        member = self.buy(starts_on=date(2028, 10, 5))
        self.succeed(member)
        item = member.installments.get(number=2)
        self.assertEqual(item.due_on, date(2028, 11, 5))
        midnight = datetime.combine(item.due_on, datetime.min.time(), ZoneInfo("America/New_York"))
        with patch("django.utils.timezone.now", return_value=midnight):
            claim = prepare_claim(item.pk)
        self.assertEqual(
            (
                claim.expires_at.astimezone(dt_timezone.utc)
                - claim.created_at.astimezone(dt_timezone.utc)
            ).total_seconds(),
            25 * 3600,
        )

    def test_database_rejects_wrong_quote_scope_and_updates(self):
        _, item = self.funded()
        with clock(item.due_on):
            data = installment_plan(item.pk)
            bad = data | {"card_total": "1.00"}
            with (
                self.assertRaisesMessage(DatabaseError, "scope does not match"),
                transaction.atomic(),
            ):
                MembershipCollectionClaim.objects.create(
                    id=uuid.uuid4(),
                    installment=item,
                    mandate_id=data["mandate"],
                    planned_on=item.due_on,
                    expires_at=datetime.combine(
                        item.due_on + timedelta(days=1),
                        datetime.min.time(),
                        ZoneInfo("America/New_York"),
                    ),
                    payment_key=uuid.uuid4(),
                    credit_key=uuid.uuid4(),
                    fingerprint=data["fingerprint"],
                    details=bad,
                )
            claim = prepare_claim(item.pk)
            with (
                self.assertRaises(DatabaseError),
                transaction.atomic(),
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "UPDATE core_membershipcollectionclaim SET fingerprint='changed' WHERE id=%s",
                    [claim.pk],
                )
        self.assertEqual(MembershipCollectionClaim.objects.count(), 1)


@override_settings(**(planner.SETTINGS | {"MEMBERSHIP_COLLECTIONS_ENABLED": True}))
class MembershipCollectionCreditAuthorityTests(RuntimeRoleMixin, TestCase):
    setUp = planner.MembershipCollectionCreditPlanTests.setUp
    flow = planner.MembershipCollectionCreditPlanTests.flow
    card = planner.MembershipCollectionCreditPlanTests.card
    save_card = planner.MembershipCollectionCreditPlanTests.save_card
    booking = planner.MembershipCollectionCreditPlanTests.booking
    arrival_inputs = planner.MembershipCollectionCreditPlanTests.arrival_inputs
    create = planner.MembershipCollectionCreditPlanTests.create
    gateway = planner.MembershipCollectionCreditPlanTests.gateway
    ready = planner.MembershipCollectionCreditPlanTests.ready
    member = planner.MembershipCollectionCreditPlanTests.member
    act = planner.MembershipCollectionCreditPlanTests.act
    paid_visit = planner.MembershipCollectionCreditPlanTests.paid_visit
    conversion = planner.MembershipCollectionCreditPlanTests.conversion

    def test_full_credit_scope_requires_no_new_card_charge_or_credit_spending(self):
        from core.customer_credit import balance
        from core.customer_credit_records import CustomerCreditApplication

        _, _, member, _ = self.conversion(adults=2)
        method = member.billing_state.mandate.method
        method.state = "removed"
        method.save(update_fields=["state"])
        item = member.installments.get(number=2)
        before = balance(self.customer.pk)
        operations = PaymentOperation.objects.count()
        with clock(item.due_on), self.runtime_role():
            claim = prepare_claim(item.pk)
            self.assertEqual(authorize(claim).details["card_total"], "0.00")
        self.assertEqual(claim.details["credit_to_apply"], "17.99")
        self.assertEqual(balance(self.customer.pk), before)
        self.assertFalse(CustomerCreditApplication.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), operations)


@override_settings(**(planner.SETTINGS | {"MEMBERSHIP_COLLECTIONS_ENABLED": True}))
class MembershipCollectionClaimRaceTests(TransactionTestCase):
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed
    funded = planner.MembershipCollectionPlanTests.funded

    def setUp(self):
        from core.models import MembershipPricing, PricingPolicy

        fixtures.MembershipPurchaseTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create(subscription="17.99", unlimited="39.99")
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def test_overlapping_workers_prepare_one_claim_and_no_financial_work(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL customer/request lock integration")
        _, item = self.funded()
        ready = Barrier(2)
        before = (MembershipInvoice.objects.count(), PaymentOperation.objects.count())

        def run():
            close_old_connections()
            try:
                ready.wait(timeout=10)
                return prepare_claim(item.pk).pk
            finally:
                connections.close_all()

        with clock(item.due_on), ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=20) for future in [pool.submit(run), pool.submit(run)]]
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipCollectionClaim.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(action="membership.collection_claimed").count(), 1
        )
        self.assertEqual(
            (MembershipInvoice.objects.count(), PaymentOperation.objects.count()), before
        )
