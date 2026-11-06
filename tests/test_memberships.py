import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.membership_calendar import boundary, renewal_start, schedule
from core.memberships import create_draft
from core.models import (
    AuditEvent,
    Booking,
    Customer,
    MembershipDraft,
    MembershipDraftCycle,
    MembershipPricing,
    PricingPolicy,
)
from tests.helpers import verified_owner_login
from tests.test_customers import staff_user
from tests.test_owner_accounts import STORAGES


class MembershipCalendarTests(SimpleTestCase):
    def test_approved_short_month_cases(self):
        for start, charged, reset in [
            (date(2027, 8, 5), date(2027, 9, 5), date(2027, 9, 5)),
            (date(2027, 10, 31), date(2027, 11, 30), date(2027, 12, 1)),
            (date(2027, 1, 29), date(2027, 2, 28), date(2027, 3, 1)),
            (date(2028, 1, 29), date(2028, 2, 29), date(2028, 2, 29)),
            (date(2028, 1, 30), date(2028, 2, 29), date(2028, 3, 1)),
            (date(2028, 1, 31), date(2028, 2, 29), date(2028, 3, 1)),
        ]:
            with self.subTest(start=start):
                self.assertEqual(boundary(start, 1), (charged, reset))
                self.assertEqual(boundary(start, 2)[0].day, start.day)

    def test_cycles_partition_term_without_gaps_and_preserve_anchor(self):
        rows = schedule(date(2027, 10, 31), 3)
        self.assertEqual(
            [(r["starts_on"], r["ends_on"], r["charge_on"]) for r in rows],
            [
                (date(2027, 10, 31), date(2027, 11, 30), date(2027, 10, 31)),
                (date(2027, 12, 1), date(2027, 12, 30), date(2027, 11, 30)),
                (date(2027, 12, 31), date(2028, 1, 30), date(2027, 12, 31)),
            ],
        )

    def test_dst_does_not_change_civil_day_windows(self):
        rows = schedule(date(2027, 2, 14), 12)
        self.assertEqual(rows[1]["starts_on"], date(2027, 3, 14))
        self.assertEqual(rows[9]["starts_on"], date(2027, 11, 14))
        self.assertEqual(rows[-1]["ends_on"], date(2028, 2, 13))

    def test_grace_renewal_and_early_renewal_examples(self):
        expiry = date(2027, 12, 5)
        for day, expected, minimum in [(1, 6, 1), (6, 6, 1), (10, 10, 1), (12, 12, 1), (13, 13, 3)]:
            self.assertEqual(
                renewal_start(expiry, date(2027, 12, day)), (date(2027, 12, expected), minimum)
            )

    def test_whole_months_invalid_and_calendar_overflow(self):
        for months in [0, -1, True, 1.5]:
            with self.assertRaises(ValidationError):
                schedule(date(2027, 1, 1), months)
        with self.assertRaises(ValidationError):
            schedule(date(9999, 12, 31), 1)
        self.assertEqual(len(schedule(date(2027, 1, 1), 25)), 25)


