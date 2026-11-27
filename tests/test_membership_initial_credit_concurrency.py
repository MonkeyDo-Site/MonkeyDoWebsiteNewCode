import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings

from core.customer_credit import balance
from core.customer_credit_corrections import correct, review
from core.membership_records import MembershipPurchase
from core.membership_reservations import lock_customer
from core.membership_sales import offer
from tests import test_customer_credit_concurrency as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures


@override_settings(**SETTINGS)
class InitialCreditRaceTests(InitialCreditFixtures, TransactionTestCase):
    setUp = fixtures.CustomerCreditRaceTests.setUp

    def test_credit_correction_finishes_while_a_purchase_waits_without_fk_deadlock(self):
        _, _, prior, _ = self.conversion(card=True)
        values = self.values()
        quoted = offer(**values)
        removal = dict(actor=self.owner, customer_id=self.customer.pk, kind="remove", value="1.00")
        removal.update(
            reviewed=review(**removal)["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Reviewed concurrent removal.",
            confirmed=True,
        )
        correction_locked, purchase_waiting = Event(), Event()
        original_review = review

        def correction_review(**kwargs):
            correction_locked.set()
            if not purchase_waiting.wait(timeout=10):
                raise AssertionError("Purchase never reached its customer advisory lock.")
            return original_review(**kwargs)

        def purchase_lock(customer_id):
            purchase_waiting.set()
            return lock_customer(customer_id)

        def run(fn):
            close_old_connections()
            try:
                try:
                    return fn()
                except ValidationError:
                    return None
            finally:
                connections.close_all()

        before = MembershipPurchase.objects.count()
        with (
            patch("core.customer_credit_corrections.review", side_effect=correction_review),
            patch("core.membership_reservations.lock_customer", side_effect=purchase_lock),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            removed = pool.submit(run, lambda: correct(**removal))
            self.assertTrue(correction_locked.wait(timeout=10))
            purchased = pool.submit(
                run,
                lambda: self.buy(
                    values,
                    reviewed=quoted["fingerprint"],
                    method=prior.billing_state.mandate.method,
                ),
            )
            self.assertIsNotNone(removed.result(timeout=20))
            self.assertIsNone(purchased.result(timeout=20))
        self.assertEqual(balance(self.customer.pk), Decimal("15.02"))
        self.assertEqual(MembershipPurchase.objects.count(), before)
