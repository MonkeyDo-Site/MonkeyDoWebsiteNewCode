from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def staff_permission(permission):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_active or not user.is_staff or not user.has_perm(permission):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def require_actor(actor, permission, owner=False):
    if (
        not actor.is_active
        or not actor.is_staff
        or not actor.has_perm(permission)
        or (owner and not actor.is_superuser)
    ):
        raise PermissionDenied
