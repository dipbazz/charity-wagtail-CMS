# Running the live site

Everything whoever hosts the site needs: how the live server is set up, its settings, the
commands it relies on, backups and logs, and the step-by-step for deploying a version and
restoring a backup.

## The live server

[`deploy/aws/`](https://github.com/dipbazz/Charity-wagtail-CMS/tree/main/deploy/aws) runs the
site on one Linux server (an AWS EC2 instance) with Docker Compose. Why one server:
[Decisions](decisions.md#one-ec2-server-with-docker-compose).

- **`compose.yaml`** builds the Dockerfile's image (gunicorn with production settings) as the
  `web` service and puts **Caddy** in front. Settings come from `deploy/aws/.env` on the server
  (copy `env.example`); Compose stops with a clear message if `SITE_HOST` or `DJANGO_SECRET_KEY` is
  missing.
- **`Caddyfile`**: Caddy answers on ports 80 and 443, gets and renews the HTTPS certificate itself
  (Let's Encrypt, falling back to ZeroSSL), redirects http to https, and sets `X-Forwarded-Proto`,
  which Django trusts.
- **Data** lives in `/srv/charity/data` on the server, mounted into the container at `/data`: the
  SQLite database, uploads and the latest backup. It outlives the container, so rebuilding keeps
  everything.
- **Logs** are capped at 3 × 10 MB per container, because Docker keeps logs forever by default.
- **Timers** (`systemd/`, copied to `/etc/systemd/system/` and enabled): `charity-publish.timer`
  runs scheduled publishing every five minutes, and `charity-backup.timer` runs the backup at
  02:30 UTC (or at the next boot if the server was off).
- The Caddy image is pinned to a digest, like CI's actions ([Security](contributing/security.md)).

Server secrets live only in `deploy/aws/.env`, which is gitignored and dockerignored.

To run the same image on your own computer, see
[Getting started](getting-started/index.md#run-it-as-the-live-site-runs-it).

## On container start

The image's command runs, in order:

1. `migrate`;
2. `update_site_url`, which copies `DJANGO_SITE_URL` into the Wagtail Site record. Every full URL
   comes from that record: API links, the news feed, the sitemap, canonical and social tags;
3. gunicorn, as the container's main process, so `docker stop` lets it finish in-flight requests.

Static files are collected when the image is built, and served compressed by WhiteNoise with
hashed names, so browsers never keep stale CSS or JavaScript.

## Environment variables

Production settings (`charity.settings.production`) read everything from the environment, and
refuse to start without the required ones rather than run half-configured. The Docker image
selects them with `DJANGO_SETTINGS_MODULE`; anywhere else, set it yourself, because `manage.py`
and `wsgi.py` fall back to the development settings.

| Variable | |
|---|---|
| `DJANGO_SECRET_KEY` | **Required** |
| `DJANGO_ALLOWED_HOSTS` | **Required**: comma-separated hostnames. Without it every request would get a bare 400 |
| `DJANGO_SITE_URL` | **Required**: the public address, e.g. `https://brightwell.example`. `http(s)://host` with an optional port and no path; `https` only on port 443, because a Wagtail Site stores a port, not a scheme. Copied into the Site record on every start, and used in admin emails |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins, e.g. `https://brightwell.example` |
| `DJANGO_LANGUAGE_CODE` | The language the site opens in at `/`: `ne` (the default) or `en`. Anything else stops the app starting. Choose before adding content: changing it later changes every page's address ([Languages](site/languages.md)) |
| `DJANGO_DATA_DIR` | Where `db.sqlite3` and uploads live; must be persistent storage. The image uses `/data` |
| `DJANGO_SERVE_MEDIA` | `true` (the image's default) serves uploads from Django. Turn it off when a web server or object storage serves `/media/`, and make that refuse `/media/documents/` ([Security](contributing/security.md#documents-are-only-served-through-wagtails-document-view)) |
| `DJANGO_SECURE_HSTS_SECONDS` | HSTS duration; one hour until HTTPS is confirmed, then raise it |
| `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USE_TLS` | SMTP server for form notifications and moderation emails; port 587 and TLS by default |
| `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD` | SMTP credentials |
| `DJANGO_DEFAULT_FROM_EMAIL` | Sender address for workflow and error emails |
| `WEB_CONCURRENCY` | gunicorn's number of workers (each takes roughly 100–150 MB) |

The AWS setup builds these from a shorter `deploy/aws/.env`:

| Variable | |
|---|---|
| `SITE_HOST` | **Required**: the public hostname. Becomes the allowed host, the CSRF origin, the site URL and Caddy's certificate name |
| `DJANGO_SECRET_KEY` | **Required** |
| `BACKUP_BUCKET` | The S3 bucket backups go to |
| `DATA_DIR` | Where the data lives on the server; default `/srv/charity/data` |
| `DJANGO_SECURE_HSTS_SECONDS` | Raise to a year (31536000) once HTTPS has worked for a while |
| `WEB_CONCURRENCY` | Default 2 |

Other production behaviour:

- **HTTPS**: http is redirected, cookies are secure, and the `X-Forwarded-Proto` header from the
  proxy in front is trusted. HSTS for subdomains and preload are off (their checks are silenced),
  because they're hard to undo and can break other services on the charity's domain.
- **Uploads**: documents up to 10 MB, of the types csv, docx, key, odt, pdf, pptx, rtf, txt, xlsx
  and zip.
- CI runs Django's deployment checks against these settings, and again inside the built image.

## Management commands

Run them with `uv run python manage.py <command>` locally, or
`sudo docker compose exec web python manage.py <command>` on the server.

| Command | |
|---|---|
| `update_site_url` | Points the Wagtail Site at `SITE_URL`. Safe to run on every deploy; the image runs it on every start. Refuses a `SITE_URL` it can't store faithfully |
| `backup_site <folder>` | Writes `db.sqlite3` (a consistent copy, made with SQLite's backup API, safe while the site serves requests) and `media.tar.gz` (the uploads, under `media/`) to a folder, overwriting an earlier backup there. Refuses a folder inside the uploads, or every backup would contain the previous ones. SQLite only |
| `seed_demo` | Builds the demo charity ([Demo content](contributing/demo-content.md)). Safe to re-run: if appeals exist it adds nothing, but it always runs `update_site_url`. Refuses a Nepali-first site, because the demo is English-first |
| `publish_scheduled` | Wagtail's: publishes and unpublishes pages with a go-live or expiry time |

## Scheduled publishing

Go-live and expiry times only take effect because `publish_scheduled` runs every five minutes
(`charity-publish.timer`). Any host needs the same, with the same environment as the web process.

## Backups

`backup.sh` runs `backup_site /data/backups/latest` inside the running container, then copies the
database and uploads archive to S3 under `backups/<UTC time>/`. The server's IAM role can write and
read `backups/` but not delete, so a compromised server can't wipe them; the bucket's lifecycle
rule removes them after 30 days.

## Errors and logs

Production logs to the web container's output (#78): server errors with their traceback, and
warnings and errors from Wagtail and this project's apps, such as a form email that couldn't be
sent. Django's defaults print nothing with debug off, which is why this is configured. Nothing is
emailed.

Read them on the server with `sudo docker compose logs --tail 200 web` in `deploy/aws/`. A new app
needs its name added to the loggers in `charity/settings/production.py`.

## Email

Email isn't configured on the live server yet (#81). Until it is, form submissions are still saved
(the failed email is logged), and pages can still be submitted and approved: the mail backend
(`core/mail.py`) reports every failure to connect in a way Wagtail's moderation emails skip, with a
10-second timeout (#77). Without that, an unreachable mail server showed editors a server error and
their page wasn't submitted. The `DJANGO_EMAIL_*` variables turn email on.

## Deploy a version

Only tagged releases go live, so the live site always runs a version listed in the changelog
([Releases](contributing/releases.md)). It's done by hand on the server today; #76 plans deploying
from GitHub with a backup and an approval each time.

1. **If the version has a migration that changes existing data, back up first:**
   `sudo systemctl start charity-backup.service`, then check it with
   `journalctl -u charity-backup.service -n 20 --no-pager`.
2. **Deploy:**

   ```bash
   cd /srv/charity/app && sudo git fetch --tags && sudo git checkout vX.Y.Z
   cd deploy/aws && sudo docker compose build && sudo docker compose up -d
   sudo docker image prune -f       # remove the previous image, so the disk doesn't fill up
   ```

   `up -d` replaces the web container with a few seconds of downtime; it runs any migrations,
   then starts. Building on a small instance takes several minutes and needs swap, or it can stop
   with "Killed".
3. **Check it:** `sudo docker compose ps` (both containers up?) and
   `sudo docker compose logs --tail 100 web`, then open the pages the change touched.
4. **If something's wrong**, check out the previous tag and build again; if a migration changed
   data, restore the backup (below).

A changed file in `deploy/aws/systemd/` must be copied to `/etc/systemd/system/` again, followed
by `sudo systemctl daemon-reload`. A new variable in `env.example` must be added to the server's
`.env` by hand before `up -d`.

## Restore a backup

```{warning}
This hasn't been rehearsed on the live server yet. Practise it once on a spare server or a copy
before you need it, and update this section with anything that turns out different.
```

Each backup is a folder `s3://<bucket>/backups/<UTC time>/` with `db.sqlite3` and `media.tar.gz`.

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

Stopping `web` first means nothing writes to the database while it's replaced; Caddy shows an error
page until it's back. Then check the logs, that the site loads and images display. Anything
published or uploaded after the backup's time is gone.

**To move the site to another host**, put `db.sqlite3` and the unpacked `media/` folder in the
directory mounted as `/data`, then start the image with the environment variables above.
