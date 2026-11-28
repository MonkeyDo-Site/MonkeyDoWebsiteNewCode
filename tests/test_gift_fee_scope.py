"""Gift receipt restrictions hold at preview, confirmation and database boundaries."""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.customer_credit import applied, balance
from core.models import FinancialLineAdjustment, FinancialPosting, PaymentOperation, PricingPolicy
from core.payments import remainders
from core.payments.amounts import ZERO
from core.payments.invoices import received
from core.payments.ledger import record_manual, record_result, request_operation
from tests import test_membership_arrival_returns as pending
from tests import test_visit_credit as credit
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class GiftFeeScopeTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    def prepare(self):
        PricingPolicy.objects.create(
            child_price=Decimal("15"),
            extra_adult_price=Decimal("5"),
            minimum_admission=Decimal("15"),
            supervised_price=Decimal("18.99"),
            tax_rate=Decimal(".066"),
            card_fee_rate=Decimal(".03"),
        )
        self.play = self.booking(children=2)
        self.inputs = self.arrival_inputs(
            self.play, children=1, method="gift_card", gift_card_verified=True
        )
        return self.play

    def accepted(self, **changes):
        return self.act(self.play, self.inputs | changes)

    def fee_allocation(self, sale):
        line = sale.lines.get(category="partial_cancellation")
        return [dict(line=str(line.pk), net="3.00", fee="0.00", item_tax="0.00", fee_tax="0.00")]

    def test_actual_gift_receipt_covers_goods_and_only_the_fee_reaches_card(self):
        self.prepare()
        with self.runtime_role():
            saved = self.accepted()
        gift = saved.sale.operations.get(tender="gift_card")
        card = saved.sale.operations.get(tender="card")
        self.assertEqual((gift.amount, card.amount), (Decimal("15.99"), Decimal("3.09")))
        self.assertEqual(received(saved.sale), Decimal("15.99"))
        fee = str(saved.sale.lines.get(category="partial_cancellation").pk)
        self.assertTrue(
            all(
                Decimal(part[key]) == ZERO
                for part in gift.allocation
                if part["line"] == fee
                for key in ["net", "fee", "item_tax", "fee_tax"]
            )
        )
        self.assertEqual(saved.sale.processing_fee, Decimal(".09"))
        self.assertEqual(saved.sale.lines.get(category="partial_cancellation").fee_tax, 0)

    def test_direct_confirmation_requires_actual_gift_verification_before_any_receipt(self):
        self.prepare()
        with self.assertRaisesMessage(ValidationError, "Verify any newly received"):
            self.accepted(gift_card_verified=False)
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())

    def test_native_page_reviews_the_actual_gift_amount_and_fee_card_on_the_same_screen(self):
        self.prepare()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        form = page.context["form"]
        values = {
            name: form[name].value() if form[name].value() is not None else ""
            for name in form.fields
        }
        values.update(
            children="1", method="gift_card", gift_card_verified="on", waiver_confirmed="yes"
        )
        proposal = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(proposal.status_code, 200, proposal.content)
        self.assertTrue(proposal.json()["can_confirm"])
        self.assertEqual(proposal.json()["gift_limit"], "15.99")
        self.assertIn("Cancellation fees use a separate payment method", proposal.json()["html"])
        self.assertIn("$3.09", proposal.json()["label"])
        values.update(confirm_review="1", reviewed_hash=proposal.json()["hash"])
        final = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(final.status_code, 200, final.content)
        self.assertEqual(
            PaymentOperation.objects.filter(tender="gift_card").get().amount, Decimal("15.99")
        )
        self.assertEqual(
            PaymentOperation.objects.filter(tender="card").get().amount, Decimal("3.09")
        )

    def test_invalid_gift_amount_returns_eligible_shortcut_limit_without_writing_money(self):
        self.prepare()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        form = page.context["form"]
        values = {
            name: form[name].value() if form[name].value() is not None else ""
            for name in form.fields
        }
        values.update(children="1", method="split", gift_card_amount="16", waiver_confirmed="yes")
        response = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["can_confirm"])
        self.assertEqual(response.json()["gift_limit"], "15.99")
        self.assertEqual(response.json()["noncard_total"], "18.99")
        self.assertFalse(PaymentOperation.objects.exists())

    def test_service_and_raw_operation_inserts_reject_gift_money_on_fee_components(self):
        self.prepare()
        saved = self.accepted(method="card")
        card = saved.sale.operations.get(tender="card")
        record_result(
            operation_id=card.pk, state="declined", source="provider", provider_reference="448111"
        )
        values = dict(
            actor=self.staff,
            sale_id=saved.sale.pk,
            tender="gift_card",
            allocation=self.fee_allocation(saved.sale),
            purpose="follow_up",
        )
        with self.assertRaisesMessage(ValidationError, "Gift-card payments cannot cover"):
            request_operation(**values, request_key=uuid.uuid4())
        for component in ("net", "fee", "item_tax", "fee_tax"):
            allocation = self.fee_allocation(saved.sale)
            allocation[0]["net"] = "0.00"
            allocation[0][component] = "0.01"
            with (
                self.subTest(component=component),
                self.assertRaisesMessage(DatabaseError, "Gift-card payments cannot cover"),
                transaction.atomic(),
            ):
                PaymentOperation.objects.create(
                    sale=saved.sale,
                    request_key=uuid.uuid4(),
                    fingerprint="f" * 64,
                    actor=self.staff,
                    kind="receipt",
                    tender="gift_card",
                    amount=".01",
                    allocation=allocation,
                    purpose="follow_up",
                )
        self.assertFalse(saved.sale.operations.filter(tender="gift_card").exists())
        self.assertFalse(FinancialPosting.objects.exists())

    def test_followup_gift_preview_cannot_claim_a_remaining_cancellation_fee(self):
        self.prepare()
        saved = self.accepted(method="card")
        card = saved.sale.operations.get(tender="card")
        record_result(
            operation_id=card.pk, state="declined", source="provider", provider_reference="448112"
        )
        with self.assertRaisesMessage(ValidationError, "Gift-card payments cannot cover"):
            remainders.preview(actor=self.staff, booking_id=self.play.pk, method="gift_card")
        _, _, facts, _, _ = remainders.preview(
            actor=self.staff, booking_id=self.play.pk, method="cash"
        )
        self.assertEqual(facts["amount"], "18.99")
        self.assertFalse(FinancialLineAdjustment.objects.filter(line__sale=saved.sale).exists())

    def test_gift_followup_still_covers_goods_if_the_fee_was_already_paid(self):
        self.prepare()
        saved = self.accepted(method="card")
        card = saved.sale.operations.get(tender="card")
        record_result(
            operation_id=card.pk, state="declined", source="provider", provider_reference="448113"
        )
        cash = request_operation(
            actor=self.staff,
            sale_id=saved.sale.pk,
            tender="cash",
            allocation=self.fee_allocation(saved.sale),
            request_key=uuid.uuid4(),
        )
        record_manual(actor=self.staff, operation_id=cash.pk, received=True)
        _, _, facts, digest, _ = remainders.preview(
            actor=self.staff, booking_id=self.play.pk, method="gift_card"
        )
        self.assertEqual(facts["amount"], "15.99")
        result = remainders.confirm(
            actor=self.staff,
            booking_id=self.play.pk,
            method="gift_card",
            context="follow_up",
            request_key=uuid.uuid4(),
            reviewed_hash=digest,
            confirmed=True,
        )
        self.assertEqual(result.sale.operations.get(tender="gift_card").amount, Decimal("15.99"))
        self.assertEqual(received(result.sale), Decimal("18.99"))

    prepare_credit = credit.VisitCreditTests.prepare
    complete_credit = credit.VisitCreditTests.complete

    def test_existing_credit_and_gift_money_leave_only_cash_for_the_cancellation_fee(self):
        self.prepare_credit(booked_children=3, value="10", method="split")
        self.inputs.update(
            children=2, split={"gift_card": "5.99", "cash": "3"}, gift_card_verified=True
        )
        saved = self.complete_credit()
        self.assertEqual(applied(saved.sale), Decimal("10"))
        self.assertEqual(balance(self.customer.pk), Decimal("6.02"))
        self.assertEqual(received(saved.sale), Decimal("8.99"))
        self.assertEqual(
            set(saved.sale.operations.values_list("tender", flat=True)), {"gift_card", "cash"}
        )
        fee = str(saved.sale.lines.get(category="partial_cancellation").pk)
        gift = saved.sale.operations.get(tender="gift_card")
        self.assertTrue(
            all(Decimal(row["net"]) == 0 for row in gift.allocation if row["line"] == fee)
        )


