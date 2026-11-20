"""Purge contact/network details only after private evidence deletion is verified."""

from importlib import import_module

from django.db import migrations

previous = import_module("core.migrations.0030_waiver_evidence_guards")
CONTACT = ("signer_email", "signer_phone", "ip_address", "user_agent")


def replace_guard(schema_editor, *, purge):
    vendor = schema_editor.connection.vendor
    if vendor not in {"postgresql", "sqlite"}:
        return
    distinct = "IS DISTINCT FROM" if vendor == "postgresql" else "IS NOT"
    frozen = [name for name in previous.FROZEN if not purge or name not in CONTACT]
    changed = " OR ".join(f"NEW.{name} {distinct} OLD.{name}" for name in frozen)
    contact_changed = " OR ".join(f"NEW.{name} {distinct} OLD.{name}" for name in CONTACT)
    cleared = "NEW.signer_email = '' AND NEW.signer_phone = '' AND NEW.user_agent = '' AND NEW.ip_address IS NULL"
    if purge:
        changed += f" OR (({contact_changed}) AND NOT (OLD.state = 'deleting' AND NEW.state = 'deleted' AND ({cleared})))"
        changed += f" OR (NEW.state = 'deleted' AND NOT ({cleared}))"
    transitions = "((OLD.state='pending' AND NEW.state IN ('signed','deleting')) OR (OLD.state='signed' AND NEW.state='deleting') OR (OLD.state='deleting' AND NEW.state IN ('deleting','deleted')))"
    invalid = f"({changed}) OR NOT {transitions} OR (NEW.state='deleted' AND NEW.deleted_at IS NULL) OR (NEW.state<>'deleted' AND NEW.deleted_at IS NOT NULL)"
    if vendor == "postgresql":
        schema_editor.execute(f"""CREATE OR REPLACE FUNCTION monkeydo_waiver_guard() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Waiver metadata cannot be deleted'; END IF;
                IF {invalid} THEN RAISE EXCEPTION 'Waiver facts or evidence transition cannot be changed'; END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;""")
    else:
        schema_editor.execute("DROP TRIGGER core_waiversignature_guard")
        schema_editor.execute(f"""CREATE TRIGGER core_waiversignature_guard BEFORE UPDATE ON core_waiversignature
            WHEN {invalid}
            BEGIN SELECT RAISE(ABORT, 'Waiver facts or evidence transition cannot be changed'); END""")


def forwards(apps, schema_editor):
    replace_guard(schema_editor, purge=True)


def backwards(apps, schema_editor):
    replace_guard(schema_editor, purge=False)


class Migration(migrations.Migration):
    dependencies = [("core", "0040_actual_receipt_dates")]
    operations = [migrations.RunPython(forwards, backwards)]
