from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Create/update default staff permissions; preserves individual account grants."

    @transaction.atomic
    def handle(self, *args, **options):
        names = {
            "view_membershipdraft",
            "add_membershipdraft",
            "view_booking",
            "add_booking",
            "change_booking",
            "view_customer",
            "add_customer",
            "change_customer",
            "view_customer_history",
            "view_customercomment",
            "add_customercomment",
            "change_customercomment",
        }
        group, _ = Group.objects.get_or_create(name="MonkeyDo Staff")
        permissions = Permission.objects.filter(content_type__app_label="core", codename__in=names)
        if permissions.count() != len(names):
            raise RuntimeError("Run migrations before configuring staff permissions.")
        group.permissions.set(permissions)
        self.stdout.write(
            self.style.SUCCESS("Default staff group configured. No users or passwords created.")
        )
