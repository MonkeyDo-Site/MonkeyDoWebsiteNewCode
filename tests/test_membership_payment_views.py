"""Installment review, collection and card replacement stay on the overview."""

import uuid

from django.test import Client, TestCase, override_settings

from core.models import FinancialPosting, PaymentOperation
from tests import test_membership_payments as fixtures
from tests.test_owner_accounts import STORAGES


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
)
class MembershipPaymentViewTests(TestCase):
    setUp = fixtures.MembershipPaymentTests.setUp
    buy = fixtures.MembershipPaymentTests.buy
    failed = fixtures.MembershipPaymentTests.failed
    new_card = fixtures.MembershipPaymentTests.new_card

    def payload(self, item, **values):
        return dict(installment=item.pk, tender="card", request_key=str(uuid.uuid4())) | values

    def test_preview_and_confirm_one_cash_receipt_from_same_overview(self):
        member, item = self.failed()
        self.client.force_login(self.staff)
        url = f"/staff/memberships/purchased/{member.pk}/"
        self.assertContains(self.client.get(url), "Resolve payment or update membership card")
        data = self.payload(item, tender="cash", action="payment_preview")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total"], "35.98")
        self.assertFalse(FinancialPosting.objects.exists())
        data.update(
            action="payment_confirm",
            reviewed=response.json()["fingerprint"],
            verified_received="on",
        )
        result = self.client.post(url, data)
        self.assertRedirects(result, url)
        self.assertContains(self.client.get(url), "$35.98")
        self.assertEqual(FinancialPosting.objects.count(), 1)
        self.assertRedirects(self.client.post(url, data), url)
        self.assertEqual(FinancialPosting.objects.count(), 1)

    def test_unknown_outcome_has_no_new_collection_and_keeps_payment_link(self):
        member = self.buy()
        item = member.installments.first()
        self.client.force_login(self.staff)
        url = f"/staff/memberships/purchased/{member.pk}/"
        response = self.client.post(url, self.payload(item, action="payment_preview"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("existing payment outcome", response.json()["error"])
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertContains(
            self.client.get(url), f"/staff/payments/{item.invoice.sale.operations.get().pk}/"
        )

    def test_card_update_keeps_existing_payment_and_records_accepted_new_source(self):
        member, item = self.failed()
        card = self.new_card()
        self.client.force_login(self.staff)
        url = f"/staff/memberships/purchased/{member.pk}/"
        result = self.client.post(
            url,
            dict(
                action="card_update",
                method=str(card.pk),
                revision=1,
                request_key=str(uuid.uuid4()),
                accepted="on",
            ),
        )
        self.assertRedirects(result, url)
        member.billing_state.refresh_from_db()
        self.assertEqual(member.billing_state.mandate.method_id, card.pk)
        self.assertEqual(item.invoice.sale.operations.get().method_id, self.method.pk)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_paid_first_payment_only_shows_future_date_and_no_due_installment_form(self):
        member = self.buy(expected_method="cash", verified_received=True)
        self.client.force_login(self.staff)
        response = self.client.get(f"/staff/memberships/purchased/{member.pk}/")
        self.assertContains(response, "No installment is due today")
        self.assertNotContains(response, "data-installment-payment")
        self.assertContains(response, "Save and use membership card")

    def test_billing_post_obeys_csrf_feature_and_collection_permissions(self):
        member, item = self.failed()
        url = f"/staff/memberships/purchased/{member.pk}/"
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(
            client.post(url, self.payload(item, action="payment_preview")).status_code, 403
        )
        self.client.force_login(self.staff)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertEqual(self.client.post(url, self.payload(item)).status_code, 404)
        self.staff.groups.clear()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(url, self.payload(item)).status_code, 403)
