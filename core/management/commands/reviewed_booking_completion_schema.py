"""Closed ordinary-booking stage upgrade from deployed 0026; no general migrate switch."""

import io
import json

from django.apps import apps
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from .reviewed_batch_two_schema import guard_database

RUNTIME_ROLE = "monkeydo-functional"
BACKUP_ROLE = "monkeydo-functional-backup"
BASELINE = ("core", "0026_owner_feedback_batch_three")
REVIEWED_NAMES = (
    "0027_payment_foundation",
    "0028_financial_record_guards",
    "0029_waiver_evidence",
    "0030_waiver_evidence_guards",
    "0031_waiver_optional_metadata",
    "0032_message_outbox",
    "0033_message_history_guards",
    "0034_waiver_review_revision",
    "0035_booking_checkout",
    "0036_checkout_record_guards",
    "0037_payment_followup_actions",
    "0038_remaining_payment_checkout",
    "0039_system_payment_followup",
    "0040_actual_receipt_dates",
    "0041_waiver_contact_retention",
    "0042_encrypted_backup_metadata",
    "0043_backup_record_guards",
    "0044_mail_delivery_events",
    "0045_mail_delivery_status_guards",
    "0046_mail_attempt_reconciliation",
    "0047_backup_issue_review",
    "0048_seventh_booking_records",
    "0049_seventh_booking_controls",
    "0050_seventh_record_guards",
    "0051_paper_waiver_version",
    "0052_booking_comment_scope",
    "0053_staff_capacity_hold",
    "0054_active_membership_purchases",
    "0055_membership_payment_purposes",
    "0056_membership_message_link",
    "0057_membership_benefit_reservations",
    "0058_membership_follow_on_cohorts",
    "0059_membership_billing_actions",
    "0060_membership_card_authorizations",
    "0061_verified_membership_renewal_authority",
    "0062_booking_membership_owner_decisions",
    "0063_membership_cancellation_refunds",
    "0064_customer_credit_conversion",
    "0065_owner_credit_corrections",
    "0066_membership_operational_exports",
    "0067_membership_renewal_notices",
    "0068_booking_membership_renewal_prompts",
    "0069_combined_membership_arrival",
    "0070_pending_membership_arrival",
    "0071_membership_arrival_owner_resolution",
    "0072_initial_public_membership_authority",
    "0073_scheduled_membership_claims",
    "0074_scheduled_membership_credit_authority",
    "0075_visit_customer_credit",
    "0076_membership_first_split",
    "0077_membership_booking_zelle",
    "0078_split_membership_arrival",
    "0079_pending_visit_receipts",
    "0080_pending_visit_returns",
    "0081_gift_cancellation_scope",
    "0082_stop_pending_arrival",
    "0083_cancelled_membership_arrival_stop",
    "0084_paid_visit_purchase",
    "0085_paid_visit_received_split",
    "0086_paid_visit_card_reservations",
    "0087_paid_visit_card_recovery",
    "0088_paid_visit_cancelled_release",
    "0089_paid_visit_recovery_card_storage",
    "0090_paid_visit_manual_payment",
)
# A hardcoded suffix allowlist supports an idempotent retry of this same reviewed stage.
IMMUTABLE = (
    "membershippaidvisitmanualpayment",
    "membershippaidvisitcardstorage",
    "membershippaidvisitcancellation",
    "membershippaidvisitrecovery",
    "membershippaidvisitintent",
    "membershippaidvisitrelease",
    "membershiparrivalclosure",
    "membershiparrivalreceiptreturn",
    "membershiparrivalreceipt",
    "membershiparrivalreceiptapplication",
    "membershipbankallocation",
    "membershipcollectionclaim",
    "membershippubliccheckout",
    "membershiparrivalresolution",
    "membershiparrivalintent",
    "membershiparrivalevent",
    "membershiparrivalcheckout",
    "membershiprenewalprompt",
    "membershippromptlink",
    "membershippromptemail",
    "membershiprenewalnotice",
    "membershiprenewalnoticedelivery",
    "customercreditcorrection",
    "customercreditcorrectionallocation",
    "visitmembershipconversion",
    "customercreditissue",
    "customercreditapplication",
    "customercreditallocation",
    "membershipcancellation",
    "membershiprefundplan",
    "membershiprefundattempt",
    "membershipbookingdecision",
    "membershiprenewallink",
    "membershiprenewallinkrevocation",
    "membershippublicacceptance",
    "membershipcardauthorization",
    "membershipbillingaction",
    "membershiporigin",
    "membershipbenefitassignment",
    "membershipbenefitbatch",
    "membershipbenefitevent",
    "membershippurchase",
    "membershipinstallment",
    "membershipinvoice",
    "membershipcardmandate",
    "paperwaiver",
    "zellereceipt",
    "zelleapplication",
    "zellerefund",
    "financialsale",
    "financialline",
    "financialposting",
    "paymentevent",
    "providerevent",
    "providerobservation",
    "paymentpolicyversion",
    "paymentconsent",
    "financiallineadjustment",
    "bookingcheckout",
    "waiverversion",
    "waivercustomerlink",
    "waiverbookinglink",
    "messageevent",
    "mailproviderevent",
    "backupdownload",
    "backuprestorecheck",
)
MUTABLE = (
    "membershiparrivalstate",
    "membershipbenefitstate",
    "membershipbilling",
    "paymentmethod",
    "paymentoperation",
    "durablejob",
    "paymentsetup",
    "bookingcardagreement",
    "bookingchargestate",
    "paymentfollowup",
    "waiversignature",
    "waiversharelink",
    "bookingwaiverreview",
    "messagedelivery",
    "backuprun",
)


