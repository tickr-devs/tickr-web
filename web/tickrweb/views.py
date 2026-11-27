"""Pages of the web app that are not allauth's: the cabinet and its admin sections."""

import logging
from functools import wraps

from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from allauth.usersessions.models import UserSession
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .invites import invite
from .mail import failure_summary
from .models import Subscriber
from .roles import (
    STRONG_FACTORS,
    LastAdmin,
    NoStrongFactor,
    admin_session,
    admins,
    is_admin,
    set_admin,
)

log = logging.getLogger(__name__)


@require_GET
def healthz(request):
    """For Caddy and the uptime check: the process answers. Says nothing else."""
    return HttpResponse("ok", content_type="text/plain")


def _passkeys(user):
    return Authenticator.objects.filter(user=user, type=Authenticator.Type.WEBAUTHN)


@login_required
@require_GET
def cabinet(request):
    """Overview: what is real today. The bot's own card stays empty until the bot reports here."""
    user = request.user
    context = {
        "device_count": UserSession.objects.filter(user=user).count(),
        "passkey_count": _passkeys(user).count(),
        "has_totp": Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists(),
    }
    if is_admin(user):
        context["waiting_count"] = (
            Subscriber.objects.filter(confirmed_at__isnull=False)
            .exclude(email__in=EmailAddress.objects.values("email"))
            .count()
        )
        context["people_count"] = get_user_model().objects.filter(is_active=True).count()
    return render(request, "cabinet/index.html", context)


def admin_only(view):
    """An admin section: an admin in a session signed in with a passkey or authenticator app."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not admin_session(request):
            return render(request, "cabinet/admin_refused.html", status=403)
        return view(request, *args, **kwargs)

    return wrapper


@admin_only
@require_http_methods(["GET", "POST"])
def early_access(request):
    """The early-access list; confirmed addresses without an account can be invited."""
    registered = {e.lower() for e in EmailAddress.objects.values_list("email", flat=True)}
    if request.method == "POST":
        chosen = Subscriber.objects.filter(
            pk__in=request.POST.getlist("invite"), confirmed_at__isnull=False
        )
        sent = failed = 0
        for subscriber in chosen:
            if subscriber.email.lower() in registered:
                continue
            try:
                invite(subscriber.email, subscriber.lang)
            except Exception as error:
                log.error("invitation not sent, no account created: %s", failure_summary(error))
                failed += 1
            else:
                sent += 1
        if sent:
            messages.success(
                request, ngettext("Invited %d person.", "Invited %d people.", sent) % sent
            )
        if failed:
            messages.error(
                request,
                ngettext(
                    "%d invitation could not be sent; no account was created.",
                    "%d invitations could not be sent; no accounts were created.",
                    failed,
                )
                % failed,
            )
        return redirect("early_access")
    rows = []
    for s in Subscriber.objects.order_by("-confirmed_at", "-signed_up_at"):
        state = (
            "member"
            if s.email.lower() in registered
            else "confirmed"
            if s.confirmed_at
            else "waiting"
        )
        rows.append({"s": s, "state": state})
    invitable = sum(r["state"] == "confirmed" for r in rows)
    return render(request, "cabinet/early_access.html", {"rows": rows, "invitable": invitable})


@admin_only
@require_GET
def people(request):
    users = (
        get_user_model()
        .objects.filter(is_active=True)
        .annotate(
            passkeys=Count(
                "authenticator", filter=Q(authenticator__type=Authenticator.Type.WEBAUTHN)
            ),
            strong=Count("authenticator", filter=Q(authenticator__type__in=STRONG_FACTORS)),
        )
        .order_by("-is_superuser", "email")
    )
    return render(
        request,
        "cabinet/people.html",
        {"people": users, "admin_count": admins().count()},
    )


@admin_only
@require_POST
def set_role(request, pk):
    target = get_object_or_404(get_user_model(), pk=pk, is_active=True)
    role = request.POST.get("role")
    if role not in {"admin", "member"}:
        return HttpResponse(status=400)
    make_admin = role == "admin"
    try:
        outcome = set_admin(target, make_admin, by=request.user)
    except LastAdmin:
        messages.error(request, _("tickr.bot needs at least one admin."))
        return redirect("people")
    except NoStrongFactor:
        messages.error(
            request,
            _("%(email)s needs a passkey or an authenticator app before becoming an admin.")
            % {"email": target.email},
        )
        return redirect("people")
    if outcome.changed and not outcome.notified:
        messages.warning(request, _("The role changed, but the notice email could not be sent."))
    if outcome.changed:
        text = (
            _("%(email)s is now an admin.") if make_admin else _("%(email)s is no longer an admin.")
        )
        messages.success(request, text % {"email": target.email})
    if target == request.user and not make_admin:
        return redirect("cabinet")
    return redirect("people")
