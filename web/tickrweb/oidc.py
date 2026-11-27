"""The Mac and iPhone apps sign in to tickr.bot and get a grant the bot accepts.

tickr.bot is an OpenID provider (allauth.idp.oidc) for two public native clients, `tickr-ios` and
`tickr-mac` (RFC 8252: authorization code + PKCE S256, redirect `tickr://signin`). The token
endpoint answers with a 60-second RS256 JWT access token, the bot grant:
iss https://tickr.bot, aud https://bot.tickr.bot (the app sends `resource`), sub = account id,
client_id, iat, exp, jti, scope "bot". The bot checks it offline with the pinned public key and
issues its own device token; tickr.bot never talks to the bot.

Only an admin in a session signed in with a passkey or an authenticator app gets a code (the same
gate as the cabinet's admin sections). Everyone else sees the refusal page instead.
"""

from allauth.idp.oidc import views as oidc_views
from allauth.idp.oidc.adapter import DefaultOIDCAdapter
from django.conf import settings
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from .roles import admin_session

# The scope the apps ask for: reach the bot API.
BOT_SCOPE = "bot"


class Adapter(DefaultOIDCAdapter):
    def get_issuer(self) -> str:
        return f"https://{settings.SITE_HOST}"

    def get_scope_choices(self):
        return [(BOT_SCOPE, _("Use your tickr.bot bot from this app"))]


def authorize(request, *args, **kwargs):
    """allauth's authorize view, opened only to an admin in a passkey/authenticator session."""
    if request.user.is_authenticated and not admin_session(request):
        return render(request, "cabinet/admin_refused.html", status=403)
    return oidc_views.authorization(request, *args, **kwargs)
