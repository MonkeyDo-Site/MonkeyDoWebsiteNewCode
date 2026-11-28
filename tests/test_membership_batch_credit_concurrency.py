"""Actual commits serialize credit sources, renewal places and immutable history."""

import uuid

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.customer_credit import balance
from core.membership_batch_credit import available
from core.membership_batch_credit_records import MembershipCreditRenewalBatch
from core.models import MembershipPricing, PricingPolicy
from tests import test_membership_cancellations as races
from tests.test_membership_batch_credit import CreditRenewalFixtures
from tests.test_membership_initial_credit import SETTINGS
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CreditRenewalRaceTests(CreditRenewalFixtures, RuntimeRoleMixin, TransactionTestCase):
    race = races.MembershipCancellationRaceTests.race

    def setUp(self):
        CreditRenewalFixtures.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create()
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def test_same_request_twice_commits_one_credit_checkout(self):
        self.family()
        data = self.review_batch()
        results = self.race(
            lambda: self.confirm_batch(reviewed=data["fingerprint"]),
            lambda: self.confirm_batch(reviewed=data["fingerprint"]),
        )
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipCreditRenewalBatch.objects.count(), 1)
        self.assertEqual(str(balance(self.customer.pk)), "37.96")
        self.assertEqual(MembershipCreditRenewalBatch.objects.get().messages.count(), 1)

    def test_distinct_checkouts_cannot_apply_the_same_reviewed_credit_twice(self):
        self.family()
        data = self.review_batch()
        results = self.race(
            lambda: self.confirm_batch(reviewed=data["fingerprint"]),
            lambda: self.confirm_batch(reviewed=data["fingerprint"], request_key=uuid.uuid4()),
        )
        self.assertEqual(sum(v is not None for v in results), 1)
        self.assertEqual(str(balance(self.customer.pk)), "37.96")
        self.assertEqual(MembershipCreditRenewalBatch.objects.count(), 1)

    def test_credit_removal_and_group_checkout_serialize_without_overdraft(self):
        from core.customer_credit_corrections import correct, review

        self.family()
        data = self.review_batch()
        values = dict(actor=self.owner, customer_id=self.customer.pk, kind="remove", value="50.00")
        removal = review(**values)
        results = self.race(
            lambda: self.confirm_batch(reviewed=data["fingerprint"]),
            lambda: correct(
                **values,
                reviewed=removal["fingerprint"],
                request_key=uuid.uuid4(),
                reason="Fictional competing correction",
                confirmed=True,
            ),
        )
        self.assertEqual(sum(v is not None for v in results), 1)
        self.assertIn(str(balance(self.customer.pk)), {"37.96", "45.94"})

    def test_used_credit_checkout_refuses_reversal(self):
        self.family()
        batch = self.confirm_batch()
        with self.assertRaisesMessage(RuntimeError, "cannot be reversed"), transaction.atomic():
            MigrationExecutor(connection).migrate([("core", "0095_unused_membership_owner_dates")])
        self.assertEqual(MembershipCreditRenewalBatch.objects.get().pk, batch.pk)
        self.assertTrue(available())

    def test_unused_schema_reverses_and_reapplies_with_runtime_grants(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0095_unused_membership_owner_dates")])
            self.assertFalse(available())
        finally:
            MigrationExecutor(connection).migrate(
                [("core", "0096_credit_funded_membership_renewals")]
            )
        self.family()
        with self.runtime_role():
            self.confirm_batch()
        self.assertEqual(MembershipCreditRenewalBatch.objects.count(), 1)

    def test_absent_upgrade_refuses_new_checkout_without_writes(self):
        self.family()
        before = self.facts()
        try:
            MigrationExecutor(connection).migrate([("core", "0095_unused_membership_owner_dates")])
            with self.assertRaisesMessage(ValidationError, "upgrade first"):
                self.review_batch()
        finally:
            MigrationExecutor(connection).migrate(
                [("core", "0096_credit_funded_membership_renewals")]
            )
        self.assertEqual(self.facts(), before)
