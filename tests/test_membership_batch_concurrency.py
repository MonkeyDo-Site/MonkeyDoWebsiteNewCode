"""Actual transactions serialize grouped renewal counts and preserve used history."""

import uuid

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.communications.services import claim
from core.membership_batch_records import MembershipRenewalBatch
from core.membership_records import MembershipOrigin
from core.models import MembershipPricing, PaymentOperation, PricingPolicy
from tests import test_membership_batch_renewals as fixtures
from tests import test_membership_cancellations as races
from tests.test_membership_initial_credit import SETTINGS
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CombinedRenewalRaceTests(RuntimeRoleMixin, TransactionTestCase):
    buy = fixtures.CombinedRenewalTests.buy
    prior = fixtures.CombinedRenewalTests.prior
    follow = fixtures.CombinedRenewalTests.follow
    follow_values = fixtures.CombinedRenewalTests.follow_values
    family = fixtures.CombinedRenewalTests.family
    review = fixtures.CombinedRenewalTests.review
    confirm = fixtures.CombinedRenewalTests.confirm
    race = races.MembershipCancellationRaceTests.race

    def setUp(self):
        fixtures.CombinedRenewalTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create()
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def test_same_checkout_submitted_twice_commits_one_set_of_receipts(self):
        self.family()
        reviewed = self.review()["fingerprint"]
        results = self.race(
            lambda: self.confirm(reviewed=reviewed), lambda: self.confirm(reviewed=reviewed)
        )
        self.assertEqual(results[0], results[1])
        self.assertIsNotNone(results[0])
        self.assertEqual(MembershipRenewalBatch.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 4)
        self.assertEqual(MembershipRenewalBatch.objects.get().messages.count(), 1)

    def test_distinct_checkouts_cannot_both_receive_the_same_full_renewal(self):
        self.family()
        reviewed = self.review()["fingerprint"]
        results = self.race(
            lambda: self.confirm(reviewed=reviewed),
            lambda: self.confirm(reviewed=reviewed, request_key=uuid.uuid4()),
        )
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(MembershipRenewalBatch.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_individual_renewal_and_combined_renewal_cannot_overcommit_original_places(self):
        self.family()
        reviewed = self.review()["fingerprint"]
        results = self.race(
            lambda: self.confirm(reviewed=reviewed), lambda: self.follow(self.first, places=2)
        )
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertLessEqual(
            sum(MembershipOrigin.objects.filter(prior=self.first).values_list("places", flat=True)),
            2,
        )
        self.assertIn(PaymentOperation.objects.count(), {3, 4})

    def test_used_group_refuses_schema_reversal_without_removing_receipts(self):
        self.family()
        batch = self.confirm()
        with self.assertRaisesMessage(RuntimeError, "cannot be reversed"), transaction.atomic():
            MigrationExecutor(connection).migrate([("core", "0090_paid_visit_manual_payment")])
        self.assertEqual(MembershipRenewalBatch.objects.get().pk, batch.pk)
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_unused_group_schema_can_reverse_and_reapply_with_runtime_grants(self):
        MigrationExecutor(connection).migrate([("core", "0090_paid_visit_manual_payment")])
        self.assertNotIn("core_membershiprenewalbatch", connection.introspection.table_names())
        MigrationExecutor(connection).migrate([("core", "0091_combined_membership_renewals")])
        self.family()
        with self.runtime_role():
            self.confirm()
        self.assertEqual(MembershipRenewalBatch.objects.count(), 1)

    def test_changed_contact_retains_historical_actor_after_that_account_is_inactive(self):
        self.family()
        batch = self.confirm()
        old = batch.messages.get().message
        type(self.staff).objects.filter(pk=self.staff.pk).update(is_active=False)
        type(self.customer).objects.filter(pk=self.customer.pk).update(
            email="current@example.invalid"
        )
        self.assertIsNone(claim(old.pk))
        new = batch.messages.exclude(message=old).get().message
        self.assertEqual(new.recipient, "current@example.invalid")
        self.assertEqual(new.actor_id, self.staff.pk)
        self.assertEqual(PaymentOperation.objects.count(), 4)
