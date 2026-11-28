"""Converted funds are conserved across the original visit, wallet and installments."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.customer_credit import applied, apply, balance, review
from core.customer_credit_records import (
    CustomerCreditApplication,
    CustomerCreditIssue,
    VisitMembershipConversion,
)
from core.membership_conversion import convert
from core.membership_conversion import review as conversion_review
from core.membership_payments import collect_installment, payment_review
from core.membership_reservations import payment_current
from core.models import FinancialLineAdjustment, FinancialPosting, PaymentOperation
from core.payments.invoices import received, settled, total
from core.payments.ledger import record_result, request_operation
from tests import test_member_booking_integration as fixtures
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
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake",
)
class CustomerCreditTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MemberBookingIntegrationTests.setUp
    flow = fixtures.MemberBookingIntegrationTests.flow
    card = fixtures.MemberBookingIntegrationTests.card
    save_card = fixtures.MemberBookingIntegrationTests.save_card
    booking = fixtures.MemberBookingIntegrationTests.booking
    arrival_inputs = fixtures.MemberBookingIntegrationTests.arrival_inputs
    create = fixtures.MemberBookingIntegrationTests.create
    gateway = fixtures.MemberBookingIntegrationTests.gateway
    ready = fixtures.MemberBookingIntegrationTests.ready
    member = fixtures.MemberBookingIntegrationTests.member
    act = fixtures.MemberBookingIntegrationTests.act

    def paid_visit(self, *, card=False, children=1, adults=1):
        booking = self.booking(children=children)
        result = self.act(
            booking, self.arrival_inputs(booking, method="card" if card else "cash", adults=adults)
        )
        if card:
            record_result(
                operation_id=result.sale.operations.get().pk,
                state="succeeded",
                source="provider",
                provider_reference="451",
            )
        booking.refresh_from_db()
        return booking, result.sale

    def conversion(self, *, card=False, children=1, adults=1):
        booking, sale = self.paid_visit(card=card, children=children, adults=adults)
        member = self.member(places=children, billing="monthly")
        data = conversion_review(actor=self.staff, booking_id=booking.pk, member_id=member.pk)
        record = convert(
            actor=self.staff,
            booking_id=booking.pk,
            member_id=member.pk,
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            confirmed=True,
        )
        return booking, sale, member, record

    def due(self, member):
        item = member.installments.order_by("number")[1]
        return dict(actor=self.staff, member_id=member.pk, installment_id=item.pk)

    def test_paid_cash_conversion_creates_backed_credit_without_receipt_or_refund(self):
        booking, sale, member, _ = self.conversion()
        self.assertEqual(received(sale), Decimal("15.99"))
        self.assertEqual(settled(sale), ZERO := Decimal("0.00"))
        self.assertEqual(total(sale), ZERO)
        self.assertEqual(balance(self.customer.pk), Decimal("15.99"))
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())
        self.assertEqual(
            booking.membership_benefits.filter(current__status="used", purchase=member).count(), 1
        )
        self.assertEqual(FinancialPosting.objects.count(), 2)

    def test_accountant_card_example_retains_fee_and_transfers_both_original_taxes(self):
        _, sale, _, record = self.conversion(card=True)
        self.assertEqual(received(sale), Decimal("16.47"))
        self.assertEqual(balance(self.customer.pk), Decimal("16.02"))
        self.assertEqual(total(sale), Decimal("0.45"))
        self.assertEqual(settled(sale), Decimal("0.45"))
        parts = record.credits.get().allocation[0]
        self.assertEqual(
            parts,
            dict(line=parts["line"], net="15.00", fee="0.00", item_tax="0.99", fee_tax="0.03"),
        )
        self.assertFalse(PaymentOperation.objects.filter(kind__in=["refund", "void"]).exists())

    def test_conversion_review_is_read_only_and_replay_reuses_original_facts(self):
        booking, sale = self.paid_visit()
        member = self.member(billing="monthly")
        data = conversion_review(actor=self.staff, booking_id=booking.pk, member_id=member.pk)
        self.assertFalse(CustomerCreditIssue.objects.exists())
        self.assertEqual(total(sale), Decimal("15.99"))
        values = dict(
            actor=self.staff,
            booking_id=booking.pk,
            member_id=member.pk,
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            confirmed=True,
        )
        with self.assertRaises(ValidationError):
            convert(**(values | dict(reviewed="stale")))
        first = convert(**values)
        self.assertEqual(convert(**values).pk, first.pk)
        self.assertEqual(CustomerCreditIssue.objects.count(), 1)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)

    def test_converted_source_cannot_also_be_refunded(self):
        _, sale, _, _ = self.conversion()
        original = sale.operations.get()
        with self.assertRaises(ValidationError):
            request_operation(
                actor=self.owner,
                sale_id=sale.pk,
                request_key=uuid.uuid4(),
                tender="cash",
                kind="refund",
                original_id=original.pk,
                allocation=original.allocation,
                purpose="correction",
            )
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())

    def test_future_due_credit_application_is_read_only_until_confirmed_and_keeps_excess(self):
        _, _, member, _ = self.conversion(children=2, adults=2)
        now = timezone.now() + timedelta(days=35)
        with patch("django.utils.timezone.now", return_value=now):
            values = self.due(member)
            data = review(**values)
            self.assertEqual(data["available"], "37.31")
            self.assertEqual(data["amount"], "35.98")
            self.assertFalse(CustomerCreditApplication.objects.exists())
            action = apply(
                **values, reviewed=data["fingerprint"], request_key=uuid.uuid4(), confirmed=True
            )
            self.assertEqual(applied(action.sale), Decimal("35.98"))
            self.assertEqual(received(action.sale), Decimal("0.00"))
            self.assertEqual(settled(action.sale), Decimal("35.98"))
            self.assertEqual(total(action.sale), Decimal("35.98"))
            self.assertEqual(balance(self.customer.pk), Decimal("1.33"))
            member.refresh_from_db()
            self.assertTrue(payment_current(member))

    def test_partial_credit_preserves_actual_receipts_and_fees_only_remaining_card_base(self):
        _, _, member, _ = self.conversion(card=True)
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            values = self.due(member)
            data = review(**values)
            self.assertEqual(data["remaining_net"], "1.97")
            self.assertEqual(data["remaining_card_fee"], "0.06")
            self.assertEqual(data["remaining_card_total"], "2.03")
            action = apply(
                **values, reviewed=data["fingerprint"], request_key=uuid.uuid4(), confirmed=True
            )
            reviewed = payment_review(**values, tender="card")
            self.assertEqual(reviewed["total"], "2.03")
            result = collect_installment(
                **values,
                tender="card",
                reviewed=reviewed["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
            )
            self.assertEqual(result.operation.amount, Decimal("2.03"))
            self.assertEqual(received(action.sale), Decimal("0.00"))
            self.assertEqual(applied(action.sale), Decimal("16.02"))
            record_result(
                operation_id=result.operation.pk,
                state="succeeded",
                source="provider",
                provider_reference="452",
            )
            self.assertEqual(received(action.sale), Decimal("2.03"))
            self.assertTrue(payment_current(member))

    def test_unknown_payment_blocks_credit_until_reconciled_without_spending_it(self):
        _, _, member, _ = self.conversion()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            values = self.due(member)
            data = payment_review(**values, tender="card")
            action = collect_installment(
                **values,
                tender="card",
                reviewed=data["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
            )
            record_result(operation_id=action.operation_id, state="unknown", source="provider")
            with self.assertRaises(ValidationError):
                review(**values)
            self.assertEqual(balance(self.customer.pk), Decimal("15.99"))

    def test_runtime_credit_evidence_and_cross_customer_spending_are_guarded(self):
        with self.runtime_role():
            _, _, member, _ = self.conversion()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            values = self.due(member)
            data = review(**values)
            with self.runtime_role():
                action = apply(
                    **values, reviewed=data["fingerprint"], request_key=uuid.uuid4(), confirmed=True
                )
        for model in (CustomerCreditIssue, CustomerCreditApplication, VisitMembershipConversion):
            with self.assertRaises(ValidationError):
                model.objects.all().delete()
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM core_customercreditallocation WHERE application_id=%s", [action.pk]
                )

    def test_unpaid_visit_and_disabled_feature_cannot_create_credit(self):
        booking, sale = self.paid_visit(card=True)
        member = self.member()
        with override_settings(MEMBERSHIP_SALES_ENABLED=False), self.assertRaises(ValidationError):
            conversion_review(actor=self.staff, booking_id=booking.pk, member_id=member.pk)
        self.assertEqual(CustomerCreditIssue.objects.count(), 0)
        self.assertEqual(
            FinancialLineAdjustment.objects.filter(reason="membership_conversion").count(), 0
        )

    def test_unpaid_visit_with_unstarted_card_receipt_cannot_create_credit(self):
        booking = self.booking()
        self.act(booking, self.arrival_inputs(booking, method="card"))
        member = self.member()
        with self.assertRaisesMessage(ValidationError, "Reconcile existing payment"):
            conversion_review(actor=self.staff, booking_id=booking.pk, member_id=member.pk)
        self.assertFalse(CustomerCreditIssue.objects.exists())

    def test_partial_conversion_preserves_uncovered_admission_and_blocks_overissuing_credit(self):
        booking, sale = self.paid_visit(children=2)
        member = self.member(places=1)
        reviewed = conversion_review(actor=self.staff, booking_id=booking.pk, member_id=member.pk)
        conversion = convert(
            actor=self.staff,
            booking_id=booking.pk,
            member_id=member.pk,
            reviewed=reviewed["fingerprint"],
            request_key=uuid.uuid4(),
            confirmed=True,
        )
        self.assertEqual(balance(member.customer_id), Decimal("15.99"))
        self.assertEqual(total(sale), Decimal("15.99"))
        self.assertEqual(settled(sale), Decimal("15.99"))
        issue = conversion.credits.get()
        part = issue.allocation[0] | dict(net="1.00", item_tax="0.00", fee_tax="0.00")
        with self.assertRaises(DatabaseError), transaction.atomic():
            CustomerCreditIssue.objects.create(
                id=uuid.uuid4(),
                conversion=conversion,
                customer=member.customer,
                original=issue.original,
                allocation=[part],
                amount="1.00",
            )

    def test_stale_credit_review_and_changed_replay_do_not_spend_twice(self):
        _, _, member, _ = self.conversion()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            values = self.due(member)
            data = review(**values, value="5.00")
            params = values | dict(
                value="5.00", reviewed=data["fingerprint"], request_key=uuid.uuid4(), confirmed=True
            )
            result = apply(**params)
            self.assertEqual(apply(**params).pk, result.pk)
            with self.assertRaises(ValidationError):
                apply(**(params | dict(value="6.00")))
            with self.assertRaises(ValidationError):
                apply(**(params | dict(request_key=uuid.uuid4())))
            self.assertEqual(balance(member.customer_id), Decimal("10.99"))

    def test_database_rejects_cross_customer_application_and_overfunding_paid_invoice(self):
        from core.customer_credit_records import CustomerCreditAllocation
        from core.models import Customer

        _, _, member, record = self.conversion()
        issue = record.credits.get()
        sale = member.installments.first().invoice.sale
        other = Customer.objects.create(last_name="Other", phone="2025550199")
        with self.assertRaises(DatabaseError), transaction.atomic():
            CustomerCreditApplication.objects.create(
                id=uuid.uuid4(),
                customer=other,
                sale=sale,
                amount="1.00",
                fingerprint="forged",
                details={},
                actor=self.owner,
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            app = CustomerCreditApplication.objects.create(
                id=uuid.uuid4(),
                customer=member.customer,
                sale=sale,
                amount="1.00",
                fingerprint="forged",
                details={},
                actor=self.owner,
            )
            CustomerCreditAllocation.objects.create(
                application=app,
                issue=issue,
                amount="1.00",
                allocation=[
                    dict(
                        line=str(sale.lines.get().pk),
                        net="1.00",
                        fee="0.00",
                        item_tax="0.00",
                        fee_tax="0.00",
                    )
                ],
            )
        self.assertEqual(balance(member.customer_id), Decimal("15.99"))

    def test_credit_expiry_notice_uses_corrected_membership_dates(self):
        from core.availability import NEW_YORK
        from core.customer_credit import expiry_notices
        from core.membership_calendar_changes import confirm as correct_dates
        from core.membership_calendar_changes import review as date_review
        from core.membership_calendar_changes import root_for
        from core.membership_sales import offer, purchase

        booking, _ = self.paid_visit()
        on = timezone.localdate(timezone=NEW_YORK)
        values = dict(
            actor=self.staff,
            customer=self.customer,
            kind="subscription",
            places=1,
            months=3,
            billing="prepaid",
            starts_on=on + timedelta(days=10),
            expected_method="cash",
        )
        member = purchase(
            **values,
            request_key=uuid.uuid4(),
            reviewed=offer(**values)["fingerprint"],
            accepted=True,
            verified_received=True,
        )
        dates = dict(
            actor=self.staff,
            member_id=member.pk,
            starts_on=on,
            reason="The customer confirmed the membership should begin today.",
            send_confirmation=False,
        )
        correct_dates(
            **dates,
            request_key=uuid.uuid4(),
            reviewed=date_review(**dates)["fingerprint"],
            customer_confirmed=True,
        )
        quoted = conversion_review(actor=self.staff, booking_id=booking.pk, member_id=member.pk)
        convert(
            actor=self.staff,
            booking_id=booking.pk,
            member_id=member.pk,
            reviewed=quoted["fingerprint"],
            request_key=uuid.uuid4(),
            confirmed=True,
        )
        corrected_end = root_for(member).ends_on
        self.assertLess(corrected_end, member.membership.ends_on)
        with patch("core.customer_credit.today", return_value=corrected_end + timedelta(days=1)):
            notices = expiry_notices()
        self.assertEqual([notice.customer_id for notice in notices], [self.customer.pk])
        self.assertEqual(notices[0].remaining, Decimal("15.99"))
        self.assertEqual(balance(self.customer.pk), Decimal("15.99"))
        connection.check_constraints()

    def test_expiry_notice_does_not_expire_credit_and_clears_when_spent(self):
        from core.customer_credit import expiry_notices

        _, _, member, _ = self.conversion()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=105)):
            self.assertEqual(expiry_notices()[0].remaining, Decimal("15.99"))
            self.assertEqual(balance(member.customer_id), Decimal("15.99"))
            values = self.due(member)
            data = review(**values)
            apply(**values, reviewed=data["fingerprint"], request_key=uuid.uuid4(), confirmed=True)
            self.assertFalse(expiry_notices())

    def test_split_receipt_credit_cannot_also_be_returned_from_its_original_cash_source(self):
        booking = self.booking(children=2)
        result = self.act(
            booking, self.arrival_inputs(booking, method="split", split={"cash": "10.00"})
        )
        card = result.sale.operations.get(tender="card")
        record_result(
            operation_id=card.pk, state="succeeded", source="provider", provider_reference="451"
        )
        member = self.member(places=1)
        data = conversion_review(actor=self.staff, booking_id=booking.pk, member_id=member.pk)
        conversion = convert(
            actor=self.staff,
            booking_id=booking.pk,
            member_id=member.pk,
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            confirmed=True,
        )
        self.assertEqual(conversion.credits.count(), 2)
        original = result.sale.operations.get(tender="cash")
        row = original.allocation[0] | dict(fee="0.00", item_tax="0.00", fee_tax="0.00")
        with self.assertRaisesMessage(ValidationError, "converted to customer credit"):
            request_operation(
                actor=self.owner,
                sale_id=result.sale.pk,
                request_key=uuid.uuid4(),
                tender="cash",
                kind="refund",
                original_id=original.pk,
                allocation=[row],
                purpose="correction",
            )
        self.assertFalse(PaymentOperation.objects.filter(kind="refund").exists())

    def test_current_price_labels_show_membership_coverage_and_preserve_original_line(self):
        from core.payments.presentation import invoice_breakdown

        _, sale, _, _ = self.conversion(card=True)
        display = invoice_breakdown(sale)
        self.assertIn("Subscription free visits", display["lines"][0]["label"])
        self.assertEqual(display["total"], "0.45")
        self.assertEqual(sale.lines.get().unit_price, Decimal("15.00"))
        self.assertEqual(sale.lines.get().net, Decimal("15.00"))

    def external_return(self, original):
        from core.models import PaymentEvent, ProviderObservation

        ProviderObservation.objects.create(
            operation=original,
            fingerprint=uuid.uuid4().hex,
            provider_reference="999",
            provider_status="external_credit",
            amount="1.00",
        )
        PaymentEvent.objects.create(
            operation=original,
            state="succeeded",
            source="provider",
            code="external_correction_review",
        )

    def test_reported_source_return_holds_unspent_credit_without_erasing_history(self):
        from core.customer_credit import held_balance, hold_notices

        _, sale, member, record = self.conversion(card=True)
        self.external_return(sale.operations.get())
        self.assertEqual(balance(member.customer_id), 0)
        self.assertEqual(held_balance(member.customer_id), Decimal("16.02"))
        self.assertEqual(hold_notices()[0].pk, record.credits.get().pk)
        self.assertEqual(record.credits.get().amount, Decimal("16.02"))
        from core.customer_credit import expiry_notices

        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=105)):
            self.assertFalse(expiry_notices())
        with (
            patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)),
            self.assertRaises(ValidationError),
        ):
            review(**self.due(member))

    def test_reported_source_return_blocks_collection_and_queued_dispatch_of_funded_installment(
        self,
    ):
        from core.membership_sales import membership_status
        from core.payments.operations import begin_dispatch

        _, sale, member, _ = self.conversion(card=True)
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=35)):
            values = self.due(member)
            data = review(**values)
            apply(**values, reviewed=data["fingerprint"], request_key=uuid.uuid4(), confirmed=True)
            quote = payment_review(**values, tender="card")
            queued = collect_installment(
                **values,
                tender="card",
                reviewed=quote["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
            )
            self.external_return(sale.operations.get())
            self.assertEqual(membership_status(member), "review")
            self.assertFalse(payment_current(member))
            with self.assertRaisesMessage(
                ValidationError, "credit source needs owner reconciliation"
            ):
                payment_review(**values, tender="cash")
            self.assertIsNone(begin_dispatch(queued.operation_id))
            queued.operation.refresh_from_db()
            self.assertEqual(queued.operation.state, "cancelled")
            self.assertEqual(applied(queued.operation.sale), Decimal("16.02"))
