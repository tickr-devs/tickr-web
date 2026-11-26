"""Inviting early-access addresses from the admin: one account and one email per address."""

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from tickrweb.models import Subscriber

pytestmark = pytest.mark.django_db

CHANGELIST = "/app/admin/tickrweb/subscriber/"


def _admin(client):
    call_command("invite", "owner@example.com", "--superuser")
    owner = get_user_model().objects.get(email="owner@example.com")
    client.force_login(owner)
    session = client.session
    session["account_authentication_methods_user"] = str(owner.pk)
    session["account_authentication_methods"] = [{"at": 0, "method": "mfa", "type": "webauthn"}]
    session.save()


def _subscriber(email, lang="en", confirmed=True):
    now = timezone.now()
    return Subscriber.objects.create(
        email=email, lang=lang, signed_up_at=now, confirmed_at=now if confirmed else None
    )


def _invite(client, *subscribers):
    return client.post(
        CHANGELIST,
        {"action": "invite_selected", "_selected_action": [s.pk for s in subscribers]},
        follow=True,
    )


def test_invites_a_confirmed_address_once(client):
    _admin(client)
    ana = _subscriber("ana@example.com")
    response = _invite(client, ana)
    assert "Invited 1 address." in response.text
    address = EmailAddress.objects.get(email="ana@example.com")
    assert address.verified
    assert not address.user.has_usable_password()
    assert not address.user.is_staff
    assert [m.to for m in mail.outbox] == [["ana@example.com"]]
    assert f"https://{settings.SITE_HOST}/login" in mail.outbox[0].body

    response = _invite(client, ana)
    assert "Skipped 1" in response.text
    assert len(mail.outbox) == 1


def test_skips_unconfirmed_addresses(client):
    _admin(client)
    response = _invite(client, _subscriber("new@example.com", confirmed=False))
    assert "Skipped 1" in response.text
    assert not EmailAddress.objects.filter(email="new@example.com").exists()
    assert mail.outbox == []


def test_spanish_invitation(client):
    _admin(client)
    _invite(client, _subscriber("eva@example.com", lang="es"))
    assert mail.outbox[0].subject == "Tu cuenta de tickr.bot está lista"


def test_a_failed_email_leaves_no_account(client, monkeypatch):
    _admin(client)

    def refuse(*args, **kwargs):
        raise OSError("mail is down")

    monkeypatch.setattr("tickrweb.invites.EmailMultiAlternatives.send", refuse)
    response = _invite(client, _subscriber("bo@example.com"))
    assert "could not be sent" in response.text
    assert not EmailAddress.objects.filter(email="bo@example.com").exists()
    assert not get_user_model().objects.filter(email="bo@example.com").exists()


def test_staff_without_add_user_permission_has_no_invite_action(client):
    call_command("invite", "helper@example.com", "--staff")
    helper = get_user_model().objects.get(email="helper@example.com")
    helper.user_permissions.add(*_view_subscriber())
    client.force_login(helper)
    session = client.session
    session["account_authentication_methods_user"] = str(helper.pk)
    session["account_authentication_methods"] = [{"at": 0, "method": "mfa", "type": "webauthn"}]
    session.save()
    _invite(client, _subscriber("cy@example.com"))
    assert not EmailAddress.objects.filter(email="cy@example.com").exists()


def _view_subscriber():
    from django.contrib.auth.models import Permission

    return Permission.objects.filter(codename__in=["view_subscriber", "change_subscriber"])
