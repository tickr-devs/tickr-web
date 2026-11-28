"""allauth hooks for tickr.bot."""

import logging

from allauth.account.adapter import DefaultAccountAdapter

from .mail import failure_summary

log = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Accounts are created by invitation only (`manage.py invite`)."""
        return False

    def send_mail(self, template_prefix, email, context):
        """Sends allauth's emails (sign-in code, password reset, address confirmation, notices).

        A failed send is logged and the page answers as if it went out. Anyone can type an address
        into the code and reset forms, and mail goes only to addresses that have an account, so an
        error page there would say "this address has an account". It also keeps a mail outage
        (SES refusing, timing out) from turning those forms into a server error.
        """
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as error:  # noqa: BLE001 (see above; the cause is logged)
            log.error("%s not sent: %s", template_prefix, failure_summary(error))
