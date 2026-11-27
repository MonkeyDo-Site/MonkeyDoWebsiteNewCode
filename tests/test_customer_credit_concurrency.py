import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core.customer_credit import apply, balance, review
from core.customer_credit_records import CustomerCreditApplication, CustomerCreditIssue
from core.membership_conversion import convert
from core.membership_conversion import review as conversion_review
from core.models import MembershipPricing, PaymentOperation, PricingPolicy
from core.payments.ledger import request_operation
from tests import test_customer_credit as credit_fixtures
from tests import test_membership_cancellations as cancellation_fixtures
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
class CustomerCreditRaceTests(TransactionTestCase):
    flow = credit_fixtures.CustomerCreditTests.flow
    card = credit_fixtures.CustomerCreditTests.card
    save_card = credit_fixtures.CustomerCreditTests.save_card
    booking = credit_fixtures.CustomerCreditTests.booking
    arrival_inputs = credit_fixtures.CustomerCreditTests.arrival_inputs
    create = credit_fixtures.CustomerCreditTests.create
    gateway = credit_fixtures.CustomerCreditTests.gateway
    ready = credit_fixtures.CustomerCreditTests.ready
    member = credit_fixtures.CustomerCreditTests.member
    act = credit_fixtures.CustomerCreditTests.act
    paid_visit = credit_fixtures.CustomerCreditTests.paid_visit
    conversion = credit_fixtures.CustomerCreditTests.conversion
    race = cancellation_fixtures.MembershipCancellationRaceTests.race

    def setUp(self):
        credit_fixtures.CustomerCreditTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create()
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def test_two_installments_cannot_both_spend_the_same_credit(self):
        _, _, member, _ = self.conversion()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=65)):
            dues = list(member.installments.filter(number__gt=1))

            def confirmation(item):
                data = review(actor=self.staff, member_id=member.pk, installment_id=item.pk)
                return lambda: apply(
                    actor=self.staff,
                    member_id=member.pk,
                    installment_id=item.pk,
                    reviewed=data["fingerprint"],
                    request_key=uuid.uuid4(),
                    confirmed=True,
                )

            results = self.race(confirmation(dues[0]), confirmation(dues[1]))
            self.assertEqual(sum(result is not None for result in results), 1)
            self.assertEqual(CustomerCreditApplication.objects.count(), 1)
            self.assertEqual(balance(member.customer_id), 0)

    def test_conversion_and_original_refund_cannot_reserve_the_same_paid_funds(self):
        booking, sale = self.paid_visit()
        member = self.member()
        data = conversion_review(actor=self.staff, booking_id=booking.pk, member_id=member.pk)
        original = sale.operations.get()
        row = original.allocation[0] | dict(net="1.00", fee="0.00", item_tax="0.00", fee_tax="0.00")
        results = self.race(
            lambda: convert(
                actor=self.staff,
                booking_id=booking.pk,
                member_id=member.pk,
                reviewed=data["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
            ),
            lambda: request_operation(
                actor=self.owner,
                sale_id=sale.pk,
                request_key=uuid.uuid4(),
                tender="cash",
                kind="refund",
                original_id=original.pk,
                allocation=[row],
                purpose="correction",
            ),
        )
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertNotEqual(
            CustomerCreditIssue.objects.exists(),
            PaymentOperation.objects.filter(kind="refund").exists(),
        )

    def test_credit_application_cannot_race_an_old_full_amount_dispatch(self):
        from core.membership_payments import collect_installment, payment_review
        from core.payments.operations import begin_dispatch

        _, _, member, _ = self.conversion()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            item = member.installments.order_by("number")[1]
            values = dict(actor=self.staff, member_id=member.pk, installment_id=item.pk)
            payment = payment_review(**values, tender="card")
            queued = collect_installment(
                **values,
                tender="card",
                reviewed=payment["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
            )
            credit = review(**values)
            results = self.race(
                lambda: apply(
                    **values,
                    reviewed=credit["fingerprint"],
                    request_key=uuid.uuid4(),
                    confirmed=True,
                ),
                lambda: begin_dispatch(queued.operation_id),
            )
            self.assertEqual(sum(result is not None for result in results), 1)
            queued.operation.refresh_from_db()
            if CustomerCreditApplication.objects.exists():
                self.assertEqual(queued.operation.state, "cancelled")
                self.assertEqual(balance(member.customer_id), 0)
            else:
                self.assertEqual(queued.operation.state, "sending")
                self.assertEqual(str(balance(member.customer_id)), "15.99")
