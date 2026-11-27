"""Compact, explicit staff membership purchase and read-only overview."""

import uuid
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .booking_forms import CustomerChoice, customer_picker
from .forms import payment_method_choices
from .membership_records import MembershipInstallment, MembershipInvoice, MembershipPurchase
from .membership_renewals import renewal_details
from .membership_reservations import summary_for
from .membership_sales import installment_paid, membership_status, offer, purchase, today
from .models import Customer, MembershipDraft, PaymentMethod, PricingPolicy
from .pagination import paginate
from .payments.amounts import ZERO
from .payments.invoices import received, total
from .permissions import staff_permission

OFFER_FIELDS = (
    "customer",
    "kind",
    "places",
    "months",
    "billing",
    "starts_on",
    "expected_method",
    "minimum_override",
    "comped",
)


class PurchaseForm(forms.Form):
    operation = forms.ChoiceField(
        required=False,
        initial="purchase",
        choices=[(x, x.title()) for x in ("purchase", "renewal", "addition")],
        widget=forms.HiddenInput,
    )
    prior_id = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    customer = CustomerChoice(queryset=Customer.objects.order_by("last_name", "pk"))
    kind = forms.ChoiceField(
        label="Membership", choices=MembershipDraft._meta.get_field("kind").choices
    )
    places = forms.IntegerField(
        min_value=1, max_value=2147483647, initial=1, label="Membership places"
    )
    months = forms.IntegerField(min_value=3, initial=3)
    billing = forms.ChoiceField(choices=MembershipDraft._meta.get_field("billing").choices)
    starts_on = forms.DateField(
        initial=today, label="Starts on", widget=forms.DateInput(attrs={"type": "date"})
    )
    expected_method = forms.ChoiceField(label="First payment")
    minimum_override = forms.BooleanField(
        required=False, label="Owner: allow a one- or two-month term"
    )
    comped = forms.BooleanField(required=False, label="Owner: complimentary membership")
    send_confirmation = forms.ChoiceField(
        required=False,
        label="Send complimentary confirmation email?",
        choices=[("", "Choose Yes or No"), ("yes", "Yes"), ("no", "No")],
    )
    method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.none(),
        required=False,
        label="Saved card",
        empty_label="Choose a saved card",
    )
    verified_received = forms.BooleanField(
        required=False, label="I confirm this membership payment was received"
    )
    accepted = forms.BooleanField(
        required=False,
        label="The customer accepts the membership terms and the scheduled payments shown above",
    )
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reviewed = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, owner=False, prior=None, operation=None, **kwargs):
        bound = args[0] if args and args[0] is not None else {}
        operation = operation or bound.get("operation") or "purchase"
        if prior is None:
            prior_id = bound.get("prior_id")
            if str(prior_id).isascii() and str(prior_id).isdigit() and len(str(prior_id)) <= 18:
                prior = (
                    MembershipPurchase.objects.select_related(
                        "membership", "customer", "billing_state__mandate"
                    )
                    .filter(pk=prior_id)
                    .first()
                )
        self.prior = prior
        self.minimum_months = 3
        initial = dict(kwargs.pop("initial", {}))
        initial["operation"] = operation
        if prior is not None:
            initial.update(
                customer=prior.customer_id,
                prior_id=prior.pk,
                kind=prior.membership.kind,
                billing=prior.membership.billing,
                places=1,
            )
            if prior.billing_state.mandate:
                initial["method"] = prior.billing_state.mandate.method_id
            if operation == "renewal":
                try:
                    details = renewal_details(prior)
                except ValidationError:
                    details = None
                if details:
                    self.minimum_months = details["minimum_months"]
                    initial.update(
                        starts_on=details["starts_on"],
                        months=self.minimum_months,
                        places=max(1, details["available_places"]),
                    )
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)
        self.fields["expected_method"].choices = payment_method_choices(
            PricingPolicy.objects.first()
        )
        labels = {
            "card": "Credit card",
            "cash": "Cash",
            "check": "Check",
            "zelle": "Zelle",
            "gift_card": "Gift card (verified)",
        }
        self.fields["expected_method"].choices = [
            (key, labels.get(key, label)) for key, label in self.fields["expected_method"].choices
        ]
        if owner:
            self.fields["months"] = forms.IntegerField(min_value=1, initial=3)
        else:
            self.fields["months"] = forms.IntegerField(
                min_value=self.minimum_months, initial=self.minimum_months
            )
            for name in ("minimum_override", "comped", "send_confirmation"):
                self.fields.pop(name)
        if prior is not None:
            self.fields["customer"].widget = forms.HiddenInput()
            if operation == "renewal":
                self.fields["starts_on"].disabled = True
                self.fields[
                    "starts_on"
                ].help_text = (
                    "Renewal starts after the current term, or today when renewing after expiry."
                )
        customer_picker(self)
        customer_id = (self.data if self.is_bound else self.initial).get("customer")
        if (
            str(customer_id).isascii()
            and str(customer_id).isdigit()
            and len(str(customer_id)) <= 18
        ):
            available = Q(reusable=True)
            if prior and prior.billing_state.mandate:
                available |= Q(pk=prior.billing_state.mandate.method_id)
            self.fields["method"].queryset = PaymentMethod.objects.filter(
                available,
                customer_id=customer_id,
                state="active",
                environment="sandbox",
                provider_method__isnull=False,
            ).order_by("last_four", "pk")
        self.fields["method"].label_from_instance = lambda card: (
            f"{card.brand} ending in {card.last_four}"
        )

    def offer_values(self):
        return {name: self.cleaned_data.get(name, False) for name in OFFER_FIELDS} | {
            "operation": self.cleaned_data.get("operation") or "purchase",
            "prior_id": self.cleaned_data.get("prior_id"),
        }


