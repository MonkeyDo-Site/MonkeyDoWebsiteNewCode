"""Explicit owner authority for an unused term whose dates cross today."""

import importlib
import re

from django.db import migrations

OLD = importlib.import_module("core.migrations.0093_membership_calendar_corrections")
ORIGINAL = (
    re.search(
        r"CREATE FUNCTION monkeydo_calendar_correction_scope\(\).*?\nEND \$\$;",
        OLD.SQL,
        re.S,
    )
    .group()
    .replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
)
BEFORE = """ OR before_start<(NEW.created_at AT TIME ZONE 'America/New_York')::date
 OR NEW.starts_on<(NEW.created_at AT TIME ZONE 'America/New_York')::date OR NEW.starts_on=before_start"""
AFTER = """ OR (((before_start<(NEW.created_at AT TIME ZONE 'America/New_York')::date
 OR NEW.starts_on<(NEW.created_at AT TIME ZONE 'America/New_York')::date))
 AND NEW.facts->'owner_date_exception' IS DISTINCT FROM 'true'::jsonb)
 OR (NEW.facts ? 'owner_date_exception' AND (
 NEW.facts->'owner_date_exception' IS DISTINCT FROM 'true'::jsonb
 OR NOT (before_start<(NEW.created_at AT TIME ZONE 'America/New_York')::date
 OR NEW.starts_on<(NEW.created_at AT TIME ZONE 'America/New_York')::date)
 OR NEW.facts->>'owner_acknowledgment' IS DISTINCT FROM 'As owner, I approve this exception. The customer agreed to the dates shown.'
 OR NOT EXISTS(SELECT 1 FROM auth_user WHERE id=NEW.actor_id AND is_active AND is_staff AND is_superuser)))
 OR (NOT (NEW.facts ? 'owner_date_exception') AND NEW.facts ? 'owner_acknowledgment')
 OR NEW.starts_on=before_start"""
assert ORIGINAL.count(BEFORE) == 1
SCOPE = ORIGINAL.replace(BEFORE, AFTER)
MARKER = """CREATE FUNCTION monkeydo_calendar_owner_dates() RETURNS boolean LANGUAGE sql STABLE AS $$ SELECT true $$"""


def install(apps, editor):
    if editor.connection.vendor == "postgresql":
        editor.execute(MARKER, params=None)
        editor.execute(SCOPE, params=None)


def remove(apps, editor):
    correction = apps.get_model("core", "MembershipCalendarCorrection")
    if correction.objects.filter(facts__owner_date_exception=True).exists():
        raise RuntimeError(
            "Recorded owner date exceptions cannot be reversed. Keep compatible code and fix forward."
        )
    if editor.connection.vendor == "postgresql":
        editor.execute(ORIGINAL, params=None)
        editor.execute("DROP FUNCTION monkeydo_calendar_owner_dates()")


class Migration(migrations.Migration):
    dependencies = [("core", "0094_paid_visit_split_remainder")]
    operations = [migrations.RunPython(install, remove)]
