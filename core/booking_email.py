"""Session-scoped completion-page email correction, never a public customer editor."""

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from .booking_completion import enabled
from .communications.content import booking_confirmation
from .communications.models import MessageDelivery
from .communications.services import enqueue
from .customers import historical_email_customers, new_comment, public_duplicate_email_message
from .models import AuditEvent, Booking, Customer, OwnerNotice
from .payments.ledger import lock_request
from .public_booking import assert_flow


@transaction.atomic
def correct_email(*, flow, email, version, request_key):
    enabled()
    assert_flow(flow)
    if flow.get("stage") != "done":
        raise ValidationError("Return to your booking completion page.")
    key = lock_request(request_key)
    booking = Booking.objects.select_related("customer").get(
        pk=flow.get("booking_id"),
        creation_key=flow["key"],
        source="customer_test",
        workflow="integrated_v1",
    )
    customer = Customer.objects.select_for_update().get(pk=booking.customer_id)
    email = email.strip().lower()
    validate_email(email)
    dedupe = f"public-email-correction:{booking.pk}:{key}"
    previous = MessageDelivery.objects.filter(dedupe_key=dedupe).first()
    if previous:
        if previous.booking_id != booking.pk or previous.recipient != email:
            raise ValidationError("This request already identifies a different email correction.")
        return previous
    if customer.revision != version:
        raise ValidationError("Your profile changed. Reload this page before updating your email.")
    if Customer.objects.exclude(pk=customer.pk).filter(email__iexact=email).exists():
        raise ValidationError(public_duplicate_email_message(email))
    if customer.email != email:
        old = customer.email
        historical = list(
            historical_email_customers(email, customer.pk).values_list("pk", flat=True)
        )
        if customer.previous_email:
            comment = new_comment(
                None, customer, "Previous email archived: " + customer.previous_email, system=True
            )
            AuditEvent.objects.create(
                action="customer.email_history_archived",
                record_type="customer",
                record_id=str(customer.pk),
                changes={"comment_id": comment.pk, "email": customer.previous_email},
            )
        customer.previous_email, customer.email = old, email
        customer.revision += 1
        customer.full_clean()
        customer.save(update_fields=["previous_email", "email", "revision"])
        AuditEvent.objects.create(
            action="customer.updated",
            record_type="customer",
            record_id=str(customer.pk),
            changes={
                "email": {"before": old, "after": email},
                "source": "public_booking_completion",
            },
        )
        if historical:
            OwnerNotice.objects.create(
                customer=customer,
                subject="Email address reused from customer history",
                details={"email": email, "previous_customer_ids": historical},
            )
    booking.customer = customer
    return enqueue(
        key=dedupe,
        kind="booking_confirmation",
        recipient=email,
        subject="Your Monkey Do adventure is booked!",
        text=booking_confirmation(booking),
        booking=booking,
        customer=customer,
    )
