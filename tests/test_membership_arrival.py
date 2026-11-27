"""The final combined action conserves money and never activates preview benefits."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.communications.models import MessageDelivery
from core.membership_arrival import confirm, review
from core.membership_records import MembershipArrivalCheckout, MembershipPurchase
from core.models import BookingCheckout, FinancialPosting, PaymentOperation
from core.payments.invoices import received
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CombinedMembershipArrivalTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    def prepare(self, *, children=3, places=2, billing="monthly", method="cash"):
        booking = self.booking(children=children)
        clock = patch("django.utils.timezone.now", return_value=booking.session.starts_at)
        clock.start()
        self.addCleanup(clock.stop)
        from core.membership_sales import today

        card = booking.card_agreement.method
        card.reusable = True
        card.save(update_fields=["reusable"])
        self.selection = dict(
            kind="subscription",
            places=places,
            months=3,
            billing=billing,
            starts_on=today(),
        )
        self.input = self.arrival_inputs(booking, method=method, adults=2)
        self.options = dict(
            actor=self.staff,
            booking_id=booking.pk,
            data=self.input,
            selection=self.selection,
            method_id=card.pk if billing == "monthly" else None,
        )
        self.key = uuid.uuid4()
        return booking

    def commit(self, **changes):
        data = review(**self.options)
        return confirm(
            **self.options,
            request_key=self.key,
            reviewed_hash=data["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=True,
            **changes,
        )

    def test_one_cash_confirmation_records_exact_totals_and_one_combined_message_once(self):
        booking = self.prepare()
        messages_before = MessageDelivery.objects.count()
        reviewed = review(**self.options)
        self.assertEqual(reviewed["facts"]["membership_due"], "35.98")
        self.assertEqual(reviewed["facts"]["visit_due"], "15.99")
        self.assertEqual(reviewed["facts"]["received_today"], "51.97")
        with self.runtime_role():
            record = self.commit()
            again = confirm(
                **self.options,
                request_key=self.key,
                reviewed_hash=reviewed["fingerprint"],
                confirmed=True,
                accepted=True,
                verified_received=True,
            )
        self.assertEqual(record.pk, again.pk)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "arrived")
        self.assertEqual(received(record.checkout.sale), Decimal("15.99"))
        member_sale = record.purchase.installments.first().invoice.sale
        self.assertEqual(received(member_sale), Decimal("35.98"))
        self.assertEqual(booking.membership_benefits.filter(current__status="used").count(), 2)
        self.assertEqual(MessageDelivery.objects.count(), messages_before + 1)
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertEqual(message.membership_id, record.purchase_id)
        self.assertEqual(message.booking_id, booking.pk)
        self.assertIn("New payment received: $51.97", message.text_body)
        self.assertNotIn("Book a visit", message.text_body)
        self.assertIn(" - ", message.subject)
        self.assertNotIn(str(booking.session.starts_at.year), message.subject)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(
            sum(PaymentOperation.objects.values_list("amount", flat=True)), Decimal("51.97")
        )

    def test_preview_has_no_financial_or_benefit_side_effects(self):
        booking = self.prepare()
        before = (
            MembershipPurchase.objects.count(),
            PaymentOperation.objects.count(),
            FinancialPosting.objects.count(),
        )
        for _ in range(2):
            reviewed = review(**self.options)
            self.assertEqual(reviewed["quote"]["total"], "15.99")
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
        self.assertFalse(booking.membership_benefits.exists())
        self.assertFalse(MembershipArrivalCheckout.objects.exists())
        self.assertEqual(
            before,
            (
                MembershipPurchase.objects.count(),
                PaymentOperation.objects.count(),
                FinancialPosting.objects.count(),
            ),
        )

    def test_late_failure_rolls_back_both_receipts_purchase_and_arrival(self):
        booking = self.prepare()
        before = MembershipPurchase.objects.count(), MessageDelivery.objects.count()
        with patch(
            "core.membership_arrival.queue_confirmation",
            side_effect=ValidationError("late failure"),
        ):
            with self.assertRaisesMessage(ValidationError, "late failure"):
                self.commit()
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
        self.assertEqual(
            before, (MembershipPurchase.objects.count(), MessageDelivery.objects.count())
        )
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertFalse(BookingCheckout.objects.exists())
        self.assertFalse(booking.membership_benefits.exists())

    def test_changed_attendees_or_membership_price_require_review(self):
        self.prepare()
        reviewed = review(**self.options)
        self.options["data"] = self.input | {"children": 2}
        with self.assertRaisesMessage(ValidationError, "changed"):
            confirm(
                **self.options,
                request_key=self.key,
                reviewed_hash=reviewed["fingerprint"],
                confirmed=True,
                accepted=True,
                verified_received=True,
            )
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_prepaid_check_needs_no_card_and_fully_covered_visit_has_no_zero_receipt(self):
        self.prepare(children=1, places=1, billing="prepaid", method="check")
        record = self.commit()
        self.assertIsNone(record.checkout.sale_id)
        self.assertIsNone(record.purchase.billing_state.mandate_id)
        self.assertEqual(record.facts["received_today"], "53.97")
        self.assertEqual(PaymentOperation.objects.get().tender, "check")

    def test_no_terms_no_received_confirmation_and_no_future_mandate_cannot_partially_save(self):
        self.prepare()
        reviewed = review(**self.options)
        base = dict(
            self.options,
            request_key=self.key,
            reviewed_hash=reviewed["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=True,
        )
        for changes in ({"accepted": False}, {"verified_received": False}, {"method_id": None}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                confirm(**(base | changes))
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_persisted_combined_link_is_immutable_in_database(self):
        self.prepare()
        record = self.commit()
        table = MembershipArrivalCheckout._meta.db_table
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET fingerprint='invalid' WHERE id=%s", [record.pk])

    def web_data(self, booking):
        return {
            **{
                k: v
                for k, v in self.input.items()
                if k not in {"waiver_confirmed", "override_capacity"}
            },
            "waiver_confirmed": "yes",
            "request_key": str(self.key),
            "version": booking.edit_version,
            "member_add": "on",
            "member_kind": self.selection["kind"],
            "member_places": self.selection["places"],
            "member_months": self.selection["months"],
            "member_billing": self.selection["billing"],
            "member_starts_on": self.selection["starts_on"].isoformat(),
            "member_card": str(self.options["method_id"] or ""),
            "member_accepted": "on",
            "member_received": "on",
        }

    def test_same_page_preview_final_confirmation_and_status_include_both_payments(self):
        booking = self.prepare()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[booking.pk])
        initial = self.client.get(url)
        self.assertContains(initial, "Buy a membership with this visit")
        values = self.web_data(booking) | {"arrival_draft": initial.context["arrival_draft"]}
        response = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data["can_confirm"])
        self.assertIn("$51.97", data["html"])
        self.assertIn("three months", data["membership_terms"])
        self.assertFalse(MembershipPurchase.objects.exists())
        result = self.client.post(
            url,
            values | {"confirm_review": "1", "reviewed_hash": data["hash"]},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertTrue(result.json()["confirmed"])
        status = self.client.get(result.json()["status_url"])
        self.assertEqual(status.json()["received"], "51.97")
        self.assertIn("membership confirmed", status.json()["message"])
        detail = self.client.get(reverse("booking_detail", args=[booking.pk]))
        self.assertContains(detail, "Membership purchased with this visit")
        self.assertContains(detail, "New payment received at confirmation: $51.97")
        self.assertContains(detail, "$15.99")
        self.assertNotContains(detail, "Minus cancelled adult admissions")

    def test_paid_price_explanation_preserves_actual_attendees_with_new_adult_allowance(self):
        self.prepare()
        record = self.commit()
        from core.payments.presentation import invoice_breakdown

        displayed = invoice_breakdown(record.checkout.sale)
        self.assertEqual(displayed["membership_attendees"]["adults"], 2)
        self.assertEqual(displayed["membership_attendees"]["children"], 3)

    def test_preview_does_not_enable_final_button_without_terms_or_received_confirmation(self):
        booking = self.prepare()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[booking.pk])
        initial = self.client.get(url)
        values = self.web_data(booking) | {"arrival_draft": initial.context["arrival_draft"]}
        for name in ("member_accepted", "member_received", "member_card"):
            with self.subTest(name=name):
                response = self.client.post(
                    url, values | {name: ""}, HTTP_ACCEPT="application/json"
                )
                self.assertEqual(response.status_code, 200, response.content)
                self.assertFalse(response.json()["can_confirm"])
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_prior_zelle_is_applied_once_and_is_not_new_money_in_combined_message(self):
        booking = self.prepare()
        from core.payments.zelle import record_receipt

        record_receipt(
            actor=self.staff,
            booking_id=booking.pk,
            request_key=uuid.uuid4(),
            value="10.00",
            sender_name="Fictional Parent",
            verified=True,
        )
        record = self.commit()
        self.assertEqual(record.facts["received_today"], "41.97")
        self.assertEqual(record.facts["visit_due"], "5.99")
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("New payment received: $41.97", message.text_body)
        self.assertIn("Previously received Zelle applied to visit: $10.00", message.text_body)

    def test_failed_late_capacity_or_waiver_review_does_not_buy_membership(self):
        self.prepare()
        data = self.options | {"data": self.input | {"children": 5}}
        with self.assertRaisesMessage(ValidationError, "more children"):
            review(**data)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_combined_email_cannot_be_suppressed_without_a_completed_arrival(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL deferred combined-purchase guard")
        booking = self.prepare()
        from core.membership_sales import offer, purchase

        values = dict(
            actor=self.staff, customer=booking.customer, expected_method="cash", **self.selection
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            purchase(
                **values,
                request_key=uuid.uuid4(),
                reviewed=offer(**values)["fingerprint"],
                accepted=True,
                method_id=self.options["method_id"],
                verified_received=True,
                combined_booking=booking,
            )
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS core_membership_combined_link IMMEDIATE")
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_combined_confirmation_respects_a_reported_funding_issue_before_email_delivery(self):
        self.prepare()
        record = self.commit()
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        from core.communications.services import claim

        with patch("core.membership_funding.member_needs_review", return_value=True):
            self.assertIsNone(claim(message.pk))
        message.refresh_from_db()
        self.assertEqual(message.state, "cancelled")
        self.assertEqual(message.code, "membership_funding_review")
        self.assertEqual(record.purchase.confirmation_mode, "combined")
