import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.customer_credit import balance
from core.customer_credit_records import CustomerCreditCorrection
from tests import test_customer_credit_corrections as fixtures
from tests.helpers import verified_owner_login
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
class CreditCorrectionViewTests(fixtures.CreditFixtures, TestCase):
    def open(self):
        self.conversion(card=True)
        verified_owner_login(self.client, self.owner)
        return reverse("customer_detail", args=[self.customer.pk])

    def test_live_preview_confirmation_replay_and_audit_on_same_page(self):
        url = self.open()
        page = self.client.get(url)
        self.assertContains(page, "Owner: correct unused credit")
        self.assertContains(page, "customer-credit-correction.js")
        data = dict(
            action="credit_correction_preview",
            kind="remove",
            value="5.00",
            reason="Corrected duplicate allowance.",
            request_key=str(page.context["correction_form"]["request_key"].value()),
        )
        preview = self.client.post(url, data)
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertIn("$11.02", preview.json()["html"])
        self.assertFalse(CustomerCreditCorrection.objects.exists())
        data.update(action="credit_correction_confirm", reviewed=preview.json()["fingerprint"])
        self.assertRedirects(self.client.post(url, data), url)
        self.assertRedirects(self.client.post(url, data), url)
        self.assertEqual(CustomerCreditCorrection.objects.count(), 1)
        page = self.client.get(url)
        self.assertContains(page, "Available: $11.02")
        self.assertContains(page, "Corrected duplicate allowance.")
        history = self.client.get(reverse("customer_history", args=[self.customer.pk]))
        self.assertContains(history, "Customer credit removed")
        self.assertContains(history, "Corrected duplicate allowance.")
        self.assertContains(history, "Available afterward")
        viewer = get_user_model().objects.create_user(
            username="credit-history-viewer", is_staff=True
        )
        viewer.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core",
                codename__in=["view_customer", "view_customer_history"],
            )
        )
        self.client.force_login(viewer)
        self.assertNotContains(
            self.client.get(reverse("customer_history", args=[self.customer.pk])),
            "Corrected duplicate allowance.",
        )

    def test_native_changed_amount_requires_review_before_explicit_confirmation(self):
        url = self.open()
        data = dict(
            action="credit_correction_confirm",
            kind="remove",
            value="5.00",
            reason="Reviewed.",
            request_key=str(uuid.uuid4()),
            reviewed="",
        )
        changed = self.client.post(url, data)
        self.assertContains(changed, "Review the current correction again")
        self.assertFalse(CustomerCreditCorrection.objects.exists())
        data["reviewed"] = changed.context["correction_form"]["reviewed"].value()
        self.assertRedirects(self.client.post(url, data), url)
        self.assertEqual(balance(self.customer.pk), Decimal("11.02"))

    def test_restore_replay_after_the_removal_has_been_fully_restored(self):
        url = self.open()
        removed = self.correction("5.00")
        data = dict(
            action="credit_correction_preview",
            kind="restore",
            original=str(removed.pk),
            value="5.00",
            reason="Restoring the earlier removal.",
            request_key=str(uuid.uuid4()),
        )
        preview = self.client.post(url, data)
        self.assertEqual(preview.status_code, 200, preview.content)
        data.update(action="credit_correction_confirm", reviewed=preview.json()["fingerprint"])
        self.assertRedirects(self.client.post(url, data), url)
        self.assertRedirects(self.client.post(url, data), url)
        self.assertEqual(balance(self.customer.pk), Decimal("16.02"))
        self.assertEqual(CustomerCreditCorrection.objects.filter(kind="restore").count(), 1)

    def test_staff_csrf_invalid_input_and_disabled_feature_cannot_mutate(self):
        url = self.open()
        data = dict(
            action="credit_correction_confirm",
            kind="restore",
            value="5.00",
            reason="Reviewed.",
            request_key=str(uuid.uuid4()),
            original=str(uuid.uuid4()),
            reviewed="forged",
        )
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertFalse(CustomerCreditCorrection.objects.exists())
        csrf = Client(enforce_csrf_checks=True)
        verified_owner_login(csrf, self.owner)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.assertNotContains(self.client.get(url), "Owner: correct unused credit")
        verified_owner_login(self.client, self.owner)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertNotContains(self.client.get(url), "Owner: correct unused credit")
            self.assertEqual(self.client.post(url, data).status_code, 403)
        self.assertEqual(self.client.post(url, {"action": "unknown"}).status_code, 405)
        self.assertEqual(balance(self.customer.pk), Decimal("16.02"))
