import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.customer_credit import balance
from core.customer_credit_records import CustomerCreditApplication
from tests import test_customer_credit as credit_fixtures
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
class CustomerCreditViewTests(TestCase):
    setUp = credit_fixtures.CustomerCreditTests.setUp
    flow = credit_fixtures.CustomerCreditTests.flow
    card = credit_fixtures.CustomerCreditTests.card
    save_card = credit_fixtures.CustomerCreditTests.save_card
    booking = credit_fixtures.CustomerCreditTests.booking
    arrival_inputs = credit_fixtures.CustomerCreditTests.arrival_inputs
    create = credit_fixtures.CustomerCreditTests.create
    gateway = credit_fixtures.CustomerCreditTests.gateway
    ready = credit_fixtures.CustomerCreditTests.ready
    member = credit_fixtures.CustomerCreditTests.member
    act = credit_fixtures.CustomerCreditTests.act
    paid_visit = credit_fixtures.CustomerCreditTests.paid_visit
    conversion = credit_fixtures.CustomerCreditTests.conversion

    def test_review_confirm_and_replay_keep_cash_and_credit_separate(self):
        _, _, member, _ = self.conversion(card=True)
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            verified_owner_login(self.client, self.owner)
            url = reverse("membership_overview", args=[member.pk])
            page = self.client.get(url)
            self.assertContains(page, "Customer credit available")
            form = page.context["credit_form"]
            data = dict(
                action="credit_preview",
                request_key=str(form["request_key"].value()),
                installment=str(form["installment"].value()),
                value="16.02",
            )
            preview = self.client.post(url, data)
            self.assertEqual(preview.status_code, 200, preview.content)
            self.assertFalse(CustomerCreditApplication.objects.exists())
            data.update(action="credit_confirm", reviewed=preview.json()["fingerprint"])
            self.assertRedirects(self.client.post(url, data), url)
            self.assertRedirects(self.client.post(url, data), url)
            self.assertEqual(CustomerCreditApplication.objects.count(), 1)
            page = self.client.get(url)
            self.assertEqual(page.context["credit_applied"], Decimal("16.02"))
            self.assertContains(page, "Customer credit applied")
            self.assertEqual(str(page.context["money_received"]), "17.99")
            self.assertContains(page, "$2.03")
            self.assertEqual(balance(member.customer_id), 0)

    def test_invalid_other_installment_and_csrf_do_not_spend_credit(self):
        _, _, member, _ = self.conversion()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            verified_owner_login(self.client, self.owner)
            url = reverse("membership_overview", args=[member.pk])
            data = dict(
                action="credit_confirm",
                request_key=str(uuid.uuid4()),
                installment="999999",
                value="15.99",
                reviewed="forged",
            )
            self.assertEqual(self.client.post(url, data).status_code, 200)
            csrf = Client(enforce_csrf_checks=True)
            verified_owner_login(csrf, self.owner)
            self.assertEqual(csrf.post(url, data).status_code, 403)
            self.assertEqual(balance(member.customer_id), Decimal("15.99"))
            self.assertFalse(CustomerCreditApplication.objects.exists())

    def test_native_changed_amount_is_reviewed_before_a_second_explicit_confirmation(self):
        _, _, member, _ = self.conversion(card=True)
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            verified_owner_login(self.client, self.owner)
            url = reverse("membership_overview", args=[member.pk])
            form = self.client.get(url).context["credit_form"]
            data = dict(
                action="credit_confirm",
                installment=str(form["installment"].value()),
                value="15.00",
                reviewed=form["reviewed"].value(),
                request_key=str(form["request_key"].value()),
            )
            changed = self.client.post(url, data)
            self.assertContains(changed, "The credit or payment changed")
            self.assertFalse(CustomerCreditApplication.objects.exists())
            data["reviewed"] = changed.context["credit_form"]["reviewed"].value()
            self.assertRedirects(self.client.post(url, data), url)
            self.assertEqual(balance(member.customer_id), Decimal("1.02"))
            self.assertEqual(CustomerCreditApplication.objects.get().amount, Decimal("15.00"))
