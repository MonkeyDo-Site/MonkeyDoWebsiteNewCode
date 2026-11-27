"""One verified public initial checkout, without creating a visit or retrying money."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.membership_public_checkout import MembershipPublicCheckout
from core.models import Booking, Customer, FinancialPosting, MembershipPurchase, PaymentOperation
from core.payments.gateway import ProviderFailure
from core.payments.ledger import record_result
from core.public_membership_views import INITIAL_SESSION_KEY
from tests import test_membership_sales as fixtures
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
class PublicMembershipJoinTests(TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp

    @property
    def url(self):
        return reverse("public_membership_join")

    def post_identity(self, data):
        flow = self.client.session[INITIAL_SESSION_KEY]
        return self.client.post(
            self.url, data | {"wizard_key": flow["key"], "wizard_stage": flow["stage"]}
        )

    def start(self, *, new=False):
        self.client.get(self.url)
        self.post_identity(
            dict(phone="2025550191" if new else self.customer.phone, visited="no" if new else "yes")
        )
        self.post_identity(
            dict(last_name="Friedman", email="new@example.invalid")
            if new
            else dict(last_name=self.customer.last_name)
        )
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200, page.content)
        form = page.context["form"]
        data = dict(
            customer=form["customer"].value(),
            request_key=str(form["request_key"].value()),
            operation="purchase",
            prior_id="",
            kind="subscription",
            places=2,
            months=3,
            billing="monthly",
            starts_on=str(timezone.localdate()),
            expected_method="card",
        )
        return page, data

    def prepare(self):
        page, data = self.start()
        response = self.client.post(reverse("public_membership_join_offer"), data)
        self.assertEqual(response.status_code, 200, response.content)
        data.update(accepted="on", reviewed=response.json()["fingerprint"])
        with patch("core.membership_card_setup.Gateway") as gateway:
            gateway.return_value.method.return_value = dict(
                id=345,
                customer_id=12,
                payment_method_type="card",
                card_type="Visa",
                last4="1118",
                expiry_month=12,
                expiry_year=2035,
            )
            result = self.client.post(
                reverse("public_membership_join_card"),
                json.dumps(dict(purchase=data, method=str(self.method.pk))),
                content_type="application/json",
            )
            self.assertEqual(result.status_code, 200, result.content)
            gateway.return_value.charge.assert_not_called()
        data.update(
            method=str(self.method.pk),
            card_authorization=result.json()["authorization_id"],
            action="confirm",
        )
        return data

    def test_one_checkout_contains_plan_card_price_terms_and_confirmation_without_visit(self):
        page, data = self.start()
        for label in (
            "Your membership",
            "Membership type",
            "Number of memberships",
            "Membership terms",
            "Confirm membership and pay",
            "data-membership-offer",
        ):
            self.assertContains(page, label)
        self.assertContains(page, 'type="hidden" name="customer"')
        self.assertNotContains(page, "Your renewal")
        self.assertEqual(page["Referrer-Policy"], "same-origin")
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(MembershipPublicCheckout.objects.count(), 1)
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_final_confirmation_is_idempotent_and_receipt_distinguishes_pending_and_received(self):
        data = self.prepare()
        for _ in range(2):
            self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        receipt = self.client.get(reverse("public_membership_join_receipt"))
        self.assertContains(receipt, "Your membership is not confirmed yet")
        self.assertNotContains(receipt, "Your renewal")
        self.assertFalse(FinancialPosting.objects.exists())
        operation = PaymentOperation.objects.get()
        record_result(
            operation_id=operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="99101",
        )
        self.assertContains(
            self.client.get(reverse("public_membership_join_receipt")),
            "Your membership is confirmed",
        )
        self.assertFalse(Booking.objects.exists())

    def test_new_customer_uses_same_checkout_without_existing_card_or_any_booking(self):
        page, data = self.start(new=True)
        self.assertContains(page, "Family Friedman")
        self.assertContains(page, "New membership card")
        self.assertEqual(Customer.objects.count(), 2)
        self.assertFalse(PaymentOperation.objects.exists())
        result = self.client.post(reverse("public_membership_join_offer"), data)
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["cards"], [])

    def test_wrong_tab_and_another_browser_cannot_use_customer_checkout_or_card(self):
        _, data = self.start()
        other = Client()
        response = other.post(reverse("public_membership_join_offer"), data)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(self.customer.email, response.content.decode())
        self.assertEqual(other.get(reverse("public_membership_join_receipt")).status_code, 302)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_current_customer_revision_stale_terms_and_foreign_prior_cannot_confirm(self):
        data = self.prepare()
        response = self.client.post(self.url, data | {"places": 3})
        self.assertContains(response, "changed", status_code=200)
        response = self.client.post(
            reverse("public_membership_join_offer"), data | {"prior_id": "987654"}
        )
        self.assertEqual(response.status_code, 400)
        self.customer.revision += 1
        self.customer.save()
        self.assertContains(
            self.client.post(self.url, data), "customer details changed", status_code=400
        )
        self.assertFalse(PaymentOperation.objects.exists())

    def test_expiry_and_restart_cannot_create_another_purchase_after_acceptance(self):
        data = self.prepare()
        self.client.post(self.url, data)
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            self.assertContains(self.client.get(self.url), "verification expired", status_code=400)
            self.assertEqual(self.client.get(self.url + "?restart=1").status_code, 400)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_conflicting_profiles_require_explicit_choice_before_any_checkout(self):
        other = Customer.objects.create(
            last_name=self.customer.last_name, phone="2025550102", email="other@example.invalid"
        )
        self.client.get(self.url)
        self.post_identity(dict(phone=self.customer.phone, visited="yes"))
        self.post_identity(dict(last_name=self.customer.last_name, email=other.email))
        page = self.client.get(self.url)
        self.assertContains(page, "Which profile would you like to use?")
        self.assertFalse(MembershipPublicCheckout.objects.exists())
        self.post_identity(dict(profile_action="other"))
        self.assertEqual(MembershipPublicCheckout.objects.get().customer_id, other.pk)

    def test_duplicate_email_recovery_returns_to_membership_identity(self):
        self.client.get(self.url)
        self.post_identity(dict(phone="2025550191", visited="no"))
        result = self.post_identity(dict(last_name="New", email=self.customer.email))
        self.assertContains(result, self.url + "?restart=1")
        self.assertNotContains(result, "/book/details/?restart=1")
        self.assertFalse(MembershipPublicCheckout.objects.exists())

    def test_csrf_and_feature_off_cover_all_join_write_endpoints(self):
        strict = Client(enforce_csrf_checks=True)
        strict.get(self.url)
        self.assertEqual(
            strict.post(self.url, dict(phone=self.customer.phone, visited="yes")).status_code, 403
        )
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            for name in (
                "public_membership_join",
                "public_membership_join_offer",
                "public_membership_join_card",
            ):
                self.assertEqual(self.client.post(reverse(name)).status_code, 404)

    def test_new_card_unknown_cannot_restart_or_repeat_provider_storage(self):
        _, data = self.start(new=True)
        offer = self.client.post(reverse("public_membership_join_offer"), data).json()
        data.update(accepted="on", reviewed=offer["fingerprint"])
        from uuid import uuid4

        payload = dict(
            purchase=data,
            setup_key=str(uuid4()),
            nonce="nonce-Synthetic",
            expiry_month=12,
            expiry_year=2035,
            retention_choice="no",
        )
        with patch("core.payments.setup.Gateway") as gateway:
            gateway.return_value.create_customer.side_effect = ProviderFailure("unknown")
            response = self.client.post(
                reverse("public_membership_join_card"),
                json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 202, response.content)
            self.assertEqual(self.client.get(self.url + "?restart=1").status_code, 400)
            payload["setup_key"] = str(uuid4())
            self.client.post(
                reverse("public_membership_join_card"),
                json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(gateway.return_value.create_customer.call_count, 1)
        self.assertFalse(PaymentOperation.objects.exists())
