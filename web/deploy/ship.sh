#!/bin/sh
# Ship a release of the tickr.bot web server, from the Mac (owner):
#   web/deploy/ship.sh [SITE_DIR]
# Packs web/ at the current commit (a clean tree only), uploads it, and with SITE_DIR also the
# built public site (python3 web/site/build.py makes web/site/out/site). Then runs tickr-web-deploy on the server over
# SSM and prints its output. Needs: aws CLI signed in (profile from AWS_PROFILE) and a clone of
# tickr-infra whose ops/aws/web holds the web server's terraform state (instance id and bucket):
# next to this repo by default (../tickr-infra), or TICKR_INFRA_DIR.
set -eu
# No pager: AWS CLI v2 otherwise shows the final result in `less`, which waits for a key press.
export AWS_PAGER=""
here=$(cd "$(dirname "$0")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)
infra="${TICKR_INFRA_DIR:-$repo/../tickr-infra}/ops/aws/web"
if [ ! -d "$infra" ]; then
  echo "No tickr-infra clone at $infra: clone tickr-devs/tickr-infra next to this repo or set TICKR_INFRA_DIR." >&2
  exit 1
fi
if ! git -C "$repo" diff --quiet HEAD -- web; then
  echo "web/ has uncommitted changes: commit them first." >&2
  exit 1
fi
# Only reviewed code reaches the server: HEAD must be on main as GitHub has it.
git -C "$repo" fetch --quiet origin main
if ! git -C "$repo" merge-base --is-ancestor HEAD origin/main; then
  echo "HEAD is not on origin/main: ship only merged commits (git switch main && git pull)." >&2
  exit 1
fi
instance=$(terraform -chdir="$infra" output -raw instance_id)
bucket=$(terraform -chdir="$infra" output -raw bucket)
commit=$(git -C "$repo" rev-parse --short HEAD)
stamp=$(date -u +%Y%m%dT%H%M%SZ)
app_key="web-$stamp-$commit.tgz"
git -C "$repo" archive --format=tar.gz HEAD:web | aws s3 cp - "s3://$bucket/releases/$app_key" --only-show-errors
site_key=""
if [ $# -ge 1 ]; then
  if [ ! -f "$1/index.html" ] || [ ! -f "$1/404.html" ]; then
    echo "$1 is not a built site (index.html and 404.html missing)." >&2
    exit 1
  fi
  site_key="site-$stamp.tgz"
  # COPYFILE_DISABLE: macOS tar would otherwise add ._* files, which would then be published.
  COPYFILE_DISABLE=1 tar -czf - -C "$1" . | aws s3 cp - "s3://$bucket/releases/$site_key" --only-show-errors
fi
command_id=$(aws ssm send-command --instance-ids "$instance" \
  --document-name AWS-RunShellScript \
  --comment "tickr-web $commit" \
  --parameters "commands=[\"/usr/local/bin/tickr-web-deploy $app_key $site_key\"]" \
  --query Command.CommandId --output text)
echo "Deploying $commit (command $command_id)..."
# The first build takes a few minutes; `aws ssm wait` gives up sooner, so poll the status.
while :; do
  sleep 10
  status=$(aws ssm get-command-invocation --command-id "$command_id" --instance-id "$instance" \
    --query Status --output text 2>/dev/null || echo Pending)
  case "$status" in Pending|InProgress|Delayed) ;; *) break ;; esac
done
aws ssm get-command-invocation --command-id "$command_id" --instance-id "$instance" \
  --query '[Status, StandardOutputContent, StandardErrorContent]' --output text
