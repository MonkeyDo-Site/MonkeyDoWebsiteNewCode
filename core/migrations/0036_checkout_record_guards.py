from django.db import migrations

TABLES = ("financiallineadjustment", "bookingcheckout")


def install(apps, schema_editor):
    for name in TABLES:
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(
                f"CREATE TRIGGER core_{name}_immutable BEFORE UPDATE OR DELETE ON core_{name} FOR EACH ROW EXECUTE FUNCTION monkeydo_financial_immutable()"
            )
        elif schema_editor.connection.vendor == "sqlite":
            for event in ("UPDATE", "DELETE"):
                schema_editor.execute(
                    f"CREATE TRIGGER core_{name}_{event.lower()}_immutable BEFORE {event} ON core_{name} BEGIN SELECT RAISE(ABORT, 'Checkout history is immutable'); END"
                )


def remove(apps, schema_editor):
    for name in TABLES:
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(f"DROP TRIGGER core_{name}_immutable ON core_{name}")
        elif schema_editor.connection.vendor == "sqlite":
            for event in ("update", "delete"):
                schema_editor.execute(f"DROP TRIGGER core_{name}_{event}_immutable")


class Migration(migrations.Migration):
    dependencies = [("core", "0035_booking_checkout")]
    operations = [migrations.RunPython(install, remove)]
