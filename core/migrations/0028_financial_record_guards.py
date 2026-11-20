from django.db import migrations

FACTS = (
    "financialsale",
    "financialline",
    "financialposting",
    "paymentevent",
    "providerevent",
    "providerobservation",
    "paymentconsent",
    "paymentpolicyversion",
)
FROZEN = (
    "request_key",
    "fingerprint",
    "sale_id",
    "original_id",
    "method_id",
    "kind",
    "tender",
    "amount",
    "purpose",
    "brand",
    "last_four",
    "allocation",
    "actor_id",
    "requested_at",
)


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION monkeydo_financial_immutable() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'Accepted financial facts are immutable'; END;
            $$ LANGUAGE plpgsql;
        """)
        for name in FACTS:
            table = "core_" + name
            schema_editor.execute(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION monkeydo_financial_immutable()"
            )
        schema_editor.execute("""
            CREATE FUNCTION monkeydo_method_identity_guard() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Payment method evidence cannot be deleted'; END IF;
                IF NEW.provider_customer IS DISTINCT FROM OLD.provider_customer OR NEW.environment IS DISTINCT FROM OLD.environment
                    OR (OLD.customer_id IS NOT NULL AND NEW.customer_id IS DISTINCT FROM OLD.customer_id)
                    OR (NEW.provider_method IS DISTINCT FROM OLD.provider_method AND NOT (NEW.state = 'removed' AND NEW.provider_method IS NULL))
                    OR (OLD.state IN ('removing','removed') AND NEW.state = 'active')
                    THEN RAISE EXCEPTION 'Payment method cannot be retargeted'; END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER core_paymentmethod_identity BEFORE UPDATE OR DELETE
                ON core_paymentmethod FOR EACH ROW EXECUTE FUNCTION monkeydo_method_identity_guard();
        """)
        changed = " OR ".join(f"NEW.{key} IS DISTINCT FROM OLD.{key}" for key in FROZEN)
        schema_editor.execute(f"""
            CREATE FUNCTION monkeydo_operation_guard() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Payment operations cannot be deleted'; END IF;
                IF {changed} THEN RAISE EXCEPTION 'Payment operation identity is immutable'; END IF;
                IF OLD.state IN ('succeeded','declined','cancelled') AND NEW IS DISTINCT FROM OLD
                    THEN RAISE EXCEPTION 'Final payment outcome is immutable'; END IF;
                IF OLD.state <> 'ready' AND NEW.state = 'ready'
                    THEN RAISE EXCEPTION 'Dispatched payments cannot be retried'; END IF;
                IF OLD.state <> 'ready' AND NEW.state = 'sending' AND OLD.state <> 'sending'
                    THEN RAISE EXCEPTION 'Dispatched payments cannot be retried'; END IF;
                IF OLD.provider_reference <> '' AND NEW.provider_reference <> OLD.provider_reference
                    THEN RAISE EXCEPTION 'Provider reference cannot be replaced'; END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER core_paymentoperation_guard BEFORE UPDATE OR DELETE
                ON core_paymentoperation FOR EACH ROW EXECUTE FUNCTION monkeydo_operation_guard();
        """)
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("""CREATE TRIGGER core_paymentmethod_identity BEFORE UPDATE ON core_paymentmethod
            WHEN NEW.provider_customer IS NOT OLD.provider_customer OR NEW.environment IS NOT OLD.environment
            OR (OLD.customer_id IS NOT NULL AND NEW.customer_id IS NOT OLD.customer_id)
            OR (NEW.provider_method IS NOT OLD.provider_method AND NOT (NEW.state='removed' AND NEW.provider_method IS NULL))
            OR (OLD.state IN ('removing','removed') AND NEW.state='active')
            BEGIN SELECT RAISE(ABORT, 'Payment method cannot be retargeted'); END""")
        schema_editor.execute("""CREATE TRIGGER core_paymentmethod_no_delete BEFORE DELETE ON core_paymentmethod
            BEGIN SELECT RAISE(ABORT, 'Payment method evidence cannot be deleted'); END""")
        for name in FACTS:
            table = "core_" + name
            for event in ("UPDATE", "DELETE"):
                schema_editor.execute(
                    f"CREATE TRIGGER {table}_{event.lower()}_immutable BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT, 'Accepted financial facts are immutable'); END"
                )
        changed = " OR ".join(f"NEW.{key} IS NOT OLD.{key}" for key in FROZEN)
        schema_editor.execute(f"""CREATE TRIGGER core_paymentoperation_identity BEFORE UPDATE ON core_paymentoperation
            WHEN {changed} BEGIN SELECT RAISE(ABORT, 'Payment operation identity is immutable'); END""")
        schema_editor.execute("""CREATE TRIGGER core_paymentoperation_final BEFORE UPDATE ON core_paymentoperation
            WHEN OLD.state IN ('succeeded','declined','cancelled') BEGIN SELECT RAISE(ABORT, 'Final payment outcome is immutable'); END""")
        schema_editor.execute("""CREATE TRIGGER core_paymentoperation_retry BEFORE UPDATE ON core_paymentoperation
            WHEN (OLD.state <> 'ready' AND NEW.state = 'ready') OR (OLD.state <> 'ready' AND NEW.state = 'sending' AND OLD.state <> 'sending') OR (OLD.provider_reference <> '' AND NEW.provider_reference <> OLD.provider_reference)
            BEGIN SELECT RAISE(ABORT, 'Dispatched payment cannot be retried or reassigned'); END""")
        schema_editor.execute("""CREATE TRIGGER core_paymentoperation_no_delete BEFORE DELETE ON core_paymentoperation
            BEGIN SELECT RAISE(ABORT, 'Payment operations cannot be deleted'); END""")


def remove(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER core_paymentmethod_identity ON core_paymentmethod")
        schema_editor.execute("DROP FUNCTION monkeydo_method_identity_guard()")
        schema_editor.execute("DROP TRIGGER core_paymentoperation_guard ON core_paymentoperation")
        schema_editor.execute("DROP FUNCTION monkeydo_operation_guard()")
        for name in FACTS:
            schema_editor.execute(f"DROP TRIGGER core_{name}_immutable ON core_{name}")
        schema_editor.execute("DROP FUNCTION monkeydo_financial_immutable()")
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER core_paymentmethod_identity")
        schema_editor.execute("DROP TRIGGER core_paymentmethod_no_delete")
        for name in FACTS:
            for event in ("update", "delete"):
                schema_editor.execute(f"DROP TRIGGER core_{name}_{event}_immutable")
        for name in ("identity", "final", "retry", "no_delete"):
            schema_editor.execute(f"DROP TRIGGER core_paymentoperation_{name}")


class Migration(migrations.Migration):
    dependencies = [("core", "0027_payment_foundation")]
    operations = [migrations.RunPython(install, remove)]
