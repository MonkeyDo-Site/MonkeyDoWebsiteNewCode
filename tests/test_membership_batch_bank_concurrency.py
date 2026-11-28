"""Real commits preserve one bank source and refuse loss of used financial history."""

import importlib
import uuid

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.membership_batch_records import MembershipRenewalBatchBank
from core.membership_batch_renewals import confirm, review
from core.models import MembershipPricing, PaymentOperation, PricingPolicy
from tests import test_membership_batch_bank as fixtures
from tests import test_membership_batch_concurrency as cash
from tests import test_membership_cancellations as races
from tests.test_membership_initial_credit import SETTINGS


@override_settings(**SETTINGS)
class CombinedRenewalBankRaceTests(TransactionTestCase):
    buy = fixtures.CombinedRenewalBankTests.buy
    prior = fixtures.CombinedRenewalBankTests.prior
    family = fixtures.CombinedRenewalBankTests.family
    bank_values = fixtures.CombinedRenewalBankTests.bank_values
    receive = fixtures.CombinedRenewalBankTests.receive
    race = races.MembershipCancellationRaceTests.race

    def setUp(self):
        fixtures.CombinedRenewalBankTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create()
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def test_same_source_request_submitted_twice_commits_one_transfer(self):
        self.family()
        values = self.bank_values()
        fingerprint = review(**values)["fingerprint"]

        def action():
            return confirm(
                **values,
                request_key=self.key,
                reviewed=fingerprint,
                accepted=True,
                verified_received=True,
            )

        results = self.race(action, action)
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipRenewalBatchBank.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_distinct_source_requests_cannot_both_claim_the_same_renewal_places(self):
        self.family()
        values = self.bank_values()
        fingerprint = review(**values)["fingerprint"]

        def action(key):
            return confirm(
                **values,
                request_key=key,
                reviewed=fingerprint,
                accepted=True,
                verified_received=True,
            )

        results = self.race(lambda: action(self.key), lambda: action(uuid.uuid4()))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(MembershipRenewalBatchBank.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_used_bank_source_refuses_reversal(self):
        self.family()
        source = self.receive().bank_receipt
        with self.assertRaisesMessage(RuntimeError, "cannot be reversed"), transaction.atomic():
            MigrationExecutor(connection).migrate([("core", "0091_combined_membership_renewals")])
        self.assertEqual(MembershipRenewalBatchBank.objects.get().pk, source.pk)
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_unused_schema_restores_published_function_exactly_and_reapplies(self):
        self.family()
        migration = importlib.import_module("core.migrations.0091_combined_membership_renewals")
        try:
            MigrationExecutor(connection).migrate([("core", "0091_combined_membership_renewals")])
            self.assertNotIn(
                "core_membershiprenewalbatchbank", connection.introspection.table_names()
            )
            with self.assertRaisesMessage(ValidationError, "not available"):
                review(**self.bank_values())
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_get_functiondef('monkeydo_renewal_batch_backed()'::regprocedure)"
                )
                restored = cursor.fetchone()[0]
                cursor.execute(
                    migration.SQL[
                        : migration.SQL.index(
                            "CREATE FUNCTION monkeydo_renewal_batch_message_scope"
                        )
                    ].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
                )
                cursor.execute(
                    "SELECT pg_get_functiondef('monkeydo_renewal_batch_backed()'::regprocedure)"
                )
                self.assertEqual(cursor.fetchone()[0], restored)
        finally:
            MigrationExecutor(connection).migrate([("core", "0095_unused_membership_owner_dates")])
        self.receive()
        self.assertEqual(MembershipRenewalBatchBank.objects.count(), 1)

    def test_cash_history_remains_readable_across_unused_bank_schema_reversal(self):
        self.family()
        self.review = cash.CombinedRenewalRaceTests.review.__get__(self)
        batch = cash.CombinedRenewalRaceTests.confirm(self)
        try:
            MigrationExecutor(connection).migrate([("core", "0091_combined_membership_renewals")])
            self.assertEqual(batch.parts.count(), 2)
            self.assertEqual(PaymentOperation.objects.count(), 4)
        finally:
            MigrationExecutor(connection).migrate([("core", "0095_unused_membership_owner_dates")])
        self.assertEqual(batch.messages.count(), 1)
