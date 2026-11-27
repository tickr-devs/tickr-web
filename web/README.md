# tickr.bot web app

Django + Postgres app behind the public site. It runs on its **own server**, never beside the
trading bot (owner decision 2026-11-25): a break-in through the website must not reach the broker
keys. It imports nothing from `src/tickr`.

## What lives where on tickr.bot

| Path | Served by |
|---|---|
| `/`, `/how-it-works/`, … | Static marketing pages (built separately), served by Caddy |
| `/static/` | This app's CSS and allauth's scripts (`collectstatic`), served by Caddy |
| `/login` | Sign-in: password, passkey, or a code emailed to you |
| `/account/…` | allauth: passkeys, password, emailed codes, signed-in devices |
| `/app` | The cabinet (signed in only): Overview, Security, Devices |
| `/app/early-access`, `/app/people` | Admin sections of the cabinet (admins only) |
| `/api/auth/app/v1/…`, `/api/app/…`, `/.well-known/apple-app-site-association` | The apps' native sign-in (below) |
| `/api/…` | JSON endpoints; `/api/healthz` answers `ok` |

Public pages must not use `/login`, `/account`, `/app`, `/api` or `/static`.

## Behind the proxy

Exactly one proxy, Caddy, sits in front of gunicorn (`ALLAUTH_TRUSTED_PROXY_COUNT = 1`), and
allauth's per-IP sign-in limits take the last `X-Forwarded-For` entry as the visitor. That holds
only if:
- gunicorn is reachable by Caddy alone (loopback, a unix socket, or a container network with
  no published port), so nobody can call it directly with a made-up header;
- Caddy overwrites `X-Forwarded-For` with the address it saw and never passes on one the client
  sent.

## Accounts

Public sign-up is closed. People join the early-access list on the site. An admin opens
**Early access** in the cabinet, ticks confirmed addresses and presses **Invite selected**: each
gets an account and an email that says to sign in at `/login` (an address that already has an
account, or is not confirmed, is skipped; if the email fails, no account is left).

An admin is an account with `is_staff` and `is_superuser`; everyone else is a member. Admins see
two more sections in the same cabinet, **Early access** and **People**, and they open only in a
session signed in with a passkey or an authenticator app (members and other sessions get 403).
On **People** an admin makes another account an admin or removes the role (`tickrweb/roles.py`);
only an account that already has a passkey or an authenticator app can be made admin.
The last admin cannot be removed, and every change is emailed to all admins and the person.

The first admin, who has nobody to invite them, is made with
`python manage.py invite you@example.com --superuser`, which creates an account with a verified
address and no password and sends no email. Its owner signs in at `/login` with an emailed code,
then adds a passkey under Security.

## The apps' sign-in

The Mac and iPhone apps sign in with their own screens through allauth's headless JSON API for the
"app" client (`/api/auth/app/v1/…`, session in the `X-Session-Token` header): passkey, email +
password, or a code by email, then an authenticator code or a passkey when the account asks for a
second step. Then `POST /api/app/bot-grant` (`tickrweb/grants.py`) gives a 60-second RS256 JWT,
the bot grant (`iss` https://tickr.bot, `aud` [https://api.tickr.bot], `sub` = account id,
`client_id` tickr-ios or tickr-mac, `jti`), which the app hands to the bot once. Only an admin
whose session was signed in with a passkey or an authenticator app gets one. The bot checks it
offline with the public key from `/api/app/grant-key.pem`, pinned in its config; tickr.bot never
calls the bot. `/.well-known/apple-app-site-association` names the apps (team id in settings) so
they can use passkeys for tickr.bot.

The signing key is made by the app container at its first start (`deploy/entrypoint.sh`,
`tickrweb/grant_key.py`) in the `grant-key` volume and never leaves the server. It is not in the
database backups: a rebuilt server (or a lost `grant-key` volume) makes a new key at the next
start, and the bot then refuses every app sign-in until its pinned PEM is replaced with the new
`/api/app/grant-key.pem`. Every grant is emailed to all admins.

## Configuration

`tickrweb/settings.py` is the configuration; every number in it has a comment. Per-server values
and secrets come from environment variables, read by name; a missing one refuses the start and
names the variable:

| Variable | What |
|---|---|
| `TICKR_WEB_HOST` | Public host, e.g. `tickr.bot` |
| `TICKR_WEB_SECRET_KEY` | Django secret key (secret) |
| `TICKR_WEB_DB_NAME`, `TICKR_WEB_DB_USER`, `TICKR_WEB_DB_HOST`, `TICKR_WEB_DB_PORT` | Postgres |
| `TICKR_WEB_DB_PASSWORD` | Postgres password (secret; optional with peer/trust auth) |
| `TICKR_WEB_FROM_EMAIL` | Sender, e.g. `tickr.bot <hello@tickr.bot>` |
| `TICKR_WEB_SES_REGION` | Amazon SES region, e.g. `us-east-1`; mail is sent with the server's instance role |
| `TICKR_WEB_DEBUG` | `1` only on a developer machine |

## Tests

```sh
cd web
uv sync
export TICKR_WEB_DB_NAME=tickrweb TICKR_WEB_DB_USER=postgres TICKR_WEB_DB_HOST=127.0.0.1 TICKR_WEB_DB_PORT=5432
uv run pytest -q
```

CI runs the same in the `web-tests` job against a Postgres 16 service.

Spanish texts: `locale/es/LC_MESSAGES/django.po`; after editing it run
`uv run python manage.py compilemessages --settings tickrweb.settings_test -i .venv`.
