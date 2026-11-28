"""Same-page combined renewal review remains read-only until explicit receipt."""

import uuid

from django.test import TestCase, override_settings
from django.urls import reverse

from core.membership_batch_records import MembershipRenewalBatch
from core.models import PaymentOperation
from tests import test_membership_batch_renewals as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS


@override_settings(**SETTINGS)
class CombinedRenewalViewTests(TestCase):
    setUp = fixtures.CombinedRenewalTests.setUp
    buy = fixtures.CombinedRenewalTests.buy
    prior = fixtures.CombinedRenewalTests.prior
    family = fixtures.CombinedRenewalTests.family

    def prepare(self):
        self.family()
        verified_owner_login(self.client, self.owner)
        self.url = reverse("membership_renewals", args=[self.customer.pk])
        data = {
            "renewals-TOTAL_FORMS": "2",
            "renewals-INITIAL_FORMS": "2",
            "renewals-MIN_NUM_FORMS": "0",
            "renewals-MAX_NUM_FORMS": "100",
            "request_key": str(uuid.uuid4()),
            "tender": "cash",
            "action": "review",
        }
        for i, row in enumerate(self.rows):
            data.update(
                {
                    f"renewals-{i}-{key}": str(value)
                    for key, value in (
                        row
                        | dict(
                            kind="subscription" if i == 0 else "unlimited", renew="on", method_id=""
                        )
                    ).items()
                }
            )
        return data

    def test_customer_navigation_and_get_show_both_terms_with_no_financial_write(self):
        self.prepare()
        before = PaymentOperation.objects.count()
        page = self.client.get(self.url)
        self.assertContains(page, "Renew memberships")
        self.assertContains(page, "Current term ends", count=2)
        self.assertContains(page, "Renewal begins", count=2)
        self.assertContains(page, "Split places between types or terms")
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertFalse(MembershipRenewalBatch.objects.exists())
        self.assertContains(
            self.client.get(reverse("customer_detail", args=[self.customer.pk])),
            "Renew memberships together",
        )

    def test_live_preview_returns_combined_total_and_creates_nothing(self):
        data = self.prepare()
        before = PaymentOperation.objects.count()
        reply = self.client.post(self.url, data | {"format": "json"})
        self.assertEqual(reply.status_code, 200, reply.content)
        self.assertIn("$57.98", reply.json()["html"])
        self.assertIn("$57.98", reply.json()["button"])
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertFalse(MembershipRenewalBatch.objects.exists())

    def test_final_receipt_redirects_to_same_page_with_each_record_and_no_resubmit_form(self):
        data = self.prepare()
        reviewed = self.client.post(self.url, data | {"format": "json"}).json()["fingerprint"]
        response = self.client.post(
            self.url,
            data | dict(action="confirm", reviewed=reviewed, accepted="on", verified_received="on"),
        )
        self.assertEqual(response.status_code, 302)
        page = self.client.get(response.url)
        self.assertContains(page, "Renewals recorded")
        self.assertContains(page, "Payment received: $57.98")
        self.assertContains(page, "One confirmation email was prepared")
        self.assertNotContains(page, "data-renewal-batch")
        self.assertEqual(MembershipRenewalBatch.objects.count(), 1)
        second = MembershipRenewalBatch.objects.get().parts.order_by("position").last().purchase
        detail = self.client.get(reverse("membership_overview", args=[second.pk]))
        self.assertContains(detail, "Shared confirmation email")
        self.assertContains(detail, "Queued")
        self.assertNotContains(detail, "Will be queued when the first payment is confirmed")

    def test_server_requires_receipt_verification_after_read_only_review(self):
        data = self.prepare()
        reviewed = self.client.post(self.url, data | {"format": "json"}).json()["fingerprint"]
        page = self.client.post(
            self.url, data | dict(action="confirm", reviewed=reviewed, accepted="on")
        )
        self.assertContains(page, "confirm the full payment was actually received")
        self.assertFalse(MembershipRenewalBatch.objects.exists())

    def test_unselected_row_with_obsolete_card_does_not_block_other_renewal(self):
        data = self.prepare()
        data.pop("renewals-1-renew")
        data["renewals-1-method_id"] = str(uuid.uuid4())
        reply = self.client.post(self.url, data | {"format": "json"})
        self.assertEqual(reply.status_code, 200, reply.content)
        self.assertIn("$17.99", reply.json()["button"])

    def test_paid_in_full_selection_does_not_bind_a_hidden_future_card(self):
        data = self.prepare()
        data["renewals-0-method_id"] = str(self.method.pk)
        reply = self.client.post(self.url, data | {"format": "json"})
        self.assertEqual(reply.status_code, 200, reply.content)

    def test_no_script_review_requires_acceptance_of_current_review_again(self):
        data = self.prepare()
        page = self.client.post(self.url, data | dict(accepted="on", verified_received="on"))
        self.assertEqual(page.status_code, 200)
        self.assertFalse(page.context["checkout"]["accepted"].value())
        self.assertFalse(page.context["checkout"]["verified_received"].value())

    def test_feature_off_does_not_expose_combined_checkout(self):
        self.family()
        verified_owner_login(self.client, self.owner)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertEqual(
                self.client.get(
                    reverse("membership_renewals", args=[self.customer.pk])
                ).status_code,
                404,
            )

    def test_read_only_staff_can_open_recorded_history_even_when_new_sales_are_paused(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission

        data = self.prepare()
        reviewed = self.client.post(self.url, data | {"format": "json"}).json()["fingerprint"]
        saved = self.client.post(
            self.url,
            data | dict(action="confirm", reviewed=reviewed, accepted="on", verified_received="on"),
        )
        reader = get_user_model().objects.create_user(username="renewal_reader", is_staff=True)
        reader.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core",
                codename__in=["view_customer", "view_membershippurchase"],
            )
        )
        self.client.force_login(reader)
        self.assertContains(self.client.get(saved.url), "Payment received: $57.98")
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertContains(self.client.get(saved.url), "Payment received: $57.98")
            self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(MembershipRenewalBatch.objects.count(), 1)
