from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import ValidationError
from django.db.models import F
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver

from .models import AccountSecurity

User = get_user_model()


def revoke_users(ids):
    AccountSecurity.objects.filter(user_id__in=list(ids)).update(version=F("version") + 1)


@receiver(pre_save, sender=User)
def remember_security_changes(sender, instance, **kwargs):
    if not instance.pk:
        instance._security_old = None
        return
    fields = ["username", "password", "email", "is_active", "is_staff", "is_superuser"]
    changed_fields = kwargs.get("update_fields")
    if changed_fields is not None:
        fields = [field for field in fields if field in changed_fields]
    old = sender.objects.filter(pk=instance.pk).values(*fields).first() if fields else None
    if old and "username" in old and old["username"] != instance.username:
        raise ValidationError("Usernames are permanent. Disable the old account instead.")
    instance._security_old = old


@receiver(post_save, sender=User)
def update_security_version(sender, instance, **kwargs):
    AccountSecurity.objects.get_or_create(user=instance)
    old = getattr(instance, "_security_old", None)
    if old and any(
        getattr(instance, field) != value for field, value in old.items() if field != "username"
    ):
        revoke_users([instance.pk])


@receiver(user_logged_in)
def bind_session_version(sender, request, user, **kwargs):
    profile, _ = AccountSecurity.objects.get_or_create(user=user)
    request.session["account_version"] = profile.version


def account_membership_changed(sender, instance, action, reverse, pk_set, **kwargs):
    if action not in {"pre_clear", "post_clear", "post_add", "post_remove"}:
        return
    if not reverse:
        ids = [instance.pk]
    elif action == "post_clear":
        ids = getattr(instance, "_cleared_security_users", [])
    elif pk_set is not None:
        ids = list(pk_set)
    else:
        ids = list(instance.user_set.values_list("pk", flat=True))
    if action == "pre_clear":
        instance._cleared_security_users = list(ids)
    else:
        revoke_users(ids)


m2m_changed.connect(
    account_membership_changed,
    sender=User.user_permissions.through,
    dispatch_uid="user_permissions_revoke",
)
m2m_changed.connect(
    account_membership_changed, sender=User.groups.through, dispatch_uid="user_groups_revoke"
)


@receiver(m2m_changed, sender=Group.permissions.through)
def group_permissions_changed(sender, instance, action, reverse, pk_set, **kwargs):
    if action not in {"pre_clear", "post_clear", "post_add", "post_remove"}:
        return
    if action == "post_clear":
        ids = getattr(instance, "_cleared_group_security_users", [])
    elif not reverse:
        ids = list(instance.user_set.values_list("pk", flat=True))
    else:
        groups = pk_set if pk_set is not None else instance.group_set.values_list("pk", flat=True)
        ids = list(
            User.objects.filter(groups__pk__in=groups).values_list("pk", flat=True).distinct()
        )
    if action == "pre_clear":
        instance._cleared_group_security_users = ids
    else:
        revoke_users(ids)
