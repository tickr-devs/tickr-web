# tickr.bot web app image: gunicorn serving Django. Caddy (deploy/compose.yaml) is in front.
FROM python:3.12-slim-bookworm

# The uv release CI uses, so the image installs exactly what uv.lock pins.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/venv UV_NO_CACHE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY manage.py ./
COPY tickrweb ./tickrweb
COPY locale ./locale
COPY deploy/entrypoint.sh /entrypoint.sh

# collectstatic needs settings but no secrets: build-only placeholder values, never used at run time.
RUN TICKR_WEB_HOST=build TICKR_WEB_SECRET_KEY=build TICKR_WEB_FROM_EMAIL=build@example.com \
    TICKR_WEB_DB_NAME=build TICKR_WEB_DB_USER=build TICKR_WEB_DB_HOST=build TICKR_WEB_DB_PORT=5432 \
    TICKR_WEB_DEBUG=1 /venv/bin/python manage.py collectstatic --noinput -v0

# Must equal service_uid in ops/aws/web/variables.tf: the server's account with that uid owns the
# secrets file and the database password (mode 600), bind-mounted into this container.
RUN groupadd --system --gid 10001 web && useradd --system --uid 10001 --gid 10001 --no-create-home web
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
# One worker process: the waitlist's rate-limit counters live in its memory (settings.CACHES).
# Threads serve requests in parallel. Seconds before a stuck request is killed: 30.
# The access log has no client address and no query string: waitlist links carry the address in
# their signed token, and the privacy page promises that IPs are never stored with an email.
CMD ["/venv/bin/gunicorn", "tickrweb.wsgi", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "30", "--access-logfile", "-", "--access-logformat", "%(t)s \"%(m)s %(U)s\" %(s)s %(b)s %(L)ss"]
