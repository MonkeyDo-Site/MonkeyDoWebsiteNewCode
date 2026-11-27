"""Staff-safe financial history and owner-only read-only-provider reconciliation."""

from decimal import Decimal
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from core.forms import phone_search_digits
from core.name_matching import match_rank, name_candidates
from core.pagination import paginate
from core.permissions import staff_permission

from .gateway import ProviderFailure
from .models import PaymentFollowup, PaymentMethod, PaymentOperation, PaymentSetup
from .operations import reconcile
from .setup import reconcile_setup


def enabled_view(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not settings.PAYMENT_SANDBOX_ENABLED:
            raise Http404
        if not request.user.has_perm("core.view_customer"):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return inner


class PaymentFilters(forms.Form):
    q = forms.CharField(max_length=120, required=False, label="Family, phone or email")
    state = forms.MultipleChoiceField(
        required=False,
        choices=PaymentOperation.State.choices,
        widget=forms.CheckboxSelectMultiple,
        label="Status",
    )
    after = forms.DateField(
        required=False, label="Requested from", widget=forms.DateInput(attrs={"type": "date"})
    )
    before = forms.DateField(
        required=False, label="Requested through", widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        data = super().clean()
        if data.get("after") and data.get("before") and data["before"] < data["after"]:
            raise forms.ValidationError("The end date must be on or after the start date.")
        return data


@staff_permission("core.view_paymentoperation")
@enabled_view
@require_safe
def payments(request):
    records = PaymentOperation.objects.select_related("sale__customer", "sale__booking").order_by(
        "-requested_at", "-pk"
    )
    form = PaymentFilters(request.GET)
    possible = []
    if form.is_valid():
        data = form.cleaned_data
        query = data["q"].strip()
        if query:
            exact, possible = name_candidates(query)
            digits = phone_search_digits(query)
            match = (
                Q(sale__customer__last_name__icontains=query)
                | Q(sale__customer__email__icontains=query)
                | Q(sale__customer__previous_email__icontains=query)
                | Q(sale__customer_id__in=exact + possible)
            )
            if digits:
                match |= Q(sale__customer__phone__contains=digits) | Q(
                    sale__customer__previous_phone__contains=digits
                )
            records = records.filter(match).order_by(
                match_rank("sale__customer_id", exact, possible), "-requested_at", "-pk"
            )
        if data["state"]:
            records = records.filter(state__in=data["state"])
        if data["after"]:
            records = records.filter(requested_at__date__gte=data["after"])
        if data["before"]:
            records = records.filter(requested_at__date__lte=data["before"])
    else:
        records = records.none()
    page = paginate(request, records)
    for item in page:
        item.possible_name = item.sale.customer_id in possible
    setups = (
        PaymentSetup.objects.filter(state__in=["unknown", "customer_sending", "method_sending"])
        .select_related("customer")
        .order_by("-created_at")[:10]
        if request.user.is_superuser
        else []
    )
    return render(
        request,
        "core/payments.html",
        {
            "operations": page,
            "form": form,
            "setups": setups,
            "removing_methods": PaymentMethod.objects.filter(state="removing")
            if request.user.is_superuser
            else [],
        },
    )


class ReconcileForm(forms.Form):
    provider_reference = forms.RegexField(
        r"^[1-9][0-9]{0,19}$",
        max_length=20,
        required=False,
        label="Banquest transaction reference (if not already recorded)",
    )


class FollowupForm(forms.Form):
    plan = forms.ChoiceField(
        choices=PaymentFollowup._meta.get_field("plan").choices, label="Payment follow-up"
    )


@staff_permission("core.view_paymentoperation")
@enabled_view
@require_http_methods(["GET", "POST"])
def payment_detail(request, pk):
    operation = get_object_or_404(
        PaymentOperation.objects.select_related("sale__customer", "sale__booking", "original"),
        pk=pk,
    )
    form = ReconcileForm(request.POST if request.method == "POST" else None)
    followup_form = FollowupForm(
        request.POST
        if request.method == "POST" and request.POST.get("action") == "followup"
        else None
    )
    if request.method == "POST" and request.POST.get("action") == "followup":
        from .checkout import note_followup

        if not request.user.has_perm("core.collect_payment"):
            raise PermissionDenied
        if followup_form.is_valid():
            try:
                note_followup(
                    actor=request.user, operation_id=pk, plan=followup_form.cleaned_data["plan"]
                )
                messages.success(
                    request, "Follow-up recorded. Payment and attendance amounts were not changed."
                )
                return redirect("payment_detail", pk=pk)
            except ValidationError as error:
                followup_form.add_error(None, " ".join(error.messages))
    elif request.method == "POST":
        if not request.user.is_superuser:
            raise PermissionDenied
        if form.is_valid():
            try:
                result = reconcile(
                    operation_id=operation.pk,
                    actor=request.user,
                    provider_reference=form.cleaned_data["provider_reference"] or None,
                )
                if result.state == "succeeded":
                    messages.success(request, "The provider result is verified and recorded.")
                else:
                    messages.warning(
                        request, "The outcome still needs review. No new charge or refund was sent."
                    )
                return redirect("payment_detail", pk=operation.pk)
            except (ValidationError, ProviderFailure):
                form.add_error(
                    None,
                    "The result could not be confirmed. Review the original provider transaction before any further payment.",
                )
    from .checkout import summary

    can_retry = bool(
        request.user.is_superuser
        and operation.sale.booking_id
        and summary(operation.sale.booking).get("can_retry")
    )
    return render(
        request,
        "core/payment_detail.html",
        {
            "operation": operation,
            "form": form,
            "followup_form": followup_form,
            "can_retry": can_retry,
        },
    )


@staff_permission("core.view_paymentoperation")
@enabled_view
@require_http_methods(["GET", "POST"])
def card_setup_detail(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    setup = get_object_or_404(PaymentSetup.objects.select_related("customer", "method"), pk=pk)
    error = None
    if request.method == "POST":
        try:
            reconcile_setup(actor=request.user, setup_id=pk)
            messages.success(request, "Saved-card metadata was reconciled. No payment was charged.")
            return redirect("card_setup_detail", pk=pk)
        except (ValidationError, ProviderFailure):
            error = (
                "Card setup still needs provider review. No nonce exchange or charge was repeated."
            )
    return render(request, "core/payment_setup_detail.html", {"setup": setup, "error": error})


class CorrectionForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    kind = forms.ChoiceField(
        choices=[("refund", "Refund already completed"), ("void", "Void already completed")]
    )
    provider_reference = forms.RegexField(
        r"^[1-9][0-9]{0,19}$",
        max_length=20,
        required=False,
        label="Completed Banquest refund / original void reference",
    )
    received_on = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Actual non-card refund date",
    )
    confirm = forms.BooleanField(
        label="This correction has already been completed. Record it here without sending another refund or void."
    )

    def __init__(self, *args, operation, **kwargs):
        super().__init__(*args, **kwargs)
        self.original = operation
        if operation.tender == "card":
            self.fields["provider_reference"].required = True
            self.fields.pop("received_on")
        else:
            self.fields["kind"].choices = [("refund", "Refund already given")]
            self.fields.pop("provider_reference")
        from .amounts import COMPONENTS

        labels = dict(
            net="Admission / product amount",
            fee="Processing fee",
            item_tax="Tax on products",
            fee_tax="Tax on processing fee",
        )
        self.parts = []
        for row in operation.allocation:
            line = operation.sale.lines.get(pk=row["line"])
            for component in COMPONENTS:
                if Decimal(row[component]):
                    name = "line_" + row["line"].replace("-", "") + "_" + component
                    self.fields[name] = forms.DecimalField(
                        min_value=0,
                        max_value=Decimal(row[component]),
                        max_digits=14,
                        decimal_places=2,
                        initial="0.00",
                        label=line.description + " — " + labels[component],
                    )
                    self.parts.append((row["line"], component, name))

    def allocation(self):
        from .amounts import COMPONENTS

        values = {
            row["line"]: {"line": row["line"], **dict.fromkeys(COMPONENTS, "0.00")}
            for row in self.original.allocation
        }
        for line, component, field in self.parts:
            values[line][component] = str(self.cleaned_data[field])
        return list(values.values())


@staff_permission("core.view_paymentoperation")
@enabled_view
@require_http_methods(["GET", "POST"])
def payment_correction(request, pk):
    import uuid

    from .corrections import record_correction

    if not request.user.is_superuser:
        raise PermissionDenied
    operation = get_object_or_404(
        PaymentOperation.objects.select_related("sale__customer"),
        pk=pk,
        kind="receipt",
        state="succeeded",
    )
    form = CorrectionForm(
        request.POST if request.method == "POST" else None,
        operation=operation,
        initial={"request_key": uuid.uuid4()},
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = record_correction(
                actor=request.user,
                original_id=operation.pk,
                kind=form.cleaned_data["kind"],
                allocation=form.allocation(),
                request_key=form.cleaned_data["request_key"],
                provider_reference=form.cleaned_data.get("provider_reference", ""),
                received_on=form.cleaned_data.get("received_on"),
                confirmed=True,
            )
            messages.success(
                request,
                "Completed correction verified and recorded. No new refund or void was sent.",
            )
            return redirect("payment_detail", pk=result.pk)
        except (ValidationError, ProviderFailure) as error:
            form.add_error(
                None,
                " ".join(error.messages)
                if isinstance(error, ValidationError)
                else "The provider correction could not be verified. Check its reference and exact amounts; nothing has been recorded.",
            )
    return render(request, "core/payment_correction.html", {"operation": operation, "form": form})


@staff_permission("core.view_paymentoperation")
@enabled_view
@require_http_methods(["GET", "POST"])
def background_job(request, pk):
    from .job_review import disposition, recover
    from .models import DurableJob

    if not request.user.is_superuser:
        raise PermissionDenied
    job = get_object_or_404(DurableJob, pk=pk)
    action, explanation = disposition(job)
    collection_item = None
    if settings.MEMBERSHIP_SALES_ENABLED and job.kind == "membership_collection":
        from core.membership_collection_queue import installment_for
        from core.membership_records import MembershipInstallment

        try:
            collection_item = installment_for(job)
        except (ValidationError, MembershipInstallment.DoesNotExist):
            pass
    error = None
    if request.method == "POST":
        try:
            recover(
                actor=request.user,
                job_id=pk,
                action=request.POST.get("action"),
                confirmed=request.POST.get("confirm") == "on",
            )
            messages.success(
                request,
                "The reviewed background action was recorded. Its outcome remains visible in the linked records.",
            )
            return redirect("dashboard")
        except ValidationError as exc:
            error = " ".join(exc.messages)
    return render(
        request,
        "core/background_job.html",
        {
            "job": job,
            "action": action,
            "explanation": explanation,
            "error": error,
            "collection_item": collection_item,
        },
    )


@staff_permission("core.view_customer")
@staff_permission("core.view_paymentoperation")
@enabled_view
@require_POST
def retire_card(request, pk):
    from .methods import retire_future_use
    from .models import PaymentMethod

    method = get_object_or_404(PaymentMethod.objects.select_related("customer"), pk=pk)
    if not request.user.has_perm("core.change_customer"):
        raise PermissionDenied
    if request.POST.get("confirm") != "on":
        messages.error(request, "Confirm removal of this card’s future-use choice first.")
    else:
        retire_future_use(actor=request.user, method_id=pk)
        messages.success(
            request,
            "This card will no longer be offered for future visits. Existing booking responsibilities remain until settled or replaced.",
        )
    return redirect("customer_detail", pk=method.customer_id)


@staff_permission("core.view_paymentoperation")
@enabled_view
@require_http_methods(["GET", "POST"])
def removal_review(request, pk):
    from .methods import reconcile_removal
    from .models import PaymentMethod

    if not request.user.is_superuser:
        raise PermissionDenied
    method = get_object_or_404(PaymentMethod, pk=pk, state="removing")
    if request.method == "POST":
        result = reconcile_removal(actor=request.user, method_id=pk)
        messages.success(
            request,
            "Provider removal verified."
            if result.state == "removed"
            else "This source is still present or could not be checked. Review removal in the provider dashboard, then check again. No deletion was repeated.",
        )
        return redirect("payments")
    return render(request, "core/card_removal_review.html", {"method": method})
