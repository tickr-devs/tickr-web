"""Pages of the web app that are not allauth's."""

from allauth.mfa.models import Authenticator
from allauth.usersessions.models import UserSession
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """For Caddy and the uptime check: the process answers. Says nothing else."""
    return HttpResponse("ok", content_type="text/plain")


@login_required
@require_GET
def cabinet(request):
    """The cabinet. Only the Account card is live; the others show sample data until the bot's
    read-only key is wired in."""
    user = request.user
    return render(
        request,
        "cabinet/index.html",
        {
            "device_count": UserSession.objects.filter(user=user).count(),
            "passkey_count": Authenticator.objects.filter(
                user=user, type=Authenticator.Type.WEBAUTHN
            ).count(),
        },
    )
