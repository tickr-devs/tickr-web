"""URLs. Public marketing pages are static files served by Caddy; Django owns only
/login, /account/, /app, /api/ and /.well-known/apple-app-site-association (see web/README.md)."""

from allauth.account.views import login
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language

from . import grants, views, waitlist

urlpatterns = [
    path("account/", include("allauth.urls")),
    # After allauth's URLs, so that reverse("account_login") gives /login.
    path("login", login, name="account_login"),
    path("app", views.cabinet, name="cabinet"),
    path("app/early-access", views.early_access, name="early_access"),
    path("app/people", views.people, name="people"),
    path("app/people/<int:pk>/role", views.set_role, name="set_role"),
    # The EN/ES switch on every page (a POST form; under /app so the proxy sends it here).
    path("app/language", set_language, name="set_language"),
    path("app/admin/", admin.site.urls),
    path("api/healthz", views.healthz, name="healthz"),
    path("api/waitlist", waitlist.join, name="waitlist_join"),
    path("api/waitlist/confirm", waitlist.confirm, name="waitlist_confirm"),
    path("api/waitlist/unsubscribe", waitlist.unsubscribe, name="waitlist_unsubscribe"),
    # The apps' native sign-in (tickrweb/grants.py): allauth's headless API, then a bot grant.
    path("api/auth/", include("allauth.headless.urls")),
    path("api/app/bot-grant", grants.bot_grant, name="bot_grant"),
    path("api/app/grant-key.pem", grants.grant_key, name="grant_key"),
    path(
        ".well-known/apple-app-site-association",
        grants.apple_app_site_association,
        name="apple_app_site_association",
    ),
]
