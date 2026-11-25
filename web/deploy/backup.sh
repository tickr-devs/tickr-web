#!/bin/sh
# Nightly Postgres dump of the tickr.bot web database to S3 (run by tickr-web-backup.timer).
# The server's instance role may only put objects into the backup bucket; the bucket's lifecycle
# rule deletes old dumps. Needs: docker, aws CLI, TICKR_WEB_BACKUP_BUCKET in compose.env.
set -eu
cd "$(dirname "$0")"
: "${TICKR_WEB_BACKUP_BUCKET:?TICKR_WEB_BACKUP_BUCKET is not set}"
stamp=$(date -u +%Y-%m-%dT%H%MZ)
docker compose exec -T db pg_dump -U tickrweb --format=custom tickrweb \
  | aws s3 cp - "s3://${TICKR_WEB_BACKUP_BUCKET}/backups/tickrweb/${stamp}.dump" --only-show-errors
echo "backup ${stamp} uploaded"
