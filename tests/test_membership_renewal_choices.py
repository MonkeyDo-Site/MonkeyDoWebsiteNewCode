"""Completed history cannot hide choices or discard already reviewed selections."""

from unittest.mock import patch

from django import forms
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core import membership_renewal_choices as choices
from core.membership_batch_records import MembershipRenewalBatch
from core.models import Customer, PaymentOperation
from tests import test_membership_batch_renewals as fixtures
from tests import test_membership_batch_views as view_fixtures
from tests.test_membership_initial_credit import SETTINGS


@override_settings(**SETTINGS)
class RenewalChoiceTests(TestCase):
    setUp = fixtures.CombinedRenewalTests.setUp
    buy = fixtures.CombinedRenewalTests.buy
    prior = fixtures.CombinedRenewalTests.prior
    follow = fixtures.CombinedRenewalTests.follow
    follow_values = fixtures.CombinedRenewalTests.follow_values
    family = fixtures.CombinedRenewalTests.family
    prepare = view_fixtures.CombinedRenewalViewTests.prepare

    def payload(self, response):
        rows, checkout = response.context["formset"], response.context["checkout"]
        data = {
            "renewals-TOTAL_FORMS": str(rows.total_form_count()),
            "renewals-INITIAL_FORMS": str(rows.initial_form_count()),
            "renewals-MIN_NUM_FORMS": "0",
            "renewals-MAX_NUM_FORMS": "100",
        }
        for field in checkout:
            value = field.value()
            if isinstance(field.field, forms.BooleanField):
                if value is True:
                    data[field.name] = "on"
            else:
                data[field.name] = "" if value is None else str(value)
        for i, row in enumerate(rows):
            for field in row:
                value = field.value()
                if isinstance(field.field, forms.BooleanField):
                    if value is True:
                        data[f"renewals-{i}-{field.name}"] = "on"
                else:
                    data[f"renewals-{i}-{field.name}"] = "" if value is None else str(value)
        return data

    def test_fully_renewed_original_is_filtered_before_the_page_limit(self):
        self.family()
        self.follow(self.first, places=2)
        before = PaymentOperation.objects.count()
        page, _, cursor = choices.page(self.customer.pk, limit=1)
        self.assertEqual([row[0].pk for row in page], [self.second.pk])
        self.assertNotIn(
            self.first.pk, choices.candidates(self.customer.pk).values_list("pk", flat=True)
        )
        self.assertIsNotNone(cursor)
        self.assertEqual(PaymentOperation.objects.count(), before)

    def test_unpaid_earlier_record_does_not_hide_later_paid_choice(self):
        unpaid = self.buy(billing="prepaid", expected_method="card", places=1)
        paid = self.prior(places=1)
        before = PaymentOperation.objects.count()
        page, unavailable, _ = choices.page(self.customer.pk, limit=1)
        self.assertEqual([row[0].pk for row in page], [paid.pk])
        self.assertEqual([row[0].pk for row in unavailable], [unpaid.pk])
        self.assertEqual(PaymentOperation.objects.count(), before)

    def test_number_and_type_search_only_return_this_customers_records(self):
        self.family()
        for query in [f"M{self.second.pk}", f"#m{self.second.pk}", "UNLIMITED"]:
            with self.subTest(query=query):
                page, _, _ = choices.page(self.customer.pk, query=query)
                self.assertEqual([row[0].pk for row in page], [self.second.pk])
        other = Customer.objects.create(
            last_name="Other", phone="2025550189", email="other@example.invalid"
        )
        self.assertEqual(choices.page(other.pk, query=f"M{self.first.pk}")[0], [])
        with self.assertRaisesMessage(ValidationError, "Search again"):
            choices.page(other.pk, cursor=self.first.pk)

    def test_show_more_keeps_counts_terms_cards_tender_and_request_identity(self):
        self.prepare()
        before = PaymentOperation.objects.count()
        with patch.object(choices, "PAGE_SIZE", 1):
            first = self.client.get(self.url)
            data = self.payload(first)
            key = data["request_key"]
            data.update(
                {
                    "action": "more",
                    "renewals-0-renew": "on",
                    "renewals-0-places": "1",
                    "renewals-0-months": "2",
                    "renewals-0-billing": "monthly",
                    "renewals-0-method_id": str(self.method.pk),
                    "tender": "check",
                    "accepted": "on",
                    "verified_received": "on",
                }
            )
            response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        rows = response.context["formset"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["renew"].value())
        self.assertEqual(rows[0]["places"].value(), 1)
        self.assertEqual(rows[0]["months"].value(), 2)
        self.assertEqual(rows[0]["billing"].value(), "monthly")
        self.assertEqual(rows[0]["method_id"].value(), str(self.method.pk))
        self.assertEqual(rows[1]["prior_id"].value(), self.second.pk)
        checkout = response.context["checkout"]
        self.assertEqual(str(checkout["request_key"].value()), key)
        self.assertEqual(checkout["tender"].value(), "check")
        self.assertFalse(checkout["accepted"].value())
        self.assertFalse(checkout["verified_received"].value())
        self.assertTrue(checkout["reviewed"].value())
        self.assertEqual(PaymentOperation.objects.count(), before)
        final = self.payload(response) | dict(
            action="confirm", accepted="on", verified_received="on"
        )
        saved = self.client.post(self.url, final)
        self.assertEqual(saved.status_code, 302)
        self.assertEqual(str(MembershipRenewalBatch.objects.get().amount), "17.99")
        self.assertEqual(PaymentOperation.objects.count(), before + 1)

    def test_search_keeps_selected_rows_even_when_they_do_not_match_the_query(self):
        self.prepare()
        before = PaymentOperation.objects.count()
        data = self.payload(self.client.get(self.url))
        data.update(
            {
                "action": "search",
                "query": f"M{self.second.pk}",
                "renewals-0-renew": "on",
                "renewals-0-kind": "unlimited",
                "renewals-0-places": "1",
                "renewals-0-months": "2",
            }
        )
        response = self.client.post(self.url, data)
        rows = response.context["formset"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["prior_id"].value(), self.first.pk)
        self.assertEqual(rows[0]["kind"].value(), "unlimited")
        self.assertEqual(rows[0]["months"].value(), 2)
        self.assertEqual(rows[1]["prior_id"].value(), self.second.pk)
        self.assertContains(response, "Selected memberships and their details stay")
        self.assertEqual(PaymentOperation.objects.count(), before)

    def test_changed_query_does_not_reuse_an_unrelated_cursor(self):
        self.prepare()
        data = self.payload(self.client.get(self.url))
        data.update(
            action="more",
            query=f"M{self.first.pk}",
            query_used="unlimited",
            cursor=str(self.second.pk),
        )
        response = self.client.post(self.url, data)
        self.assertEqual(
            [row["prior_id"].value() for row in response.context["formset"]], [self.first.pk]
        )

    def test_invalid_selected_input_remains_visible_instead_of_being_lost_on_browse(self):
        self.prepare()
        data = self.payload(self.client.get(self.url))
        data.update(
            {
                "action": "search",
                "query": "unlimited",
                "renewals-0-renew": "on",
                "renewals-0-places": "0",
            }
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.context["formset"][0]["places"].value(), "0")
        self.assertContains(response, "greater than or equal to 1")
        self.assertFalse(MembershipRenewalBatch.objects.exists())

    def test_browsing_keeps_a_monthly_selection_that_still_needs_a_future_card(self):
        self.prepare()
        data = self.payload(self.client.get(self.url))
        data.update(
            {
                "action": "search",
                "query": "unlimited",
                "renewals-0-renew": "on",
                "renewals-0-billing": "monthly",
                "renewals-0-method_id": "",
            }
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a saved card")
        self.assertTrue(response.context["formset"][0]["renew"].value())
        self.assertEqual(response.context["formset"][0]["billing"].value(), "monthly")
        self.assertFalse(MembershipRenewalBatch.objects.exists())
