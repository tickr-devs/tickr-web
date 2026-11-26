#!/bin/sh
# Nightly Postgres dump of the tickr.bot web database to S3 (run by tickr-web-backup.timer).
# The server's instance role may only put objects into the backup bucket; the bucket's lifecycle
# rule deletes old dumps. Needs: docker, aws CLI, TICKR_WEB_BACKUP_BUCKET in compose.env.
set -eu
cd "$(dirname "$0")"
: "${TICKR_WEB_BACKUP_BUCKET:?TICKR_WEB_BACKUP_BUCKET is not set}"
stamp=$(date -u +%Y-%m-%dT%H%MZ)
# Dump to a file first: a failed pg_dump stops the script (set -e) before anything is uploaded,
# where a pipe into `aws s3 cp` would upload a truncated dump and report success.
dump=$(mktemp /var/tmp/tickr-web-backup.XXXXXX)
trap 'rm -f -- "$dump"' EXIT
docker compose exec -T db pg_dump -U tickrweb --format=custom tickrweb > "$dump"
if [ ! -s "$dump" ]; then
  echo "backup ${stamp}: pg_dump wrote nothing; not uploaded." >&2
  exit 1
fi
aws s3 cp "$dump" "s3://${TICKR_WEB_BACKUP_BUCKET}/backups/tickrweb/${stamp}.dump" --only-show-errors
echo "backup ${stamp} uploaded"