def reviewed_plan():
    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    if BASELINE not in executor.loader.applied_migrations:
        raise CommandError("The deployed reviewed 0026 baseline is required.")
    if any(
        app == "core" and (app, name) not in executor.loader.disk_migrations
        for app, name in executor.loader.applied_migrations
    ):
        raise CommandError("Unknown core migration history; no update authorized.")
    plan = [
        (migration.app_label, migration.name, backwards)
        for migration, backwards in executor.migration_plan(executor.loader.graph.leaf_nodes())
    ]
    allowed = [
        [("core", name, False) for name in REVIEWED_NAMES[index:]]
        for index in range(len(REVIEWED_NAMES) + 1)
    ]
    if plan not in allowed:
        raise CommandError(
            "Unexpected migration plan. Only the reviewed booking/membership stage 0027–0088 is allowed."
        )
    return plan


def grant_runtime_access():
    with connection.cursor() as cursor:
        role = connection.ops.quote_name(RUNTIME_ROLE)
        for name in IMMUTABLE + MUTABLE:
            table = "core_" + name
            cursor.execute(f"REVOKE ALL ON {table} FROM {role}")
            permissions = "SELECT, INSERT" + (", UPDATE" if name in MUTABLE else "")
            cursor.execute(f"GRANT {permissions} ON {table} TO {role}")
            cursor.execute(
                "SELECT pg_get_serial_sequence(%s, %s)",
                [table, apps.get_model("core", name)._meta.pk.column],
            )
            sequence = cursor.fetchone()[0]
            if sequence:
                quoted = ".".join(connection.ops.quote_name(part) for part in sequence.split("."))
                cursor.execute(f"REVOKE ALL ON SEQUENCE {quoted} FROM {role}")
                cursor.execute(f"GRANT USAGE, SELECT ON SEQUENCE {quoted} TO {role}")
        # Temporary holds are replaceable operational records, not financial or
        # signed evidence. Final confirmation deletes only its own hold.
        cursor.execute(f"REVOKE ALL ON core_bookingcapacityhold FROM {role}")
        cursor.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON core_bookingcapacityhold TO {role}"
        )
        # The backup role has no application write privileges beyond backup status
        # and a durable failure alert. A root-owned installer creates this exact role.
        cursor.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=%s",
            [BACKUP_ROLE],
        )
        backup = cursor.fetchone()
        if not backup or any(backup):
            raise CommandError(
                "The dedicated least-privileged backup role must be installed first."
            )
        role = connection.ops.quote_name(BACKUP_ROLE)
        database = connection.ops.quote_name(connection.settings_dict["NAME"])
        cursor.execute(f"GRANT CONNECT ON DATABASE {database} TO {role}")
        cursor.execute(
            f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM {role}"
        )
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
        cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
        cursor.execute(f"GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        for name in ("backuprun", "messagedelivery", "messageevent", "durablejob"):
            cursor.execute(f"GRANT INSERT ON core_{name} TO {role}")
            cursor.execute(
                "SELECT pg_get_serial_sequence(%s, %s)",
                ["core_" + name, apps.get_model("core", name)._meta.pk.column],
            )
            sequence = cursor.fetchone()[0]
            if sequence:
                quoted = ".".join(connection.ops.quote_name(part) for part in sequence.split("."))
                cursor.execute(f"GRANT USAGE ON SEQUENCE {quoted} TO {role}")
        for name in ("backuprun",):
            cursor.execute(f"GRANT UPDATE ON core_{name} TO {role}")


class Command(BaseCommand):
    help = (
        "Validate/apply only the reviewed ordinary/supervised booking stage to functional staging."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        guard_database()
        locked = False
        try:
            if options["apply"]:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [73216, 1])
                    locked = cursor.fetchone()[0]
                    if not locked:
                        raise CommandError(
                            "The booking calendar is busy; no schema update started."
                        )
                    cursor.execute("SET lock_timeout='10s'")
                    cursor.execute("SET statement_timeout='120s'")
            plan = reviewed_plan()
            if options["apply"]:
                with transaction.atomic():
                    call_command(
                        "migrate",
                        "core",
                        REVIEWED_NAMES[-1],
                        interactive=False,
                        verbosity=0,
                        stdout=io.StringIO(),
                    )
                    if reviewed_plan():
                        raise CommandError("Reviewed schema preparation did not finish.")
                    grant_runtime_access()
                    call_command("configure_staff_group", stdout=io.StringIO())
            self.stdout.write(
                json.dumps(
                    {
                        "pending": [name for app, name, backwards in plan],
                        "applied": [name for app, name, backwards in plan]
                        if options["apply"]
                        else [],
                    }
                )
            )
        finally:
            if locked:
                with connection.cursor() as cursor:
                    cursor.execute("RESET lock_timeout")
                    cursor.execute("RESET statement_timeout")
                    cursor.execute("SELECT pg_advisory_unlock(%s,%s)", [73216, 1])
