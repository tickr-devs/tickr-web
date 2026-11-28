"""Accounts are invite-only: one function creates an invited account, one emails the invitation.

An invited account has a verified address and no password. Its owner signs in at /login with a
code sent to that address, then adds a passkey and a password under /account/.
"""

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import translation

from .mail import styled_email


class AlreadyHasAccount(Exception):
    """The address already belongs to an account."""


def has_account(email: str) -> bool:
    return EmailAddress.objects.filter(email__iexact=email).exists()


def create_invited_account(email: str, *, staff: bool = False, superuser: bool = False):
    email = email.strip().lower()
    if has_account(email):
        raise AlreadyHasAccount(email)
    user_model = get_user_model()
    with transaction.atomic():
        user = user_model(
            username=email, email=email, is_staff=staff or superuser, is_superuser=superuser
        )
        user.set_unusable_password()
        user.save()
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def send_invitation(email: str, lang: str) -> None:
    context = {"login_url": f"https://{settings.SITE_HOST}/login"}
    with translation.override(lang):
        message = styled_email("invites/subject.txt", "invites/body.txt", context, to=[email])
    message.send()


def invite(email: str, lang: str) -> None:
    """Creates the account and emails the invitation; if the email fails, no account is left."""
    with transaction.atomic():
        create_invited_account(email)
        send_invitation(email, lang)
