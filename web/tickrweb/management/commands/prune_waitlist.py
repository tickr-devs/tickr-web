"""Delete early-access rows never confirmed within WAITLIST_CONFIRM_MAX_AGE_SECONDS (nightly)."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from tickrweb.models import Subscriber


class Command(BaseCommand):
    help = "Delete unconfirmed early-access addresses whose confirmation link has expired."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(seconds=settings.WAITLIST_CONFIRM_MAX_AGE_SECONDS)
        deleted, _ = Subscriber.objects.filter(
            confirmed_at__isnull=True, signed_up_at__lt=cutoff
        ).delete()
        self.stdout.write(f"Deleted {deleted} unconfirmed addresses.")
