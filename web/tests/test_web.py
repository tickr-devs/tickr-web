"""The web app's sign-in, closed sign-up, invitations and security headers."""

import re

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _invite(email="owner@example.com", *flags):
    call_command("invite", email, *flags)
    return get_user_model().objects.get(email=email)


def _sign_in_with(client, user, *records):
    """Signs `user` in, with allauth's record of how the session was authenticated."""
    client.force_login(user)
    session = client.session
    session["account_authentication_methods_user"] = str(user.pk)
    session["account_authentication_methods"] = [{"at": 0, **r} for r in records]
    session.save()


def test_health_answers_without_sign_in(client):
    response = client.get("/api/healthz")
    assert response.status_code == 200
    assert response.content == b"ok"


def test_login_lives_at_slash_login(client):
    assert reverse("account_login") == "/login"
    response = client.get("/login")
    assert response.status_code == 200
    assert b'name="login"' in response.content


def test_cabinet_needs_sign_in(client):
    response = client.get("/app")
    assert response.status_code == 302
    assert response["Location"].startswith("/login?next=/app")


def test_admin_uses_the_site_sign_in(client):
    response = client.get("/app/admin/", follow=True)
    assert response.request["PATH_INFO"] == "/login"


def test_admin_never_serves_its_own_password_form(client):
    _sign_in_with(client, _invite("member@example.com"), {"method": "password"})
    response = client.get("/app/admin/login/")
    assert response.status_code == 403
    assert b'name="password"' not in response.content
    response = client.post(
        "/app/admin/login/", {"username": "owner@example.com", "password": "guess"}
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "record",
    [
        {"method": "code"},
        {"method": "password"},
        {"method": "mfa", "type": "recovery_codes"},
    ],
)
def test_admin_refuses_staff_without_a_passkey_or_authenticator(client, record):
    _sign_in_with(client, _invite("owner@example.com", "--superuser"), record)
    assert client.get("/app/admin/").status_code == 302
    assert client.get("/app/admin/login/").status_code == 403


@pytest.mark.parametrize("factor", ["webauthn", "totp"])
def test_admin_opens_for_staff_signed_in_with_a_strong_factor(client, factor):
    _sign_in_with(
        client, _invite("owner@example.com", "--staff"), {"method": "mfa", "type": factor}
    )
    assert client.get("/app/admin/").status_code == 200


def test_admin_refuses_a_strong_factor_without_staff(client):
    _sign_in_with(client, _invite("member@example.com"), {"method": "mfa", "type": "webauthn"})
    assert client.get("/app/admin/login/").status_code == 403


def test_staff_and_superuser_are_separate_flags():
    staff = _invite("staff@example.com", "--staff")
    assert staff.is_staff and not staff.is_superuser
    owner = _invite("owner@example.com", "--superuser")
    assert owner.is_staff and owner.is_superuser


def test_public_sign_up_is_closed(client):
    response = client.post(
        "/account/signup/", {"email": "x@example.com", "password1": "a-long-enough-password-1"}
    )
    assert not get_user_model().objects.filter(email="x@example.com").exists()
    assert response.status_code == 200


def test_invite_makes_a_verified_account_without_password():
    user = _invite()
    assert not user.has_usable_password()
    assert EmailAddress.objects.get(user=user).verified


def test_invite_refuses_a_second_account_for_one_address():
    _invite()
    with pytest.raises(CommandError):
        call_command("invite", "OWNER@example.com")


def test_invite_refuses_what_is_not_an_address():
    with pytest.raises(CommandError):
        call_command("invite", "not-an-address")


def test_invited_owner_signs_in_with_an_emailed_code(client):
    _invite()
    response = client.post(reverse("account_request_login_code"), {"email": "owner@example.com"})
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    code = re.search(r"^([A-Z0-9]{4}-[A-Z0-9]{4})$", mail.outbox[0].body, re.MULTILINE).group(1)
    response = client.post(reverse("account_confirm_login_code"), {"code": code})
    assert response.status_code == 302
    assert client.get("/app").status_code == 200


