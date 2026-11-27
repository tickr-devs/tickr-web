"""Settings for the tickr.bot web app.

This file is the web app's configuration: every number below has a comment saying what it is and
its unit. Secrets and per-server values come from environment variables read one NAME at a time
(`_required` / `_optional`); a missing required variable refuses the start and names the variable,
never a value. The web app runs on its own server, never beside the trading bot.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ImproperlyConfigured(f"Environment variable {name} is not set.")
    return value


def _optional(name: str) -> str:
    return os.environ.get(name, "")


# Public host name the site is served at, e.g. "tickr.bot". The only host Django answers for.
SITE_HOST = _required("TICKR_WEB_HOST")
SECRET_KEY = _required("TICKR_WEB_SECRET_KEY")
# "1" only on a developer machine: debug pages, plain-HTTP cookies. Anything else is production.
DEBUG = _optional("TICKR_WEB_DEBUG") == "1"

ALLOWED_HOSTS = [SITE_HOST]
CSRF_TRUSTED_ORIGINS = [f"https://{SITE_HOST}"]

INSTALLED_APPS = [
    "tickrweb.admin_apps.TickrAdminConfig",  # the admin with tickrweb.admin_site rules
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",  # allauth's signed-in devices page uses its template tags
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.usersessions",
    "allauth.headless",  # the apps' native sign-in screens use its JSON API, see tickrweb/grants.py
    "tickrweb",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "tickrweb.security.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "allauth.usersessions.middleware.UserSessionsMiddleware",
]

ROOT_URLCONF = "tickrweb.urls"
WSGI_APPLICATION = "tickrweb.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # The site's templates first, so they replace allauth's layout.
        "DIRS": [BASE_DIR / "tickrweb" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "tickrweb.context_processors.frame",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _required("TICKR_WEB_DB_NAME"),
        "USER": _required("TICKR_WEB_DB_USER"),
        "PASSWORD": _optional("TICKR_WEB_DB_PASSWORD"),
        "HOST": _required("TICKR_WEB_DB_HOST"),
        "PORT": _required("TICKR_WEB_DB_PORT"),
        # Seconds a database connection is kept open between requests (Django's CONN_MAX_AGE).
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Argon2id first: new and changed passwords are hashed with it.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    # Shortest password accepted, in characters (NIST SP 800-63B-4 minimum, password used alone).
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 15},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# --- Sessions and cookies ---
# "__Host-" cookies are accepted by browsers only over HTTPS, for this host, on path "/".
SESSION_COOKIE_NAME = "sessionid" if DEBUG else "__Host-sessionid"
CSRF_COOKIE_NAME = "csrftoken" if DEBUG else "__Host-csrftoken"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# A session ends this many seconds after sign-in (7 days).
SESSION_COOKIE_AGE = 604800

# --- HTTPS (Caddy terminates TLS and sets X-Forwarded-Proto) ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Browsers use HTTPS only for this many seconds after a visit (HSTS, 1 year).
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --- Languages: English and US Spanish only ---
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("es", "Español")]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True
USE_TZ = True
TIME_ZONE = "America/New_York"

STATIC_URL = "/static/"
# Folder `collectstatic` fills; Caddy serves it at /static/.
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Sign-in (django-allauth) ---
LOGIN_URL = "/login"
LOGIN_REDIRECT_URL = "/app"
ACCOUNT_LOGOUT_REDIRECT_URL = "/login"
ACCOUNT_ADAPTER = "tickrweb.adapters.AccountAdapter"
# Accounts are created by invitation only (`manage.py invite`); the public sign-up page is closed.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = "tickr.bot · "
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
ACCOUNT_SESSION_REMEMBER = True
# Proxies in front of gunicorn: one, Caddy. It overwrites X-Forwarded-For with the address it
# saw, so allauth takes the last entry as the client and its per-IP limits count per visitor.
# Without this every visitor shares Caddy's address and one bucket. gunicorn must be reachable
# only by Caddy (web/README.md).
ALLAUTH_TRUSTED_PROXY_COUNT = 1
# allauth's own limits: "count/period[/key]" with periods s, m, h, d.
ACCOUNT_RATE_LIMITS = {
    # Wrong passwords for one account from one IP: 5 per 15 minutes.
    "login_failed": "5/15m/ip,5/15m/key",
    # Sign-in attempts from one IP: 30 per hour.
    "login": "30/h/ip",
    # Sign-in codes emailed to one address: 3 per 5 minutes.
    "request_login_code": "3/5m/ip,3/5m/key",
    # Password reset: 20 requests a minute from one IP, 3 emails per 20 minutes per address.
    "reset_password": "20/m/ip,3/20m/key",
}
# Seconds a sign-in code sent by email stays valid (15 minutes).
ACCOUNT_LOGIN_BY_CODE_TIMEOUT = 900
# Wrong tries before an emailed sign-in code is void.
ACCOUNT_LOGIN_BY_CODE_MAX_ATTEMPTS = 3

MFA_SUPPORTED_TYPES = ["webauthn", "totp", "recovery_codes"]
MFA_PASSKEY_LOGIN_ENABLED = True
# Passkeys on localhost only while developing (WebAuthn needs HTTPS elsewhere).
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = DEBUG
USERSESSIONS_TRACK_ACTIVITY = True

# --- The apps sign in natively (allauth headless, "app" client) and get a bot grant ---
HEADLESS_CLIENTS = ("app",)
# The site's own pages stay; headless only adds the JSON API under /api/auth/app/v1/.
HEADLESS_ONLY = False
# RSA private key (PEM) that signs the bot grants. Made on the server at first start
# (deploy/entrypoint.sh, tickrweb/grant_key.py), kept in a volume, never copied anywhere; the bot
# pins its public key.
with open(_required("TICKR_WEB_GRANT_KEY_FILE"), encoding="ascii") as _key:
    BOT_GRANT_PRIVATE_KEY = _key.read()
# The bot API, the only audience a grant is for (the bot's remote_signin_audience).
BOT_API_AUDIENCE = "https://api.tickr.bot"
# Seconds a bot grant is valid: the app redeems it at the bot right away.
BOT_GRANT_SECONDS = 60
# Apple team id that signs the apps (public: it is in every signed app). tickr.bot names it in
# /.well-known/apple-app-site-association so the apps can use passkeys for tickr.bot.
APPLE_TEAM_ID = "2C66ZTA2N4"
# The apps' bundle ids (apps/ TICKR_BUNDLE_ID_PREFIX + ".ios" / ".mac").
APPLE_APP_BUNDLE_IDS = ["bot.tickr.ios", "bot.tickr.mac"]

# --- Email: Amazon SES API with the server's instance role (no stored mail password) ---
DEFAULT_FROM_EMAIL = _required("TICKR_WEB_FROM_EMAIL")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
if _optional("TICKR_WEB_SES_REGION"):
    EMAIL_BACKEND = "django_ses.SESBackend"
    USE_SES_V2 = True
    AWS_SES_REGION_NAME = _required("TICKR_WEB_SES_REGION")
    AWS_SES_REGION_ENDPOINT = f"email.{AWS_SES_REGION_NAME}.amazonaws.com"
elif DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    raise ImproperlyConfigured("Environment variable TICKR_WEB_SES_REGION is not set.")

# --- Early-access list (tickrweb/waitlist.py) ---
# The rate-limit counters live in this process's memory: gunicorn runs ONE worker process
# (with threads), so the counts are shared by all requests. Restarting the app clears them.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
# Sign-up attempts allowed from one IP address per WAITLIST_WINDOW_SECONDS.
WAITLIST_PER_IP = 5
# Length of the per-IP window, in seconds (1 hour).
WAITLIST_WINDOW_SECONDS = 3600
# New or unconfirmed addresses accepted per WAITLIST_DAY_SECONDS (confirmation emails sent).
WAITLIST_NEW_PER_DAY = 500
# Length of that window, in seconds (1 day).
WAITLIST_DAY_SECONDS = 86400
# Seconds before the same unconfirmed address can be sent another confirmation email (1 hour).
WAITLIST_RESEND_COOLDOWN_SECONDS = 3600
# Seconds a confirmation link stays valid; unconfirmed rows older than this are pruned (7 days).
WAITLIST_CONFIRM_MAX_AGE_SECONDS = 604800

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
