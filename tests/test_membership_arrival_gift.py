"""One presented-gift verification covers the exact combined manual payment."""

from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.communications.models import MessageDelivery
from core.membership_arrival import confirm, review
from core.membership_arrival_forms import ready
from core.membership_records import MembershipArrivalCheckout, MembershipPurchase
from core.models import FinancialPosting, PaymentOperation
from core.payments.invoices import received
from tests import test_membership_arrival as arrivals
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class GiftMembershipArrivalTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = arrivals.CombinedMembershipArrivalTests.prepare
    web_data = arrivals.CombinedMembershipArrivalTests.web_data

    def gift(self, **values):
        booking = self.prepare(method="gift_card", **values)
        self.options["data"]["gift_card_verified"] = True
        return booking

    def confirm_gift(self, **changes):
        reviewed_hash = changes.get("reviewed_hash") or review(**self.options)["fingerprint"]
        return confirm(
            **(
                self.options
                | dict(
                    request_key=self.key,
                    reviewed_hash=reviewed_hash,
                    confirmed=True,
                    accepted=True,
                    verified_received=False,
                )
                | changes
            )
        )

    def test_one_verification_records_both_gift_receipts_without_a_card_request(self):
        booking = self.gift()
        before = MessageDelivery.objects.count()
        with self.runtime_role(), patch("core.payments.operations.Gateway") as gateway:
            record = self.confirm_gift()
            self.assertEqual(self.confirm_gift(reviewed_hash=record.fingerprint).pk, record.pk)
            gateway.assert_not_called()
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "arrived")
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(
            set(PaymentOperation.objects.values_list("tender", flat=True)), {"gift_card"}
        )
        self.assertEqual(
            received(record.purchase.installments.first().invoice.sale), Decimal("35.98")
        )
        self.assertEqual(received(record.checkout.sale), Decimal("15.99"))
        self.assertEqual(record.facts["received_today"], "51.97")
        self.assertEqual(record.purchase.installments.get(number=2).quote["total"], "37.06")
        self.assertIsNotNone(record.purchase.billing_state.mandate_id)
        self.assertEqual(MessageDelivery.objects.count(), before + 1)
        mail = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("New payment received: $51.97", mail.text_body)
        self.assertNotIn("gift_card", mail.text_body)
        self.assertFalse(MessageDelivery.objects.filter(kind="membership_confirmation").exists())

    def test_unverified_or_string_verification_cannot_be_replaced_by_cash_checkbox(self):
        self.gift()
        for value in (False, "on", None):
            self.options["data"]["gift_card_verified"] = value
            with (
                self.subTest(value=value),
                self.assertRaisesMessage(ValidationError, "physical gift card"),
            ):
                self.confirm_gift(verified_received=True)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(MembershipArrivalCheckout.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())

    def test_unchecked_preview_is_read_only_and_does_not_require_duplicate_receipt_checkbox(self):
        self.gift()
        self.options["data"]["gift_card_verified"] = False
        reviewed = review(**self.options)
        data = self.options["data"] | {
            "member_accepted": True,
            "member_card": self.options["method_id"],
        }
        self.assertFalse(ready(data, reviewed))
        self.assertTrue(ready(data | {"gift_card_verified": True}, reviewed))
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_prepaid_gift_needs_no_membership_card_or_zero_visit_receipt(self):
        self.gift(children=1, places=1, billing="prepaid")
        record = self.confirm_gift()
        self.assertIsNone(record.purchase.billing_state.mandate_id)
        self.assertIsNone(record.checkout.sale_id)
        self.assertEqual(record.facts["received_today"], "53.97")
        self.assertEqual(PaymentOperation.objects.get().tender, "gift_card")

    def test_monthly_gift_without_future_card_or_accepted_terms_does_not_partially_record_money(
        self,
    ):
        self.gift()
        for changes in ({"method_id": None}, {"accepted": False}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.confirm_gift(**changes)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_late_arrival_failure_rolls_back_both_gift_receipts(self):
        booking = self.gift()
        with (
            patch(
                "core.membership_arrival.queue_confirmation",
                side_effect=ValidationError("Local late fault"),
            ),
            self.assertRaises(ValidationError),
        ):
            self.confirm_gift()
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())

    def test_existing_zelle_is_separate_from_the_new_combined_gift_payment(self):
        from core.payments.zelle import record_receipt

        booking = self.gift()
        record_receipt(
            actor=self.staff,
            booking_id=booking.pk,
            request_key=self.key,
            value="10.00",
            sender_name="Fictional parent",
            verified=True,
        )
        record = self.confirm_gift()
        self.assertEqual(record.facts["received_today"], "41.97")
        self.assertEqual(record.facts["visit_due"], "5.99")
        mail = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("New payment received: $41.97", mail.text_body)
        self.assertIn("Previously received Zelle applied to visit: $10.00", mail.text_body)

    def test_one_page_preview_and_confirm_use_gift_verification_without_cash_confirmation(self):
        booking = self.gift()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[booking.pk])
        page = self.client.get(url)
        values = self.web_data(booking) | {
            "arrival_draft": page.context["arrival_draft"],
            "gift_card_verified": "on",
        }
        values.pop("member_received")
        quote = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(quote.status_code, 200, quote.content)
        self.assertTrue(quote.json()["can_confirm"])
        self.assertIn("record gift card $51.97", quote.json()["label"])
        self.assertIn("Gift card received today", quote.json()["html"])
        result = self.client.post(
            url,
            values | {"confirm_review": "1", "reviewed_hash": quote.json()["hash"]},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertTrue(result.json()["confirmed"])
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_native_preview_hides_the_inapplicable_cash_confirmation(self):
        booking = self.gift()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[booking.pk])
        page = self.client.get(url)
        values = self.web_data(booking) | {
            "arrival_draft": page.context["arrival_draft"],
            "gift_card_verified": "on",
        }
        values.pop("member_received")
        response = self.client.post(url, values)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].fields["member_received"].arrival_hidden)
        self.assertContains(response, 'data-arrival-field="member_received" hidden', html=False)
        self.assertFalse(MembershipPurchase.objects.exists())
