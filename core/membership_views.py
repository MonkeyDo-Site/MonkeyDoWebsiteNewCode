import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from .booking_forms import CustomerChoice, customer_picker
from .forms import payment_method_choices
from .memberships import EDIT_FIELDS, create_draft, current_draft, edit_draft
from .models import AuditEvent, Customer, MembershipDraft, MembershipPricing, PricingPolicy
from .pagination import paginate
from .permissions import staff_permission


class DraftForm(forms.Form):
    customer = CustomerChoice(queryset=Customer.objects.order_by("last_name", "pk"))
    kind = forms.ChoiceField(label="Type", choices=MembershipDraft._meta.get_field("kind").choices)
    places = forms.IntegerField(min_value=1, max_value=2147483647, label="Amount", initial=1)
    months = forms.IntegerField(min_value=3, label="Months", initial=3)
    billing = forms.ChoiceField(choices=MembershipDraft._meta.get_field("billing").choices)
    starts_on = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="Test start date (New York)"
    )
    expected_method = forms.ChoiceField(
        choices=MembershipDraft._meta.get_field("expected_method").choices
    )
    creation_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)

    minimum_override = forms.BooleanField(
        required=False, label="Owner: allow a one- or two-month exception"
    )

    def __init__(self, *args, owner=False, **kwargs):
        super().__init__(*args, **kwargs)
        if owner:
            self.fields["months"].min_value = 1
            self.fields["months"].validators = [forms.IntegerField(min_value=1).validators[0]]
            self.fields["months"].widget.attrs["min"] = 1
        else:
            self.fields.pop("minimum_override")
        self.fields["expected_method"].choices = payment_method_choices(
            PricingPolicy.objects.first()
        )
        customer_picker(self)

    def clean(self):
        data = super().clean()
        if data.get("months", 3) < 3 and not data.get("minimum_override"):
            self.add_error("minimum_override", "Confirm the owner exception for this shorter term.")
        return data


class MembershipPricingForm(forms.ModelForm):
    class Meta:
        model = MembershipPricing
        fields = ("subscription", "unlimited")
        labels = {
            "subscription": "Subscription monthly price per place",
            "unlimited": "Unlimited monthly price per place",
        }


@staff_permission("core.view_membershipdraft")
@staff_permission("core.view_customer")
@require_safe
def drafts(request):
    customer = request.GET.get("customer", "")
    records = (
        MembershipDraft.objects.select_related("customer", "actor", "pricing", "fee_policy")
        .filter(purchase__isnull=True)
        .prefetch_related("revisions")
    )
    if customer.isascii() and customer.isdigit() and len(customer) <= 18:
        records = records.filter(customer_id=int(customer))
    page = paginate(request, records)
    page.object_list = [current_draft(record) for record in page.object_list]
    return render(request, "core/membership_drafts.html", {"drafts": page})


