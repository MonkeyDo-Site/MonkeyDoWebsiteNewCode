"""Split review, verified receipt and card balance remain on the existing page."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.membership_paid_visit_split_records import MembershipPaidVisitSplit
from core.models import PaymentOperation
from tests import test_membership_paid_visit_split as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures


@override_settings(**SETTINGS)
class PaidVisitSplitViewTests(InitialCreditFixtures, TestCase):
    prepare = fixtures.PaidVisitSplitTests.prepare
    buy_card = fixtures.PaidVisitSplitTests.buy_card
    decline = fixtures.PaidVisitSplitTests.decline
    setup_decline = fixtures.PaidVisitSplitTests.setup_decline
    prepare_split = fixtures.PaidVisitSplitTests.prepare_split
    receive = fixtures.PaidVisitSplitTests.receive

    def page(self):
        self.prepare_split()
        verified_owner_login(self.client, self.staff)
        self.url = reverse("membership_overview", args=[self.member.pk])
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        form = page.context["paid_visit_split"]["form"]
        data = {field.html_name: str(field.value()) for field in form if field.value() is not None}
        data |= {"paid-visit-split-manual_amount": "0.97", "paid-visit-split-tender": "cash"}
        return data

    def reviewed(self, data):
        result = self.client.post(
            self.url, data | dict(action="paid_visit_split_review", format="json")
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertIn("$1.03", result.json()["html"])
        return data | {
            "paid-visit-split-reviewed": result.json()["fingerprint"],
            "paid-visit-split-verified_received": "on",
            "paid-visit-split-card_authorized": "on",
        }

    def test_review_is_readonly_and_confirm_returns_to_the_same_membership(self):
        data = self.reviewed(self.page())
        self.assertFalse(MembershipPaidVisitSplit.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 2)
        result = self.client.post(self.url, data | dict(action="paid_visit_split_confirm"))
        self.assertRedirects(result, self.url)
        page = self.client.get(self.url)
        self.assertContains(page, "receipt recorded")
        self.assertContains(page, "$0.97")
        self.assertContains(page, "$1.03")
        self.assertNotContains(page, "Split the remaining payment")
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_card_preparation_failure_shows_received_money_and_exact_resume_action(self):
        data = self.reviewed(self.page())
        with patch(
            "core.membership_paid_visit_split.request_card",
            side_effect=ValidationError("Interrupted"),
        ):
            response = self.client.post(self.url, data | dict(action="paid_visit_split_confirm"))
        self.assertRedirects(response, self.url)
        page = self.client.get(self.url)
        self.assertContains(page, "No remaining card payment has been requested")
        self.assertContains(page, "Request remaining card payment — $1.03")
        self.assertEqual(PaymentOperation.objects.count(), 3)
        split = MembershipPaidVisitSplit.objects.get()
        self.assertEqual(split.card_attempts.count(), 0)

    def test_reviewing_an_already_received_split_never_requests_a_card(self):
        data = self.reviewed(self.page())
        self.receive()
        count = PaymentOperation.objects.count()
        reply = self.client.post(
            self.url, data | dict(action="paid_visit_split_review", format="json")
        )
        self.assertEqual(reply.status_code, 400)
        self.assertIn("already recorded", reply.json()["error"])
        self.assertEqual(PaymentOperation.objects.count(), count)
        self.assertFalse(MembershipPaidVisitSplit.objects.get().card_attempts.exists())

    def test_stale_amount_requires_review_and_receipt_confirmation_again(self):
        data = self.reviewed(self.page())
        reply = self.client.post(
            self.url,
            data | {"action": "paid_visit_split_confirm", "paid-visit-split-manual_amount": "0.96"},
        )
        self.assertContains(reply, "Review the split again")
        form = reply.context["paid_visit_split"]["form"]
        self.assertFalse(form["verified_received"].value())
        self.assertFalse(form["card_authorized"].value())
        self.assertFalse(MembershipPaidVisitSplit.objects.exists())

    def test_paused_sales_keeps_received_history_readable_but_rejects_new_requests(self):
        data = self.reviewed(self.page())
        self.receive()
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            page = self.client.get(self.url)
            self.assertContains(page, "receipt recorded")
            self.assertNotContains(page, "Request remaining card payment —")
            self.assertEqual(
                self.client.post(
                    self.url, data | dict(action="paid_visit_split_confirm")
                ).status_code,
                404,
            )
        self.assertEqual(PaymentOperation.objects.count(), 3)
