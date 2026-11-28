"""Prevent new gift-card receipts from funding any cancellation-fee component."""

from django.db import migrations


def install(apps, editor):
    vendor = editor.connection.vendor
    if vendor == "postgresql":
        editor.execute("""CREATE FUNCTION monkeydo_gift_fee_scope() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN
            IF NEW.kind='receipt' AND NEW.tender='gift_card'
              AND (TG_OP='INSERT' OR (NEW.state IS DISTINCT FROM OLD.state AND NEW.state IN ('sending','succeeded')))
              AND EXISTS (SELECT 1 FROM jsonb_array_elements(NEW.allocation) part
                JOIN core_financialline l ON l.id::text=part->>'line'
                WHERE l.sale_id=NEW.sale_id AND l.category IN ('partial_cancellation','cancellation_fee')
                  AND ((part->>'net')::numeric<>0 OR (part->>'fee')::numeric<>0
                    OR (part->>'item_tax')::numeric<>0 OR (part->>'fee_tax')::numeric<>0))
            THEN RAISE EXCEPTION 'Gift-card payments cannot cover cancellation or no-show fees'; END IF;
            RETURN NEW;
          END $$;
          CREATE TRIGGER a_gift_fee_scope BEFORE INSERT OR UPDATE OF state ON core_paymentoperation
            FOR EACH ROW EXECUTE FUNCTION monkeydo_gift_fee_scope();""")
    elif vendor == "sqlite":
        invalid = """NEW.kind='receipt' AND NEW.tender='gift_card'
          AND EXISTS (SELECT 1 FROM json_each(NEW.allocation) part JOIN core_financialline l
            ON REPLACE(l.id,'-','')=REPLACE(json_extract(part.value,'$.line'),'-','')
            WHERE l.sale_id=NEW.sale_id AND l.category IN ('partial_cancellation','cancellation_fee')
              AND (CAST(json_extract(part.value,'$.net') AS NUMERIC)<>0
                OR CAST(json_extract(part.value,'$.fee') AS NUMERIC)<>0
                OR CAST(json_extract(part.value,'$.item_tax') AS NUMERIC)<>0
                OR CAST(json_extract(part.value,'$.fee_tax') AS NUMERIC)<>0))"""
        for name, event, extra in [
            ("insert", "INSERT", ""),
            (
                "update",
                "UPDATE OF state",
                " AND NEW.state<>OLD.state AND NEW.state IN ('sending','succeeded')",
            ),
        ]:
            editor.execute(
                f"CREATE TRIGGER a_gift_fee_scope_{name} BEFORE {event} ON core_paymentoperation WHEN {invalid}{extra} BEGIN SELECT RAISE(ABORT,'Gift-card payments cannot cover cancellation or no-show fees'); END"
            )


def remove(apps, editor):
    if editor.connection.vendor == "postgresql":
        editor.execute(
            "DROP TRIGGER a_gift_fee_scope ON core_paymentoperation; DROP FUNCTION monkeydo_gift_fee_scope();"
        )
    elif editor.connection.vendor == "sqlite":
        editor.execute("DROP TRIGGER a_gift_fee_scope_insert")
        editor.execute("DROP TRIGGER a_gift_fee_scope_update")


class Migration(migrations.Migration):
    dependencies = [("core", "0080_pending_visit_returns")]
    operations = [migrations.RunPython(install, remove)]
