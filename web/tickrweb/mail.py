"""What may be logged when sending an email fails."""


def failure_summary(error: Exception) -> str:
    """The error's class and, for an AWS error, its code and message.

    An SES rejection names the refused recipient in its message ("…failed the check…: a@b.c"),
    and the privacy page promises addresses are never logged, so that message is left out; an
    access error names only the role and the action, which is what one needs to fix it.
    """
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return type(error).__name__
    details = response.get("Error", {})
    code = details.get("Code", "")
    if code in {"AccessDenied", "AccessDeniedException"}:
        return f"{type(error).__name__} {code}: {details.get('Message', '')}"
    return f"{type(error).__name__} {code}"
