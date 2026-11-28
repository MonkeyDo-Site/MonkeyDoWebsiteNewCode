"""Today's paid admissions fund a first membership, with no circular paid-member dependency."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from core.customer_credit import applied, balance
from core.customer_credit_records import CustomerCreditIssue, VisitMembershipConversion
from core.membership_sales import installment_paid, offer, purchase
from core.models import FinancialPosting, MembershipDraft, PaymentOperation
from core.payments.invoices import received, settled, total
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitPurchaseTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    def prepare(self, *, card=False, children=1, adults=1, **changes):
        self.visit, self.original = self.paid_visit(card=card, children=children, adults=adults)
        card_method = self.visit.card_agreement.method
        card_method.reusable = True
        card_method.save(update_fields=["reusable"])
        self.method = card_method
        self.options = (
            self.values(credit="0", expected_method="cash")
            | dict(paid_visit_id=self.visit.pk, places=children)
            | changes
        )
        return self.visit

    def commit(self, *, reviewed=None, key=None, verified=True, **changes):
        options = self.options | changes
        data = offer(**options)
        self.key = key or uuid.uuid4()
        self.saved_offer = data
        return purchase(
            **options,
            request_key=self.key,
            reviewed=reviewed or data["fingerprint"],
            accepted=True,
            verified_received=verified,
            method_id=self.method.pk if options["billing"] == "monthly" else None,
        )

    def test_cash_admission_funds_first_membership_and_only_two_dollars_are_new(self):
        self.prepare()
        data = offer(**self.options)
        self.assertEqual(data["paid_visit"]["applied"], "15.99")
        self.assertEqual(data["first_payment_total"], "2.00")
        self.assertFalse(VisitMembershipConversion.objects.exists())
        with self.runtime_role():
            member = self.commit()
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS core_paid_visit_purchase_complete IMMEDIATE")
            cursor.execute("SET CONSTRAINTS core_paid_visit_purchase_complete DEFERRED")
        first = member.installments.first()
        self.assertEqual(received(self.original), Decimal("15.99"))
        self.assertEqual(total(self.original), 0)
        self.assertEqual(settled(self.original), 0)
        self.assertEqual(applied(first.invoice.sale), Decimal("15.99"))
        self.assertEqual(received(first.invoice.sale), Decimal("2"))
        self.assertTrue(installment_paid(first))
        self.assertEqual(balance(self.customer.pk), 0)
        self.assertEqual(
            self.visit.membership_benefits.filter(purchase=member, current__status="used").count(),
            1,
        )
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(member.installments.get(number=2).quote["total"], "18.53")

    def test_original_card_fee_stays_and_both_original_taxes_fund_the_membership(self):
        self.prepare(card=True)
        data = offer(**self.options)
        self.assertEqual(data["paid_visit"]["applied"], "16.02")
        self.assertEqual(data["first_payment_total"], "1.97")
        member = self.commit()
        record = member.visit_conversions.get()
        self.assertEqual(total(self.original), Decimal(".45"))
        self.assertEqual(settled(self.original), Decimal(".45"))
        self.assertEqual(received(self.original), Decimal("16.47"))
        source = record.credits.get()
        self.assertEqual(source.allocation[0]["fee_tax"], "0.03")
        self.assertEqual(source.allocation[0]["fee"], "0.00")
        self.assertEqual(received(member.installments.first().invoice.sale), Decimal("1.97"))
        self.assertFalse(PaymentOperation.objects.filter(kind__in=["refund", "void"]).exists())

    def test_excess_stays_credit_without_zero_receipt_and_preserves_billing_dates(self):
        self.prepare(children=2, adults=2)
        before = FinancialPosting.objects.count()
        member = self.commit(verified=False)
        self.assertEqual(applied(member.installments.first().invoice.sale), Decimal("35.98"))
        self.assertEqual(received(member.installments.first().invoice.sale), 0)
        self.assertEqual(balance(self.customer.pk), Decimal("1.33"))
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(FinancialPosting.objects.count(), before)
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 2)

    def test_prepaid_check_and_new_amount_verification(self):
        self.prepare(billing="prepaid", expected_method="check")
        self.assertEqual(offer(**self.options)["first_payment_total"], "37.98")
        with self.assertRaisesMessage(ValidationError, "actually received"):
            self.commit(verified=False)
        self.assertEqual(MembershipDraft.objects.count(), 0)
        member = self.commit()
        self.assertIsNone(member.billing_state.mandate_id)
        self.assertEqual(received(member.installments.first().invoice.sale), Decimal("37.98"))
        self.assertEqual(member.installments.count(), 1)

    def test_same_request_reuses_purchase_conversion_and_actual_payment(self):
        self.prepare()
        data = offer(**self.options)
        key = uuid.uuid4()
        first = self.commit(reviewed=data["fingerprint"], key=key)
        again = purchase(
            **self.options,
            request_key=key,
            reviewed=data["fingerprint"],
            accepted=True,
            verified_received=True,
            method_id=self.method.pk,
        )
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(CustomerCreditIssue.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_late_benefit_failure_rolls_back_purchase_credit_and_new_receipt(self):
        self.prepare()
        with (
            patch(
                "core.membership_paid_visit.queue_confirmation",
                side_effect=ValidationError("Fictional final failure"),
            ),
            self.assertRaisesMessage(ValidationError, "final failure"),
        ):
            self.commit()
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertFalse(CustomerCreditIssue.objects.exists())
        self.assertFalse(MembershipDraft.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(total(self.original), Decimal("15.99"))

    def test_public_ineligible_and_not_yet_supported_remainders_never_convert(self):
        self.prepare()
        with self.assertRaises(PermissionDenied):
            offer(**(self.options | dict(actor=None)))
        for values in (
            dict(expected_method="card"),
            dict(comped=True, actor=self.owner),
            dict(starts_on=self.values()["starts_on"].replace(day=10)),
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                offer(**(self.options | values))
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_deferred_guard_rejects_a_purchase_without_its_recorded_conversion(self):
        self.prepare()
        with self.assertRaisesMessage(DatabaseError, "complete conversion"), transaction.atomic():
            with patch("core.membership_paid_visit.complete_purchase"):
                self.commit()
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS core_paid_visit_purchase_complete IMMEDIATE")
        self.assertFalse(MembershipDraft.objects.exists())

    def test_zero_principal_does_not_create_zero_credit_application_or_receipt(self):
        from core.models import MembershipPricing

        self.prepare()
        MembershipPricing.objects.create(subscription="0", unlimited="39.99", actor=self.owner)
        member = self.commit(verified=False)
        self.assertTrue(installment_paid(member.installments.first()))
        self.assertEqual(received(member.installments.first().invoice.sale), 0)
        self.assertEqual(balance(self.customer.pk), Decimal("15.99"))
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_one_combined_message_separates_existing_funds_and_new_money(self):
        from core.communications.models import MessageDelivery

        self.prepare(card=True)
        member = self.commit()
        message = MessageDelivery.objects.get(membership=member)
        self.assertEqual(message.kind, "membership_visit_confirmation")
        self.assertIn("Original visit payment received: $16.47", message.text_body)
        self.assertIn("Original visit processing fee retained: $0.45", message.text_body)
        self.assertIn("Paid visit funds applied to membership: $16.02", message.text_body)
        self.assertIn("New membership payment received: $1.97", message.text_body)
        self.assertIn("next scheduled membership payment is $18.53", message.text_body)
        self.assertNotIn("2027", message.subject)
        self.assertFalse(
            MessageDelivery.objects.filter(
                membership=member, kind="membership_confirmation"
            ).exists()
        )

    def test_changed_contact_refreshes_only_unattempted_message_before_claim(self):
        from core.communications.models import MessageDelivery
        from core.communications.services import claim

        self.prepare()
        member = self.commit()
        original = MessageDelivery.objects.get(membership=member)
        self.customer.email = "new-contact@example.invalid"
        self.customer.save(update_fields=["email"])
        self.assertIsNone(claim(original.pk))
        original.refresh_from_db()
        self.assertEqual(original.state, "cancelled")
        current = MessageDelivery.objects.get(membership=member, state="queued")
        self.assertEqual(current.recipient, self.customer.email)
        with override_settings(RESEND_API_KEY="fake-not-used-by-claim"):
            self.assertEqual(claim(current.pk).state, "sending")

    def test_attempted_combined_message_never_queues_a_second_copy(self):
        from core.communications.models import MessageDelivery
        from core.communications.services import claim
        from core.membership_paid_visit import queue_confirmation

        self.prepare()
        member = self.commit()
        message = MessageDelivery.objects.get(membership=member)
        with override_settings(RESEND_API_KEY="fake-not-used-by-claim"):
            self.assertEqual(claim(message.pk).state, "sending")
        self.assertEqual(queue_confirmation(member).pk, message.pk)
        self.assertIsNone(claim(message.pk))
        message.refresh_from_db()
        self.assertEqual(message.state, "unknown")
        self.assertEqual(MessageDelivery.objects.filter(membership=member).count(), 1)

    def web_values(self):
        return dict(
            customer=self.customer.pk,
            kind="subscription",
            places=1,
            months=3,
            billing="monthly",
            starts_on=str(self.options["starts_on"]),
            expected_method="cash",
            paid_visit_id=self.visit.pk,
            credit_amount="0",
            operation="purchase",
            request_key=str(uuid.uuid4()),
            accepted="on",
            verified_received="on",
            method=str(self.method.pk),
            action="confirm",
        )

    def test_booking_button_combined_page_preview_confirmation_and_return_links(self):
        from django.urls import reverse

        from tests.helpers import verified_owner_login

        self.prepare(card=True)
        verified_owner_login(self.client, self.owner)
        page = self.client.get(reverse("booking_detail", args=[self.visit.pk]))
        self.assertContains(page, "Apply today's visit toward a membership purchase")
        url = reverse("membership_purchase")
        page = self.client.get(url, dict(paid_visit=self.visit.pk))
        self.assertContains(page, "Apply visit to membership")
        self.assertEqual(page.context["form"]["paid_visit_id"].value(), self.visit.pk)
        self.assertEqual(
            {k for k, _ in page.context["form"].fields["expected_method"].choices},
            {"cash", "check", "split"},
        )
        values = self.web_values()
        preview = self.client.post(reverse("membership_offer"), values)
        self.assertEqual(preview.status_code, 200, preview.content)
        data = preview.json()
        self.assertEqual(data["payment_due_today"], "1.97")
        self.assertIn("Paid visit applied", data["html"])
        self.assertIn("16.02", data["html"])
        values["reviewed"] = data["fingerprint"]
        saved = self.client.post(url, values)
        member = VisitMembershipConversion.objects.get(booking=self.visit).purchase
        self.assertRedirects(saved, reverse("membership_overview", args=[member.pk]))
        replay = self.client.post(url, values)
        self.assertRedirects(replay, saved.url)
        self.assertRedirects(
            self.client.get(
                url, dict(purchase_key=values["request_key"], paid_visit=self.visit.pk)
            ),
            saved.url,
        )
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertContains(self.client.get(saved.url), "Return to converted visit")
        booking = self.client.get(reverse("booking_detail", args=[self.visit.pk]))
        self.assertContains(booking, "Visit applied toward membership")
        self.assertNotContains(booking, "Apply today's visit toward a membership purchase")

    def test_card_setup_reload_keeps_paid_visit_context_without_financial_action(self):
        from django.urls import reverse

        from core.membership_card_setup import make_flow
        from tests.helpers import verified_owner_login

        self.prepare()
        verified_owner_login(self.client, self.owner)
        key = uuid.uuid4()
        flow = make_flow(
            actor=self.owner,
            customer=self.customer,
            request_key=key,
            offer=offer(**(self.options | dict(actor=self.owner))),
        )
        session = self.client.session
        session["membership_card_flows"] = {str(key): flow}
        session.save()
        page = self.client.get(reverse("membership_purchase"), dict(purchase_key=str(key)))
        self.assertContains(page, "Apply visit to membership")
        self.assertEqual(page.context["form"]["paid_visit_id"].value(), self.visit.pk)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertFalse(VisitMembershipConversion.objects.exists())

    def test_nonexistent_and_other_customer_sources_have_clear_validation_without_writes(self):
        from core.models import Customer

        self.prepare()
        for source in (0, True, 999999, "bad"):
            with self.subTest(source=source), self.assertRaises(ValidationError):
                offer(**(self.options | dict(paid_visit_id=source)))
        other = Customer.objects.create(last_name="Other", phone="2025550999")
        with self.assertRaises(ValidationError):
            offer(**(self.options | dict(customer=other)))
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_unrecorded_provider_return_blocks_transfer_without_erasing_original_payment(self):
        self.prepare(card=True)
        self.external_return(self.original.operations.get())
        with self.assertRaisesMessage(ValidationError, "provider return"):
            offer(**self.options)
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertFalse(CustomerCreditIssue.objects.exists())
        self.assertEqual(received(self.original), Decimal("16.47"))

    def test_changed_membership_price_requires_fresh_review_before_any_conversion(self):
        from core.models import MembershipPricing

        self.prepare()
        old = offer(**self.options)["fingerprint"]
        MembershipPricing.objects.create(subscription="18.99", unlimited="39.99", actor=self.owner)
        with self.assertRaisesMessage(ValidationError, "price changed"):
            self.commit(reviewed=old)
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertFalse(MembershipDraft.objects.exists())
        self.assertEqual(total(self.original), Decimal("15.99"))

    def test_changed_price_clears_rendered_terms_and_receipt_proof_without_javascript(self):
        from django.urls import reverse

        from core.models import MembershipPricing
        from tests.helpers import verified_owner_login

        self.prepare()
        verified_owner_login(self.client, self.owner)
        values = self.web_values()
        old = self.client.post(reverse("membership_offer"), values).json()["fingerprint"]
        values.update(reviewed=old, first_gift_verified="on", first_zelle_verified="on")
        MembershipPricing.objects.create(subscription="18.99", unlimited="39.99", actor=self.owner)
        response = self.client.post(reverse("membership_purchase"), values)
        self.assertContains(response, "price changed")
        form = response.context["form"]
        for name in (
            "accepted",
            "verified_received",
            "first_gift_verified",
            "first_zelle_verified",
        ):
            self.assertFalse(form[name].value(), name)
        self.assertNotEqual(form["reviewed"].value(), old)
        self.assertEqual(response.context["offer"]["payment_due_today"], Decimal("3.00"))
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertFalse(MembershipDraft.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)
