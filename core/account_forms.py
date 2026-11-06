from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import Permission

SAFE_STAFF_PERMISSIONS = {
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


class OwnerCodeForm(forms.Form):
    code = forms.CharField(
        max_length=80,
        label="Sign-in code or offline recovery code",
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code"}),
    )


class RecoveryEmailForm(forms.Form):
    secondary_email = forms.EmailField(label="Secondary recovery email", required=False)


class StaffPermissionField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, permission):
        return permission.name


class StaffAccountForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, required=False, label="New password")
    is_active = forms.BooleanField(required=False, initial=True, label="Account enabled")
    permissions = StaffPermissionField(
        queryset=Permission.objects.none(), required=False, widget=forms.CheckboxSelectMultiple
    )
    version = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        initial = {}
        if user:
            initial = {
                "email": user.email,
                "is_active": user.is_active,
                "version": user.account_security.version,
            }
            initial["permissions"] = (
                Permission.objects.filter(
                    content_type__app_label="core", codename__in=SAFE_STAFF_PERMISSIONS
                )
                .filter(forms_permission_filter(user))
                .distinct()
            )
        else:
            initial["permissions"] = Permission.objects.filter(
                content_type__app_label="core", codename__in=SAFE_STAFF_PERMISSIONS
            )
            initial["is_active"] = True
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["permissions"].queryset = Permission.objects.filter(
            content_type__app_label="core", codename__in=SAFE_STAFF_PERMISSIONS
        ).order_by("name")
        if user:
            self.fields.pop("username")
            self.fields["version"].required = True
        else:
            self.fields.pop("version")
            self.fields["password"].required = True

    def clean_username(self):
        username = get_user_model().normalize_username(self.cleaned_data["username"])
        get_user_model()._meta.get_field("username").run_validators(username)
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username has already been used. Choose another.")
        return username

    def clean(self):
        data = super().clean()
        if data.get("password"):
            user = self.user or get_user_model()(
                username=data.get("username", ""), email=data.get("email", "")
            )
            try:
                password_validation.validate_password(data["password"], user)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return data


def forms_permission_filter(user):
    from django.db.models import Q

    return Q(user=user) | Q(group__user=user)


class StaffPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        from .models import AccountSecurity

        users = {user.pk: user for user in super().get_users(email) if user.is_staff}
        for profile in AccountSecurity.objects.filter(
            secondary_email__iexact=email,
            user__is_superuser=True,
            user__is_active=True,
            user__is_staff=True,
        ).select_related("user"):
            if profile.user.has_usable_password():
                users[profile.user_id] = profile.user
        return users.values()

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        from django.core.mail import EmailMultiAlternatives
        from django.template import loader

        from .models import SecurityAlert

        try:
            subject = "".join(loader.render_to_string(subject_template_name, context).splitlines())
            message = EmailMultiAlternatives(
                subject,
                loader.render_to_string(email_template_name, context),
                from_email,
                [to_email],
            )
            if html_email_template_name:
                message.attach_alternative(
                    loader.render_to_string(html_email_template_name, context), "text/html"
                )
            delivered = message.send() == 1
        except Exception:
            # Do not use the inherited exception logger: provider errors can contain tokens.
            delivered = False
        if not delivered:
            SecurityAlert.objects.create(
                subject="Password reset email could not be sent",
                details={"scope": "reset_email", "account_id": context["user"].pk},
            )

    def save(
        self,
        domain_override=None,
        subject_template_name="registration/password_reset_subject.txt",
        email_template_name="registration/password_reset_email.txt",
        use_https=False,
        token_generator=None,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        from django.contrib.sites.shortcuts import get_current_site
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        from .tokens import account_reset_token

        email = self.cleaned_data["email"]
        domain = domain_override or get_current_site(request).domain
        for user in self.get_users(email):
            context = {
                "email": email,
                "domain": domain,
                "site_name": "MonkeyDo",
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "user": user,
                "token": (token_generator or account_reset_token).make_token(user),
                "protocol": "https" if use_https else "http",
                **(extra_email_context or {}),
            }
            self.send_mail(
                subject_template_name,
                email_template_name,
                context,
                from_email,
                email,
                html_email_template_name,
            )
