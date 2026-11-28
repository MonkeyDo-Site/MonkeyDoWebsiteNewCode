"""A new owner's current visit consent cannot rewrite an earlier membership payment."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core import membership_arrival_recovery as recovery
from core.membership_arrival_pending import complete
from core.membership_records import (
    MembershipArrivalCheckout,
    MembershipArrivalIntent,
    MembershipArrivalResolution,
    MembershipPurchase,
)
from core.models import PaymentOperation
from core.payments.invoices import received
from tests import test_membership_arrival_pending as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class OwnerArrivalRecoveryTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PendingMembershipArrivalTests.prepare
    begin = fixtures.PendingMembershipArrivalTests.begin
    pay_first = fixtures.PendingMembershipArrivalTests.pay_first

    def start(self, *, paid=True):
        self.begin()
        if paid:
            self.pay_first()
        self.recovery_data = self.input | {
            "pending_review": self.intent.pk,
            "pending_reason": "Review current counts after the first payment was reconciled.",
        }
        self.recovery_key = uuid.uuid4()

    def owner_review(self):
        recovery.begin_review(actor=self.owner, intent_id=self.intent.pk)
        self.intent = MembershipArrivalIntent.objects.select_related("purchase", "progress").get(
            pk=self.intent.pk
        )
        return recovery.preview(actor=self.owner, intent=self.intent, data=self.recovery_data)[0]

    def accept(self, digest=None, **changes):
        return recovery.confirm(
            actor=self.owner,
            intent_id=self.intent.pk,
            data=self.recovery_data,
            request_key=self.recovery_key,
            reviewed_hash=digest or self.owner_review()[-1],
            confirmed=True,
            **changes,
        )

    def test_new_owner_can_complete_expired_review_without_rebuying_membership(self):
        self.start()
        self.intent.refresh_from_db()
        original_facts = self.intent.facts
        with patch(
            "django.utils.timezone.now", return_value=self.intent.expires_at + timedelta(seconds=1)
        ):
            reviewed = self.owner_review()
            with self.runtime_role():
                arrival = self.accept(reviewed[-1])
        self.assertEqual(arrival.actor_id, self.owner.pk)
        resolution = MembershipArrivalResolution.objects.get()
        self.assertEqual(resolution.actor_id, self.owner.pk)
        self.assertEqual(resolution.request_key, self.recovery_key)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(received(self.intent.operation.sale), Decimal("37.06"))
        self.intent.refresh_from_db()
        self.assertEqual(self.intent.facts, original_facts)
        self.assertEqual(self.intent.actor_id, self.staff.pk)
        self.assertEqual(MembershipArrivalCheckout.objects.get().actor_id, self.owner.pk)

    def test_owner_start_stops_original_automatic_continuation(self):
        self.start()
        self.owner_review()
        state = complete(self.intent.pk)
        self.assertEqual(state.code, "owner_review_requested")
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.play.refresh_from_db()
        self.assertEqual(self.play.attendance, "")

    def test_unknown_first_payment_cannot_be_replaced_by_a_fresh_visit_review(self):
        self.start(paid=False)
        with self.assertRaisesMessage(ValidationError, "Confirm the existing membership payment"):
            self.owner_review()
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_staff_cannot_take_over_fresh_owner_authority(self):
        self.start()
        self.assertFalse(self.staff.is_superuser)
        with self.assertRaises(PermissionDenied):
            recovery.begin_review(actor=self.staff, intent_id=self.intent.pk)

    def test_changed_counts_and_deactivated_original_actor_use_new_owner_consent(self):
        self.start()
        type(self.staff).objects.filter(pk=self.staff.pk).update(is_active=False)
        self.recovery_data["children"] = 2
        arrival = self.accept()
        self.assertEqual(arrival.details["quote"]["total"], "3.09")
        self.assertEqual(arrival.details["counts"]["children"], 2)
        self.assertEqual(arrival.actor_id, self.owner.pk)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_stale_current_review_does_not_create_another_financial_fact(self):
        self.start()
        reviewed = self.owner_review()
        self.recovery_data["children"] = 2
        with self.assertRaisesMessage(ValidationError, "changed"):
            self.accept(reviewed[-1])
        self.assertFalse(MembershipArrivalResolution.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_confirmation_replays_only_the_same_owner_request_and_current_hash(self):
        self.start()
        reviewed = self.owner_review()
        arrival = self.accept(reviewed[-1])
        repeated = self.accept(reviewed[-1])
        self.assertEqual(arrival.pk, repeated.pk)
        self.assertEqual(MembershipArrivalResolution.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        with self.assertRaisesMessage(ValidationError, "another owner review"):
            self.accept("changed")

    def test_fresh_owner_evidence_is_immutable_and_does_not_impersonate_staff(self):
        self.start()
        self.accept()
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_membershiparrivalresolution SET reason='changed' WHERE intent_id=%s",
                [self.intent.pk],
            )

    def test_database_rejects_resolution_attributed_to_nonowner(self):
        self.start()
        reviewed = self.owner_review()
        original = MembershipArrivalResolution.objects.create

        def change_actor(**values):
            return original(**(values | {"actor": self.staff}))

        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            patch(
                "core.membership_arrival_recovery.MembershipArrivalResolution.objects.create",
                side_effect=change_actor,
            ),
        ):
            self.accept(reviewed[-1])
        self.assertFalse(MembershipArrivalResolution.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def web_review(self):
        verified_owner_login(self.client, self.owner)
        self.url = reverse("booking_arrival", args=[self.play.pk])
        response = self.client.post(self.url, {"start_owner_review": "1"})
        self.assertEqual(response.status_code, 302)
        return self.client.get(response.url)

    def posted(self, page):
        return self.recovery_data | {
            "request_key": str(page.context["form"]["request_key"].value()),
            "version": self.play.edit_version,
            "pending_review": str(self.intent.pk),
            "waiver_confirmed": "yes",
            "arrival_draft": page.context["arrival_draft"],
        }

    def test_current_counts_waivers_and_different_visit_tender_share_one_page(self):
        self.start()
        page = self.web_review()
        self.assertContains(page, "Membership purchased · $37.06 received")
        self.assertNotContains(page, 'name="member_add"')
        self.assertContains(page, "Active customer waivers")
        values = self.posted(page) | {"method": "cash", "member_add": "on"}
        reviewed = self.client.post(self.url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertIn("15.99", reviewed.json()["label"])
        values.update(reviewed_hash=reviewed.json()["hash"], confirm_review="1")
        final = self.client.post(self.url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(final.status_code, 200, final.content)
        self.assertTrue(final.json()["confirmed"])
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        result = MembershipArrivalResolution.objects.get()
        self.assertEqual(result.checkout.sale.operations.get().tender, "cash")
        self.assertEqual(result.checkout.sale.operations.get().amount, Decimal("15.99"))
        saved = self.client.get(reverse("booking_detail", args=[self.play.pk]))
        self.assertContains(saved, "Arrival confirmed after owner review")
        self.assertContains(saved, self.recovery_data["pending_reason"])

    def test_private_draft_return_preserves_owner_review_and_entered_fields(self):
        self.start()
        page = self.web_review()
        values = self.posted(page) | {
            "method": "cash",
            "children": "2",
            "pending_reason": "Corrected caller counts",
        }
        response = self.client.post(self.url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        returned = self.client.get(self.url + "?draft=" + values["arrival_draft"])
        self.assertEqual(returned.status_code, 200)
        self.assertEqual(
            returned.context["form"]["pending_reason"].value(), "Corrected caller counts"
        )
        self.assertEqual(str(returned.context["form"]["children"].value()), "2")
        self.assertNotContains(returned, 'name="member_add"')
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_owner_review_get_cannot_stop_automatic_continuation(self):
        self.start()
        verified_owner_login(self.client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        response = self.client.get(url + "?review_pending=1")
        self.assertEqual(response.status_code, 302)
        self.intent.progress.refresh_from_db()
        self.assertEqual(self.intent.progress.status, "waiting")
        self.assertEqual(self.intent.events.count(), 1)

    def test_fresh_review_checks_current_capacity_and_explicit_owner_override(self):
        self.start()
        from core.models import Session

        Session.objects.filter(pk=self.play.session_id).update(child_capacity=3)
        self.recovery_data.update(children=4, waiver_mismatch_accepted=True)
        with self.assertRaisesMessage(ValidationError, "capacity"):
            self.owner_review()
        self.recovery_data["override_capacity"] = True
        arrival = self.accept()
        self.assertEqual(arrival.details["counts"]["children"], 4)
        self.assertTrue(arrival.details["override_capacity"])
        self.assertEqual(MembershipPurchase.objects.count(), 1)

    def test_native_review_then_confirmation_uses_the_current_visit_amount(self):
        self.start()
        page = self.web_review()
        values = self.posted(page) | {"method": "cash", "children": "2", "preview": "1"}
        reviewed = self.client.post(self.url, values)
        self.assertEqual(reviewed.status_code, 200)
        self.assertContains(reviewed, "Confirm arrival and record cash — $3.00")
        values.pop("preview")
        values.update(
            reviewed_hash=reviewed.context["form"]["reviewed_hash"].value(), confirm_review="1"
        )
        completed = self.client.post(self.url, values)
        self.assertEqual(completed.status_code, 302)
        result = MembershipArrivalResolution.objects.get()
        self.assertEqual(result.checkout.sale.operations.get().amount, Decimal("3.00"))
        self.assertEqual(result.actor_id, self.owner.pk)

    def test_starting_owner_review_requires_csrf_and_does_not_mutate_on_rejection(self):
        self.start()
        client = Client(enforce_csrf_checks=True)
        verified_owner_login(client, self.owner)
        url = reverse("booking_arrival", args=[self.play.pk])
        rejected = client.post(url, {"start_owner_review": "1"})
        self.assertEqual(rejected.status_code, 403)
        self.intent.progress.refresh_from_db()
        self.assertEqual(self.intent.progress.status, "waiting")
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_validation_error_keeps_member_benefits_in_the_visible_safe_estimate(self):
        self.start()
        page = self.web_review()
        values = self.posted(page) | {"pending_reason": "", "confirm_review": "1"}
        invalid = self.client.post(self.url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(invalid.status_code, 400)
        result = invalid.json()
        self.assertFalse(result["can_confirm"])
        self.assertEqual(result["noncard_total"], "15.99")
        self.assertIn("Subscription free visits", result["html"])
        self.assertEqual(PaymentOperation.objects.count(), 1)
