"""The apps' sign-in: authorization code + PKCE for tickr-ios/tickr-mac, a bot grant out."""

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.django_db

BOT = "https://bot.tickr.bot"
REDIRECT = "tickr://signin"
STRONG = {"method": "mfa", "type": "webauthn"}


def _account(email, *flags):
    call_command("invite", email, *flags)
    return get_user_model().objects.get(email=email)


def _client(user, record=STRONG):
    client = Client()
    client.force_login(user)
    session = client.session
    session["account_authentication_methods_user"] = str(user.pk)
    session["account_authentication_methods"] = [{"at": 0, **record}]
    session.save()
    return client


def _pkce():
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _authorize(client, challenge, **extra):
    params = {
        "client_id": "tickr-ios",
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": "bot",
        "state": "s1",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": BOT,
        **extra,
    }
    return client.get("/identity/o/authorize", params)


def _token(code, verifier, **extra):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "client_id": "tickr-ios",
        "redirect_uri": REDIRECT,
        "resource": BOT,
        **extra,
    }
    return Client().post("/identity/o/api/token", data)


def _code(response):
    assert response.status_code == 302, response.content[:300]
    location = urlsplit(response["Location"])
    assert f"{location.scheme}://{location.netloc}" == REDIRECT
    query = parse_qs(location.query)
    assert query["state"] == ["s1"]
    return query["code"][0]


def _public_key():
    keys = Client().get("/.well-known/jwks.json").json()["keys"]
    assert len(keys) == 1
    return jwt.PyJWK(keys[0])


def test_owner_gets_a_bot_grant():
    owner = _account("owner@example.com", "--superuser")
    verifier, challenge = _pkce()
    code = _code(_authorize(_client(owner), challenge))
    response = _token(code, verifier)
    assert response.status_code == 200, response.content
    body = response.json()
    grant = jwt.decode(
        body["access_token"],
        _public_key(),
        algorithms=["RS256"],
        audience=BOT,
        issuer=f"https://{settings.SITE_HOST}",
    )
    assert grant["sub"] == str(owner.pk)
    assert grant["client_id"] == "tickr-ios"
    assert grant["scope"] == "bot"
    assert grant["exp"] - grant["iat"] == settings.IDP_OIDC_ACCESS_TOKEN_EXPIRES_IN
    assert grant["jti"]
    assert "email" not in grant


def test_the_apps_cannot_refresh():
    owner = _account("owner@example.com", "--superuser")
    verifier, challenge = _pkce()
    body = _token(_code(_authorize(_client(owner), challenge)), verifier).json()
    response = Client().post(
        "/identity/o/api/token",
        {
            "grant_type": "refresh_token",
            "refresh_token": body["refresh_token"],
            "client_id": "tickr-ios",
        },
    )
    assert response.status_code in {400, 401}
    assert "access_token" not in response.json()


def test_a_code_works_once():
    owner = _account("owner@example.com", "--superuser")
    verifier, challenge = _pkce()
    code = _code(_authorize(_client(owner), challenge))
    assert _token(code, verifier).status_code == 200
    assert _token(code, verifier).status_code == 400


def test_the_code_needs_the_matching_verifier():
    owner = _account("owner@example.com", "--superuser")
    _, challenge = _pkce()
    code = _code(_authorize(_client(owner), challenge))
    other, _ = _pkce()
    assert _token(code, other).status_code == 400


def test_pkce_is_required():
    owner = _account("owner@example.com", "--superuser")
    response = _client(owner).get(
        "/identity/o/authorize",
        {
            "client_id": "tickr-ios",
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": "bot",
            "state": "s1",
        },
    )
    assert response.status_code == 302
    assert "error=" in response["Location"] and "code=" not in response["Location"]


def test_only_the_registered_redirect_is_used():
    owner = _account("owner@example.com", "--superuser")
    _, challenge = _pkce()
    response = _authorize(_client(owner), challenge, redirect_uri="https://evil.example/cb")
    assert "Location" not in response  # an error page here, never a redirect
    assert b"code=" not in response.content


@pytest.mark.parametrize(
    "flags,record",
    [
        ((), STRONG),  # a member
        (("--staff",), STRONG),  # staff without superuser
        (("--superuser",), {"method": "code"}),  # admin signed in with an emailed code
        (("--superuser",), {"method": "password"}),
    ],
)
def test_only_an_admin_with_a_passkey_or_authenticator_gets_a_code(flags, record):
    user = _account("someone@example.com", *flags)
    _, challenge = _pkce()
    response = _authorize(_client(user, record), challenge)
    assert response.status_code == 403
    assert "Location" not in response


def test_signed_out_people_are_sent_to_sign_in():
    _, challenge = _pkce()
    response = _authorize(Client(), challenge)
    assert response.status_code == 302
    assert response["Location"].startswith("/login?next=")


def test_discovery_names_tickr_bot_as_issuer():
    config = Client().get("/.well-known/openid-configuration").json()
    assert config["issuer"] == f"https://{settings.SITE_HOST}"
    assert config["code_challenge_methods_supported"] == ["S256"]


def test_the_signing_key_is_made_once_and_only_readable_by_its_owner(tmp_path):
    from tickrweb.oidc_key import ensure

    path = tmp_path / "oidc.pem"
    assert ensure(str(path)) is True
    first = path.read_text()
    assert first.startswith("-----BEGIN PRIVATE KEY-----")
    assert path.stat().st_mode & 0o777 == 0o600
    assert ensure(str(path)) is False
    assert path.read_text() == first
