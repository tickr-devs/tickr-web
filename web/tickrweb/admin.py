"""Admin pages (staff only, /app/admin/)."""

import logging

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from .invites import has_account, invite
from .mail import failure_summary
from .models import Subscriber

log = logging.getLogger(__name__)


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "lang", "signed_up_at", "confirmed_at", "account"]
    list_filter = ["lang", ("confirmed_at", admin.EmptyFieldListFilter)]
    search_fields = ["email"]
    actions = ["invite_selected"]

    @admin.display(boolean=True, description=_("Account"))
    def account(self, subscriber):
        return has_account(subscriber.email)

    def has_invite_permission(self, request):
        return request.user.has_perm("auth.add_user")

    @admin.action(description=_("Invite to tickr.bot"), permissions=["invite"])
    def invite_selected(self, request, queryset):
        invited = skipped = failed = 0
        for subscriber in queryset:
            # Only addresses whose owner clicked the confirmation link, and only once.
            if subscriber.confirmed_at is None or has_account(subscriber.email):
                skipped += 1
                continue
            try:
                invite(subscriber.email, subscriber.lang)
            except Exception as error:
                log.error("invitation not sent, no account created: %s", failure_summary(error))
                failed += 1
            else:
                invited += 1
        if invited:
            self.message_user(
                request,
                ngettext("Invited %d address.", "Invited %d addresses.", invited) % invited,
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                ngettext(
                    "Skipped %d: not confirmed yet or already has an account.",
                    "Skipped %d: not confirmed yet or already have an account.",
                    skipped,
                )
                % skipped,
                messages.WARNING,
            )
        if failed:
            self.message_user(
                request,
                ngettext(
                    "%d invitation could not be sent; no account was created.",
                    "%d invitations could not be sent; no accounts were created.",
                    failed,
                )
                % failed,
                messages.ERROR,
            )
