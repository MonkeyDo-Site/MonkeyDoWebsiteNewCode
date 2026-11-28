"""A first card remainder is bound to its accepted split, not the whole invoice."""

from django.conf import settings
from django.db import migrations


def scope(apps, editor, split):
    pg = editor.connection.vendor == "postgresql"
    user = apps.get_model(settings.AUTH_USER_MODEL)._meta.db_table

    def value(path):
        return (
            "NEW.facts" + "".join("->'" + p + "'" for p in path[:-1]) + "->>'" + path[-1] + "'"
            if pg
            else "json_extract(NEW.facts,'$." + ".".join(path) + "')"
        )

    due = f"o.amount=CAST({value(['review', 'membership_due'])} AS NUMERIC)"
    if split:
        card = (
            "i.quote->'initial_split'->>'card_total'"
            if pg
            else "json_extract(i.quote,'$.initial_split.card_total')"
        )
        total = "i.quote->>'total'" if pg else "json_extract(i.quote,'$.total')"
        credit = (
            "i.quote->'initial_split'->>'credit_amount'"
            if pg
            else "json_extract(i.quote,'$.initial_split.credit_amount')"
        )
        bank = (
            "i.quote->'initial_split'->'recorded_zelle'->>'amount'"
            if pg
            else "json_extract(i.quote,'$.initial_split.recorded_zelle.amount')"
        )
        rows = (
            "jsonb_array_elements(NEW.facts->'review'->'arrival'->'plan') part"
            if pg
            else "json_each(NEW.facts,'$.review.arrival.plan') part"
        )
        advance = (
            "COALESCE((part->>'advance')::boolean,FALSE)"
            if pg
            else "COALESCE(json_extract(part.value,'$.advance'),0)"
        )
        tender = "part->>'tender'" if pg else "json_extract(part.value,'$.tender')"
        amount = "part->>'amount'" if pg else "json_extract(part.value,'$.amount')"
        plan_array = (
            "jsonb_typeof(NEW.facts->'review'->'arrival'->'plan')='array'"
            if pg
            else "json_type(NEW.facts,'$.review.arrival.plan')='array'"
        )
        due = f"""(({card} IS NULL AND {due}) OR (
          {card} IS NOT NULL AND {plan_array} AND EXISTS (SELECT 1 FROM core_membershipdraft d WHERE d.id=p.membership_id AND d.expected_method='split') AND CAST({card} AS NUMERIC)>0 AND o.amount=CAST({card} AS NUMERIC)
          AND o.amount=CAST({value(["review", "membership_card_due"])} AS NUMERIC)
          AND CAST({value(["review", "membership_due"])} AS NUMERIC)=CAST({total} AS NUMERIC)-COALESCE(CAST({credit} AS NUMERIC),0)-COALESCE(CAST({bank} AS NUMERIC),0)
          AND {value(["data", "method"])}='split'
          AND NOT EXISTS (SELECT 1 FROM {rows} WHERE NOT {advance} AND {tender}<>'card' AND CAST({amount} AS NUMERIC)>0)))"""
    expiry = (
        "NEW.expires_at=NEW.accepted_at+interval '30 minutes'"
        if pg
        else "ABS(julianday(NEW.expires_at)-julianday(NEW.accepted_at)-1.0/48)<0.00000001"
    )
    check = f"""EXISTS (SELECT 1 FROM core_membershippurchase p
      JOIN core_booking b ON b.id=NEW.booking_id JOIN core_paymentoperation o ON o.id=NEW.operation_id
      JOIN core_membershipinvoice inv ON inv.sale_id=o.sale_id
      JOIN core_membershipinstallment i ON i.id=inv.installment_id JOIN {user} u ON u.id=NEW.actor_id
      WHERE p.membership_id=NEW.purchase_id AND p.actor_id=NEW.actor_id AND p.source='staff'
      AND p.confirmation_mode='combined' AND p.customer_id=b.customer_id AND i.purchase_id=p.membership_id AND i.number=1
      AND o.kind='receipt' AND o.tender='card' AND o.state='ready' AND o.amount>0 AND o.actor_id=NEW.actor_id
      AND b.workflow='integrated_v1' AND b.attendance='' AND b.setup_pending=FALSE AND u.is_staff AND u.is_active
      AND CAST({value(["review", "booking"])} AS TEXT)=CAST(b.id AS TEXT)
      AND CAST({value(["review", "actor"])} AS TEXT)=CAST(NEW.actor_id AS TEXT)
      AND {due}
      AND REPLACE(CAST(o.method_id AS TEXT),'-','')=REPLACE({value(["review", "method_id"])},'-','')
      AND CAST({value(["review", "session", "id"])} AS TEXT)=CAST(b.session_id AS TEXT)
      AND {value(["review", "offer"])}=p.fingerprint AND {value(["offer", "fingerprint"])}=p.fingerprint)
      AND {expiry}"""
    if pg:
        editor.execute(f"""CREATE OR REPLACE FUNCTION monkeydo_membershiparrivalintent_scope() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN IF ({check}) IS NOT TRUE THEN RAISE EXCEPTION 'Pending membership arrival scope does not match'; END IF; RETURN NEW; END $$""")
    elif editor.connection.vendor == "sqlite":
        editor.execute("DROP TRIGGER core_membershiparrivalintent_scope")
        editor.execute(
            f"CREATE TRIGGER core_membershiparrivalintent_scope BEFORE INSERT ON core_membershiparrivalintent BEGIN SELECT RAISE(ABORT,'Pending arrival scope does not match') WHERE NOT COALESCE(({check}),0); END"
        )


def install(apps, editor):
    scope(apps, editor, True)


def remove(apps, editor):
    if (
        apps.get_model("core", "MembershipArrivalIntent")
        .objects.filter(purchase__membership__expected_method="split")
        .exists()
    ):
        raise RuntimeError(
            "Accepted split membership arrivals exist; keep compatible code or fix forward."
        )
    scope(apps, editor, False)


class Migration(migrations.Migration):
    dependencies = [("core", "0077_membership_booking_zelle")]
    operations = [migrations.RunPython(install, remove)]
