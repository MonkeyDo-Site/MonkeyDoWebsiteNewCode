from django.db import migrations


def setup(apps, schema_editor):
    Policy = apps.get_model("core", "PricingPolicy")
    if not Policy.objects.exists():
        Policy.objects.create()
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""CREATE FUNCTION monkeydo_price_immutable() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Historical pricing records are immutable'; END;
        $$ LANGUAGE plpgsql;""")
        for table in ("core_pricingpolicy", "core_bookingquote"):
            schema_editor.execute(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION monkeydo_price_immutable()"
            )
    elif schema_editor.connection.vendor == "sqlite":
        for table in ("core_pricingpolicy", "core_bookingquote"):
            for action in ("UPDATE", "DELETE"):
                schema_editor.execute(
                    f"CREATE TRIGGER {table}_{action.lower()}_immutable BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Historical pricing records are immutable'); END"
                )


def reverse(apps, schema_editor):
    for table in ("core_pricingpolicy", "core_bookingquote"):
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        else:
            for action in ("update", "delete"):
                schema_editor.execute(f"DROP TRIGGER {table}_{action}_immutable")
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP FUNCTION monkeydo_price_immutable()")


class Migration(migrations.Migration):
    dependencies = [("core", "0013_booking_creation_actor")]
    operations = [migrations.RunPython(setup, reverse)]
