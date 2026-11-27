"""Booking choices are optional, scoped, immutable and never a purchase."""

import uuid
from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.availability import NEW_YORK
from core.membership_booking_prompts import choose, context
from core.membership_public_authority import resolve_link, verified_scope, verify_identity
from core.membership_records import MembershipRenewalLink, MembershipRenewalPrompt
from core.models import (
    Booking,
    BookingCapacityHold,
    Customer,
    FinancialPosting,
    PaymentOperation,
)
from core.public_booking import profile_proof
from tests import test_membership_sales as fixtures
from tests import test_public_membership_views as public_fixtures
from tests.test_membership_renewals import clock
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin

SETTINGS = dict(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    RESEND_API_KEY="fake-never-delivered",
)


class PromptFixtures:
    setUp = fixtures.MembershipPurchaseTests.setUp
    buy = fixtures.MembershipPurchaseTests.buy

    def prior(self):
        return self.buy(
            billing="prepaid",
            expected_method="cash",
            verified_received=True,
            send_confirmation=False,
        )

    def flow(self):
        key = str(uuid.uuid4())
        return dict(
            key=key,
            expires=(timezone.now() + timedelta(minutes=20)).timestamp(),
            customer_id=self.customer.pk,
            customer_revision=self.customer.revision,
            phone=self.customer.phone,
            proof=profile_proof(self.customer, key),
            workflow="integrated_v1",
            stage="details",
        )

    def row(self, flow, *, source="public", actor=None, pending_email=""):
        rows = context(
            customer=self.customer,
            flow=flow,
            source=source,
            actor=actor,
            pending_email=pending_email,
        )["renewal_rows"]
        return rows[0] if rows else None

    def choice(self, flow, action, *, row=None, source="public", actor=None, pending_email=""):
        row = row or self.row(flow, source=source, actor=actor, pending_email=pending_email)
        return choose(
            customer=self.customer,
            flow=flow,
            source=source,
            actor=actor,
            token=row["token"],
            action=action,
            pending_email=pending_email,
        )


