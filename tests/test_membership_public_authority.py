"""A verified renewal proof never acts as a staff financial permission."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.membership_card_setup import choose_saved, make_flow
from core.membership_public_authority import (
    authorize_dispatch,
    create_link,
    resolve_link,
    revoke_link,
    submit,
    verified_scope,
    verify_identity,
)
from core.membership_records import MembershipPublicAcceptance, MembershipRenewalLink
from core.membership_renewals import renewal_details
from core.membership_sales import invoice_for, membership_status, offer, purchase
from core.models import (
    Customer,
    FinancialPosting,
    MembershipPurchase,
    PaymentMethod,
    PaymentOperation,
)
from core.payments.ledger import full_allocation, record_result, request_operation
from core.payments.operations import begin_dispatch
from core.payments.setup import exchange
from tests import test_membership_renewals as fixtures
from tests import test_payment_setup as card_fixtures
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
class MembershipPublicAuthorityTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipRenewalTests.setUp
    buy = fixtures.MembershipRenewalTests.buy
    prior = fixtures.MembershipRenewalTests.prior

    def context(self, prior=None, *, customer=None, key=None):
        prior = prior or self.prior()
        link, token = create_link(actor=self.staff, prior=prior, request_key=uuid.uuid4())
        customer = customer or self.customer
        proof = verify_identity(
            token=token,
            phone=customer.phone,
            last_name=customer.last_name,
            request_key=key or uuid.uuid4(),
        )
        values = dict(
            customer=customer,
            kind="subscription",
            places=1,
            months=1,
            billing="monthly",
            starts_on=renewal_details(prior)["starts_on"],
            expected_method="card",
            operation="renewal",
            prior_id=prior.pk,
        )
        return dict(prior=prior, link=link, token=token, proof=proof, values=values)

    def authorize_card(self, context, method=None):
        method = method or self.method
        proof, values = context["proof"], context["values"]
        data = offer(actor=None, authority=proof, **values)
        flow = make_flow(
            actor=None,
            authority=proof,
            customer=values["customer"],
            request_key=verified_scope(proof)["request_key"],
            offer=data,
        )
        with patch("core.membership_card_setup.Gateway") as gateway:
            gateway.return_value.method.return_value = dict(
                id=int(method.provider_method),
                customer_id=int(method.provider_customer),
                payment_method_type="card",
                card_type=method.brand,
                last4=method.last_four,
                expiry_month=12,
                expiry_year=2035,
            )
            auth = choose_saved(actor=None, flow=flow, method_id=method.pk, accepted=True)
            gateway.return_value.charge.assert_not_called()
        return data, auth

    def checkout(self, context, *, method=None):
        method = method or self.method
        data, auth = self.authorize_card(context, method)
        values = {
            key: context["values"][key]
            for key in ("kind", "places", "months", "billing", "starts_on")
        }
        member = submit(
            proof=context["proof"],
            reviewed=data["fingerprint"],
            accepted=True,
            card_authorization_id=auth.pk,
            method_id=method.pk,
            **values,
        )
        return member, auth, data

    def test_private_link_is_idempotent_expires_in_thirty_days_and_verifies_phone_and_name(self):
        prior = self.prior()
        key = uuid.uuid4()
        link, token = create_link(actor=self.staff, prior=prior, request_key=key)
        self.assertEqual(create_link(actor=self.staff, prior=prior, request_key=key), (link, token))
        self.assertEqual(link.expires_at - timezone.now(), timedelta(days=30))
        self.assertEqual(resolve_link(token).prior_id, prior.pk)
        for phone, name in (
            (self.customer.phone, "Other"),
            ("2025550999", self.customer.last_name),
        ):
            with self.subTest(phone=phone), self.assertRaises(ValidationError):
                verify_identity(token=token, phone=phone, last_name=name)
        with (
            patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=30)),
            self.assertRaises(ValidationError),
        ):
            resolve_link(token)
        self.assertEqual(MembershipRenewalLink.objects.count(), 1)

    def test_proof_is_short_lived_bound_to_current_profile_and_link_can_be_revoked(self):
        c = self.context()
        self.assertEqual(verified_scope(c["proof"])["customer"], self.customer.pk)
        with (
            patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)),
            self.assertRaises(PermissionDenied),
        ):
            verified_scope(c["proof"])
        self.customer.revision += 1
        self.customer.save(update_fields=["revision"])
        with self.assertRaises(PermissionDenied):
            verified_scope(c["proof"])
        revoke_link(actor=self.staff, link_id=c["link"].pk)
        with self.assertRaises(ValidationError):
            resolve_link(c["token"])

    def test_public_purchase_records_customer_attribution_and_only_one_initial_card_request(self):
        c = self.context()
        before = MembershipPurchase.objects.count()
        member, auth, _ = self.checkout(c)
        self.assertEqual(MembershipPurchase.objects.count(), before + 1)
        self.assertEqual(member.source, "public")
        self.assertIsNone(member.actor_id)
        self.assertIsNone(member.membership.actor_id)
        self.assertIsNone(member.billing_state.mandate.actor_id)
        op = member.installments.first().invoice.sale.operations.get()
        self.assertIsNone(op.actor_id)
        self.assertIsNone(op.sale.actor_id)
        self.assertEqual(op.state, "ready")

        self.assertEqual(op.amount, Decimal("18.53"))
        self.assertEqual(member.public_acceptance.link_id, c["link"].pk)
        self.assertEqual(member.public_acceptance.card_authorization_id, auth.pk)
        self.assertEqual(len(member.public_acceptance.proof_hash), 64)
        self.assertFalse(FinancialPosting.objects.filter(operation=op).exists())
        self.assertEqual(membership_status(member), "pending")

    def test_durable_dispatch_survives_expired_browser_proof_and_never_claims_twice(self):
        c = self.context()
        member, _, _ = self.checkout(c)
        op = member.installments.first().invoice.sale.operations.get()
        with patch(
            "django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=21)
        ):
            with self.assertRaises(PermissionDenied):
                verified_scope(c["proof"])
            self.assertEqual(begin_dispatch(op.pk).state, "sending")
            self.assertIsNone(begin_dispatch(op.pk))

    def test_revocation_stops_new_access_without_rewriting_an_already_accepted_payment(self):
        c = self.context()
        member, _, _ = self.checkout(c)
        op = member.installments.first().invoice.sale.operations.get()
        revoke_link(actor=self.owner, link_id=c["link"].pk)
        with self.assertRaises(PermissionDenied):
            verified_scope(c["proof"])
        authorize_dispatch(op)

    def test_success_queues_one_approved_renewal_email_and_does_not_backdate_benefits(self):
        c = self.context()
        member, _, _ = self.checkout(c)
        op = member.installments.first().invoice.sale.operations.get()
        record_result(
            operation_id=op.pk, state="succeeded", source="provider", provider_reference="7001"
        )
        record_result(
            operation_id=op.pk, state="succeeded", source="provider", provider_reference="7001"
        )
        self.assertEqual(membership_status(member), "scheduled")
        messages = MessageDelivery.objects.filter(membership=member)
        self.assertEqual(messages.count(), 1)
        self.assertEqual(messages.get().kind, "membership_renewal")
        self.assertEqual(member.membership.starts_on, renewal_details(c["prior"])["starts_on"])

    def test_lost_response_and_reverified_same_link_return_original_purchase_without_another_charge(
        self,
    ):
        c = self.context()
        member, auth, data = self.checkout(c)
        values = {
            key: c["values"][key] for key in ("kind", "places", "months", "billing", "starts_on")
        }
        for proof in (
            c["proof"],
            verify_identity(
                token=c["token"], phone=self.customer.phone, last_name=self.customer.last_name
            ),
        ):
            result = submit(
                proof=proof,
                reviewed=data["fingerprint"],
                accepted=True,
                card_authorization_id=auth.pk,
                method_id=self.method.pk,
                **values,
            )
            self.assertEqual(result.pk, member.pk)
        self.assertEqual(member.installments.first().invoice.sale.operations.count(), 1)

    def test_public_proof_cannot_buy_another_product_customer_or_owner_exception(self):
        c = self.context()
        other = Customer.objects.create(last_name="Rosen", phone="2025550102")
        for values in (
            dict(operation="purchase", prior_id=None),
            dict(customer=other),
            dict(minimum_override=True),
            dict(comped=True),
            dict(expected_method="cash"),
        ):
            with self.subTest(values=values), self.assertRaises(PermissionDenied):
                offer(actor=None, authority=c["proof"], **(c["values"] | values))
        with self.assertRaises(PermissionDenied):
            offer(actor=None, **c["values"])

    def test_public_proof_cannot_refund_collect_partial_or_pay_another_invoice(self):
        c = self.context()
        member, _, _ = self.checkout(c)
        sale = member.installments.first().invoice.sale
        args = dict(
            actor=None,
            public_membership_authority=c["proof"],
            sale_id=sale.pk,
            request_key=uuid.uuid4(),
            tender="card",
            method_id=self.method.pk,
            purpose="member_purchase",
            allocation=full_allocation(sale),
        )
        with self.assertRaises(PermissionDenied):
            request_operation(**(args | dict(kind="refund")))
        allocation = full_allocation(sale)
        allocation[0].update(net="1.00", fee="0.00")
        with self.assertRaises(PermissionDenied):
            request_operation(**(args | dict(allocation=allocation)))
        other_sale = c["prior"].installments.first().invoice.sale
        with self.assertRaises(PermissionDenied):
            request_operation(
                **(args | dict(sale_id=other_sale.pk, allocation=full_allocation(other_sale)))
            )
        self.assertEqual(sale.operations.count(), 1)

    def test_public_proof_never_authorizes_later_installment_collection(self):
        c = self.context()
        c["values"]["months"] = 3
        member, _, _ = self.checkout(c)
        with self.assertRaises(PermissionDenied):
            invoice_for(
                member.installments.get(number=2), actor=None, tender="card", authority=c["proof"]
            )
        self.assertEqual(member.installments.filter(invoice__isnull=False).count(), 1)

    def test_new_public_card_uses_membership_storage_without_a_booking_consent(self):
        c = self.context()
        data = offer(actor=None, authority=c["proof"], **c["values"])
        scope = verified_scope(c["proof"])
        flow = make_flow(
            actor=None,
            authority=c["proof"],
            customer=self.customer,
            request_key=scope["request_key"],
            offer=data,
        )
        with patch("core.payments.setup.Gateway") as gateway:
            card_fixtures.CardSetupTests.gateway(self, gateway)
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
        self.assertIsNone(saved.actor_id)
        self.assertIsNone(saved.consent_id)
        self.assertIsNone(saved.membership_authorization.actor_id)
        values = {
            key: c["values"][key] for key in ("kind", "places", "months", "billing", "starts_on")
        }
        member = submit(
            proof=c["proof"],
            reviewed=data["fingerprint"],
            accepted=True,
            card_authorization_id=saved.membership_authorization.pk,
            method_id=saved.method_id,
            **values,
        )
        self.assertEqual(member.billing_state.mandate.method_id, saved.method_id)

    card = card_fixtures.CardSetupTests.card

    def test_scope_cannot_replay_another_customers_public_request_key(self):
        a = self.context()
        customer = Customer.objects.create(last_name="Rosen", phone="2025550103")
        prior = self.prior(customer=customer)
        b = self.context(prior, customer=customer)
        card = PaymentMethod.objects.create(
            customer=customer,
            provider_customer="13",
            provider_method="346",
            brand="Visa",
            last_four="4242",
            reusable=True,
            consent_at=timezone.now(),
            consent_version="test",
        )
        member, _, data = self.checkout(b, method=card)
        proof = verify_identity(
            token=a["token"],
            phone=self.customer.phone,
            last_name=self.customer.last_name,
            request_key=member.request_key,
        )
        with self.assertRaises(PermissionDenied):
            purchase(
                actor=None,
                authority=proof,
                request_key=member.request_key,
                reviewed=data["fingerprint"],
                accepted=True,
                **a["values"],
            )

    def test_public_evidence_is_immutable_and_database_checks_customer_scope(self):
        c = self.context()
        with self.runtime_role():
            member, auth, _ = self.checkout(c)
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_membershippublicacceptance SET customer_revision=99 WHERE purchase_id=%s",
                    [member.pk],
                )
        customer = Customer.objects.create(last_name="Other", phone="2025550104")
        other_prior = self.prior(customer=customer)
        other_link, _ = create_link(actor=self.staff, prior=other_prior, request_key=uuid.uuid4())
        with self.assertRaisesMessage(DatabaseError, "scope does not match"), transaction.atomic():
            MembershipPublicAcceptance.objects.create(
                purchase=member,
                link=other_link,
                card_authorization=auth,
                proof_hash="a" * 64,
                customer_revision=1,
                verified_at=timezone.now(),
            )

    def test_disabling_memberships_or_stopping_unstarted_renewal_blocks_dispatch(self):
        c = self.context()
        member, _, _ = self.checkout(c)
        op = member.installments.first().invoice.sale.operations.get()
        with override_settings(MEMBERSHIP_SALES_ENABLED=False), self.assertRaises(ValidationError):
            begin_dispatch(op.pk)
        state = member.billing_state
        state.stopped_on = member.membership.starts_on
        state.save(update_fields=["stopped_on"])
        with self.assertRaises(ValidationError):
            begin_dispatch(op.pk)
        op.refresh_from_db()
        self.assertEqual(op.state, "ready")


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
class PublicMembershipRaceTests(TransactionTestCase):
    def setUp(self):
        from core.models import MembershipPricing, PricingPolicy

        MembershipPublicAuthorityTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create(
                subscription="17.99", unlimited="39.99", actor=self.owner
            )
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    buy = MembershipPublicAuthorityTests.buy
    prior = MembershipPublicAuthorityTests.prior
    context = MembershipPublicAuthorityTests.context
    authorize_card = MembershipPublicAuthorityTests.authorize_card

    def race(self, same_link):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL customer-lock integration")
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections, connections

        prior = self.prior()
        first = self.context(prior)
        second = (
            self.context(prior)
            if not same_link
            else first
            | dict(
                proof=verify_identity(
                    token=first["token"],
                    phone=self.customer.phone,
                    last_name=self.customer.last_name,
                )
            )
        )
        payloads = []
        for context in (first, second):
            context["values"]["places"] = 2
            data, auth = self.authorize_card(context)
            payloads.append(
                dict(
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
            )
        barrier = Barrier(2)

        def attempt(payload):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET LOCAL lock_timeout='10s'")
                        return submit(**payload).pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, payloads))
        self.assertEqual(MembershipPublicAcceptance.objects.count(), 1)
        self.assertEqual(MembershipPurchase.objects.filter(source="public").count(), 1)
        self.assertEqual(PaymentOperation.objects.filter(actor__isnull=True).count(), 1)
        if same_link:
            self.assertIsNotNone(results[0])
            self.assertEqual(results[0], results[1])
        else:
            self.assertEqual(results.count(None), 1, results)

    def test_simultaneous_links_cannot_renew_more_places_than_the_original_cohort(self):
        self.race(same_link=False)

    def test_simultaneous_browsers_on_one_link_return_one_purchase_and_one_payment(self):
        self.race(same_link=True)
