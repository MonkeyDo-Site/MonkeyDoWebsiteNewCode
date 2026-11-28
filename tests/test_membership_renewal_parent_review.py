"""A paid early renewal does not silently decide the unresolved earlier-arrears policy."""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse

from core.communications.models import MessageDelivery
from core.communications.services import claim
from core.membership_booking_exceptions import resolve, unavailable_memberships
from core.membership_funding import held_members, member_needs_review
from core.membership_payments import collect_installment, payment_review
from core.membership_renewal_review import parents_needing_review, reviews
from core.membership_reporting import reporting_members
from core.membership_reservations import payment_current, places_for
from core.membership_sales import installment_paid, membership_status
from core.models import FinancialPosting, PaymentOperation
from core.payments.invoices import received
from tests import test_membership_renewals as renewal_fixtures
from tests import test_membership_reservations as booking_fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PrepaidRenewalParentReviewTests(RuntimeRoleMixin, TestCase):
    setUp = renewal_fixtures.MembershipRenewalTests.setUp
    buy = renewal_fixtures.MembershipRenewalTests.buy
    follow_values = renewal_fixtures.MembershipRenewalTests.follow_values
    follow = renewal_fixtures.MembershipRenewalTests.follow
    booking = booking_fixtures.MembershipReservationTests.booking
    quote = booking_fixtures.MembershipReservationTests.quote
    assign = booking_fixtures.MembershipReservationTests.assign

    def family(self):
        self.prior = self.buy(billing="monthly", expected_method="cash", verified_received=True)
        self.renewed = self.follow(self.prior)
        self.start = self.renewed.membership.starts_on
        self.sale = self.renewed.installments.first().invoice.sale
        return self.renewed

    def restore_parent(self):
        for item in self.prior.installments.all():
            if installment_paid(item):
                continue
            options = dict(
                actor=self.staff, member_id=self.prior.pk, installment_id=item.pk, tender="cash"
            )
            data = payment_review(**options)
            collect_installment(
                **options,
                reviewed=data["fingerprint"],
                request_key=uuid.uuid4(),
                confirmed=True,
                verified_received=True,
            )

    def test_paid_prepaid_renewal_is_review_not_unpaid_when_earlier_term_falls_overdue(self):
        self.family()
        self.assertEqual(membership_status(self.renewed), "scheduled")
        self.assertFalse(parents_needing_review(self.renewed))
        with renewal_fixtures.clock(self.start):
            with self.runtime_role():
                self.assertEqual(membership_status(self.renewed), "review")
                self.assertFalse(payment_current(self.renewed))
                self.assertTrue(installment_paid(self.renewed.installments.first()))
                self.assertEqual(received(self.sale), Decimal("17.99"))
                self.assertEqual(
                    [p.pk for p in parents_needing_review(self.renewed)], [self.prior.pk]
                )
                self.assertIn(self.renewed.pk, held_members())
                self.assertEqual(
                    reporting_members().get(pk=self.renewed.pk).report_status, "review"
                )

    def test_no_new_benefits_while_unresolved_and_receipts_terms_and_prices_are_unchanged(self):
        self.family()
        original_terms = self.renewed.terms_text
        original_quotes = [item.quote for item in self.renewed.installments.all()]
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with (
            renewal_fixtures.clock(self.start),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            self.assertEqual(
                places_for(self.customer.pk, appointment_on=self.start, children=1), []
            )
            gateway.assert_not_called()
        self.renewed.refresh_from_db()
        self.assertEqual(self.renewed.terms_text, original_terms)
        self.assertEqual([item.quote for item in self.renewed.installments.all()], original_quotes)
        self.assertEqual(
            before, (PaymentOperation.objects.count(), FinancialPosting.objects.count())
        )

    def test_resolving_earlier_required_payments_clears_review_without_recollecting_renewal(self):
        self.family()
        with renewal_fixtures.clock(self.start):
            self.assertTrue(member_needs_review(self.renewed))
            self.restore_parent()
            self.assertFalse(member_needs_review(self.renewed))
            self.assertTrue(payment_current(self.renewed))
            self.assertEqual(membership_status(self.renewed), "active")
            self.assertEqual(
                len(places_for(self.customer.pk, appointment_on=self.start, children=1)), 1
            )
            self.assertEqual(self.sale.operations.count(), 1)
            self.assertEqual(received(self.sale), Decimal("17.99"))

    def test_existing_future_reservation_keeps_its_snapshot_and_owner_choice_stays_explicit(self):
        self.family()
        booking = self.booking(day=self.start)
        quote = self.quote(booking)
        self.assign(booking, quote=quote)
        saved = quote.snapshot
        with renewal_fixtures.clock(self.start):
            self.assertEqual(unavailable_memberships(booking), [self.renewed.pk])
            with self.assertRaises(PermissionDenied):
                resolve(
                    booking, actor=self.staff, choice="honor", reason="Staff cannot decide this"
                )
            decision = resolve(
                booking, actor=self.owner, choice="honor", reason="Owner reviewed this booking only"
            )
            self.assertEqual(decision["memberships"], [self.renewed.pk])
            self.assertFalse(payment_current(self.renewed))
        quote.refresh_from_db()
        self.assertEqual(quote.snapshot, saved)
        self.assertEqual(booking.membership_benefits.filter(current__status="reserved").count(), 1)

    def test_owner_dashboard_and_same_membership_page_explain_paid_renewal_and_clear_after_resolution(
        self,
    ):
        self.family()
        with renewal_fixtures.clock(self.start):
            verified_owner_login(self.client, self.owner)
            response = self.client.get(reverse("membership_overview", args=[self.renewed.pk]))
            self.assertContains(response, "This prepaid renewal payment is recorded")
            self.assertContains(
                response, f"Review earlier membership #{self.prior.membership_number}"
            )
            dashboard = self.client.get(reverse("dashboard"))
            self.assertContains(dashboard, "Paid renewals needing owner review")
            self.restore_parent()
            self.assertNotContains(
                self.client.get(reverse("dashboard")), "Paid renewals needing owner review"
            )

    def test_queued_customer_confirmation_does_not_claim_ready_benefits_during_review(self):
        self.family()
        message = MessageDelivery.objects.get(membership=self.renewed, kind="membership_renewal")
        with renewal_fixtures.clock(self.start):
            self.assertIsNone(claim(message.pk))
        message.refresh_from_db()
        self.assertEqual((message.state, message.code), ("cancelled", "membership_funding_review"))

    def test_parent_future_installments_not_yet_due_do_not_create_a_review_hold(self):
        self.family()
        with renewal_fixtures.clock(date(2027, 11, 1)):
            self.assertFalse(parents_needing_review(self.renewed))
            self.assertTrue(payment_current(self.renewed))
            self.assertEqual(reviews(), [])
            self.assertEqual(
                len(places_for(self.customer.pk, appointment_on=self.start, children=1)), 1
            )

    def test_fully_paid_parent_and_ordinary_prepaid_purchase_remain_unaffected(self):
        self.prior = self.buy(billing="prepaid", expected_method="cash", verified_received=True)
        renewed = self.follow(self.prior)
        with renewal_fixtures.clock(renewed.membership.starts_on):
            self.assertFalse(parents_needing_review(self.prior))
            self.assertFalse(parents_needing_review(renewed))
            self.assertEqual(membership_status(renewed), "active")

    def test_explicit_as_of_date_agrees_between_status_and_reporting(self):
        self.family()
        self.assertEqual(membership_status(self.renewed, on=self.start), "review")
        self.assertEqual(
            reporting_members(on=self.start).get(pk=self.renewed.pk).report_status, "review"
        )

    def test_explicit_owner_complimentary_renewal_does_not_invent_unpaid_new_money(self):
        from core.membership_sales import offer, purchase

        self.prior = self.buy(billing="monthly", expected_method="cash", verified_received=True)
        values = self.follow_values(self.prior, actor=self.owner, comped=True)
        data = offer(**values)
        renewed = purchase(
            **values,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            accepted=True,
            send_confirmation=False,
        )
        with renewal_fixtures.clock(renewed.membership.starts_on):
            self.assertFalse(parents_needing_review(renewed))
            self.assertEqual(membership_status(renewed), "active")
            self.assertFalse(renewed.installments.exists())

    def test_unpaid_or_declined_renewal_is_not_described_as_a_paid_renewal(self):
        from core.payments.ledger import record_result

        prior = self.buy(billing="monthly", expected_method="cash", verified_received=True)
        renewed = self.follow(prior, expected_method="card")
        sale = renewed.installments.first().invoice.sale
        operation = sale.operations.get()
        with renewal_fixtures.clock(renewed.membership.starts_on):
            verified_owner_login(self.client, self.owner)
            for state in ("ready", "declined"):
                with self.subTest(state=state):
                    if state == "declined":
                        record_result(
                            operation_id=operation.pk,
                            state="declined",
                            source="provider",
                            code="test_declined",
                        )
                    self.assertEqual(received(sale), Decimal("0.00"))
                    self.assertEqual(membership_status(renewed), "pending")
                    self.assertFalse(parents_needing_review(renewed))
                    self.assertFalse(reviews(live_only=True))
                    self.assertFalse(payment_current(renewed))
                    page = self.client.get(reverse("membership_overview", args=[renewed.pk]))
                    self.assertContains(page, "The first membership payment is not yet confirmed")
                    self.assertNotContains(page, "This prepaid renewal payment is recorded")
                    self.assertNotContains(
                        self.client.get(reverse("dashboard")),
                        "Paid renewals needing owner review",
                    )
