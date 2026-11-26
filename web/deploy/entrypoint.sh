#!/bin/sh
# Loads the secrets file (NAME='value' lines, mounted read-only) into this process only, so the
# values never appear in `docker inspect`. Then applies migrations and starts the given command.
set -eu
if [ -n "${TICKR_WEB_ENV_FILE:-}" ]; then
  if [ ! -r "$TICKR_WEB_ENV_FILE" ]; then
    echo "TICKR_WEB_ENV_FILE is set but the file cannot be read." >&2
    exit 2
  fi
  set -a
  . "$TICKR_WEB_ENV_FILE"
  set +a
fi
if [ -r /run/secrets/db_password ]; then
  TICKR_WEB_DB_PASSWORD=$(cat /run/secrets/db_password)
  export TICKR_WEB_DB_PASSWORD
fi
/venv/bin/python /app/manage.py migrate --noinput
exec "$@"
