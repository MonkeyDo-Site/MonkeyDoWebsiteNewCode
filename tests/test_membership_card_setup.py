"""Membership card storage is separate from visit consent and never charges."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.membership_card_setup import choose_saved, make_flow, reviewed_source
from core.membership_records import MembershipCardAuthorization
from core.membership_sales import offer, purchase
from core.models import AuditEvent, FinancialSale, PaymentConsent, PaymentOperation
from core.payments.gateway import ProviderFailure
from core.payments.setup import exchange, reusable_methods
from tests import test_membership_sales as fixtures
from tests import test_payment_setup as setup_fixtures
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
)
class MembershipCardSetupTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy

    def flow(self, **values):
        return make_flow(
            actor=self.staff,
            customer=self.customer,
            request_key=self.key,
            offer=offer(**(self.values | values)),
        )

    def save_card(self, flow, **values):
        return exchange(
            flow=flow,
            actor=self.staff,
            request_key=values.pop("key", uuid.uuid4()),
            nonce="nonce-Synthetic",
            expiry_month=12,
            expiry_year=2035,
            retain=values.pop("retain", False),
            payment_accepted=True,
            cancellation_accepted=False,
            **values,
        )

    def gateway(self, mocked):
        setup_fixtures.CardSetupTests.gateway(self, mocked)

    card = setup_fixtures.CardSetupTests.card

    def test_saving_card_records_member_authorization_without_visit_consent_or_charge(self):
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(self.flow())
        self.assertEqual(setup.kind, "membership")
        self.assertEqual(setup.state, "succeeded")
        self.assertIsNone(setup.consent_id)
        self.assertFalse(PaymentConsent.objects.exists())
        self.assertFalse(FinancialSale.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertEqual(setup.membership_authorization.actor, self.staff)
        self.assertIn("does not charge", setup.membership_authorization.storage_text)
        self.assertFalse(
            AuditEvent.objects.filter(action="payment.displayed_terms_accepted").exists()
        )
        self.assertNotIn(
            "Synthetic", str(list(AuditEvent.objects.values_list("changes", flat=True)))
        )
        gateway.return_value.charge.assert_not_called()
        gateway.return_value.verify.assert_not_called()

    def test_final_purchase_accepts_only_the_new_card_authorized_for_its_current_selection(self):
        data = offer(**self.values)
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(self.flow())
        authority = setup.membership_authorization
        member = purchase(
            **self.values,
            request_key=self.key,
            reviewed=data["fingerprint"],
            accepted=True,
            method_id=setup.method_id,
            card_authorization_id=authority.pk,
        )
        self.assertEqual(member.billing_state.mandate.method_id, setup.method_id)
        self.assertEqual(
            PaymentOperation.objects.get().amount,
            Decimal(data["installments"][0]["quote"]["total"]),
        )
        self.assertEqual(PaymentOperation.objects.get().state, "ready")
        setup.method.refresh_from_db()
        self.assertFalse(setup.method.reusable)

    def test_changed_terms_request_customer_or_actor_cannot_reuse_old_card_authority(self):
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(self.flow())
        authority = setup.membership_authorization
        common = dict(
            actor=self.staff,
            authorization_id=authority.pk,
            customer=self.customer,
            request_key=self.key,
            reviewed=offer(**self.values)["fingerprint"],
        )
        for changes in (
            dict(reviewed="stale"),
            dict(request_key=uuid.uuid4()),
            dict(actor=self.owner),
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                reviewed_source(**(common | changes))
        with (
            patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)),
            self.assertRaises(ValidationError),
        ):
            reviewed_source(**common)
        self.assertFalse(FinancialSale.objects.exists())

    def test_unknown_setup_persists_authority_but_never_repeats_its_nonce_exchange(self):
        key = uuid.uuid4()
        with patch("core.payments.setup.Gateway") as gateway:
            gateway.return_value.create_customer.side_effect = ProviderFailure()
            flow = self.flow()
            first = self.save_card(flow, key=key)
            second = self.save_card(flow, key=key)
            self.assertEqual(first.state, "unknown")
            self.assertEqual(first.pk, second.pk)
            gateway.return_value.create_customer.assert_called_once()
        self.assertEqual(MembershipCardAuthorization.objects.count(), 1)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_future_visit_retention_changes_only_when_membership_purchase_is_confirmed(self):
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(self.flow(), retain=True)
        self.method.refresh_from_db()
        self.assertTrue(self.method.reusable)
        purchase(
            **self.values,
            request_key=self.key,
            reviewed=offer(**self.values)["fingerprint"],
            accepted=True,
            method_id=setup.method_id,
            card_authorization_id=setup.membership_authorization.pk,
        )
        self.method.refresh_from_db()
        self.assertFalse(self.method.reusable)
        flow = setup_fixtures.CardSetupTests.flow(self)
        self.assertIn(setup.method_id, reusable_methods(flow).values_list("pk", flat=True))

    def test_membership_storage_cannot_be_used_as_a_booking_consent(self):
        from core.payments.setup import selected_consent

        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(self.flow())
        booking_flow = setup_fixtures.CardSetupTests.flow(self)
        booking_flow["payment_consent"] = str(setup.membership_authorization.pk)
        with self.assertRaises(ValidationError):
            selected_consent(booking_flow)

    def test_current_scoped_card_can_be_authorized_again_for_changed_membership_terms(self):
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(self.flow())
        with patch("core.membership_card_setup.Gateway") as gateway:
            gateway.return_value.method.return_value = self.card()
            current = choose_saved(
                actor=self.staff, flow=self.flow(places=3), method_id=setup.method_id, accepted=True
            )
        self.assertEqual(current.method_id, setup.method_id)
        self.assertNotEqual(
            current.offer_fingerprint, setup.membership_authorization.offer_fingerprint
        )
        self.assertEqual(PaymentOperation.objects.count(), 0)

    def test_runtime_authority_is_append_only(self):
        with self.runtime_role(), patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(self.flow())
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_membershipcardauthorization SET retain=true WHERE id=%s",
                    [setup.membership_authorization.pk],
                )
