"""Unused historical terms require explicit owner authority, not rewritten purchases."""

import uuid
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.membership_calendar_changes import (
    OWNER_ACKNOWLEDGMENT,
    confirm,
    review,
    root_for,
)
from core.membership_calendar_records import MembershipCalendarCorrection
from core.membership_sales import membership_status
from core.models import PaymentOperation
from tests import test_membership_calendar_changes as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS
from tests.test_payment_runtime_grants import RuntimeRoleMixin


class OwnerDateFixtures:
    setUp = fixtures.MembershipCalendarCorrectionTests.setUp
    buy = fixtures.MembershipCalendarCorrectionTests.buy
    succeed = fixtures.MembershipCalendarCorrectionTests.succeed
    prepaid = fixtures.MembershipCalendarCorrectionTests.prepaid
    evidence = fixtures.MembershipCalendarCorrectionTests.evidence

    def at(self, day):
        return patch(
            "django.utils.timezone.now",
            return_value=datetime.combine(
                day, datetime.min.time(), ZoneInfo("America/New_York")
            ).replace(hour=12),
        )

    def owner_values(self, **changes):
        return (self.inputs | dict(actor=self.owner)) | changes

    def save_owner(self, **changes):
        values = self.owner_values(**changes)
        return confirm(
            **values,
            request_key=self.date_key,
            reviewed=review(**values)["fingerprint"],
            customer_confirmed=True,
            owner_approved=True,
        )


