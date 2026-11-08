"""Design-only release: no operational staff/customer/booking routes."""

from django.urls import path

from core.design_preview import frozen_page
from core.staging_access import staging_access

urlpatterns = [
    path("staging/access/", staging_access, name="staging_access"),
    path("", frozen_page, {"filename": "index.html"}, name="home"),
    path("<str:filename>", frozen_page),
]
