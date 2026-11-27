"""The early-access list: double opt-in, limits, privacy promises, unsubscribe, import."""

import hashlib
import re
from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from tickrweb.models import Subscriber

pytestmark = pytest.mark.django_db
ORIGIN = "https://testserver"


@pytest.fixture(autouse=True)
def _fresh_limits():
    cache.clear()


def _join(client, email="a@example.com", lang="en", origin=ORIGIN, ip="203.0.113.9", **extra):
    data = {"email": email, "lang": lang, "website": "", **extra}
    return client.post(
        "/api/waitlist",
        data,
        HTTP_ORIGIN=origin,
        HTTP_ACCEPT="application/json",
        HTTP_X_FORWARDED_FOR=ip,
    )


def _links(message):
    return re.findall(r"https://testserver(/api/waitlist/\S+)", message.body)


def test_join_sends_one_confirmation_and_stores_only_the_promised_fields(client):
    response = _join(client)
    assert response.json() == {"status": "confirm"}
    row = Subscriber.objects.get()
    assert row.confirmed_at is None
    assert {f.name for f in Subscriber._meta.fields} == {
        "id",
        "email",
        "lang",
        "signed_up_at",
        "confirmed_at",
    }
    assert len(mail.outbox) == 1
    assert "List-Unsubscribe" in mail.outbox[0].extra_headers


def test_opening_the_link_only_asks_and_the_button_confirms(client):
    _join(client)
    confirm, _ = _links(mail.outbox[0])
    response = client.get(confirm)
    assert response.status_code == 200
    assert Subscriber.objects.get().confirmed_at is None
    client.post(confirm)
    assert Subscriber.objects.get().confirmed_at is not None


def test_unsubscribe_asks_first_then_deletes(client):
    _join(client)
    _, leave = _links(mail.outbox[0])
    assert client.get(leave).status_code == 200
    assert Subscriber.objects.exists()
    client.post(leave)
    assert not Subscriber.objects.exists()


def test_a_forged_link_does_nothing(client):
    _join(client)
    assert client.post("/api/waitlist/confirm?t=forged").status_code == 400
    assert client.post("/api/waitlist/unsubscribe?t=forged").status_code == 400
    assert Subscriber.objects.get().confirmed_at is None


def test_a_confirmed_address_is_not_revealed_or_mailed_again(client):
    _join(client)
    client.post(_links(mail.outbox[0])[0])
    assert _join(client).json() == {"status": "confirm"}
    assert len(mail.outbox) == 1


def test_invalid_address(client):
    assert _join(client, email="nope").json() == {"status": "invalid"}
    assert not Subscriber.objects.exists()


def test_honeypot_says_ok_and_does_nothing(client):
    assert _join(client, website="http://spam").json() == {"status": "ok"}
    assert not Subscriber.objects.exists() and not mail.outbox


def test_other_origins_are_refused(client):
    assert _join(client, origin="https://evil.example").status_code == 403
    assert _join(client, origin="null").status_code == 403


def test_per_ip_limit(client, settings):
    for n in range(settings.WAITLIST_PER_IP):
        assert _join(client, email=f"a{n}@example.com").json()["status"] == "confirm"
    assert _join(client, email="late@example.com").json() == {"status": "rate"}


def test_spanish_confirmation(client):
    _join(client, lang="es")
    assert Subscriber.objects.get().lang == "es"
    assert mail.outbox[0].subject == "Confirme su lugar en la lista de tickr.bot"


def test_prune_deletes_only_expired_unconfirmed(settings):
    old = timezone.now() - timedelta(seconds=settings.WAITLIST_CONFIRM_MAX_AGE_SECONDS + 1)
    Subscriber.objects.create(email="old@example.com", lang="en", signed_up_at=old)
    Subscriber.objects.create(
        email="kept@example.com", lang="en", signed_up_at=old, confirmed_at=old
    )
    Subscriber.objects.create(email="new@example.com", lang="en", signed_up_at=timezone.now())
    call_command("prune_waitlist")
    assert set(Subscriber.objects.values_list("email", flat=True)) == {
        "kept@example.com",
        "new@example.com",
    }


def test_import_the_old_csv(tmp_path):
    path = tmp_path / "emails.csv"
    path.write_text(
        "2026-11-25T19:30:00Z,One@Example.com,en\n"
        "2026-11-25T19:31:00Z,two@example.com,es\n"
        "broken line\n"
        "2026-11-25T19:32:00Z,one@example.com,en\n",
        "utf-8",
    )
    call_command("import_waitlist", str(path))
    assert dict(Subscriber.objects.values_list("email", "lang")) == {
        "one@example.com": "en",
        "two@example.com": "es",
    }
    assert len(mail.outbox) == 2


def test_one_confirmation_per_address_per_cooldown_from_any_ip(client, settings):
    for n in range(3):
        response = _join(client, ip=f"203.0.113.{n}")
        assert response.json() == {"status": "confirm"}
    assert len(mail.outbox) == 1
    cache.delete("waitlist:sent:" + hashlib.sha256(b"a@example.com").hexdigest())
    _join(client)
    assert len(mail.outbox) == 2


def test_a_resent_link_restarts_the_row_clock(client):
    _join(client)
    old = timezone.now() - timedelta(days=6)
    Subscriber.objects.update(signed_up_at=old)
    cache.clear()
    _join(client)
    assert Subscriber.objects.get().signed_up_at > old


def test_a_failed_send_is_logged_without_the_address(client, monkeypatch, caplog):
    class Refused(Exception):
        response = {"Error": {"Code": "MessageRejected", "Message": "failed: a@example.com"}}

    def refuse(*args, **kwargs):
        raise Refused

    monkeypatch.setattr("tickrweb.waitlist.EmailMultiAlternatives.send", refuse)
    response = _join(client)
    assert response.json() == {"status": "error"}
    assert "Refused MessageRejected" in caplog.text
    assert "a@example.com" not in caplog.text


def test_an_access_error_is_logged_with_its_message(client, monkeypatch, caplog):
    class Denied(Exception):
        response = {"Error": {"Code": "AccessDeniedException", "Message": "no ses:GetAccount"}}

    def deny(*args, **kwargs):
        raise Denied

    monkeypatch.setattr("tickrweb.waitlist.EmailMultiAlternatives.send", deny)
    _join(client)
    assert "no ses:GetAccount" in caplog.text


def test_an_access_error_naming_a_recipient_is_logged_without_it(client, monkeypatch, caplog):
    message = (
        "User: arn:aws:sts::123456789012:assumed-role/tickr-web/i-0abc is not authorized to "
        "perform: ses:SendEmail on resource: "
        "arn:aws:ses:us-east-1:123456789012:identity/a@example.com because no identity-based "
        "policy allows the ses:SendEmail action"
    )

    class Denied(Exception):
        response = {"Error": {"Code": "AccessDeniedException", "Message": message}}

    def deny(*args, **kwargs):
        raise Denied

    monkeypatch.setattr("tickrweb.waitlist.EmailMultiAlternatives.send", deny)
    _join(client)
    assert "identity/<address> because" in caplog.text
    assert "ses:SendEmail on resource" in caplog.text
    assert "a@example.com" not in caplog.text
