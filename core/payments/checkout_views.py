"""Two-step staff review/confirm forms. Merely opening or previewing never charges."""

import uuid
from decimal import Decimal
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from core.membership_arrival_forms import confirm as arrival_confirm
from core.membership_arrival_forms import preview as arrival_preview
from core.membership_arrival_forms import ready as membership_ready
from core.models import Booking
from core.permissions import staff_permission

from .checkout import charge_state, coverage_facts, preview


def combined_label(combined):
    tender = combined["offer"]["expected_method"]
    if tender == "card":
        return f"Confirm arrival and membership — charge card ${combined['facts']['payment_due_today']}"
    return (
        f"Confirm arrival and membership — record {tender} ${combined['facts']['received_today']}"
    )


class ReceiptForm(forms.Form):
    received_on = forms.DateField(
        required=False,
        label="Zelle bank receipt date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="For an earlier Zelle transfer, use the bank receipt date. Leave blank for today.",
    )
    zelle_sender = forms.CharField(
        required=False, max_length=160, label="Zelle sender name/account"
    )

    def clean_received_on(self):
        from .receipts import receipt_date

        return receipt_date(self.cleaned_data.get("received_on"))


class ArrivalForm(ReceiptForm):
    apply_available_benefits = forms.BooleanField(
        required=False, label="Apply available Unlimited benefit"
    )
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reviewed_hash = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    children = forms.IntegerField(min_value=0, max_value=32767, label="Children")
    adults = forms.IntegerField(min_value=0, max_value=32767, label="Adults")
    babies = forms.IntegerField(min_value=0, max_value=32767, label="Babies")
    socks = forms.IntegerField(min_value=0, max_value=2147483647, label="Grip socks")
    waiver_confirmed = forms.ChoiceField(
        choices=[("", "Choose Yes or No"), ("yes", "Yes"), ("no", "No")],
        label="Was a waiver signed for everyone in this booking?",
        error_messages={"required": "The waiver confirmation field is required."},
    )
    waiver_mismatch_accepted = forms.ChoiceField(
        required=False,
        choices=[("yes", "Yes, go ahead"), ("no", "No, review waivers")],
        widget=forms.RadioSelect,
        label="Do you want to go ahead?",
    )
    method = forms.ChoiceField(choices=[], label="Actual payment")
    cash_amount = forms.DecimalField(
        required=False, min_value=0, max_digits=14, decimal_places=2, label="Cash already received"
    )
    check_amount = forms.DecimalField(
        required=False, min_value=0, max_digits=14, decimal_places=2, label="Check already received"
    )
    zelle_amount = forms.DecimalField(
        required=False, min_value=0, max_digits=14, decimal_places=2, label="Zelle already received"
    )
    gift_card_amount = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label="Physical gift-card amount presented",
    )
    zelle_verified = forms.BooleanField(
        required=False,
        label="Zelle payment was verified in the business bank account.",
        help_text="A customer screenshot alone does not confirm receipt.",
    )
    gift_card_verified = forms.BooleanField(
        required=False, label="The physical gift card has been presented and verified."
    )
    override_capacity = forms.BooleanField(
        required=False,
        label="Allow these unexpected attendees at arrival even if the configured capacity is exceeded.",
    )

    special_admissions = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label="Owner: adjust admissions price (optional)",
        help_text="Attendee counts changed? Keep or adjust the agreed total. Socks stay separate; no automatic partial cancellation fee is added.",
    )

    def __init__(
        self,
        *args,
        booking,
        owner=False,
        previewing=False,
        actor=None,
        pending_intent=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.previewing = previewing
        self.fields["waiver_confirmed"].required = not previewing
        self.booking = booking
        self.pending_intent = pending_intent
        from core.membership_arrival_forms import configure

        if pending_intent is None:
            configure(self, booking, actor)
        else:
            self.fields["pending_review"] = forms.UUIDField(widget=forms.HiddenInput)
            self.fields["pending_reason"] = forms.CharField(
                max_length=500,
                required=not previewing,
                label="Reason for reviewing this arrival again",
            )
        from core.membership_booking_exceptions import add_fields

        add_fields(self, booking=booking, owner=owner)
        from core.membership_booking import has_available_daily

        if not has_available_daily(booking):
            self.fields.pop("apply_available_benefits")
        special = charge_state(booking)
        if not owner or special.special_subtotal is None or special.comped:
            self.fields.pop("special_admissions")
        else:
            self.initial["special_admissions"] = special.special_subtotal
        self.fields["method"].choices = [
            (
                "card",
                "Charge card on file"
                if booking.expected_method == "card"
                else "No alternate payment received — charge card on file",
            ),
            ("cash", "Cash received"),
            ("check", "Check received"),
            ("zelle", "Zelle received"),
            ("gift_card", "Physical gift card presented"),
            ("split", "Split payment"),
        ]
        from .zelle import facts

        if facts(booking)["available"]:
            self.fields["method"].choices = [
                (
                    key,
                    "Charge remaining balance to card on file"
                    if key == "card"
                    else "Apply recorded Zelle"
                    if key == "zelle"
                    else label,
                )
                for key, label in self.fields["method"].choices
            ]
        if charge_state(booking).comped:
            self.fields["method"].choices = [("comped", "Owner-comped booking — no payment")]

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        method = data["method"]
        needs_zelle = method == "split" and data.get("zelle_amount")
        if not self.previewing and needs_zelle and not data["zelle_verified"]:
            self.add_error(
                "zelle_verified", "Verify the received Zelle payment in the business bank account."
            )
        if (
            (method == "gift_card" or (method == "split" and data.get("gift_card_amount")))
            and not self.previewing
            and not data["gift_card_verified"]
        ):
            self.add_error(
                "gift_card_verified",
                "Present and verify the physical gift card before recording this tender.",
            )
        data["waiver_confirmed"] = data.get("waiver_confirmed") == "yes"
        data["waiver_mismatch_accepted"] = data.get("waiver_mismatch_accepted") == "yes"
        if self.pending_intent and data.get("pending_review") != self.pending_intent.pk:
            self.add_error("pending_review", "Return to this booking's unfinished arrival.")
        data["split"] = {
            kind: str(data.get(kind + "_amount") or "0.00")
            for kind in ("cash", "check", "zelle", "gift_card")
        }
        from core.membership_arrival_forms import clean

        clean(self)
        return data


class ClosureForm(ReceiptForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reviewed_hash = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    charge_fee = forms.ChoiceField(
        choices=[
            ("", "Choose whether to charge"),
            ("yes", "Charge the applicable fee"),
            ("no", "Do not charge a fee"),
        ],
        label="Cancellation / no-show fee",
    )
    method = forms.ChoiceField(
        required=False,
        choices=[("card", "Charge card on file")],
        label="Fee payment",
        initial="card",
        widget=forms.HiddenInput,
    )

    send_email = forms.ChoiceField(
        choices=[("", "Choose Yes or No"), ("yes", "Yes"), ("no", "No")],
        label="Send customer email?",
    )
    reopen_affected_sessions = forms.BooleanField(
        required=False,
        label="Reopen affected sessions",
        help_text="Removes only this booking/custom session’s blocks. Independent closures remain.",
    )

    def __init__(self, *args, booking, kind, owner=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.booking = booking
        self.fields.pop("received_on")
        self.fields.pop("zelle_sender")
        if not booking.customer.email:
            self.fields["send_email"].help_text = "Add a customer email before selecting Yes."
        if not owner or kind != "cancellation":
            self.fields.pop("reopen_affected_sessions")
        if charge_state(booking).comped:
            self.fields["charge_fee"].choices = [("no", "Owner-comped booking — no fee")]
            self.fields["charge_fee"].initial = "no"

    def clean(self):
        data = super().clean()
        data["send_email"] = data.get("send_email") == "yes"
        if data["send_email"] and not self.booking.customer.email:
            self.add_error("send_email", "Add a current customer email or choose No.")
        data["charge_fee"] = data.get("charge_fee") == "yes"
        data["method"] = data.get("method") or "card"
        return data


def guarded(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not settings.BOOKING_COMPLETION_ENABLED:
            raise Http404
        for permission in ("core.change_booking", "core.view_customer", "core.collect_payment"):
            if not request.user.has_perm(permission):
                raise PermissionDenied
        return view(request, *args, **kwargs)

    return inner


def confirm_label(kind, quote, plan):
    noun = {"arrival": "arrival", "cancellation": "cancellation", "no_show": "no show"}[kind]
    if not plan:
        return (
            f"Confirm {noun} without a fee"
            if kind != "arrival"
            else "Confirm arrival — no payment due"
            if not quote.get("owner_comped")
            else "Confirm arrival — owner-comped $0"
        )
    if any(p.get("advance") for p in plan):
        new_parts = [p for p in plan if not p.get("advance")]
        if not new_parts:
            return f"Confirm {noun} — apply recorded Zelle"
        card_part = next((p for p in new_parts if p["tender"] == "card"), None)
        if card_part:
            return f"Confirm {noun} — apply Zelle and charge ${card_part['amount']}"
        remaining = sum((Decimal(p["amount"]) for p in new_parts), Decimal("0"))
        methods = ", ".join(p["tender"].replace("_", " ") for p in new_parts)
        return f"Confirm {noun} — apply Zelle and record {methods} ${remaining:.2f}"
    card = sum((p["amount"] != "0.00" and p["tender"] == "card" for p in plan))
    if card and len(plan) == 1:
        return f"Confirm {noun} and charge ${quote['total']}"
    if card:
        card_amount = next(p["amount"] for p in plan if p["tender"] == "card")
        return f"Confirm {noun}, record received funds and charge ${card_amount}"
    methods = ", ".join(p["tender"].replace("_", " ") for p in plan)
    return f"Confirm {noun} and record {methods} — ${quote['total']}"


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def checkout(request, pk, kind="arrival"):
    booking = get_object_or_404(
        Booking.objects.select_related("customer", "session"), pk=pk, workflow="integrated_v1"
    )
    from core.membership_arrival_pending import active_for_booking, status_data
    from core.membership_records import MembershipArrivalIntent

    pending = active_for_booking(pk)
    recovering = False
    if pending and kind == "arrival":
        from core import membership_arrival_recovery as recovery

        if request.method == "POST" and request.POST.get("start_owner_review") == "1":
            try:
                state = recovery.begin_review(actor=request.user, intent_id=pending.pk)
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
                return redirect("booking_arrival", pk=pk)
            return (
                redirect("booking_detail", pk=pk)
                if state.status == "completed"
                else redirect(reverse("booking_arrival", args=[pk]) + "?review_pending=1")
            )
        recovering = request.GET.get("review_pending") == "1" or str(
            request.POST.get("pending_review", "")
        ) == str(pending.pk)
        token = request.POST.get("arrival_draft") or request.GET.get("draft")
        if not recovering and token:
            from . import arrival_drafts

            try:
                saved = arrival_drafts.get(request, booking, token)
                recovering = saved["fields"].get("pending_review") == str(pending.pk)
            except ValidationError:
                pass
        if recovering:
            try:
                recovery.authorize(request.user, pending, reviewing=True)
            except ValidationError as error:
                if request.headers.get("Accept") == "application/json":
                    return JsonResponse(
                        {"errors": {"__all__": [{"message": " ".join(error.messages)}]}}, status=409
                    )
                messages.error(request, " ".join(error.messages))
                return redirect("booking_arrival", pk=pk)
    if pending and not recovering:
        if not request.user.has_perm("core.view_membershippurchase"):
            raise PermissionDenied
        if request.method == "POST" and request.POST.get("continue_approved") == "1":
            if request.user.pk != pending.actor_id and not request.user.is_superuser:
                raise PermissionDenied
            progress = status_data(pending)
            if not progress["can_continue"]:
                messages.error(request, progress["message"])
                return redirect("booking_arrival", pk=pk)
            from core.membership_arrival_pending import complete
            from core.models import AuditEvent

            complete(pending.pk)
            AuditEvent.objects.create(
                actor=request.user,
                action="membership.arrival_rechecked",
                record_type="booking",
                record_id=str(booking.reference),
                changes={"intent_id": str(pending.pk)},
            )
            return redirect("booking_arrival", pk=pk)
        if request.method == "GET" and kind == "arrival":
            progress = status_data(pending)
            may_recheck = request.user.pk == pending.actor_id or request.user.is_superuser
            may_start_review = False
            if request.user.is_superuser:
                try:
                    recovery.authorize(request.user, pending)
                    may_start_review = True
                except ValidationError:
                    pass
            return render(
                request,
                "core/booking_arrival_pending.html",
                {
                    "booking": booking,
                    "intent": pending,
                    "progress": progress,
                    "may_recheck": may_recheck,
                    "may_continue": progress["can_continue"] and may_recheck,
                    "may_start_review": may_start_review,
                    "counts": pending.facts["review"]["arrival"]["counts"],
                    "quote": pending.facts["review"]["arrival"]["quote"],
                    "status_url": reverse("booking_arrival_status", args=[pk, pending.pk]),
                    "sales_enabled": settings.MEMBERSHIP_SALES_ENABLED,
                    "has_extra_hold": booking.session.capacity_holds.filter(
                        pk=pending.hold_key, expires_at__gt=timezone.now()
                    ).exists(),
                },
            )
        if request.headers.get("Accept") == "application/json":
            if (
                request.POST.get("confirm_review") == "1"
                and str(request.POST.get("request_key")) == str(pending.pk)
                and request.POST.get("reviewed_hash") == pending.fingerprint
                and pending.actor_id == request.user.pk
            ):
                return JsonResponse(
                    {
                        "accepted": True,
                        "pending_membership": True,
                        "pending_url": reverse("booking_arrival", args=[pk]),
                        "status_url": reverse("booking_arrival_status", args=[pk, pending.pk]),
                        "booking_url": reverse("booking_detail", args=[pk]),
                    },
                    headers={"Cache-Control": "no-store"},
                )
            return JsonResponse(
                {
                    "errors": {
                        "__all__": [
                            {
                                "message": "Membership and arrival are already in progress. Open their current status."
                            }
                        ]
                    }
                },
                status=409,
            )
        return redirect("booking_arrival", pk=pk)
    form_type = ArrivalForm if kind == "arrival" else ClosureForm
    initial = {
        "request_key": uuid.uuid4(),
        "version": booking.edit_version,
        "method": "comped" if charge_state(booking).comped else booking.expected_method,
        "zelle_sender": booking.zelle_sender,
    }
    if kind == "arrival":
        initial.update(
            {name: getattr(booking, name) for name in ("children", "adults", "babies", "socks")}
        )
        if recovering:
            initial.update(pending.facts["review"]["arrival"]["counts"])
            initial.update(pending_review=str(pending.pk), apply_available_benefits=True)
    else:
        initial["method"] = "card"
    args = {"booking": booking, "owner": request.user.is_superuser}
    if kind == "arrival":
        args["actor"] = request.user
        args["pending_intent"] = pending if recovering else None
    if kind != "arrival":
        args["kind"] = kind
        args["owner"] = request.user.is_superuser
    is_live = request.headers.get("Accept") == "application/json"
    draft_token = None
    draft = None
    if kind == "arrival":
        from . import arrival_drafts

        if booking.attendance:
            return redirect("booking_detail", pk=pk)
        draft_token = request.POST.get("arrival_draft") or request.GET.get("draft")
        if draft_token:
            try:
                draft = arrival_drafts.get(request, booking, draft_token)
            except ValidationError as error:
                if is_live:
                    return JsonResponse(
                        {"errors": {"__all__": [{"message": " ".join(error.messages)}]}}, status=409
                    )
                messages.warning(request, " ".join(error.messages))
                return redirect("booking_arrival", pk=pk)
            if request.method == "GET":
                initial.update(draft["fields"])
        else:
            draft_token = arrival_drafts.create(request, booking, initial)
            draft = arrival_drafts.get(request, booking, draft_token)
        if request.method == "POST":
            draft = arrival_drafts.save(request, booking, draft_token, request.POST)
            departure = request.POST.get("continue_to")
            if departure == "card":
                return redirect(reverse("booking_card_change", args=[pk]) + "?draft=" + draft_token)
            if departure == "waiver":
                from core.waivers.services import create_share

                _, share_token = create_share(actor=request.user, booking_id=pk)
                arrival_drafts.set_waiver(request, booking, draft_token, share_token)
                return redirect(reverse("booking_waiver_sign", args=[pk]) + "?draft=" + draft_token)
        args["previewing"] = request.method == "POST" and request.POST.get("confirm_review") != "1"
    form = form_type(request.POST if request.method == "POST" else None, initial=initial, **args)
    reviewed = None
    combined = None
    label = None
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            if request.POST.get("confirm_review") == "1":
                result = arrival_confirm(
                    actor=request.user,
                    booking_id=pk,
                    kind=kind,
                    data=data,
                    request_key=data["request_key"],
                    reviewed_hash=data["reviewed_hash"],
                    confirmed=True,
                    pending_intent=pending if recovering else None,
                )
                if isinstance(result, MembershipArrivalIntent):
                    arrival_drafts.discard(request, draft_token)
                    if is_live:
                        return JsonResponse(
                            {
                                "accepted": True,
                                "pending_membership": True,
                                "pending_url": reverse("booking_arrival", args=[pk]),
                                "status_url": reverse(
                                    "booking_arrival_status", args=[pk, result.pk]
                                ),
                                "booking_url": reverse("booking_detail", args=[pk]),
                            },
                            headers={"Cache-Control": "no-store"},
                        )
                    return redirect("booking_arrival", pk=pk)
                queued = bool(
                    result.sale
                    and result.sale.operations.filter(
                        tender="card", state__in=["ready", "sending", "unknown", "action"]
                    ).exists()
                )
                if kind == "arrival":
                    from . import arrival_drafts

                    arrival_drafts.discard(request, draft_token)
                    if is_live:
                        return JsonResponse(
                            {
                                "confirmed": True,
                                "status_url": reverse(
                                    "booking_arrival_status", args=[pk, result.pk]
                                ),
                                "booking_url": reverse("booking_detail", args=[pk]),
                            },
                            headers={"Cache-Control": "no-store"},
                        )
                messages.success(
                    request,
                    "Attendance/action saved. Card payment is pending provider confirmation."
                    if queued
                    else "The reviewed booking action and actual received tender were recorded.",
                )
                return redirect("booking_detail", pk=pk)
            if data["version"] != booking.edit_version:
                raise ValidationError(
                    "The booking changed. Reload it and review the current details."
                )
            (_, _, quote, plan, _, digest), combined = arrival_preview(
                actor=request.user,
                booking_id=pk,
                kind=kind,
                data=data,
                validate_waivers=not is_live,
                pending_intent=pending if recovering else None,
            )
            values = request.POST.copy()
            values["reviewed_hash"] = digest
            form = form_type(values, **args)
            form.is_valid()
            reviewed = {"quote": quote, "plan": plan, "combined": combined}
            label = combined_label(combined) if combined else confirm_label(kind, quote, plan)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    from core.waivers.paper import active_customer_waivers

    from .zelle import facts as zelle_facts

    prepaid = zelle_facts(booking)
    from .zelle_views import ZelleReceiptForm

    zelle_form = ZelleReceiptForm(
        initial={"request_key": uuid.uuid4(), "sender_name": booking.zelle_sender}
    )
    from core.waivers.forms import NamedPaperWaiverForm

    arrival_paper_form = NamedPaperWaiverForm(
        prefix="paper",
        initial={
            **(draft.get("paper", {}) if draft else {}),
            "request_key": (draft.get("paper", {}).get("request_key") if draft else None)
            or uuid.uuid4(),
        },
    )
    for field in arrival_paper_form.fields.values():
        field.widget.attrs["form"] = "arrival-paper-record"

    if request.method == "GET" and kind == "arrival":
        values = {**initial, "waiver_confirmed": initial.get("waiver_confirmed", "")}
        preview_form = ArrivalForm(values, **(args | {"previewing": True}))
        if preview_form.is_valid():
            try:
                (_, _, quote, plan, _, digest), combined = arrival_preview(
                    actor=request.user,
                    booking_id=pk,
                    kind=kind,
                    data=preview_form.cleaned_data,
                    validate_waivers=False,
                    pending_intent=pending if recovering else None,
                )
                reviewed = {"quote": quote, "plan": plan, "combined": combined}
                form.initial["reviewed_hash"] = digest
                label = combined_label(combined) if combined else confirm_label(kind, quote, plan)
            except ValidationError as error:
                form = preview_form
                form.add_error(None, error)
    if reviewed:
        from core.price_adjustments import booking_price_adjustment

        reviewed["adjustment"] = booking_price_adjustment(booking, reviewed["quote"])
        reviewed["prepaid"] = prepaid["received"] - prepaid["refunded"]
        reviewed["refund_due"] = max(0, prepaid["available"] - Decimal(reviewed["quote"]["total"]))
        reviewed["remaining"] = max(0, Decimal(reviewed["quote"]["total"]) - prepaid["available"])
    waiver = (
        coverage_facts(
            booking,
            {
                name: (form.cleaned_data.get(name, 0) if form.is_bound else initial.get(name, 0))
                for name in ("children", "babies")
            },
        )
        if kind == "arrival"
        else None
    )
    if is_live:
        from django.template.loader import render_to_string

        if form.errors or reviewed is None:
            payload = {
                "errors": form.errors.get_json_data(),
                "hash": "",
                "can_confirm": False,
                "waiver": waiver,
            }
            if kind == "arrival" and not form.cleaned_data.get("member_add"):
                try:
                    from core.pricing import Line, quote_lines

                    valid = dict(form.cleaned_data, method="cash", split={})
                    _, _, safe_quote, _, _, _ = preview(
                        actor=request.user,
                        booking_id=pk,
                        kind=kind,
                        data=recovery.data_for(pending, valid) if recovering else valid,
                        validate_waivers=False,
                        membership_intent=pending if recovering else None,
                    )
                    lines = [
                        Line(
                            row["label"],
                            row["quantity"],
                            Decimal(row["unit_price"]),
                            row["taxable"],
                        )
                        for row in safe_quote["lines"]
                    ]
                    no_card = quote_lines(
                        lines, booking.quotes.first().policy, card_base=Decimal("0")
                    )
                    payload.update(
                        noncard_total=no_card["total"],
                        prepaid_available=str(prepaid["available"]),
                        html=render_to_string(
                            "core/partials/arrival_price.html",
                            {"reviewed": {"quote": safe_quote}},
                            request=request,
                        ),
                    )
                except ValidationError:
                    pass
            return JsonResponse(payload, status=400)
        from core.pricing import Line, quote_lines

        lines = [
            Line(row["label"], row["quantity"], Decimal(row["unit_price"]), row["taxable"])
            for row in quote["lines"]
        ]
        noncard = quote_lines(lines, booking.quotes.first().policy, card_base=Decimal("0"))
        return JsonResponse(
            {
                "html": render_to_string(
                    "core/partials/arrival_price.html", {"reviewed": reviewed}, request=request
                ),
                "hash": form["reviewed_hash"].value(),
                "label": label,
                "can_confirm": form.cleaned_data.get("waiver_confirmed") is True
                and membership_ready(form.cleaned_data, combined)
                and (
                    not waiver["mismatch"]
                    or form.cleaned_data.get("waiver_mismatch_accepted") is True
                )
                and (
                    not any(p["tender"] == "gift_card" for p in plan)
                    or form.cleaned_data.get("gift_card_verified") is True
                )
                and (
                    not any(p["tender"] == "zelle" and not p.get("advance") for p in plan)
                    or form.cleaned_data.get("zelle_verified") is True
                ),
                "waiver": waiver,
                "membership_terms": combined["offer"]["terms"] if combined else "",
                "membership_ready": membership_ready(form.cleaned_data, combined),
                "membership_needs_card": bool(
                    combined
                    and not combined["offer"]["comped"]
                    and (
                        combined["offer"]["billing"] == "monthly"
                        or combined["facts"]["membership_due"] != "0.00"
                    )
                ),
                "noncard_total": noncard["total"],
                "prepaid_available": str(prepaid["available"]),
                "plan": [
                    {
                        "tender": p["tender"],
                        "amount": p["amount"],
                        "advance": bool(p.get("advance")),
                    }
                    for p in plan
                ],
            },
            headers={"Cache-Control": "no-store"},
        )
    heading = {
        "arrival": "Start arrival",
        "cancellation": "Cancel booking",
        "no_show": "Mark as no show",
    }[kind]
    return render(
        request,
        "core/booking_checkout.html",
        {
            "booking": booking,
            "form": form,
            "reviewed": reviewed,
            "confirm_label": label,
            "heading": heading,
            "pending_membership": pending if recovering else None,
            "pending_receipt": status_data(pending) if recovering else None,
            "kind": kind,
            "zelle": prepaid,
            "zelle_form": zelle_form,
            "arrival_paper_form": arrival_paper_form,
            "arrival_draft": draft_token,
            "waiver_counts": waiver,
            "split_rows": draft.get("fields", {}).get("split_rows", "") if draft else "",
            "active_waivers": active_customer_waivers(booking) if kind == "arrival" else [],
        },
    )


class RemainingForm(ReceiptForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reviewed_hash = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    method = forms.ChoiceField(
        choices=[
            ("card", "Charge card on file"),
            ("cash", "Cash received"),
            ("check", "Check received"),
            ("zelle", "Zelle received"),
            ("gift_card", "Physical gift card presented"),
        ],
        label="Remaining payment",
    )
    context = forms.ChoiceField(
        choices=[
            ("", "Choose payment context"),
            ("arrival", "Customer is here reviewing the payment"),
            ("follow_up", "Following up after contacting the customer"),
        ],
        label="Payment review",
    )
    zelle_verified = forms.BooleanField(
        required=False, label="Zelle payment was verified in the business bank account."
    )
    gift_card_verified = forms.BooleanField(
        required=False, label="The physical gift card has been presented and verified."
    )

    def clean(self):
        data = super().clean()
        if data.get("method") == "zelle" and not data.get("zelle_verified"):
            self.add_error(
                "zelle_verified", "Verify the actual receipt in the business bank account."
            )
        if data.get("method") == "gift_card" and not data.get("gift_card_verified"):
            self.add_error(
                "gift_card_verified", "Verify the physical gift card before recording this tender."
            )
        return data


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def remaining_payment(request, pk, retry=False):
    from . import remainders

    booking = get_object_or_404(
        Booking.objects.select_related("customer", "session"), pk=pk, workflow="integrated_v1"
    )
    if retry and not request.user.is_superuser:
        raise PermissionDenied
    if retry:
        from .checkout import summary

        if not summary(booking).get("can_retry"):
            messages.warning(
                request, "This balance cannot be retried. Review its latest payment status first."
            )
            return redirect("booking_detail", pk=pk)
    form = RemainingForm(
        request.POST if request.method == "POST" else None,
        initial={
            "request_key": uuid.uuid4(),
            "method": "card",
            "zelle_sender": booking.zelle_sender,
            "context": "follow_up" if retry else "",
        },
    )
    if retry:
        form.fields["method"].choices = [("card", "Retry card on file")]
    elif booking.attendance in {"cancelled", "no_show"}:
        form.fields["method"].choices = [
            choice for choice in form.fields["method"].choices if choice[0] != "gift_card"
        ]
    reviewed = None
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        try:
            if request.POST.get("confirm_review") == "1":
                remainders.confirm(
                    actor=request.user,
                    booking_id=pk,
                    method=values["method"],
                    context=values["context"],
                    received_on=values.get("received_on"),
                    zelle_sender=values.get("zelle_sender", ""),
                    request_key=values["request_key"],
                    reviewed_hash=values["reviewed_hash"],
                    confirmed=True,
                    retry_declined=retry,
                )
                messages.success(
                    request,
                    "The reviewed remaining-payment action was recorded. Card payments require provider confirmation.",
                )
                return redirect("booking_detail", pk=pk)
            _, _, facts, digest, last_four = remainders.preview(
                actor=request.user,
                booking_id=pk,
                method=values["method"],
                context=values["context"],
                received_on=values.get("received_on"),
                zelle_sender=values.get("zelle_sender", ""),
                retry_declined=retry,
            )
            posted = request.POST.copy()
            posted["reviewed_hash"] = digest
            method_choices = form.fields["method"].choices
            form = RemainingForm(posted)
            form.fields["method"].choices = method_choices
            form.is_valid()
            reviewed = {
                "amount": facts["amount"],
                "method": values["method"],
                "last_four": last_four,
            }
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    return render(
        request,
        "core/remaining_payment.html",
        {"booking": booking, "form": form, "reviewed": reviewed, "retry": retry},
    )


class CompedForm(forms.Form):
    special_admissions = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label="Special admissions total (optional)",
        help_text="Leave blank for standard pricing. This covers admissions only; grip socks, tax and applicable processing fees stay separate.",
    )
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    comped = forms.BooleanField(
        required=False, label="Complimentary booking — all charges and cancellation fees are $0"
    )
    confirm = forms.BooleanField(label="Apply these owner pricing choices.")


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def complimentary(request, pk):
    from .comped import set_price

    if not request.user.is_superuser:
        raise PermissionDenied
    booking = get_object_or_404(
        Booking.objects.select_related("session"), pk=pk, workflow="integrated_v1"
    )
    form = CompedForm(
        request.POST if request.method == "POST" else None,
        initial={
            "version": booking.edit_version,
            "comped": charge_state(booking).comped,
            "special_admissions": charge_state(booking).special_subtotal,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            set_price(
                actor=request.user,
                booking_id=pk,
                version=form.cleaned_data["version"],
                comped=form.cleaned_data["comped"],
                special_admissions=form.cleaned_data["special_admissions"],
            )
            messages.success(
                request,
                "Owner pricing saved. Review the booking details and any required setup; waiver coverage is still required.",
            )
            return redirect("booking_detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    return render(request, "core/booking_comped.html", {"booking": booking, "form": form})


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET"])
def arrival_status(request, pk, checkout_id):
    from .invoices import received
    from .models import BookingCheckout

    pending = None
    from core.membership_schema import available

    if available("core_membershiparrivalintent"):
        from core.membership_arrival_pending import status_data
        from core.membership_records import MembershipArrivalCheckout, MembershipArrivalIntent

        pending = (
            MembershipArrivalIntent.objects.filter(pk=checkout_id, booking_id=pk)
            .select_related("progress", "purchase__membership", "purchase__billing_state")
            .first()
        )
        if pending:
            if not request.user.has_perm("core.view_membershippurchase"):
                raise PermissionDenied
            if pending.progress.status != "completed":
                return JsonResponse(
                    status_data(pending) | {"booking_url": reverse("booking_detail", args=[pk])},
                    headers={"Cache-Control": "no-store"},
                )
            checkout_id = MembershipArrivalCheckout.objects.get(pk=pending.pk).checkout_id

    checkout = get_object_or_404(
        BookingCheckout.objects.select_related("booking", "sale"),
        pk=checkout_id,
        booking_id=pk,
        kind="arrival",
    )
    operations = list(checkout.sale.operations.filter(kind="receipt")) if checkout.sale_id else []
    cards = [op for op in operations if op.tender == "card"]
    states = {op.state for op in cards}
    if states & {"declined", "cancelled"}:
        state, message = (
            "declined",
            "Arrival saved. The card payment was declined or cancelled. Review the unpaid balance before trying another payment.",
        )
    elif states & {"unknown", "action"}:
        state, message = (
            "review",
            "Arrival saved. The card payment needs review; its outcome is not confirmed. Do not submit another charge.",
        )
    elif states & {"ready", "sending"}:
        state, message = "processing", "Arrival saved. Card payment is processing."
    elif cards:
        state, message = "succeeded", "Arrival confirmed. Card payment approved."
    else:
        state, message = (
            "succeeded",
            "Arrival confirmed. The reviewed received payment was recorded.",
        )
    combined = (
        getattr(checkout, "membership_purchase", None)
        if available("core_membershiparrivalcheckout")
        else None
    )
    new_received = received(checkout.sale) if checkout.sale_id else Decimal("0.00")
    if combined:
        from core.membership_arrival import membership_funded

        if not membership_funded(combined):
            state, message = (
                "review",
                "The membership funding needs owner review before another payment.",
            )
    if combined and state == "succeeded":
        # The visit status must include the simultaneously collected membership
        # payment, while applied credit and earlier Zelle stay separate.
        from .amounts import ZERO, amount

        first = combined.purchase.installments.first()
        member_paid = received(first.invoice.sale) if first else ZERO
        prepaid = sum((amount(p["amount"]) for p in checkout.details["plan"] if p["advance"]), ZERO)
        new_received = member_paid + max(ZERO, new_received - prepaid)
        message = "Arrival and membership confirmed. The reviewed received payment was recorded."
    pending_data = {}
    if pending:
        from .invoices import settled, total

        first_sale = pending.purchase.installments.first().invoice.sale
        pending_data = {
            "membership_received": str(received(first_sale)),
            "membership_balance": str(
                max(Decimal("0.00"), total(first_sale) - settled(first_sale))
            ),
            "pending_membership": False,
        }
    return JsonResponse(
        {
            "state": state,
            "message": message,
            "received": str(new_received),
            "booking_url": reverse("booking_detail", args=[pk]),
            **pending_data,
        },
        headers={"Cache-Control": "no-store"},
    )
