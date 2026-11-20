from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from .customers import correct_previous_phone, create_customer, save_comment, update_customer
from .forms import CommentForm, CustomerForm, PreviousPhoneForm, phone_search_digits
from .memberships import current_draft
from .models import AuditEvent, Customer, CustomerComment, PaymentOperation, WaiverSignature
from .name_matching import match_rank, name_candidates
from .pagination import paginate
from .payments.models import PaymentMethod
from .permissions import staff_permission


def form_error(form, exc):
    form.add_error(None, " ".join(exc.messages))


@staff_permission("core.view_customer")
@require_safe
def customer_list(request):
    query = request.GET.get("q", "").strip()[:120]
    customers = Customer.objects.order_by("last_name", "pk")
    customer_type = request.GET.get("type", "")
    if customer_type in dict(Customer._meta.get_field("customer_type").choices):
        customers = customers.filter(customer_type=customer_type)
    can_comments = request.user.has_perm("core.view_customercomment")
    digits = phone_search_digits(query)
    exact, possible = name_candidates(query) if query else ([], [])
    if query:
        criteria = (
            Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(previous_email__icontains=query)
        )
        if query.isascii() and query.isdigit():
            criteria |= Q(pk=int(query)) if len(query) <= 18 else Q(pk=-1)
        if digits:
            criteria |= Q(phone__contains=digits) | Q(previous_phone__contains=digits)
        if can_comments:
            criteria |= Q(comments__body__icontains=query)
            if digits:
                criteria |= Q(comments__search_digits__contains=digits)
        customers = (
            customers.filter(criteria | Q(pk__in=exact + possible))
            .distinct()
            .order_by(match_rank("pk", exact, possible), "last_name", "pk")
        )
    page = paginate(request, customers)
    for customer in page:
        matched = []
        if customer.pk in possible:
            matched.append("Possible Last Name match")
        if query:
            for field, label in (
                ("last_name", "Last Name"),
                ("email", "Current email"),
                ("previous_email", "Previous email"),
            ):
                if query.casefold() in getattr(customer, field).casefold():
                    matched.append(label)
            if (
                query.isascii()
                and query.isdigit()
                and len(query) <= 18
                and int(query) == customer.pk
            ):
                matched.append("Customer ID")
            for field, label in (("phone", "Current phone"), ("previous_phone", "Previous phone")):
                if digits and digits in getattr(customer, field):
                    matched.append(label)
            if can_comments:
                comment_filter = Q(body__icontains=query)
                if digits:
                    comment_filter |= Q(search_digits__contains=digits)
                if customer.comments.filter(comment_filter).exists():
                    matched.append("Comment")
        customer.search_matches = ", ".join(matched)
    return render(
        request,
        "core/customers.html",
        {
            "customers": page,
            "query": query,
            "customer_type": customer_type,
            "type_choices": Customer._meta.get_field("customer_type").choices,
            "filter_query": request.GET.urlencode(),
        },
    )


@staff_permission("core.view_customer")
@require_safe
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    bookings = customer.bookings.select_related("session").order_by("session__starts_at", "pk")
    can_view_bookings = request.user.has_perm("core.view_booking")
    if not can_view_bookings:
        bookings = bookings.none()
    today = timezone.localdate()
    todays = list(bookings.filter(session__starts_at__date=today))
    comments = (
        customer.comments.select_related("author")
        if request.user.has_perm("core.view_customercomment")
        else []
    )
    return render(
        request,
        "core/customer_detail.html",
        {
            "customer": customer,
            "customer_waivers": WaiverSignature.objects.filter(
                Q(customer_links__customer=customer) | Q(booking_links__booking__customer=customer)
            )
            .distinct()
            .order_by("-signed_at")[:3]
            if settings.WAIVER_ENABLED and request.user.has_perm("core.view_waiversignature")
            else [],
            "waiver_now": timezone.now(),
            "saved_methods": PaymentMethod.objects.filter(
                customer=customer, reusable=True, state="active"
            )
            if settings.PAYMENT_SANDBOX_ENABLED
            and request.user.has_perm("core.view_paymentoperation")
            else [],
            "payment_operations": PaymentOperation.objects.filter(sale__customer=customer).order_by(
                "-requested_at"
            )[:5]
            if settings.PAYMENT_SANDBOX_ENABLED
            and request.user.has_perm("core.view_paymentoperation")
            else [],
            "comments": comments,
            "membership_drafts": [
                current_draft(root)
                for root in customer.membership_drafts.select_related(
                    "pricing", "fee_policy"
                ).prefetch_related("revisions")
            ]
            if request.user.has_perm("core.view_membershipdraft")
            else [],
            "can_view_bookings": can_view_bookings,
            "first_today": todays[0] if todays else None,
            "more_today": todays[1:],
            "upcoming_count": bookings.filter(session__starts_at__date__gt=today).count(),
            "previous_count": bookings.filter(session__starts_at__date__lt=today).count(),
            "bookings": bookings,
            "comment_form": CommentForm(),
        },
    )


