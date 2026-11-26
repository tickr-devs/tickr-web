"""Move the old Namecheap list (tickr-signups/emails.csv: "UTC time,email,lang") into Postgres.

Those addresses never confirmed, so each gets a confirmation email now and counts as signed up at
import time: unconfirmed ones are pruned like any other once the link expires.
Addresses already in the table are skipped.
"""

import csv
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.validators import validate_email
from django.utils import timezone

from tickrweb.models import Subscriber
from tickrweb.waitlist import send_confirmation


class Command(BaseCommand):
    help = "Import emails.csv from the old site and send each new address a confirmation email."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=Path)

    def handle(self, *args, csv_path, **options):
        added = skipped = invalid = 0
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.reader(handle):
                if len(row) != 3:
                    invalid += 1
                    continue
                email, lang = row[1].strip().lower(), row[2].strip()
                try:
                    validate_email(email)
                except ValidationError:
                    invalid += 1
                    continue
                subscriber, created = Subscriber.objects.get_or_create(
                    email=email,
                    defaults={
                        "lang": "es" if lang == "es" else "en",
                        "signed_up_at": timezone.now(),
                    },
                )
                if not created:
                    skipped += 1
                    continue
                send_confirmation(subscriber)
                added += 1
        self.stdout.write(f"Imported {added}, already there {skipped}, unreadable rows {invalid}.")