@override_settings(**SETTINGS)
class OwnerUnusedDateTests(OwnerDateFixtures, RuntimeRoleMixin, TestCase):
    def test_started_unused_prepaid_preserves_original_evidence_and_same_membership(self):
        self.prepaid()
        before = self.evidence()
        with self.at(date(2027, 11, 1)), self.runtime_role():
            proposed = review(**self.owner_values())
            self.assertTrue(proposed["owner_date_exception"])
            self.assertEqual(proposed["owner_acknowledgment"], OWNER_ACKNOWLEDGMENT)
            self.assertFalse(MembershipCalendarCorrection.objects.exists())
            saved = self.save_owner()
            self.assertEqual(membership_status(self.member), "scheduled")
            connection.check_constraints()
        after = self.evidence()
        before["root"].pop("_state")
        after["root"].pop("_state")
        self.assertEqual(before, after)
        self.assertEqual(saved.purchase_id, self.member.pk)
        self.assertEqual(root_for(self.member).starts_on, date(2027, 11, 5))
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_existing_customer_confirmation_does_not_implicitly_approve_an_owner_exception(self):
        self.prepaid()
        with self.at(date(2027, 11, 1)):
            values = self.owner_values()
            data = review(**values)
            for approved in (False, 1):
                with (
                    self.subTest(approved=approved),
                    self.assertRaisesMessage(ValidationError, "explicitly approve"),
                ):
                    confirm(
                        **values,
                        request_key=self.date_key,
                        reviewed=data["fingerprint"],
                        customer_confirmed=True,
                        owner_approved=approved,
                    )
        self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_staff_cannot_correct_a_started_term_or_backdate_a_future_term(self):
        self.prepaid()
        with self.assertRaisesMessage(ValidationError, "Only the owner"):
            review(**(self.inputs | dict(starts_on=date(2027, 10, 30))))
        with (
            self.at(date(2027, 11, 1)),
            self.assertRaisesMessage(ValidationError, "owner date exception"),
        ):
            review(**self.inputs)
        self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_owner_past_start_retains_cycle_ids_and_uses_current_corrected_cycle(self):
        from core.membership_calendar_changes import cycle_on
        from core.membership_reservations import places_for

        self.prepaid()
        with self.at(date(2027, 11, 1)):
            self.save_owner(starts_on=date(2027, 10, 30))
            self.assertEqual(membership_status(self.member), "active")
            offered = places_for(self.customer.pk, appointment_on=date(2027, 11, 2), children=1)
            self.assertEqual(len(offered), 1)
            self.assertEqual(offered[0].cycle_starts_on, date(2027, 10, 30))
            self.assertEqual(
                cycle_on(self.member, date(2027, 11, 2)).pk,
                self.member.membership.cycles.get(number=1).pk,
            )
        self.assertFalse(self.member.benefit_assignments.exists())
        connection.check_constraints()

    def test_expired_unused_complimentary_term_can_be_moved_without_new_money(self):
        self.member = self.buy(actor=self.owner, comped=True, send_confirmation=False)
        self.inputs = dict(
            member_id=self.member.pk,
            starts_on=date(2028, 2, 8),
            reason="Owner and customer agreed to move the unused term.",
            send_confirmation=False,
        )
        self.date_key = uuid.uuid4()
        with self.at(date(2028, 2, 5)):
            self.assertEqual(membership_status(self.member), "expired")
            self.save_owner()
            self.assertEqual(membership_status(self.member), "scheduled")
        self.assertEqual(PaymentOperation.objects.count(), 0)
        self.assertEqual(self.member.membership.starts_on, date(2027, 10, 31))
        connection.check_constraints()

    def test_expired_paid_term_may_remain_expired_with_corrected_history(self):
        from core.membership_reporting import reporting_members

        self.prepaid()
        with self.at(date(2028, 2, 5)):
            self.save_owner(starts_on=date(2027, 10, 30))
            self.assertEqual(membership_status(self.member), "expired")
            listed = reporting_members(on=date(2028, 2, 5)).get(pk=self.member.pk)
            self.assertEqual(listed.report_status, "expired")
            self.assertEqual(listed.effective_ends_on, date(2028, 1, 29))
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_owner_does_not_override_monthly_or_any_prior_benefit_assignment(self):
        from core.membership_reservations import finish, reserve
        from tests.test_membership_reservations import MembershipReservationTests

        self.prepaid()
        with self.at(date(2027, 11, 1)):
            booking = MembershipReservationTests.booking(self, day=date(2027, 11, 2), children=1)
            quote = MembershipReservationTests.quote(self, booking)
            reserve(
                actor=self.staff, booking_id=booking.pk, quote_id=quote.pk, request_key=uuid.uuid4()
            )
            for action in (None, "released"):
                if action:
                    finish(
                        actor=self.staff,
                        booking_id=booking.pk,
                        request_key=uuid.uuid4(),
                        action=action,
                        reason="cancellation",
                    )
                with self.assertRaisesMessage(ValidationError, "used in a booking"):
                    review(**self.owner_values())
        self.key = uuid.uuid4()
        monthly = self.buy()
        self.succeed(monthly)
        with (
            self.at(date(2027, 11, 1)),
            self.assertRaisesMessage(ValidationError, "payment-schedule"),
        ):
            review(**self.owner_values(member_id=monthly.pk))

    def test_dates_only_email_and_replay_do_not_collect_or_message_twice(self):
        self.prepaid()
        with self.at(date(2027, 11, 1)), patch("core.payments.operations.Gateway") as provider:
            values = self.owner_values(send_confirmation=True)
            proposed = review(**values)
            saved = self.save_owner(send_confirmation=True)
            replay = confirm(
                **values,
                request_key=self.date_key,
                reviewed=proposed["fingerprint"],
                customer_confirmed=True,
                owner_approved=True,
            )
            self.assertEqual(saved.pk, replay.pk)
            message = saved.messages.get().message
            self.assertIn("November 5, 2027", message.text_body)
            self.assertNotIn("payment of", message.text_body)
            self.assertEqual(message.state, "queued")
            provider.assert_not_called()
        self.assertEqual(MembershipCalendarCorrection.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_database_refuses_missing_false_or_staff_owner_authority(self):
        self.prepaid()
        with self.at(date(2027, 11, 1)):
            data = review(**self.owner_values())
            for mode in ("missing", "false", "staff"):
                facts = dict(data)
                actor = self.owner
                if mode == "missing":
                    facts.pop("owner_date_exception")
                    facts.pop("owner_acknowledgment")
                elif mode == "false":
                    facts["owner_date_exception"] = False
                else:
                    actor = self.staff
                    facts["actor"] = actor.pk
                with (
                    self.subTest(mode=mode),
                    self.assertRaises(DatabaseError),
                    transaction.atomic(),
                ):
                    MembershipCalendarCorrection.objects.create(
                        id=uuid.uuid4(),
                        purchase=self.member,
                        version=1,
                        starts_on=date.fromisoformat(data["starts_on"]),
                        ends_on=date.fromisoformat(data["ends_on"]),
                        before=data["before"],
                        cycles=data["cycles"],
                        facts=facts,
                        fingerprint=data["fingerprint"],
                        reason=data["reason"],
                        customer_confirmed=True,
                        send_confirmation=False,
                        actor=actor,
                    )
        self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_owner_does_not_override_unconfirmed_payment(self):
        self.member = self.buy(billing="prepaid")
        self.inputs = dict(
            member_id=self.member.pk,
            starts_on=date(2027, 11, 5),
            reason="Correct intended start.",
            send_confirmation=False,
        )
        with self.at(date(2027, 11, 1)), self.assertRaisesMessage(ValidationError, "payment"):
            review(**self.owner_values())
        self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_owner_does_not_override_a_linked_addition(self):
        self.prepaid()
        self.key = uuid.uuid4()
        self.buy(
            operation="addition",
            prior_id=self.member.pk,
            places=1,
            billing="prepaid",
            expected_method="cash",
            verified_received=True,
        )
        with self.at(date(2027, 11, 1)), self.assertRaisesMessage(ValidationError, "linked"):
            review(**self.owner_values())
        self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_stale_owner_approval_is_not_used_for_an_ordinary_future_correction(self):
        self.prepaid()
        values = self.owner_values()
        quoted = review(**values)
        self.assertNotIn("owner_date_exception", quoted)
        with self.assertRaisesMessage(ValidationError, "explicitly approve"):
            confirm(
                **values,
                request_key=self.date_key,
                reviewed=quoted["fingerprint"],
                customer_confirmed=True,
                owner_approved=True,
            )
        saved = confirm(
            **values,
            request_key=self.date_key,
            reviewed=quoted["fingerprint"],
            customer_confirmed=True,
        )
        self.assertNotIn("owner_date_exception", saved.facts)

    def test_owner_exception_is_unavailable_before_reviewed_upgrade(self):
        self.prepaid()
        with (
            self.at(date(2027, 11, 1)),
            patch("core.membership_calendar_changes.owner_dates_available", return_value=False),
            self.assertRaisesMessage(ValidationError, "upgrade"),
        ):
            review(**self.owner_values())


@override_settings(**SETTINGS)
class OwnerUnusedDateViewTests(OwnerDateFixtures, TestCase):
    def test_combined_acknowledgment_and_same_page_confirmation(self):
        self.prepaid()
        with self.at(date(2027, 11, 1)):
            verified_owner_login(self.client, self.owner)
            url = reverse("membership_overview", args=[self.member.pk])
            page = self.client.get(url)
            self.assertIsNotNone(page.context["calendar_form"])
            form = page.context["calendar_form"]
            data = {
                field.html_name: str(field.value()) for field in form if field.value() is not None
            } | {
                "calendar-starts_on": "2027-11-05",
                "calendar-reason": "Customer agreed to move this unused term.",
                "calendar-send_confirmation": "no",
            }
            reply = self.client.post(url, data | dict(action="calendar_review", format="json"))
            self.assertEqual(reply.status_code, 200, reply.content)
            self.assertTrue(reply.json()["owner_approved"])
            self.assertEqual(reply.json()["acknowledgment"], OWNER_ACKNOWLEDGMENT)
            self.assertIn("Owner date exception", reply.json()["html"])
            saved = self.client.post(
                url,
                data
                | {
                    "action": "calendar_confirm",
                    "calendar-reviewed": reply.json()["fingerprint"],
                    "calendar-customer_confirmed": "on",
                    "calendar-owner_approved": "True",
                },
            )
            self.assertRedirects(saved, url)
            self.assertContains(self.client.get(url), "Owner date exception approved")
            self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_staff_sees_history_without_owner_editor_for_started_term(self):
        self.prepaid()
        with self.at(date(2027, 11, 1)):
            verified_owner_login(self.client, self.staff)
            page = self.client.get(reverse("membership_overview", args=[self.member.pk]))
            self.assertIsNone(page.context["calendar_form"])
            self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_no_javascript_review_renders_the_explicit_owner_acknowledgment(self):
        self.prepaid()
        with self.at(date(2027, 11, 1)):
            verified_owner_login(self.client, self.owner)
            url = reverse("membership_overview", args=[self.member.pk])
            form = self.client.get(url).context["calendar_form"]
            data = {
                field.html_name: str(field.value()) for field in form if field.value() is not None
            } | {
                "calendar-starts_on": "2027-11-05",
                "calendar-reason": "Customer agreed to move this unused term.",
                "calendar-send_confirmation": "no",
                "action": "calendar_review",
            }
            reply = self.client.post(url, data)
            self.assertEqual(reply.status_code, 200)
            self.assertContains(reply, OWNER_ACKNOWLEDGMENT)
            self.assertEqual(reply.context["calendar_form"]["owner_approved"].value(), "True")
            self.assertFalse(MembershipCalendarCorrection.objects.exists())

    def test_stale_no_javascript_confirmation_returns_with_a_clear_blocking_message(self):
        from core.membership_reservations import reserve
        from tests.test_membership_reservations import MembershipReservationTests

        self.prepaid()
        with self.at(date(2027, 11, 1)):
            verified_owner_login(self.client, self.owner)
            url = reverse("membership_overview", args=[self.member.pk])
            form = self.client.get(url).context["calendar_form"]
            data = {
                field.html_name: str(field.value()) for field in form if field.value() is not None
            } | {
                "calendar-starts_on": "2027-11-05",
                "calendar-reason": "Customer agreed to move the unused term.",
                "calendar-send_confirmation": "no",
            }
            reviewed = self.client.post(url, data | dict(action="calendar_review"))
            fingerprint = reviewed.context["calendar_form"]["reviewed"].value()
            booking = MembershipReservationTests.booking(self, day=date(2027, 11, 2), children=1)
            quote = MembershipReservationTests.quote(self, booking)
            reserve(
                actor=self.staff, booking_id=booking.pk, quote_id=quote.pk, request_key=uuid.uuid4()
            )
            refused = self.client.post(
                url,
                data
                | {
                    "action": "calendar_confirm",
                    "calendar-reviewed": fingerprint,
                    "calendar-owner_approved": "True",
                    "calendar-customer_confirmed": "on",
                },
            )
            self.assertRedirects(refused, url, fetch_redirect_response=False)
            self.assertContains(self.client.get(url), "used in a booking")
            self.assertFalse(MembershipCalendarCorrection.objects.exists())
            self.assertEqual(root_for(self.member).starts_on, date(2027, 10, 31))
            self.assertEqual(PaymentOperation.objects.count(), 1)
