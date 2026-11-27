"""Actually received visit money is durable while first membership funding waits."""

import copy
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.membership_arrival import receipt_summary
from core.membership_arrival_pending import complete, fresh_preview, status_data
from core.membership_arrival_receipts import summary
from core.membership_records import (
    MembershipArrivalCheckout,
    MembershipArrivalIntent,
    MembershipArrivalReceipt,
    MembershipArrivalReceiptApplication,
    MembershipPurchase,
)
from core.models import FinancialPosting, PaymentOperation
from core.payments.invoices import received
from core.payments.ledger import record_result
from core.payments.zelle import facts as bank_facts
from core.payments.zelle import record_receipt
from tests import test_membership_arrival_first_card_split as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PendingVisitReceiptTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.FirstSplitCardArrivalTests.prepare
    start = fixtures.FirstSplitCardArrivalTests.start
    accept = fixtures.FirstSplitCardArrivalTests.accept
    result = fixtures.FirstSplitCardArrivalTests.result

    def mixed(self):
        self.start()
        self.input.update(
            split=dict(cash="3", check="2", zelle="1", gift_card="1"),
            zelle_verified=True,
            gift_card_verified=True,
            zelle_sender="Fictional visit sender",
            received_on=timezone.localdate() - timedelta(days=1),
        )

    def test_received_tenders_apply_once_with_original_dates_after_membership_funding(self):
        self.mixed()
        intent = self.accept()
        self.assertEqual(MembershipArrivalReceipt.objects.count(), 4)
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(status_data(intent)["received"], "22.00")
        self.assertEqual(status_data(intent)["visit_received"], "7.00")
        self.assertEqual(summary(intent)["total"], Decimal("7"))
        json.dumps(status_data(intent), cls=DjangoJSONEncoder)
        self.play.refresh_from_db()
        self.assertEqual(self.play.attendance, "")
        self.assertFalse(self.play.membership_benefits.exists())
        fresh_preview(MembershipArrivalIntent.objects.get(pk=intent.pk), proposed=True)
        self.result()
        with self.runtime_role():
            self.assertEqual(complete(intent.pk).status, "completed")
            self.assertEqual(complete(intent.pk).status, "completed")
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        self.assertEqual(MembershipArrivalReceiptApplication.objects.count(), 4)
        self.assertEqual(PaymentOperation.objects.count(), 8)
        for source in intent.visit_receipts.all():
            op = source.application.operation
            self.assertEqual(op.amount, source.amount)
            self.assertEqual(op.tender, source.tender)
            self.assertEqual(op.manual_received_on, source.received_on)
            self.assertEqual(op.state, "succeeded")
        self.assertEqual(received(record.checkout.sale), Decimal("7"))
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("43.61"))
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )
        card = record.checkout.sale.operations.get(tender="card")
        record_result(
            operation_id=card.pk, state="succeeded", source="provider", provider_reference="449797"
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("43.61") + card.amount)
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )

    def test_visit_gift_and_bank_proofs_are_independent_and_fail_before_any_money(self):
        self.mixed()
        for field in ("zelle_verified", "gift_card_verified"):
            with self.subTest(field=field):
                self.input[field] = False
                with self.assertRaises(ValidationError):
                    self.accept()
                self.assertFalse(MembershipPurchase.objects.exists())
                self.assertFalse(MembershipArrivalReceipt.objects.exists())
                self.input[field] = True

    def test_late_receipt_failure_rolls_back_the_whole_confirmation(self):
        from core.membership_arrival_receipts import record

        self.mixed()

        def fail(intent):
            record(intent)
            raise ValidationError("Fictional late receipt failure")

        with (
            patch("core.membership_arrival_receipts.record", side_effect=fail),
            self.assertRaises(ValidationError),
        ):
            self.accept()
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(MembershipArrivalIntent.objects.exists())
        self.assertFalse(MembershipArrivalReceipt.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())

    def test_unknown_membership_result_preserves_all_actual_visit_funds(self):
        self.mixed()
        intent = self.accept()
        self.result("unknown")
        self.assertEqual(complete(intent.pk).status, "review")
        self.assertEqual(status_data(intent)["visit_received"], "7.00")
        self.assertEqual(MembershipArrivalReceipt.objects.count(), 4)
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_expiry_preserves_receipts_and_changed_manual_amount_requires_owner_review(self):
        from core.membership_arrival_recovery import begin_review, preview

        self.mixed()
        intent = self.accept()
        self.result()
        with patch(
            "core.membership_arrival_pending.timezone.now",
            return_value=intent.expires_at + timedelta(minutes=1),
        ):
            self.assertEqual(complete(intent.pk).status, "review")
        begin_review(actor=self.owner, intent_id=intent.pk)
        intent.refresh_from_db()
        data = copy.deepcopy(self.input) | dict(
            pending_review=str(intent.pk), pending_reason="Review original receipts"
        )
        data["split"]["cash"] = "2"
        with self.assertRaisesMessage(ValidationError, "Previously received visit funds"):
            preview(actor=self.owner, intent=intent, data=data)
        self.assertEqual(summary(intent)["total"], Decimal("7"))
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())

    def test_pending_page_and_booking_show_actual_funds_without_claiming_arrival_paid(self):
        self.mixed()
        self.accept()
        self.client.force_login(self.staff)
        page = self.client.get(reverse("booking_arrival", args=[self.play.pk]))
        self.assertContains(page, "Visit funds already received")
        self.assertContains(page, "Fictional visit sender")
        self.assertContains(page, "7.00")
        self.assertContains(page, "visit card payment has not been requested")
        booking = self.client.get(reverse("booking_detail", args=[self.play.pk]))
        self.assertContains(booking, "Visit funds already received:")
        self.assertContains(booking, "$7.00")
        self.assertFalse(MembershipArrivalCheckout.objects.exists())

    def test_raw_scope_and_immutable_source_history_reject_wrong_amount_date_actor_and_application(
        self,
    ):
        self.mixed()
        intent = self.accept()
        source = intent.visit_receipts.get(tender="cash")
        for changed in [
            dict(amount="4"),
            dict(actor=self.owner),
            dict(received_on=source.received_on - timedelta(days=1)),
            dict(sender="forged"),
        ]:
            values = (
                dict(
                    intent=intent,
                    tender=source.tender,
                    amount=source.amount,
                    received_on=source.received_on,
                    sender="",
                    actor=source.actor,
                )
                | changed
            )
            with (
                self.subTest(changed=changed),
                self.assertRaisesMessage(DatabaseError, "does not match"),
                transaction.atomic(),
            ):
                MembershipArrivalReceipt.objects.create(**values)
        for statement in [
            "UPDATE core_membershiparrivalreceipt SET amount=8 WHERE id=%s",
            "DELETE FROM core_membershiparrivalreceipt WHERE id=%s",
        ]:
            with (
                self.assertRaisesMessage(DatabaseError, "immutable"),
                transaction.atomic(),
                connection.cursor() as cur,
            ):
                cur.execute(statement, [source.pk])
        with self.assertRaisesMessage(DatabaseError, "does not match"), transaction.atomic():
            MembershipArrivalReceiptApplication.objects.create(
                receipt=source, operation=intent.operation
            )

    def test_deferred_scope_requires_every_original_tender_before_commit(self):
        self.mixed()
        with (
            self.assertRaisesMessage(DatabaseError, "all original received tenders"),
            transaction.atomic(),
        ):
            with patch("core.membership_arrival_receipts.record"):
                self.accept()
            with connection.cursor() as cur:
                cur.execute("SET CONSTRAINTS core_pending_visit_complete IMMEDIATE")
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(MembershipArrivalReceipt.objects.exists())

    def test_prior_booking_bank_and_new_manual_visit_funds_remain_distinct(self):
        self.start()
        record_receipt(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            value="25",
            sender_name="Fictional prior transfer",
            verified=True,
        )
        self.input.update(
            member_recorded_zelle="20", member_check_amount="0", split=dict(cash="2", check="1")
        )
        intent = self.accept()
        self.assertEqual(status_data(intent)["membership_new_received"], "10.00")
        self.assertEqual(status_data(intent)["visit_received"], "3.00")
        self.assertEqual(status_data(intent)["visit_prepaid"], "5.00")
        self.assertEqual(status_data(intent)["visit_total_received"], "8.00")
        self.assertEqual(status_data(intent)["received"], "38.00")
        self.assertEqual(bank_facts(self.play)["available"], Decimal("5"))
        self.assertEqual(MembershipArrivalReceipt.objects.count(), 2)
        self.result()
        self.assertEqual(complete(intent.pk).status, "completed")
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        self.assertEqual(MembershipArrivalReceiptApplication.objects.count(), 2)
        self.assertEqual(bank_facts(self.play)["available"], 0)
        self.assertEqual(self.play.zelle_receipts.count(), 1)
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("19.16"))
        self.assertEqual(received(record.checkout.sale), Decimal("8"))

    def test_owner_fresh_review_applies_original_receipts_without_changing_their_actor(self):
        from core import membership_arrival_recovery as recovery

        self.mixed()
        intent = self.accept()
        self.result()
        data = self.input | dict(
            pending_review=intent.pk, pending_reason="Review the original received tenders"
        )
        with patch(
            "django.utils.timezone.now", return_value=intent.expires_at + timedelta(seconds=1)
        ):
            recovery.begin_review(actor=self.owner, intent_id=intent.pk)
            intent.refresh_from_db()
            reviewed = recovery.preview(actor=self.owner, intent=intent, data=data)[0]
            with self.runtime_role():
                arrival = recovery.confirm(
                    actor=self.owner,
                    intent_id=intent.pk,
                    data=data,
                    request_key=uuid.uuid4(),
                    reviewed_hash=reviewed[-1],
                    confirmed=True,
                )
        self.assertEqual(arrival.actor_id, self.owner.pk)
        self.assertEqual(
            set(intent.visit_receipts.values_list("actor_id", flat=True)), {self.staff.pk}
        )
        self.assertEqual(MembershipArrivalReceiptApplication.objects.count(), 4)
        self.assertEqual(received(arrival.sale), Decimal("7"))

    def test_all_card_membership_keeps_manual_visit_funds_while_first_card_waits(self):
        self.start()
        self.input.update(member_cash_amount="0", member_check_amount="0", split=dict(cash="10"))
        intent = self.accept()
        self.assertEqual(intent.operation.amount, Decimal("37.06"))
        self.assertEqual(status_data(intent)["membership_received"], "0.00")
        self.assertEqual(status_data(intent)["visit_received"], "10.00")
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.result()
        self.assertEqual(complete(intent.pk).status, "completed")
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        self.assertEqual(received(record.checkout.sale), Decimal("10"))
        self.assertEqual(record.checkout.sale.operations.get(tender="card").amount, Decimal("6.17"))
        self.assertEqual(MembershipArrivalReceiptApplication.objects.count(), 1)

    def test_fully_received_visit_needs_no_visit_card_after_membership_funding(self):
        self.start()
        self.input["split"] = dict(cash="10", check="5.99")
        intent = self.accept()
        self.assertEqual(status_data(intent)["visit_received"], "15.99")
        self.assertEqual(intent.facts["review"]["visit_card_due"], "0.00")
        self.result()
        self.assertEqual(complete(intent.pk).status, "completed")
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        self.assertFalse(record.checkout.sale.operations.filter(tender="card").exists())
        self.assertEqual(received(record.checkout.sale), Decimal("15.99"))
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("52.60"))
        self.assertEqual(MembershipArrivalReceiptApplication.objects.count(), 2)
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )

    def test_deferred_scope_rejects_duplicate_accepted_tender_rows(self):
        from core.membership_arrival import review

        self.mixed()

        def duplicated(**options):
            result = review(**options)
            part = next(p for p in result["facts"]["arrival"]["plan"] if p["tender"] == "cash")
            result["facts"]["arrival"]["plan"].append(copy.deepcopy(part))
            return result

        with (
            self.assertRaisesMessage(DatabaseError, "all original received tenders"),
            transaction.atomic(),
        ):
            with patch("core.membership_arrival.review", side_effect=duplicated):
                self.accept()
            with connection.cursor() as cur:
                cur.execute("SET CONSTRAINTS core_pending_visit_complete IMMEDIATE")
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(MembershipArrivalReceipt.objects.exists())
