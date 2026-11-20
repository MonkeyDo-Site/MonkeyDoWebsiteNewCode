from django.db import migrations

FACTS = ("waiverversion", "waivercustomerlink", "waiverbookinglink")
FROZEN = (
    "request_key",
    "fingerprint",
    "version_id",
    "flow_hash",
    "signer_name",
    "signer_email",
    "signer_phone",
    "relationship",
    "minors",
    "signature_method",
    "adult_accepted",
    "waiver_accepted",
    "electronic_accepted",
    "signed_at",
    "valid_until",
    "delete_after",
    "object_key",
    "evidence_hash",
    "ip_address",
    "user_agent",
    "created_at",
)


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        for name in FACTS:
            schema_editor.execute(
                f"CREATE TRIGGER core_{name}_immutable BEFORE UPDATE OR DELETE ON core_{name} FOR EACH ROW EXECUTE FUNCTION monkeydo_financial_immutable()"
            )
        changed = " OR ".join(f"NEW.{key} IS DISTINCT FROM OLD.{key}" for key in FROZEN)
        schema_editor.execute(f"""
            CREATE FUNCTION monkeydo_waiver_guard() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Waiver metadata cannot be deleted'; END IF;
                IF {changed} THEN RAISE EXCEPTION 'Signed waiver metadata is immutable'; END IF;
                IF NOT ((OLD.state = 'pending' AND NEW.state IN ('signed','deleting'))
                    OR (OLD.state = 'signed' AND NEW.state = 'deleting')
                    OR (OLD.state = 'deleting' AND NEW.state IN ('deleting','deleted')))
                    THEN RAISE EXCEPTION 'Invalid waiver evidence transition'; END IF;
                IF NEW.state = 'deleted' AND NEW.deleted_at IS NULL
                    THEN RAISE EXCEPTION 'Evidence deletion must be dated'; END IF;
                IF NEW.state <> 'deleted' AND NEW.deleted_at IS NOT NULL
                    THEN RAISE EXCEPTION 'Evidence deletion is not confirmed'; END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER core_waiversignature_guard BEFORE UPDATE OR DELETE ON core_waiversignature
            FOR EACH ROW EXECUTE FUNCTION monkeydo_waiver_guard();
        """)
    elif vendor == "sqlite":
        for name in FACTS:
            for event in ("UPDATE", "DELETE"):
                schema_editor.execute(
                    f"CREATE TRIGGER core_{name}_{event.lower()}_immutable BEFORE {event} ON core_{name} BEGIN SELECT RAISE(ABORT, 'Waiver evidence is immutable'); END"
                )
        changed = " OR ".join(f"NEW.{key} IS NOT OLD.{key}" for key in FROZEN)
        schema_editor.execute(f"""CREATE TRIGGER core_waiversignature_guard BEFORE UPDATE ON core_waiversignature
            WHEN ({changed}) OR NOT ((OLD.state='pending' AND NEW.state IN ('signed','deleting'))
                OR (OLD.state='signed' AND NEW.state='deleting')
                OR (OLD.state='deleting' AND NEW.state IN ('deleting','deleted')))
                OR (NEW.state='deleted' AND NEW.deleted_at IS NULL)
                OR (NEW.state<>'deleted' AND NEW.deleted_at IS NOT NULL)
            BEGIN SELECT RAISE(ABORT, 'Waiver metadata or evidence state cannot be changed'); END""")
        schema_editor.execute(
            "CREATE TRIGGER core_waiversignature_no_delete BEFORE DELETE ON core_waiversignature BEGIN SELECT RAISE(ABORT, 'Waiver metadata cannot be deleted'); END"
        )


def remove(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER core_waiversignature_guard ON core_waiversignature")
        schema_editor.execute("DROP FUNCTION monkeydo_waiver_guard()")
        for name in FACTS:
            schema_editor.execute(f"DROP TRIGGER core_{name}_immutable ON core_{name}")
    elif schema_editor.connection.vendor == "sqlite":
        for name in FACTS:
            for event in ("update", "delete"):
                schema_editor.execute(f"DROP TRIGGER core_{name}_{event}_immutable")
        schema_editor.execute("DROP TRIGGER core_waiversignature_guard")
        schema_editor.execute("DROP TRIGGER core_waiversignature_no_delete")


class Migration(migrations.Migration):
    dependencies = [("core", "0029_waiver_evidence")]
    operations = [migrations.RunPython(install, remove)]
