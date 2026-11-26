"""allauth hooks for tickr.bot."""

from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Accounts are created by invitation only (`manage.py invite`)."""
        return False
