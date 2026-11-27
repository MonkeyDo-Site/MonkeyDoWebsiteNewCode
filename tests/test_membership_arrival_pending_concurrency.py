"""Pending membership/arrival acceptance and completion serialize independently."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings

from core import membership_arrival, membership_arrival_pending
from core.membership_records import (
    MembershipArrivalCheckout,
    MembershipArrivalIntent,
    MembershipPurchase,
)
from core.models import PaymentOperation
from core.payments import checkout
from core.payments.ledger import record_result
from tests import test_customer_credit_concurrency as fixtures
from tests import test_membership_arrival as arrival_fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures


@override_settings(**SETTINGS)
class PendingArrivalRaceTests(InitialCreditFixtures, TransactionTestCase):
    setUp = fixtures.CustomerCreditRaceTests.setUp
    prepare = arrival_fixtures.CombinedMembershipArrivalTests.prepare

    def inputs(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL pending-arrival transaction races")
        self.play = self.prepare(method="card")
        self.accepted = membership_arrival.review(**self.options)

    def call(self, key):
        return membership_arrival.confirm(
            **self.options,
            request_key=key,
            reviewed_hash=self.accepted["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=False,
        )

    def run_in_connection(self, fn):
        close_old_connections()
        try:
            try:
                return fn()
            except ValidationError:
                return None
        finally:
            connections.close_all()

    def test_different_keys_cannot_create_two_pending_purchases_for_one_booking(self):
        self.inputs()
        created, competing = Event(), Event()
        second_key = uuid.uuid4()
        original_create, original_lock = (
            membership_arrival_pending.create,
            membership_arrival.lock_request,
        )

        def paused_create(**kwargs):
            result = original_create(**kwargs)
            created.set()
            if not competing.wait(timeout=10):
                raise AssertionError("Competing acceptance never reached its request lock.")
            return result

        def checked_lock(key):
            if key == second_key:
                competing.set()
            return original_lock(key)

        with (
            patch("core.membership_arrival_pending.create", side_effect=paused_create),
            patch("core.membership_arrival.lock_request", side_effect=checked_lock),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first = pool.submit(self.run_in_connection, lambda: self.call(self.key))
            self.assertTrue(created.wait(timeout=10))
            second = pool.submit(self.run_in_connection, lambda: self.call(second_key))
            self.assertIsNotNone(first.result(timeout=20))
            self.assertIsNone(second.result(timeout=20))
        self.assertEqual(MembershipArrivalIntent.objects.count(), 1)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_overlapping_worker_completions_request_the_visit_payment_once(self):
        self.inputs()
        intent = self.call(self.key)
        record_result(
            operation_id=intent.operation_id,
            state="succeeded",
            source="provider",
            provider_reference="993",
        )
        visit_created, competing = Event(), Event()
        original_confirm, original_lock = checkout.confirm, membership_arrival_pending.lock_request

        def paused_confirm(**kwargs):
            result = original_confirm(**kwargs)
            visit_created.set()
            if not competing.wait(timeout=10):
                raise AssertionError("Second completion never reached its request lock.")
            return result

        def checked_lock(key):
            if visit_created.is_set():
                competing.set()
            return original_lock(key)

        with (
            patch("core.payments.checkout.confirm", side_effect=paused_confirm),
            patch("core.membership_arrival_pending.lock_request", side_effect=checked_lock),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first = pool.submit(
                self.run_in_connection, lambda: membership_arrival_pending.complete(intent.pk)
            )
            self.assertTrue(visit_created.wait(timeout=10))
            second = pool.submit(
                self.run_in_connection, lambda: membership_arrival_pending.complete(intent.pk)
            )
            self.assertEqual(first.result(timeout=20).status, "completed")
            self.assertEqual(second.result(timeout=20).status, "completed")
        self.assertEqual(MembershipArrivalCheckout.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)
