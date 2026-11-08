from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .models import (
    AuditEvent,
    Booking,
    BookingQuote,
    CalendarDate,
    Customer,
    MembershipDraft,
    MembershipDraftCycle,
    MembershipPricing,
    PricingPolicy,
    Session,
    SiteSettings,
    WeeklySlot,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Customer)
class CustomerAdmin(ReadOnlyAdmin):
    list_display = ("customer_number", "last_name", "phone", "email")
    search_fields = ("last_name", "phone", "email")


@admin.register(Session)
class SessionAdmin(ReadOnlyAdmin):
    list_display = ("starts_at", "ends_at", "public", "kind", "child_capacity", "total_capacity")


@admin.register(Booking)
class BookingAdmin(ReadOnlyAdmin):
    list_display = ("reference", "customer", "session", "children", "adults", "attendance")


class SettingsInspector(ReadOnlyAdmin):
    exclude = ("staging_password_hash",)


admin.site.register(SiteSettings, SettingsInspector)
admin.site.register(AuditEvent, ReadOnlyAdmin)
admin.site.site_header = "MonkeyDo · TEST MODE"


# Identity changes must pass through owner workflows and session revocation.


class UserInspector(ReadOnlyAdmin):
    exclude = ("password",)


for model in (get_user_model(), Group):
    if admin.site.is_registered(model):
        admin.site.unregister(model)
    admin.site.register(model, UserInspector if model == get_user_model() else ReadOnlyAdmin)

admin.site.register(PricingPolicy, ReadOnlyAdmin)
admin.site.register(BookingQuote, ReadOnlyAdmin)

admin.site.register(CalendarDate, ReadOnlyAdmin)

for model in (MembershipPricing, MembershipDraft, MembershipDraftCycle):
    admin.site.register(model, ReadOnlyAdmin)

admin.site.register(WeeklySlot, ReadOnlyAdmin)
