"""The private customer renewal screen reveals only verified renewal data."""

import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.membership_records import MembershipPublicAcceptance
from core.models import MembershipPricing, PaymentOperation
from core.payments.gateway import ProviderFailure
from core.payments.ledger import record_result
from tests import test_membership_public_authority as fixtures
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
class PublicMembershipViewTests(TestCase):
    setUp = fixtures.MembershipPublicAuthorityTests.setUp
    buy = fixtures.MembershipPublicAuthorityTests.buy
    prior = fixtures.MembershipPublicAuthorityTests.prior
    context = fixtures.MembershipPublicAuthorityTests.context

    def start(self, context=None, client=None):
        context = context or self.context()
        client = client or self.client
        url = reverse("public_membership_renewal", args=[context["token"]])
        result = client.post(
            url, dict(action="verify", phone=self.customer.phone, last_name=self.customer.last_name)
        )
        self.assertEqual(result.status_code, 302, result.content)
        page = client.get(url)
        self.assertEqual(page.status_code, 200, page.content)
        form = page.context["form"]
        data = dict(
            customer=self.customer.pk,
            kind="subscription",
            places=1,
            months=1,
            billing="monthly",
            starts_on=str(form["starts_on"].value()),
            expected_method="card",
            operation="renewal",
            prior_id=context["prior"].pk,
            request_key=str(form["request_key"].value()),
        )
        return context, url, data

    def prepare(self, context=None):
        c, url, data = self.start(context)
        response = self.client.post(reverse("public_membership_offer", args=[c["token"]]), data)
        self.assertEqual(response.status_code, 200, response.content)
        data.update(reviewed=response.json()["fingerprint"], accepted="on")
        payload = dict(purchase=data, method=str(self.method.pk))
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
            saved = self.client.post(
                reverse("public_membership_card", args=[c["token"]]),
                json.dumps(payload),
                content_type="application/json",
            )
        self.assertEqual(saved.status_code, 200, saved.content)
        data.update(
            method=saved.json()["method_id"],
            card_authorization=saved.json()["authorization_id"],
            action="confirm",
        )
        return c, url, data

    def test_details_are_hidden_until_phone_and_name_verification_and_private_pages_are_not_cached(
        self,
    ):
        c = self.context()
        url = reverse("public_membership_renewal", args=[c["token"]])
        response = self.client.get(url)
        self.assertContains(response, "Verify your details")
        self.assertNotContains(response, self.customer.last_name)
        self.assertNotContains(response, "$17.99")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertIn("no-store", response["Cache-Control"])
        bad = self.client.post(
            url, dict(action="verify", phone=self.customer.phone, last_name="Other")
        )
        self.assertContains(bad, "could not be verified")
        self.assertNotContains(bad, self.customer.last_name)
        _, _, _ = self.start(c)
        self.assertContains(self.client.get(url), "Your renewal")

    def test_anonymous_customer_can_review_and_confirm_one_renewal_without_staff_privileges(self):
        c, url, data = self.prepare()
        result = self.client.post(url, data)
        self.assertEqual(result.status_code, 302, result.content)
        receipt = self.client.get(result.url)
        self.assertContains(receipt, "Your renewal is not confirmed yet")
        self.assertContains(receipt, "$0.00")
        self.assertContains(receipt, "still being checked")
        member = MembershipPublicAcceptance.objects.get().purchase
        self.assertEqual(member.source, "public")
        self.assertIsNone(member.actor_id)
        self.assertEqual(member.installments.first().invoice.sale.operations.count(), 1)
        repeated = self.client.post(url, data)
        self.assertEqual(repeated.url, result.url)
        self.assertEqual(member.installments.first().invoice.sale.operations.count(), 1)

    def test_verified_second_browser_sees_the_recorded_result_and_never_starts_another_payment(
        self,
    ):
        c, url, data = self.prepare()
        self.client.post(url, data)
        other = Client()
        other.post(
            url, dict(action="verify", phone=self.customer.phone, last_name=self.customer.last_name)
        )
        response = other.get(url)
        self.assertEqual(response.url, reverse("public_membership_receipt", args=[c["token"]]))
        self.assertEqual(MembershipPublicAcceptance.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.filter(actor__isnull=True).count(), 1)

    def test_only_the_cookie_scoped_profile_request_and_renewal_are_accepted(self):
        c, url, data = self.start()
        offer_url = reverse("public_membership_offer", args=[c["token"]])
        for changes in (
            dict(customer=99999),
            dict(prior_id=99999),
            dict(request_key=str(uuid.uuid4())),
            dict(comped="on"),
            dict(expected_method="cash"),
            dict(card_number="unsupported"),
        ):
            with self.subTest(changes=changes):
                result = self.client.post(offer_url, data | changes)
                self.assertEqual(result.status_code, 400, result.content)
        self.assertFalse(MembershipPublicAcceptance.objects.exists())
        unverified = Client()
        self.assertEqual(unverified.post(offer_url, data).status_code, 400)

    def test_stale_price_stops_before_purchase_and_current_terms_are_shown_again(self):
        c, url, data = self.prepare()
        MembershipPricing.objects.create(subscription="20.00", unlimited="45.00", actor=self.owner)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "membership or price changed")
        self.assertFalse(MembershipPublicAcceptance.objects.exists())

    def test_expired_verification_requires_verification_again_before_showing_details(self):
        c, url, _ = self.start()
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            response = self.client.get(url)
        self.assertContains(response, "Verify your details")
        self.assertNotContains(response, self.customer.last_name)

    def test_confirmed_payment_and_decline_have_truthful_customer_receipts(self):
        c, url, data = self.prepare()
        result = self.client.post(url, data)
        member = MembershipPublicAcceptance.objects.get().purchase
        op = member.installments.first().invoice.sale.operations.get()
        record_result(
            operation_id=op.pk, state="succeeded", source="provider", provider_reference="8001"
        )
        receipt = self.client.get(result.url)
        self.assertContains(receipt, "Your renewal is confirmed")
        self.assertContains(receipt, "$18.53")
        self.assertContains(receipt, "will be emailed")
        self.assertNotContains(receipt, "is sent")

    def test_cancelled_private_renewal_reports_refund_due_without_claiming_new_confirmation(self):
        from core.membership_cancellations import cancel, review

        _, url, data = self.prepare()
        result = self.client.post(url, data)
        member = MembershipPublicAcceptance.objects.get().purchase
        op = member.installments.first().invoice.sale.operations.get()
        record_result(
            operation_id=op.pk, state="succeeded", source="provider", provider_reference="8001"
        )
        reviewed = review(
            actor=self.owner, member_id=member.pk, timing="immediate", refund_amount="10.00"
        )
        cancel(
            actor=self.owner,
            member_id=member.pk,
            timing="immediate",
            refund_amount="10.00",
            reviewed=reviewed["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Customer requested cancellation.",
            early_override=True,
            send_confirmation=False,
        )
        receipt = self.client.get(result.url)
        self.assertContains(receipt, "Membership ended")
        self.assertContains(receipt, "A refund of $10.00 remains due")
        self.assertContains(receipt, "$18.53")
        self.assertNotContains(receipt, "A renewal confirmation will be emailed")
        self.assertNotContains(receipt, "Your renewal is confirmed")

    def test_feature_recovery_invalid_link_and_csrf_gates_are_preserved(self):
        c = self.context()
        url = reverse("public_membership_renewal", args=[c["token"]])
        self.assertEqual(
            self.client.get(reverse("public_membership_renewal", args=["invalid"])).status_code, 404
        )
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertEqual(self.client.get(url).status_code, 404)
        with override_settings(RECOVERY_HOLD=True):
            self.assertEqual(self.client.get(url).status_code, 503)
        csrf = Client(enforce_csrf_checks=True)
        self.assertEqual(
            csrf.post(
                url,
                dict(action="verify", phone=self.customer.phone, last_name=self.customer.last_name),
            ).status_code,
            403,
        )

    def test_staff_can_create_customer_link_on_overview_without_binding_a_payment_form(self):
        prior = self.prior()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("membership_overview", args=[prior.pk]),
            dict(action="renewal_link", link_request_key=str(uuid.uuid4())),
        )
        self.assertContains(response, "Open customer renewal page")
        self.assertContains(response, "does not change the seven-day renewal grace period")
        self.assertFalse(response.context["payment_form"].is_bound)
        self.assertEqual(PaymentOperation.objects.filter(actor__isnull=True).count(), 0)

    def test_uncertain_public_card_save_survives_reload_and_is_not_exchanged_again(self):
        c, url, data = self.start()
        offer_response = self.client.post(
            reverse("public_membership_offer", args=[c["token"]]), data
        )
        data.update(reviewed=offer_response.json()["fingerprint"], accepted="on")
        setup_key = uuid.uuid4()
        payload = dict(
            purchase=data,
            setup_key=str(setup_key),
            nonce="nonce-Synthetic",
            expiry_month=12,
            expiry_year=2035,
            retention_choice="no",
        )
        endpoint = reverse("public_membership_card", args=[c["token"]])
        with patch("core.payments.setup.Gateway") as gateway:
            gateway.return_value.create_customer.side_effect = ProviderFailure()
            for _ in range(2):
                response = self.client.post(
                    endpoint, json.dumps(payload), content_type="application/json"
                )
                self.assertEqual(response.status_code, 202, response.content)
            gateway.return_value.create_customer.assert_called_once()
        status = reverse("public_membership_card_status", args=[c["token"], setup_key])
        self.assertContains(self.client.get(url), status)
        self.assertEqual(self.client.get(status).status_code, 202)
        self.assertEqual(Client().get(status).status_code, 404)
        self.assertFalse(MembershipPublicAcceptance.objects.exists())

    def test_declined_renewal_receipt_claims_no_funds_and_does_not_offer_another_purchase(self):
        c, url, data = self.prepare()
        result = self.client.post(url, data)
        member = MembershipPublicAcceptance.objects.get().purchase
        op = member.installments.first().invoice.sale.operations.get()
        record_result(
            operation_id=op.pk, state="declined", source="provider", provider_reference="8002"
        )
        receipt = self.client.get(result.url)
        self.assertContains(receipt, "payment was declined")
        self.assertContains(receipt, "$0.00")
        self.assertNotContains(receipt, "data-membership-purchase")
        self.assertEqual(self.client.post(url, data).url, result.url)
        self.assertEqual(member.installments.first().invoice.sale.operations.count(), 1)
