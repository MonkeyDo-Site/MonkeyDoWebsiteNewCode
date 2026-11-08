from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from core.memberships import create_draft
from core.models import (
    AuditEvent,
    MembershipDraft,
    MembershipDraftCycle,
    MembershipPricing,
    PricingPolicy,
)
from tests.test_memberships import MembershipDraftTests


@skipUnless(
    connection.vendor == "postgresql", "Membership submission concurrency requires PostgreSQL."
)
class MembershipConcurrencyTests(TransactionTestCase):
    def setUp(self):
        MembershipDraftTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create()
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def test_simultaneous_same_submission_creates_one_cohort_and_schedule(self):
        ready = Barrier(2)

        def attempt(_):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.staff.pk)
                ready.wait(timeout=10)
                return create_draft(**(self.args | {"actor": actor})).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipDraft.objects.count(), 1)
        self.assertEqual(MembershipDraftCycle.objects.count(), 3)
        self.assertEqual(AuditEvent.objects.filter(action="membership.draft_created").count(), 1)