@staff_permission("core.add_customer")
@require_http_methods(["GET", "POST"])
def customer_create(request):
    form = CustomerForm(
        request.POST if request.method == "POST" else None, owner=request.user.is_superuser
    )
    if request.method == "POST" and form.is_valid():
        try:
            customer = create_customer(
                actor=request.user,
                last_name=form.cleaned_data["last_name"],
                phone=form.cleaned_data["phone"],
                email=form.cleaned_data["email"],
                customer_type=form.cleaned_data.get("customer_type", "family"),
                referral_source=form.cleaned_data["referral_source"],
            )
        except ValidationError as exc:
            form_error(form, exc)
        else:
            warn_historical_email(request, customer)
            messages.success(request, "Customer created.")
            return redirect("customer_detail", pk=customer.pk)
    return render(
        request,
        "core/customer_form.html",
        {
            "form": form,
            "heading": "Create customer",
            "email_conflict": email_conflict(form)
            if request.user.has_perm("core.view_customer")
            else None,
        },
    )


@staff_permission("core.view_customer")
@staff_permission("core.change_customer")
@require_http_methods(["GET", "POST"])
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(
        request.POST if request.method == "POST" else None,
        customer=customer,
        owner=request.user.is_superuser,
    )
    if request.method == "POST" and form.is_valid():
        try:
            customer = update_customer(actor=request.user, customer_id=pk, **form.cleaned_data)
        except ValidationError as exc:
            form_error(form, exc)
        else:
            warn_historical_email(request, customer)
            messages.success(
                request,
                "Customer updated. No confirmation email has been sent; booking email integration is not yet enabled.",
            )
            return redirect("customer_detail", pk=pk)
    return render(
        request,
        "core/customer_form.html",
        {
            "form": form,
            "heading": "Edit customer",
            "customer": customer,
            "email_conflict": email_conflict(form, pk),
        },
    )


