"""Payment history preserves staff access, filters and safe card metadata."""

from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import PaymentOperation
from core.payments.ledger import record_result
from tests import test_payment_ledger as fixtures
from tests.helpers import verified_owner_login


@override_settings(PAYMENT_SANDBOX_ENABLED=True)
class PaymentViewTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create
    sale = fixtures.PaymentLedgerTests.sale
    operation = fixtures.PaymentLedgerTests.operation

    def login(self, owner=True):
        if owner:
            verified_owner_login(self.client, self.owner)
        else:
            self.client.force_login(self.staff)

    def test_history_is_filtered_paged_and_exposes_no_charging_reference(self):
        op = self.operation(self.sale())
        self.login()
        response = self.client.get(reverse("payments"), {"q": self.customer.email, "per_page": 10})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("payment_detail", args=[op.pk]))
        self.assertContains(response, reverse("customer_detail", args=[self.customer.pk]))
        self.assertNotContains(response, self.method.provider_method)
        self.assertEqual(response.context["operations"].paginator.count, 1)
        response = self.client.get(reverse("payments"), {"state": ["unknown", "declined"]})
        self.assertEqual(response.context["operations"].paginator.count, 0)
        response = self.client.get(
            reverse("payments"), {"after": "2027-03-10", "before": "2027-03-09"}
        )
        self.assertEqual(response.context["operations"].paginator.count, 0)
        self.assertContains(response, "The end date must be on or after the start date.")

    def test_detail_shows_only_actual_postings_and_readable_history(self):
        op = self.operation(self.sale())
        record_result(
            operation_id=op.pk, state="unknown", source="provider", code="transport_unknown"
        )
        self.login()
        response = self.client.get(reverse("payment_detail", args=[op.pk]))
        self.assertContains(response, "Outcome unknown")
        self.assertContains(response, "No successful financial amounts")
        self.assertNotContains(response, self.method.provider_method)
        self.assertContains(response, "Check provider result")

    def test_staff_can_view_but_not_reconcile_and_needs_customer_permission(self):
        op = self.operation(self.sale())
        self.login(owner=False)
        detail = reverse("payment_detail", args=[op.pk])
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertNotContains(self.client.get(detail), "Check provider result")
        with patch("core.payments.views.reconcile") as gateway:
            self.assertEqual(self.client.post(detail, {}).status_code, 403)
            gateway.assert_not_called()
        self.staff.groups.clear()
        self.staff.user_permissions.clear()
        self.staff.user_permissions.add(Permission.objects.get(codename="view_paymentoperation"))
        self.client.logout()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(detail).status_code, 403)

    def test_owner_check_never_dispatches_a_new_payment(self):
        op = self.operation(self.sale())
        record_result(operation_id=op.pk, state="unknown", source="provider")
        self.login()
        with patch(
            "core.payments.views.reconcile", return_value=PaymentOperation.objects.get(pk=op.pk)
        ) as lookup:
            response = self.client.post(
                reverse("payment_detail", args=[op.pk]), {"provider_reference": "451"}
            )
        self.assertEqual(response.status_code, 302)
        lookup.assert_called_once_with(
            operation_id=op.pk, actor=self.owner, provider_reference="451"
        )
        with override_settings(PAYMENT_SANDBOX_ENABLED=False):
            self.assertEqual(self.client.get(reverse("payments")).status_code, 404)
