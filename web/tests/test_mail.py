"""The site's emails in the approved design: an HTML version beside the plain text, in the
reader's language, with images that exist and no raw links outside the one button."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from tickrweb.invites import send_invitation
from tickrweb.models import Subscriber
from tickrweb.waitlist import send_confirmation

pytestmark = pytest.mark.django_db

MAIL_IMAGES = Path(settings.BASE_DIR) / "tickrweb/static/web/mail"


@pytest.fixture(autouse=True)
def _no_rate_history():
    cache.clear()  # earlier tests' code and reset requests count against the same limits
    yield
    cache.clear()


def _html(message) -> str:
    [(html, kind)] = message.alternatives
    assert kind == "text/html"
    return html


def _check_design(html: str) -> None:
    images = re.findall(r'src="([^"]+)"', html)
    prefix = f"https://{settings.SITE_HOST}/static/web/mail/"
    assert images and all(src.startswith(prefix) for src in images)
    for src in images:
        assert (MAIL_IMAGES / src.removeprefix(prefix)).is_file(), src
    assert "wordmark-light.png" in html and "wordmark-dark.png" in html
    # Links only as link targets, never as visible text.
    visible = re.sub(r"<[^>]+>", " ", html)
    assert "https://" not in visible


def test_sign_in_code_email(client):
    call_command("invite", "owner@example.com")
    client.post(reverse("account_request_login_code"), {"email": "owner@example.com"})
    [message] = mail.outbox
    code = re.search(r"^(\d{6})$", message.body, re.MULTILINE).group(1)
    assert message.subject == "Your sign-in code"  # the code never shows on a locked screen
    assert code not in message.subject
    html = _html(message)
    _check_design(html)
    assert code in html and "key-light.png" in html
    minutes = settings.ACCOUNT_LOGIN_BY_CODE_TIMEOUT // 60
    assert f"The code works for {minutes} minutes." in html


def test_sign_in_code_email_in_spanish(client):
    call_command("invite", "owner@example.com")
    client.post(
        reverse("account_request_login_code"),
        {"email": "owner@example.com"},
        HTTP_ACCEPT_LANGUAGE="es",
    )
    [message] = mail.outbox
    assert message.subject == "Su código para entrar"
    assert 'lang="es"' in _html(message) and "Escríbalo" in message.body


def test_password_reset_email(client):
    call_command("invite", "owner@example.com")
    client.post(reverse("account_reset_password"), {"email": "owner@example.com"})
    [message] = mail.outbox
    assert message.subject == "Reset your password"
    html = _html(message)
    _check_design(html)
    link = re.search(r'class="btn" href="([^"]+)"', html).group(1)
    assert "/account/password/reset/key/" in link and link in message.body


def test_invitation_email_in_spanish():
    send_invitation("new@example.com", "es")
    [message] = mail.outbox
    assert message.subject == "Su cuenta de tickr.bot está lista"
    html = _html(message)
    _check_design(html)
    assert "Lo invitamos a tickr.bot" in html and "star-light.png" in html


def test_waitlist_email_has_the_button_and_the_removal_link():
    now = timezone.now()
    subscriber = Subscriber.objects.create(email="a@example.com", lang="en", signed_up_at=now)
    send_confirmation(subscriber)
    [message] = mail.outbox
    html = _html(message)
    _check_design(html)
    days = settings.WAITLIST_CONFIRM_MAX_AGE_SECONDS // (24 * 60 * 60)
    assert f"deleted in {days} days, or" in html
    targets = re.findall(r'href="([^"]+)"', html)
    assert any("/api/waitlist/confirm?t=" in t for t in targets)
    assert any("/api/waitlist/unsubscribe?t=" in t for t in targets)


def test_admin_notices():
    from tickrweb.grants import _tell_admins
    from tickrweb.roles import _notify

    call_command("invite", "owner@example.com", "--superuser")
    _tell_admins("owner@example.com", "tickr-mac")
    _notify(["owner@example.com"], "anna@example.com", True, "owner@example.com")
    grant, role = mail.outbox
    assert grant.subject == "New sign-in to the bot from Mac"
    assert role.subject == "anna@example.com is now an admin"
    for message in (grant, role):
        _check_design(_html(message))
    assert reverse("usersessions_list") in _html(grant)
