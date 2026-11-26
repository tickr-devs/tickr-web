"""The admin at /app/admin/: staff only, and only in a session signed in with a passkey or an
authenticator app. A password or an emailed code alone is not enough, so control of the owner's
mailbox does not open the admin. Django's own admin login form is never served: it would
check passwords outside allauth's rate limits.
"""

from allauth.account.authentication import get_authentication_records
from django.contrib import admin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render

# allauth's record types for a second factor that is not a mailbox: passkey and authenticator app.
STRONG_FACTORS = {"webauthn", "totp"}


def signed_in_with_a_strong_factor(request) -> bool:
    records = get_authentication_records(request, request.user)
    return any(r.get("method") == "mfa" and r.get("type") in STRONG_FACTORS for r in records)


class TickrAdminSite(admin.AdminSite):
    site_header = "tickr.bot"
    site_title = "tickr.bot admin"

    def has_permission(self, request):
        return (
            request.user.is_active
            and request.user.is_staff
            and signed_in_with_a_strong_factor(request)
        )

    def login(self, request, extra_context=None):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), "/login")
        if self.has_permission(request):
            return redirect("admin:index")
        return render(request, "admin_refused.html", status=403)
