import re

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from .customers import correct_previous_phone, create_customer, save_comment, update_customer
from .forms import CommentForm, CustomerForm, PreviousPhoneForm
from .models import AuditEvent, Customer, CustomerComment
from .permissions import staff_permission


def form_error(form, exc):
    form.add_error(None, " ".join(exc.messages))


@staff_permission("core.view_customer")
@require_safe
def customer_list(request):
    query = request.GET.get("q", "").strip()[:120]
    customers = Customer.objects.order_by("last_name", "pk")
    can_comments = request.user.has_perm("core.view_customercomment")
    digits = re.sub(r"\D", "", query)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
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
        customers = customers.filter(criteria).distinct()
    page = Paginator(customers, 25).get_page(request.GET.get("page"))
    for customer in page:
        matched = []
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
    return render(request, "core/customers.html", {"customers": page, "query": query})


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
            "comments": comments,
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
            )
        except ValidationError as exc:
            form_error(form, exc)
        else:
            messages.success(request, "Customer created.")
            return redirect("customer_detail", pk=customer.pk)
    return render(request, "core/customer_form.html", {"form": form, "heading": "Create customer"})


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
            update_customer(actor=request.user, customer_id=pk, **form.cleaned_data)
        except ValidationError as exc:
            form_error(form, exc)
        else:
            messages.success(
                request,
                "Customer updated. No confirmation email has been sent; booking email integration is not yet enabled.",
            )
            return redirect("customer_detail", pk=pk)
    return render(
        request,
        "core/customer_form.html",
        {"form": form, "heading": "Edit customer", "customer": customer},
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
    }
    for event in page:
        event.display_action = labels.get(event.action, "Customer history event")
        data = event.changes
        rows = []
        if event.action == "customer.updated":
            rows = [{"label": fields.get(key, key), **value} for key, value in data.items()]
        elif event.action == "customer.created":
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
        event.change_rows = rows
    return render(request, "core/customer_history.html", {"customer": customer, "events": page})
