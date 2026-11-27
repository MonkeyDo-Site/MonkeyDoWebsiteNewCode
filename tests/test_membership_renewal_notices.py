import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from core.communications.models import MessageDelivery
from core.communications.presentation import confirmation_html
from core.communications.services import claim, deliver, enqueue
from core.communications.transport import MailUnavailable
from core.membership_cancellations import cancel
from core.membership_cancellations import review as cancellation_review
from core.membership_public_authority import (
    create_link,
    resolve_link,
    token_for,
    verified_scope,
    verify_identity,
)
from core.membership_records import (
    MembershipRenewalLink,
    MembershipRenewalNotice,
    MembershipRenewalNoticeDelivery,
)
from core.membership_renewal_notices import notice_dates, prepare_due, prepare_notice
from core.models import (
    Customer,
    FinancialPosting,
    MembershipPricing,
    PaymentOperation,
    PricingPolicy,
)
from tests import test_membership_cancellations as race_fixtures
from tests import test_membership_renewals as fixtures
from tests.helpers import verified_owner_login
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
    RESEND_API_KEY="fake-notice-key",
)


class NoticeFixtures:
    setUp = fixtures.MembershipRenewalTests.setUp
    buy = fixtures.MembershipRenewalTests.buy
    follow_values = fixtures.MembershipRenewalTests.follow_values
    follow = fixtures.MembershipRenewalTests.follow

    def prior(self, **changes):
        changes.setdefault("send_confirmation", False)
        return fixtures.MembershipRenewalTests.prior(self, **changes)

    def window(self, member, kind="expiry"):
        return fixtures.clock(notice_dates(member.membership.ends_on)[kind])