@override_settings(**SETTINGS)
class BookingRenewalPromptTests(PromptFixtures, RuntimeRoleMixin, TestCase):
    start = public_fixtures.PublicMembershipViewTests.start

    def test_only_last_five_days_show_and_get_context_is_read_only(self):
        member = self.prior()
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with clock(member.membership.ends_on - timedelta(days=6)):
            self.assertIsNone(self.row(self.flow()))
        with clock(member.membership.ends_on - timedelta(days=5)):
            row = self.row(self.flow())
            self.assertEqual(row["minimum"], 1)
            self.assertEqual(row["places"], 2)
        self.assertFalse(MembershipRenewalPrompt.objects.exists())
        self.assertFalse(MembershipRenewalLink.objects.exists())
        self.assertEqual(
            (PaymentOperation.objects.count(), FinancialPosting.objects.count()), before
        )

    def test_not_now_hides_same_flow_and_defers_until_one_later_booking_at_thirty_days(self):
        member = self.prior()
        end = member.membership.ends_on
        with clock(end - timedelta(days=5)):
            flow = self.flow()
            row = self.row(flow)
            self.choice(flow, "not_now", row=row)
            self.choice(flow, "not_now", row=row)
            self.assertIsNone(self.row(flow))
            self.assertIsNone(self.row(self.flow()))
        with clock(end + timedelta(days=29)):
            self.assertIsNone(self.row(self.flow()))
        with clock(end + timedelta(days=30)):
            later = self.flow()
            row = self.row(later)
            self.assertEqual(row["payload"]["window"], "followup")
            self.choice(later, "seen", row=row)
            self.assertIsNotNone(self.row(later))
            self.assertIsNone(self.row(self.flow()))
            self.choice(later, "not_now", row=row)
        with clock(end + timedelta(days=90)):
            self.assertIsNone(self.row(self.flow()))
        self.assertEqual(MembershipRenewalPrompt.objects.count(), 4)

    def test_renew_is_a_protected_link_without_payment_or_automatic_booking(self):
        member = self.prior()
        with clock(member.membership.ends_on - timedelta(days=5)):
            flow = self.flow()
            row = self.row(flow)
            before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
            with self.runtime_role():
                answer = self.choice(flow, "renew", row=row)
                self.assertEqual(self.choice(flow, "renew", row=row), answer)
            link = MembershipRenewalLink.objects.get()
            self.assertIsNone(link.actor_id)
            self.assertIsNone(link.notice_id)
            self.assertEqual(link.prompt.prompt.source, "public")
            self.assertEqual(link.expires_at - link.prompt.created_at, timedelta(days=30))
            self.assertEqual(resolve_link(answer["url"].split("/")[-2]).pk, link.pk)
            with self.assertRaises(PermissionDenied):
                verified_scope("forged")
            proof = verify_identity(
                token=answer["url"].split("/")[-2],
                phone=self.customer.phone,
                last_name=self.customer.last_name,
            )
            self.assertEqual(verified_scope(proof)["customer"], self.customer.pk)
            self.assertFalse(Booking.objects.exists())
            self.assertFalse(BookingCapacityHold.objects.exists())
            self.assertEqual(
                (PaymentOperation.objects.count(), FinancialPosting.objects.count()), before
            )

    def test_staff_renewal_records_actual_actor_and_uses_existing_sale_screen(self):
        member = self.prior()
        with clock(member.membership.ends_on):
            flow = self.flow()
            row = self.row(flow, source="staff", actor=self.staff)
            answer = self.choice(flow, "renew", row=row, source="staff", actor=self.staff)
            self.assertEqual(answer["url"], reverse("membership_renew", args=[member.pk]))
            self.assertEqual(MembershipRenewalPrompt.objects.get(action="renew").actor, self.staff)
            self.assertFalse(MembershipRenewalLink.objects.exists())

    @override_settings(
        BANQUEST_API_SOURCE_KEY="fake-sandbox", BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake"
    )
    def test_booking_link_can_complete_an_explicit_verified_private_checkout_once(self):
        from core.membership_records import MembershipPublicAcceptance

        member = self.prior()
        with clock(member.membership.ends_on - timedelta(days=5)):
            flow = self.flow()
            answer = self.choice(flow, "renew")
            token = answer["url"].split("/")[-2]
            _, url, data = public_fixtures.PublicMembershipViewTests.prepare(
                self, dict(token=token, prior=member)
            )
            with self.runtime_role():
                response = self.client.post(url, data)
                repeated = self.client.post(url, data)
            self.assertEqual(response.status_code, 302, response.content)
            self.assertEqual(repeated["Location"], response["Location"])
            acceptance = MembershipPublicAcceptance.objects.get()
            self.assertIsNotNone(acceptance.link.prompt_id)
            operation = acceptance.purchase.installments.first().invoice.sale.operations.get()
            self.assertIsNone(operation.actor_id)
            self.assertEqual(operation.state, "ready")
            self.assertFalse(Booking.objects.exists())

    def test_flow_source_actor_and_changed_customer_cannot_reuse_another_review(self):
        member = self.prior()
        with clock(member.membership.ends_on):
            flow = self.flow()
            row = self.row(flow)
            for changes in (dict(flow=self.flow()), dict(source="staff", actor=self.owner)):
                values = (
                    dict(
                        customer=self.customer,
                        flow=flow,
                        source="public",
                        actor=None,
                        token=row["token"],
                        action="not_now",
                    )
                    | changes
                )
                with self.assertRaises(ValidationError):
                    choose(**values)
            Customer.objects.filter(pk=self.customer.pk).update(revision=self.customer.revision + 1)
            self.customer.refresh_from_db()
            with self.assertRaises(ValidationError):
                self.choice(flow, "not_now", row=row)
        self.assertFalse(MembershipRenewalPrompt.objects.exists())

    def test_only_one_actual_choice_is_accepted_for_a_flow_and_show_is_idempotent(self):
        member = self.prior()
        with clock(member.membership.ends_on):
            flow = self.flow()
            row = self.row(flow)
            self.choice(flow, "seen", row=row)
            self.choice(flow, "seen", row=row)
            self.choice(flow, "not_now", row=row)
            with self.assertRaises(ValidationError):
                self.choice(flow, "email_later", row=row)
        self.assertEqual(MembershipRenewalPrompt.objects.count(), 2)

    def test_expired_reminder_is_tomorrow_at_nine_and_does_not_extend_grace(self):
        member = self.prior()
        with clock(member.membership.ends_on + timedelta(days=8)):
            flow = self.flow()
            row = self.row(flow)
            self.assertEqual(row["minimum"], 3)
            self.assertTrue(row["reminder_after_grace"])
            self.choice(flow, "email_later", row=row)
            event = MembershipRenewalPrompt.objects.get(action="email_later")
            when = event.remind_at.astimezone(NEW_YORK)
            self.assertEqual(
                when.date(), timezone.now().astimezone(NEW_YORK).date() + timedelta(days=1)
            )
            self.assertEqual(when.hour, 9)
        self.assertFalse(MembershipRenewalLink.objects.exists())

    def test_reminder_follows_new_york_dst(self):
        self.prior()
        with clock(date(2028, 3, 11)):
            flow = self.flow()
            self.choice(flow, "email_later")
            event = MembershipRenewalPrompt.objects.get(action="email_later")
            self.assertEqual(event.remind_at.astimezone(NEW_YORK).utcoffset(), timedelta(hours=-4))

    def test_missing_email_requires_contact_and_pending_booking_email_is_not_saved_here(self):
        member = self.prior()
        with clock(member.membership.ends_on):
            Customer.objects.filter(pk=self.customer.pk).update(email="")
            self.customer.refresh_from_db()
            flow = self.flow()
            row = self.row(flow)
            self.assertFalse(row["can_email"])
            with self.assertRaises(ValidationError):
                self.choice(flow, "email_later", row=row)
            self.assertFalse(MembershipRenewalPrompt.objects.exists())
            row = self.row(flow, pending_email="pending@example.invalid")
            self.assertTrue(row["pending_contact"])
            self.choice(flow, "email_later", row=row, pending_email="pending@example.invalid")
            self.customer.refresh_from_db()
            self.assertEqual(self.customer.email, "")

    def test_runtime_facts_are_immutable_and_customer_scope_is_guarded(self):
        member = self.prior()
        with clock(member.membership.ends_on):
            flow = self.flow()
            with self.runtime_role():
                self.choice(flow, "not_now")
                event = MembershipRenewalPrompt.objects.get(action="seen")
                with self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "UPDATE core_membershiprenewalprompt SET action='renew' WHERE id=%s",
                            [event.pk],
                        )
            wrong = Customer.objects.create(last_name="Other", phone="2025550199")
            values = {
                field.attname: getattr(event, field.attname)
                for field in event._meta.concrete_fields
                if field.attname not in {"id", "created_at"}
            }
            with self.assertRaises(DatabaseError), transaction.atomic():
                MembershipRenewalPrompt.objects.create(
                    id=uuid.uuid4(), **(values | dict(customer_id=wrong.pk, flow_key=uuid.uuid4()))
                )

    def test_public_endpoint_requires_current_browser_proof_and_csrf(self):
        member = self.prior()
        with clock(member.membership.ends_on):
            flow = self.flow()
            row = self.row(flow)
            session = self.client.session
            session["customer_test_booking"] = flow
            session.save()
            endpoint = reverse("public_membership_choice")
            data = dict(decision=row["token"] + ".not_now")
            csrf = Client(enforce_csrf_checks=True)
            csrf.cookies = self.client.cookies
            self.assertEqual(csrf.post(endpoint, data).status_code, 403)
            self.assertEqual(self.client.get(endpoint).status_code, 405)
            self.assertEqual(Client().post(endpoint, data).status_code, 400)
            response = self.client.post(endpoint, data, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()["action"], "not_now")
            self.assertEqual(self.client.session["customer_test_booking"], flow)

    def test_public_renew_native_path_still_requires_private_phone_verification(self):
        member = self.prior()
        with clock(member.membership.ends_on):
            flow = self.flow()
            row = self.row(flow)
            session = self.client.session
            session["customer_test_booking"] = flow
            session.save()
            response = self.client.post(
                reverse("public_membership_choice"), dict(decision=row["token"] + ".renew")
            )
            self.assertEqual(response.status_code, 302)
            anonymous = Client().get(response["Location"])
            self.assertContains(anonymous, "Phone number")
            self.assertNotContains(anonymous, self.customer.email)

    def test_stale_token_feature_and_recovery_gates_create_nothing(self):
        member = self.prior()
        with clock(member.membership.ends_on):
            flow = self.flow()
            row = self.row(flow)
            for setting in (dict(MEMBERSHIP_SALES_ENABLED=False), dict(RECOVERY_HOLD=True)):
                with override_settings(**setting), self.assertRaises(ValidationError):
                    self.choice(flow, "not_now", row=row)
            with patch(
                "django.core.signing.time.time", return_value=timezone.now().timestamp() + 3600
            ):
                with self.assertRaises(ValidationError):
                    self.choice(flow, "not_now", row=row)
        self.assertFalse(MembershipRenewalPrompt.objects.exists())
