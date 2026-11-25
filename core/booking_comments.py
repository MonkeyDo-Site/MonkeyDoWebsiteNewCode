"""Permission-checked booking comments using the existing audited comment record."""

import re

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.forms import CommentForm
from core.models import AuditEvent, Booking, CustomerComment
from core.permissions import require_actor, staff_permission


@transaction.atomic
def save(*, actor, booking_id, body, comment_id=None, revision=None):
    for permission in (
        "core.view_booking",
        "core.change_booking",
        "core.view_customer",
        "core.view_customercomment",
        "core.change_customercomment" if comment_id else "core.add_customercomment",
    ):
        require_actor(actor, permission)
    booking = Booking.objects.get(pk=booking_id)
    if comment_id:
        comment = CustomerComment.objects.select_for_update().get(
            pk=comment_id, booking=booking, customer=booking.customer
        )
        if revision != comment.revision:
            raise ValidationError("This booking comment changed. Reload before editing.")
        before = comment.body
        comment.body = body.strip()
        comment.revision += 1
    else:
        before = None
        comment = CustomerComment(
            booking=booking, customer=booking.customer, author=actor, body=body.strip()
        )
    comment.search_digits = re.sub(r"\D", "", comment.body)
    comment.full_clean()
    comment.save()
    AuditEvent.objects.create(
        actor=actor,
        action="booking.comment_updated" if comment_id else "booking.comment_added",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "comment_id": comment.pk,
            "before": before,
            "after": comment.body,
            "revision": comment.revision,
        },
    )
    return comment


@staff_permission("core.view_booking")
@staff_permission("core.view_customer")
@staff_permission("core.view_customercomment")
@require_http_methods(["GET", "POST"])
def edit(request, pk, comment_id=None):
    require_actor(request.user, "core.change_booking")
    require_actor(
        request.user, "core.change_customercomment" if comment_id else "core.add_customercomment"
    )
    booking = get_object_or_404(Booking.objects.select_related("customer"), pk=pk)
    comment = (
        get_object_or_404(CustomerComment, pk=comment_id, booking=booking) if comment_id else None
    )
    form = CommentForm(
        request.POST if request.method == "POST" else None,
        initial={"body": comment.body, "revision": comment.revision} if comment else {},
    )
    if request.method == "POST" and form.is_valid():
        try:
            save(actor=request.user, booking_id=pk, comment_id=comment_id, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            messages.success(request, "Booking comment saved with history.")
            return redirect(reverse("booking_detail", args=[pk]) + "#booking-comments")
    return render(
        request,
        "core/booking_comment_form.html",
        {"booking": booking, "form": form, "editing": comment is not None},
    )
