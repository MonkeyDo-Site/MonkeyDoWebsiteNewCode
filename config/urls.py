from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from core import views

urlpatterns = [
    path("", views.page, name="home"),
    path("about/", views.page, {"name": "about"}, name="about"),
    path("memberships-clubs-parties/", views.page, {"name": "programs"}, name="programs"),
    path("contact/", views.page, {"name": "contact"}, name="contact"),
    path("book/", views.schedule, name="schedule"),
    path("staff/today/", views.today, name="today"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("health/", views.health, name="health"),
]
