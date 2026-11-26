"""URLs. Public marketing pages are static files served by Caddy; Django owns only
/login, /account/, /app and /api/ (see web/README.md)."""

from allauth.account.views import login
from django.contrib import admin
from django.urls import include, path

from . import views, waitlist

urlpatterns = [
    path("account/", include("allauth.urls")),
    # After allauth's URLs, so that reverse("account_login") gives /login.
    path("login", login, name="account_login"),
    path("app", views.cabinet, name="cabinet"),
    path("app/early-access", views.early_access, name="early_access"),
    path("app/people", views.people, name="people"),
    path("app/people/<int:pk>/role", views.set_role, name="set_role"),
    path("app/admin/", admin.site.urls),
    path("api/healthz", views.healthz, name="healthz"),
    path("api/waitlist", waitlist.join, name="waitlist_join"),
    path("api/waitlist/confirm", waitlist.confirm, name="waitlist_confirm"),
    path("api/waitlist/unsubscribe", waitlist.unsubscribe, name="waitlist_unsubscribe"),
]
