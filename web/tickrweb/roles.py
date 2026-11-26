"""Who is an admin of tickr.bot, and how that changes.

An admin is an account with is_staff and is_superuser both set; everyone else is a member.
Admins see the admin sections of the cabinet (Early access, People), and only in a session
signed in with a passkey or an authenticator app (admin_site.signed_in_with_a_strong_factor).
Another admin grants or removes the role on the People page; the last admin cannot be removed,
and every change is emailed to all admins.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import translation

from .admin_site import signed_in_with_a_strong_factor


class LastAdmin(Exception):
    """Removing this role would leave tickr.bot without an admin."""


def is_admin(user) -> bool:
    return bool(user.is_authenticated and user.is_active and user.is_staff and user.is_superuser)


def admin_session(request) -> bool:
    """The admin sections open: an admin, signed in with a passkey or an authenticator app."""
    return is_admin(request.user) and signed_in_with_a_strong_factor(request)


def admins():
    return get_user_model().objects.filter(is_active=True, is_staff=True, is_superuser=True)


def set_admin(target, make_admin: bool, *, by) -> bool:
    """Grants or removes the role; returns whether anything changed. Emails every admin."""
    with transaction.atomic():
        user_model = get_user_model()
        # Lock the admin rows so two removals at once cannot both pass the last-admin check.
        list(admins().select_for_update())
        target = user_model.objects.select_for_update().get(pk=target.pk)
        if is_admin(target) == make_admin:
            return False
        if not make_admin and admins().exclude(pk=target.pk).count() == 0:
            raise LastAdmin
        target.is_staff = target.is_superuser = make_admin
        target.save(update_fields=["is_staff", "is_superuser"])
        recipients = sorted({a.email for a in admins()} | {target.email})
        transaction.on_commit(lambda: _notify(recipients, target.email, make_admin, by.email))
    return True


def _notify(recipients, email, made_admin, by_email):
    context = {"email": email, "by": by_email, "made_admin": made_admin}
    context["people_url"] = f"https://{settings.SITE_HOST}/app/people"
    with translation.override("en"):
        subject = render_to_string("roles/changed_subject.txt", context).strip()
        body = render_to_string("roles/changed_body.txt", context)
    EmailMultiAlternatives(subject, body, bcc=recipients).send()