@override_settings(**SETTINGS)
class RenewalNoticeTests(NoticeFixtures, RuntimeRoleMixin, TestCase):
    def test_exact_due_days_dry_run_and_repeat_prepare_do_not_move_money_or_repeat_notices(self):
        member = self.prior()
        before = FinancialPosting.objects.count(), PaymentOperation.objects.count()
        dates = notice_dates(member.membership.ends_on)
        with fixtures.clock(dates["expiry"] - timedelta(days=1)):
            self.assertEqual(prepare_due()["ready"], 0)
        with self.window(member):
            output = StringIO()
            call_command("prepare_membership_notices", dry_run=True, stdout=output)
            self.assertIn("Dry run", output.getvalue())
            self.assertFalse(MembershipRenewalNotice.objects.exists())
            self.assertEqual(prepare_due()["ready"], 1)
            self.assertEqual(prepare_due()["ready"], 0)
            message = prepare_notice(member_id=member.pk, kind="expiry")
            self.assertEqual(message.state, "queued")
        self.assertEqual(MembershipRenewalNotice.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.filter(kind="membership_expiry_notice").count(), 1)
        self.assertEqual(
            before, (FinancialPosting.objects.count(), PaymentOperation.objects.count())
        )

    def test_expiry_and_grace_copy_keep_exact_dates_one_month_renewal_and_system_authority(self):
        member = self.prior()
        with self.window(member):
            expiry = prepare_notice(member_id=member.pk, kind="expiry")
            link = expiry.renewal_notice_evidence.notice.renewal_link
            self.assertIsNone(link.actor_id)
            self.assertEqual(resolve_link(token_for(link)).pk, link.pk)
            self.assertEqual(link.expires_at - link.notice.created_at, timedelta(days=30))
            self.assertIn("2 Subscription memberships expire", expiry.text_body)
            self.assertNotIn("no benefits", expiry.text_body.lower())
        with self.window(member, "grace"):
            grace = prepare_notice(member_id=member.pk, kind="grace")
            self.assertIn("renewal grace period ends tomorrow", grace.text_body)
            self.assertIn("begin as soon as you renew", grace.text_body)
            link = grace.renewal_notice_evidence.notice.renewal_link
            proof = verify_identity(
                token=token_for(link), phone=self.customer.phone, last_name=self.customer.last_name
            )
            self.assertEqual(verified_scope(proof)["prior"], member.pk)
            from core.membership_renewals import renewal_details

            self.assertEqual(renewal_details(member)["minimum_months"], 1)
            with self.assertRaises(PermissionDenied):
                create_link(actor=None, prior=member, request_key=uuid.uuid4())
            page = self.client.get(reverse("public_membership_renewal", args=[token_for(link)]))
            self.assertNotContains(page, self.customer.email)
            self.assertNotContains(page, self.customer.last_name)
        with fixtures.clock(
            notice_dates(member.membership.ends_on)["deadline"] + timedelta(days=1)
        ):
            self.assertEqual(resolve_link(token_for(link)).pk, link.pk)
            self.assertEqual(renewal_details(member)["minimum_months"], 3)

    def test_batch_limit_advances_beyond_previous_notices_and_skips_ineligible_members(self):
        first = self.prior()
        second = self.prior()
        with self.window(first):
            self.assertEqual(prepare_due(limit=1)["ready"], 1)
            self.assertEqual(prepare_due(limit=1)["ready"], 1)
            self.assertEqual(prepare_due(limit=1)["ready"], 0)
            self.assertEqual(
                set(MembershipRenewalNotice.objects.values_list("purchase_id", flat=True)),
                {first.pk, second.pk},
            )

    def test_notice_date_changes_at_new_york_midnight_rather_than_utc_midnight(self):
        member = self.prior()
        from core.availability import NEW_YORK

        midnight = datetime.combine(
            notice_dates(member.membership.ends_on)["expiry"], datetime.min.time(), NEW_YORK
        ).astimezone(dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=midnight - timedelta(seconds=1)):
            self.assertEqual(prepare_due()["ready"], 0)
        with patch("django.utils.timezone.now", return_value=midnight):
            self.assertEqual(prepare_due()["ready"], 1)

    def test_returning_to_an_earlier_contact_preserves_cancelled_attempts_and_prepares_one_current_message(
        self,
    ):
        member = self.prior()
        with self.window(member):
            first = prepare_notice(member_id=member.pk, kind="expiry")
            Customer.objects.filter(pk=self.customer.pk).update(email="temporary@example.invalid")
            with patch("core.communications.services.send") as send:
                self.assertEqual(deliver(first.pk).state, "cancelled")
                second = MessageDelivery.objects.get(
                    kind="membership_expiry_notice", state="queued"
                )
                Customer.objects.filter(pk=self.customer.pk).update(email=self.customer.email)
                self.assertEqual(deliver(second.pk).state, "cancelled")
                send.assert_not_called()
            current = MessageDelivery.objects.get(kind="membership_expiry_notice", state="queued")
            self.assertEqual(current.recipient, self.customer.email)
            self.assertEqual(prepare_notice(member_id=member.pk, kind="expiry").pk, current.pk)
            self.assertEqual(
                MessageDelivery.objects.filter(
                    kind="membership_expiry_notice", state="cancelled"
                ).count(),
                2,
            )

    def test_current_contact_and_partial_renewal_supersede_old_snapshot_before_send(self):
        member = self.prior()
        with self.window(member):
            original = prepare_notice(member_id=member.pk, kind="expiry")
            self.follow(member, places=1)
            Customer.objects.filter(pk=self.customer.pk).update(email="new-current@example.invalid")
            with patch("core.communications.services.send") as send:
                self.assertEqual(deliver(original.pk).state, "cancelled")
                send.assert_not_called()
            fresh = MessageDelivery.objects.filter(
                kind="membership_expiry_notice", state="queued"
            ).get()
            self.assertEqual(fresh.recipient, "new-current@example.invalid")
            self.assertIn("1 Subscription membership expires", fresh.text_body)
            original.refresh_from_db()
            self.assertEqual(original.recipient, "family@example.invalid")
            self.assertIn("2 Subscription memberships expire", original.text_body)
            with patch("core.communications.services.send", return_value=str(uuid.uuid4())) as send:
                self.assertEqual(deliver(fresh.pk).state, "sent")
                self.assertEqual(deliver(fresh.pk).state, "sent")
                self.assertEqual(send.call_count, 1)

    def test_full_renewal_cancellation_and_stale_day_stop_an_unsent_notice(self):
        for reason in ("renewed", "cancelled", "late"):
            member = self.prior()
            with self.window(member):
                message = prepare_notice(member_id=member.pk, kind="expiry")
                if reason == "renewed":
                    self.follow(member, places=2)
                elif reason == "cancelled":
                    data = cancellation_review(
                        actor=self.owner,
                        member_id=member.pk,
                        timing="immediate",
                        refund_amount="0.00",
                    )
                    cancel(
                        actor=self.owner,
                        member_id=member.pk,
                        timing="immediate",
                        refund_amount="0.00",
                        reviewed=data["fingerprint"],
                        request_key=uuid.uuid4(),
                        reason="Reviewed cancellation.",
                        early_override=True,
                        send_confirmation=False,
                    )
                day = notice_dates(member.membership.ends_on)["expiry"] + timedelta(
                    days=1 if reason == "late" else 0
                )
                with fixtures.clock(day), patch("core.communications.services.send") as send:
                    self.assertEqual(deliver(message.pk).state, "cancelled")
                    send.assert_not_called()

    def test_overdue_and_missing_contact_do_not_receive_renewal_or_customer_failure_mail(self):
        self.key = uuid.uuid4()
        overdue = self.buy(expected_method="cash", verified_received=True, send_confirmation=False)
        with self.window(overdue):
            self.assertEqual(prepare_due()["ready"], 0)
            self.assertIsNone(prepare_notice(member_id=overdue.pk, kind="expiry"))
        paid = self.prior()
        Customer.objects.filter(pk=self.customer.pk).update(email="")
        with self.window(paid):
            self.assertEqual(prepare_due()["ready"], 0)
        self.assertFalse(MembershipRenewalNotice.objects.exists())

    def test_unknown_delivery_is_not_retried_and_has_no_replacement_snapshot(self):
        member = self.prior()
        with self.window(member):
            message = prepare_notice(member_id=member.pk, kind="expiry")
            with patch("core.communications.services.send", side_effect=MailUnavailable()) as send:
                self.assertEqual(deliver(message.pk).state, "unknown")
                self.assertEqual(deliver(message.pk).state, "unknown")
                self.assertEqual(send.call_count, 1)
            self.assertIsNone(prepare_notice(member_id=member.pk, kind="expiry"))
            self.assertEqual(
                MessageDelivery.objects.filter(kind="membership_expiry_notice").count(), 1
            )

    def test_reported_unrecorded_original_card_return_stops_the_notice(self):
        from tests import test_customer_credit as credit_fixtures

        self.key = uuid.uuid4()
        member = self.buy(billing="prepaid", expected_method="card", send_confirmation=False)
        original = fixtures.MembershipRenewalTests.succeed(self, member)
        with self.window(member):
            message = prepare_notice(member_id=member.pk, kind="expiry")
            credit_fixtures.CustomerCreditTests.external_return(self, original)
            with patch("core.communications.services.send") as send:
                self.assertEqual(deliver(message.pk).state, "cancelled")
                send.assert_not_called()
            self.assertIsNone(prepare_notice(member_id=member.pk, kind="expiry"))

    def test_feature_recovery_and_email_gates_and_html_link_are_truthful(self):
        member = self.prior()
        with self.window(member):
            with (
                override_settings(MEMBERSHIP_SALES_ENABLED=False),
                self.assertRaises(ValidationError),
            ):
                prepare_due()
            with override_settings(RECOVERY_HOLD=True), self.assertRaises(ValidationError):
                prepare_due()
            with override_settings(BOOKING_EMAIL_ENABLED=False):
                self.assertEqual(prepare_due()["ready"], 0)
            message = prepare_notice(member_id=member.pk, kind="expiry")
            html = confirmation_html(message.text_body)
            self.assertIn("Renew membership</a>", html)
            self.assertIn("Ready for more Monkey Do adventures?", html)
            self.assertNotIn("<script>", confirmation_html("<script>alert('x')</script>"))

    def test_runtime_immutable_evidence_and_database_scopes(self):
        member = self.prior()
        with self.window(member), self.runtime_role():
            message = prepare_notice(member_id=member.pk, kind="expiry")
        notice = message.renewal_notice_evidence.notice
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipRenewalNotice.objects.create(
                id=uuid.uuid4(),
                purchase=member,
                kind="grace",
                ends_on=member.membership.ends_on,
                due_on=notice.due_on,
                places=1,
            )
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_membershiprenewalnotice SET places=1 WHERE id=%s", [notice.pk]
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipRenewalLink.objects.create(
                id=uuid.uuid4(),
                prior=member,
                customer=self.customer,
                actor=None,
                expires_at=notice.created_at + timedelta(days=30),
            )
        other = self.prior()
        forged = enqueue(
            key=str(uuid.uuid4()),
            kind="membership_expiry_notice",
            recipient=self.customer.email,
            subject="Scope test",
            text="Scope test",
            customer=self.customer,
            membership=other,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            MembershipRenewalNoticeDelivery.objects.create(notice=notice, message=forged)
        with patch("core.communications.services.send") as send:
            self.assertEqual(deliver(forged.pk).state, "cancelled")
            send.assert_not_called()

    def test_readonly_overview_shows_notice_history_without_queueing_another(self):
        member = self.prior()
        with self.window(member):
            prepare_notice(member_id=member.pk, kind="expiry")
            count = MessageDelivery.objects.count()
            verified_owner_login(self.client, self.owner)
            page = self.client.get(reverse("membership_overview", args=[member.pk]))
            self.assertContains(page, "Renewal notices")
            self.assertContains(page, "Queued")
            self.assertEqual(MessageDelivery.objects.count(), count)

    def test_link_lifetime_across_dst_is_thirty_absolute_days(self):
        with fixtures.clock(datetime(2027, 12, 13).date()):
            member = self.prior(starts_on=datetime(2027, 12, 13).date())
        with self.window(member):
            message = prepare_notice(member_id=member.pk, kind="expiry")
            link = message.renewal_notice_evidence.notice.renewal_link
            self.assertEqual(
                link.expires_at.timestamp() - link.notice.created_at.timestamp(), 30 * 24 * 60 * 60
            )


@override_settings(**SETTINGS)
class RenewalNoticeRaceTests(NoticeFixtures, TransactionTestCase):
    race = race_fixtures.MembershipCancellationRaceTests.race

    def setUp(self):
        fixtures.MembershipRenewalTests.setUp(self)
        if not MembershipPricing.objects.exists():
            MembershipPricing.objects.create()
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def test_competing_producers_prepare_one_scoped_notice(self):
        member = self.prior()
        with self.window(member):
            results = self.race(
                lambda: prepare_notice(member_id=member.pk, kind="expiry"),
                lambda: prepare_notice(member_id=member.pk, kind="expiry"),
            )
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipRenewalNotice.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.filter(kind="membership_expiry_notice").count(), 1)

    def test_full_renewal_and_mail_claim_have_consistent_lock_order_and_no_later_stale_send(self):
        member = self.prior()
        with self.window(member):
            message = prepare_notice(member_id=member.pk, kind="expiry")
            results = self.race(lambda: self.follow(member, places=2), lambda: claim(message.pk))
        self.assertIsNotNone(results[0])
        message.refresh_from_db()
        self.assertIn(message.state, {"sending", "cancelled"})
        if message.state == "cancelled":
            self.assertIsNone(results[1])
        else:
            self.assertIsNotNone(results[1])
