from django.db import migrations


def install_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION monkeydo_reject_audit_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Audit events are append-only';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER monkeydo_audit_append_only
        BEFORE UPDATE OR DELETE ON core_auditevent
        FOR EACH ROW EXECUTE FUNCTION monkeydo_reject_audit_mutation();
    """)


def remove_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        DROP TRIGGER monkeydo_audit_append_only ON core_auditevent;
        DROP FUNCTION monkeydo_reject_audit_mutation();
    """)


class Migration(migrations.Migration):
    dependencies = [("core", "0002_booking_booking_mode_attendees_and_more")]
    operations = [migrations.RunPython(install_guard, remove_guard)]
