import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core import customer_credit as wallet
from core.customer_credit_corrections import correct, review
from core.customer_credit_records import CustomerCreditCorrection
from tests import test_customer_credit_concurrency as race_fixtures
from tests import test_customer_credit_corrections as fixtures
from tests.test_owner_accounts import STORAGES


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake",
)
class CreditCorrectionRaceTests(fixtures.CreditFixtures, TransactionTestCase):
    setUp = race_fixtures.CustomerCreditRaceTests.setUp
    race = race_fixtures.CustomerCreditRaceTests.race

    def values(self, *, kind="remove", value="5.00", original=None):
        inputs = dict(
            actor=self.owner,
            customer_id=self.customer.pk,
            kind=kind,
            value=value,
            original_id=original,
        )
        data = review(**inputs)
        return inputs | dict(
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Reviewed race.",
            confirmed=True,
        )

    def test_remove_and_apply_cannot_use_the_same_unused_credit(self):
        _, _, member, _ = self.conversion()
        values = self.values(value="15.99")
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            due = self.due(member)
            data = wallet.review(**due)
            results = self.race(
                lambda: correct(**values),
                lambda: wallet.apply(
                    **due, reviewed=data["fingerprint"], request_key=uuid.uuid4(), confirmed=True
                ),
            )
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(wallet.balance(self.customer.pk), 0)

    def test_duplicate_owner_confirmation_appends_one_correction(self):
        self.conversion()
        values = self.values()
        results = self.race(lambda: correct(**values), lambda: correct(**values))
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(CustomerCreditCorrection.objects.count(), 1)
        self.assertEqual(str(wallet.balance(self.customer.pk)), "10.99")

    def test_competing_restorations_cannot_exceed_original_removal(self):
        self.conversion()
        original = self.correction("10.00")
        first = self.values(kind="restore", value="8.00", original=original.pk)
        second = first | dict(request_key=uuid.uuid4())
        results = self.race(lambda: correct(**first), lambda: correct(**second))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(str(wallet.balance(self.customer.pk)), "13.99")
        self.assertEqual(CustomerCreditCorrection.objects.filter(kind="restore").count(), 1)
