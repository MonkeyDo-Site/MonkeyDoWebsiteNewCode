"""Combined owner cancellation/refund controls retain exact payment truth."""

import uuid
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.membership_cancellations import notices
from core.membership_records import MembershipCancellation, MembershipRefundPlan
from core.models import FinancialLineAdjustment, PaymentOperation
from core.payments.gateway import ProviderFailure
from tests import test_membership_cancellations as fixtures
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
)
class MembershipCancellationViewTests(TestCase):
    setUp = fixtures.MembershipCancellationTests.setUp
    buy = fixtures.MembershipCancellationTests.buy
    succeed = fixtures.MembershipCancellationTests.succeed
    prepaid = fixtures.MembershipCancellationTests.prepaid

    def owner_page(self, member):
        verified_owner_login(self.client, self.owner)
        return self.client.get(reverse("membership_overview", args=[member.pk]))

    def payload(self, member, **changes):
        page = self.owner_page(member)
        return (
            dict(
                action="cancel_preview",
                timing="immediate",
                refund_amount="20.00",
                reason="Customer called; owner reviewed the funds.",
                early_override="on",
                send_confirmation="no",
                refund_action="due",
                request_key=str(page.context["cancel_form"]["request_key"].value()),
            )
            | changes
        )

    def reviewed(self, member, **changes):
        values = self.payload(member, **changes)
        result = self.client.post(reverse("membership_overview", args=[member.pk]), values)
        self.assertEqual(result.status_code, 200, result.content)
        return values | dict(action="cancel_confirm", reviewed=result.json()["fingerprint"])

    def test_owner_review_and_final_cancellation_stay_on_the_overview_and_replay_once(self):
        member = self.prepaid()
        values = self.reviewed(member)
        self.assertFalse(MembershipCancellation.objects.exists())
        url = reverse("membership_overview", args=[member.pk])
        self.assertRedirects(self.client.post(url, values), url)
        self.assertRedirects(self.client.post(url, values), url)
        self.assertEqual(MembershipCancellation.objects.count(), 1)
        self.assertEqual(MembershipRefundPlan.objects.count(), 1)
        self.assertContains(self.client.get(url), "Still due:")
        self.assertContains(self.client.get(url), "Record cash refund completed")
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())

    def test_manual_completion_clears_dashboard_refund_without_collecting_new_money(self):
        member = self.prepaid()
        values = self.reviewed(member)
        url = reverse("membership_overview", args=[member.pk])
        self.client.post(url, values)
        plan = MembershipRefundPlan.objects.get()
        dashboard = reverse("dashboard")
        self.assertContains(self.client.get(dashboard), "Membership refunds due")
        data = dict(
            action="refund_confirm",
            plan_id=str(plan.pk),
            request_key=str(uuid.uuid4()),
            manual_returned="on",
            reviewed_balance=str(plan.amount),
        )
        self.assertRedirects(self.client.post(url, data), url)
        self.assertRedirects(self.client.post(url, data), url)
        self.assertEqual(PaymentOperation.objects.filter(kind="refund").count(), 1)
        self.assertEqual(FinancialLineAdjustment.objects.count(), 1)
        self.assertFalse(notices()["refunds"])
        self.assertNotContains(self.client.get(dashboard), "Membership refunds due")
        self.assertContains(self.client.get(url), "Completed")

    def test_card_refund_now_shows_pending_without_claiming_returned_money(self):
        member = self.prepaid(card=True)
        values = self.reviewed(member, refund_action="process")
        url = reverse("membership_overview", args=[member.pk])
        self.assertRedirects(self.client.post(url, values), url)
        result = self.client.get(url)
        self.assertContains(result, "Check the existing refund outcome before another attempt")
        self.assertContains(result, "Returned: <strong>$0.00</strong>", html=False)
        self.assertEqual(PaymentOperation.objects.get(kind="refund").state, "ready")
        self.assertFalse(FinancialLineAdjustment.objects.exists())

    def test_ordinary_staff_cannot_create_cancellation_or_refund_even_with_known_member(self):
        member = self.prepaid()
        values = self.reviewed(member)
        self.client.force_login(self.staff)
        url = reverse("membership_overview", args=[member.pk])
        for action in ("cancel_preview", "cancel_confirm", "refund_confirm"):
            result = self.client.post(url, values | dict(action=action))
            self.assertEqual(result.status_code, 403)
        self.assertNotContains(
            self.client.get(url), "Owner: cancel membership and review any refund"
        )
        self.assertFalse(MembershipCancellation.objects.exists())

    def test_stale_review_requires_another_explicit_confirmation_and_preserves_reason(self):
        member = self.prepaid()
        values = self.reviewed(member)
        url = reverse("membership_overview", args=[member.pk])
        result = self.client.post(url, values | dict(refund_amount="25.00"))
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "review changed")
        self.assertContains(result, "Customer called; owner reviewed the funds.")
        self.assertFalse(MembershipCancellation.objects.exists())
        retry = values | dict(
            refund_amount="25.00", reviewed=result.context["cancel_form"]["reviewed"].value()
        )
        self.assertRedirects(self.client.post(url, retry), url)
        self.assertEqual(MembershipRefundPlan.objects.get().amount, 25)

    def test_csrf_and_feature_boundaries_cover_new_actions(self):
        member = self.prepaid()
        values = self.reviewed(member)
        url = reverse("membership_overview", args=[member.pk])
        client = Client(enforce_csrf_checks=True)
        verified_owner_login(client, self.owner)
        self.assertEqual(client.post(url, values).status_code, 403)
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            self.assertEqual(self.client.post(url, values).status_code, 404)
        self.assertFalse(MembershipCancellation.objects.exists())

    def test_missing_email_requires_no_or_contact_update_before_recording(self):
        member = self.prepaid()
        self.customer.email = ""
        self.customer.save(update_fields=["email"])
        values = self.reviewed(member, send_confirmation="yes")
        result = self.client.post(reverse("membership_overview", args=[member.pk]), values)
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Add a customer email or choose No")
        self.assertFalse(MembershipCancellation.objects.exists())

    def test_card_import_requires_completed_confirmation_and_records_only_verified_money(self):
        member = self.prepaid(card=True)
        values = self.reviewed(member)
        url = reverse("membership_overview", args=[member.pk])
        self.client.post(url, values)
        plan = MembershipRefundPlan.objects.get()
        data = dict(
            action="refund_confirm",
            plan_id=str(plan.pk),
            request_key=str(uuid.uuid4()),
            refund_amount="5.00",
            reviewed_balance="20.00",
            card_refund_action="record",
            completed_provider_reference="1441914",
        )
        invalid = self.client.post(url, data)
        self.assertContains(invalid, "Confirm the refund already completed")
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())
        with patch("core.payments.corrections.Gateway") as gateway:
            gateway.return_value.transaction.side_effect = ProviderFailure()
            failure = self.client.post(url, data | dict(completed_confirmed="on"))
            self.assertContains(failure, "Banquest could not verify the completed refund")
            self.assertContains(failure, "Nothing was recorded and no new refund was sent")
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())
        with patch("core.payments.corrections.Gateway") as gateway:
            gateway.return_value.transaction.return_value = (
                fixtures.MembershipCancellationTests.refund_evidence(self, plan.original)
            )
            self.assertRedirects(self.client.post(url, data | dict(completed_confirmed="on")), url)
            gateway.return_value.refund.assert_not_called()
        self.assertEqual(PaymentOperation.objects.get(kind="refund").state, "succeeded")
        self.assertEqual(notices()["refunds"][0].remaining, 15)
