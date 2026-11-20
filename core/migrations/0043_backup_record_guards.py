"""Protect recorded integrity metadata and owner download/restore evidence."""

from django.db import migrations

FACTS = ("backupdownload", "backuprestorecheck")
FROZEN = ("id", "object_key", "monthly", "month", "started_at")
INTEGRITY = ("sha256", "size", "encryption_fingerprint")


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        for name in FACTS:
            schema_editor.execute(
                f"CREATE TRIGGER core_{name}_immutable BEFORE UPDATE OR DELETE ON core_{name} FOR EACH ROW EXECUTE FUNCTION monkeydo_financial_immutable()"
            )
        frozen = " OR ".join(f"NEW.{name} IS DISTINCT FROM OLD.{name}" for name in FROZEN)
        integrity = " OR ".join(f"NEW.{name} IS DISTINCT FROM OLD.{name}" for name in INTEGRITY)
        schema_editor.execute(f"""CREATE FUNCTION monkeydo_backup_guard() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Backup history cannot be deleted'; END IF;
                IF {frozen} THEN RAISE EXCEPTION 'Backup identity is immutable'; END IF;
                IF OLD.sha256 <> '' AND ({integrity}) THEN RAISE EXCEPTION 'Backup integrity facts are immutable'; END IF;
                IF OLD.verified_at IS NOT NULL AND NEW.verified_at IS DISTINCT FROM OLD.verified_at THEN RAISE EXCEPTION 'Verified backup date is immutable'; END IF;
                IF OLD.state = 'removed' THEN RAISE EXCEPTION 'Removed backup history is immutable'; END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER core_backuprun_guard BEFORE UPDATE OR DELETE ON core_backuprun FOR EACH ROW EXECUTE FUNCTION monkeydo_backup_guard();""")
    elif vendor == "sqlite":
        for name in FACTS:
            for action in ("UPDATE", "DELETE"):
                schema_editor.execute(
                    f"CREATE TRIGGER core_{name}_{action.lower()}_immutable BEFORE {action} ON core_{name} BEGIN SELECT RAISE(ABORT, 'Backup history is immutable'); END"
                )
        frozen = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in FROZEN)
        integrity = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in INTEGRITY)
        schema_editor.execute(
            f"""CREATE TRIGGER core_backuprun_guard BEFORE UPDATE ON core_backuprun WHEN ({frozen}) OR (OLD.sha256<>'' AND ({integrity})) OR (OLD.verified_at IS NOT NULL AND NEW.verified_at IS NOT OLD.verified_at) OR OLD.state='removed' BEGIN SELECT RAISE(ABORT, 'Backup history is immutable'); END"""
        )
        schema_editor.execute(
            "CREATE TRIGGER core_backuprun_no_delete BEFORE DELETE ON core_backuprun BEGIN SELECT RAISE(ABORT, 'Backup history cannot be deleted'); END"
        )


def remove(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for name in FACTS:
            schema_editor.execute(f"DROP TRIGGER core_{name}_immutable ON core_{name}")
        schema_editor.execute("DROP TRIGGER core_backuprun_guard ON core_backuprun")
        schema_editor.execute("DROP FUNCTION monkeydo_backup_guard()")
    elif schema_editor.connection.vendor == "sqlite":
        for name in FACTS:
            for action in ("update", "delete"):
                schema_editor.execute(f"DROP TRIGGER core_{name}_{action}_immutable")
        schema_editor.execute("DROP TRIGGER core_backuprun_guard")
        schema_editor.execute("DROP TRIGGER core_backuprun_no_delete")


class Migration(migrations.Migration):
    dependencies = [("core", "0042_encrypted_backup_metadata")]
    operations = [migrations.RunPython(install, remove)]
