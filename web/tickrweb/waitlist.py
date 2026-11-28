"""The early-access list: POST /api/waitlist from the static site, double opt-in by email.

Replies are JSON {"status": ...} with the statuses the site's form knows: "confirm" (check your
email), "invalid", "rate", "error"; a filled honeypot gets "ok" and nothing happens. Whether an
address is already on the list is never revealed: every valid address gets "confirm".
The sender's IP is used only as a rate-limit key in the process's memory and never stored.
"""

import hashlib
import logging

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone, translation
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .mail import failure_summary, styled_email
from .models import Subscriber

log = logging.getLogger(__name__)

CONFIRM_SALT = "tickrweb.waitlist.confirm"
UNSUBSCRIBE_SALT = "tickrweb.waitlist.unsubscribe"
SECONDS_PER_DAY = 24 * 60 * 60


def _reply(status: str, code: int = 200) -> JsonResponse:
    return JsonResponse({"status": status}, status=code)


def _over_limit(key: str, limit: int, seconds: int) -> bool:
    """Counts one more hit for `key` in the cache; True once more than `limit` in the window."""
    cache.add(key, 0, seconds)
    try:
        return cache.incr(key) > limit
    except ValueError:  # the entry expired between add and incr
        cache.set(key, 1, seconds)
        return False


def _client_key(request) -> str:
    # Caddy is the only client of gunicorn and sets X-Forwarded-For to the visitor's address.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    address = forwarded.split(",")[-1].strip() or request.META.get("REMOTE_ADDR", "")
    return hashlib.sha256(address.encode()).hexdigest()


def _site_url(path: str) -> str:
    return f"https://{settings.SITE_HOST}{path}"


def send_confirmation(subscriber: Subscriber) -> None:
    confirm = signing.dumps(subscriber.email, salt=CONFIRM_SALT)
    leave = signing.dumps(subscriber.email, salt=UNSUBSCRIBE_SALT)
    context = {
        "confirm_url": _site_url(reverse("waitlist_confirm") + f"?t={confirm}"),
        "unsubscribe_url": _site_url(reverse("waitlist_unsubscribe") + f"?t={leave}"),
        "keep_days": settings.WAITLIST_CONFIRM_MAX_AGE_SECONDS // SECONDS_PER_DAY,
    }
    with translation.override(subscriber.lang):
        message = styled_email(
            "waitlist/confirm_subject.txt",
            "waitlist/confirm_body.txt",
            context,
            to=[subscriber.email],
            headers={
                "List-Unsubscribe": f"<{context['unsubscribe_url']}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        )
    message.send()


@csrf_exempt  # a static page posts here; same-origin is checked from the Origin header instead
@require_POST
def join(request):
    if request.headers.get("Origin") != f"https://{settings.SITE_HOST}":
        return _reply("error", 403)
    if request.POST.get("website"):
        return _reply("ok")
    window = settings.WAITLIST_WINDOW_SECONDS
    if _over_limit(f"waitlist:ip:{_client_key(request)}", settings.WAITLIST_PER_IP, window):
        return _reply("rate", 429)
    email = request.POST.get("email", "").strip().lower()
    lang = "es" if request.POST.get("lang") == "es" else "en"
    try:
        validate_email(email)
    except ValidationError:
        return _reply("invalid", 400)
    if len(email) > Subscriber._meta.get_field("email").max_length:
        return _reply("invalid", 400)
    existing = Subscriber.objects.filter(email=email).first()
    if existing is not None and existing.confirmed_at is not None:
        return _reply("confirm")
    # One confirmation email per address per cooldown, whatever IP asks: nobody can use the form
    # to flood a stranger's inbox. The answer stays "confirm", so it reveals nothing.
    address_key = "waitlist:sent:" + hashlib.sha256(email.encode()).hexdigest()
    if not cache.add(address_key, 1, settings.WAITLIST_RESEND_COOLDOWN_SECONDS):
        return _reply("confirm")
    day = settings.WAITLIST_DAY_SECONDS
    if _over_limit("waitlist:new-per-day", settings.WAITLIST_NEW_PER_DAY, day):
        return _reply("rate", 429)
    try:
        with transaction.atomic():
            subscriber, created = Subscriber.objects.get_or_create(
                email=email, defaults={"lang": lang, "signed_up_at": timezone.now()}
            )
            if not created:
                # A new link: restart the row's clock, so prune never deletes it before the link
                # expires.
                subscriber.signed_up_at = timezone.now()
                subscriber.save(update_fields=["signed_up_at"])
    except IntegrityError:
        return _reply("confirm")
    try:
        send_confirmation(subscriber)
    except Exception as error:
        log.error("waitlist confirmation email not sent: %s", failure_summary(error))
        return _reply("error", 502)
    return _reply("confirm")


def _email_from(request, salt: str, max_age: int | None) -> str | None:
    try:
        return signing.loads(request.GET.get("t", ""), salt=salt, max_age=max_age)
    except signing.BadSignature:
        return None


@csrf_exempt  # the signed link is the key; a cross-site POST could only confirm its own address
@require_http_methods(["GET", "POST"])
def confirm(request):
    """GET shows a button and changes nothing (mail scanners open links); POST confirms."""
    email = _email_from(request, CONFIRM_SALT, settings.WAITLIST_CONFIRM_MAX_AGE_SECONDS)
    subscriber = Subscriber.objects.filter(email=email).first() if email else None
    if subscriber is None:
        return render(request, "waitlist/result.html", {"outcome": "expired"}, status=400)
    translation.activate(subscriber.lang)
    if request.method == "GET":
        context = {"outcome": "confirm", "token": request.GET["t"]}
        return render(request, "waitlist/result.html", context)
    if subscriber.confirmed_at is None:
        subscriber.confirmed_at = timezone.now()
        subscriber.save(update_fields=["confirmed_at"])
    return render(request, "waitlist/result.html", {"outcome": "confirmed"})


@csrf_exempt  # one-click unsubscribe (RFC 8058) posts without a token; the signed link is the key
@require_http_methods(["GET", "POST"])
def unsubscribe(request):
    email = _email_from(request, UNSUBSCRIBE_SALT, None)
    if email is None:
        return render(request, "waitlist/result.html", {"outcome": "expired"}, status=400)
    if request.method == "GET":
        return render(
            request, "waitlist/result.html", {"outcome": "ask", "token": request.GET["t"]}
        )
    Subscriber.objects.filter(email=email).delete()
    return render(request, "waitlist/result.html", {"outcome": "removed"})
