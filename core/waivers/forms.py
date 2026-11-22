from django import forms

MINOR_NAME_INSTRUCTIONS = {
    "Parent": (
        "First names of minors covered by this electronic waiver",
        "Enter each minor’s first name on a separate line.",
    ),
    "Legal guardian": (
        "First and last names of minors covered by this electronic waiver",
        "Enter each minor’s first and last name on a separate line.",
    ),
}
DEFAULT_MINOR_HELP = "Parent: enter first names. Legal guardian: enter first and last names. Enter one minor per line."

ADULT = "I confirm that I am at least 18 years old."
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
    relationship = forms.ChoiceField(
        required=False,
        choices=[("", "Select one"), ("Parent", "Parent"), ("Legal guardian", "Legal guardian")],
        label="Your relationship to the participant(s)",
    )
    minors = forms.CharField(
        max_length=18000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Names of minors covered by this electronic waiver",
        help_text=DEFAULT_MINOR_HELP,
    )
    adult_accepted = forms.BooleanField(label=ADULT)
    waiver_accepted = forms.BooleanField(label=AGREEMENT)
    electronic_accepted = forms.BooleanField(label=ELECTRONIC)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        relation = (
            self.data.get(self.add_prefix("relationship"))
            if self.is_bound
            else self.initial.get("relationship")
        )
        instructions = MINOR_NAME_INSTRUCTIONS.get(relation)
        if instructions:
            self.fields["minors"].label, self.fields["minors"].help_text = instructions
        for relation, (label, help_text) in MINOR_NAME_INSTRUCTIONS.items():
            key = "parent" if relation == "Parent" else "guardian"
            self.fields["minors"].widget.attrs["data-" + key + "-label"] = label
            self.fields["minors"].widget.attrs["data-" + key + "-help"] = help_text
        self.fields["minors"].widget.attrs["data-default-label"] = (
            "Names of minors covered by this electronic waiver"
        )
        self.fields["minors"].widget.attrs["data-default-help"] = DEFAULT_MINOR_HELP

    def clean_minors(self):
        names = [" ".join(x.split()) for x in self.cleaned_data["minors"].splitlines() if x.strip()]
        if len(names) > 100 or any(len(x) > 180 for x in names):
            raise forms.ValidationError("Enter no more than 100 minors, one name per line.")
        if len({x.casefold() for x in names}) != len(names):
            raise forms.ValidationError("List each minor once.")
        return names

    def clean(self):
        data = super().clean()
        if data.get("minors") and not data.get("relationship"):
            self.add_error("relationship", "Select your legal relationship to the minors listed.")
        if not data.get("minors") and data.get("relationship") in {"Parent", "Legal guardian"}:
            self.add_error("minors", "Enter the names of the minors you are signing for.")
        if data.get("relationship") == "Legal guardian" and any(
            len(name.split()) < 2 for name in data.get("minors", [])
        ):
            self.add_error(
                "minors",
                "Enter a first and last name for every minor when signing as a legal guardian.",
            )
        if not data.get("minors") and not data.get("relationship"):
            data["relationship"] = "Attending adult"
        return data


class PaperWaiverForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    paper_signed = forms.BooleanField(
        required=False,
        label="Paper waivers signed",
        help_text="Mark only after all required paper waivers have actually been signed. This does not create an electronic signature.",
    )
