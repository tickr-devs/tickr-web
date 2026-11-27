"""Retry-After on the apps' refused password sign-in.

allauth answers a password sign-in blocked by ACCOUNT_RATE_LIMITS["login_failed"] with a plain
400 form error (code too_many_login_attempts) and no wait. The apps show how long to wait, so
this adds Retry-After: the seconds until the blocking window lets one more attempt in. It reads
allauth's own rate-limit history and changes nothing in it. With no history to read, it adds
nothing and the apps say "try again later".
"""

import json
import logging
import math
import time

from allauth.account.adapter import get_adapter
from allauth.core.internal import ratelimit
from django.core.cache import cache

# The headless (app client) password sign-in, as mounted in urls.py.
LOGIN_PATH = "/api/auth/app/v1/auth/login"
BLOCKED_CODE = "too_many_login_attempts"

log = logging.getLogger(__name__)


def _blocked(response) -> bool:
    if response.status_code != 400:
        return False
    try:
        errors = json.loads(response.content).get("errors", [])
    except (ValueError, AttributeError):
        return False
    return any(isinstance(e, dict) and e.get("code") == BLOCKED_CODE for e in errors)


def seconds_until_allowed(request, email: str) -> int | None:
    """Seconds until every login_failed rate for this request lets one attempt in."""
    key = get_adapter()._get_login_attempts_cache_key(request, email=email)
    now = time.time()
    wait = None
    for rate in ratelimit.get_rates(app="allauth.account", action="login_failed"):
        if rate.per not in ("ip", "key"):
            continue
        cache_key = ratelimit.get_cache_key(
            request,
            app="allauth.account",
            action="login_failed",
            rate=rate,
            key=key if rate.per == "key" else None,
        )
        # Newest first, as allauth keeps it; drop what has left the window.
        history = [ts for ts in cache.get(cache_key, []) if ts > now - rate.duration]
        if len(history) >= rate.amount:
            # One attempt is allowed again when the oldest hit that still counts expires.
            opens = history[rate.amount - 1] + rate.duration - now
            wait = max(wait or 0, math.ceil(opens))
    return wait


class LoginRetryAfterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method != "POST" or request.path != LOGIN_PATH or not _blocked(response):
            return response
        # Retry-After is only a hint: any failure here (allauth internals renamed, an unreadable
        # body) leaves the refusal as allauth sent it, never a 500.
        try:
            email = json.loads(request.body).get("email")
            wait = (
                seconds_until_allowed(request, email) if isinstance(email, str) and email else None
            )
        except Exception as error:  # noqa: BLE001 (fail open, see above)
            log.warning("Retry-After not added: %s", type(error).__name__)
            return response
        if wait:
            response["Retry-After"] = str(wait)
        return response