@staff_permission("core.view_membershipdraft")
@staff_permission("core.add_membershipdraft")
@staff_permission("core.view_customer")
@require_http_methods(["GET", "POST"])
def draft_create(request):
    form = DraftForm(
        request.POST if request.method == "POST" else None, owner=request.user.is_superuser
    )
    if request.method == "POST" and form.is_valid():
        try:
            draft = create_draft(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(
                request,
                "Test membership draft saved. No membership benefits, payments or scheduled charges were activated.",
            )
            return redirect("membership_detail", pk=draft.pk)
    return render(
        request,
        "core/membership_form.html",
        {"form": form, "heading": "Create test membership draft"},
    )


@staff_permission("core.view_membershipdraft")
@staff_permission("core.view_customer")
@require_safe
def draft_detail(request, pk):
    draft = get_object_or_404(
        MembershipDraft.objects.select_related(
            "customer", "actor", "pricing", "fee_policy"
        ).prefetch_related("revisions"),
        pk=pk,
    )
    root = draft
    if hasattr(root, "purchase"):
        return redirect("membership_overview", pk=root.pk)
    draft = current_draft(root)
    latest_number = draft.version_number
    selected = request.GET.get("revision", "")
    if selected:
        from django.http import Http404

        if not selected.isascii() or not selected.isdigit() or len(selected) > 9:
            raise Http404
        number = int(selected)
        if number == 1:
            draft = current_draft(root, original=True)
        else:
            revision = get_object_or_404(root.revisions, number=number)
            draft = current_draft(root, revision)
    return render(
        request,
        "core/membership_detail.html",
        {
            "draft": draft,
            "historical_version": draft.version_number != latest_number,
            "version_numbers": [1]
            + list(root.revisions.order_by("number").values_list("number", flat=True)),
            "history": AuditEvent.objects.filter(
                record_type="membership_draft", record_id=str(draft.pk)
            ).select_related("actor"),
            "cycles": Paginator(draft.version_cycles, 24).get_page(request.GET.get("page")),
        },
    )


@staff_permission("core.add_membershippricing")
@require_http_methods(["GET", "POST"])
def membership_pricing(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    current = MembershipPricing.objects.first()
    form = MembershipPricingForm(
        request.POST if request.method == "POST" else None,
        initial={"subscription": current.subscription, "unlimited": current.unlimited}
        if current
        else {},
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            row = form.save(commit=False)
            row.actor = request.user
            row.save()
            AuditEvent.objects.create(
                actor=request.user,
                action="membership.pricing_created",
                record_type="membership_pricing",
                record_id=str(row.pk),
                changes={
                    "previous_version": current.pk if current else None,
                    "subscription": str(row.subscription),
                    "unlimited": str(row.unlimited),
                },
            )
        messages.success(
            request,
            "Future test drafts will use this price version. Existing drafts retain their saved prices.",
        )
        return redirect("membership_pricing")
    return render(
        request, "core/membership_form.html", {"form": form, "heading": "Membership draft pricing"}
    )


class DraftEditForm(DraftForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    submission_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)

    def __init__(self, *args, draft, owner=False, **kwargs):
        self.draft = draft
        initial = {key: getattr(draft, key) for key in EDIT_FIELDS}
        initial.update(version=draft.version_number, minimum_override=draft.months < 3)
        super().__init__(*args, owner=owner, initial=initial, **kwargs)
        self.fields.pop("customer")
        self.fields.pop("creation_key")
        self.fields["expected_method"].choices = payment_method_choices(draft.fee_policy)
        if draft.months < 3:
            from django.core.validators import MinValueValidator

            self.fields["months"].min_value = 1
            self.fields["months"].validators = [MinValueValidator(1)]
            self.fields["months"].widget.attrs["min"] = 1
            self.fields[
                "months"
            ].help_text = "The existing owner-approved short term may be retained. A different short term requires the owner."

    def clean(self):
        data = forms.Form.clean(self)
        inherited = (
            all(
                data.get(key) == getattr(self.draft, key)
                for key in ("kind", "places", "months", "starts_on")
            )
            and self.draft.months < 3
        )
        if data.get("months", 3) < 3 and not inherited and not data.get("minimum_override"):
            self.add_error(
                "months", "A different one- or two-month term requires an owner exception."
            )
        return data


@staff_permission("core.view_membershipdraft")
@staff_permission("core.change_membershipdraft")
@staff_permission("core.view_customer")
@require_http_methods(["GET", "POST"])
def draft_edit(request, pk):
    root = get_object_or_404(
        MembershipDraft.objects.select_related("customer", "pricing", "fee_policy"), pk=pk
    )
    if hasattr(root, "purchase"):
        return redirect("membership_overview", pk=root.pk)
    draft = current_draft(root)
    form = DraftEditForm(
        request.POST if request.method == "POST" else None,
        draft=draft,
        owner=request.user.is_superuser,
    )
    if request.method == "POST" and form.is_valid():
        try:
            edit_draft(actor=request.user, draft_id=pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(
                request,
                "Membership draft updated. The ID is unchanged and the earlier version is retained. No payment or benefits were activated.",
            )
            return redirect("membership_detail", pk=pk)
    return render(
        request,
        "core/membership_form.html",
        {"form": form, "draft": draft, "heading": f"Edit membership #{draft.membership_number}"},
    )