@override_settings(STORAGES=STORAGES)
class MembershipDraftTests(TestCase):
    def setUp(self):
        clock = patch(
            "django.utils.timezone.now",
            return_value=datetime(2027, 1, 1, 12, tzinfo=ZoneInfo("America/New_York")),
        )
        clock.start()
        self.addCleanup(clock.stop)
        self.staff = staff_user()
        self.owner = staff_user("owner", owner=True)
        self.customer = Customer.objects.create(
            last_name="Test Family", phone="2025550188", email="test@example.invalid"
        )
        self.args = dict(
            actor=self.staff,
            customer=self.customer,
            kind="subscription",
            places=2,
            months=3,
            billing="monthly",
            starts_on=date(2028, 1, 31),
            expected_method="card",
            creation_key=uuid.uuid4(),
        )

    def create(self, **changes):
        return create_draft(**(self.args | changes))

    def test_saved_monthly_draft_has_prices_dates_and_no_active_benefits(self):
        draft = self.create()
        self.assertEqual(draft.ends_on, date(2028, 4, 30))
        self.assertEqual(draft.snapshot["original_anchor_day"], 31)
        self.assertFalse(draft.snapshot["benefits_active"])
        self.assertFalse(draft.snapshot["terms_accepted"])
        self.assertEqual(draft.cycles.count(), 3)
        cycle = draft.cycles.get(number=2)
        self.assertEqual(cycle.charge_on, date(2028, 2, 29))
        self.assertEqual(cycle.starts_on, date(2028, 3, 1))
        self.assertEqual(cycle.quote["total"], "37.06")
        self.assertEqual(cycle.quote["sales_tax"], "0.00")
        self.assertFalse(Booking.objects.exists())
        self.assertEqual(
            AuditEvent.objects.get(action="membership.draft_created").actor, self.staff
        )

    def test_prepaid_has_one_whole_term_payment_and_no_later_installments(self):
        draft = self.create(billing="prepaid")
        self.assertEqual(draft.cycles.get(number=1).quote["subtotal"], "107.94")
        self.assertEqual(draft.cycles.get(number=1).quote["total"], "111.18")
        for cycle in draft.cycles.exclude(number=1):
            self.assertIsNone(cycle.charge_on)
            self.assertIsNone(cycle.quote)

    def test_unlimited_and_noncash_fee_rules_and_arbitrary_term(self):
        draft = self.create(kind="unlimited", expected_method="cash", months=7)
        self.assertEqual(draft.cycles.get(number=1).quote["total"], "79.98")
        self.assertEqual(draft.cycles.count(), 7)

    def test_pricing_changes_do_not_rewrite_existing_draft(self):
        first = self.create()
        original = first.cycles.get(number=1).quote
        MembershipPricing.objects.create(subscription="20", unlimited="45", actor=self.owner)
        PricingPolicy.objects.create(card_fee_rate="0.04")
        second = self.create(creation_key=uuid.uuid4())
        self.assertEqual(second.unit_price, Decimal("20"))
        self.assertEqual(second.cycles.get(number=1).quote["total"], "41.60")
        self.assertEqual(first.cycles.get(number=1).quote, original)
        self.assertEqual(MembershipDraft.objects.count(), 2)

    def test_idempotence_and_changed_payload_rejected(self):
        draft = self.create()
        self.assertEqual(self.create().pk, draft.pk)
        with self.assertRaises(ValidationError):
            self.create(places=3)
        self.assertEqual(MembershipDraftCycle.objects.count(), 3)

    def test_initial_minimum_validation_and_overflow(self):
        for changes in [
            {"months": 2},
            {"places": 0},
            {"places": True},
            {"billing": "auto"},
            {"starts_on": date(2000, 1, 1)},
            {"months": 999999999},
        ]:
            with self.assertRaises(ValidationError):
                self.create(**changes)
        self.assertFalse(MembershipDraft.objects.exists())

    def test_audit_failure_rolls_back_draft_and_cycles(self):
        with patch("core.memberships.AuditEvent.objects.create", side_effect=RuntimeError("test")):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertFalse(MembershipDraft.objects.exists())
        self.assertFalse(MembershipDraftCycle.objects.exists())

    def test_draft_cycle_and_price_immutability(self):
        draft = self.create()
        for obj in [draft, draft.cycles.first(), MembershipPricing.objects.first()]:
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                obj.delete()
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(f"UPDATE {obj._meta.db_table} SET id=id WHERE id=%s", [obj.pk])

    def test_permissions_and_csrf(self):
        restricted = get_user_model().objects.create_user(username="restricted", is_staff=True)
        self.client.force_login(restricted)
        self.assertEqual(self.client.get("/staff/memberships/").status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.create(actor=restricted)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(client.post("/staff/memberships/new/", {}).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/staff/memberships/pricing/").status_code, 403)

    def test_forms_and_snapshot_not_client_supplied(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            "/staff/memberships/new/",
            {
                **{k: v for k, v in self.args.items() if k != "actor"},
                "customer": self.customer.pk,
                "starts_on": "2028-01-31",
                "unit_price": "0.01",
                "benefits_active": True,
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertContains(self.client.get(response.url), "Benefits inactive")
        self.assertEqual(MembershipDraft.objects.get().unit_price, Decimal("17.99"))

    def test_owner_prices_append_version_and_leave_draft_intact(self):
        draft = self.create()
        verified_owner_login(self.client, self.owner)
        response = self.client.post(
            "/staff/memberships/pricing/", {"subscription": "21", "unlimited": "44"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MembershipPricing.objects.first().subscription, Decimal("21"))
        self.assertEqual(draft.unit_price, Decimal("17.99"))
