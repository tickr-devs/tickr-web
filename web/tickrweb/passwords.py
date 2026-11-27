"""Refuse passwords that appear in known breaches (Have I Been Pwned, k-anonymity).

Only the first 5 hex characters of the password's SHA-1 leave the server; the service answers
with every suffix in that range and the match is made here, so neither the password nor its full
hash is ever sent. If the service cannot be reached the password is accepted and the failure is
logged without the password: a password alone never opens the admin sections or a bot grant
(they need a passkey or an authenticator app), so an outage must not lock people out.
"""

import hashlib
import logging
import urllib.request

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

log = logging.getLogger(__name__)

# The range endpoint (https://haveibeenpwned.com/API/v3#PwnedPasswords); no API key needed.
RANGE_URL = "https://api.pwnedpasswords.com/range/"
# Characters of the SHA-1 hex digest sent to the service (the k-anonymity prefix).
PREFIX_LENGTH = 5


def times_breached(password: str) -> int | None:
    """How often the password is in the breach list; None when the service cannot be asked."""
    digest = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = digest[:PREFIX_LENGTH], digest[PREFIX_LENGTH:]
    request = urllib.request.Request(
        RANGE_URL + prefix,
        # Padding makes every answer the same size, so the range cannot be told from its length.
        headers={"Add-Padding": "true", "User-Agent": "tickr.bot password check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.PASSWORD_BREACH_CHECK_SECONDS) as r:
            body = r.read().decode("ascii")
        for line in body.splitlines():
            candidate, _sep, count = line.partition(":")
            if candidate.strip() == suffix:
                return int(count)
        return 0
    except Exception as error:  # an outage or a garbled answer must not lock people out
        log.warning("breached-password check unavailable: %s", type(error).__name__)
        return None


class BreachedPasswordValidator:
    def validate(self, password, user=None):
        if times_breached(password):
            raise ValidationError(
                _("This password is in a list of leaked passwords. Choose another one."),
                code="password_breached",
            )

    def get_help_text(self):
        return _("Your password can't be one that appeared in a data breach.")
