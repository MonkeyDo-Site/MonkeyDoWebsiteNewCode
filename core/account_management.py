from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .account_forms import SAFE_STAFF_PERMISSIONS
from .models import AccountSecurity, AuditEvent
from .permissions import require_actor


@transaction.atomic
def save_staff_account(
    *,
    owner,
    username=None,
    email,
    password="",
    is_active=True,
    permissions=(),
    user_id=None,
    version=None,
):
    require_actor(owner, "auth.change_user", owner=True)
    selected = list(permissions)
    if any(
        p.content_type.app_label != "core" or p.codename not in SAFE_STAFF_PERMISSIONS
        for p in selected
    ):
        raise ValidationError("Only the displayed staff capabilities may be granted.")
    User = get_user_model()
    if user_id:
        user = User.objects.select_for_update().get(pk=user_id)
        profile = AccountSecurity.objects.select_for_update().get(user=user)
        if user.is_superuser or not user.is_staff:
            raise ValidationError(
                "Use owner recovery settings for the owner account; this screen manages staff only."
            )
        if profile.version != version:
            raise ValidationError("This staff account changed. Reload before saving.")
        before = {
            "email": user.email,
            "enabled": user.is_active,
            "permissions": sorted(user.get_all_permissions()),
        }
    else:
        if not username or User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Choose a username that has never been used.")
        if not password:
            raise ValidationError("A password is required for a new staff account.")
        user = User(username=User.normalize_username(username), is_staff=True, is_superuser=False)
        before = None
    user.email = email
    user.is_active = is_active
    if password:
        password_validation.validate_password(password, user)
        user.set_password(password)
    try:
        with transaction.atomic():
            user.full_clean()
            user.save()
    except IntegrityError:
        raise ValidationError("That username has already been used. Choose another.") from None
    user.groups.clear()
    user.user_permissions.set(selected)
    # Always invalidate sessions, including when a settings save has no m2m diff.
    profile = AccountSecurity.objects.select_for_update().get(user=user)
    profile.version += 1
    profile.save()
    AuditEvent.objects.create(
        actor=owner,
        action="security.staff_updated" if user_id else "security.staff_created",
        record_type="account",
        record_id=str(user.pk),
        changes={
            "before": before,
            "after": {
                "email": email,
                "enabled": is_active,
                "permissions": sorted("core." + p.codename for p in selected),
            },
            "password_changed": bool(password),
        },
    )
    return user
