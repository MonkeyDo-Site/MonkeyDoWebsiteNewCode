from django.db import migrations

FROZEN = (
    "dedupe_key",
    "fingerprint",
    "customer_id",
    "booking_id",
    "kind",
    "template_version",
    "recipient",
    "subject",
    "text_body",
    "unsigned_waiver",
    "created_at",
    "actor_id",
)


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "CREATE TRIGGER core_messageevent_immutable BEFORE UPDATE OR DELETE ON core_messageevent FOR EACH ROW EXECUTE FUNCTION monkeydo_financial_immutable()"
        )
        changed = " OR ".join(f"NEW.{key} IS DISTINCT FROM OLD.{key}" for key in FROZEN)
        schema_editor.execute(f"""
            CREATE FUNCTION monkeydo_message_guard() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Message history cannot be deleted'; END IF;
                IF {changed} THEN RAISE EXCEPTION 'Message content is immutable'; END IF;
                IF OLD.state IN ('sent','failed','cancelled') AND NEW IS DISTINCT FROM OLD
                    THEN RAISE EXCEPTION 'Final message outcome is immutable'; END IF;
                IF OLD.state <> 'queued' AND NEW.state = 'queued'
                    THEN RAISE EXCEPTION 'An uncertain message cannot be automatically resent'; END IF;
                IF OLD.state NOT IN ('queued','sending') AND NEW.state = 'sending'
                    THEN RAISE EXCEPTION 'An uncertain message cannot be automatically resent'; END IF;
                IF OLD.provider_reference <> '' AND NEW.provider_reference <> OLD.provider_reference
                    THEN RAISE EXCEPTION 'Message provider reference cannot be changed'; END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER core_messagedelivery_guard BEFORE UPDATE OR DELETE ON core_messagedelivery
                FOR EACH ROW EXECUTE FUNCTION monkeydo_message_guard();
        """)
    elif schema_editor.connection.vendor == "sqlite":
        for event in ("UPDATE", "DELETE"):
            schema_editor.execute(
                f"CREATE TRIGGER core_messageevent_{event.lower()}_immutable BEFORE {event} ON core_messageevent BEGIN SELECT RAISE(ABORT, 'Message history is immutable'); END"
            )
        changed = " OR ".join(f"NEW.{key} IS NOT OLD.{key}" for key in FROZEN)
        schema_editor.execute(f"""CREATE TRIGGER core_messagedelivery_guard BEFORE UPDATE ON core_messagedelivery
            WHEN ({changed}) OR OLD.state IN ('sent','failed','cancelled')
                OR (OLD.state<>'queued' AND NEW.state='queued')
                OR (OLD.state NOT IN ('queued','sending') AND NEW.state='sending')
                OR (OLD.provider_reference<>'' AND NEW.provider_reference<>OLD.provider_reference)
            BEGIN SELECT RAISE(ABORT, 'Message content or sending state cannot be rewritten'); END""")
        schema_editor.execute(
            "CREATE TRIGGER core_messagedelivery_no_delete BEFORE DELETE ON core_messagedelivery BEGIN SELECT RAISE(ABORT, 'Message history cannot be deleted'); END"
        )


def remove(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER core_messagedelivery_guard ON core_messagedelivery")
        schema_editor.execute("DROP FUNCTION monkeydo_message_guard()")
        schema_editor.execute("DROP TRIGGER core_messageevent_immutable ON core_messageevent")
    elif schema_editor.connection.vendor == "sqlite":
        for name in (
            "core_messageevent_update_immutable",
            "core_messageevent_delete_immutable",
            "core_messagedelivery_guard",
            "core_messagedelivery_no_delete",
        ):
            schema_editor.execute(f"DROP TRIGGER {name}")


class Migration(migrations.Migration):
    dependencies = [("core", "0032_message_outbox")]
    operations = [migrations.RunPython(install, remove)]
