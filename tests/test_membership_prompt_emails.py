"""Requested reminders use current facts and never repeat uncertain delivery."""

import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings

from core.communications.models import MessageDelivery
from core.communications.services import claim, deliver, enqueue
from core.communications.transport import MailUnavailable
from core.membership_prompt_emails import prepare, prepare_due
from core.membership_records import (
    MembershipPromptEmail,
    MembershipPromptLink,
    MembershipRenewalPrompt,
)
from core.models import Customer, FinancialPosting, PaymentOperation
from tests import test_customer_credit as credit_fixtures
from tests import test_membership_renewals as renewal_fixtures
from tests import test_membership_sales as sale_fixtures
from tests.test_membership_booking_prompts import SETTINGS, PromptFixtures
from tests.test_membership_renewals import clock
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class RequestedRenewalEmailTests(PromptFixtures, RuntimeRoleMixin, TestCase):
    follow = renewal_fixtures.MembershipRenewalTests.follow
    follow_values = renewal_fixtures.MembershipRenewalTests.follow_values

    def request(self, member, *, on=None, pending_email=""):
        with clock(on or member.membership.ends_on - timedelta(days=5)):
            flow = self.flow()
            self.choice(flow, "email_later", pending_email=pending_email)
            return MembershipRenewalPrompt.objects.get(purchase=member, action="email_later")

    def at(self, when):
        return patch("django.utils.timezone.now", return_value=when)

    def test_due_at_nine_once_with_immutable_link_and_no_money_or_email_delivery(self):
        member = self.prior()
        event = self.request(member)
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with self.at(event.remind_at - timedelta(seconds=1)):
            self.assertIsNone(prepare(event.pk))
            self.assertEqual(prepare_due()["ready"], 0)
        self.assertFalse(MembershipPromptLink.objects.exists())
        with self.at(event.remind_at):
            self.assertEqual(prepare_due(dry_run=True)["ready"], 1)
            self.assertFalse(MembershipPromptLink.objects.exists())
            with self.runtime_role():
                self.assertEqual(prepare_due()["ready"], 1)
            self.assertEqual(prepare_due()["ready"], 0)
            message = prepare(event.pk)
            self.assertEqual(
                MessageDelivery.objects.filter(kind="membership_requested_renewal").count(), 1
            )
            self.assertEqual(message.state, "queued")
            self.assertIn("renewal link you requested", message.text_body)
            self.assertIn("will begin after your current term ends", message.text_body)
            authority = MembershipPromptLink.objects.get()
            self.assertEqual(authority.link.expires_at - authority.created_at, timedelta(days=30))
        self.assertEqual(
            (PaymentOperation.objects.count(), FinancialPosting.objects.count()), before
        )

    def test_already_expired_request_has_future_timing_and_current_three_month_minimum(self):
        member = self.prior()
        event = self.request(member, on=member.membership.ends_on + timedelta(days=8))
        with self.at(event.remind_at):
            message = prepare(event.pk)
        self.assertIn("ended on", message.text_body)
        self.assertIn("requires a new three-month minimum", message.text_body)
        self.assertIn("begin when you renew", message.text_body)
        self.assertNotIn("tomorrow", message.text_body)
        self.assertNotIn("expires on", message.text_body)

    def test_pending_booking_email_is_not_a_delivery_destination_until_actually_saved(self):
        member = self.prior()
        Customer.objects.filter(pk=self.customer.pk).update(email="")
        self.customer.refresh_from_db()
        event = self.request(member, pending_email="pending@example.invalid")
        with self.at(event.remind_at):
            self.assertIsNone(prepare(event.pk))
            self.assertEqual(prepare_due()["ready"], 0)
            Customer.objects.filter(pk=self.customer.pk).update(email="confirmed@example.invalid")
            self.assertEqual(prepare_due()["ready"], 1)
        self.assertEqual(
            MessageDelivery.objects.get(kind="membership_requested_renewal").recipient,
            "confirmed@example.invalid",
        )

    def test_partial_renewal_rebuilds_the_unsent_remaining_place_snapshot(self):
        member = self.prior()
        event = self.request(member)
        with self.at(event.remind_at):
            old = prepare(event.pk)
            self.follow(member, places=1)
            self.assertIsNone(claim(old.pk))
            old.refresh_from_db()
            self.assertEqual(old.state, "cancelled")
            current = MessageDelivery.objects.get(
                kind="membership_requested_renewal", state="queued"
            )
            self.assertIn("Your 1 Subscription membership ends", current.text_body)
            self.assertIn("Your 2 Subscription memberships end", old.text_body)

    def test_full_renewal_withdraws_requested_message_before_any_send(self):
        member = self.prior()
        event = self.request(member)
        with self.at(event.remind_at):
            message = prepare(event.pk)
            self.follow(member, places=2)
            with patch("core.communications.services.send") as send:
                self.assertEqual(deliver(message.pk).state, "cancelled")
                send.assert_not_called()
            self.assertIsNone(prepare(event.pk))

    def test_contact_reversal_keeps_frozen_versions_and_unknown_delivery_is_not_repeated(self):
        member = self.prior()
        event = self.request(member)
        with self.at(event.remind_at):
            first = prepare(event.pk)
            Customer.objects.filter(pk=self.customer.pk).update(email="second@example.invalid")
            second = prepare(event.pk)
            Customer.objects.filter(pk=self.customer.pk).update(email=self.customer.email)
            third = prepare(event.pk)
            self.assertNotEqual(first.pk, third.pk)
            self.assertNotEqual(second.pk, third.pk)
            self.assertEqual(
                MessageDelivery.objects.filter(
                    kind="membership_requested_renewal", state="queued"
                ).count(),
                1,
            )
            with patch(
                "core.communications.services.send", side_effect=MailUnavailable("mail_network")
            ) as send:
                self.assertEqual(deliver(third.pk).state, "unknown")
                self.assertEqual(deliver(third.pk).state, "unknown")
                self.assertEqual(send.call_count, 1)
            self.assertIsNone(prepare(event.pk))
            self.assertEqual(MembershipPromptEmail.objects.count(), 3)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.state, second.state), ("cancelled", "cancelled"))

    def test_current_payment_review_and_cancellation_stop_prepared_reminders(self):
        member = self.buy(billing="prepaid", send_confirmation=False)
        original = sale_fixtures.MembershipPurchaseTests.succeed(self, member)
        event = self.request(member)
        with self.at(event.remind_at):
            message = prepare(event.pk)
            credit_fixtures.CustomerCreditTests.external_return(self, original)
            with patch("core.communications.services.send") as send:
                self.assertEqual(deliver(message.pk).state, "cancelled")
                send.assert_not_called()

    def test_thirty_day_request_expiry_does_not_create_a_stale_email(self):
        member = self.prior()
        event = self.request(member)
        with self.at(event.remind_at + timedelta(days=30, seconds=1)):
            self.assertEqual(prepare_due()["ready"], 0)
            self.assertIsNone(prepare(event.pk))
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_requested_renewal").exists()
        )

    def test_missing_authority_is_not_delivered_and_wrong_customer_mapping_is_rejected(self):
        member = self.prior()
        event = self.request(member)
        with self.at(event.remind_at):
            genuine = prepare(event.pk)
            forged = enqueue(
                key=str(uuid.uuid4()),
                kind="membership_requested_renewal",
                recipient=self.customer.email,
                subject="Test",
                text="Test",
                customer=self.customer,
            )
            with patch("core.communications.services.send") as send:
                self.assertEqual(deliver(forged.pk).state, "cancelled")
                send.assert_not_called()
            with self.assertRaises(DatabaseError), transaction.atomic():
                MembershipPromptEmail.objects.create(
                    authority=genuine.renewal_prompt_evidence.authority, message=forged
                )

    def test_producer_progress_skips_missing_contacts_before_the_batch_limit(self):
        member = self.prior()
        first = self.request(member)
        other = Customer.objects.create(
            last_name="Second", phone="2025550199", email="second@example.invalid"
        )
        previous = self.customer
        self.customer = other
        self.values = self.values | dict(customer=other)
        self.key = uuid.uuid4()
        second_member = self.prior()
        second = self.request(second_member)
        Customer.objects.filter(pk=previous.pk).update(email="")
        with self.at(max(first.remind_at, second.remind_at)):
            self.assertEqual(prepare_due(limit=1)["ready"], 1)
        self.assertEqual(MembershipPromptLink.objects.get().prompt_id, second.pk)

    def test_worker_keeps_processing_other_jobs_if_a_reminder_producer_fails(self):
        output, error = StringIO(), StringIO()
        with (
            patch("core.membership_renewal_notices.prepare_due", side_effect=DatabaseError()),
            patch("core.membership_prompt_emails.prepare_due") as requested,
            patch("core.management.commands.run_payment_jobs.run_one", return_value=False) as job,
        ):
            call_command("run_payment_jobs", limit=1, stdout=output, stderr=error)
        self.assertIn("needs review", error.getvalue())
        requested.assert_called_once_with(limit=1)
        job.assert_called_once()

    def test_contact_change_during_claim_keeps_replacement_authority(self):
        from core.membership_prompt_emails import refresh

        member = self.prior()
        event = self.request(member)
        with self.at(event.remind_at):
            message = prepare(event.pk)
            changed = False

            def raced(authority):
                nonlocal changed
                result = refresh(authority)
                if not changed:
                    Customer.objects.filter(pk=self.customer.pk).update(
                        email="late-change@example.invalid"
                    )
                    changed = True
                return result

            with patch("core.membership_prompt_emails.refresh", side_effect=raced):
                self.assertIsNone(claim(message.pk))
            replacement = MessageDelivery.objects.get(
                kind="membership_requested_renewal", state="queued"
            )
            self.assertEqual(replacement.recipient, "late-change@example.invalid")
            self.assertEqual(replacement.renewal_prompt_evidence.authority.prompt_id, event.pk)
