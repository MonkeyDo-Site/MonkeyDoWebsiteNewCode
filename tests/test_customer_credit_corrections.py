"""An owner can remove only unused credit and restore only an earlier removal."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core import customer_credit as wallet
from core.customer_credit_corrections import correct, restorables, review
from core.customer_credit_records import (
    CustomerCreditAllocation,
    CustomerCreditApplication,
    CustomerCreditCorrection,
    CustomerCreditCorrectionAllocation,
)
from core.models import AuditEvent, Customer, FinancialPosting, PaymentOperation
from core.payments.invoices import received, settled
from tests import test_customer_credit as fixtures
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin


class CreditFixtures:
    setUp = fixtures.CustomerCreditTests.setUp
    flow = fixtures.CustomerCreditTests.flow
    card = fixtures.CustomerCreditTests.card
    save_card = fixtures.CustomerCreditTests.save_card
    booking = fixtures.CustomerCreditTests.booking
    arrival_inputs = fixtures.CustomerCreditTests.arrival_inputs
    create = fixtures.CustomerCreditTests.create
    gateway = fixtures.CustomerCreditTests.gateway
    ready = fixtures.CustomerCreditTests.ready
    member = fixtures.CustomerCreditTests.member
    act = fixtures.CustomerCreditTests.act
    paid_visit = fixtures.CustomerCreditTests.paid_visit
    conversion = fixtures.CustomerCreditTests.conversion
    due = fixtures.CustomerCreditTests.due
    external_return = fixtures.CustomerCreditTests.external_return

    def correction(self, value, *, kind="remove", original=None, **changes):
        values = dict(actor=self.owner, customer_id=self.customer.pk, kind=kind, value=value)
        if original:
            values["original_id"] = original.pk
        data = review(**values)
        return correct(
            **(
                values
                | dict(
                    reviewed=data["fingerprint"],
                    request_key=uuid.uuid4(),
                    reason="Owner reviewed the credit correction.",
                    confirmed=True,
                )
                | changes
            )
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
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake",
)
class CreditCorrectionTests(CreditFixtures, RuntimeRoleMixin, TestCase):
    def test_owner_and_same_customer_scopes_are_enforced_below_the_service(self):
        _, _, _, conversion = self.conversion()
        removed = self.correction("5.00")
        other = Customer.objects.create(
            last_name="Other", phone="2025550191", email="other-credit@example.invalid"
        )
        values = dict(
            kind="remove",
            amount="1.00",
            reason="Raw permission test",
            fingerprint="raw",
            details={},
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            CustomerCreditCorrection.objects.create(
                id=uuid.uuid4(), customer=self.customer, actor=self.staff, **values
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            CustomerCreditCorrection.objects.create(
                id=uuid.uuid4(),
                customer=other,
                actor=self.owner,
                **(values | dict(kind="restore", original=removed)),
            )
        header = CustomerCreditCorrection.objects.create(
            id=uuid.uuid4(), customer=other, actor=self.owner, **values
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            CustomerCreditCorrectionAllocation.objects.create(
                correction=header, issue=conversion.credits.get(), amount="1.00"
            )
        self.assertEqual(wallet.balance(self.customer.pk), Decimal("10.99"))

    def test_remove_and_restore_preserve_actual_money_and_original_conversion(self):
        _, source, _, conversion = self.conversion(card=True)
        count = FinancialPosting.objects.count(), PaymentOperation.objects.count()
        values = dict(actor=self.owner, customer_id=self.customer.pk, kind="remove", value="5.00")
        data = review(**values)
        self.assertEqual(data["after_available"], "11.02")
        self.assertFalse(CustomerCreditCorrection.objects.exists())
        with self.runtime_role():
            removed = self.correction("5.00")
            self.assertEqual(wallet.balance(self.customer.pk), Decimal("11.02"))
            self.correction("2.00", kind="restore", original=removed)
        self.assertEqual(wallet.balance(self.customer.pk), Decimal("13.02"))
        self.assertEqual(restorables(self.customer.pk).get().unrestored, Decimal("3.00"))
        self.assertEqual(received(source), Decimal("16.47"))
        self.assertEqual(settled(source), Decimal("0.45"))
        self.assertEqual(conversion.credits.get().amount, Decimal("16.02"))
        self.assertEqual(
            count, (FinancialPosting.objects.count(), PaymentOperation.objects.count())
        )
        self.assertEqual(
            AuditEvent.objects.filter(action__startswith="customer.credit_").count(), 2
        )

    def test_restoration_can_follow_spending_but_cannot_exceed_specific_removal(self):
        _, _, member, _ = self.conversion(card=True)
        removed = self.correction("10.00")
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            values = self.due(member)
            data = wallet.review(**values)
            wallet.apply(
                **values, reviewed=data["fingerprint"], request_key=uuid.uuid4(), confirmed=True
            )
        self.assertEqual(wallet.balance(self.customer.pk), 0)
        self.correction("4.00", kind="restore", original=removed)
        self.correction("6.00", kind="restore", original=removed)
        self.assertEqual(wallet.balance(self.customer.pk), Decimal("10.00"))
        with self.assertRaises(ValidationError):
            self.correction("0.01", kind="restore", original=removed)
        self.assertFalse(restorables(self.customer.pk).exists())
        with self.assertRaises(ValidationError):
            self.correction("10.01")

    def test_restoration_does_not_release_a_provider_hold(self):
        _, source, _, _ = self.conversion(card=True)
        removed = self.correction("5.00")
        self.external_return(source.operations.get())
        with self.assertRaises(ValidationError):
            self.correction("1.00")
        self.correction("5.00", kind="restore", original=removed)
        self.assertEqual(wallet.balance(self.customer.pk), 0)
        self.assertEqual(wallet.held_balance(self.customer.pk), Decimal("16.02"))

    def test_permission_feature_recovery_confirmation_and_reason_guards(self):
        self.conversion()
        values = dict(actor=self.owner, customer_id=self.customer.pk, kind="remove", value="5.00")
        with self.assertRaises(PermissionDenied):
            review(**(values | dict(actor=self.staff)))
        with override_settings(MEMBERSHIP_SALES_ENABLED=False), self.assertRaises(ValidationError):
            review(**values)
        for changes in (dict(reason=" "), dict(confirmed=False)):
            with self.assertRaises(ValidationError):
                self.correction("5.00", **changes)
        with override_settings(RECOVERY_HOLD=True), self.assertRaises(ValidationError):
            self.correction("5.00")
        with self.assertRaises(ValidationError):
            self.correction("5.00", kind="restore")
        self.assertFalse(CustomerCreditCorrection.objects.exists())

    def test_stale_review_and_replay_do_not_double_remove(self):
        self.conversion()
        values = dict(actor=self.owner, customer_id=self.customer.pk, kind="remove", value="5.00")
        data = review(**values)
        values |= dict(
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Reviewed.",
            confirmed=True,
        )
        first = correct(**values)
        self.assertEqual(correct(**values).pk, first.pk)
        for change in (dict(request_key=uuid.uuid4()), dict(reason="Changed reason")):
            with self.assertRaises(ValidationError):
                correct(**(values | change))
        self.assertEqual(CustomerCreditCorrection.objects.count(), 1)

    def test_database_prevents_bypassing_removals_and_unbacked_restoration(self):
        _, _, member, conversion = self.conversion()
        self.correction("10.00")
        issue = conversion.credits.get()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            data = wallet.review(**self.due(member))
            from core.membership_sales import invoice_for

            invoice = invoice_for(
                member.installments.order_by("number")[1], actor=self.owner, tender="card"
            )
            application = CustomerCreditApplication.objects.create(
                id=uuid.uuid4(),
                customer=self.customer,
                sale=invoice.sale,
                amount="10.00",
                fingerprint="raw-test",
                details=data,
                actor=self.owner,
            )
            line = invoice.sale.lines.get()
            with self.assertRaises(DatabaseError), transaction.atomic():
                with self.runtime_role():
                    CustomerCreditAllocation.objects.create(
                        application=application,
                        issue=issue,
                        amount="10.00",
                        allocation=[
                            dict(
                                line=str(line.pk),
                                net="10.00",
                                fee="0.00",
                                item_tax="0.00",
                                fee_tax="0.00",
                            )
                        ],
                    )
        removed = CustomerCreditCorrection.objects.get()
        restore = CustomerCreditCorrection.objects.create(
            id=uuid.uuid4(),
            customer=self.customer,
            original=removed,
            kind="restore",
            amount="11.00",
            reason="Raw overrestore test",
            fingerprint="raw-test",
            details={},
            actor=self.owner,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            CustomerCreditCorrectionAllocation.objects.create(
                correction=restore, issue=issue, amount="11.00"
            )
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_customercreditcorrection SET amount=1 WHERE id=%s", [removed.pk]
            )
        self.assertEqual(wallet.balance(self.customer.pk), Decimal("5.99"))
