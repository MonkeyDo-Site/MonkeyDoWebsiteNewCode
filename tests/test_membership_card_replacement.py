"""Replacement storage authorizes only the remaining accepted membership payments."""

import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.membership_card_setup import make_flow
from core.membership_payments import card_update_review, change_card
from core.membership_records import MembershipBillingAction
from core.models import PaymentConsent, PaymentOperation, PaymentSetup
from core.payments.gateway import ProviderFailure
from tests import test_membership_card_setup as fixtures
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
class MembershipCardReplacementTests(TestCase):
    setUp = fixtures.MembershipCardSetupTests.setUp
    buy = fixtures.MembershipCardSetupTests.buy
    gateway = fixtures.MembershipCardSetupTests.gateway
    card = fixtures.MembershipCardSetupTests.card
    save_card = fixtures.MembershipCardSetupTests.save_card

    def member_flow(self):
        member = self.buy()
        self.key = uuid.uuid4()
        self.current = card_update_review(actor=self.staff, member_id=member.pk)
        flow = make_flow(
            actor=self.staff, customer=self.customer, request_key=self.key, offer=self.current
        )
        return member, flow

    def save_replacement(self, flow, retain=False):
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            return self.save_card(flow, retain=retain)

    def update(self, member, setup, **changes):
        return change_card(
            **(
                dict(
                    actor=self.staff,
                    member_id=member.pk,
                    method_id=setup.method_id,
                    revision=1,
                    request_key=self.key,
                    accepted=True,
                    reviewed=self.current["fingerprint"],
                    card_authorization_id=setup.membership_authorization.pk,
                )
                | changes
            )
        )

    def test_new_scoped_source_updates_once_without_charging_or_changing_old_operations(self):
        member, flow = self.member_flow()
        old_op = PaymentOperation.objects.get()
        original_terms = member.terms_text
        original_dates = list(member.installments.values_list("due_on", flat=True))
        setup = self.save_replacement(flow)
        member.billing_state.refresh_from_db()
        self.assertEqual(member.billing_state.mandate.method_id, self.method.pk)
        self.assertIn("does not charge it or retry", setup.membership_authorization.storage_text)
        self.assertNotIn("initial payment", setup.membership_authorization.storage_text)
        action = self.update(member, setup)
        self.assertEqual(self.update(member, setup).pk, action.pk)
        member.billing_state.refresh_from_db()
        self.assertEqual(member.billing_state.mandate.method_id, setup.method_id)
        old_op.refresh_from_db()
        self.method.refresh_from_db()
        self.assertEqual(old_op.method_id, self.method.pk)
        self.assertEqual(old_op.state, "ready")
        self.assertEqual(self.method.state, "active")
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertFalse(PaymentConsent.objects.exists())
        self.assertEqual(member.terms_text, original_terms)
        self.assertEqual(list(member.installments.values_list("due_on", flat=True)), original_dates)
        self.assertEqual(
            action.details["card_authorization"], str(setup.membership_authorization.pk)
        )

    def test_authorization_cannot_move_to_another_membership_request_source_or_actor(self):
        member, flow = self.member_flow()
        setup = self.save_replacement(flow)
        for change in (
            {"request_key": uuid.uuid4()},
            {"method_id": self.method.pk},
            {"actor": self.owner},
            {"reviewed": "stale"},
            {"accepted": False},
        ):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.update(member, setup, **change)
        self.assertFalse(MembershipBillingAction.objects.exists())

    def test_other_billing_update_invalidates_stored_authority_and_blocks_new_exchange(self):
        member, flow = self.member_flow()
        setup = self.save_replacement(flow)
        change_card(
            actor=self.staff,
            member_id=member.pk,
            method_id=self.method.pk,
            revision=1,
            request_key=uuid.uuid4(),
            accepted=True,
        )
        with self.assertRaises(ValidationError):
            self.update(member, setup)
        with patch("core.payments.setup.Gateway") as gateway, self.assertRaises(ValidationError):
            self.save_card(flow)
        gateway.return_value.create_customer.assert_not_called()
        gateway.return_value.save_card.assert_not_called()
        gateway.return_value.method.assert_not_called()
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_authority_for_one_membership_cannot_update_another_of_same_customer(self):
        member, flow = self.member_flow()
        setup = self.save_replacement(flow)
        other = self.buy()
        with self.assertRaises(ValidationError):
            self.update(
                member,
                setup,
                member_id=other.pk,
                reviewed=card_update_review(actor=self.staff, member_id=other.pk)["fingerprint"],
            )
        self.assertFalse(MembershipBillingAction.objects.exists())

    def test_future_visit_retention_changes_default_only_on_confirmed_update(self):
        member, flow = self.member_flow()
        setup = self.save_replacement(flow, retain=True)
        self.method.refresh_from_db()
        self.assertTrue(self.method.reusable)
        self.update(member, setup)
        self.method.refresh_from_db()
        self.assertFalse(self.method.reusable)
        self.assertEqual(self.method.state, "active")
        self.assertEqual(PaymentOperation.objects.get().method_id, self.method.pk)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_expired_authority_cannot_update_billing(self):
        member, flow = self.member_flow()
        setup = self.save_replacement(flow)
        with (
            patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)),
            self.assertRaises(ValidationError),
        ):
            self.update(member, setup)
        self.assertFalse(MembershipBillingAction.objects.exists())

    def endpoint_payload(self, member):
        self.client.force_login(self.staff)
        page = self.client.get(f"/staff/memberships/purchased/{member.pk}/")
        form = page.context["card_form"]
        return dict(
            update={key: str(form[key].value()) for key in ("request_key", "revision", "reviewed")}
            | {"accepted": True},
            setup_key=str(uuid.uuid4()),
            nonce="nonce-Synthetic",
            expiry_month=12,
            expiry_year=2035,
            retention_choice="no",
        )

    def send(self, member, data, client=None):
        return (client or self.client).post(
            f"/staff/memberships/{member.pk}/card/",
            json.dumps(data),
            content_type="application/json",
        )

    def test_combined_overview_new_card_endpoint_then_final_update_has_no_new_payment(self):
        member, _ = self.member_flow()
        payload = self.endpoint_payload(member)
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            result = self.send(member, payload)
        self.assertEqual(result.status_code, 200, result.content)
        member.billing_state.refresh_from_db()
        self.assertEqual(member.billing_state.revision, 1)
        post = payload["update"] | dict(
            action="card_update",
            method=result.json()["method_id"],
            card_authorization=result.json()["authorization_id"],
        )
        response = self.client.post(f"/staff/memberships/purchased/{member.pk}/", post)
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(
            self.client.post(f"/staff/memberships/purchased/{member.pk}/", post).status_code, 302
        )
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(MembershipBillingAction.objects.count(), 1)
        self.assertContains(
            self.client.get(f"/staff/memberships/purchased/{member.pk}/"),
            "Save and use membership card",
        )

    def test_uncertain_save_reload_and_replay_never_exchange_again_or_update_mandate(self):
        member, _ = self.member_flow()
        payload = self.endpoint_payload(member)
        with patch("core.payments.setup.Gateway") as gateway:
            gateway.return_value.create_customer.side_effect = ProviderFailure()
            first = self.send(member, payload)
            self.assertEqual(first.status_code, 202, first.content)
            self.assertEqual(self.send(member, payload).status_code, 202)
            gateway.return_value.create_customer.assert_called_once()
        url = f"/staff/memberships/card/{payload['setup_key']}/"
        self.assertEqual(self.client.get(url).status_code, 202)
        page = self.client.get(
            f"/staff/memberships/purchased/{member.pk}/?card_key={payload['update']['request_key']}"
        )
        self.assertContains(page, url)
        other = Client()
        other.force_login(self.staff)
        self.assertEqual(other.get(url).status_code, 404)
        member.billing_state.refresh_from_db()
        self.assertEqual(member.billing_state.revision, 1)
        self.assertFalse(MembershipBillingAction.objects.exists())

    def test_endpoint_rejects_raw_fields_stale_review_and_unaccepted_before_io(self):
        member, _ = self.member_flow()
        payload = self.endpoint_payload(member)
        for data in (
            payload | {"card_number": "forbidden"},
            payload | {"update": payload["update"] | {"accepted": False}},
            payload | {"update": payload["update"] | {"reviewed": "stale"}},
        ):
            with patch("core.payments.setup.Gateway") as gateway:
                self.assertEqual(self.send(member, data).status_code, 400)
                gateway.assert_not_called()
        self.assertFalse(PaymentSetup.objects.exists())

    def test_endpoint_csrf_permissions_feature_and_recovery_gate(self):
        member, _ = self.member_flow()
        payload = self.endpoint_payload(member)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(self.send(member, payload, client).status_code, 403)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertEqual(self.send(member, payload).status_code, 404)
        with override_settings(RECOVERY_HOLD=True), patch("core.payments.setup.Gateway") as gateway:
            self.assertEqual(self.send(member, payload).status_code, 400)
            gateway.assert_not_called()
        self.staff.groups.clear()
        self.client.force_login(self.staff)
        self.assertEqual(self.send(member, payload).status_code, 403)
