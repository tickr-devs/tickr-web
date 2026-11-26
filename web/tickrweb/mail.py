"""What may be logged when sending an email fails."""

import re

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
