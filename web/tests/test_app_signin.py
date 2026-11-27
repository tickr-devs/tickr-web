"""The apps' native sign-in: allauth headless ("app" client), then a bot grant for the bot API."""

import json
import time

import jwt
import pytest
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    generate_totp_secret,
    hotp_value,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.django_db

API = "/api/auth/app/v1"
BOT = "https://api.tickr.bot"
PASSWORD = "correct horse battery staple"


def _account(email, *flags, totp=False):
    call_command("invite", email, *flags)
    user = get_user_model().objects.get(email=email)
    user.set_password(PASSWORD)
    user.save()
    secret = None
    if totp:
        secret = generate_totp_secret()
        TOTP.activate(user, secret)
    return user, secret


def _post(path, data, token=None):
    headers = {"HTTP_X_SESSION_TOKEN": token} if token else {}
    return Client().post(path, json.dumps(data), content_type="application/json", **headers)


def _totp_now(secret):
    return format_hotp_value(hotp_value(secret, int(time.time()) // 30))


def _sign_in(email, secret=None):
    """Email + password, then the authenticator code when asked. Returns the session token."""
    response = _post(f"{API}/auth/login", {"email": email, "password": PASSWORD})
    body = response.json()
    token = body["meta"]["session_token"]
    if response.status_code == 401:
        flows = {f["id"]: f for f in body["data"]["flows"]}
        assert flows["mfa_authenticate"]["is_pending"]
        response = _post(f"{API}/auth/2fa/authenticate", {"code": _totp_now(secret)}, token)
        body = response.json()
    assert response.status_code == 200, body
    assert body["meta"]["is_authenticated"]
    return body["meta"].get("session_token", token)


def _grant(token, client_id="tickr-ios", resource=BOT):
    return _post("/api/app/bot-grant", {"client_id": client_id, "resource": resource}, token)


def _public_key():
    return Client().get("/api/app/grant-key.pem").content


def test_admin_with_authenticator_gets_a_bot_grant():
    owner, secret = _account("owner@example.com", "--superuser", totp=True)
    response = _grant(_sign_in("owner@example.com", secret))
    assert response.status_code == 200, response.content
    assert response["Cache-Control"] == "no-store"
    body = response.json()
    assert body["expires_in"] == settings.BOT_GRANT_SECONDS
    assert body["email"] == "owner@example.com"
    header = jwt.get_unverified_header(body["grant"])
    assert header["alg"] == "RS256" and header["kid"]
    claims = jwt.decode(
        body["grant"],
        _public_key(),
        algorithms=["RS256"],
        audience=BOT,
        issuer=f"https://{settings.SITE_HOST}",
    )
    assert claims["aud"] == [BOT]
    assert claims["sub"] == str(owner.pk)
    assert claims["client_id"] == "tickr-ios"
    assert claims["scope"] == "bot" and claims["token_use"] == "access"
    assert claims["exp"] - claims["iat"] == settings.BOT_GRANT_SECONDS
    assert claims["jti"]
    assert "email" not in claims
    notice = mail.outbox[-1]
    assert notice.bcc == ["owner@example.com"]
    assert "owner@example.com signed in to the bot from the iPhone/iPad app" in notice.subject


def test_a_failed_notice_does_not_stop_the_sign_in(monkeypatch, caplog):
    def refuse(self, *args, **kwargs):
        raise OSError("mail refused")

    monkeypatch.setattr("tickrweb.grants.EmailMultiAlternatives.send", refuse)
    _, secret = _account("owner@example.com", "--superuser", totp=True)
    assert _grant(_sign_in("owner@example.com", secret)).status_code == 200
    assert "bot grant notice not sent: OSError" in caplog.text


def test_each_grant_has_its_own_id():
    _, secret = _account("owner@example.com", "--superuser", totp=True)
    token = _sign_in("owner@example.com", secret)
    first, second = (
        jwt.decode(_grant(token).json()["grant"], options={"verify_signature": False})
        for _ in range(2)
    )
    assert first["jti"] != second["jti"]


def test_a_password_alone_is_not_enough():
    _account("owner@example.com", "--superuser")
    response = _grant(_sign_in("owner@example.com"))
    assert response.status_code == 403
    assert response.json() == {"error": "needs_passkey_or_authenticator"}


def test_members_get_no_grant():
    _, secret = _account("member@example.com", totp=True)
    response = _grant(_sign_in("member@example.com", secret))
    assert response.status_code == 403
    assert response.json() == {"error": "not_allowed"}


@pytest.mark.parametrize("token", [None, "made-up"])
def test_signed_out_apps_get_no_grant(token):
    assert _grant(token).status_code == 401


def test_signing_out_ends_the_session():
    _, secret = _account("owner@example.com", "--superuser", totp=True)
    token = _sign_in("owner@example.com", secret)
    response = Client().delete(f"{API}/auth/session", HTTP_X_SESSION_TOKEN=token)
    assert response.status_code == 401  # allauth: no longer authenticated
    assert _grant(token).status_code == 401


@pytest.mark.parametrize(
    "client_id,resource,error",
    [
        ("tickr-web", BOT, "unknown_client"),
        ("tickr-ios", "https://evil.example", "unknown_resource"),
        ("tickr-ios", None, "unknown_resource"),
    ],
)
def test_unknown_clients_and_resources_are_refused(client_id, resource, error):
    _, secret = _account("owner@example.com", "--superuser", totp=True)
    response = _grant(_sign_in("owner@example.com", secret), client_id, resource)
    assert response.status_code == 400
    assert response.json() == {"error": error}


def test_the_mac_app_is_a_client_too():
    _, secret = _account("owner@example.com", "--superuser", totp=True)
    grant = _grant(_sign_in("owner@example.com", secret), "tickr-mac").json()["grant"]
    assert jwt.decode(grant, options={"verify_signature": False})["client_id"] == "tickr-mac"


def test_sign_in_by_emailed_code_is_offered():
    _account("owner@example.com", "--superuser")
    response = _post(f"{API}/auth/code/request", {"email": "owner@example.com"})
    assert response.status_code == 401
    flows = {f["id"]: f for f in response.json()["data"]["flows"]}
    assert flows["login_by_code"]["is_pending"]
    assert len(mail.outbox) == 1


def test_config_lists_the_ways_in():
    config = Client().get(f"{API}/config").json()["data"]
    assert config["account"]["login_by_code_enabled"] is True
    assert set(config["mfa"]["supported_types"]) == {"webauthn", "totp", "recovery_codes"}
    assert config["mfa"]["passkey_login_enabled"] is True


def test_apple_passkey_file():
    body = Client().get("/.well-known/apple-app-site-association").json()
    assert body == {
        "webcredentials": {"apps": ["2C66ZTA2N4.bot.tickr.ios", "2C66ZTA2N4.bot.tickr.mac"]}
    }


def test_password_reset_from_the_app_mails_a_link_to_the_site():
    _account("owner@example.com", "--superuser")
    response = _post(f"{API}/auth/password/request", {"email": "owner@example.com"})
    assert response.status_code == 200
    assert "/account/password/reset/key/" in mail.outbox[0].body


def test_the_signing_key_is_made_once_and_only_readable_by_its_owner(tmp_path):
    from tickrweb.grant_key import ensure

    path = tmp_path / "grant.pem"
    assert ensure(str(path)) is True
    first = path.read_text()
    assert first.startswith("-----BEGIN PRIVATE KEY-----")
    assert path.stat().st_mode & 0o777 == 0o600
    assert ensure(str(path)) is False
    assert path.read_text() == first


def test_a_crash_mid_write_leaves_no_key_behind(tmp_path, monkeypatch):
    from tickrweb import grant_key

    def crash():
        raise OSError("disk full")

    monkeypatch.setattr(grant_key, "new_private_key_pem", crash)
    path = tmp_path / "grant.pem"
    with pytest.raises(OSError):
        grant_key.ensure(str(path))
    assert list(tmp_path.iterdir()) == []


def test_ses_calls_give_up_before_a_grant_expires():
    config = settings.AWS_SES_CONFIG
    attempts = config.retries["total_max_attempts"]
    calls_per_email = 2  # django-ses v2: get_account, then send_email
    worst = calls_per_email * attempts * (config.connect_timeout + config.read_timeout)
    assert worst < settings.BOT_GRANT_SECONDS