def test_password_sign_in_and_minimum_length(client):
    user = _invite()
    user.set_password("correct horse battery staple")
    user.save()
    response = client.post(
        "/login", {"login": "owner@example.com", "password": "correct horse battery staple"}
    )
    assert response.status_code == 302
    response = client.post(
        reverse("account_change_password"),
        {
            "oldpassword": "correct horse battery staple",
            "password1": "short-pass1",
            "password2": "short-pass1",
        },
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("correct horse battery staple")


def test_cabinet_shows_the_account_and_is_not_cached(client):
    user = _invite()
    client.force_login(user)
    response = client.get("/app")
    assert b"owner@example.com" in response.content
    assert b"Sample data" not in response.content
    assert response.context["device_count"] == 1
    assert response.context["passkey_count"] == 0
    assert response["Cache-Control"] == "no-store"


def test_security_headers(client):
    response = client.get("/login")
    csp = response["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Referrer-Policy"] == "same-origin"


def test_spanish_pages(client):
    response = client.get("/login", HTTP_ACCEPT_LANGUAGE="es")
    assert b'lang="es"' in response.content


def test_spanish_cabinet(client):
    client.force_login(_invite())
    response = client.get("/app", HTTP_ACCEPT_LANGUAGE="es")
    assert "Cerrar sesión" in response.content.decode()


def _ask_code(email, forwarded_for):
    """One request from a fresh browser session (a pending code would short-cut the form)."""
    return Client().post(
        reverse("account_request_login_code"),
        {"email": email},
        HTTP_X_FORWARDED_FOR=forwarded_for,
    )


def test_per_ip_limits_count_each_visitor_behind_the_proxy(settings):
    """Caddy sends the visitor's address as the last X-Forwarded-For entry: one visitor's
    requests must not use up another's limit, and a forged first entry changes nothing."""
    settings.ACCOUNT_RATE_LIMITS = {**settings.ACCOUNT_RATE_LIMITS, "request_login_code": "3/5m/ip"}
    for n in range(3):
        assert _ask_code(f"a{n}@example.com", "203.0.113.1").status_code == 302
    assert _ask_code("a3@example.com", "203.0.113.1").status_code == 200  # form error
    assert _ask_code("a4@example.com", "198.51.100.7, 203.0.113.1").status_code == 200
    assert _ask_code("b0@example.com", "203.0.113.2").status_code == 302


SIGNED_IN_PAGES = [
    "/app",
    "/account/2fa/",
    "/account/password/change/",
    "/account/password/reset/",
    "/account/sessions/",
    "/account/2fa/webauthn/add/",
    "/account/2fa/totp/activate/",
    "/account/reauthenticate/",
    "/account/reauthenticate/code/",
]


@pytest.mark.parametrize("path", SIGNED_IN_PAGES)
def test_every_signed_in_page_opens(client, path):
    owner = _invite("owner@example.com", "--superuser")
    owner.set_password("correct horse battery staple")
    owner.save()
    _sign_in_with(client, owner, {"method": "mfa", "type": "webauthn"})
    response = client.get(path)
    assert response.status_code in {200, 302}, path
    if response.status_code == 302:
        assert client.get(response["Location"]).status_code == 200, path


def test_admin_sections_show_in_the_cabinet_only_for_admins(client):
    _sign_in_with(client, _invite("member@example.com"), {"method": "code"})
    page = client.get("/app").text
    assert "/app/people" not in page and "/app/early-access" not in page
    owner = Client()
    _sign_in_with(
        owner, _invite("owner@example.com", "--superuser"), {"method": "mfa", "type": "webauthn"}
    )
    page = owner.get("/app").text
    assert "/app/people" in page and "/app/early-access" in page
    assert "/app/admin/" not in page
