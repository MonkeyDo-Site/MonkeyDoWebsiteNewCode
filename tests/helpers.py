from django.utils import timezone

from core.models import AccountSecurity


def verified_owner_login(client, user):
    """Fixture for non-auth tests only; dedicated auth tests exercise actual MFA."""
    client.force_login(user)
    session = client.session
    session["owner_mfa_version"] = AccountSecurity.objects.get(user=user).version
    session["owner_verified_at"] = timezone.now().timestamp()
    session.save()
