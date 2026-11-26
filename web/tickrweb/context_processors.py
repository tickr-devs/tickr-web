"""What every signed-in page's frame needs: the side navigation and whether the admin parts show."""

from .roles import admin_session, is_admin

# (url prefix, label key) of the side navigation; admin items only for an admin.
_MEMBER = [("/app", "overview"), ("/account/2fa/", "security"), ("/account/sessions/", "devices")]
_ADMIN = [("/app/early-access", "early_access"), ("/app/people", "people")]


def frame(request):
    if not request.user.is_authenticated:
        return {}
    path = request.path
    items = _MEMBER + (_ADMIN if is_admin(request.user) else [])
    # The longest matching prefix wins, so /app/people is not also "Overview".
    active = max(
        (p for p, _ in items if path == p or path.startswith(p.rstrip("/") + "/")),
        key=len,
        default="",
    )
    if path.startswith("/account/password") or path.startswith("/account/reauthenticate"):
        active = "/account/2fa/"
    return {
        "nav_active": active,
        "nav_admin": is_admin(request.user),
        "admin_session": admin_session(request),
    }
