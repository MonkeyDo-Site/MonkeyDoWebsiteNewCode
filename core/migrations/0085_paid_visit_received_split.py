"""Permit only fully verified manual split remainders on paid-visit first purchases."""

from django.db import migrations

PREVIOUS = """CREATE OR REPLACE FUNCTION monkeydo_paid_visit_purchase_complete() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
      IF EXISTS (SELECT 1 FROM core_membershipdraft d WHERE d.id=NEW.membership_id AND d.snapshot ? 'paid_visit_purchase')
        AND NOT EXISTS (
          SELECT 1 FROM core_membershippurchase p JOIN core_membershipdraft d ON d.id=p.membership_id
          JOIN core_visitmembershipconversion c ON c.purchase_id=p.membership_id
          JOIN core_booking b ON b.id=c.booking_id
          JOIN core_membershipinstallment item ON item.purchase_id=p.membership_id AND item.number=1
          JOIN core_membershipinvoice inv ON inv.installment_id=item.id
          WHERE p.membership_id=NEW.membership_id AND p.source='staff' AND p.purpose='purchase'
          AND p.actor_id=c.actor_id AND p.customer_id=b.customer_id
          AND b.workflow='integrated_v1' AND b.attendance='arrived'
          AND d.expected_method IN ('cash','check')
          AND (d.snapshot->'paid_visit_purchase'->>'booking')::bigint=b.id
          AND c.details->'paid_visit_purchase'->>'offer'=p.fingerprint
          AND c.details->'paid_visit_purchase'->>'request_key'=p.request_key::text
          AND (c.details->>'credit')::numeric>0
          AND (c.details->'paid_visit_purchase'->>'applied')::numeric=(d.snapshot->'paid_visit_purchase'->>'applied')::numeric
          AND (c.details->'paid_visit_purchase'->>'new_payment')::numeric=(d.snapshot->'paid_visit_purchase'->>'new_payment')::numeric
          AND (c.details->>'credit')::numeric=(SELECT COALESCE(SUM(amount),0) FROM core_customercreditissue WHERE conversion_id=c.id)
          AND (d.snapshot->'paid_visit_purchase'->>'applied')::numeric=
            (SELECT COALESCE(SUM(a.amount),0) FROM core_customercreditallocation a
              JOIN core_customercreditissue issue ON issue.id=a.issue_id JOIN core_customercreditapplication app ON app.id=a.application_id
              WHERE issue.conversion_id=c.id AND app.sale_id=inv.sale_id AND app.customer_id=p.customer_id AND app.actor_id=p.actor_id
                AND app.details->>'conversion'=c.id::text)
          AND (d.snapshot->'paid_visit_purchase'->>'applied')::numeric=
            (SELECT COALESCE(SUM(amount),0) FROM core_customercreditapplication WHERE sale_id=inv.sale_id)
          AND (d.snapshot->'paid_visit_purchase'->>'new_payment')::numeric=
            (SELECT COALESCE(SUM(amount),0) FROM core_paymentoperation WHERE sale_id=inv.sale_id AND kind='receipt' AND state='succeeded')
          AND NOT EXISTS (SELECT 1 FROM core_paymentoperation op WHERE op.sale_id=inv.sale_id
            AND (op.kind<>'receipt' OR op.state<>'succeeded' OR op.tender<>d.expected_method OR op.actor_id IS DISTINCT FROM p.actor_id))
          AND (d.snapshot->'paid_visit_purchase'->>'applied')::numeric+(d.snapshot->'paid_visit_purchase'->>'new_payment')::numeric=
            (SELECT COALESCE(SUM(net+fee+item_tax+fee_tax),0) FROM core_financialline WHERE sale_id=inv.sale_id)
          AND NOT EXISTS (SELECT 1 FROM core_financiallineadjustment a JOIN core_financialline l ON l.id=a.line_id WHERE l.sale_id=inv.sale_id)
          AND EXISTS (SELECT 1 FROM core_membershipbenefitassignment a JOIN core_membershipbenefitstate cur ON cur.assignment_id=a.id
            WHERE a.purchase_id=p.membership_id AND a.booking_id=b.id AND a.quote_id=c.updated_quote_id AND cur.status='used')
        )
      THEN RAISE EXCEPTION 'Paid visit purchase requires its complete conversion, known funding and benefit usage'; END IF;
      RETURN NEW; END $$;
"""

