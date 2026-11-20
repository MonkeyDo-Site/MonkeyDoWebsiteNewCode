from django import forms

from core.forms import normalize_phone

ADULT = "I confirm that I am at least 18 years old and legally authorized to sign for myself and/or the minors listed above."
AGREEMENT = "I have read and agree to the complete MONKEYDO LLC Liability Waiver shown above."
ELECTRONIC = "I consent to use electronic records and signatures. I understand that typing my legal name and selecting “Sign waiver” constitutes my electronic signature."


class SignatureForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.CharField(max_length=60, widget=forms.HiddenInput)
    text_hash = forms.CharField(max_length=64, widget=forms.HiddenInput)
    signer_name = forms.CharField(
        max_length=180,
        label="Your full legal name",
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    signer_email = forms.EmailField(label="Your email address")
    signer_phone = forms.CharField(max_length=30, required=False, label="Your phone number")
    relationship = forms.ChoiceField(
        choices=[("", "Select one")]
        + [(x, x) for x in ("Self", "Parent", "Legal guardian", "Self and parent/legal guardian")],
        label="Your relationship to the participant(s)",
    )
    minors = forms.CharField(
        max_length=18000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Names of minors covered by this electronic waiver",
        help_text="Enter each minor’s full name on a separate line. Leave blank if you are signing only for yourself.",
    )
    adult_accepted = forms.BooleanField(label=ADULT)
    waiver_accepted = forms.BooleanField(label=AGREEMENT)
    electronic_accepted = forms.BooleanField(label=ELECTRONIC)

    def clean_signer_phone(self):
        value = self.cleaned_data["signer_phone"]
        return normalize_phone(value) if value else ""

    def clean_minors(self):
        names = [" ".join(x.split()) for x in self.cleaned_data["minors"].splitlines() if x.strip()]
        if len(names) > 100 or any(len(x) > 180 for x in names):
            raise forms.ValidationError("Enter no more than 100 minors, one full name per line.")
        if len({x.casefold() for x in names}) != len(names):
            raise forms.ValidationError("List each minor once.")
        return names

    def clean(self):
        data = super().clean()
        if data.get("minors") and data.get("relationship") == "Self":
            self.add_error("relationship", "Select your legal relationship to the minors listed.")
        if not data.get("minors") and data.get("relationship") in {"Parent", "Legal guardian"}:
            self.add_error("minors", "Enter the names of the minors you are signing for.")
        return data


class PaperWaiverForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    paper_signed = forms.BooleanField(
        required=False,
        label="Paper waivers signed",
        help_text="Mark only after all required paper waivers have actually been signed. This does not create an electronic signature.",
    )
