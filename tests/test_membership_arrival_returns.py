import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core import membership_arrival_recovery as recovery
from core.membership_arrival import receipt_summary
from core.membership_arrival_pending import complete
from core.membership_arrival_receipts import summary
from core.membership_arrival_returns import record, review
from core.membership_records import (
    MembershipArrivalCheckout,
    MembershipArrivalReceiptApplication,
    MembershipArrivalReceiptReturn,
)
from core.models import PaymentOperation
from core.payments.ledger import record_result
from tests import test_membership_arrival_receipts as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PendingReturnTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PendingVisitReceiptTests.prepare
    start = fixtures.PendingVisitReceiptTests.start
    mixed = fixtures.PendingVisitReceiptTests.mixed
    accept = fixtures.PendingVisitReceiptTests.accept
    result = fixtures.PendingVisitReceiptTests.result

    def paid(self):
        self.mixed()
        self.accept()
        self.result()
        self.cash = self.intent.visit_receipts.get(tender="cash")
        recovery.begin_review(actor=self.owner, intent_id=self.intent.pk)
        self.intent.refresh_from_db()

    def give_back(self, source=None, value="2", key=None, **changes):
        source = source or self.cash
        current = review(actor=self.owner, receipt_id=source.pk)
        return record(
            **(
                dict(
                    actor=self.owner,
                    receipt_id=source.pk,
                    request_key=key or uuid.uuid4(),
                    value=value,
                    completed_on=timezone.localdate(),
                    reviewed_hash=current["fingerprint"],
                    confirmed=True,
                    verified_returned=True,
                )
                | changes
            )
        )

    def owner_finish(self, **changes):
        self.intent.refresh_from_db()
        data = (
            self.input
            | dict(
                pending_review=self.intent.pk,
                pending_reason="Review remaining received funds",
                method="card",
                split={},
                zelle_verified=False,
                gift_card_verified=False,
            )
            | changes
        )
        current = recovery.preview(actor=self.owner, intent=self.intent, data=data)[0]
        result = recovery.confirm(
            actor=self.owner,
            intent_id=self.intent.pk,
            data=data,
            request_key=uuid.uuid4(),
            reviewed_hash=current[-1],
            confirmed=True,
        )
        return result

    def test_partial_actual_return_preserves_source_and_applies_only_remainder(self):
        self.paid()
        with self.runtime_role():
            self.give_back()
        self.assertEqual(self.intent.visit_receipts.get(tender="cash").amount, Decimal("3"))
        self.assertEqual(summary(self.intent)["returned"], Decimal("2"))
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))
        self.assertEqual(complete(self.intent.pk).status, "review")
        self.assertEqual(PaymentOperation.objects.count(), 3)
        with self.runtime_role():
            arrival = self.owner_finish()
        self.cash.refresh_from_db()
        self.assertEqual(self.cash.application.operation.amount, Decimal("1"))
        self.assertEqual(arrival.sale.operations.get(tender="card").amount, Decimal("11.32"))
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        saved = MembershipArrivalCheckout.objects.get(pk=self.intent.pk)
        card = arrival.sale.operations.get(tender="card")
        record_result(
            operation_id=card.pk, state="succeeded", source="provider", provider_reference="448010"
        )
        self.assertEqual(receipt_summary(saved)["new_received"], Decimal("52.93"))

    def test_only_owner_can_record_actual_return_after_confirmed_membership_funding(self):
        self.paid()
        with self.assertRaises(PermissionDenied):
            review(actor=self.staff, receipt_id=self.cash.pk)
        with self.assertRaises(ValidationError):
            self.give_back(verified_returned=False)
        with self.assertRaises(ValidationError):
            self.give_back(value="4")
        self.assertFalse(MembershipArrivalReceiptReturn.objects.exists())

    def test_repeated_confirmation_reuses_return_without_second_money_out(self):
        self.paid()
        key = uuid.uuid4()
        current = review(actor=self.owner, receipt_id=self.cash.pk)
        first = self.give_back(key=key)
        replay = self.give_back(key=key, reviewed_hash=current["fingerprint"])
        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))

    def test_owner_records_return_on_pending_page_then_reviews_remaining_funds_without_new_proofs(
        self,
    ):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.paid()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        self.assertContains(page, "Record returned visit funds")
        values = page.context["return_form"].initial | dict(
            receipt=str(self.cash.pk),
            amount="2",
            completed_on=str(timezone.localdate()),
            verified_returned="on",
            record_visit_return="1",
        )
        saved = self.client.post(url, values)
        self.assertEqual(saved.status_code, 302)
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        pending = self.client.get(url)
        self.assertContains(pending, "Visit funds remaining")
        self.assertContains(pending, "$5.00")
        self.assertNotContains(pending, "Visit card after membership funding")
        self.client.post(url, dict(start_owner_review="1"))
        page = self.client.get(url + "?review_pending=1")
        self.assertEqual(page.status_code, 200)
        form = page.context["form"]
        data = {
            name: form[name].value() if form[name].value() is not None else ""
            for name in form.fields
        }
        data.update(
            method="card",
            waiver_confirmed="yes",
            waiver_mismatch_accepted="yes",
            pending_reason="Review actual returned funds",
        )
        quote = self.client.post(url + "?review_pending=1", data, HTTP_ACCEPT="application/json")
        self.assertEqual(quote.status_code, 200, quote.content)
        self.assertTrue(quote.json()["can_confirm"])
        self.assertIn("apply received visit funds $5.00", quote.json()["label"])
        self.assertIn("charge card $11.32", quote.json()["label"])
        self.assertIn("Card to charge", quote.json()["html"])
        self.assertNotIn("New Card received", quote.json()["html"])
        data.update(confirm_review="1", reviewed_hash=quote.json()["hash"])
        result = self.client.post(url + "?review_pending=1", data, HTTP_ACCEPT="application/json")
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(self.cash.application.operation.amount, Decimal("1"))

    def test_return_controls_require_explicit_owner_pause_before_actual_return(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.mixed()
        self.accept()
        self.result()
        source = self.intent.visit_receipts.get(tender="cash")
        with self.assertRaisesMessage(ValidationError, "Start a fresh owner review"):
            review(actor=self.owner, receipt_id=source.pk)
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        self.assertNotContains(self.client.get(url), "Record completed return")
        held = self.client.post(url, dict(start_owner_review="1"))
        self.assertEqual(held.status_code, 302)
        page = self.client.get(held.url)
        self.assertContains(page, "Record completed return")
        self.assertContains(page, 'id="id_return_amount"')
        self.assertEqual(complete(self.intent.pk).code, "owner_review_requested")
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())

    def test_unconfirmed_membership_cannot_authorize_unused_visit_return(self):
        self.mixed()
        self.accept()
        self.result("unknown")
        source = self.intent.visit_receipts.get(tender="cash")
        with self.assertRaisesMessage(ValidationError, "Confirm the existing membership payment"):
            review(actor=self.owner, receipt_id=source.pk)
        with self.assertRaises(ValidationError):
            recovery.begin_review(actor=self.owner, intent_id=self.intent.pk)
        self.assertFalse(MembershipArrivalReceiptReturn.objects.exists())
        self.assertEqual(summary(self.intent)["total"], Decimal("7"))

    def test_full_returns_allow_genuinely_new_cash_without_reapplying_old_receipts(self):
        self.paid()
        for source in self.intent.visit_receipts.all():
            self.give_back(source, str(source.amount))
        self.assertEqual(summary(self.intent)["total"], 0)
        arrival = self.owner_finish(method="split", split=dict(cash="5"))
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())
        self.assertEqual(arrival.sale.operations.get(tender="cash").amount, Decimal("5"))
        self.assertEqual(summary(self.intent)["gross"], Decimal("7"))
        self.assertEqual(summary(self.intent)["returned"], Decimal("7"))

    def test_new_zelle_above_remaining_source_needs_its_own_proof_and_date(self):
        self.paid()
        source = self.intent.visit_receipts.get(tender="zelle")
        self.give_back(source, ".50")
        data = dict(
            method="split",
            split=dict(cash="3", check="2", zelle=".75", gift_card="1"),
            received_on=timezone.localdate(),
            zelle_sender="Fictional additional transfer",
        )
        with self.assertRaises(ValidationError):
            self.owner_finish(**data, zelle_verified=False)
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())
        arrival = self.owner_finish(**data, zelle_verified=True)
        source.refresh_from_db()
        self.assertEqual(source.application.operation.amount, Decimal(".50"))
        self.assertEqual(source.application.operation.manual_received_on, source.received_on)
        new = arrival.sale.operations.get(tender="zelle", amount=Decimal(".25"))
        self.assertEqual(new.manual_received_on, timezone.localdate())
        self.assertEqual(source.received_on, timezone.localdate() - timedelta(days=1))

    def test_return_invalidates_previous_source_budget_and_arrival_review(self):
        self.paid()
        old = review(actor=self.owner, receipt_id=self.cash.pk)
        data = self.input | dict(
            pending_review=self.intent.pk,
            pending_reason="Reviewed before completed return",
            method="card",
            split={},
        )
        price = recovery.preview(actor=self.owner, intent=self.intent, data=data)[0]
        self.give_back()
        with self.assertRaisesMessage(ValidationError, "unused receipt balance changed"):
            self.give_back(value=".50", reviewed_hash=old["fingerprint"])
        with self.assertRaisesMessage(ValidationError, "Review its current total again"):
            recovery.confirm(
                actor=self.owner,
                intent_id=self.intent.pk,
                data=data,
                request_key=uuid.uuid4(),
                reviewed_hash=price[-1],
                confirmed=True,
            )
        self.assertFalse(MembershipArrivalReceiptApplication.objects.exists())

    def test_exact_return_replay_after_arrival_remains_one_immutable_fact(self):
        self.paid()
        old = review(actor=self.owner, receipt_id=self.cash.pk)
        key = uuid.uuid4()
        first = self.give_back(key=key)
        self.owner_finish()
        replay = record(
            actor=self.owner,
            receipt_id=self.cash.pk,
            request_key=key,
            value="2",
            completed_on=first.completed_on,
            reviewed_hash=old["fingerprint"],
            confirmed=True,
            verified_returned=True,
        )
        self.assertEqual(first.pk, replay.pk)
        with self.assertRaises(ValidationError):
            review(actor=self.owner, receipt_id=self.cash.pk)
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)

    def test_database_rejects_wrong_actor_date_stale_budget_and_mutated_return_history(self):
        self.paid()
        values = dict(
            receipt=self.cash,
            actor=self.owner,
            fingerprint="f" * 64,
            amount=Decimal("2"),
            reviewed_available=Decimal("3"),
            completed_on=timezone.localdate(),
        )
        for changed in [
            dict(actor=self.staff),
            dict(reviewed_available=Decimal("4")),
            dict(amount=Decimal("4"), reviewed_available=Decimal("4")),
            dict(completed_on=self.cash.received_on - timedelta(days=1)),
            dict(completed_on=timezone.localdate() + timedelta(days=1)),
            dict(fingerprint="short"),
        ]:
            with (
                self.subTest(changed=changed),
                self.assertRaises(DatabaseError),
                transaction.atomic(),
            ):
                MembershipArrivalReceiptReturn.objects.create(
                    **(values | changed), request_key=uuid.uuid4()
                )
        returned = self.give_back()
        for statement in [
            "UPDATE core_membershiparrivalreceiptreturn SET amount=1 WHERE id=%s",
            "DELETE FROM core_membershiparrivalreceiptreturn WHERE id=%s",
        ]:
            with self.assertRaisesMessage(DatabaseError, "immutable"), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(statement, [returned.pk])
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))

    def test_return_preserves_private_arrival_entries_without_recreating_returned_cash(self):
        from django.urls import reverse

        from core.payments import arrival_drafts
        from tests.helpers import verified_owner_login

        self.paid()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url + "?review_pending=1")
        token = page.context["arrival_draft"]
        form = page.context["form"]
        fields = {
            name: str(form[name].value()) if form[name].value() is not None else ""
            for name in form.fields
        }
        fields.update(
            babies="1",
            method="split",
            cash_amount="5",
            pending_reason="Two extra cash dollars actually received",
            split_rows='[{"method":"cash","amount":"5"}]',
            zelle_verified="on",
            gift_card_verified="on",
        )
        values = page.context["return_form"].initial | dict(
            receipt=str(self.cash.pk),
            amount="2",
            completed_on=str(timezone.localdate()),
            verified_returned="on",
            record_visit_return="1",
            arrival_draft=token,
            arrival_fields=json.dumps(fields),
        )
        for _ in range(2):
            result = self.client.post(url, values)
            self.assertRedirects(result, url + "?draft=" + token)
            draft = self.client.session[arrival_drafts.KEY][token]
            self.assertEqual(draft["fields"]["babies"], "1")
            self.assertEqual(draft["fields"]["cash_amount"], "3.00")
            self.assertEqual(draft["fields"]["split_rows"], "")
            self.assertFalse(draft["fields"]["zelle_verified"])
            self.assertFalse(draft["fields"]["gift_card_verified"])
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))

    def test_an_expired_or_unrelated_arrival_draft_cannot_record_a_return(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.paid()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        values = page.context["return_form"].initial | dict(
            receipt=str(self.cash.pk),
            amount="2",
            completed_on=str(timezone.localdate()),
            verified_returned="on",
            record_visit_return="1",
            arrival_draft=str(uuid.uuid4()),
        )
        result = self.client.post(url, values)
        self.assertContains(result, "arrival draft expired")
        self.assertFalse(MembershipArrivalReceiptReturn.objects.exists())
