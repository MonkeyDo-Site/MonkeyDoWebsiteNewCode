"""Saving a replacement card never changes future installments or sends a charge."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.membership_card_setup import make_flow
from core.membership_paid_visit_new_card import (
    pending,
    scoped_methods,
    storage_review,
    terms,
)
from core.membership_paid_visit_pending import complete, stop, stop_facts
from core.membership_paid_visit_records import MembershipPaidVisitCardStorage
from core.membership_paid_visit_recovery import request as recover
from core.membership_paid_visit_recovery import review
from core.models import PaymentConsent, PaymentOperation
from core.payments.gateway import ProviderFailure
from core.payments.ledger import record_result
from core.payments.methods import begin_removal, expire_membership_sources, expire_unused_setups
from core.payments.operations import begin_dispatch
from core.payments.setup import exchange
from tests import test_membership_paid_visit_recovery as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitNewCardTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PaidVisitRecoveryTests.prepare
    buy_card = fixtures.PaidVisitRecoveryTests.buy_card
    decline = fixtures.PaidVisitRecoveryTests.decline
    setup_decline = fixtures.PaidVisitRecoveryTests.setup_decline

    def storage_flow(self):
        self.setup_decline()
        _, data = storage_review(actor=self.staff, intent_id=self.intent.pk)
        offer = dict(
            operation="paid_visit_recovery",
            origin={"prior_id": self.member.pk},
            expected_method="card",
            fingerprint=data["fingerprint"],
            terms=terms(data),
        )
        self.flow = make_flow(
            actor=self.staff, customer=self.customer, request_key=uuid.uuid4(), offer=offer
        )
        self.flow["recovery_intent"] = str(self.intent.pk)
        self.flow["setup_key"] = str(uuid.uuid4())
        return self.flow

    def save_recovery_card(self, *, retain=False):
        return exchange(
            flow=self.flow,
            actor=self.staff,
            request_key=self.flow["setup_key"],
            nonce="nonce-Synthetic",
            expiry_month=12,
            expiry_year=2035,
            retain=retain,
            payment_accepted=True,
            cancellation_accepted=False,
        )

    def recovery_gateway(self, gateway):
        gateway.return_value.create_customer.return_value = {"id": 12}
        gateway.return_value.save_card.return_value = {"id": 321}
        gateway.return_value.method.return_value = {
            "id": 321,
            "customer_id": 12,
            "payment_method_type": "card",
            "card_type": "Visa",
            "last4": "6789",
            "expiry_month": 12,
            "expiry_year": 2035,
        }

    def known_card(self, *, retain=False):
        self.storage_flow()
        self.consent_count = PaymentConsent.objects.count()
        with patch("core.payments.setup.Gateway") as gateway:
            self.recovery_gateway(gateway)
            with self.runtime_role():
                self.setup = self.save_recovery_card(retain=retain)
        self.assertEqual(self.setup.state, "succeeded")
        return self.setup.method

    def request_new(self, method):
        data = review(actor=self.staff, intent_id=self.intent.pk, method_id=method.pk)
        return recover(
            actor=self.staff,
            intent_id=self.intent.pk,
            method_id=method.pk,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            confirmed=True,
        )

    def test_new_nonretained_card_saves_without_charge_or_future_mandate(self):
        method = self.known_card()
        self.assertFalse(method.reusable)
        self.assertIn(method, scoped_methods(self.intent))
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(PaymentConsent.objects.count(), self.consent_count)
        self.assertEqual(MembershipPaidVisitCardStorage.objects.count(), 1)
        self.assertTrue(
            MembershipPaidVisitCardStorage.objects.get().authorization.storage_version.startswith(
                "MD-PAID-VISIT"
            )
        )
        with self.runtime_role():
            replacement = self.request_new(method)
        self.assertEqual(replacement.operation.method_id, method.pk)
        self.assertEqual(replacement.operation.amount, Decimal("2.03"))
        self.member.billing_state.refresh_from_db()
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)

    def test_unknown_save_blocks_retry_and_release_without_another_exchange(self):
        self.storage_flow()
        with patch("core.payments.setup.Gateway") as gateway:
            self.recovery_gateway(gateway)
            gateway.return_value.save_card.side_effect = ProviderFailure("storage_unknown")
            self.setup = self.save_recovery_card()
            again = self.save_recovery_card()
        self.assertEqual((self.setup.state, again.pk), ("unknown", self.setup.pk))
        self.assertEqual(gateway.return_value.save_card.call_count, 1)
        self.assertTrue(pending(self.intent))
        with self.assertRaises(ValidationError):
            review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)
        self.assertFalse(stop_facts(self.intent)["allowed"])
        with self.assertRaises(ValidationError):
            stop(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=uuid.uuid4(),
                reviewed=stop_facts(self.intent)["fingerprint"],
                reason="Cancel application",
            )
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_storage_authority_is_immutable_under_runtime_role(self):
        self.known_card()
        with self.assertRaises(DatabaseError), transaction.atomic(), self.runtime_role():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_membershippaidvisitcardstorage SET fingerprint=%s", ["b" * 64]
                )

    def test_known_card_remains_needed_until_source_is_closed_then_can_be_disposed(self):
        method = self.known_card()
        with self.assertRaises(ValidationError):
            begin_removal(method.pk)
        replacement = self.request_new(method)
        self.assertIsNotNone(begin_dispatch(replacement.operation.pk))
        record_result(
            operation_id=replacement.operation.pk,
            state="succeeded",
            source="provider",
            provider_reference="991781",
        )
        complete(self.intent.pk)
        self.assertGreaterEqual(expire_membership_sources(), 1)
        self.assertIsNotNone(begin_removal(method.pk))

    def test_confirmed_future_visit_choice_survives_unused_setup_cleanup(self):
        method = self.known_card(retain=True)
        self.request_new(method)
        self.method.refresh_from_db()
        self.assertFalse(self.method.reusable)
        self.member.billing_state.refresh_from_db()
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)
        with patch(
            "core.payments.methods.timezone.now", return_value=timezone.now() + timedelta(hours=1)
        ):
            expire_unused_setups()
        method.refresh_from_db()
        self.assertTrue(method.reusable)

    def browser_payload(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.storage_flow()
        # The authorized storage actor is the same staff member who owns this session.
        verified_owner_login(self.client, self.staff)
        session = self.client.session
        session["membership_card_flows"] = {self.flow["key"]: self.flow}
        session.save()
        self.endpoint = reverse("membership_paid_visit_card_setup", args=[self.member.pk])
        return dict(
            storage_key=self.flow["key"],
            setup_key=self.flow["setup_key"],
            nonce="nonce-Synthetic",
            expiry_month=12,
            expiry_year=2035,
            retention_choice="no",
            confirmed=True,
        )

    def test_browser_save_response_then_explicit_request_keeps_future_card(self):
        from django.urls import reverse

        payload = self.browser_payload()
        with patch("core.payments.setup.Gateway") as gateway:
            self.recovery_gateway(gateway)
            response = self.client.post(self.endpoint, payload, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["state"], "saved")
        self.assertTrue(data["recovery_choice"])
        self.assertEqual(PaymentOperation.objects.count(), 2)
        response = self.client.post(
            reverse("membership_overview", args=[self.member.pk]),
            dict(
                action="paid_visit_card_recover",
                request_key=str(uuid.uuid4()),
                card_choice=data["recovery_choice"],
                confirmed="on",
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.member.billing_state.refresh_from_db()
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)

    def test_browser_requires_explicit_consent_before_any_storage(self):
        payload = self.browser_payload()
        payload["confirmed"] = False
        with patch("core.payments.setup.Gateway") as gateway:
            response = self.client.post(self.endpoint, payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        gateway.assert_not_called()
        self.assertFalse(MembershipPaidVisitCardStorage.objects.exists())

    def test_uncertain_save_survives_reload_and_status_read_never_reposts(self):
        from django.urls import reverse

        payload = self.browser_payload()
        with patch("core.payments.setup.Gateway") as gateway:
            self.recovery_gateway(gateway)
            gateway.return_value.save_card.side_effect = ProviderFailure("unknown")
            response = self.client.post(self.endpoint, payload, content_type="application/json")
            self.assertEqual(response.status_code, 202, response.content)
            status_url = response.json()["status_url"]
            status = self.client.get(status_url)
            self.assertEqual(status.status_code, 202)
            page = self.client.get(reverse("membership_overview", args=[self.member.pk]))
            self.assertContains(page, status_url)
            repeat = self.client.post(self.endpoint, payload, content_type="application/json")
            self.assertEqual(repeat.status_code, 202, repeat.content)
        self.assertEqual(gateway.return_value.save_card.call_count, 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertFalse(stop_facts(self.intent)["allowed"])

    def test_unknown_storage_also_blocks_direct_database_source_release(self):
        from core.membership_paid_visit_records import MembershipPaidVisitRelease

        self.storage_flow()
        with patch("core.payments.setup.Gateway") as gateway:
            self.recovery_gateway(gateway)
            gateway.return_value.save_card.side_effect = ProviderFailure("unknown")
            self.save_recovery_card()
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipPaidVisitRelease.objects.create(
                intent=self.intent,
                request_key=uuid.uuid4(),
                kind="stopped",
                reason="Bypass storage review",
                actor=self.owner,
            )

    def test_a_second_known_decline_allows_reusing_this_nonretained_source_explicitly(self):
        method = self.known_card()
        first = self.request_new(method)
        self.decline(first.operation)
        with self.runtime_role():
            second = self.request_new(method)
        self.assertEqual(second.previous_id, first.operation.pk)
        self.assertEqual(second.sequence, 2)
        self.assertEqual(second.operation.method_id, method.pk)
        self.assertEqual(second.operation.amount, Decimal("2.03"))
        self.assertEqual(MembershipPaidVisitCardStorage.objects.count(), 1)

    def test_abandoned_retention_choice_is_not_a_confirmed_future_visit_card(self):
        method = self.known_card(retain=True)
        stop(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=stop_facts(self.intent)["fingerprint"],
            reason="Do not apply this visit",
        )
        with patch(
            "core.payments.methods.timezone.now", return_value=timezone.now() + timedelta(hours=1)
        ):
            self.assertGreaterEqual(expire_unused_setups(), 1)
        method.refresh_from_db()
        self.method.refresh_from_db()
        self.assertFalse(method.reusable)
        self.assertTrue(self.method.reusable)

    def test_expired_storage_review_cannot_exchange_a_fresh_nonce(self):
        self.storage_flow()
        self.flow["expires"] = timezone.now().timestamp() - 1
        with patch("core.payments.setup.Gateway") as gateway:
            with self.assertRaises(ValidationError):
                self.save_recovery_card()
        gateway.return_value.create_customer.assert_not_called()
        gateway.return_value.save_card.assert_not_called()
        self.assertFalse(MembershipPaidVisitCardStorage.objects.exists())

    def test_another_session_cannot_use_this_storage_context(self):
        from django.test import Client

        payload = self.browser_payload()
        other = Client()
        from tests.helpers import verified_owner_login

        verified_owner_login(other, self.staff)
        with patch("core.payments.setup.Gateway") as gateway:
            response = other.post(self.endpoint, payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        gateway.assert_not_called()

    def test_an_unscoped_card_authority_cannot_be_attached_to_the_reserved_purchase(self):
        from core.membership_records import MembershipCardAuthorization

        self.storage_flow()
        fake = MembershipCardAuthorization.objects.create(
            method=self.method,
            customer=self.customer,
            request_key=uuid.uuid4(),
            flow_hash="a" * 64,
            offer_fingerprint=self.flow["offer_fingerprint"],
            terms_text=self.flow["terms_text"],
            storage_version="MD-PAID-VISIT-RECOVERY-CARD-2026-01",
            storage_text="Synthetic unscoped source",
            actor=self.staff,
            expires_at=timezone.now() + timedelta(minutes=20),
        )
        _, data = storage_review(actor=self.staff, intent_id=self.intent.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipPaidVisitCardStorage.objects.create(
                authorization=fake,
                intent=self.intent,
                previous=self.operation,
                facts=data,
                fingerprint="b" * 64,
            )

    def test_owner_lookup_recovers_unknown_storage_without_another_card_save(self):
        from core.payments.setup import reconcile_setup

        self.storage_flow()
        with patch("core.payments.setup.Gateway") as gateway:
            self.recovery_gateway(gateway)
            gateway.return_value.save_card.side_effect = ProviderFailure("unknown")
            unknown = self.save_recovery_card()
            self.assertEqual(unknown.state, "unknown")
            gateway.return_value.methods.return_value = [{"id": 321}]
            known = reconcile_setup(actor=self.owner, setup_id=unknown.pk)
        self.assertEqual(known.state, "succeeded")
        self.assertEqual(gateway.return_value.create_customer.call_count, 1)
        self.assertEqual(gateway.return_value.save_card.call_count, 1)
        self.assertEqual(gateway.return_value.methods.call_count, 1)
        self.assertFalse(pending(self.intent))
        self.assertEqual(PaymentOperation.objects.count(), 2)
        replacement = self.request_new(known.method)
        self.assertEqual(replacement.operation.amount, Decimal("2.03"))
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.member.billing_state.refresh_from_db()
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)

    def test_future_visit_selector_includes_retained_card_only_after_confirmation(self):
        from core.payments.setup import reusable_methods
        from tests.test_payment_setup import CardSetupTests

        method = self.known_card(retain=True)
        future_flow = CardSetupTests.flow(self)
        self.assertNotIn(method, reusable_methods(future_flow))
        self.assertIn(self.method, reusable_methods(future_flow))
        self.request_new(method)
        self.assertIn(method, reusable_methods(future_flow))
        self.assertNotIn(self.method, reusable_methods(future_flow))
        self.member.billing_state.refresh_from_db()
        self.assertEqual(self.member.billing_state.mandate.method_id, self.method.pk)
