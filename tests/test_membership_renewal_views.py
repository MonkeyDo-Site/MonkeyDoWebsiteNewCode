"""Follow-on membership screens keep the source, dates and payment together."""

import uuid

from django.test import TestCase, override_settings

from core.communications.models import MessageDelivery
from core.membership_records import MembershipOrigin
from core.models import FinancialSale
from tests import test_membership_renewals as fixtures
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
class MembershipRenewalViewTests(TestCase):
    setUp = fixtures.MembershipRenewalTests.setUp
    buy = fixtures.MembershipRenewalTests.buy
    prior = fixtures.MembershipRenewalTests.prior
    follow_values = fixtures.MembershipRenewalTests.follow_values

    def payload(self, prior, **changes):
        data = self.follow_values(prior, **changes)
        data.pop("actor")
        data["customer"] = data["customer"].pk
        data["request_key"] = str(uuid.uuid4())
        return data

    def test_qualified_renewal_form_and_one_confirmation_use_fixed_dates_and_current_price(self):
        prior = self.prior()
        self.client.force_login(self.staff)
        url = f"/staff/memberships/purchased/{prior.pk}/renew/"
        page = self.client.get(url)
        self.assertContains(page, "Renew membership")
        self.assertEqual(page.context["form"]["months"].value(), 1)
        self.assertEqual(str(page.context["form"]["starts_on"].value()), "2028-01-31")
        self.assertTrue(page.context["form"].fields["starts_on"].disabled)
        data = self.payload(prior, kind="unlimited")
        response = self.client.post("/staff/memberships/offer/", data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["minimum_months"], 1)
        data.update(
            reviewed=response.json()["fingerprint"],
            accepted="on",
            verified_received="on",
            action="confirm",
        )
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, response.content)
        origin = MembershipOrigin.objects.get()
        self.assertEqual(origin.prior_id, prior.pk)
        self.assertEqual(origin.purchase.membership.kind, "unlimited")
        self.assertEqual(origin.purchase.membership.starts_on.isoformat(), "2028-01-31")
        overview = self.client.get(response.url)
        self.assertContains(overview, "Renewal of")
        self.assertContains(overview, f"#{prior.membership_number}")
        email = MessageDelivery.objects.get(membership=origin.purchase)
        self.assertEqual(email.kind, "membership_renewal")
        self.assertEqual(email.subject, "Your Monkey Do membership is renewed!")
        self.assertIn("changing from Subscription to Unlimited", email.text_body)
        self.assertIn("$39.99", email.text_body)
        self.assertNotIn(f"#{prior.membership_number}", email.text_body)

    def test_addition_has_its_own_minimum_and_confirmation_keeps_original_memberships(self):
        prior = self.prior()
        self.client.force_login(self.staff)
        url = f"/staff/memberships/purchased/{prior.pk}/add/"
        page = self.client.get(url)
        self.assertContains(page, "Add membership places")
        self.assertEqual(page.context["form"].fields["months"].min_value, 3)
        self.assertFalse(page.context["form"].fields["starts_on"].disabled)
        data = self.payload(prior, operation="addition", months=3, places=4)
        response = self.client.post("/staff/memberships/offer/", data)
        self.assertEqual(response.status_code, 200, response.content)
        data.update(
            reviewed=response.json()["fingerprint"],
            accepted="on",
            verified_received="on",
            action="confirm",
        )
        result = self.client.post(url, data)
        self.assertEqual(result.status_code, 302, result.content)
        added = MembershipOrigin.objects.get().purchase
        self.assertEqual(added.membership.places, 4)
        self.assertEqual(added.membership.months, 3)
        self.assertEqual(MessageDelivery.objects.get(membership=added).kind, "membership_addition")
        self.assertIn(
            "existing memberships keep their own dates and benefits",
            MessageDelivery.objects.get(membership=added).text_body,
        )
        self.assertEqual(prior.membership.places, 2)

    def test_path_membership_cannot_be_changed_by_posting_another_source(self):
        first = self.prior()
        second = self.prior(places=1)
        self.client.force_login(self.staff)
        data = self.payload(second)
        reviewed = self.client.post("/staff/memberships/offer/", data).json()["fingerprint"]
        data.update(reviewed=reviewed, accepted="on", verified_received="on", action="confirm")
        before = FinancialSale.objects.count()
        result = self.client.post(f"/staff/memberships/purchased/{first.pk}/renew/", data)
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "membership or price changed")
        self.assertEqual(FinancialSale.objects.count(), before)
        self.assertFalse(MembershipOrigin.objects.exists())

    def test_unaccepted_terms_do_not_create_an_addition_or_another_receipt(self):
        prior = self.prior()
        self.client.force_login(self.staff)
        data = self.payload(prior, operation="addition", months=3)
        data.update(
            reviewed=self.client.post("/staff/memberships/offer/", data).json()["fingerprint"],
            action="confirm",
            verified_received="on",
        )
        before = FinancialSale.objects.count()
        result = self.client.post(f"/staff/memberships/purchased/{prior.pk}/add/", data)
        self.assertContains(result, "Review and accept the membership terms")
        self.assertEqual(FinancialSale.objects.count(), before)
        self.assertFalse(MembershipOrigin.objects.exists())
