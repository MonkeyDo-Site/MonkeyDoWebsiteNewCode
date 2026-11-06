from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from core.models import AuditEvent


class AuditTests(TestCase):
    def setUp(self):
        self.event = AuditEvent.objects.create(
            action="test.event", record_type="test", record_id="1"
        )

    def test_application_cannot_edit_or_delete_audit(self):
        self.event.action = "changed"
        with self.assertRaises(ValidationError):
            self.event.save()
        with self.assertRaises(ValidationError):
            self.event.delete()
        with self.assertRaises(ValidationError):
            AuditEvent.objects.all().update(action="changed")
        with self.assertRaises(ValidationError):
            AuditEvent.objects.all().delete()
        self.event.refresh_from_db()
        self.assertEqual(self.event.action, "test.event")

    @skipUnless(connection.vendor == "postgresql", "PostgreSQL database-level audit guard.")
    def test_database_rejects_direct_audit_mutation(self):
        for sql in (
            "UPDATE core_auditevent SET action = %s WHERE id = %s",
            "DELETE FROM core_auditevent WHERE action = %s AND id = %s",
        ):
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql, ["test.event", self.event.pk])
        self.assertEqual(AuditEvent.objects.count(), 1)
