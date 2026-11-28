"""Real source/storage/request races and used/unused additive schema boundaries."""

import uuid
from unittest.mock import patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.membership_paid_visit_new_card import pending
from core.membership_paid_visit_pending import stop, stop_facts
from core.membership_paid_visit_records import (
    MembershipPaidVisitCardStorage,
    MembershipPaidVisitRecovery,
)
from core.membership_paid_visit_recovery import request as recover
from core.membership_paid_visit_recovery import review
from core.models import PaymentSetup
from core.payments.gateway import ProviderFailure
from tests import test_customer_credit_concurrency as races
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_membership_paid_visit_new_card import PaidVisitNewCardTests
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitNewCardRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    race = races.CustomerCreditRaceTests.race
    prepare = PaidVisitNewCardTests.prepare
    buy_card = PaidVisitNewCardTests.buy_card
    decline = PaidVisitNewCardTests.decline
    setup_decline = PaidVisitNewCardTests.setup_decline
    storage_flow = PaidVisitNewCardTests.storage_flow
    save_recovery_card = PaidVisitNewCardTests.save_recovery_card
    recovery_gateway = PaidVisitNewCardTests.recovery_gateway
    known_card = PaidVisitNewCardTests.known_card

    def test_duplicate_storage_keys_exchange_once_with_real_transactions(self):
        self.storage_flow()
        with patch("core.payments.setup.Gateway") as gateway:
            self.recovery_gateway(gateway)
            self.race(self.save_recovery_card, self.save_recovery_card)
        self.assertEqual(MembershipPaidVisitCardStorage.objects.count(), 1)
        self.assertEqual(gateway.return_value.create_customer.call_count, 1)
        self.assertEqual(gateway.return_value.save_card.call_count, 1)
        self.assertEqual(PaymentSetup.objects.filter(kind="membership").count(), 1)
        self.assertFalse(MembershipPaidVisitRecovery.objects.exists())

    def test_unknown_storage_and_a_separate_saved_card_request_cannot_both_start(self):
        self.storage_flow()
        data = review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)

        def request():
            return recover(
                actor=self.staff,
                intent_id=self.intent.pk,
                method_id=self.method.pk,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                confirmed=True,
            )

        with patch("core.payments.setup.Gateway") as gateway:
            self.recovery_gateway(gateway)
            gateway.return_value.save_card.side_effect = ProviderFailure("unknown")
            self.race(self.save_recovery_card, request)
        self.assertEqual(int(pending(self.intent)) + MembershipPaidVisitRecovery.objects.count(), 1)

    def test_unknown_storage_and_source_release_cannot_both_commit(self):
        self.storage_flow()
        facts = stop_facts(self.intent)

        def release():
            return stop(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=uuid.uuid4(),
                reviewed=facts["fingerprint"],
                reason="Owner stops before collection",
            )

        with patch("core.payments.setup.Gateway") as gateway:
            self.recovery_gateway(gateway)
            gateway.return_value.save_card.side_effect = ProviderFailure("unknown")
            self.race(self.save_recovery_card, release)
        self.assertFalse(pending(self.intent) and hasattr(self.intent, "release"))
        self.assertEqual(
            MembershipPaidVisitCardStorage.objects.count() + int(hasattr(self.intent, "release")), 1
        )

    def test_used_storage_refuses_reversal_to_published_0088(self):
        self.known_card()
        with self.assertRaisesRegex(RuntimeError, "has been used"):
            MigrationExecutor(connection).migrate([("core", "0088_paid_visit_cancelled_release")])
        self.assertIn("core_membershippaidvisitcardstorage", connection.introspection.table_names())

    def test_unused_schema_reverses_and_restores_before_runtime_storage(self):
        MigrationExecutor(connection).migrate([("core", "0088_paid_visit_cancelled_release")])
        self.assertNotIn(
            "core_membershippaidvisitcardstorage", connection.introspection.table_names()
        )
        MigrationExecutor(connection).migrate([("core", "0091_combined_membership_renewals")])
        self.known_card()
        self.assertEqual(MembershipPaidVisitCardStorage.objects.count(), 1)
