from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from core import customer_views, dashboard, views
from core.security import ProtectedLoginView

urlpatterns = [
    path("", views.page, name="home"),
    path("about/", views.page, {"name": "about"}, name="about"),
    path("memberships-clubs-parties/", views.page, {"name": "programs"}, name="programs"),
    path("contact/", views.page, {"name": "contact"}, name="contact"),
    path("book/", views.schedule, name="schedule"),
    path("staff/today/", views.today, name="today"),
    path("accounts/login/", ProtectedLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Do not leave the inspector with an unthrottled second password endpoint.
    path("admin/login/", RedirectView.as_view(pattern_name="login", query_string=True)),
    path("admin/", admin.site.urls),
    path("staff/customers/", customer_views.customer_list, name="customers"),
    path("staff/customers/new/", customer_views.customer_create, name="customer_create"),
    path("staff/customers/<int:pk>/", customer_views.customer_detail, name="customer_detail"),
    path("staff/customers/<int:pk>/edit/", customer_views.customer_edit, name="customer_edit"),
    path(
        "staff/customers/<int:pk>/previous-phone/",
        customer_views.previous_phone,
        name="previous_phone",
    ),
    path("staff/customers/<int:pk>/comments/new/", customer_views.comment_edit, name="comment_add"),
    path(
        "staff/customers/<int:pk>/comments/<int:comment_id>/",
        customer_views.comment_edit,
        name="comment_edit",
    ),
    path(
        "staff/customers/<int:pk>/history/",
        customer_views.customer_history,
        name="customer_history",
    ),
    path("staff/dashboard/", dashboard.dashboard, name="dashboard"),
    path("staff/security-alerts/<int:pk>/resolve/", dashboard.resolve_alert, name="resolve_alert"),
    path("health/", views.health, name="health"),
]
