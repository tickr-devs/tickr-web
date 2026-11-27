"""Create an account for one email address and mark the address verified.

The account has no password: its owner signs in with a code sent to that address, then adds a
password and a passkey under /account/. No password ever passes through this command, and it
sends no email (Invite on the cabinet's Early access page does).
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from tickrweb.invites import AlreadyHasAccount, create_invited_account


class Command(BaseCommand):
    help = "Create an invited account (sign-in by emailed code)."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument(
            "--staff",
            action="store_true",
            help="Staff flag only; an admin needs --superuser as well.",
        )
        parser.add_argument(
            "--superuser", action="store_true", help="Every admin permission (implies --staff)."
        )

    def handle(self, *args, email, staff, superuser, **options):
        email = email.strip().lower()
        try:
            validate_email(email)
        except ValidationError as error:
            raise CommandError("That is not an email address.") from error
        try:
            create_invited_account(email, staff=staff, superuser=superuser)
        except AlreadyHasAccount as error:
            raise CommandError("An account with that email address already exists.") from error
        self.stdout.write(f"Invited {email}. Sign in at /login with an emailed code.")
