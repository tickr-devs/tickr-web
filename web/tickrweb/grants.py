"""The Mac and iPhone apps sign in with native screens and get a grant the bot accepts.

The apps use allauth's headless JSON API for the "app" client under /api/auth/app/v1/ (every way
in the site offers: passkey, email + password, a code by email, then TOTP or a passkey as the
second step), holding the session in the X-Session-Token header. Then:

POST /api/app/bot-grant {client_id, resource} with X-Session-Token returns {grant, expires_in,
email (for "Signed in as …")}; the grant is a 60-second RS256
JWT, the bot grant: iss https://tickr.bot, aud [BOT_API_AUDIENCE], sub = account id, client_id,
iat, exp, jti, scope "bot", token_use "access", header kid. The bot checks it offline with the
pinned public key (GET /api/app/grant-key.pem) and issues its own device token; tickr.bot never
talks to the bot. The app then signs out (DELETE /api/auth/app/v1/auth/session).

Only an admin whose session was signed in with a passkey or an authenticator app gets a grant
(the same gate as the cabinet's admin sections), and every grant is emailed to all admins.

This module uses allauth.headless.internal.sessionkit (not public API): allauth is pinned below
the next major version, and tests/test_app_signin.py checks the gate through a real headless
sign-in, so an upgrade that changes the session cannot pass silently.
"""

import base64
import hashlib
import json
import logging
import time
import uuid
from types import SimpleNamespace

import jwt
from allauth.headless.internal.sessionkit import authenticate_by_x_session_token
from cryptography.hazmat.primitives import serialization
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone, translation
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .admin_site import signed_in_with_a_strong_factor
from .mail import failure_summary
from .roles import admins, is_admin

log = logging.getLogger(__name__)

# The apps that may ask for a grant (their bundle ids end in .ios and .mac).
CLIENT_IDS = {"tickr-ios", "tickr-mac"}
# The only scope a grant carries: reach the bot API.
BOT_SCOPE = "bot"
# How each app is named in the notice email.
APP_NAMES = {"tickr-ios": "the iPhone/iPad app", "tickr-mac": "the Mac app"}


def _private_key():
    return serialization.load_pem_private_key(settings.BOT_GRANT_PRIVATE_KEY.encode(), None)


def public_key_pem() -> bytes:
    return (
        _private_key()
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )


def key_id() -> str:
    """RFC 7638 thumbprint of the public key, so the bot can tell keys apart after a rotation."""
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_private_key().public_key()))
    canonical = json.dumps({k: jwk[k] for k in ("e", "kty", "n")}, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _refuse(code: str, status: int) -> JsonResponse:
    return JsonResponse({"error": code}, status=status)


@csrf_exempt  # the apps hold no cookies; the X-Session-Token header is the key
@require_POST
def bot_grant(request):
    signed_in = authenticate_by_x_session_token(request.headers.get("X-Session-Token", ""))
    if signed_in is None or signed_in.user is None or not signed_in.user.is_authenticated:
        return _refuse("not_signed_in", 401)
    try:
        body = json.loads(request.body)
    except ValueError:
        return _refuse("invalid_request", 400)
    if not isinstance(body, dict):
        return _refuse("invalid_request", 400)
    client_id, resource = body.get("client_id"), body.get("resource")
    if client_id not in CLIENT_IDS:
        return _refuse("unknown_client", 400)
    if resource != settings.BOT_API_AUDIENCE:
        return _refuse("unknown_resource", 400)
    user = signed_in.user
    if not is_admin(user):
        return _refuse("not_allowed", 403)
    if not signed_in_with_a_strong_factor(SimpleNamespace(session=signed_in.session, user=user)):
        return _refuse("needs_passkey_or_authenticator", 403)
    now = int(time.time())
    claims = {
        "iss": f"https://{settings.SITE_HOST}",
        "aud": [settings.BOT_API_AUDIENCE],
        "sub": str(user.pk),
        "client_id": client_id,
        "iat": now,
        "exp": now + settings.BOT_GRANT_SECONDS,
        "jti": uuid.uuid4().hex,
        "scope": BOT_SCOPE,
        "token_use": "access",
    }
    grant = jwt.encode(claims, _private_key(), algorithm="RS256", headers={"kid": key_id()})
    _tell_admins(user.email, client_id)
    response = JsonResponse(
        {"grant": grant, "expires_in": settings.BOT_GRANT_SECONDS, "email": user.email}
    )
    response["Cache-Control"] = "no-store"
    return response


def _tell_admins(email: str, client_id: str) -> None:
    """Every grant is emailed to all admins: the key is the bot's trust anchor, so a grant nobody
    expected must be seen. A mail failure is logged and does not stop the sign-in (the bot also
    alerts on every new device)."""
    context = {
        "email": email,
        "app": APP_NAMES[client_id],
        "when": timezone.localtime().strftime("%b %d, %H:%M"),
        "security_url": f"https://{settings.SITE_HOST}/account/2fa/",
    }
    try:
        with translation.override("en"):
            subject = render_to_string("grants/issued_subject.txt", context).strip()
            body = render_to_string("grants/issued_body.txt", context)
        recipients = sorted({a.email for a in admins()})
        EmailMultiAlternatives(subject, body, bcc=recipients).send()
    except Exception as error:
        log.error("bot grant notice not sent: %s", failure_summary(error))


@require_GET
def grant_key(request):
    """The public key the bot pins (PEM). Public by design."""
    return HttpResponse(public_key_pem(), content_type="application/x-pem-file")


@require_GET
def apple_app_site_association(request):
    """Lets the apps use passkeys for tickr.bot (Associated Domains, webcredentials)."""
    apps = [f"{settings.APPLE_TEAM_ID}.{bundle}" for bundle in settings.APPLE_APP_BUNDLE_IDS]
    return JsonResponse({"webcredentials": {"apps": apps}})