@override_settings(**SETTINGS)
class PendingGiftFeeTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = pending.PendingReturnTests.prepare
    start = pending.PendingReturnTests.start
    mixed = pending.PendingReturnTests.mixed
    accept = pending.PendingReturnTests.accept
    result = pending.PendingReturnTests.result
    paid = pending.PendingReturnTests.paid
    give_back = pending.PendingReturnTests.give_back
    owner_finish = pending.PendingReturnTests.owner_finish

    def test_unused_gift_is_returned_before_a_fee_only_pending_arrival_can_finish(self):
        self.paid()
        self.give_back(self.intent.visit_receipts.get(tender="cash"), "3")
        self.give_back(self.intent.visit_receipts.get(tender="check"), "1")
        before = PaymentOperation.objects.count()
        with self.assertRaisesMessage(ValidationError, "Gift-card amount exceeds"):
            self.owner_finish(children=2)
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertFalse(self.intent.visit_receipts.filter(application__isnull=False).exists())
        self.give_back(self.intent.visit_receipts.get(tender="gift_card"), "1")
        arrival = self.owner_finish(children=2)
        self.assertFalse(arrival.sale.operations.filter(tender="gift_card").exists())
        self.assertEqual(arrival.sale.operations.get(tender="card").amount, Decimal("1.03"))
        self.assertEqual(received(arrival.sale), Decimal("2"))
