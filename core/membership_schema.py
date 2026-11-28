"""Read accepted financial evidence even when new membership sales are paused."""

from django.conf import settings
from django.db import connection


def available(table):
    if settings.MEMBERSHIP_SALES_ENABLED:
        return True
    # Earlier deployments have no membership tables. Catalog access avoids
    # requiring the runtime role to read or change Django migration history.
    with connection.cursor() as cursor:
        return table in connection.introspection.table_names(cursor)
