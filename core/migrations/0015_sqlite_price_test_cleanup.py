from django.db import migrations


def allow_local_flush(apps, schema_editor):
    # PostgreSQL remains the supported database and guards both UPDATE/DELETE.
    # SQLite is local-only: allow Django's DELETE-based test flush, while ORM
    # deletion and raw UPDATE guards remain. PostgreSQL uses TRUNCATE for flush.
    if schema_editor.connection.vendor == "sqlite":
        for table in ("core_pricingpolicy", "core_bookingquote"):
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {table}_delete_immutable")


def restore(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        for table in ("core_pricingpolicy", "core_bookingquote"):
            schema_editor.execute(
                f"CREATE TRIGGER {table}_delete_immutable BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'Historical pricing records are immutable'); END"
            )


class Migration(migrations.Migration):
    dependencies = [("core", "0014_seed_and_guard_pricing")]
    operations = [migrations.RunPython(allow_local_flush, restore)]
