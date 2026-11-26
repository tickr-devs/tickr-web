"""Test settings: the real settings with test-only values for the named variables.

The database variables are not set here: CI's Postgres service and a developer's local Postgres
provide TICKR_WEB_DB_NAME, TICKR_WEB_DB_USER, TICKR_WEB_DB_HOST and TICKR_WEB_DB_PORT.
"""

import os

os.environ["TICKR_WEB_HOST"] = "testserver"
os.environ["TICKR_WEB_SECRET_KEY"] = "test-only-not-a-secret"
os.environ["TICKR_WEB_FROM_EMAIL"] = "tickr.bot <hello@example.com>"
os.environ["TICKR_WEB_DEBUG"] = "1"

from .settings import *  # noqa: F403

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
# Fast hashing in tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
