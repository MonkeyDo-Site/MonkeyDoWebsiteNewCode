"""Independent PostgreSQL sessions cannot duplicate a final prompt or reminder."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings

from core.membership_prompt_emails import prepare
from core.membership_records import MembershipPromptEmail, MembershipRenewalPrompt
from core.models import MembershipPricing, PricingPolicy
from tests.test_membership_booking_prompts import SETTINGS, PromptFixtures
from tests.test_membership_renewals import clock


@override_settings(**SETTINGS)
class MembershipPromptRaceTests(PromptFixtures, TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL advisory locks")
        PromptFixtures.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create(
                subscription="17.99", unlimited="39.99", actor=self.owner
            )
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def race(self, first, second):
        ready = Barrier(2)

        def attempt(fn):
            close_old_connections()
            try:
                ready.wait(timeout=10)
                try:
                    return fn()
                except ValidationError:
                    return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(attempt, (first, second)))

    def test_only_one_later_booking_can_record_the_one_further_prompt(self):
        member = self.prior()
        with clock(member.membership.ends_on - timedelta(days=5)):
            self.choice(self.flow(), "not_now")
        with clock(member.membership.ends_on + timedelta(days=30)):
            first, second = self.flow(), self.flow()
            first_row, second_row = self.row(first), self.row(second)
            answers = self.race(
                lambda: self.choice(first, "seen", row=first_row),
                lambda: self.choice(second, "seen", row=second_row),
            )
        self.assertEqual(sum(answer is not None for answer in answers), 1)
        self.assertEqual(
            MembershipRenewalPrompt.objects.filter(window="followup", action="seen").count(), 1
        )

    def test_competing_requested_reminder_preparations_share_one_link_and_message(self):
        member = self.prior()
        with clock(member.membership.ends_on - timedelta(days=5)):
            self.choice(self.flow(), "email_later")
            event = MembershipRenewalPrompt.objects.get(action="email_later")
        with patch("django.utils.timezone.now", return_value=event.remind_at):
            answers = self.race(lambda: prepare(event.pk).pk, lambda: prepare(event.pk).pk)
        self.assertEqual(answers[0], answers[1])
        self.assertEqual(MembershipPromptEmail.objects.count(), 1)
