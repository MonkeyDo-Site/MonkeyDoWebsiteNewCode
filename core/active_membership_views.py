"""Compact, explicit staff membership purchase and read-only overview."""

import uuid
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .booking_forms import CustomerChoice, customer_picker
from .forms import payment_method_choices
from .membership_prompt_emails import overview_context as requested_renewal_context
from .membership_records import MembershipInstallment, MembershipInvoice, MembershipPurchase
from .membership_renewal_notices import overview_context as renewal_notice_context
from .membership_renewals import renewal_details
from .membership_reservations import summary_for
from .membership_sales import installment_paid, membership_status, offer, purchase, today
from .models import Customer, MembershipDraft, PaymentMethod, PricingPolicy
from .pagination import paginate
from .payments.amounts import ZERO
from .payments.invoices import received, settled, total
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
    card_authorization = forms.UUIDField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, owner=False, prior=None, operation=None, actor=None, **kwargs):
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
            if self.is_bound and self.data.get("card_authorization") and actor:
                from .membership_card_setup import reviewed_source

                try:
                    selected = reviewed_source(
                        actor=actor,
                        authorization_id=self.data["card_authorization"],
                        customer=Customer.objects.get(pk=customer_id),
                        request_key=self.data.get("request_key"),
                        reviewed=self.data.get("reviewed"),
                    )
                    available |= Q(pk=selected.pk)
                except (ValidationError, Customer.DoesNotExist):
                    pass
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
    reviewed = forms.CharField(required=False, widget=forms.HiddenInput)
    card_authorization = forms.UUIDField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, member, actor=None, **kwargs):
        from .membership_payments import available_cards, card_update_review

        kwargs.setdefault("auto_id", "id_membership_card_%s")
        super().__init__(*args, **kwargs)
        self.fields["method"].queryset = available_cards(member)
        self.fields["method"].label_from_instance = lambda card: (
            f"{card.brand} ending in {card.last_four}"
        )
        self.initial["revision"] = member.billing_state.revision
        if member.billing_state.mandate:
            self.initial["method"] = member.billing_state.mandate.method_id
        if (
            actor
            and actor.has_perm("core.collect_payment")
            and actor.has_perm("core.add_membershippurchase")
            and member.purpose != "complimentary"
        ):
            self.initial["reviewed"] = card_update_review(actor=actor, member_id=member.pk)[
                "fingerprint"
            ]
        if self.is_bound and self.data.get("card_authorization") and actor:
            from .membership_card_setup import reviewed_source

            try:
                method = reviewed_source(
                    actor=actor,
                    authorization_id=self.data["card_authorization"],
                    customer=member.customer,
                    request_key=self.data.get("request_key"),
                    reviewed=self.data.get("reviewed"),
                )
                self.fields["method"].queryset = PaymentMethod.objects.filter(
                    Q(pk=method.pk) | Q(pk__in=self.fields["method"].queryset)
                )
            except ValidationError:
                pass


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
@require_http_methods(["GET", "HEAD", "POST"])
def memberships(request):
    check_enabled()
    from .membership_exports import export_response
    from .membership_reporting import filtered_members

    records, form, possible = filtered_members(
        request.POST if request.method == "POST" else request.GET
    )
    if request.method == "POST":
        if request.POST.get("action") != "export" or not request.user.has_perm(
            "core.export_membership_records"
        ):
            raise PermissionDenied
        if form.is_valid():
            return export_response(request, records, form)
    page = paginate(request, records)
    for member in page.object_list:
        member.possible_name_match = member.customer_id in possible
    rows = [(member, member.report_status) for member in page.object_list]
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("ends_from", None)
    params.pop("ends_to", None)
    params.pop("expiry", None)
    return render(
        request,
        "core/active_memberships.html",
        {
            "memberships": page,
            "rows": rows,
            "filter_form": form,
            "clear_expiry_query": params.urlencode(),
        },
    )


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
    initial = {"customer": request.GET.get("customer", "")}
    if request.method == "GET":
        saved_key = request.GET.get("purchase_key")
        owned_flow = request.session.get("membership_card_flows", {}).get(saved_key)
        if owned_flow and owned_flow.get("staff_actor") == request.user.pk:
            initial["request_key"] = saved_key
            initial["customer"] = owned_flow["customer_id"]
    form = PurchaseForm(
        posted,
        owner=request.user.is_superuser,
        initial=initial,
        prior=prior,
        operation=operation,
        actor=request.user,
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
                    card_authorization_id=form.cleaned_data.get("card_authorization"),
                    verified_received=form.cleaned_data["verified_received"],
                    send_confirmation={"yes": True, "no": False}.get(
                        form.cleaned_data.get("send_confirmation")
                    ),
                )
                return redirect("membership_overview", pk=member.pk)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
    setup_flow = request.session.get("membership_card_flows", {}).get(
        str(form["request_key"].value()), {}
    )
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
            "membership_card_configured": bool(
                settings.PAYMENT_SANDBOX_ENABLED
                and settings.BANQUEST_API_SOURCE_KEY
                and settings.BANQUEST_TOKENIZATION_PUBLIC_KEY.startswith("pk_")
            ),
            "membership_card_public_key": settings.BANQUEST_TOKENIZATION_PUBLIC_KEY,
            "membership_card_status_url": reverse(
                "membership_card_status", args=[setup_flow["setup_key"]]
            )
            if setup_flow.get("setup_key")
            else "",
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
    flow = request.session.get("membership_card_flows", {}).get(request.POST.get("request_key"))
    if (
        flow
        and flow.get("staff_actor") == request.user.pk
        and flow.get("customer_id") == form.cleaned_data["customer"].pk
    ):
        from .membership_card_setup import available_methods

        try:
            cards = available_methods(flow).order_by("last_four", "pk")
        except ValidationError:
            pass
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
    from .membership_cancellation_views import ACTIONS as cancellation_actions
    from .membership_cancellation_views import overview_controls

    cancellation_response, cancellation_context = overview_controls(request, member)
    if cancellation_response is not None:
        return cancellation_response
    from .customer_credit_views import ACTIONS as credit_actions
    from .customer_credit_views import controls as credit_controls

    credit_response, credit_context = credit_controls(request, member)
    if credit_response is not None:
        return credit_response
    payment_form = InstallmentPaymentForm(
        request.POST
        if request.method == "POST"
        and request.POST.get("action") in {"payment_preview", "payment_review", "payment_confirm"}
        else None,
        member=member,
    )
    card_form = MembershipCardForm(
        request.POST
        if request.method == "POST" and request.POST.get("action") == "card_update"
        else None,
        member=member,
        actor=request.user,
    )
    if not card_form.is_bound:
        saved_key = request.GET.get("card_key")
        saved_flow = request.session.get("membership_card_flows", {}).get(saved_key, {})
        if (
            saved_flow.get("operation") == "card_update"
            and saved_flow.get("prior_id") == member.pk
            and saved_flow.get("staff_actor") == request.user.pk
            and saved_flow.get("offer_fingerprint") == card_form.initial.get("reviewed")
        ):
            card_form.initial["request_key"] = saved_key
    payment_quote = None
    public_renewal_url = ""
    if request.method == "POST" and request.POST.get("action") == "renewal_link":
        from .membership_public_authority import create_link

        if not request.user.has_perm("core.collect_payment") or not request.user.has_perm(
            "core.add_membershippurchase"
        ):
            raise PermissionDenied
        try:
            _, token = create_link(
                actor=request.user,
                prior=member,
                request_key=forms.UUIDField().clean(request.POST.get("link_request_key")),
            )
            public_renewal_url = request.build_absolute_uri(
                reverse("public_membership_renewal", args=[token])
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    if request.method == "POST" and request.POST.get("action") not in {
        "renewal_link",
        *cancellation_actions,
        *credit_actions,
    }:
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
                        card_authorization_id=values["card_authorization"],
                        reviewed=values["reviewed"] or None,
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
    from .membership_funding import sale_needs_review

    installments = list(member.installments.select_related("invoice__sale", "cycle"))
    paid = ZERO
    for item in installments:
        item.paid = installment_paid(item)
        item.needs_review = hasattr(item, "invoice") and sale_needs_review(item.invoice.sale)
        item.cancelled = bool(
            member.billing_state.stopped_on
            and item.cycle.starts_on >= member.billing_state.stopped_on
        )
        try:
            item.money_received = received(item.invoice.sale)
            item.operations = item.invoice.sale.operations.order_by("requested_at")
            item.remaining = max(ZERO, total(item.invoice.sale) - settled(item.invoice.sale))
            item.effective_total = total(item.invoice.sale)
        except MembershipInvoice.DoesNotExist:
            item.money_received, item.remaining, item.operations = ZERO, item.quote["total"], []
            item.effective_total = item.quote["total"]
        paid += item.money_received
    status = membership_status(member)
    from .customer_credit import applied, balance, held_balance

    credit_used = sum(
        (applied(item.invoice.sale) for item in installments if hasattr(item, "invoice")), ZERO
    )
    from .payments.models import PaymentOperation

    funds = PaymentOperation.objects.filter(
        sale__membership_invoice__installment__purchase=member, state="succeeded"
    ).aggregate(
        gross=Sum("amount", filter=Q(kind="receipt")),
        returned=Sum("amount", filter=~Q(kind="receipt")),
    )
    from .membership_renewals import remaining_places, renewal_details

    renewal_problem = ""
    try:
        renewal_details(member)
    except ValidationError as exc:
        renewal_problem = " ".join(exc.messages)
    first = installments[0] if installments else None
    next_item = next((item for item in installments if not item.paid and not item.cancelled), None)
    setup_flow = request.session.get("membership_card_flows", {}).get(
        str(card_form["request_key"].value()), {}
    )
    return render(
        request,
        "core/active_membership_detail.html",
        {
            **renewal_notice_context(member),
            **requested_renewal_context(member),
            **cancellation_context,
            **credit_context,
            "member": member,
            "public_renewal_url": public_renewal_url,
            "renewal_link_key": uuid.uuid4(),
            "renewal_places": remaining_places(member),
            "renewal_problem": renewal_problem,
            "follow_on": member.follow_on.select_related("purchase__membership").order_by(
                "-purchased_on", "-purchase_id"
            )[:20],
            "root": member.membership,
            "status": status,
            "funding_review": any(item.needs_review for item in installments),
            "installments": installments,
            "money_received": paid,
            "credit_applied": credit_used,
            "credit_balance": balance(member.customer_id),
            "credit_held": held_balance(member.customer_id),
            "gross_received": funds["gross"] or ZERO,
            "money_returned": funds["returned"] or ZERO,
            "benefit_summary": summary_for(member),
            "next_item": next_item,
            "first": first,
            "today": today(),
            "payment_form": payment_form,
            "card_form": card_form,
            "membership_card_replacement": True,
            "membership_card_configured": bool(
                settings.PAYMENT_SANDBOX_ENABLED
                and settings.BANQUEST_API_SOURCE_KEY
                and settings.BANQUEST_TOKENIZATION_PUBLIC_KEY.startswith("pk_")
            ),
            "membership_card_public_key": settings.BANQUEST_TOKENIZATION_PUBLIC_KEY,
            "membership_card_endpoint": reverse("membership_card_replacement", args=[member.pk]),
            "membership_card_status_prefix": reverse("membership_card_setup"),
            "membership_card_status_url": reverse(
                "membership_card_status", args=[setup_flow["setup_key"]]
            )
            if setup_flow.get("setup_key")
            else "",
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
