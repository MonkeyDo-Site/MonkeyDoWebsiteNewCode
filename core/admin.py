from django.contrib import admin

from .models import AuditEvent, Booking, Customer, Session, SiteSettings


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


admin.site.register(SiteSettings, ReadOnlyAdmin)
admin.site.register(AuditEvent, ReadOnlyAdmin)
admin.site.site_header = "MonkeyDo · TEST MODE"
