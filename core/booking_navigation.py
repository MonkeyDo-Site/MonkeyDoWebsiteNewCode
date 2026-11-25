"""Session-owned GET checkpoints for browser history; financial actions remain POST-only."""

from copy import deepcopy

from django.shortcuts import redirect

CHECKPOINTS = "customer_booking_navigation"
RANK = {
    "phone": 1,
    "retry_phone": 2,
    "name": 2,
    "previous": 2,
    "contact": 2,
    "email": 2,
    "email_lookup": 2,
    "name_confirm": 2,
    "email_confirm": 2,
    "details": 3,
    "waiver": 4,
    "review": 5,
    "done": 6,
}


def remember(request, flow):
    history = request.session.get(CHECKPOINTS, {})
    if history.get("key") != flow["key"]:
        history = {"key": flow["key"], "steps": {}}
    history["steps"][flow["stage"]] = deepcopy(flow)
    request.session[CHECKPOINTS] = history


def restore(request, flow):
    if request.method != "GET" or "step" not in request.GET:
        return flow, None
    if request.GET.get("flow") != flow["key"]:
        return flow, redirect("customer_booking")
    step = request.GET["step"]
    if step == flow["stage"]:
        return flow, None
    history = request.session.get(CHECKPOINTS, {})
    saved = history.get("steps", {}).get(step) if history.get("key") == flow["key"] else None
    if saved is None or step == "done" or saved.get("workflow") != flow.get("workflow"):
        return flow, redirect("customer_booking")
    if saved.get("navigation_revision", 0) != flow.get("navigation_revision", 0) and RANK.get(
        step, 2
    ) >= RANK.get(flow["stage"], 2):
        return flow, redirect("customer_booking")
    restored = deepcopy(saved)
    restored["answers"] = flow.get("answers", {})
    restored["navigation_revision"] = flow.get("navigation_revision", 0)
    # Reuse only the same customer's later signed evidence/card recovery pointer.
    if saved.get("proof") == flow.get("proof") and saved.get("contact") == flow.get("contact"):
        for name in (
            "waiver_signatures",
            "last_waiver_signature",
            "payment_setup_key",
            "payment_consent",
            "payment_method_changed",
            "payment_consent_method",
        ):
            if name in flow:
                restored[name] = flow[name]
            else:
                restored.pop(name, None)
    return restored, None


def remember_answers(flow, stage, form, post):
    if RANK.get(stage, 2) >= 4:
        return
    answers = {
        name: post.get(name, "") for name in form.fields if not form.fields[name].widget.is_hidden
    }
    previous = flow.setdefault("answers", {}).get(stage)
    if previous is not None and previous != answers:
        flow["navigation_revision"] = flow.get("navigation_revision", 0) + 1
    flow["answers"][stage] = answers