@staff_permission("core.view_customer")
@staff_permission("core.change_customer")
@require_http_methods(["GET", "POST"])
def previous_phone(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    customer = get_object_or_404(Customer, pk=pk)
    form = PreviousPhoneForm(
        request.POST if request.method == "POST" else None,
        initial={"phone": customer.previous_phone, "revision": customer.revision},
    )
    if request.method == "POST" and form.is_valid():
        try:
            correct_previous_phone(actor=request.user, customer_id=pk, **form.cleaned_data)
        except ValidationError as exc:
            form_error(form, exc)
        else:
            messages.success(
                request, "Previous phone corrected. The change was recorded in customer history."
            )
            return redirect("customer_detail", pk=pk)
    return render(
        request,
        "core/customer_form.html",
        {"form": form, "heading": "Correct previous phone", "customer": customer},
    )


@staff_permission("core.view_customer")
@require_http_methods(["GET", "POST"])
def comment_edit(request, pk, comment_id=None):
    permission = "core.change_customercomment" if comment_id else "core.add_customercomment"
    if not request.user.has_perm(permission) or (
        comment_id and not request.user.has_perm("core.view_customercomment")
    ):
        raise PermissionDenied
    customer = get_object_or_404(Customer, pk=pk)
    comment = (
        get_object_or_404(CustomerComment, pk=comment_id, customer=customer) if comment_id else None
    )
    form = CommentForm(
        request.POST if request.method == "POST" else None,
        initial={"body": comment.body, "revision": comment.revision} if comment else {},
    )
    if request.method == "POST" and form.is_valid():
        try:
            save_comment(
                actor=request.user, customer_id=pk, comment_id=comment_id, **form.cleaned_data
            )
        except ValidationError as exc:
            form_error(form, exc)
        else:
            messages.success(request, "Comment saved with history.")
            return redirect("customer_detail", pk=pk)
    return render(
        request,
        "core/customer_form.html",
        {
            "form": form,
            "heading": "Edit comment" if comment else "Add comment",
            "customer": customer,
        },
    )


@staff_permission("core.view_customer")
@staff_permission("core.view_customer_history")
@require_safe
def customer_history(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    events = AuditEvent.objects.filter(record_type="customer", record_id=str(pk)).select_related(
        "actor"
    )
    if not request.user.has_perm("core.view_customercomment"):
        events = events.exclude(action__in=["customer.comment_added", "customer.comment_updated"])
    page = Paginator(events, 30).get_page(request.GET.get("page"))
    labels = {
        "customer.created": "Customer created",
        "customer.updated": "Customer details updated",
        "customer.public_email_added": "Email added during booking",
        "customer.public_test_created": "Customer created during booking",
        "customer.email_notice_reviewed": "Historical email notice reviewed",
        "customer.public_profile_conflict": "Booking verification matched different customer profiles",
        "customer.profile_conflict_reviewed": "Owner reviewed the booking profile conflict",
        "customer.comment_added": "Comment added",
        "customer.comment_updated": "Comment edited",
        "customer.email_history_archived": "Previous email archived",
        "customer.previous_phone_corrected": "Previous phone corrected",
    }
    fields = {
        "last_name": "Last Name",
        "phone": "Current phone",
        "previous_phone": "Previous phone",
        "email": "Current email",
        "previous_email": "Previous email",
        "customer_type": "Customer type",
        "referral_source": "How did you hear about MonkeyDo?",
    }
    for event in page:
        event.display_action = labels.get(event.action, "Customer history event")
        data = event.changes
        rows = []
        if event.action in {"customer.updated", "customer.public_email_added"}:
            rows = [{"label": fields.get(key, key), **value} for key, value in data.items()]
        elif event.action in {"customer.created", "customer.public_test_created"}:
            rows = [
                {"label": fields.get(key, key), "before": "", "after": value}
                for key, value in data.items()
            ]
        elif event.action in {"customer.comment_added", "customer.comment_updated"}:
            rows = [
                {
                    "label": "Comment",
                    "before": data.get("before", ""),
                    "after": data.get("after", ""),
                }
            ]
        elif event.action == "customer.previous_phone_corrected":
            rows = [
                {
                    "label": "Previous phone",
                    "before": data.get("before", ""),
                    "after": data.get("after", ""),
                }
            ]
        elif event.action == "customer.email_history_archived":
            rows = [
                {
                    "label": "Previous email",
                    "before": data.get("email", ""),
                    "after": "Preserved in a dated staff comment",
                }
            ]
        for row in rows:
            if row["label"] == "Customer type":
                row["before"] = dict(Customer._meta.get_field("customer_type").choices).get(
                    row["before"], row["before"]
                )
                row["after"] = dict(Customer._meta.get_field("customer_type").choices).get(
                    row["after"], row["after"]
                )
        event.is_creation = event.action in {
            "customer.created",
            "customer.public_test_created",
            "customer.comment_added",
        }
        event.change_rows = rows
    return render(request, "core/customer_history.html", {"customer": customer, "events": page})


@staff_permission("core.view_customer")
@require_safe
def customer_choices(request):
    from django.http import JsonResponse

    query = request.GET.get("q", "").strip()[:120]
    if len(query) < 2:
        return JsonResponse({"results": []})
    digits = phone_search_digits(query)
    exact, possible = name_candidates(query)
    criteria = Q(last_name__icontains=query) | Q(pk__in=exact + possible)
    if digits:
        criteria |= Q(phone__contains=digits) | Q(previous_phone__contains=digits)
    rows = Customer.objects.filter(criteria).order_by(
        match_rank("pk", exact, possible), "last_name", "pk"
    )[:30]
    return JsonResponse(
        {
            "results": [
                {
                    "id": c.pk,
                    "text": f"{c.last_name} · {c.phone} · {c.customer_number}"
                    + (" · Possible name match" if c.pk in possible else ""),
                }
                for c in rows
            ]
        },
        headers={"Cache-Control": "private, no-store"},
    )


def warn_historical_email(request, customer):
    from .customers import historical_email_customers

    if historical_email_customers(customer.email, customer.pk).exists():
        messages.warning(
            request,
            "This email address appears in another customer's previous contact history. It is not currently assigned to that customer, so your change was allowed. The profiles have not been merged.",
        )


def email_conflict(form, exclude=None):
    if not form.is_bound or not form.errors.get("email"):
        return None
    email = form.data.get("email", "").strip()[:254]
    return (
        Customer.objects.filter(email__iexact=email).exclude(pk=exclude).first() if email else None
    )
