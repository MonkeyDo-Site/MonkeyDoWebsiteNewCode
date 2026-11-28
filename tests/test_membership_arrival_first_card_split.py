"""Received first-installment parts survive its conditional card/visit sequence."""

import copy
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.communications.models import MessageDelivery
from core.membership_arrival import confirm, receipt_summary, review
from core.membership_arrival_pending import allow_dispatch, complete, fresh_preview, status_data
from core.membership_payments import collect_installment, payment_review
from core.membership_records import MembershipArrivalCheckout, MembershipArrivalIntent
from core.membership_sales import membership_status
from core.models import PaymentOperation
from core.payments.invoices import received
from core.payments.ledger import record_result
from core.payments.zelle import facts, record_receipt
from tests import test_membership_arrival as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class FirstSplitCardArrivalTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.CombinedMembershipArrivalTests.prepare
    web_data = fixtures.CombinedMembershipArrivalTests.web_data

    def start(self, **changes):
        self.play = self.prepare(method="split", **changes)
        self.input.update(
            member_first_method="split", member_cash_amount="10", member_check_amount="5", split={}
        )
        self.options["method_id"] = self.play.card_agreement.method_id
        return self.play

    def accept(self):
        self.accepted = review(**self.options)
        with self.runtime_role():
            self.intent = confirm(
                **self.options,
                request_key=self.key,
                reviewed_hash=self.accepted["fingerprint"],
                confirmed=True,
                accepted=True,
                verified_received=True,
            )
        return self.intent

    def result(self, state="succeeded"):
        return record_result(
            operation_id=self.intent.operation_id,
            state=state,
            source="provider",
            provider_reference="441094",
        )

    def test_one_accepted_first_card_remainder_preserves_manual_money_then_completes_visit_once(
        self,
    ):
        self.start()
        intent = self.accept()
        self.assertIsInstance(intent, MembershipArrivalIntent)
        self.assertEqual(intent.operation.amount, Decimal("21.61"))
        self.assertEqual(intent.facts["review"]["membership_due"], "36.61")
        self.assertEqual(intent.facts["review"]["membership_card_due"], "21.61")
        self.assertEqual(intent.facts["review"]["visit_card_due"], "16.47")
        self.assertEqual(intent.facts["review"]["received_today"], "15.00")
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(received(intent.operation.sale), Decimal("15"))
        self.assertEqual(membership_status(intent.purchase), "pending")
        self.assertFalse(self.play.membership_benefits.exists())
        self.assertTrue(allow_dispatch(intent))
        replay = confirm(
            **self.options,
            request_key=self.key,
            reviewed_hash=self.accepted["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=True,
        )
        self.assertEqual(replay.pk, intent.pk)
        self.result()
        fresh_preview(intent, proposed=False)
        self.assertEqual(complete(intent.pk).status, "completed")
        self.assertEqual(complete(intent.pk).status, "completed")
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("36.61"))
        self.assertEqual(self.play.membership_benefits.filter(current__status="used").count(), 2)
        self.assertEqual(PaymentOperation.objects.count(), 4)
        visit = record.checkout.sale.operations.get(tender="card")
        self.assertEqual(visit.amount, Decimal("16.47"))
        self.assertEqual(visit.method_id, self.play.card_agreement.method_id)
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )
        record_result(
            operation_id=visit.pk, state="succeeded", source="provider", provider_reference="441096"
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("53.08"))
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )
        self.assertEqual(intent.purchase.installments.get(number=2).quote["total"], "37.06")

    def test_recorded_bank_is_not_subtracted_again_before_first_dispatch_or_visit(self):
        self.start()
        record_receipt(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            value="25",
            sender_name="Fictional old bank transfer",
            verified=True,
        )
        self.input.update(member_recorded_zelle="20", member_check_amount="0")
        intent = self.accept()
        self.assertEqual(intent.operation.amount, Decimal("6.16"))
        self.assertEqual(received(intent.operation.sale), Decimal("30"))
        self.assertEqual(facts(self.play)["available"], Decimal("5"))
        self.assertEqual(status_data(intent)["membership_new_received"], "10.00")
        self.assertTrue(allow_dispatch(intent))
        fresh_preview(intent, proposed=True)
        self.result()
        fresh_preview(MembershipArrivalIntent.objects.get(pk=intent.pk), proposed=False)
        self.assertEqual(complete(intent.pk).status, "completed")
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        visit = record.checkout.sale.operations.get(tender="card")
        self.assertEqual(visit.amount, Decimal("11.32"))
        self.assertEqual(facts(self.play)["available"], 0)
        record_result(
            operation_id=visit.pk, state="succeeded", source="provider", provider_reference="441097"
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("27.48"))

    def test_prepaid_first_split_requires_its_card_even_with_no_visit_charge(self):
        self.start(children=1, places=1, billing="prepaid")
        self.input.update(member_cash_amount="50", member_check_amount="0")
        intent = self.accept()
        self.assertEqual(intent.operation.amount, Decimal("4.09"))
        self.assertIsNotNone(intent.purchase.billing_state.mandate_id)
        self.result()
        fresh_preview(intent, proposed=False)
        self.assertEqual(complete(intent.pk).status, "completed")
        self.assertIsNone(MembershipArrivalCheckout.objects.get(pk=intent.pk).checkout.sale_id)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_received_visit_cash_is_saved_before_the_first_card_result(self):
        self.start()
        self.input["split"] = {"cash": "1"}
        intent = self.accept()
        self.assertEqual(intent.visit_receipts.get().amount, Decimal("1"))
        self.assertEqual(status_data(intent)["visit_received"], "1.00")
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_unknown_first_card_keeps_received_money_and_blocks_replacement(self):
        self.start()
        intent = self.accept()
        self.result("unknown")
        first = intent.purchase.installments.first()
        with self.assertRaises(ValidationError):
            payment_review(
                actor=self.staff,
                member_id=intent.purchase_id,
                installment_id=first.pk,
                tender="cash",
            )
        self.assertEqual(status_data(intent)["membership_received"], "15.00")
        self.assertEqual(complete(intent.pk).status, "review")
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertFalse(MembershipArrivalCheckout.objects.exists())

    def test_known_decline_collects_remaining_principal_and_does_not_repeat_manual_parts(self):
        self.start()
        intent = self.accept()
        self.result("declined")
        args = dict(
            actor=self.staff,
            member_id=intent.purchase_id,
            installment_id=intent.purchase.installments.first().pk,
            tender="cash",
        )
        quote = payment_review(**args)
        self.assertEqual(quote["total"], "20.98")
        collect_installment(
            **args,
            request_key=uuid.uuid4(),
            reviewed=quote["fingerprint"],
            confirmed=True,
            verified_received=True,
        )
        self.assertEqual(complete(intent.pk).status, "completed")
        self.assertEqual(received(intent.operation.sale), Decimal("35.98"))
        self.assertEqual(intent.operation.sale.operations.filter(tender="check").count(), 1)

    def test_database_scope_refuses_wrong_remainder_and_unrecorded_visit_manual_parts(self):
        self.start()
        intent = self.accept()
        for change in ("remainder", "visit"):
            data = copy.deepcopy(intent.facts)
            if change == "remainder":
                data["review"]["membership_card_due"] = "36.61"
            else:
                data["review"]["arrival"]["plan"].append(
                    dict(tender="cash", amount="1.00", advance=False)
                )
            with (
                self.subTest(change=change),
                self.assertRaisesMessage(DatabaseError, "scope does not match"),
                transaction.atomic(),
            ):
                MembershipArrivalIntent.objects.create(
                    id=uuid.uuid4(),
                    purchase=intent.purchase,
                    booking=self.play,
                    operation=intent.operation,
                    actor=self.staff,
                    fingerprint=intent.fingerprint,
                    facts=data,
                    hold_key=uuid.uuid4(),
                    accepted_at=intent.accepted_at,
                    expires_at=intent.expires_at,
                )

    def test_same_page_json_reviews_each_card_and_keeps_prepaid_card_requirement(self):
        self.start(children=1, places=1, billing="prepaid")
        self.input.update(member_cash_amount="50", member_check_amount="0")
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        values = self.web_data(self.play) | {"arrival_draft": page.context["arrival_draft"]}
        quote = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(quote.status_code, 200, quote.content)
        self.assertTrue(quote.json()["membership_needs_card"])
        self.assertTrue(quote.json()["can_confirm"])
        self.assertIn("charge membership card $4.09", quote.json()["label"])
        self.assertIn("to charge first", quote.json()["html"])

    def test_funded_manual_membership_can_leave_the_entire_visit_on_its_booking_card(self):
        self.start()
        self.input.update(member_cash_amount="35.98", member_check_amount="0")
        values = review(**self.options)
        record = confirm(
            **self.options,
            request_key=self.key,
            reviewed_hash=values["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=True,
        )
        self.assertIsInstance(record, MembershipArrivalCheckout)
        self.assertEqual(
            received(record.purchase.installments.first().invoice.sale), Decimal("35.98")
        )
        self.assertEqual(
            record.checkout.sale.operations.get(tender="card").amount, Decimal("16.47")
        )
