import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from .booking_forms import CustomerChoice
from .memberships import create_draft
from .models import AuditEvent, Customer, MembershipDraft, MembershipPricing
from .permissions import staff_permission


class DraftForm(forms.Form):
    customer = CustomerChoice(queryset=Customer.objects.order_by("last_name", "pk"))
    kind = forms.ChoiceField(choices=MembershipDraft._meta.get_field("kind").choices)
    places = forms.IntegerField(
        min_value=1, max_value=2147483647, label="Anonymous membership places", initial=1
    )
    months = forms.IntegerField(
        min_value=3, label="Whole months (new membership minimum: 3)", initial=3
    )
    billing = forms.ChoiceField(choices=MembershipDraft._meta.get_field("billing").choices)
    starts_on = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="Test start date (New York)"
    )
    expected_method = forms.ChoiceField(
        choices=MembershipDraft._meta.get_field("expected_method").choices
    )
    creation_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)


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
    records = MembershipDraft.objects.select_related("customer", "actor")
    if customer.isascii() and customer.isdigit() and len(customer) <= 18:
        records = records.filter(customer_id=int(customer))
    return render(
        request,
        "core/membership_drafts.html",
        {"drafts": Paginator(records, 25).get_page(request.GET.get("page"))},
    )


@staff_permission("core.view_membershipdraft")
@staff_permission("core.add_membershipdraft")
@staff_permission("core.view_customer")
@require_http_methods(["GET", "POST"])
def draft_create(request):
    form = DraftForm(request.POST if request.method == "POST" else None)
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
    draft = get_object_or_404(MembershipDraft.objects.select_related("customer", "actor"), pk=pk)
    return render(
        request,
        "core/membership_detail.html",
        {
            "draft": draft,
            "cycles": Paginator(draft.cycles.all(), 24).get_page(request.GET.get("page")),
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
