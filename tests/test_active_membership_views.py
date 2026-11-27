"""Purchase screens share one explicit submit and never collect on preview."""

import uuid

from django.test import Client, TestCase, override_settings

from core.membership_records import MembershipPurchase
from core.models import FinancialSale, PaymentOperation
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
)
class ActiveMembershipViewTests(TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy
    succeed = fixtures.MembershipPurchaseTests.succeed

    def post_data(self, **changes):
        return (
            dict(
                customer=self.customer.pk,
                kind="subscription",
                places=2,
                months=3,
                billing="monthly",
                starts_on="2027-10-31",
                expected_method="card",
                request_key=str(uuid.uuid4()),
            )
            | changes
        )

    def test_offer_returns_price_terms_and_owned_cards_without_writes(self):
        self.client.force_login(self.staff)
        result = self.client.post("/staff/memberships/offer/", self.post_data())
        self.assertEqual(result.status_code, 200, result.content)
        self.assertIn("$37.06", result.json()["html"])
        self.assertIn("two free ordinary child visits", result.json()["terms"])
        self.assertEqual(result.json()["cards"][0]["id"], str(self.method.pk))
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(FinancialSale.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_one_confirm_returns_pending_overview_and_duplicate_submit_reuses_purchase(self):
        self.client.force_login(self.staff)
        data = self.post_data()
        data.update(
            reviewed=self.client.post("/staff/memberships/offer/", data).json()["fingerprint"],
            action="confirm",
            accepted="on",
            method=str(self.method.pk),
        )
        first = self.client.post("/staff/memberships/purchase/", data)
        self.assertEqual(first.status_code, 302, first.content)
        self.assertContains(self.client.get(first.url), "Benefits are pending")
        self.assertEqual(self.client.post("/staff/memberships/purchase/", data).url, first.url)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertContains(self.client.get("/staff/memberships/purchased/"), "Pending")
        member = MembershipPurchase.objects.get()
        self.succeed(member)
        overview = self.client.get(first.url)
        self.assertContains(overview, "Total money received")
        self.assertContains(overview, "$37.06")
        self.assertContains(overview, "Active")
        self.assertContains(overview, "No automatic renewal")
        self.assertRedirects(self.client.get(f"/staff/memberships/{member.pk}/edit/"), first.url)
        self.assertNotContains(
            self.client.get("/staff/memberships/"), f"#{member.membership_number}"
        )

    def test_page_requires_accepted_terms_and_stale_total_is_reviewed_on_same_page(self):
        self.client.force_login(self.staff)
        data = self.post_data(action="confirm", reviewed="old", method=str(self.method.pk))
        result = self.client.post("/staff/memberships/purchase/", data)
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Review and accept the membership terms")
        self.assertFalse(MembershipPurchase.objects.exists())
        data.update(accepted="on")
        result = self.client.post("/staff/memberships/purchase/", data)
        self.assertContains(result, "The membership or price changed")
        self.assertContains(result, "Membership payment details")

    def test_permissions_feature_gate_csrf_and_preview_is_post_only(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/staff/memberships/offer/").status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)
        self.assertEqual(
            csrf_client.post("/staff/memberships/purchase/", self.post_data()).status_code, 403
        )
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertEqual(self.client.get("/staff/memberships/purchased/").status_code, 404)
        self.staff.groups.clear()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/staff/memberships/purchase/").status_code, 403)

    def test_backend_form_owner_exceptions_are_not_available_to_staff(self):
        self.client.force_login(self.staff)
        result = self.client.post(
            "/staff/memberships/offer/",
            self.post_data(months=1, comped="on", minimum_override="on"),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("greater than or equal to 3", result.json()["error"])
        self.assertNotContains(self.client.get("/staff/memberships/purchase/"), "Owner exceptions")

    def test_rendered_purchase_has_customer_search_and_no_second_stage(self):
        self.client.force_login(self.staff)
        response = self.client.get(f"/staff/memberships/purchase/?customer={self.customer.pk}")
        self.assertContains(response, "Search customer by name or phone")
        self.assertContains(response, "Confirm membership purchase")
        self.assertContains(response, "data-membership-offer")
        self.assertContains(response, "data-membership-terms")
        self.assertContains(response, "membership-purchase.js")
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_customer_and_payment_pages_link_to_purchased_membership(self):
        member = self.buy()
        self.succeed(member)
        self.client.force_login(self.staff)
        page = self.client.get(f"/staff/customers/{self.customer.pk}/")
        self.assertContains(page, f"#{member.membership_number}")
        self.assertContains(page, "Active")
        self.assertNotContains(page, "Test drafts only")
        op = member.installments.first().invoice.sale.operations.get()
        payment = self.client.get(f"/staff/payments/{op.pk}/")
        self.assertContains(payment, f"#{member.membership_number}")
        self.assertContains(payment, "Installment 1")
