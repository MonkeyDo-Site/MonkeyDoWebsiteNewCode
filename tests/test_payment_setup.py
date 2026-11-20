"""Consent, nonce exchange, stale-tab isolation and retained/booking-only lifecycles."""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.models import Booking, PaymentConsent, PaymentMethod, PaymentPolicyVersion, PaymentSetup
from core.payments.gateway import ProviderFailure
from core.payments.methods import expire_unused_setups, remove_unused
from core.payments.policy import POLICY_HASH, VERSION
from core.payments.setup import (
    bind_booking,
    choose_saved,
    exchange,
    selected_consent,
)
from core.public_booking import profile_proof
from tests import test_payment_ledger as fixtures


@override_settings(
    PAYMENT_SANDBOX_ENABLED=True, CUSTOMER_TEST_BOOKING=True, BANQUEST_API_SOURCE_KEY="fake-sandbox"
)
class CardSetupTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create
    sale = fixtures.PaymentLedgerTests.sale
    operation = fixtures.PaymentLedgerTests.operation

    def flow(self, new=False):
        key = str(uuid.uuid4())
        data = {
            "key": key,
            "expires": (timezone.now() + timedelta(minutes=20)).timestamp(),
            "stage": "details",
            "workflow": "integrated_v1",
            "phone": self.customer.phone,
        }
        if new:
            data["phone"] = "2025550191"
            data["contact"] = {"last_name": "New Family", "email": "new@example.invalid"}
        else:
            data["proof"] = profile_proof(self.customer, key)
        return data

    def card(self):
        return {
            "id": 123,
            "customer_id": 12,
            "payment_method_type": "card",
            "card_type": "Visa",
            "last4": "1234",
            "expiry_month": 12,
            "expiry_year": 2035,
        }

    def save_card(self, flow, **changes):
        data = {
            "flow": flow,
            "request_key": uuid.uuid4(),
            "nonce": "nonce-Synthetic",
            "expiry_month": 12,
            "expiry_year": 2035,
            "retain": False,
            "payment_accepted": True,
            "cancellation_accepted": True,
        }
        return exchange(**(data | changes))

    def gateway(self, mocked):
        mocked.return_value.create_customer.return_value = {"id": 12}
        mocked.return_value.save_card.return_value = {"id": 123}
        mocked.return_value.method.return_value = self.card()

    def test_card_save_does_not_charge_or_verify_and_never_persists_nonce_or_expiry(self):
        flow = self.flow()
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(flow)
            self.assertEqual(setup.state, "succeeded")
            gateway.return_value.charge.assert_not_called()
            gateway.return_value.verify.assert_not_called()
            self.assertEqual(setup.method.last_four, "1234")
        policy = PaymentPolicyVersion.objects.get()
        self.assertEqual(policy.content_hash, POLICY_HASH)
        self.assertIn("after you arrive", policy.text["payment"])
        self.assertEqual(PaymentConsent.objects.get().version, VERSION)
        for model in (PaymentSetup, PaymentMethod, PaymentConsent):
            fields = {f.name for f in model._meta.fields}
            self.assertNotIn("nonce", fields)
            self.assertNotIn("expiry_month", fields)
            self.assertNotIn("cvv", fields)
        self.assertNotEqual(setup.nonce_hash, "nonce-Synthetic")
        self.assertFalse(Booking.objects.exists())

    def test_saved_choice_checks_current_provider_ownership_and_transient_expiry_without_charge(
        self,
    ):
        self.sale()
        self.method.reusable = True
        self.method.save(update_fields=["reusable"])
        flow = self.flow()
        evidence = self.card() | {"id": int(self.method.provider_method)}
        with patch("core.payments.setup.Gateway") as gateway:
            gateway.return_value.method.return_value = evidence
            accepted = choose_saved(
                flow=flow,
                method_id=self.method.pk,
                payment_accepted=True,
                cancellation_accepted=True,
            )
            self.assertEqual(accepted.method_id, self.method.pk)
            gateway.return_value.charge.assert_not_called()
            gateway.return_value.verify.assert_not_called()
        for response, message in (
            (evidence | {"expiry_year": 2020}, "Your saved card has expired"),
            (evidence | {"expiry_year": None}, "Your saved payment method could not be used"),
            (evidence | {"customer_id": 999}, "Your saved payment method could not be used"),
        ):
            with self.subTest(message=message), patch("core.payments.setup.Gateway") as gateway:
                gateway.return_value.method.return_value = response
                with self.assertRaisesMessage(ValidationError, message):
                    choose_saved(
                        flow=flow,
                        method_id=self.method.pk,
                        payment_accepted=True,
                        cancellation_accepted=True,
                    )

    def test_abandoned_card_is_disposed_even_if_future_retention_was_selected(self):
        flow = self.flow()
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(flow, retain=True)
        PaymentSetup.objects.filter(pk=setup.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(expire_unused_setups(), 1)
        setup.method.refresh_from_db()
        self.assertFalse(setup.method.reusable)
        self.assertEqual(setup.method.state, "active")
        from core.models import DurableJob

        job = DurableJob.objects.get()
        self.assertEqual(job.kind, "method_remove")
        self.assertEqual(job.reference, str(setup.method_id))

    def test_checked_policies_and_valid_transient_nonce_are_required_before_provider_io(self):
        for changes in (
            {"payment_accepted": False},
            {"cancellation_accepted": False},
            {"nonce": "not-a-token"},
            {"expiry_year": 2020},
        ):
            with self.subTest(changes=changes), patch("core.payments.setup.Gateway") as gateway:
                self.gateway(gateway)
                with self.assertRaises(ValidationError):
                    self.save_card(self.flow(), **changes)
                gateway.return_value.create_customer.assert_not_called()
        self.assertFalse(PaymentMethod.objects.exists())

    def test_duplicate_nonce_exchange_is_idempotent_but_changed_nonce_is_not_replayed(self):
        flow = self.flow()
        key = uuid.uuid4()
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            first = self.save_card(flow, request_key=key)
            second = self.save_card(flow, request_key=key)
            self.assertEqual(first.pk, second.pk)
            self.assertEqual(gateway.return_value.save_card.call_count, 1)
            with self.assertRaises(ValidationError):
                self.save_card(flow, request_key=key, nonce="nonce-Different")
        self.assertEqual(PaymentMethod.objects.count(), 1)
        self.assertEqual(PaymentConsent.objects.count(), 1)

    def test_unknown_nonce_outcome_is_not_retried_and_blocks_other_exchange_for_that_flow(self):
        flow = self.flow()
        key = uuid.uuid4()
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            gateway.return_value.save_card.side_effect = ProviderFailure()
            self.assertEqual(self.save_card(flow, request_key=key).state, "unknown")
            self.assertEqual(self.save_card(flow, request_key=key).state, "unknown")
            self.assertEqual(gateway.return_value.save_card.call_count, 1)
            with self.assertRaises(ValidationError):
                self.save_card(flow, request_key=uuid.uuid4())
        self.assertFalse(PaymentMethod.objects.exists())

    def test_consent_cannot_move_to_a_different_or_restarted_customer_flow(self):
        flow = self.flow()
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(flow)
        flow["payment_consent"] = str(setup.method.consents.get().pk)
        self.assertEqual(selected_consent(flow).method_id, setup.method_id)
        other = self.flow()
        other["payment_consent"] = flow["payment_consent"]
        with self.assertRaises(ValidationError):
            selected_consent(other)
        self.customer.revision += 1
        self.customer.save(update_fields=["revision"])
        with self.assertRaises(ValidationError):
            selected_consent(flow)

    def test_new_customer_setup_does_not_create_profile_and_binds_only_at_final_booking(self):
        flow = self.flow(new=True)
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(flow)
        self.assertIsNone(setup.method.customer_id)
        from core.booking_management import create_test_booking
        from core.models import Customer

        self.assertEqual(Customer.objects.count(), 1)
        customer = Customer.objects.create(
            last_name=flow["contact"]["last_name"],
            phone=flow["phone"],
            email=flow["contact"]["email"],
        )
        booking = create_test_booking(
            actor=self.owner,
            customer=customer,
            session_id=self.create().pk,
            children=1,
            adults=1,
            expected_method="card",
            creation_key=uuid.uuid4(),
        )
        Booking.objects.filter(pk=booking.pk).update(workflow="integrated_v1")
        flow["payment_consent"] = str(setup.method.consents.get().pk)
        agreement = bind_booking(flow=flow, booking=booking)
        self.assertEqual(bind_booking(flow=flow, booking=booking).pk, agreement.pk)
        agreement.method.refresh_from_db()
        self.assertEqual(agreement.method.customer_id, booking.customer_id)
        self.assertEqual(agreement.method.booking_id, booking.pk)

    def test_booking_only_removal_preserves_last_four_and_waits_for_dependencies(self):
        sale = self.sale()
        method = self.method
        operation = self.operation(sale)
        with patch("core.payments.methods.Gateway") as gateway:
            with self.assertRaises(ValidationError):
                remove_unused(method.pk)
            gateway.return_value.delete_method.assert_not_called()
        # A definitive declined operation leaves no pending money responsibility;
        # the final booking/fee resolver still controls agreement state.
        from core.payments.ledger import record_result

        record_result(operation_id=operation.pk, state="declined", source="provider")
        with patch("core.payments.methods.Gateway") as gateway:
            removed = remove_unused(method.pk)
            gateway.return_value.delete_method.assert_called_once_with(method.provider_method)
        self.assertEqual(removed.state, "removed")
        self.assertIsNone(removed.provider_method)
        self.assertEqual(removed.last_four, "1234")
        self.assertEqual(operation.last_four, "1234")

    def test_reusable_card_is_not_automatically_deleted(self):
        self.sale()
        self.method.reusable = True
        self.method.save(update_fields=["reusable"])
        with patch("core.payments.methods.Gateway") as gateway:
            with self.assertRaises(ValidationError):
                remove_unused(self.method.pk)
            gateway.return_value.delete_method.assert_not_called()

    def test_http_setup_rejects_stale_wizard_and_raw_card_keys_and_requires_csrf(self):
        flow = self.flow()
        flow["session_id"] = self.create().pk
        session = self.client.session
        session["customer_test_booking"] = flow
        session.save()
        payload = {
            "request_key": str(uuid.uuid4()),
            "nonce": "nonce-Synthetic",
            "expiry_month": 12,
            "expiry_year": 2035,
            "agree_payment": True,
            "agree_cancellation": True,
            "wizard_key": str(uuid.uuid4()),
            "wizard_stage": "details",
            "policy_version": VERSION,
        }
        with patch("core.payments.setup.Gateway") as gateway:
            response = self.client.post(
                "/book/card/setup/", data=payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 400)
            gateway.assert_not_called()
            payload["wizard_key"] = flow["key"]
            payload["card_number"] = "not-accepted"
            self.assertEqual(
                self.client.post(
                    "/book/card/setup/", data=payload, content_type="application/json"
                ).status_code,
                400,
            )
            gateway.assert_not_called()
        secure = Client(enforce_csrf_checks=True)
        state = secure.session
        state["customer_test_booking"] = flow
        state.save()
        self.assertEqual(
            secure.post("/book/card/setup/", data={}, content_type="application/json").status_code,
            403,
        )

    def test_http_saved_metadata_never_exposes_provider_source_and_status_is_flow_scoped(self):
        flow = self.flow()
        flow["session_id"] = self.create().pk
        session = self.client.session
        session["customer_test_booking"] = flow
        session.save()
        key = uuid.uuid4()
        payload = {
            "request_key": str(key),
            "nonce": "nonce-Synthetic",
            "expiry_month": 12,
            "expiry_year": 2035,
            "agree_payment": True,
            "agree_cancellation": True,
            "wizard_key": flow["key"],
            "wizard_stage": "details",
            "policy_version": VERSION,
        }
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            response = self.client.post(
                "/book/card/setup/", data=payload, content_type="application/json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"state", "brand", "last_four", "consent_id"})
        self.assertEqual(self.client.get(f"/book/card/setup/{key}/").json()["state"], "saved")
        session = self.client.session
        session["customer_test_booking"] = self.flow()
        session.save()
        self.assertEqual(self.client.get(f"/book/card/setup/{key}/").status_code, 404)
        self.assertNotIn("1234", self.client.get(f"/book/card/setup/{key}/").content.decode())
