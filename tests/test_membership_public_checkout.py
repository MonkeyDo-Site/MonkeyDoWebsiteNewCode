"""Initial public payments use durable evidence without acquiring staff powers."""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core import public_identity
from core.communications.models import MessageDelivery
from core.membership_card_setup import make_flow
from core.membership_public_authority import authorize_dispatch, submit, verified_scope
from core.membership_public_checkout import begin
from core.membership_records import MembershipPublicAcceptance, MembershipPublicCheckout
from core.membership_sales import membership_status, offer
from core.models import (
    AuditEvent,
    Booking,
    Customer,
    FinancialPosting,
    MembershipPricing,
    MembershipPurchase,
    PaymentOperation,
    PricingPolicy,
)
from core.payments.ledger import full_allocation, record_result, request_operation
from core.payments.operations import begin_dispatch
from core.payments.setup import exchange
from core.public_booking import profile_proof
from tests import test_membership_public_authority as public
from tests import test_membership_sales as fixtures
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
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class InitialPublicCheckoutTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp
    authorize_card = public.MembershipPublicAuthorityTests.authorize_card
    checkout = public.MembershipPublicAuthorityTests.checkout

    def context(self, **changes):
        key = str(uuid.uuid4())
        flow = (
            dict(
                key=key,
                stage="details",
                phone=self.customer.phone,
                proof=profile_proof(self.customer, key),
                expires=timezone.now().timestamp() + 1200,
            )
            | changes
        )
        proof = begin(flow)
        values = {key: value for key, value in self.values.items() if key != "actor"}
        return dict(proof=proof, flow=flow, values=values)

    def test_initial_payment_is_one_pending_request_then_one_actual_receipt_and_confirmation(self):
        context = self.context()
        with self.runtime_role():
            member, auth, _ = self.checkout(context)
        accepted = member.public_acceptance
        self.assertIsNone(accepted.link_id)
        self.assertEqual(accepted.checkout_id, member.request_key)
        self.assertEqual(accepted.card_authorization_id, auth.pk)
        self.assertEqual(member.purpose, "purchase")
        self.assertEqual(member.source, "public")
        self.assertIsNone(member.actor_id)
        self.assertEqual(membership_status(member), "pending")
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertFalse(MessageDelivery.objects.exists())
        self.assertFalse(Booking.objects.exists())
        operation = member.installments.first().invoice.sale.operations.get()
        self.assertEqual(operation.state, "ready")
        for _ in range(2):
            record_result(
                operation_id=operation.pk,
                state="succeeded",
                source="provider",
                provider_reference="99001",
            )
        self.assertEqual(FinancialPosting.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.filter(membership=member).count(), 1)
        self.assertEqual(membership_status(member), "active")

    def test_accepted_dispatch_survives_browser_expiry_but_cannot_replay(self):
        context = self.context()
        member, _, _ = self.checkout(context)
        operation = member.installments.first().invoice.sale.operations.get()
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            with self.assertRaises(PermissionDenied):
                verified_scope(context["proof"])
            with self.assertRaises(ValidationError):
                begin(context["flow"])
            authorize_dispatch(operation)
            self.assertEqual(begin_dispatch(operation.pk).state, "sending")
            self.assertIsNone(begin_dispatch(operation.pk))
        record_result(operation_id=operation.pk, state="unknown", source="provider")
        self.assertIsNone(begin_dispatch(operation.pk))
        self.assertFalse(FinancialPosting.objects.exists())

    def test_repeated_identity_and_final_submission_return_same_checkout_and_purchase(self):
        context = self.context()
        member, auth, data = self.checkout(context)
        proof = begin(context["flow"])
        scope = verified_scope(proof)
        self.assertEqual(scope["request_key"], member.request_key)
        again = submit(
            proof=proof,
            reviewed=data["fingerprint"],
            accepted=True,
            card_authorization_id=auth.pk,
            method_id=self.method.pk,
            **{
                key: context["values"][key]
                for key in ("kind", "places", "months", "billing", "starts_on")
            },
        )
        self.assertEqual(again.pk, member.pk)
        self.assertEqual(MembershipPublicCheckout.objects.count(), 1)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_initial_authority_cannot_choose_other_customer_renewal_short_term_or_owner_exception(
        self,
    ):
        context = self.context()
        other = Customer.objects.create(last_name="Other", phone="2025550105")
        for updates in (
            dict(customer=other),
            dict(operation="renewal", prior_id=1),
            dict(expected_method="cash"),
            dict(minimum_override=True),
            dict(comped=True),
            dict(credit_amount="1.00"),
        ):
            with self.subTest(updates=updates), self.assertRaises(PermissionDenied):
                offer(actor=None, authority=context["proof"], **(context["values"] | updates))
        with self.assertRaises(ValidationError):
            offer(actor=None, authority=context["proof"], **(context["values"] | {"months": 2}))
        self.assertFalse(PaymentOperation.objects.exists())

    def test_decline_does_not_allow_browser_authority_to_request_another_payment(self):
        context = self.context()
        member, _, _ = self.checkout(context)
        sale = member.installments.first().invoice.sale
        operation = sale.operations.get()
        record_result(
            operation_id=operation.pk,
            state="declined",
            source="provider",
            provider_reference="99002",
        )
        values = dict(
            actor=None,
            public_membership_authority=context["proof"],
            sale_id=sale.pk,
            tender="card",
            method_id=self.method.pk,
            purpose="member_purchase",
            allocation=full_allocation(sale),
        )
        with self.assertRaises(PermissionDenied):
            request_operation(request_key=uuid.uuid4(), **values)
        repeated = request_operation(request_key=operation.request_key, **values)
        self.assertEqual(repeated.pk, operation.pk)
        self.assertEqual(repeated.state, "declined")
        self.assertIsNone(begin_dispatch(repeated.pk))
        self.assertEqual(sale.operations.count(), 1)

    def test_missing_unverified_and_cross_flow_profile_cannot_begin_purchase(self):
        context = self.context()
        for flow in (
            context["flow"] | {"stage": "name"},
            context["flow"] | {"key": str(uuid.uuid4())},
            context["flow"] | {"proof": "invalid"},
            context["flow"] | {"expires": timezone.now().timestamp()},
        ):
            with self.subTest(flow=flow), self.assertRaises((ValidationError, PermissionDenied)):
                begin(flow)
        self.assertEqual(MembershipPublicCheckout.objects.count(), 1)
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_customer_change_invalidates_browser_but_preserves_accepted_payment_evidence(self):
        context = self.context()
        member, _, _ = self.checkout(context)
        self.customer.revision += 1
        self.customer.save()
        with self.assertRaises(PermissionDenied):
            verified_scope(context["proof"])
        with self.assertRaises(ValidationError):
            begin(context["flow"])
        authorize_dispatch(member.installments.first().invoice.sale.operations.get())

    def test_new_customer_is_created_once_only_after_shared_identity_and_without_booking(self):
        flow = dict(key=str(uuid.uuid4()), stage="phone", expires=timezone.now().timestamp() + 600)
        for data in (
            dict(phone="2025550191", visited="no"),
            dict(last_name="Friedman", email="new@example.invalid", referral_source="Friend"),
        ):
            kwargs = {"phone": flow["phone"]} if flow["stage"] == "contact" else {}
            form = public_identity.form_type(flow)(data, **kwargs)
            self.assertTrue(form.is_valid(), form.errors)
            public_identity.advance(flow, form, post=data)
        self.assertEqual(Customer.objects.count(), 1)
        with self.runtime_role():
            proof = begin(flow)
            again = begin(flow)
        scope = verified_scope(proof)
        self.assertEqual(verified_scope(again)["request_key"], scope["request_key"])
        self.assertEqual(Customer.objects.count(), 2)
        self.assertEqual(scope["customer_record"].email, "new@example.invalid")
        self.assertEqual(scope["expires"] - timezone.now().timestamp(), 600)
        self.assertEqual(
            AuditEvent.objects.filter(action="customer.public_membership_created").count(), 1
        )
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_new_contact_cannot_claim_an_existing_number_or_email(self):
        for contact in (
            dict(phone=self.customer.phone, email="new@example.invalid"),
            dict(phone="2025550191", email=self.customer.email),
        ):
            with self.subTest(contact=contact), self.assertRaises(ValidationError):
                begin(
                    dict(
                        key=str(uuid.uuid4()),
                        stage="details",
                        expires=timezone.now().timestamp() + 1200,
                        phone=contact["phone"],
                        new_contact_ready=True,
                        contact=dict(last_name="New", email=contact["email"]),
                    )
                )
        self.assertEqual(Customer.objects.count(), 1)
        self.assertFalse(MembershipPublicCheckout.objects.exists())

    def test_brand_new_customer_can_store_membership_only_card_then_explicitly_purchase(self):
        proof = begin(
            dict(
                key=str(uuid.uuid4()),
                stage="details",
                expires=timezone.now().timestamp() + 1200,
                phone="2025550191",
                new_contact_ready=True,
                contact=dict(last_name="Friedman", email="new@example.invalid"),
            )
        )
        scope = verified_scope(proof)
        values = {key: value for key, value in self.values.items() if key != "actor"} | {
            "customer": scope["customer_record"]
        }
        data = offer(actor=None, authority=proof, **values)
        flow = make_flow(
            actor=None,
            authority=proof,
            customer=scope["customer_record"],
            request_key=scope["request_key"],
            offer=data,
        )
        with patch("core.payments.setup.Gateway") as gateway, self.runtime_role():
            gateway.return_value.create_customer.return_value = {"id": 912}
            gateway.return_value.save_card.return_value = {"id": 913}
            gateway.return_value.method.return_value = dict(
                id=913,
                customer_id=912,
                payment_method_type="card",
                card_type="Visa",
                last4="1234",
                expiry_month=12,
                expiry_year=2035,
            )
            saved = exchange(
                actor=None,
                flow=flow,
                request_key=uuid.uuid4(),
                nonce="nonce-Synthetic",
                expiry_month=12,
                expiry_year=2035,
                retain=False,
                payment_accepted=True,
                cancellation_accepted=False,
            )
            self.assertEqual(saved.state, "succeeded")
            self.assertFalse(saved.method.reusable)
            self.assertIsNone(saved.consent_id)
            self.assertFalse(MembershipPurchase.objects.exists())
            self.assertFalse(PaymentOperation.objects.exists())
            member = submit(
                proof=proof,
                reviewed=data["fingerprint"],
                accepted=True,
                card_authorization_id=saved.membership_authorization.pk,
                method_id=saved.method_id,
                **{
                    key: values[key] for key in ("kind", "places", "months", "billing", "starts_on")
                },
            )
            gateway.return_value.charge.assert_not_called()
            gateway.return_value.verify.assert_not_called()
        self.assertEqual(member.customer_id, scope["customer"])
        self.assertEqual(member.billing_state.mandate.method_id, saved.method_id)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertFalse(Booking.objects.exists())
        self.method.refresh_from_db()
        self.assertTrue(self.method.reusable)

    def test_feature_off_cannot_create_a_customer_or_checkout(self):
        with override_settings(MEMBERSHIP_SALES_ENABLED=False), self.assertRaises(PermissionDenied):
            self.context()
        self.assertEqual(Customer.objects.count(), 1)
        self.assertFalse(MembershipPublicCheckout.objects.exists())

    def test_missing_email_is_added_before_card_scope_without_overwriting_an_existing_address(self):
        self.customer.email = ""
        self.customer.save()
        context = self.context(contact_email="added@example.invalid")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "added@example.invalid")
        self.assertEqual(verified_scope(context["proof"])["revision"], self.customer.revision)
        self.assertEqual(verified_scope(begin(context["flow"]))["revision"], self.customer.revision)
        self.context(contact_email="ignored@example.invalid")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "added@example.invalid")

    def test_database_enforces_identity_and_accepted_scope_and_immutable_sources(self):
        context = self.context()
        member, auth, _ = self.checkout(context)
        other = self.context()
        with self.assertRaisesMessage(DatabaseError, "scope does not match"), transaction.atomic():
            MembershipPublicAcceptance.objects.create(
                purchase=member,
                checkout=verified_scope(other["proof"])["checkout_record"],
                card_authorization=auth,
                proof_hash="a" * 64,
                customer_revision=self.customer.revision,
                verified_at=timezone.now(),
            )
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_membershippubliccheckout SET customer_revision=99 WHERE id=%s",
                [member.request_key],
            )
        with (
            self.assertRaisesMessage(DatabaseError, "identity scope does not match"),
            transaction.atomic(),
        ):
            MembershipPublicCheckout.objects.create(
                id=uuid.uuid4(),
                customer=self.customer,
                customer_revision=self.customer.revision,
                identity_hash="a" * 64,
                verified_at=timezone.now(),
                expires_at=timezone.now() + timedelta(minutes=21),
            )


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
class InitialPublicCheckoutRaceTests(TransactionTestCase):
    context = InitialPublicCheckoutTests.context
    authorize_card = InitialPublicCheckoutTests.authorize_card

    def setUp(self):
        fixtures.MembershipPurchaseTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create(
                subscription="17.99", unlimited="39.99", actor=self.owner
            )
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def race(self, action, payloads):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL public checkout concurrency")
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        barrier = Barrier(2)

        def run(payload):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout='10s'")
                    try:
                        return action(payload)
                    except ValidationError:
                        return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, payloads))

    def new_flow(self):
        return dict(
            key=str(uuid.uuid4()),
            stage="details",
            expires=timezone.now().timestamp() + 1200,
            new_contact_ready=True,
            phone="2025550191",
            contact=dict(last_name="Friedman", email="new@example.invalid"),
        )

    def test_repeated_begin_creates_one_customer_and_one_identity(self):
        flow = self.new_flow()
        results = self.race(lambda value: verified_scope(begin(value))["request_key"], [flow, flow])
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(Customer.objects.count(), 2)
        self.assertEqual(MembershipPublicCheckout.objects.count(), 1)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_distinct_browsers_cannot_create_duplicate_customer_contacts(self):
        first = self.new_flow()
        results = self.race(
            lambda value: verified_scope(begin(value))["request_key"],
            [first, first | {"key": str(uuid.uuid4())}],
        )
        self.assertEqual(results.count(None), 1)
        self.assertEqual(Customer.objects.count(), 2)
        self.assertEqual(MembershipPublicCheckout.objects.count(), 1)

    def test_simultaneous_confirmation_requests_one_initial_payment(self):
        context = self.context()
        data, auth = self.authorize_card(context)
        payload = dict(
            proof=context["proof"],
            reviewed=data["fingerprint"],
            accepted=True,
            card_authorization_id=auth.pk,
            method_id=self.method.pk,
            **{
                key: context["values"][key]
                for key in ("kind", "places", "months", "billing", "starts_on")
            },
        )
        results = self.race(lambda value: submit(**value).pk, [payload, payload])
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(MembershipPublicAcceptance.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertFalse(FinancialPosting.objects.exists())
