"""Test settings: the real settings with test-only values for the named variables.

The database variables are not set here: CI's Postgres service and a developer's local Postgres
provide TICKR_WEB_DB_NAME, TICKR_WEB_DB_USER, TICKR_WEB_DB_HOST and TICKR_WEB_DB_PORT.
"""

import atexit
import os
import tempfile


def _make_test_key() -> str:
    from tickrweb.grant_key import new_private_key_pem

    handle, path = tempfile.mkstemp(prefix="tickrweb-test-grant-", suffix=".pem")
    with os.fdopen(handle, "w", encoding="ascii") as out:
        out.write(new_private_key_pem())
    atexit.register(os.remove, path)
    return path


os.environ["TICKR_WEB_HOST"] = "testserver"
os.environ["TICKR_WEB_SECRET_KEY"] = "test-only-not-a-secret"
os.environ["TICKR_WEB_FROM_EMAIL"] = "tickr.bot <hello@example.com>"
os.environ["TICKR_WEB_DEBUG"] = "1"
# A fresh signing key per test run (tickrweb/grant_key.py makes the server's the same way).
os.environ["TICKR_WEB_GRANT_KEY_FILE"] = _make_test_key()

from .settings import *  # noqa: E402, F403 (the variables above must be set first)

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
# Fast hashing in tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Tests run without collectstatic, so plain names (the hashed names need its manifest).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
