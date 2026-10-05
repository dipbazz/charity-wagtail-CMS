# Restore a backup

How to put the live site back to a nightly backup. [Deployment](../topics/deployment.md#backups)
explains what the backups contain and where they go.

```{warning}
This procedure hasn't been rehearsed on the live server yet. A backup that has never been
restored is only a hope: practise it once on a spare server or a copy before you need it, and
update this page with anything that turns out different.
```

## What a backup holds

Each backup is a folder in S3, `s3://<bucket>/backups/<UTC time>/`, with:

- `db.sqlite3`: a consistent copy of the database;
- `media.tar.gz`: every upload, under a top-level `media/` folder.

Backups are kept for 30 days.

## Restore on the server

```bash
B=your-bucket-name
aws s3 ls s3://$B/backups/                            # pick a time
mkdir -p /tmp/restore && aws s3 cp --recursive s3://$B/backups/TIME/ /tmp/restore/

cd /srv/charity/app/deploy/aws
sudo docker compose stop web
sudo cp /tmp/restore/db.sqlite3 /srv/charity/data/db.sqlite3
sudo rm -rf /srv/charity/data/media && sudo tar -xzf /tmp/restore/media.tar.gz -C /srv/charity/data
sudo chown -R 1000:1000 /srv/charity/data      # the container runs as user 1000
sudo docker compose start web
```

Stopping `web` first means nothing writes to the database while it's replaced. Caddy keeps
running and shows an error page until `web` is back.

## Check it

- `sudo docker compose logs --tail 100 web` shows migrations and gunicorn starting cleanly.
- The site loads, recent pages are as they were at the backup's time, and images display.
- Anything published or uploaded after the backup's time is gone and has to be redone.

## Restore somewhere else

The site is one Docker image plus that folder, so a backup can move it to any host with Docker:
put `db.sqlite3` and the unpacked `media/` folder in the directory mounted as `/data`
(`DJANGO_DATA_DIR`), then start the image with the settings in the
[settings reference](../reference/settings.md).
