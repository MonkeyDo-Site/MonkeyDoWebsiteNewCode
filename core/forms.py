import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Customer


def normalize_phone(value, *, optional=False):
    value = value.strip()
    if optional and not value:
        return ""
    if not re.fullmatch(r"[0-9+().\s-]+", value):
        raise forms.ValidationError("Enter a ten-digit US phone number.")
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise forms.ValidationError("Enter a ten-digit US phone number.")
    return digits


class CustomerForm(forms.Form):
    last_name = forms.CharField(max_length=120, label="Last Name")
    phone = forms.CharField(max_length=40, widget=forms.TextInput(attrs={"type": "tel"}))
    email = forms.EmailField()
    move_previous_phone = forms.ChoiceField(
        required=False,
        choices=[("", "Choose if changing phone"), ("yes", "Yes"), ("no", "No")],
        label="Do you want to move the old number to the previous number field?",
    )
    customer_type = forms.ChoiceField(choices=Customer._meta.get_field("customer_type").choices)
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput, required=False)

    def __init__(self, *args, customer=None, owner=False, **kwargs):
        self.customer = customer
        self.owner = owner
        initial = {}
        if customer:
            initial = {
                field: getattr(customer, field)
                for field in ("last_name", "phone", "email", "customer_type", "revision")
            }
        super().__init__(*args, initial=initial, **kwargs)
        if not customer:
            self.fields.pop("move_previous_phone")
            self.fields.pop("revision")
        else:
            self.fields["revision"].required = True
        if not owner:
            self.fields.pop("customer_type")

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])

    def clean(self):
        data = super().clean()
        if self.customer and data.get("phone") and data["phone"] != self.customer.phone:
            if data.get("move_previous_phone") not in {"yes", "no"}:
                self.add_error(
                    "move_previous_phone", "Please choose Yes or No when changing the phone number."
                )
        return data


class CommentForm(forms.Form):
    body = forms.CharField(
        max_length=4000, label="Comment", widget=forms.Textarea(attrs={"rows": 4})
    )
    revision = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)


class PreviousPhoneForm(forms.Form):
    phone = forms.CharField(
        max_length=40, required=False, label="Previous phone (leave empty to clear)"
    )
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"], optional=True)


class StaffAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise self.get_invalid_login_error()