class InstallmentPaymentForm(forms.Form):
    installment = forms.ModelChoiceField(
        queryset=MembershipInstallment.objects.none(), label="Installment"
    )
    tender = forms.ChoiceField(
        label="Payment method",
        choices=[
            ("card", "Membership card"),
            ("cash", "Cash"),
            ("check", "Check"),
            ("zelle", "Zelle"),
            ("gift_card", "Physical gift card (verified)"),
        ],
    )
    received_on = forms.DateField(
        required=False,
        label="Zelle bank receipt date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    verified_received = forms.BooleanField(
        required=False, label="I verified that this payment was received"
    )
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reviewed = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, member, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["installment"].queryset = member.installments.select_related("cycle").filter(
            due_on__lte=today()
        )
        if member.billing_state.stopped_on:
            self.fields["installment"].queryset = self.fields["installment"].queryset.filter(
                cycle__starts_on__lt=member.billing_state.stopped_on
            )
        unpaid_ids = [
            item.pk for item in self.fields["installment"].queryset if not installment_paid(item)
        ]
        # Bound confirmations may be a replay after the first request settled.
        # The immutable action key handles that replay; the service rejects any
        # new attempt against an already-paid installment.
        if not self.is_bound:
            self.fields["installment"].queryset = self.fields["installment"].queryset.filter(
                pk__in=unpaid_ids
            )
        self.fields["installment"].label_from_instance = lambda item: (
            f"Month {item.number} · {item.due_on:%b %d, %Y}"
        )
        unpaid = next(
            (item for item in self.fields["installment"].queryset if not installment_paid(item)),
            None,
        )
        if unpaid:
            self.initial["installment"] = unpaid.pk


class MembershipCardForm(forms.Form):
    method = forms.ModelChoiceField(queryset=PaymentMethod.objects.none(), label="Membership card")
    accepted = forms.BooleanField(
        label="The customer authorizes this card for the remaining accepted membership payments, including applicable card processing fees"
    )
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)

    def __init__(self, *args, member, **kwargs):
        from .membership_payments import available_cards

        kwargs.setdefault("auto_id", "id_membership_card_%s")
        super().__init__(*args, **kwargs)
        self.fields["method"].queryset = available_cards(member)
        self.fields["method"].label_from_instance = lambda card: (
            f"{card.brand} ending in {card.last_four}"
        )
        self.initial["revision"] = member.billing_state.revision
        if member.billing_state.mandate:
            self.initial["method"] = member.billing_state.mandate.method_id


def check_enabled():
    if not settings.MEMBERSHIP_SALES_ENABLED:
        raise Http404


def display_offer(data):
    if data is None:
        return None
    return data | {
        "starts_on": date.fromisoformat(data["starts_on"]),
        "ends_on": date.fromisoformat(data["ends_on"]),
        "installments": [
            item | {"due_on": date.fromisoformat(item["due_on"])} for item in data["installments"]
        ],
    }


