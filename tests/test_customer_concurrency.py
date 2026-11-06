from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from core.customers import create_customer, update_customer
from core.models import AuditEvent, Customer


@skipUnless(connection.vendor == "postgresql", "Contact ownership concurrency requires PostgreSQL.")
class CustomerConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="concurrency-staff", is_staff=True
        )
        call_command("configure_staff_group", stdout=StringIO())
        self.actor.groups.add(Group.objects.get(name="MonkeyDo Staff"))

    def parallel(self, operation):
        ready = Barrier(2)
        actor_id = self.actor.pk

        def attempt(i):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                ready.wait(timeout=10)
                try:
                    operation(actor, i)
                    return "saved"
                except ValidationError:
                    return "rejected"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(attempt, range(2)))

    def test_simultaneous_creation_never_duplicates_phone_or_audit(self):
        results = self.parallel(
            lambda actor, i: create_customer(
                actor=actor, last_name=f"Test {i}", phone="2025550100", email="test@example.invalid"
            )
        )
        self.assertCountEqual(results, ["saved", "rejected"])
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="customer.created").count(), 1)

    def test_simultaneous_corrections_do_not_silently_overwrite(self):
        customer = create_customer(
            actor=self.actor, last_name="Original", phone="2025550100", email="test@example.invalid"
        )
        results = self.parallel(
            lambda actor, i: update_customer(
                actor=actor,
                customer_id=customer.pk,
                revision=1,
                last_name=f"Changed {i}",
                phone=customer.phone,
                email=customer.email,
            )
        )
        self.assertCountEqual(results, ["saved", "rejected"])
        self.assertEqual(AuditEvent.objects.filter(action="customer.updated").count(), 1)
        customer.refresh_from_db()
        self.assertEqual(customer.revision, 2)


@skipUnless(connection.vendor == "postgresql", "Login serialization requires PostgreSQL.")
class LoginConcurrencyTests(TransactionTestCase):
    def test_parallel_failures_cannot_bypass_five_attempt_delay(self):
        from unittest.mock import patch

        from django.test import Client, override_settings
        from django.utils import timezone

        from core.models import LoginThrottle

        ready = Barrier(6)
        fixed_now = timezone.now()

        def attempt(_):
            close_old_connections()
            try:
                ready.wait(timeout=10)
                return (
                    Client()
                    .post(
                        "/accounts/login/",
                        {"username": "unknown-concurrent", "password": "artificial-wrong-password"},
                    )
                    .status_code
                )
            finally:
                connections.close_all()

        with (
            override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]),
            patch("core.security.timezone.now", return_value=fixed_now),
            ThreadPoolExecutor(max_workers=6) as pool,
        ):
            results = list(pool.map(attempt, range(6)))
        self.assertEqual(results.count(200), 5)
        self.assertEqual(results.count(429), 1)
        self.assertEqual(LoginThrottle.objects.get(key__startswith="account:").failures, 5)
