"""The site's emails: how they are built, and what may be logged when sending one fails."""

import re

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

# Anything shaped like an address, also inside an ARN such as ...:identity/a@b.c.
_ADDRESS = re.compile(r"[^\s/:\"'<>]+@[^\s/:\"'<>]+")


def failure_summary(error: Exception) -> str:
    """The error's class and, for an AWS error, its code and message.

    An SES rejection names the refused recipient in its message ("…failed the check…: a@b.c"),
    and the privacy page promises addresses are never logged, so that message is left out. An
    access error's message is kept (it names the role and the action, which is what one needs to
    fix it) with every address in it replaced: a denial can name a recipient's identity ARN.
    """
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return type(error).__name__
    details = response.get("Error", {})
    code = details.get("Code", "")
    if code in {"AccessDenied", "AccessDeniedException"}:
        message = _ADDRESS.sub("<address>", details.get("Message", ""))
        return f"{type(error).__name__} {code}: {message}"
    return f"{type(error).__name__} {code}"


def styled_email(
    subject_template: str, body_template: str, context: dict, **message
) -> EmailMultiAlternatives:
    """An email in the site's mail design: the plain-text body from `body_template` (a .txt) and
    the same message as HTML from the .html beside it (templates/mail/base.html), rendered in the
    active language. `message` is passed on to EmailMultiAlternatives (to, bcc, headers)."""
    subject = " ".join(render_to_string(subject_template, context).split())
    text = render_to_string(body_template, context)
    html = render_to_string(body_template.removesuffix(".txt") + ".html", context)
    email = EmailMultiAlternatives(subject, text, **message)
    email.attach_alternative(html, "text/html")
    return email