@staff_permission("core.view_membershippurchase")
@staff_permission("core.view_customer")
@require_safe
def memberships(request):
    check_enabled()
    records = MembershipPurchase.objects.select_related(
        "membership", "customer", "billing_state"
    ).prefetch_related("installments__invoice__sale")
    customer = request.GET.get("customer", "")
    if customer.isascii() and customer.isdigit() and len(customer) <= 18:
        records = records.filter(customer_id=customer)
    page = paginate(request, records.order_by("-accepted_at", "-pk"))
    rows = [(member, membership_status(member)) for member in page.object_list]
    return render(request, "core/active_memberships.html", {"memberships": page, "rows": rows})


@staff_permission("core.add_membershippurchase")
@staff_permission("core.view_customer")
@staff_permission("core.collect_payment")
@require_http_methods(["GET", "POST"])
def membership_purchase(request, operation="purchase", prior_pk=None):
    check_enabled()
    prior = (
        get_object_or_404(
            MembershipPurchase.objects.select_related(
                "membership", "customer", "billing_state__mandate"
            ),
            pk=prior_pk,
        )
        if prior_pk
        else None
    )
    posted = request.POST.copy() if request.method == "POST" else None
    if prior and posted is not None:
        posted.update(customer=str(prior.customer_id), prior_id=str(prior.pk), operation=operation)
    form = PurchaseForm(
        posted,
        owner=request.user.is_superuser,
        initial={"customer": request.GET.get("customer", "")},
        prior=prior,
        operation=operation,
    )
    reviewed_offer = None
    if request.method == "POST" and form.is_valid():
        try:
            reviewed_offer = offer(actor=request.user, **form.offer_values())
            if request.POST.get("action") == "confirm":
                member = purchase(
                    actor=request.user,
                    **form.offer_values(),
                    request_key=form.cleaned_data["request_key"],
                    reviewed=form.cleaned_data["reviewed"],
                    accepted=form.cleaned_data["accepted"],
                    method_id=form.cleaned_data["method"].pk
                    if form.cleaned_data["method"]
                    else None,
                    verified_received=form.cleaned_data["verified_received"],
                    send_confirmation={"yes": True, "no": False}.get(
                        form.cleaned_data.get("send_confirmation")
                    ),
                )
                return redirect("membership_overview", pk=member.pk)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
    return render(
        request,
        "core/membership_purchase.html",
        {
            "form": form,
            "offer": display_offer(reviewed_offer),
            "prior": prior,
            "operation": operation,
            "heading": {
                "purchase": "Purchase membership",
                "renewal": "Renew membership",
                "addition": "Add membership places",
            }[operation],
        },
    )


@staff_permission("core.add_membershippurchase")
@staff_permission("core.view_customer")
@staff_permission("core.collect_payment")
@require_POST
def membership_offer(request):
    check_enabled()
    # Only product/price inputs are validated here; a preview never saves anything.
    form = PurchaseForm(request.POST, owner=request.user.is_superuser)
    for name in (
        "method",
        "accepted",
        "verified_received",
        "reviewed",
        "request_key",
        "send_confirmation",
    ):
        form.fields.pop(name, None)
    if not form.is_valid():
        return JsonResponse(
            {"error": " ".join(str(error) for errors in form.errors.values() for error in errors)},
            status=400,
        )
    try:
        data = offer(actor=request.user, **form.offer_values())
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    available = Q(reusable=True)
    if form.prior and form.prior.billing_state.mandate:
        available |= Q(pk=form.prior.billing_state.mandate.method_id)
    cards = PaymentMethod.objects.filter(
        available,
        customer=form.cleaned_data["customer"],
        state="active",
        environment="sandbox",
        provider_method__isnull=False,
    ).order_by("last_four", "pk")
    return JsonResponse(
        {
            "html": render_to_string(
                "core/partials/membership_offer.html",
                {"offer": display_offer(data)},
                request=request,
            ),
            "fingerprint": data["fingerprint"],
            "terms": data["terms"],
            "starts_on": data["starts_on"],
            "minimum_months": data["minimum_months"],
            "cards": [
                {"id": str(card.pk), "label": f"{card.brand} ending in {card.last_four}"}
                for card in cards
            ],
        }
    )


