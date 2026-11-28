"""Expired purchase proof can select a receipt, never authorize another payment."""

import copy
import json
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core import membership_receipt_access as access
from core.membership_public_authority import verified_scope
from core.models import (
    AuditEvent,
    Customer,
    MembershipCardAuthorization,
    MembershipPublicCheckout,
    MembershipPurchase,
    PaymentOperation,
)
from core.public_membership_views import INITIAL_SESSION_KEY
from core.public_membership_views import SESSION_KEY as PURCHASE_KEY
from tests import test_public_membership_join as initial
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
class PublicMembershipReceiptTests(TestCase):
    setUp = initial.PublicMembershipJoinTests.setUp
    url = initial.PublicMembershipJoinTests.url
    post_identity = initial.PublicMembershipJoinTests.post_identity
    start = initial.PublicMembershipJoinTests.start
    prepare = initial.PublicMembershipJoinTests.prepare

    def accepted(self):
        data = self.prepare()
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        member = MembershipPurchase.objects.get()
        source = member.public_acceptance.checkout
        return member, source, data

    def post_verify(self, data):
        flow = self.client.session[access.SESSION_KEY]["flow"]
        return self.client.post(
            reverse("public_membership_receipt_verify"),
            data | dict(wizard_key=flow["key"], wizard_stage=flow["stage"]),
        )

    def verify(self, *, phone=None, name=None):
        response = self.client.get(reverse("public_membership_receipt_verify"))
        self.assertEqual(response.status_code, 200, response.content)
        return self.post_verify(
            dict(phone=phone or self.customer.phone, last_name=name or self.customer.last_name)
        )

    def test_fresh_verification_reads_same_receipt_without_extending_any_financial_deadline(self):
        member, source, data = self.accepted()
        old_card_expiry = MembershipCardAuthorization.objects.get().expires_at
        old_source_expiry = source.expires_at
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            response = self.client.get(reverse("public_membership_join_receipt"))
            self.assertRedirects(
                response, reverse("public_membership_receipt_verify"), fetch_redirect_response=False
            )
            page = self.client.get(reverse("public_membership_receipt_verify"))
            self.assertNotContains(page, self.customer.email)
            self.assertNotContains(page, "Subscription")
            self.assertNotContains(page, "Have you visited")
            self.assertEqual(self.verify().status_code, 302)
            page = self.client.get(reverse("public_membership_join_receipt"))
            self.assertContains(
                page, "Receipt for your existing membership. No new payment was requested."
            )
            self.assertContains(page, "Your membership is not confirmed yet")
            self.assertContains(page, "$0.00")
            self.assertEqual(
                self.client.post(
                    reverse("public_membership_join_card"),
                    json.dumps(dict(purchase=data, method=str(self.method.pk))),
                    content_type="application/json",
                ).status_code,
                400,
            )
        source.refresh_from_db()
        self.assertEqual(source.expires_at, old_source_expiry)
        self.assertEqual(MembershipCardAuthorization.objects.get().expires_at, old_card_expiry)
        self.assertEqual(MembershipPublicCheckout.objects.count(), 1)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(action="membership.public_receipt_verified").count(), 1
        )

    def test_read_proof_cannot_be_used_as_purchase_authority(self):
        member, _, _ = self.accepted()
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            self.verify()
            proof = self.client.session[access.SESSION_KEY]["proof"]
            with self.assertRaises(PermissionDenied):
                verified_scope(proof)
            session = self.client.session
            session[PURCHASE_KEY][str(member.request_key)]["proof"] = proof
            session.save()
            self.assertEqual(
                self.client.post(reverse("public_membership_join_offer"), {}).status_code, 400
            )
            self.assertEqual(
                self.client.get(reverse("public_membership_receipt_verify")).status_code, 404
            )
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_another_verified_customer_cannot_read_original_purchase(self):
        self.accepted()
        other = Customer.objects.create(
            last_name=self.customer.last_name, phone="2025550183", email="other@example.invalid"
        )
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            response = self.verify(phone=other.phone, name=other.last_name)
            self.assertContains(response, "identify the customer", status_code=400)
            self.assertNotIn("proof", self.client.session[access.SESSION_KEY])
            self.assertEqual(
                self.client.get(reverse("public_membership_join_receipt")).status_code, 302
            )
        self.assertEqual(Customer.objects.count(), 2)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_email_verifies_the_same_customer_on_one_form(self):
        self.accepted()
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            self.client.get(reverse("public_membership_receipt_verify"))
            response = self.post_verify(
                dict(phone=self.customer.phone, email=self.customer.email.upper())
            )
            self.assertRedirects(
                response, reverse("public_membership_join_receipt"), fetch_redirect_response=False
            )
            self.assertContains(
                self.client.get(reverse("public_membership_join_receipt")),
                "No new payment was requested",
            )
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_previous_phone_keeps_explicit_current_number_confirmation(self):
        self.accepted()
        old_phone = self.customer.phone
        self.customer.previous_phone = old_phone
        self.customer.phone = "2025550183"
        self.customer.revision += 1
        self.customer.save()
        self.client.get(reverse("public_membership_receipt_verify"))
        self.post_verify(dict(phone=old_phone, last_name=self.customer.last_name))
        self.assertEqual(self.client.session[access.SESSION_KEY]["flow"]["stage"], "previous")
        self.assertNotIn("proof", self.client.session[access.SESSION_KEY])
        response = self.post_verify(dict(confirm_phone="yes"))
        self.assertRedirects(
            response, reverse("public_membership_join_receipt"), fetch_redirect_response=False
        )
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_new_contact_choices_never_create_a_customer_or_new_checkout(self):
        self.accepted()
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            self.client.get(reverse("public_membership_receipt_verify"))
            self.post_verify(dict(phone="2025550191", last_name="New"))
            page = self.client.get(reverse("public_membership_receipt_verify"))
            self.assertNotContains(page, "Continue as a new customer")
            self.assertContains(
                self.post_verify(dict(continue_new="1")),
                "existing customer profile",
                status_code=400,
            )
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(MembershipPublicCheckout.objects.count(), 1)

    def test_current_contact_changes_require_fresh_read_identity_without_rewriting_original_evidence(
        self,
    ):
        _, source, _ = self.accepted()
        old_revision = source.customer_revision
        self.customer.phone = "2025550183"
        self.customer.email = ""
        self.customer.revision += 1
        self.customer.save()
        self.assertEqual(self.verify(phone=self.customer.phone).status_code, 302)
        page = self.client.get(reverse("public_membership_join_receipt"))
        self.assertContains(page, "No new payment was requested")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "")
        source.refresh_from_db()
        self.assertEqual(source.customer_revision, old_revision)
        self.assertEqual(Customer.objects.count(), 1)

    def test_copied_read_state_without_original_private_purchase_is_unavailable(self):
        self.accepted()
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            self.verify()
            other = Client()
            session = other.session
            session[access.SESSION_KEY] = copy.deepcopy(self.client.session[access.SESSION_KEY])
            session[INITIAL_SESSION_KEY] = copy.deepcopy(self.client.session[INITIAL_SESSION_KEY])
            session.save()
            page = other.get(reverse("public_membership_receipt_verify"))
            self.assertEqual(page.status_code, 404)
            self.assertNotContains(page, self.customer.last_name, status_code=404)

    def test_read_expiry_repeats_verification_without_renewing_financial_source(self):
        _, source, _ = self.accepted()
        now = timezone.now()
        with patch("django.utils.timezone.now", return_value=now + timedelta(minutes=21)):
            self.verify()
            original_browser = self.client.session[access.SESSION_KEY]["browser"]
        with patch("django.utils.timezone.now", return_value=now + timedelta(minutes=42)):
            self.assertEqual(
                self.client.get(reverse("public_membership_join_receipt")).status_code, 302
            )
            self.assertEqual(
                self.client.get(reverse("public_membership_receipt_verify")).status_code, 200
            )
            self.assertNotEqual(
                self.client.session[access.SESSION_KEY]["browser"], original_browser
            )
            self.assertNotIn("proof", self.client.session[access.SESSION_KEY])
        source.refresh_from_db()
        self.assertEqual(source.expires_at, now + timedelta(minutes=20))

    def test_changed_profile_invalidates_a_read_grant_and_stale_tab_cannot_skip_matching(self):
        self.accepted()
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            self.client.get(reverse("public_membership_receipt_verify"))
            flow = copy.deepcopy(self.client.session[access.SESSION_KEY]["flow"])
            self.post_verify(dict(action="restart"))
            response = self.client.post(
                reverse("public_membership_receipt_verify"),
                dict(
                    wizard_key=flow["key"],
                    wizard_stage="phone",
                    phone=self.customer.phone,
                    last_name=self.customer.last_name,
                ),
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                self.post_verify(
                    dict(phone=self.customer.phone, last_name=self.customer.last_name)
                ).status_code,
                302,
            )
            self.customer.revision += 1
            self.customer.save()
            self.assertEqual(
                self.client.get(reverse("public_membership_join_receipt")).status_code, 302
            )
            self.assertEqual(
                self.client.get(reverse("public_membership_receipt_verify")).status_code, 200
            )
            self.assertNotIn("proof", self.client.session[access.SESSION_KEY])

    def test_no_accepted_purchase_cannot_create_a_receipt_grant_and_csrf_and_gates_apply(self):
        self.prepare()
        self.assertEqual(
            self.client.get(reverse("public_membership_receipt_verify")).status_code, 404
        )
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(
            strict.post(reverse("public_membership_receipt_verify"), {}).status_code, 403
        )
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertEqual(
                self.client.get(reverse("public_membership_receipt_verify")).status_code, 404
            )
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
