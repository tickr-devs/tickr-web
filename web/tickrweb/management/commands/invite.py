"""Create an account for one email address and mark the address verified.

The account has no password: its owner signs in with a code sent to that address, then adds a
password and a passkey under /account/. No password ever passes through this command.
"""

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction


class Command(BaseCommand):
    help = "Create an invited account (sign-in by emailed code)."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument(
            "--staff", action="store_true", help="May open /app/admin/ (with a passkey)."
        )
        parser.add_argument(
            "--superuser", action="store_true", help="Every admin permission (implies --staff)."
        )

    def handle(self, *args, email, staff, superuser, **options):
        email = email.strip().lower()
        try:
            validate_email(email)
        except Exception as error:
            raise CommandError("That is not an email address.") from error
        if EmailAddress.objects.filter(email__iexact=email).exists():
            raise CommandError("An account with that email address already exists.")
        user_model = get_user_model()
        with transaction.atomic():
            user = user_model(
                username=email, email=email, is_staff=staff or superuser, is_superuser=superuser
            )
            user.set_unusable_password()
            user.save()
            EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        self.stdout.write(f"Invited {email}. Sign in at /login with an emailed code.")
