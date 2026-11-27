import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.membership_card_setup import choose_saved, make_flow
from core.membership_public_authority import create_link
from core.membership_records import MembershipPurchase
from core.membership_sales import offer, purchase
from core.models import FinancialPosting, PaymentOperation
from tests import test_public_membership_views as public_fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures


@override_settings(**SETTINGS)
class InitialCreditViewTests(InitialCreditFixtures, TestCase):
    def payload(self, **changes):
        values = self.values(**changes)
        values.pop("actor")
        values["customer"] = self.customer.pk
        values["request_key"] = str(uuid.uuid4())
        return values

    def test_staff_preview_and_confirm_show_only_remaining_cash_as_money_received(self):
        _, _, prior, _ = self.conversion()
        self.client.force_login(self.staff)
        data = self.payload(credit="15.99", expected_method="cash")
        response = self.client.post(reverse("membership_offer"), data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["payment_due_today"], "2.00")
        self.assertEqual(response.json()["credit_available"], "15.99")
        self.assertIn("Customer credit applied", response.json()["html"])
        data.update(
            action="confirm",
            accepted="on",
            verified_received="on",
            method=str(prior.billing_state.mandate.method_id),
            reviewed=response.json()["fingerprint"],
        )
        result = self.client.post(reverse("membership_purchase"), data)
        self.assertEqual(result.status_code, 302, result.content)
        page = self.client.get(result["Location"])
        self.assertContains(page, "Customer credit applied")
        self.assertEqual(page.context["money_received"], 2)
        self.assertEqual(page.context["credit_applied"], Decimal("15.99"))

    def test_prepaid_full_credit_preview_needs_neither_card_nor_receipt_checkbox(self):
        self.conversion(children=5, adults=2)
        self.client.force_login(self.staff)
        data = self.payload(credit="53.97", billing="prepaid")
        preview = self.client.post(reverse("membership_offer"), data)
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertFalse(preview.json()["needs_card"])
        self.assertEqual(preview.json()["payment_due_today"], "0.00")
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        data.update(action="confirm", accepted="on", reviewed=preview.json()["fingerprint"])
        response = self.client.post(reverse("membership_purchase"), data)
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(
            (PaymentOperation.objects.count(), FinancialPosting.objects.count()), before
        )

    def test_changed_credit_requires_current_card_authorization(self):
        _, _, prior, _ = self.conversion(card=True)
        key = uuid.uuid4()
        old = self.values(credit="5.00")
        method = prior.billing_state.mandate.method
        flow = make_flow(
            actor=self.staff, customer=self.customer, request_key=key, offer=offer(**old)
        )
        with patch("core.membership_card_setup.Gateway") as gateway:
            gateway.return_value.method.return_value = dict(
                id=int(method.provider_method),
                customer_id=12,
                payment_method_type="card",
                card_type="Visa",
                last4=method.last_four,
                expiry_month=12,
                expiry_year=2035,
            )
            authority = choose_saved(
                actor=self.staff, flow=flow, method_id=method.pk, accepted=True
            )
            gateway.return_value.charge.assert_not_called()
        changed = self.values(credit="10.00")
        before = MembershipPurchase.objects.count(), PaymentOperation.objects.count()
        with self.assertRaises(ValidationError):
            purchase(
                **changed,
                request_key=key,
                reviewed=offer(**changed)["fingerprint"],
                accepted=True,
                method_id=method.pk,
                card_authorization_id=authority.pk,
            )
        self.assertEqual(
            (MembershipPurchase.objects.count(), PaymentOperation.objects.count()), before
        )

    def test_private_renewal_rejects_unscoped_credit_including_malformed_json(self):
        _, _, prior, _ = self.conversion(card=True)
        _, token = create_link(actor=self.staff, prior=prior, request_key=uuid.uuid4())
        _, url, data = public_fixtures.PublicMembershipViewTests.start(
            self, dict(token=token, prior=prior)
        )
        page = self.client.get(url)
        self.assertNotContains(page, 'name="credit_amount"')
        for value in ("5.00", dict(amount="5.00")):
            # Form and nested card JSON use the same strict renewal form.
            if isinstance(value, str):
                response = self.client.post(
                    reverse("public_membership_offer", args=[token]),
                    data | dict(credit_amount=value),
                )
            else:
                response = self.client.post(
                    reverse("public_membership_card", args=[token]),
                    dict(purchase=data | dict(credit_amount=value), method="new"),
                    content_type="application/json",
                )
            self.assertEqual(response.status_code, 400, response.content)

    def test_native_amount_change_renders_a_fresh_review_and_csrf_still_applies(self):
        self.conversion(card=True)
        self.client.force_login(self.staff)
        data = self.payload(credit="5.00")
        preview = self.client.post(reverse("membership_offer"), data)
        data.update(
            action="confirm",
            accepted="on",
            credit_amount="10.00",
            reviewed=preview.json()["fingerprint"],
        )
        before = MembershipPurchase.objects.count()
        response = self.client.post(reverse("membership_purchase"), data)
        self.assertContains(response, "Review the current total")
        self.assertEqual(MembershipPurchase.objects.count(), before)
        csrf = Client(enforce_csrf_checks=True)
        csrf.cookies = self.client.cookies
        self.assertEqual(csrf.post(reverse("membership_purchase"), data).status_code, 403)
