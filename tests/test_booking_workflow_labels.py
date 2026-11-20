"""Stable provenance labels/filters preserve older records without converting them."""

import uuid

from django.test import TestCase
from django.urls import reverse

from core.booking_management import create_test_booking
from core.models import Booking
from tests import test_payment_ledger as fixtures
from tests.helpers import verified_owner_login


class BookingWorkflowTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create

    def test_filter_and_badge_do_not_reclassify_old_cancelled_or_current_records(self):
        session = self.create()
        old = create_test_booking(
            actor=self.owner,
            customer=self.customer,
            session_id=session.pk,
            children=1,
            adults=1,
            creation_key=uuid.uuid4(),
        )
        new = create_test_booking(
            actor=self.owner,
            customer=self.customer,
            session_id=session.pk,
            children=1,
            adults=1,
            creation_key=uuid.uuid4(),
        )
        Booking.objects.filter(pk=old.pk).update(attendance="cancelled")
        Booking.objects.filter(pk=new.pk).update(workflow="integrated_v1")
        verified_owner_login(self.client, self.owner)
        response = self.client.get(reverse("bookings"), {"workflow": "legacy_test"})
        self.assertEqual(
            list(response.context["bookings"].object_list), [Booking.objects.get(pk=old.pk)]
        )
        self.assertContains(response, "Old test booking")
        response = self.client.get(reverse("bookings"), {"workflow": "integrated_v1"})
        self.assertEqual(response.context["bookings"].paginator.count, 1)
        self.assertEqual(response.context["bookings"][0].pk, new.pk)
        old.refresh_from_db()
        self.assertEqual(old.workflow, "legacy_test")
        self.assertEqual(old.attendance, "cancelled")
        response = self.client.get(reverse("today"), {"workflow": "integrated_v1"})
        self.assertEqual(response.context["bookings"].paginator.count, 1)
