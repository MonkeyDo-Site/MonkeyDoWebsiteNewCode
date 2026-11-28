"""The same backed funds cannot be spent twice or dispatched after a source hold."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.customer_credit import balance
from core.customer_credit_corrections import correct
from core.customer_credit_corrections import review as correction_review
from core.customer_credit_records import CustomerCreditApplication
from core.membership_reservations import lock_customer
from core.payments import checkout
from core.payments.operations import begin_dispatch
from tests import test_customer_credit_concurrency as races
from tests import test_visit_credit as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures


@override_settings(**SETTINGS)
class VisitCreditRaceTests(InitialCreditFixtures, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    prepare = fixtures.VisitCreditTests.prepare
    complete = fixtures.VisitCreditTests.complete
    race = races.CustomerCreditRaceTests.race

    def threaded(self, fn):
        close_old_connections()
        try:
            return fn()
        finally:
            connections.close_all()

    def test_overlapping_same_confirmation_creates_one_application_and_card_request(self):
        proposed = self.prepare()
        applied, waiting = Event(), Event()
        from core import visit_credit

        original_apply, original_lock = visit_credit.apply, checkout.lock_request

        def pause(**kwargs):
            result = original_apply(**kwargs)
            applied.set()
            if not waiting.wait(timeout=10):
                raise AssertionError("The duplicate never reached its confirmation lock.")
            return result

        def request_lock(key):
            if applied.is_set():
                waiting.set()
            return original_lock(key)

        def confirm():
            return self.complete(reviewed=proposed[-1]).pk

        with (
            patch("core.visit_credit.apply", side_effect=pause),
            patch("core.payments.checkout.lock_request", side_effect=request_lock),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first = pool.submit(self.threaded, confirm)
            self.assertTrue(applied.wait(timeout=10))
            second = pool.submit(self.threaded, confirm)
            self.assertEqual(first.result(timeout=20), second.result(timeout=20))
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)
        self.assertEqual(self.play.checkouts.get().sale.operations.count(), 1)
        self.assertEqual(balance(self.customer.pk), Decimal("6.02"))

    def test_two_arrivals_and_owner_removal_share_the_same_source_budget(self):
        proposed = self.prepare()
        self.data = self.data | {
            "starts_at": self.data["starts_at"] + timedelta(hours=2),
            "ends_at": self.data["ends_at"] + timedelta(hours=2),
        }
        second = self.booking(children=2)
        second_options = dict(
            actor=self.staff,
            booking_id=second.pk,
            kind="arrival",
            data=self.arrival_inputs(second, visit_credit="10.00"),
        )
        next_review = checkout.preview(**second_options)
        results = self.race(
            lambda: self.complete(reviewed=proposed[-1]),
            lambda: checkout.confirm(
                **second_options,
                request_key=uuid.uuid4(),
                reviewed_hash=next_review[-1],
                confirmed=True,
            ),
        )
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)
        self.assertEqual(balance(self.customer.pk), Decimal("6.02"))

    def test_owner_removal_and_arrival_cannot_spend_the_same_unused_money(self):
        proposed = self.prepare()
        values = dict(actor=self.owner, customer_id=self.customer.pk, kind="remove", value="16.02")
        reviewed = correction_review(**values)
        results = self.race(
            lambda: self.complete(reviewed=proposed[-1]),
            lambda: correct(
                **values,
                reviewed=reviewed["fingerprint"],
                request_key=uuid.uuid4(),
                reason="Fictional race correction",
                confirmed=True,
            ),
        )
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertIn(balance(self.customer.pk), [Decimal("0.00"), Decimal("6.02")])

    def test_dispatch_waits_for_source_review_and_never_charges_from_an_old_snapshot(self):
        self.prepare()
        record = self.complete()
        operation = record.sale.operations.get()
        held, waiting = Event(), Event()

        def correction():
            with transaction.atomic():
                lock_customer(self.customer.pk)
                held.set()
                if not waiting.wait(timeout=10):
                    raise AssertionError("Dispatch never reached the source lock.")
                self.external_return(self.original_sale.operations.get(kind="receipt"))

        def dispatch_lock(customer_id):
            waiting.set()
            return lock_customer(customer_id)

        with (
            patch("core.membership_reservations.lock_customer", side_effect=dispatch_lock),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first = pool.submit(self.threaded, correction)
            self.assertTrue(held.wait(timeout=10))
            second = pool.submit(self.threaded, lambda: begin_dispatch(operation.pk))
            first.result(timeout=20)
            self.assertIsNone(second.result(timeout=20))
        operation.refresh_from_db()
        self.assertEqual(operation.state, "cancelled")

    def test_reverse_refuses_accepted_visit_credit_without_removing_its_scope(self):
        self.prepare()
        record = self.complete()
        with (
            self.assertRaisesMessage(RuntimeError, "Accepted visit credit exists"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate(
                [("core", "0074_scheduled_membership_credit_authority")]
            )
        self.assertEqual(record.visit_credit_application.amount, Decimal("10.00"))
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)

    def test_unused_visit_scope_reverses_and_restores_without_rewriting_existing_sources(self):
        self.prepare()
        try:
            MigrationExecutor(connection).migrate(
                [("core", "0074_scheduled_membership_credit_authority")]
            )
            self.assertEqual(balance(self.customer.pk), Decimal("16.02"))
        finally:
            MigrationExecutor(connection).migrate([("core", "0086_paid_visit_card_reservations")])
        record = self.complete()
        self.assertEqual(record.visit_credit_application.amount, Decimal("10.00"))
