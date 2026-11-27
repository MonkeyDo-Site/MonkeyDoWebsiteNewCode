"""New membership card authority stays separate from the booking's visit card."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.membership_arrival_forms import purchase_key
from core.membership_records import MembershipArrivalIntent, MembershipPurchase
from core.models import PaymentConsent, PaymentOperation, PaymentSetup
from core.payments.gateway import ProviderFailure
from tests import test_membership_arrival as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CombinedArrivalNewCardTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.CombinedMembershipArrivalTests.prepare
    web_data = fixtures.CombinedMembershipArrivalTests.web_data

    def start(self):
        self.play = self.prepare(method="card")
        self.client.force_login(self.staff)
        self.url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(self.url)
        self.inputs = self.web_data(self.play) | {
            "arrival_draft": page.context["arrival_draft"],
            "member_card": "new",
        }
        response = self.client.post(self.url, self.inputs, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.quote = response.json()
        self.card_payload = dict(
            purchase=self.quote["membership_card_purchase"] | {"accepted": True},
            setup_key=str(uuid.uuid4()),
            nonce="nonce-Synthetic",
            expiry_month=12,
            expiry_year=2035,
            retention_choice="no",
        )

    def store(self, *, unknown=False):
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            gateway.return_value.method.return_value["last4"] = "1111"
            if unknown:
                gateway.return_value.save_card.side_effect = ProviderFailure()
            with self.runtime_role():
                response = self.client.post(
                    reverse("membership_card_setup"),
                    self.card_payload,
                    content_type="application/json",
                )
            gateway.return_value.charge.assert_not_called()
            gateway.return_value.verify.assert_not_called()
        return response

    def reviewed_source(self, response):
        saved = response.json()
        self.inputs.update(
            member_card=saved["method_id"], member_card_authorization=saved["authorization_id"]
        )
        return self.client.post(self.url, self.inputs, HTTP_ACCEPT="application/json")

    def finish(self, reviewed):
        return self.client.post(
            self.url,
            self.inputs | {"confirm_review": "1", "reviewed_hash": reviewed.json()["hash"]},
            HTTP_ACCEPT="application/json",
        )

    def test_received_membership_split_binds_new_future_card_without_using_it_for_visit(self):
        self.start()
        self.inputs.update(
            method="split",
            member_first_method="split",
            member_cash_amount="10.00",
            member_check_amount="25.98",
            cash_amount="10.00",
            member_received="on",
        )
        quote = self.client.post(self.url, self.inputs, HTTP_ACCEPT="application/json")
        self.assertEqual(quote.status_code, 200, quote.content)
        self.assertTrue(quote.json()["can_confirm"])
        self.card_payload["purchase"] = quote.json()["membership_card_purchase"] | {
            "accepted": True
        }
        self.assertEqual(self.card_payload["purchase"]["first_check"], "25.98")
        saved = self.store()
        self.assertEqual(saved.status_code, 200, saved.content)
        reviewed = self.reviewed_source(saved)
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        accepted = self.finish(reviewed)
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertTrue(accepted.json()["confirmed"])
        self.assertFalse(MembershipArrivalIntent.objects.exists())
        member = MembershipPurchase.objects.get()
        self.assertEqual(member.billing_state.mandate.method.last_four, "1111")
        member_sale = member.installments.first().invoice.sale
        self.assertEqual(member_sale.operations.count(), 2)
        self.assertFalse(member_sale.operations.filter(tender="card").exists())
        visit_card = self.play.checkouts.get(kind="arrival").sale.operations.get(tender="card")
        self.assertEqual(visit_card.method_id, self.play.card_agreement.method_id)
        self.assertEqual(visit_card.amount, Decimal("6.17"))

    def test_new_nonretained_card_saves_without_payment_then_funds_only_membership(self):
        self.start()
        self.assertTrue(self.quote["can_confirm"])
        self.assertEqual(self.card_payload["purchase"]["request_key"], str(purchase_key(self.key)))
        consent_count = PaymentConsent.objects.count()
        saved = self.store()
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertEqual(PaymentConsent.objects.count(), consent_count)
        reviewed = self.reviewed_source(saved)
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertEqual(
            reviewed.json()["membership_card_review"], self.quote["membership_card_review"]
        )
        accepted = self.finish(reviewed)
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertTrue(accepted.json()["pending_membership"])
        pending = MembershipArrivalIntent.objects.get()
        method = pending.operation.method
        self.assertEqual(method.last_four, "1111")
        self.assertFalse(method.reusable)
        self.assertEqual(pending.operation.amount, Decimal("37.06"))
        self.assertEqual(pending.purchase.billing_state.mandate.method_id, method.pk)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.play.card_agreement.refresh_from_db()
        self.assertNotEqual(self.play.card_agreement.method_id, method.pk)
        self.assertEqual(PaymentConsent.objects.count(), consent_count)

    def test_nonretained_method_cannot_be_selected_without_its_scoped_authority(self):
        self.start()
        saved = self.store().json()
        self.inputs.update(member_card=saved["method_id"])
        invalid = self.client.post(self.url, self.inputs, HTTP_ACCEPT="application/json")
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_changed_membership_terms_need_new_card_authority_without_reexchanging_nonce(self):
        self.start()
        saved = self.store()
        self.inputs["member_places"] = 1
        reviewed = self.reviewed_source(saved)
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertNotEqual(
            reviewed.json()["membership_card_authorization_offer"],
            reviewed.json()["membership_card_purchase"]["reviewed"],
        )
        invalid = self.finish(reviewed)
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        purchase = reviewed.json()["membership_card_purchase"] | {"accepted": True}
        method_id = saved.json()["method_id"]
        method = PaymentSetup.objects.get(pk=self.card_payload["setup_key"]).method
        with patch("core.membership_card_setup.Gateway") as gateway:
            gateway.return_value.method.return_value = self.card() | {
                "id": int(method.provider_method),
                "customer_id": int(method.provider_customer),
                "last4": "1111",
            }
            refreshed = self.client.post(
                reverse("membership_card_setup"),
                {"purchase": purchase, "method": method_id},
                content_type="application/json",
            )
            gateway.return_value.save_card.assert_not_called()
            gateway.return_value.charge.assert_not_called()
        self.assertEqual(refreshed.status_code, 200, refreshed.content)
        current = self.reviewed_source(refreshed)
        self.assertEqual(self.finish(current).status_code, 200)
        self.assertEqual(PaymentSetup.objects.filter(kind="membership").count(), 1)

    def test_unknown_storage_can_be_checked_and_reloaded_without_purchase_or_new_exchange(self):
        self.start()
        first = self.store(unknown=True)
        self.assertEqual(first.status_code, 202, first.content)
        setup = PaymentSetup.objects.get(pk=self.card_payload["setup_key"])
        self.assertEqual(setup.state, "unknown")
        with patch("core.payments.setup.Gateway") as gateway:
            repeated = self.client.post(
                reverse("membership_card_setup"), self.card_payload, content_type="application/json"
            )
            checked = self.client.get(reverse("membership_card_status", args=[setup.pk]))
            page = self.client.get(self.url + "?draft=" + self.inputs["arrival_draft"])
            gateway.return_value.save_card.assert_not_called()
            gateway.return_value.charge.assert_not_called()
        self.assertEqual(repeated.status_code, 202)
        self.assertEqual(checked.status_code, 202)
        self.assertEqual(
            page.context["membership_card_status_url"],
            reverse("membership_card_status", args=[setup.pk]),
        )
        self.assertEqual(str(page.context["form"]["children"].value()), "3")
        self.assertContains(page, '<option value="new" selected>')
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_another_browser_or_request_cannot_use_the_saved_card_authority(self):
        self.start()
        saved = self.store()
        other = Client()
        other.force_login(self.staff)
        status = other.get(reverse("membership_card_status", args=[self.card_payload["setup_key"]]))
        self.assertEqual(status.status_code, 404)
        self.inputs["request_key"] = str(uuid.uuid4())
        invalid = self.reviewed_source(saved)
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_prepaid_cash_review_does_not_require_secure_card_entry(self):
        self.start()
        self.inputs.update(member_billing="prepaid", method="cash", member_received="on")
        reviewed = self.client.post(self.url, self.inputs, HTTP_ACCEPT="application/json")
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertFalse(reviewed.json()["membership_needs_card"])
        self.assertTrue(reviewed.json()["can_confirm"])

    def test_future_visit_card_is_replaced_only_at_final_confirm_and_visit_binding_stays(self):
        self.start()
        original = self.play.card_agreement.method
        self.card_payload["retention_choice"] = "yes"
        saved = self.store()
        original.refresh_from_db()
        self.assertTrue(original.reusable)
        reviewed = self.reviewed_source(saved)
        self.assertEqual(self.finish(reviewed).status_code, 200)
        original.refresh_from_db()
        self.assertFalse(original.reusable)
        self.assertEqual(original.state, "active")
        self.play.card_agreement.refresh_from_db()
        self.assertEqual(self.play.card_agreement.method_id, original.pk)
        self.assertTrue(MembershipArrivalIntent.objects.get().operation.method.reusable)

    def test_expired_card_authority_does_not_extend_or_create_a_purchase(self):
        self.start()
        saved = self.store()
        self.inputs.update(
            member_card=saved.json()["method_id"],
            member_card_authorization=saved.json()["authorization_id"],
        )
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            reviewed = self.client.post(self.url, self.inputs, HTTP_ACCEPT="application/json")
            self.assertEqual(reviewed.status_code, 200)
            self.assertTrue(reviewed.json()["membership_card_authorization_expired"])
            invalid = self.finish(reviewed)
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
