import re
import secrets
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import (
    AccountSecurity,
    AuditEvent,
    OwnerChallenge,
    OwnerRecoveryCode,
    SecurityAlert,
    SecurityRequestLimit,
    TrustedOwnerBrowser,
)

TRUST_COOKIE = "monkeydo_owner_browser"


def digest(scope, value):
    return salted_hmac(scope, value, algorithm="sha256").hexdigest()


@transaction.atomic
def allow_security_request(scope, limit, minutes=15):
    key = digest("security-request", scope)
    SecurityRequestLimit.objects.get_or_create(key=key, defaults={"started_at": timezone.now()})
    bucket = SecurityRequestLimit.objects.select_for_update().get(key=key)
    now = timezone.now()
    if now - bucket.started_at >= timedelta(minutes=minutes):
        bucket.count = 0
        bucket.started_at = now
    if bucket.count >= limit:
        return False
    bucket.count += 1
    bucket.save()
    return True


def trusted_browser(user, token):
    if not token or len(token) > 100:
        return False
    profile, _ = AccountSecurity.objects.get_or_create(user=user)
    return TrustedOwnerBrowser.objects.filter(
        user=user,
        digest=digest("trusted-owner-browser", token),
        version=profile.version,
        expires_at__gt=timezone.now(),
    ).first()


def owner_message(address, code):
    # Deliberately in-memory until the separately reviewed email integration.
    try:
        return (
            send_mail(
                "[MONKEYDO TEST] Your owner sign-in code",
                f"This is a test message from the MonkeyDo staging website.\n\nYour sign-in code is {code}. It expires in ten minutes.\n\nThe Monkey Do team",
                None,
                [address],
                fail_silently=False,
            )
            == 1
        )
    except Exception:
        # Provider exceptions may contain secrets or message content; do not persist them.
        return False


def record_delivery(challenge, address, code):
    challenge.delivered = owner_message(address, code)
    challenge.save(update_fields=["delivered"])
    if not challenge.delivered:
        SecurityAlert.objects.create(
            subject="Owner verification email could not be sent",
            details={"account_id": challenge.user_id, "scope": "owner_email"},
        )


@transaction.atomic
def start_owner_challenge(user):
    if not user.is_active or not user.is_staff or not user.is_superuser or not user.email:
        raise ValidationError("An active owner account with a primary email is required.")
    if not allow_security_request(f"owner-send:{user.pk}", 5):
        raise ValidationError("Please wait before requesting another owner sign-in code.")
    profile = AccountSecurity.objects.get(user=user)
    now = timezone.now()
    challenge = OwnerChallenge(
        user=user,
        version=profile.version,
        credential_hash=user.get_session_auth_hash(),
        expires_at=now + timedelta(minutes=10),
        last_sent_at=now,
    )
    code = f"{secrets.randbelow(1000000):06d}"
    challenge.digest = digest("owner-challenge", f"{challenge.pk}:{code}")
    challenge.save()
    record_delivery(challenge, user.email, code)
    AuditEvent.objects.create(
        action="security.owner_challenge_created", record_type="account", record_id=str(user.pk)
    )
    return challenge


@transaction.atomic
def resend_owner_challenge(challenge_id, secondary=False):
    challenge = (
        OwnerChallenge.objects.select_for_update().select_related("user").get(pk=challenge_id)
    )
    user = challenge.user
    profile = AccountSecurity.objects.get(user=user)
    now = timezone.now()
    if (
        challenge.consumed_at
        or challenge.attempts >= 5
        or now >= challenge.expires_at
        or profile.version != challenge.version
        or not user.is_active
        or not user.is_superuser
        or not constant_time_compare(challenge.credential_hash, user.get_session_auth_hash())
    ):
        raise ValidationError("Please sign in again to request a new code.")
    if now - challenge.last_sent_at < timedelta(seconds=60):
        raise ValidationError("Wait at least one minute before requesting another code.")
    address = profile.secondary_email if secondary else user.email
    if not address:
        raise ValidationError("That recovery email is not configured.")
    if not allow_security_request(f"owner-send:{user.pk}", 5):
        raise ValidationError("Please wait before requesting another code.")
    code = f"{secrets.randbelow(1000000):06d}"
    while constant_time_compare(
        challenge.digest, digest("owner-challenge", f"{challenge.pk}:{code}")
    ):
        code = f"{secrets.randbelow(1000000):06d}"
    challenge.digest = digest("owner-challenge", f"{challenge.pk}:{code}")
    challenge.last_sent_at = now
    challenge.save()
    record_delivery(challenge, address, code)
    AuditEvent.objects.create(
        action="security.owner_code_resent",
        record_type="account",
        record_id=str(user.pk),
        changes={"secondary": secondary},
    )


