from django.db import migrations

TABLES = ("core_membershippricing", "core_membershipdraft", "core_membershipdraftcycle")


def setup(apps, schema_editor):
    Pricing = apps.get_model("core", "MembershipPricing")
    if not Pricing.objects.exists():
        Pricing.objects.create()
    for table in TABLES:
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION monkeydo_price_immutable()"
            )
        elif schema_editor.connection.vendor == "sqlite":
            schema_editor.execute(
                f"CREATE TRIGGER {table}_update_immutable BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'Historical membership drafts are immutable'); END"
            )


def reverse(apps, schema_editor):
    for table in TABLES:
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        elif schema_editor.connection.vendor == "sqlite":
            schema_editor.execute(f"DROP TRIGGER {table}_update_immutable")


class Migration(migrations.Migration):
    dependencies = [("core", "0017_membershippricing_membershipdraft_and_more")]
    operations = [migrations.RunPython(setup, reverse)]