@staff_permission("core.view_membershippurchase")
@staff_permission("core.view_customer")
@require_http_methods(["GET", "POST"])
def membership_overview(request, pk):
    check_enabled()
    member = get_object_or_404(
        MembershipPurchase.objects.select_related(
            "membership", "customer", "billing_state__mandate__method"
        ),
        pk=pk,
    )
    payment_form = InstallmentPaymentForm(
        request.POST
        if request.method == "POST" and request.POST.get("action") != "card_update"
        else None,
        member=member,
    )
    card_form = MembershipCardForm(
        request.POST
        if request.method == "POST" and request.POST.get("action") == "card_update"
        else None,
        member=member,
    )
    payment_quote = None
    if request.method == "POST":
        from .membership_payments import change_card, collect_installment, payment_review

        if not request.user.has_perm("core.collect_payment") or not request.user.has_perm(
            "core.add_membershippurchase"
        ):
            raise PermissionDenied
        action = request.POST.get("action")
        form = card_form if action == "card_update" else payment_form
        if form.is_valid():
            values = form.cleaned_data
            try:
                if action == "card_update":
                    change_card(
                        actor=request.user,
                        member_id=member.pk,
                        method_id=values["method"].pk,
                        revision=values["revision"],
                        request_key=values["request_key"],
                        accepted=values["accepted"],
                    )
                    messages.success(request, "Membership card updated. No payment was requested.")
                    return redirect("membership_overview", pk=member.pk)
                params = dict(
                    actor=request.user,
                    member_id=member.pk,
                    installment_id=values["installment"].pk,
                    tender=values["tender"],
                    received_on=values["received_on"],
                )
                if action == "payment_confirm":
                    result = collect_installment(
                        **params,
                        reviewed=values["reviewed"],
                        request_key=values["request_key"],
                        confirmed=True,
                        verified_received=values["verified_received"],
                    )
                    messages.success(
                        request,
                        "Membership payment requested. Check its result before another attempt."
                        if result.operation.tender == "card"
                        else "Membership payment recorded.",
                    )
                    return redirect("membership_overview", pk=member.pk)
                if action not in {"payment_preview", "payment_review"}:
                    raise ValidationError("Choose a membership billing action.")
                payment_quote = payment_review(**params)
                if action == "payment_preview":
                    return JsonResponse(
                        payment_quote
                        | {
                            "html": render_to_string(
                                "core/partials/membership_payment_review.html",
                                {"payment_quote": payment_quote},
                                request=request,
                            )
                        }
                    )
                payment_form.data = payment_form.data.copy()
                payment_form.data["reviewed"] = payment_quote["fingerprint"]
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
        if action == "payment_preview":
            return JsonResponse(
                {
                    "error": " ".join(
                        str(error) for errors in form.errors.values() for error in errors
                    )
                },
                status=400,
            )
    installments = list(member.installments.select_related("invoice__sale", "cycle"))
    paid = ZERO
    for item in installments:
        item.paid = installment_paid(item)
        item.cancelled = bool(
            member.billing_state.stopped_on
            and item.cycle.starts_on >= member.billing_state.stopped_on
        )
        try:
            item.money_received = received(item.invoice.sale)
            item.operations = item.invoice.sale.operations.order_by("requested_at")
            item.remaining = max(ZERO, total(item.invoice.sale) - item.money_received)
            item.effective_total = total(item.invoice.sale)
        except MembershipInvoice.DoesNotExist:
            item.money_received, item.remaining, item.operations = ZERO, item.quote["total"], []
            item.effective_total = item.quote["total"]
        paid += item.money_received
    status = membership_status(member)
    from .membership_renewals import remaining_places, renewal_details

    renewal_problem = ""
    try:
        renewal_details(member)
    except ValidationError as exc:
        renewal_problem = " ".join(exc.messages)
    first = installments[0] if installments else None
    next_item = next((item for item in installments if not item.paid and not item.cancelled), None)
    return render(
        request,
        "core/active_membership_detail.html",
        {
            "member": member,
            "renewal_places": remaining_places(member),
            "renewal_problem": renewal_problem,
            "follow_on": member.follow_on.select_related("purchase__membership").order_by(
                "-purchased_on", "-purchase_id"
            )[:20],
            "root": member.membership,
            "status": status,
            "installments": installments,
            "money_received": paid,
            "benefit_summary": summary_for(member),
            "next_item": next_item,
            "first": first,
            "today": today(),
            "payment_form": payment_form,
            "card_form": card_form,
            "billing_history": member.billing_actions.select_related(
                "actor", "mandate__method", "operation"
            ).order_by("-recorded_at")[:20],
            "payment_quote": payment_quote,
            "has_due_payment": payment_form.fields["installment"].queryset.exists(),
            "current_cycle": member.membership.cycles.filter(
                starts_on__lte=today(), ends_on__gte=today()
            ).first(),
        },
    )
