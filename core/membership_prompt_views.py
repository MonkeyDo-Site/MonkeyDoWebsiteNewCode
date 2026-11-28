"""CSRF-protected renewal choices reuse the browser's existing booking draft."""

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from . import public_booking_views
from .membership_booking_prompts import choose
from .payments import staff_create
from .permissions import staff_permission
from .public_booking import customer_from_flow


def failure(request, error, return_url):
    text = (
        " ".join(error.messages)
        if isinstance(error, ValidationError)
        else "Choose a current renewal option."
    )
    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse({"error": text}, status=400)
    return render(
        request,
        "core/membership_prompt_saved.html",
        dict(error=text, return_url=return_url),
        status=400,
    )


def respond(request, *, flow, source, actor, return_url):
    try:
        value = request.POST.get("decision", "")
        token, action = value.rsplit(".", 1)
        customer = customer_from_flow(flow)
        answer = choose(
            customer=customer,
            flow=flow,
            source=source,
            actor=actor,
            token=token,
            action=action,
            pending_email=flow.get("contact_email", ""),
        )
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse(answer, headers={"Cache-Control": "private, no-store"})
        if answer.get("url"):
            return redirect(answer["url"])
        return render(
            request,
            "core/membership_prompt_saved.html",
            dict(
                message=answer["message"],
                return_url=return_url,
            ),
        )
    except (ValidationError, ValueError) as error:
        return failure(request, error, return_url)


@staff_permission("core.add_booking")
@require_POST
@sensitive_post_parameters("decision")
def staff_choice(request, token):
    try:
        flow = staff_create.read(request, token)
        if flow.get("completed_booking"):
            raise ValidationError("This booking is already confirmed. Open its current details.")
    except ValidationError as error:
        return failure(request, error, reverse("booking_create"))
    return respond(
        request,
        flow=flow,
        source="staff",
        actor=request.user,
        return_url=reverse("booking_create") + "?draft=" + str(token),
    )


@public_booking_views.enabled
@require_POST
@sensitive_post_parameters("decision")
def public_choice(request):
    try:
        public_booking_views.limit(request, "membership_choice", 240)
        flow = public_booking_views.current(request)
        if flow.get("workflow") != "integrated_v1" or flow.get("stage") not in {
            "details",
            "waiver",
            "review",
        }:
            raise ValidationError("Return to the current booking before choosing a renewal option.")
    except ValidationError as error:
        return failure(request, error, reverse("customer_booking"))
    return respond(
        request, flow=flow, source="public", actor=None, return_url=reverse("customer_booking")
    )
