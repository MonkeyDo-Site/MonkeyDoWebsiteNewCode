from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from core.account_management import save_staff_account
from core.account_security import (
    rotate_recovery_codes,
    start_owner_challenge,
    verify_owner_challenge,
)
from core.models import TrustedOwnerBrowser


@skipUnless(connection.vendor == "postgresql", "Account concurrency requires PostgreSQL.")
class AccountConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner", email="owner@example.invalid", is_staff=True, is_superuser=True
        )

    def parallel(self, operation):
        barrier = Barrier(2)

        def attempt(i):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation(i)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(attempt, range(2)))

    def test_same_email_code_can_create_only_one_verified_browser(self):
        import re

        from django.core import mail

        challenge = start_owner_challenge(self.owner)
        code = re.search(r"code is ([0-9]{6})", mail.outbox[-1].body).group(1)
        results = self.parallel(lambda i: bool(verify_owner_challenge(challenge.pk, code)))
        self.assertCountEqual(results, [True, False])
        self.assertEqual(TrustedOwnerBrowser.objects.count(), 1)

    def test_recovery_code_single_use_across_distinct_challenges(self):
        code = rotate_recovery_codes(self.owner)[0]
        challenges = [start_owner_challenge(self.owner) for _ in range(2)]
        results = self.parallel(lambda i: bool(verify_owner_challenge(challenges[i].pk, code)))
        self.assertCountEqual(results, [True, False])
        self.assertEqual(TrustedOwnerBrowser.objects.count(), 1)

    def test_concurrent_case_variant_username_creation_is_controlled(self):
        from django.core.exceptions import ValidationError

        owner_id = self.owner.pk

        def operation(i):
            owner = get_user_model().objects.get(pk=owner_id)
            try:
                save_staff_account(
                    owner=owner,
                    username=["new-staff", "NEW-STAFF"][i],
                    email="staff@example.invalid",
                    password="Artificial-Staff-Test-928!",
                )
                return True
            except ValidationError:
                return False

        self.assertCountEqual(self.parallel(operation), [True, False])

    def test_two_browsers_cannot_redeem_reset_link_twice(self):
        import re
        from unittest.mock import patch

        from django.core import mail
        from django.test import Client

        from core.account_views import ProtectedPasswordResetConfirmView

        get_user_model().objects.create_user(
            username="reset-staff",
            email="staff@example.invalid",
            password="Original-artificial-password-172!",
            is_staff=True,
        )
        clients = [Client(), Client()]
        clients[0].post("/accounts/password-reset/", {"email": "staff@example.invalid"})
        link = re.search(
            r"/accounts/reset/[A-Za-z0-9_-]+/[A-Za-z0-9-]+/", mail.outbox[-1].body
        ).group(0)
        paths = [client.get(link).url for client in clients]
        ready = Barrier(2)
        original = ProtectedPasswordResetConfirmView.form_valid

        def synchronized(view, form):
            ready.wait(timeout=10)
            return original(view, form)

        def operation(i):
            password = f"Updated-artificial-password-{i}-741!"
            return (
                clients[i]
                .post(paths[i], {"new_password1": password, "new_password2": password})
                .status_code
            )

        with patch.object(ProtectedPasswordResetConfirmView, "form_valid", synchronized):
            self.assertCountEqual(self.parallel(operation), [302, 200])
