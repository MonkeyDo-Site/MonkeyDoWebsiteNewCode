"""Browser-scoped membership card setup and one final purchase confirmation."""

import json
import uuid
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from core.membership_records import MembershipCardAuthorization, MembershipPurchase
from core.membership_sales import offer
from core.models import FinancialSale, PaymentConsent, PaymentOperation
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
class MembershipCardViewTests(TestCase):
    setUp = fixtures.MembershipCardSetupTests.setUp
    gateway = fixtures.MembershipCardSetupTests.gateway
    card = fixtures.MembershipCardSetupTests.card

    def payload(self):
        return dict(
            purchase=dict(
                customer=self.customer.pk,
                kind="subscription",
                places=2,
                months=3,
                billing="monthly",
                starts_on="2027-10-31",
                expected_method="card",
                operation="purchase",
                request_key=str(self.key),
                reviewed=offer(**self.values)["fingerprint"],
                accepted=True,
            ),
            setup_key=str(uuid.uuid4()),
            nonce="nonce-Synthetic",
            expiry_month=12,
            expiry_year=2035,
            retention_choice="no",
        )

    def send(self, data):
        return self.client.post(
            "/staff/memberships/card/", json.dumps(data), content_type="application/json"
        )

    def test_new_card_saves_no_visit_consent_and_one_confirmation_uses_it_for_membership(self):
        self.client.force_login(self.staff)
        data = self.payload()
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            result = self.send(data)
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["state"], "saved")
        self.assertFalse(FinancialSale.objects.exists())
        self.assertFalse(PaymentConsent.objects.exists())
        post = data["purchase"] | dict(
            action="confirm",
            method=result.json()["method_id"],
            card_authorization=result.json()["authorization_id"],
        )
        saved = self.client.post("/staff/memberships/purchase/", post)
        self.assertEqual(saved.status_code, 302, saved.content)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        member = MembershipPurchase.objects.get()
        self.assertEqual(
            member.billing_state.mandate.method_id, uuid.UUID(result.json()["method_id"])
        )

    def test_prepaid_split_can_authorize_a_card_only_for_the_remaining_part(self):
        self.client.force_login(self.staff)
        values = self.values | dict(
            billing="prepaid", expected_method="split", split={"cash": "100.00"}
        )
        data = self.payload()
        data["purchase"].update(
            billing="prepaid",
            expected_method="split",
            first_cash="100.00",
            reviewed=offer(**values)["fingerprint"],
        )
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            result = self.send(data)
        self.assertEqual(result.status_code, 200, result.content)
        self.assertFalse(PaymentOperation.objects.exists())
        final = self.client.post(
            "/staff/memberships/purchase/",
            data["purchase"]
            | dict(
                action="confirm",
                method=result.json()["method_id"],
                card_authorization=result.json()["authorization_id"],
                verified_received="on",
            ),
        )
        self.assertEqual(final.status_code, 302, final.content)
        self.assertEqual(str(PaymentOperation.objects.get(tender="card").amount), "8.18")
        self.assertEqual(str(PaymentOperation.objects.get(tender="cash").amount), "100.00")
        self.assertFalse(PaymentConsent.objects.exists())

    def test_fully_manual_prepaid_split_cannot_start_an_unnecessary_card_exchange(self):
        self.client.force_login(self.staff)
        values = self.values | dict(
            billing="prepaid", expected_method="split", split={"cash": "107.94"}
        )
        data = self.payload()
        data["purchase"].update(
            billing="prepaid",
            expected_method="split",
            first_cash="107.94",
            reviewed=offer(**values)["fingerprint"],
        )
        with patch("core.payments.setup.Gateway") as gateway:
            response = self.send(data)
            gateway.assert_not_called()
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_uncertain_setup_replays_without_provider_post_and_recovers_only_in_original_browser(
        self,
    ):
        self.client.force_login(self.staff)
        data = self.payload()
        with patch("core.payments.setup.Gateway") as gateway:
            gateway.return_value.create_customer.side_effect = ProviderFailure()
            first = self.send(data)
            second = self.send(data)
            gateway.return_value.create_customer.assert_called_once()
        self.assertEqual(first.status_code, 202, first.content)
        self.assertEqual(second.status_code, 202, second.content)
        url = first.json()["status_url"]
        self.assertEqual(self.client.get(url).status_code, 202)
        other = Client()
        other.force_login(self.staff)
        self.assertEqual(other.get(url).status_code, 404)
        reload = self.client.get(f"/staff/memberships/purchase/?purchase_key={self.key}")
        self.assertContains(reload, url)
        self.assertEqual(str(reload.context["form"]["request_key"].value()), str(self.key))
        self.assertFalse(PaymentOperation.objects.exists())

    def test_stale_or_unaccepted_terms_and_raw_fields_are_rejected_before_provider_io(self):
        self.client.force_login(self.staff)
        for change in (dict(accepted=False), dict(reviewed="stale")):
            data = self.payload()
            data["purchase"].update(change)
            with patch("core.payments.setup.Gateway") as gateway:
                self.assertEqual(self.send(data).status_code, 400)
                gateway.assert_not_called()
        data = self.payload() | {"card_number": "synthetic-forbidden-field"}
        with patch("core.payments.setup.Gateway") as gateway:
            self.assertEqual(self.send(data).status_code, 400)
            gateway.assert_not_called()
        self.assertFalse(MembershipCardAuthorization.objects.exists())

    def test_card_endpoints_require_csrf_permission_and_feature_flag(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(
            client.post(
                "/staff/memberships/card/",
                json.dumps(self.payload()),
                content_type="application/json",
            ).status_code,
            403,
        )
        self.client.force_login(self.staff)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertEqual(self.send({}).status_code, 404)
        self.staff.groups.clear()
        self.client.force_login(self.staff)
        self.assertEqual(self.send({}).status_code, 403)

    def test_new_card_remains_available_after_membership_selection_changes(self):
        self.client.force_login(self.staff)
        data = self.payload()
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            result = self.send(data)
        preview = self.client.post("/staff/memberships/offer/", data["purchase"] | dict(places=3))
        self.assertEqual(preview.status_code, 200)
        self.assertIn(result.json()["method_id"], [row["id"] for row in preview.json()["cards"]])
