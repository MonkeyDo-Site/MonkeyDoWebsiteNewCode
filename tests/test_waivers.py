"""Evidence integrity, explicit consent, current coverage, shared-link privacy and retention."""

import hashlib
import io
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import AuditEvent, Session, WaiverSignature, WaiverVersion
from core.waivers.services import (
    VERSION,
    approved_version,
    create_share,
    expire_evidence,
    plus_years,
    share_expiration,
    share_for_token,
    sign,
    valid_customer_signatures,
)
from core.waivers.storage import EvidenceStore, EvidenceUnavailable
from tests import test_payment_setup as fixtures
from tests.helpers import verified_owner_login

NY = ZoneInfo("America/New_York")


class MemoryEvidence:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, expected_hash):
        if key in self.objects and self.objects[key] != data:
            raise EvidenceUnavailable()
        self.objects[key] = data
        return self.get(key, expected_hash)

    def get(self, key, expected_hash):
        data = self.objects[key]
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise EvidenceUnavailable()
        return data

    def delete(self, key):
        self.objects.pop(key, None)


@override_settings(WAIVER_ENABLED=True, CUSTOMER_TEST_BOOKING=True, PAYMENT_SANDBOX_ENABLED=True)
class WaiverTests(TestCase):
    setUp = fixtures.CardSetupTests.setUp
    create = fixtures.CardSetupTests.create
    sale = fixtures.CardSetupTests.sale
    flow = fixtures.CardSetupTests.flow

    def signing_data(self, **changes):
        version = approved_version()
        return {
            "request_key": uuid.uuid4(),
            "version": version.pk,
            "text_hash": version.text_hash,
            "signer_name": "Test Guardian",
            "signer_email": "guardian@example.invalid",
            "signer_phone": "",
            "relationship": "Parent",
            "minors": "Test Minor",
            "adult_accepted": True,
            "waiver_accepted": True,
            "electronic_accepted": True,
        } | changes

    def test_approved_complete_text_and_explicit_consent_are_required_before_storage(self):
        version = approved_version()
        self.assertIn("EVEN IF ARISING FROM THE NEGLIGENCE", version.legal_html)
        self.assertIn("psychological, emotional, spiritual", version.legal_html)
        self.assertEqual(len(version.source_hash), 64)
        for changes in (
            {"adult_accepted": False},
            {"electronic_accepted": False},
            {"waiver_accepted": False},
            {"text_hash": "changed"},
            {"relationship": "Self"},
            {"minors": ""},
        ):
            with (
                self.subTest(changes=changes),
                patch("core.waivers.services.EvidenceStore") as store,
            ):
                with self.assertRaises(ValidationError):
                    sign(data=self.signing_data(**changes), flow=self.flow())
                store.assert_not_called()
        self.assertFalse(WaiverSignature.objects.exists())

    def test_saved_evidence_is_exact_repeatable_and_kept_out_of_database(self):
        flow = self.flow()
        data = self.signing_data(signer_name="<script>Test</script>")
        memory = MemoryEvidence()
        with patch("core.waivers.services.EvidenceStore", return_value=memory):
            first = sign(data=data, flow=flow)
            second = sign(data=data, flow=flow)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.state, "signed")
        self.assertEqual(len(memory.objects), 1)
        document = memory.objects[first.object_key].decode()
        self.assertIn("&lt;script&gt;Test&lt;/script&gt;", document)
        self.assertNotIn("<script>Test</script>", document)
        self.assertIn("Test Minor", document)
        self.assertEqual(AuditEvent.objects.filter(action="waiver.signed").count(), 1)
        self.assertEqual(list(valid_customer_signatures(self.customer)), [first])
        self.assertFalse(
            any(
                field.get_internal_type() == "BinaryField" for field in WaiverSignature._meta.fields
            )
        )
        with self.assertRaises(ValidationError):
            sign(data=data | {"signer_name": "Another Guardian"}, flow=flow)

    def test_storage_failure_leaves_pending_and_same_request_can_recover_without_duplicate_signature(
        self,
    ):
        data, flow = self.signing_data(), self.flow()
        with patch("core.waivers.services.EvidenceStore") as store:
            store.return_value.put.side_effect = EvidenceUnavailable()
            with self.assertRaises(EvidenceUnavailable):
                sign(data=data, flow=flow)
        signature = WaiverSignature.objects.get()
        self.assertEqual(signature.state, "pending")
        self.assertFalse(valid_customer_signatures(self.customer).exists())
        with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
            result = sign(data=data, flow=flow)
        self.assertEqual(result.pk, signature.pk)
        self.assertEqual(result.state, "signed")

    def test_owner_reconciles_written_evidence_without_repeating_upload_or_signing(self):
        from core.waivers.services import reconcile_evidence

        self.sale()
        _, token = create_share(actor=self.owner, booking_id=self.booking.pk)
        memory = MemoryEvidence()
        with patch("core.waivers.services.EvidenceStore", return_value=memory):
            with patch(
                "core.waivers.services.complete_signature",
                side_effect=ValidationError("Interrupted local save"),
            ):
                with self.assertRaises(ValidationError):
                    sign(data=self.signing_data(), share_token=token)
            pending = WaiverSignature.objects.get()
            self.assertEqual(pending.state, "pending")
            self.assertEqual(pending.booking_links.get().booking_id, self.booking.pk)
            verified = reconcile_evidence(actor=self.owner, signature_id=pending.pk)
        self.assertEqual(verified.state, "signed")
        self.assertEqual(WaiverSignature.objects.count(), 1)

    def test_paper_mark_is_audited_booking_fact_and_not_an_electronic_signature(self):
        from core.waivers.services import booking_coverage, set_paper

        self.sale()
        review = set_paper(actor=self.staff, booking_id=self.booking.pk, revision=0, signed=True)
        self.assertTrue(booking_coverage(self.booking))
        self.assertFalse(WaiverSignature.objects.exists())
        self.assertTrue(AuditEvent.objects.filter(action="waiver.paper_reviewed").exists())
        with self.assertRaises(ValidationError):
            set_paper(actor=self.staff, booking_id=self.booking.pk, revision=0, signed=False)
        set_paper(
            actor=self.staff, booking_id=self.booking.pk, revision=review.revision, signed=False
        )
        self.assertFalse(booking_coverage(self.booking))

    def test_shared_signing_exposes_only_appointment_and_allows_independent_parents(self):
        self.sale()
        link, token = create_share(actor=self.owner, booking_id=self.booking.pk)
        response = self.client.get(reverse("shared_waiver", args=[token]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.customer.email)
        self.assertNotContains(response, self.customer.phone)
        self.assertNotContains(response, str(self.booking.reference))
        memory = MemoryEvidence()
        with patch("core.waivers.services.EvidenceStore", return_value=memory):
            first = sign(data=self.signing_data(), share_token=token)
            second = sign(data=self.signing_data(signer_name="Second Guardian"), share_token=token)
        self.assertEqual(self.booking.waiver_links.count(), 2)
        self.assertFalse(first.customer_links.exists())
        response = self.client.get(reverse("shared_waiver", args=[token]))
        self.assertNotContains(response, first.signer_name)
        self.assertNotContains(response, second.signer_name)
        self.assertEqual(share_for_token(token).pk, link.pk)
        self.assertNotEqual(link.token_hash, token)

    def test_link_expiry_uses_new_york_next_day_and_follows_rescheduling(self):
        self.sale()
        link, token = create_share(actor=self.owner, booking_id=self.booking.pk)
        deadline = share_expiration(self.booking)
        with patch("django.utils.timezone.now", return_value=deadline + timedelta(seconds=1)):
            with self.assertRaisesMessage(ValidationError, "this link has expired"):
                share_for_token(token)
            Session.objects.filter(pk=self.booking.session_id).update(
                starts_at=self.booking.session.starts_at + timedelta(days=2),
                ends_at=self.booking.session.ends_at + timedelta(days=2),
            )
            self.assertEqual(share_for_token(token).pk, link.pk)

    def test_leap_year_anniversary_preserves_new_york_wall_time(self):
        moment = datetime(2028, 2, 29, 17, 23, tzinfo=NY)
        self.assertEqual(plus_years(moment, 1), datetime(2029, 2, 28, 17, 23, tzinfo=NY))
        self.assertEqual(plus_years(moment, 2), datetime(2030, 2, 28, 17, 23, tzinfo=NY))

    def test_retention_deletes_only_remote_file_and_keeps_minimal_history(self):
        memory = MemoryEvidence()
        when = timezone.now()
        with patch("core.waivers.services.EvidenceStore", return_value=memory):
            signature = sign(data=self.signing_data(), flow=self.flow())
            self.assertEqual(expire_evidence(), 0)
            with patch(
                "django.utils.timezone.now", return_value=plus_years(when, 2) + timedelta(seconds=1)
            ):
                self.assertEqual(expire_evidence(), 1)
        signature.refresh_from_db()
        self.assertEqual(signature.state, "deleted")
        self.assertIsNotNone(signature.deleted_at)
        self.assertEqual(signature.signer_name, "Test Guardian")
        self.assertEqual(signature.signer_email, "")
        self.assertEqual(signature.signer_phone, "")
        self.assertEqual(signature.user_agent, "")
        self.assertIsNone(signature.ip_address)
        self.assertFalse(memory.objects)
        self.assertTrue(AuditEvent.objects.filter(action="waiver.evidence_removed").exists())

    def test_sql_rewriting_signed_metadata_or_legal_text_is_blocked(self):
        with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
            signature = sign(data=self.signing_data(), flow=self.flow())
        with self.assertRaises(DatabaseError), transaction.atomic():
            WaiverSignature.objects.filter(pk=signature.pk).update(signer_name="Overwritten")
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_waiverversion SET legal_html=%s WHERE code=%s", ["Changed", VERSION]
            )
        self.assertEqual(WaiverVersion.objects.get().text_hash, signature.version.text_hash)

    def test_staff_history_search_and_evidence_permission_are_separate(self):
        memory = MemoryEvidence()
        with patch("core.waivers.services.EvidenceStore", return_value=memory):
            signature = sign(data=self.signing_data(), flow=self.flow())
            verified_owner_login(self.client, self.owner)
            response = self.client.get(reverse("waivers"), {"q": "Test Minor", "status": "valid"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["signatures"].paginator.count, 1)
            response = self.client.get(reverse("waiver_evidence", args=[signature.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertIn("sandbox", response["Content-Security-Policy"])
            self.assertContains(response, "Test Minor")
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("waiver_evidence", args=[signature.pk])).status_code, 302
        )


@override_settings(
    WAIVER_ENABLED=True,
    R2_ACCOUNT_ID="a" * 32,
    R2_WAIVER_BUCKET="monkeydo-waivers-staging",
    R2_WAIVER_ACCESS_KEY="fake-key",
    R2_WAIVER_SECRET_KEY="fake-secret",
)
class EvidenceStorageTests(SimpleTestCase):
    def test_storage_is_fixed_private_endpoint_bounded_and_verifies_actual_bytes(self):
        data = b"synthetic signed evidence"
        digest = hashlib.sha256(data).hexdigest()
        with patch("core.waivers.storage.boto3.client") as client:
            client.return_value.get_object.return_value = {
                "Body": io.BytesIO(data),
                "ContentLength": len(data),
            }
            store = EvidenceStore()
            key = "staging/waivers/" + "a" * 32 + ".html"
            self.assertEqual(store.put(key, data, digest), data)
            self.assertEqual(
                client.call_args.kwargs["endpoint_url"],
                "https://" + "a" * 32 + ".r2.cloudflarestorage.com",
            )
            self.assertEqual(client.return_value.put_object.call_args.kwargs["IfNoneMatch"], "*")
            self.assertNotIn("ACL", client.return_value.put_object.call_args.kwargs)
            client.return_value.get_object.return_value = {"Body": io.BytesIO(b"tampered")}
            with self.assertRaises(EvidenceUnavailable):
                store.get(key, digest)
            with self.assertRaises(EvidenceUnavailable):
                store.get("production/waiver.html", digest)
        with override_settings(R2_WAIVER_BUCKET="production-waivers"):
            with self.assertRaises(EvidenceUnavailable):
                EvidenceStore()
