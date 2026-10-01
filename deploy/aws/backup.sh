#!/bin/sh
# Nightly backup: a consistent copy of the database and an archive of the uploads, made inside
# the running container, then copied to S3 under backups/<UTC time>/. The server's IAM role may
# write and read backups/ but not delete, so a compromised server can't wipe them; the bucket's
# lifecycle rule removes them after 30 days. Run nightly by systemd/charity-backup.timer.
set -eu

cd "$(dirname "$0")"
setting() { sed -n "s/^$1=//p" .env | tail -n 1; }
bucket=$(setting BACKUP_BUCKET)
data_dir=$(setting DATA_DIR)
data_dir=${data_dir:-/srv/charity/data}
[ -n "$bucket" ] || { echo "Set BACKUP_BUCKET in $(pwd)/.env" >&2; exit 1; }

docker compose exec -T web python manage.py backup_site /data/backups/latest

stamp=$(date -u +%Y-%m-%dT%H%M%SZ)
aws s3 cp --recursive --only-show-errors "$data_dir/backups/latest" "s3://$bucket/backups/$stamp/"
echo "Backed up to s3://$bucket/backups/$stamp/"