@transaction.atomic
def verify_owner_challenge(challenge_id, code):
    # Return failures, rather than raising after counter writes, so attempts commit.
    challenge = (
        OwnerChallenge.objects.select_for_update().select_related("user").get(pk=challenge_id)
    )
    user = challenge.user
    profile = AccountSecurity.objects.get(user=user)
    now = timezone.now()
    if (
        challenge.consumed_at
        or challenge.attempts >= 5
        or now >= challenge.expires_at
        or profile.version != challenge.version
        or not user.is_active
        or not user.is_staff
        or not user.is_superuser
        or not constant_time_compare(challenge.credential_hash, user.get_session_auth_hash())
    ):
        return None
    if not allow_security_request(f"owner-verify:{user.pk}", 20):
        return None
    challenge.attempts += 1
    supplied = re.sub(r"\s", "", code.strip())
    matched = bool(
        re.fullmatch(r"[0-9]{6}", supplied)
        and constant_time_compare(
            challenge.digest, digest("owner-challenge", f"{challenge.pk}:{supplied}")
        )
    )
    if not matched:
        normalized = supplied.replace("-", "").upper()
        if re.fullmatch(r"[0-9A-F]{24}", normalized):
            recovery = (
                OwnerRecoveryCode.objects.select_for_update()
                .filter(
                    user=user,
                    digest=digest("owner-recovery", f"{user.pk}:{normalized}"),
                    used_at__isnull=True,
                    retired_at__isnull=True,
                )
                .first()
            )
            if recovery:
                recovery.used_at = now
                recovery.save()
                matched = True
    if matched or challenge.attempts >= 5:
        challenge.consumed_at = now
    challenge.save()
    if not matched:
        if challenge.attempts >= 5:
            SecurityAlert.objects.create(
                subject="Owner verification attempts exhausted",
                details={
                    "account_id": user.pk,
                    "scope": "owner_mfa",
                    "attempts": challenge.attempts,
                },
            )
        return None
    token = secrets.token_urlsafe(32)
    TrustedOwnerBrowser.objects.create(
        user=user,
        digest=digest("trusted-owner-browser", token),
        version=profile.version,
        expires_at=now + timedelta(days=30),
    )
    AuditEvent.objects.create(
        actor=user, action="security.owner_verified", record_type="account", record_id=str(user.pk)
    )
    return user, token, profile.version


@transaction.atomic
def rotate_recovery_codes(owner):
    if not owner.is_active or not owner.is_staff or not owner.is_superuser:
        raise ValidationError("Owner permission required.")
    # Serialize rotations; retain used historical facts, never raw codes.
    AccountSecurity.objects.select_for_update().get(user=owner)
    OwnerRecoveryCode.objects.filter(
        user=owner, used_at__isnull=True, retired_at__isnull=True
    ).update(retired_at=timezone.now())
    codes = []
    for _ in range(10):
        raw = secrets.token_hex(12).upper()
        OwnerRecoveryCode.objects.create(
            user=owner, digest=digest("owner-recovery", f"{owner.pk}:{raw}")
        )
        codes.append("-".join(raw[i : i + 4] for i in range(0, 24, 4)))
    AuditEvent.objects.create(
        actor=owner,
        action="security.recovery_codes_rotated",
        record_type="account",
        record_id=str(owner.pk),
    )
    return codes
