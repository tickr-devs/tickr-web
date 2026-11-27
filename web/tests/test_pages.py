"""Every page renders in the shared style, in English and Spanish, and the language switch works."""

import re
import time
from html.parser import HTMLParser

import pytest
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    generate_totp_secret,
    hotp_value,
)
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone, translation

from tickrweb.models import Subscriber
from tickrweb.templatetags.devices import device_name

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"

ENTRANCE = [
    "/login",
    "/account/login/code/",
    "/account/password/reset/",
    "/account/password/reset/done/",
    "/account/password/reset/key/1-bad/",
]
SIGNED_IN = [
    "/app",
    "/app/bot",
    "/app/apps",
    "/account/2fa/",
    "/account/sessions/",
    "/account/logout/",
    "/app/people",
    "/app/early-access",
]


def _owner_client(lang):
    call_command("invite", "owner@example.com", "--superuser")
    user = get_user_model().objects.get(email="owner@example.com")
    Authenticator.objects.create(user=user, type=Authenticator.Type.WEBAUTHN, data={"name": "Mac"})
    now = timezone.now()
    Subscriber.objects.create(
        email="eva@example.com", lang="es", signed_up_at=now, confirmed_at=now
    )
    client = Client(headers={"accept-language": lang})
    client.force_login(user)
    session = client.session
    session["account_authentication_methods_user"] = str(user.pk)
    session["account_authentication_methods"] = [{"at": 0, "method": "mfa", "type": "webauthn"}]
    session.save()
    return client


def _check(response, lang, status=200):
    assert response.status_code == status
    html = response.content.decode()
    assert "web/app.css" in html
    assert f'lang="{lang}"' in html
    assert 'action="/app/language"' in html


@pytest.mark.parametrize("lang", ["en", "es"])
@pytest.mark.parametrize("path", ENTRANCE)
def test_entrance_pages_render(path, lang):
    _check(Client(headers={"accept-language": lang}).get(path), lang)


@pytest.mark.parametrize("lang", ["en", "es"])
def test_expired_early_access_link_renders(lang):
    client = Client(headers={"accept-language": lang})
    _check(client.get("/api/waitlist/confirm?t=bad"), lang, status=400)


@pytest.mark.parametrize("lang", ["en", "es"])
@pytest.mark.parametrize("path", SIGNED_IN)
def test_signed_in_pages_render(path, lang):
    _check(_owner_client(lang).get(path), lang)


def test_language_switch_keeps_the_page():
    client = Client()
    response = client.post("/app/language", {"language": "es", "next": "/login"})
    assert response.status_code == 302 and response["Location"] == "/login"
    assert "Inicie sesión en tickr.bot" in client.get("/login").content.decode()


@pytest.mark.parametrize(
    ("agent", "name"),
    [
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/26.1 Safari/605.1.15",
            "Safari on Mac",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 26_1 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) CriOS/142.0 Mobile/15E148 Safari/604.1",
            "Chrome on iPhone",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/142.0 Safari/537.36 Edg/142.0",
            "Edge on Windows",
        ),
        ("", "Unknown browser"),
    ],
)
def test_devices_show_a_readable_browser_name(agent, name):
    with translation.override("en"):
        assert device_name(agent) == name


class _Forms(HTMLParser):
    """The forms of a page: action plus the names and values of their inputs."""

    def __init__(self):
        super().__init__()
        self.forms = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.forms.append({"action": a.get("action") or "", "fields": {}})
        elif tag in ("input", "button") and self.forms and a.get("name"):
            self.forms[-1]["fields"][a["name"]] = a.get("value") or ""


def _form_with(response, field):
    """The page's form that has an input named field, as (action, its other fields)."""
    parser = _Forms()
    parser.feed(response.content.decode())
    form = next(f for f in parser.forms if field in f["fields"])
    return form["action"] or response.request["PATH_INFO"], form["fields"]


def _sign_in_lands_in_the_cabinet(client, response):
    assert response.status_code == 302 and response["Location"] == "/app"
    assert client.get("/app").status_code == 200


def test_emailed_code_sign_in_through_the_pages():
    call_command("invite", "eva@example.com")
    mail.outbox.clear()
    client = Client()
    action, fields = _form_with(client.get("/account/login/code/"), "email")
    response = client.post(action, {**fields, "email": "eva@example.com"}, follow=True)
    code = re.search(r"\b([A-Z0-9]{6})\b", mail.outbox[-1].body).group(1)
    action, fields = _form_with(response, "code")
    _sign_in_lands_in_the_cabinet(client, client.post(action, {**fields, "code": code}))


def test_authenticator_sign_in_through_the_pages():
    call_command("invite", "owner@example.com", "--superuser")
    user = get_user_model().objects.get(email="owner@example.com")
    user.set_password(PASSWORD)
    user.save()
    secret = generate_totp_secret()
    TOTP.activate(user, secret)
    client = Client()
    action, fields = _form_with(client.get("/login"), "password")
    response = client.post(
        action, {**fields, "login": "owner@example.com", "password": PASSWORD}, follow=True
    )
    action, fields = _form_with(response, "code")
    code = format_hotp_value(hotp_value(secret, int(time.time()) // 30))
    _sign_in_lands_in_the_cabinet(client, client.post(action, {**fields, "code": code}))


MANIFEST = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}


@pytest.mark.parametrize("path", ENTRANCE + SIGNED_IN)
def test_pages_render_with_the_production_static_storage(path, tmp_path):
    """Hashed static names as in production: a name missing from the manifest would be a 500."""
    with override_settings(STATIC_ROOT=tmp_path, STORAGES=MANIFEST):
        call_command("collectstatic", interactive=False, verbosity=0)
        client = _owner_client("en") if path in SIGNED_IN else Client()
        html = client.get(path).content.decode()
    assert re.search(r'href="/static/web/app\.[0-9a-f]{12}\.css"', html), path
