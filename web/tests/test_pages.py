"""Every page renders in the shared style, in English and Spanish, and the language switch works."""

import pytest
from allauth.mfa.models import Authenticator
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.utils import timezone, translation

from tickrweb.models import Subscriber
from tickrweb.templatetags.devices import device_name

pytestmark = pytest.mark.django_db

ENTRANCE = [
    "/login",
    "/account/login/code/",
    "/account/password/reset/",
    "/account/password/reset/done/",
    "/account/password/reset/key/1-bad/",
]
SIGNED_IN = [
    "/app",
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
