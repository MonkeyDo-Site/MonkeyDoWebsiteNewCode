from django.contrib.auth.tokens import PasswordResetTokenGenerator

from .models import AccountSecurity


class AccountPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        version = (
            AccountSecurity.objects.filter(user_id=user.pk)
            .values_list("version", flat=True)
            .first()
            or 0
        )
        return super()._make_hash_value(user, timestamp) + f":{version}"


account_reset_token = AccountPasswordResetTokenGenerator()
