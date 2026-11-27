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
# One point for the alarm tickr-web-backup-missing (tickr-infra ops/aws/web/main.tf): no point for a day means
# no dump reached S3. The region is this machine's own, read from the instance metadata (IMDSv2).
imds=http://169.254.169.254/latest
token=$(curl -sSf -X PUT "$imds/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
region=$(curl -sSf -H "X-aws-ec2-metadata-token: $token" "$imds/meta-data/placement/region")
if ! aws cloudwatch put-metric-data --region "$region" --namespace Tickr/Web --metric-name BackupUploaded --value 1; then
  echo "backup ${stamp}: the dump IS in S3, but the alarm's metric was not sent (tickr-web-backup-missing will fire)." >&2
  exit 1
fi
