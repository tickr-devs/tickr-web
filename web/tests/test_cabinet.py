"""The cabinet's admin sections: who opens them, roles, the last admin, inviting from the list."""

import pytest
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from tickrweb.models import Subscriber

pytestmark = pytest.mark.django_db

STRONG = {"method": "mfa", "type": "webauthn"}


def _account(email, *flags):
    call_command("invite", email, *flags)
    return get_user_model().objects.get(email=email)


def _with_passkey(user):
    Authenticator.objects.create(user=user, type=Authenticator.Type.WEBAUTHN, data={})
    return user


def _client(user, record=STRONG):
    client = Client()
    client.force_login(user)
    session = client.session
    session["account_authentication_methods_user"] = str(user.pk)
    session["account_authentication_methods"] = [{"at": 0, **record}]
    session.save()
    return client


def _role(client, user, role):
    return client.post(f"/app/people/{user.pk}/role", {"role": role}, follow=True)


@pytest.mark.parametrize("path", ["/app/people", "/app/early-access"])
def test_members_are_refused_the_admin_sections(path):
    client = _client(_account("member@example.com"))
    assert client.get(path).status_code == 403


@pytest.mark.parametrize("record", [{"method": "code"}, {"method": "password"}])
@pytest.mark.parametrize("path", ["/app/people", "/app/early-access"])
def test_admins_need_a_passkey_or_authenticator_session(path, record):
    client = _client(_account("owner@example.com", "--superuser"), record)
    assert client.get(path).status_code == 403


def test_staff_without_superuser_is_not_an_admin():
    client = _client(_account("staff@example.com", "--staff"))
    assert client.get("/app/people").status_code == 403


def test_admin_opens_people_and_early_access():
    client = _client(_account("owner@example.com", "--superuser"))
    assert client.get("/app/people").status_code == 200
    assert client.get("/app/early-access").status_code == 200


def test_a_member_cannot_change_roles():
    owner = _account("owner@example.com", "--superuser")
    member = _account("member@example.com")
    response = _role(_client(member), member, "admin")
    assert response.status_code == 403
    member.refresh_from_db()
    assert not member.is_superuser
    owner.refresh_from_db()
    assert owner.is_superuser


def test_an_admin_makes_another_admin_and_every_admin_is_told(django_capture_on_commit_callbacks):
    owner = _account("owner@example.com", "--superuser")
    member = _with_passkey(_account("member@example.com"))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        response = _role(_client(owner), member, "admin")
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.is_staff and member.is_superuser
    assert len(mail.outbox) == 1
    assert set(mail.outbox[0].bcc) == {"owner@example.com", "member@example.com"}
    assert mail.outbox[0].to == []


def test_an_admin_removes_another_admin_and_both_are_told(django_capture_on_commit_callbacks):
    owner = _account("owner@example.com", "--superuser")
    second = _account("second@example.com", "--superuser")
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        _role(_client(owner), second, "member")
    second.refresh_from_db()
    assert not second.is_staff and not second.is_superuser
    assert set(mail.outbox[0].bcc) == {"owner@example.com", "second@example.com"}


@pytest.mark.parametrize("factor", [None, Authenticator.Type.RECOVERY_CODES])
def test_only_an_account_with_a_passkey_or_authenticator_can_be_made_admin(factor):
    owner = _account("owner@example.com", "--superuser")
    member = _account("member@example.com")
    if factor:
        Authenticator.objects.create(user=member, type=factor, data={})
    response = _role(_client(owner), member, "admin")
    assert "needs a passkey or an authenticator app" in response.text
    member.refresh_from_db()
    assert not member.is_superuser


def test_an_authenticator_app_is_enough_to_be_made_admin():
    owner = _account("owner@example.com", "--superuser")
    member = _account("member@example.com")
    Authenticator.objects.create(user=member, type=Authenticator.Type.TOTP, data={})
    _role(_client(owner), member, "admin")
    member.refresh_from_db()
    assert member.is_superuser


@pytest.mark.django_db(transaction=True)  # real commits: the notice runs before the view answers
def test_a_failed_notice_keeps_the_change_and_says_so(monkeypatch):
    def refuse(*args):
        raise OSError("mail refused")

    monkeypatch.setattr("tickrweb.roles._notify", refuse)
    owner = _account("owner@example.com", "--superuser")
    member = _with_passkey(_account("member@example.com"))
    response = _role(_client(owner), member, "admin")
    assert response.status_code == 200
    assert "the notice email could not be sent" in response.text
    member.refresh_from_db()
    assert member.is_superuser


def test_the_last_admin_cannot_be_removed():
    owner = _account("owner@example.com", "--superuser")
    mail.outbox.clear()
    response = _role(_client(owner), owner, "member")
    assert "needs at least one admin" in response.text
    owner.refresh_from_db()
    assert owner.is_staff and owner.is_superuser
    assert mail.outbox == []


def test_an_admin_can_step_down_while_another_remains():
    owner = _account("owner@example.com", "--superuser")
    _account("second@example.com", "--superuser")
    response = _role(_client(owner), owner, "member")
    assert response.request["PATH_INFO"] == "/app"
    owner.refresh_from_db()
    assert not owner.is_superuser


def test_an_unknown_role_is_refused():
    owner = _account("owner@example.com", "--superuser")
    second = _account("second@example.com", "--superuser")
    response = _client(owner).post(f"/app/people/{second.pk}/role", {"role": "boss"})
    assert response.status_code == 400
    second.refresh_from_db()
    assert second.is_superuser


def test_role_changes_need_post():
    owner = _account("owner@example.com", "--superuser")
    member = _account("member@example.com")
    assert _client(owner).get(f"/app/people/{member.pk}/role").status_code == 405


def _subscriber(email, confirmed=True):
    now = timezone.now()
    return Subscriber.objects.create(
        email=email, lang="es", signed_up_at=now, confirmed_at=now if confirmed else None
    )


def test_early_access_invites_only_confirmed_addresses_without_an_account():
    owner = _account("owner@example.com", "--superuser")
    confirmed = _subscriber("new@example.com")
    waiting = _subscriber("waiting@example.com", confirmed=False)
    already = _subscriber("owner@example.com")
    mail.outbox.clear()
    response = _client(owner).post(
        "/app/early-access", {"invite": [confirmed.pk, waiting.pk, already.pk]}, follow=True
    )
    assert "Invited 1 person." in response.text
    accounts = set(get_user_model().objects.values_list("email", flat=True))
    assert accounts == {"owner@example.com", "new@example.com"}
    assert [m.to for m in mail.outbox] == [["new@example.com"]]


def test_early_access_lists_each_state():
    owner = _account("owner@example.com", "--superuser")
    EmailAddress.objects.filter(user=owner).update(email="Owner@example.com")
    _subscriber("new@example.com")
    _subscriber("waiting@example.com", confirmed=False)
    _subscriber("owner@example.com")
    rows = _client(owner).get("/app/early-access").context["rows"]
    states = {r["s"].email: r["state"] for r in rows}
    assert states == {
        "new@example.com": "confirmed",
        "waiting@example.com": "waiting",
        "owner@example.com": "member",
    }


def test_early_access_rows_pick_by_tap_and_the_button_counts_them():
    owner = _account("owner@example.com", "--superuser")
    _subscriber("new@example.com")
    page = _client(owner).get("/app/early-access").text
    assert 'class="tb pick"' in page
    assert 'data-count-label="Invite {count}"' in page
    assert 'data-empty-label="Invite selected"' in page
    assert "/static/web/app.js" in page