RECEIVED_SPLIT = """CREATE OR REPLACE FUNCTION monkeydo_paid_visit_purchase_complete() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
      IF EXISTS (SELECT 1 FROM core_membershipdraft d WHERE d.id=NEW.membership_id AND d.snapshot ? 'paid_visit_purchase')
        AND NOT EXISTS (
          SELECT 1 FROM core_membershippurchase p JOIN core_membershipdraft d ON d.id=p.membership_id
          JOIN core_visitmembershipconversion c ON c.purchase_id=p.membership_id
          JOIN core_booking b ON b.id=c.booking_id
          JOIN core_membershipinstallment item ON item.purchase_id=p.membership_id AND item.number=1
          JOIN core_membershipinvoice inv ON inv.installment_id=item.id
          WHERE p.membership_id=NEW.membership_id AND p.source='staff' AND p.purpose='purchase'
          AND p.actor_id=c.actor_id AND p.customer_id=b.customer_id
          AND b.workflow='integrated_v1' AND b.attendance='arrived'
          AND d.expected_method IN ('cash','check','split')
          AND (d.snapshot->'paid_visit_purchase'->>'booking')::bigint=b.id
          AND c.details->'paid_visit_purchase'->>'offer'=p.fingerprint
          AND c.details->'paid_visit_purchase'->>'request_key'=p.request_key::text
          AND (c.details->>'credit')::numeric>0
          AND (c.details->'paid_visit_purchase'->>'applied')::numeric=(d.snapshot->'paid_visit_purchase'->>'applied')::numeric
          AND (c.details->'paid_visit_purchase'->>'new_payment')::numeric=(d.snapshot->'paid_visit_purchase'->>'new_payment')::numeric
          AND (c.details->>'credit')::numeric=(SELECT COALESCE(SUM(amount),0) FROM core_customercreditissue WHERE conversion_id=c.id)
          AND (d.snapshot->'paid_visit_purchase'->>'applied')::numeric=
            (SELECT COALESCE(SUM(a.amount),0) FROM core_customercreditallocation a
              JOIN core_customercreditissue issue ON issue.id=a.issue_id JOIN core_customercreditapplication app ON app.id=a.application_id
              WHERE issue.conversion_id=c.id AND app.sale_id=inv.sale_id AND app.customer_id=p.customer_id AND app.actor_id=p.actor_id
                AND app.details->>'conversion'=c.id::text)
          AND (d.snapshot->'paid_visit_purchase'->>'applied')::numeric=
            (SELECT COALESCE(SUM(amount),0) FROM core_customercreditapplication WHERE sale_id=inv.sale_id)
          AND (d.snapshot->'paid_visit_purchase'->>'new_payment')::numeric=
            (SELECT COALESCE(SUM(amount),0) FROM core_paymentoperation WHERE sale_id=inv.sale_id AND kind='receipt' AND state='succeeded')
          AND NOT EXISTS (SELECT 1 FROM core_paymentoperation op WHERE op.sale_id=inv.sale_id
            AND (op.kind<>'receipt' OR op.state<>'succeeded' OR (CASE WHEN d.expected_method='split' THEN op.tender NOT IN ('cash','check','zelle','gift_card') ELSE op.tender<>d.expected_method END) OR op.actor_id IS DISTINCT FROM p.actor_id))
          AND (d.snapshot->'paid_visit_purchase'->>'applied')::numeric+(d.snapshot->'paid_visit_purchase'->>'new_payment')::numeric=
            (SELECT COALESCE(SUM(net+fee+item_tax+fee_tax),0) FROM core_financialline WHERE sale_id=inv.sale_id)
          AND (d.expected_method<>'split' OR (
            item.quote->'initial_split'=d.snapshot->'paid_visit_purchase'->'received_split'
            AND item.quote->'initial_split'->>'version'='paid-visit-received-split-v1'
            AND (item.quote->'initial_split'->>'unallocated')::numeric=0
            AND (item.quote->'initial_split'->>'card_total')::numeric=0
            AND (item.quote->'initial_split'->>'card_net')::numeric=0
            AND (item.quote->'initial_split'->>'manual_total')::numeric=(d.snapshot->'paid_visit_purchase'->>'new_payment')::numeric
            AND (item.quote->'initial_split'->>'credit_amount')::numeric=(d.snapshot->'paid_visit_purchase'->>'applied')::numeric
            AND NOT (item.quote->'initial_split' ? 'recorded_zelle')
            AND jsonb_typeof(item.quote->'initial_split'->'parts')='array'
            AND (SELECT COUNT(DISTINCT x->>'tender') FROM jsonb_array_elements(item.quote->'initial_split'->'parts') x)=jsonb_array_length(item.quote->'initial_split'->'parts')
            AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(item.quote->'initial_split'->'parts') x
              WHERE NOT (x ?& ARRAY['tender','amount','net','fee','received_on']) OR x->>'tender' NOT IN ('cash','check','zelle','gift_card')
                OR (x->>'amount')::numeric<=0 OR (x->>'net')::numeric<>(x->>'amount')::numeric OR (x->>'fee')::numeric<>0
                OR NOT EXISTS (SELECT 1 FROM core_paymentoperation op WHERE op.sale_id=inv.sale_id
                  AND op.tender=x->>'tender' AND op.amount=(x->>'amount')::numeric AND op.manual_received_on=(x->>'received_on')::date)
                OR (x->>'tender' IN ('cash','check') AND d.snapshot->'paid_visit_purchase'->'verification'->'cash_check' IS DISTINCT FROM 'true'::jsonb)
                OR (x->>'tender'='gift_card' AND d.snapshot->'paid_visit_purchase'->'verification'->'gift_card' IS DISTINCT FROM 'true'::jsonb)
                OR (x->>'tender'='zelle' AND (d.snapshot->'paid_visit_purchase'->'verification'->'zelle' IS DISTINCT FROM 'true'::jsonb OR COALESCE(btrim(x->>'sender'),'')='')))
            AND (SELECT COUNT(*) FROM core_paymentoperation WHERE sale_id=inv.sale_id)=jsonb_array_length(item.quote->'initial_split'->'parts')
          ))
          AND NOT EXISTS (SELECT 1 FROM core_financiallineadjustment a JOIN core_financialline l ON l.id=a.line_id WHERE l.sale_id=inv.sale_id)
          AND EXISTS (SELECT 1 FROM core_membershipbenefitassignment a JOIN core_membershipbenefitstate cur ON cur.assignment_id=a.id
            WHERE a.purchase_id=p.membership_id AND a.booking_id=b.id AND a.quote_id=c.updated_quote_id AND cur.status='used')
        )
      THEN RAISE EXCEPTION 'Paid visit purchase requires its complete conversion, known funding and benefit usage'; END IF;
      RETURN NEW; END $$;
"""


def install(apps, editor):
    if editor.connection.vendor == "postgresql":
        editor.execute(RECEIVED_SPLIT)


def remove(apps, editor):
    if (
        apps.get_model("core", "MembershipPurchase")
        .objects.filter(
            membership__expected_method="split",
            membership__snapshot__has_key="paid_visit_purchase",
        )
        .exists()
    ):
        raise RuntimeError("Paid-visit split purchases exist; keep compatible code or fix forward.")
    if editor.connection.vendor == "postgresql":
        editor.execute(PREVIOUS)


class Migration(migrations.Migration):
    dependencies = [("core", "0084_paid_visit_purchase")]
    operations = [migrations.RunPython(install, remove)]
