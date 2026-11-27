"""Expired storage evidence can be read; only fresh explicit consent can replace authority."""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.membership_records import MembershipCardAuthorization, MembershipPurchase
from core.models import PaymentOperation, PaymentSetup
from tests import test_membership_arrival_card_entry as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class ExpiredMembershipCardReviewTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.CombinedArrivalNewCardTests.prepare
    web_data = fixtures.CombinedArrivalNewCardTests.web_data
    start = fixtures.CombinedArrivalNewCardTests.start
    store = fixtures.CombinedArrivalNewCardTests.store
    reviewed_source = fixtures.CombinedArrivalNewCardTests.reviewed_source
    finish = fixtures.CombinedArrivalNewCardTests.finish

    def expired(self, *, unknown=False):
        self.start()
        self.saved = self.store(unknown=unknown)
        self.setup = PaymentSetup.objects.get(pk=self.card_payload["setup_key"])
        self.original = self.setup.membership_authorization
        self.original_expiry = self.original.expires_at
        self.later = timezone.now() + timedelta(minutes=21)

    def refresh_data(self):
        return dict(
            purchase=self.card_payload["purchase"],
            method=str(self.setup.method_id),
            previous_authorization=str(self.original.pk),
        )

    def post_refresh(self, payload):
        with patch("core.membership_card_setup.Gateway") as gateway:
            if self.setup.method_id:
                method = self.setup.method
                gateway.return_value.method.return_value = self.card() | {
                    "id": int(method.provider_method),
                    "customer_id": int(method.provider_customer),
                    "last4": "1111",
                }
            response = self.client.post(
                reverse("membership_card_setup"), payload, content_type="application/json"
            )
            gateway.return_value.save_card.assert_not_called()
            gateway.return_value.charge.assert_not_called()
        return response, gateway

    def test_expired_setup_status_is_read_only_and_keeps_original_expiry(self):
        self.expired()
        flow_before = self.client.session["membership_card_flows"]
        with (
            patch("django.utils.timezone.now", return_value=self.later),
            patch("core.payments.setup.Gateway") as gateway,
        ):
            result = self.client.get(reverse("membership_card_status", args=[self.setup.pk]))
            preview = self.client.post(reverse("membership_offer"), self.card_payload["purchase"])
            gateway.assert_not_called()
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["authorization_expired"])
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertIn(str(self.setup.method_id), [row["id"] for row in preview.json()["cards"]])
        self.original.refresh_from_db()
        self.assertEqual(self.original.expires_at, self.original_expiry)
        self.assertEqual(self.client.session["membership_card_flows"], flow_before)
        self.assertEqual(MembershipCardAuthorization.objects.count(), 1)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_fresh_explicit_review_uses_get_and_new_authority_before_purchase(self):
        self.expired()
        with patch("django.utils.timezone.now", return_value=self.later):
            fresh, gateway = self.post_refresh(self.refresh_data())
            self.assertEqual(fresh.status_code, 200, fresh.content)
            gateway.return_value.method.assert_called_once()
            new = MembershipCardAuthorization.objects.get(pk=fresh.json()["authorization_id"])
            self.assertNotEqual(new.pk, self.original.pk)
            self.assertEqual(new.expires_at, self.later + timedelta(minutes=20))
            status = self.client.get(reverse("membership_card_status", args=[self.setup.pk]))
            self.assertEqual(status.json()["authorization_id"], str(new.pk))
            self.assertFalse(status.json()["authorization_expired"])
            self.assertEqual(status.json()["authorization_seconds_remaining"], 1200)
            self.assertEqual(
                self.client.session["membership_card_flows"][str(new.request_key)]["setup_key"],
                str(self.setup.pk),
            )
            self.original.refresh_from_db()
            self.assertEqual(self.original.expires_at, self.original_expiry)
            self.assertFalse(PaymentOperation.objects.exists())
            reviewed = self.reviewed_source(fresh)
            self.assertEqual(self.finish(reviewed).status_code, 200)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentSetup.objects.filter(kind="membership").count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_unknown_expired_setup_is_visible_but_cannot_refresh_or_repeat_storage(self):
        self.expired(unknown=True)
        with patch("django.utils.timezone.now", return_value=self.later):
            status = self.client.get(reverse("membership_card_status", args=[self.setup.pk]))
            self.assertEqual(status.status_code, 202)
            payload = self.refresh_data() | {"method": str(self.play.card_agreement.method_id)}
            blocked, gateway = self.post_refresh(payload)
            self.assertEqual(blocked.status_code, 400)
            gateway.assert_not_called()
            with patch("core.payments.setup.Gateway") as storage:
                repeated = self.client.post(
                    reverse("membership_card_setup"),
                    self.card_payload | {"setup_key": str(uuid.uuid4())},
                    content_type="application/json",
                )
                storage.assert_not_called()
        self.assertEqual(repeated.status_code, 400)
        self.assertEqual(MembershipCardAuthorization.objects.count(), 1)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_fresh_scope_requires_current_terms_acceptance(self):
        self.expired()
        payload = self.refresh_data()
        payload["purchase"] = payload["purchase"] | {"accepted": False}
        with patch("django.utils.timezone.now", return_value=self.later):
            rejected, gateway = self.post_refresh(payload)
        self.assertEqual(rejected.status_code, 400)
        gateway.assert_not_called()
        self.assertEqual(MembershipCardAuthorization.objects.count(), 1)

    def test_another_browser_cannot_recreate_an_expired_card_flow(self):
        self.expired()
        other = Client()
        other.force_login(self.staff)
        with (
            patch("django.utils.timezone.now", return_value=self.later),
            patch("core.membership_card_setup.Gateway") as gateway,
        ):
            rejected = other.post(
                reverse("membership_card_setup"),
                self.refresh_data(),
                content_type="application/json",
            )
            gateway.assert_not_called()
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(MembershipCardAuthorization.objects.count(), 1)

    def test_customer_revision_change_does_not_relax_expired_scope(self):
        self.expired()
        type(self.customer).objects.filter(pk=self.customer.pk).update(
            revision=self.customer.revision + 1
        )
        with patch("django.utils.timezone.now", return_value=self.later):
            rejected, gateway = self.post_refresh(self.refresh_data())
            status = self.client.get(reverse("membership_card_status", args=[self.setup.pk]))
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(status.status_code, 404)
        gateway.assert_not_called()

    def test_another_actor_cannot_use_a_copied_expired_flow(self):
        self.expired()
        other = Client()
        verified_owner_login(other, self.owner)
        session = other.session
        session["membership_card_flows"] = self.client.session["membership_card_flows"]
        session.save()
        with (
            patch("django.utils.timezone.now", return_value=self.later),
            patch("core.membership_card_setup.Gateway") as gateway,
        ):
            rejected = other.post(
                reverse("membership_card_setup"),
                self.refresh_data(),
                content_type="application/json",
            )
            gateway.assert_not_called()
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(MembershipCardAuthorization.objects.count(), 1)

    def test_expired_review_does_not_authorize_a_different_saved_source(self):
        self.expired()
        with patch("django.utils.timezone.now", return_value=self.later):
            rejected, gateway = self.post_refresh(
                self.refresh_data() | {"method": str(self.play.card_agreement.method_id)}
            )
        self.assertEqual(rejected.status_code, 400)
        gateway.assert_not_called()
        self.assertEqual(MembershipCardAuthorization.objects.count(), 1)

    def test_an_existing_purchase_cannot_receive_fresh_initial_payment_authority(self):
        self.expired()
        reviewed = self.reviewed_source(self.saved)
        self.assertEqual(self.finish(reviewed).status_code, 200)
        with patch("core.payments.setup.Gateway") as storage:
            replay = self.client.post(
                reverse("membership_card_setup"), self.card_payload, content_type="application/json"
            )
            storage.assert_not_called()
        self.assertEqual(replay.status_code, 400)
        with patch("django.utils.timezone.now", return_value=self.later):
            rejected, gateway = self.post_refresh(self.refresh_data())
            status = self.client.get(reverse("membership_card_status", args=[self.setup.pk]))
        self.assertEqual(rejected.status_code, 400)
        gateway.assert_not_called()
        self.assertTrue(status.json()["purchase_recorded"])
        self.assertEqual(PaymentOperation.objects.count(), 1)
