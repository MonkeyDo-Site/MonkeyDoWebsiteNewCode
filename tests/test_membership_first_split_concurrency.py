import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.customer_credit import balance
from core.customer_credit_records import CustomerCreditApplication
from core.membership_records import MembershipPurchase
from core.membership_sales import offer, purchase, today
from core.models import PaymentOperation
from tests import test_customer_credit_concurrency as races
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures


@override_settings(**SETTINGS)
class MembershipFirstSplitRaceTests(InitialCreditFixtures, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    race = races.CustomerCreditRaceTests.race

    def manual_values(self):
        return dict(
            actor=self.staff,
            customer=self.customer,
            kind="subscription",
            places=2,
            months=3,
            billing="prepaid",
            starts_on=today(),
            expected_method="split",
            split={"cash": "50.00", "check": "57.94"},
        )

    def test_overlapping_confirmation_records_one_membership_and_receipt_set(self):
        from core import membership_first_split, membership_sales

        values = self.manual_values()
        fingerprint = offer(**values)["fingerprint"]
        key = uuid.uuid4()
        accepted, waiting = Event(), Event()
        original_record, original_lock = (
            membership_first_split.record,
            membership_sales.lock_request,
        )

        def record(**kwargs):
            result = original_record(**kwargs)
            accepted.set()
            if not waiting.wait(timeout=10):
                raise AssertionError("The second confirmation did not reach its request lock.")
            return result

        def lock(value):
            if value == key and accepted.is_set():
                waiting.set()
            return original_lock(value)

        def confirm():
            close_old_connections()
            try:
                return purchase(
                    **values,
                    request_key=key,
                    reviewed=fingerprint,
                    accepted=True,
                    verified_received=True,
                ).pk
            finally:
                connections.close_all()

        with (
            patch("core.membership_first_split.record", side_effect=record),
            patch("core.membership_sales.lock_request", side_effect=lock),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first = pool.submit(confirm)
            self.assertTrue(accepted.wait(timeout=10))
            second = pool.submit(confirm)
            self.assertEqual(first.result(timeout=20), second.result(timeout=20))
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_two_first_purchases_cannot_spend_the_same_credit_source(self):
        _, _, prior, _ = self.conversion(card=True)
        values = self.values(credit="10.00", expected_method="split", split={"cash": "3.00"})
        reviewed = offer(**values)["fingerprint"]

        def confirm():
            return purchase(
                **values,
                request_key=uuid.uuid4(),
                reviewed=reviewed,
                accepted=True,
                verified_received=True,
                method_id=prior.billing_state.mandate.method_id,
            )

        results = self.race(confirm, confirm)
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(MembershipPurchase.objects.count(), 2)
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)
        self.assertEqual(str(balance(self.customer.pk)), "6.02")

    def test_reverse_refuses_accepted_split_payments_before_changing_model_state(self):
        values = self.manual_values()
        member = purchase(
            **values,
            request_key=uuid.uuid4(),
            reviewed=offer(**values)["fingerprint"],
            accepted=True,
            verified_received=True,
        )
        with (
            self.assertRaisesMessage(RuntimeError, "Accepted split membership payments"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0075_visit_customer_credit")])
        self.assertEqual(
            MembershipPurchase.objects.get(pk=member.pk).membership.expected_method, "split"
        )
        self.assertIn(
            ("core", "0076_membership_first_split"),
            MigrationExecutor(connection).loader.applied_migrations,
        )

    def test_unused_choice_reverses_and_restores_then_accepts_a_current_split(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0075_visit_customer_credit")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0082_stop_pending_arrival")])
        values = self.manual_values()
        member = purchase(
            **values,
            request_key=uuid.uuid4(),
            reviewed=offer(**values)["fingerprint"],
            accepted=True,
            verified_received=True,
        )
        self.assertEqual(member.installments.first().invoice.sale.operations.count(), 2)
