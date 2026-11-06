"""Audited staff-only customer changes. No public lookup or outbound delivery yet."""

import re

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Q

from .forms import normalize_phone
from .models import AuditEvent, Customer, CustomerComment
from .permissions import require_actor


def contact_lock():
    # Serialize contact-number ownership checks across different customers.
    # PostgreSQL's unique constraint also protects current phone values.
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [727001])


def check_phone_available(phone, customer_id=None):
    conflicts = Customer.objects.exclude(pk=customer_id).filter(
        Q(phone=phone) | Q(previous_phone=phone)
    )
    if conflicts.exists():
        raise ValidationError(
            "This phone belongs to an existing or previous customer contact. Resolve that record before reusing the number."
        )


def audit(actor, action, customer, changes):
    AuditEvent.objects.create(
        actor=actor,
        action=action,
        record_type="customer",
        record_id=str(customer.pk),
        changes=changes,
    )


def new_comment(actor, customer, body, system=False):
    comment = CustomerComment(
        customer=customer,
        author=actor,
        body=body.strip(),
        system_generated=system,
        search_digits=re.sub(r"\D", "", body),
    )
    comment.full_clean()
    comment.save()
    return comment


@transaction.atomic
def create_customer(*, actor, last_name, phone, email, customer_type="family"):
    require_actor(actor, "core.add_customer", owner=customer_type != "family")
    phone = normalize_phone(phone)
    contact_lock()
    check_phone_available(phone)
    customer = Customer(
        last_name=last_name.strip(), phone=phone, email=email.strip(), customer_type=customer_type
    )
    customer.full_clean()
    customer.save()
    audit(
        actor,
        "customer.created",
        customer,
        {f: getattr(customer, f) for f in ("last_name", "phone", "email", "customer_type")},
    )
    return customer


@transaction.atomic
def update_customer(
    *,
    actor,
    customer_id,
    revision,
    last_name,
    phone,
    email,
    move_previous_phone=None,
    customer_type=None,
):
    require_actor(actor, "core.change_customer")
    contact_lock()
    customer = Customer.objects.select_for_update().get(pk=customer_id)
    if customer.revision != revision:
        raise ValidationError(
            "This customer changed while you were editing. Reload the page and review the latest record."
        )
    phone = normalize_phone(phone)
    before = {
        f: getattr(customer, f)
        for f in (
            "last_name",
            "phone",
            "email",
            "customer_type",
            "previous_phone",
            "previous_email",
        )
    }
    if customer_type is not None and customer_type != customer.customer_type:
        require_actor(actor, "core.change_customer", owner=True)
        customer.customer_type = customer_type
    if phone != customer.phone:
        if move_previous_phone not in {"yes", "no"}:
            raise ValidationError("Choose whether to move the old phone to Previous phone.")
        check_phone_available(phone, customer.pk)
        if move_previous_phone == "yes":
            customer.previous_phone = customer.phone
        customer.phone = phone
    email = email.strip()
    if email != customer.email:
        if customer.previous_email:
            archived = new_comment(
                actor, customer, f"Previous email archived: {customer.previous_email}", system=True
            )
            audit(
                actor,
                "customer.email_history_archived",
                customer,
                {"comment_id": archived.pk, "email": customer.previous_email},
            )
        customer.previous_email = customer.email
        customer.email = email
    customer.last_name = last_name.strip()
    customer.full_clean()
    changes = {
        f: {"before": old, "after": getattr(customer, f)}
        for f, old in before.items()
        if old != getattr(customer, f)
    }
    if changes:
        customer.revision += 1
        customer.save()
        audit(actor, "customer.updated", customer, changes)
    return customer


@transaction.atomic
def correct_previous_phone(*, actor, customer_id, revision, phone):
    require_actor(actor, "core.change_customer", owner=True)
    contact_lock()
    customer = Customer.objects.select_for_update().get(pk=customer_id)
    if revision != customer.revision:
        raise ValidationError("Customer changed. Reload and review before correcting.")
    phone = normalize_phone(phone, optional=True)
    if phone:
        check_phone_available(phone, customer.pk)
    old = customer.previous_phone
    if old != phone:
        customer.previous_phone = phone
        customer.revision += 1
        customer.save()
        audit(actor, "customer.previous_phone_corrected", customer, {"before": old, "after": phone})
    return customer


@transaction.atomic
def save_comment(*, actor, customer_id, body, comment_id=None, revision=None):
    require_actor(
        actor, "core.change_customercomment" if comment_id else "core.add_customercomment"
    )
    require_actor(actor, "core.view_customer")
    customer = Customer.objects.get(pk=customer_id)
    if comment_id:
        require_actor(actor, "core.view_customercomment")
        comment = CustomerComment.objects.select_for_update().get(pk=comment_id, customer=customer)
        if comment.system_generated:
            raise ValidationError("Archived contact history cannot be edited.")
        if revision != comment.revision:
            raise ValidationError("Comment changed. Reload before editing.")
        old = comment.body
        comment.body = body.strip()
        comment.search_digits = re.sub(r"\D", "", body)
        comment.revision += 1
        comment.full_clean()
        comment.save()
        changes = {"comment_id": comment.pk, "before": old, "after": comment.body}
    else:
        comment = new_comment(actor, customer, body)
        changes = {"comment_id": comment.pk, "after": comment.body}
    audit(
        actor,
        "customer.comment_updated" if comment_id else "customer.comment_added",
        customer,
        changes,
    )
    return comment
