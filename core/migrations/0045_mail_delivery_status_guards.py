"""Allow verified delivery/bounce progression while preserving accepted message contents."""

from importlib import import_module

from django.db import migrations

previous = import_module("core.migrations.0033_message_history_guards")


def replace_guard(schema_editor, *, delivery):
    vendor = schema_editor.connection.vendor
    if vendor not in {"postgresql", "sqlite"}:
        return
    distinct = "IS DISTINCT FROM" if vendor == "postgresql" else "IS NOT"
    changed = " OR ".join(f"NEW.{key} {distinct} OLD.{key}" for key in previous.FROZEN)
    if delivery:
        state = "(OLD.state='sent' AND NEW.state NOT IN ('sent','delivered','bounced')) OR (OLD.state='delivered' AND NEW.state NOT IN ('delivered','bounced')) OR (OLD.state IN ('bounced','failed','cancelled') AND NEW.state<>OLD.state)"
        dated = " OR ".join(
            f"(OLD.{key} IS NOT NULL AND NEW.{key} {distinct} OLD.{key})"
            for key in ("sent_at", "delivered_at", "bounced_at")
        )
    else:
        state = "OLD.state IN ('sent','failed','cancelled')"
        dated = "1=0"
    invalid = f"({changed}) OR ({state}) OR ({dated}) OR (OLD.state<>'queued' AND NEW.state='queued') OR (OLD.state NOT IN ('queued','sending') AND NEW.state='sending') OR (OLD.provider_reference<>'' AND NEW.provider_reference<>OLD.provider_reference)"
    if vendor == "postgresql":
        schema_editor.execute(f"""CREATE OR REPLACE FUNCTION monkeydo_message_guard() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Message history cannot be deleted'; END IF;
                IF {invalid} THEN RAISE EXCEPTION 'Message contents or accepted delivery history cannot change'; END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;""")
    else:
        schema_editor.execute("DROP TRIGGER core_messagedelivery_guard")
        schema_editor.execute(
            f"""CREATE TRIGGER core_messagedelivery_guard BEFORE UPDATE ON core_messagedelivery WHEN {invalid} BEGIN SELECT RAISE(ABORT, 'Message history cannot change'); END"""
        )


def install(apps, schema_editor):
    replace_guard(schema_editor, delivery=True)
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "CREATE TRIGGER core_mailproviderevent_immutable BEFORE UPDATE OR DELETE ON core_mailproviderevent FOR EACH ROW EXECUTE FUNCTION monkeydo_financial_immutable()"
        )
    elif schema_editor.connection.vendor == "sqlite":
        for action in ("UPDATE", "DELETE"):
            schema_editor.execute(
                f"CREATE TRIGGER core_mailproviderevent_{action.lower()}_immutable BEFORE {action} ON core_mailproviderevent BEGIN SELECT RAISE(ABORT, 'Provider mail facts are immutable'); END"
            )


def remove(apps, schema_editor):
    replace_guard(schema_editor, delivery=False)
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER core_mailproviderevent_immutable ON core_mailproviderevent"
        )
    elif schema_editor.connection.vendor == "sqlite":
        for action in ("update", "delete"):
            schema_editor.execute(f"DROP TRIGGER core_mailproviderevent_{action}_immutable")


class Migration(migrations.Migration):
    dependencies = [("core", "0044_mail_delivery_events")]
    operations = [migrations.RunPython(install, remove)]
