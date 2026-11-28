"""Who is an admin of tickr.bot, and how that changes.

An admin is an account with is_staff and is_superuser both set; everyone else is a member.
Admins see the admin sections of the cabinet (Early access, People), and only in a session
signed in with a passkey or an authenticator app (signed_in_with_a_strong_factor).
Another admin grants or removes the role on the People page. Only an account that already has
a passkey or an authenticator app can be made admin (so a new admin is never only as strong as
their mailbox); the last admin cannot be removed; every change is emailed to all admins.
"""

import logging

from allauth.account.authentication import get_authentication_records
from allauth.mfa.models import Authenticator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import translation

from .mail import failure_summary, styled_email

log = logging.getLogger(__name__)

STRONG_FACTORS = (Authenticator.Type.WEBAUTHN, Authenticator.Type.TOTP)


class LastAdmin(Exception):
    """Removing this role would leave tickr.bot without an admin."""


class NoStrongFactor(Exception):
    """The account has no passkey or authenticator app yet, so it cannot be made admin."""


def has_strong_factor(user) -> bool:
    return Authenticator.objects.filter(user=user, type__in=STRONG_FACTORS).exists()


def signed_in_with_a_strong_factor(request) -> bool:
    """This session was signed in with a passkey or an authenticator app, not a mailbox."""
    records = get_authentication_records(request, request.user)
    return any(r.get("method") == "mfa" and r.get("type") in STRONG_FACTORS for r in records)


def is_admin(user) -> bool:
    return bool(user.is_authenticated and user.is_active and user.is_staff and user.is_superuser)


def admin_session(request) -> bool:
    """The admin sections open: an admin, signed in with a passkey or an authenticator app."""
    return is_admin(request.user) and signed_in_with_a_strong_factor(request)


def admins():
    return get_user_model().objects.filter(is_active=True, is_staff=True, is_superuser=True)


class Outcome:
    """What set_admin did: whether the role changed, and whether the notice email went out."""

    def __init__(self):
        self.changed = False
        self.notified = True


def set_admin(target, make_admin: bool, *, by) -> Outcome:
    """Grants or removes the role and emails every admin about it."""
    outcome = Outcome()
    with transaction.atomic():
        user_model = get_user_model()
        # Lock the admin rows so two removals at once cannot both pass the last-admin check.
        list(admins().select_for_update())
        target = user_model.objects.select_for_update().get(pk=target.pk)
        if is_admin(target) == make_admin:
            return outcome
        if make_admin and not has_strong_factor(target):
            raise NoStrongFactor
        if not make_admin and admins().exclude(pk=target.pk).count() == 0:
            raise LastAdmin
        target.is_staff = target.is_superuser = make_admin
        target.save(update_fields=["is_staff", "is_superuser"])
        recipients = sorted({a.email for a in admins()} | {target.email})
        outcome.changed = True

        def notify():
            try:
                _notify(recipients, target.email, make_admin, by.email)
            except Exception as error:  # the change stands; say the notice failed, never crash
                log.error("role change notice not sent: %s", failure_summary(error))
                outcome.notified = False

        # Runs when the outermost transaction commits. ATOMIC_REQUESTS is off (settings.py), so
        # that is the end of this block and outcome.notified is set before set_admin returns.
        # Turning ATOMIC_REQUESTS on would defer it past the view and lose the warning.
        transaction.on_commit(notify)
    return outcome


def _notify(recipients, email, made_admin, by_email):
    context = {"email": email, "by": by_email, "made_admin": made_admin}
    context["people_url"] = f"https://{settings.SITE_HOST}/app/people"
    with translation.override("en"):
        message = styled_email(
            "roles/changed_subject.txt", "roles/changed_body.txt", context, bcc=recipients
        )
    message.send()
