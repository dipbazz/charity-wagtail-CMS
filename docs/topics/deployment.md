# Deployment

How the live site runs, and what any host needs. [Deploy a change](../how-to/deploy-a-change.md)
and [Restore a backup](../how-to/restore-a-backup.md) are the step-by-step guides.

## The live server

[`deploy/aws/`](https://github.com/dipbazz/Charity-wagtail-CMS/tree/main/deploy/aws) runs the
site on a single Linux server (an AWS EC2 instance) with Docker Compose:

- **`compose.yaml`** builds the Dockerfile's image (gunicorn with production settings) as the
  `web` service and puts **Caddy** in front. Settings come from `deploy/aws/.env` on the server;
  copy `env.example` to start it. Compose stops with a clear message if `SITE_HOST` or
  `DJANGO_SECRET_KEY` is missing.
- **`Caddyfile`**: Caddy answers on ports 80 and 443, gets and renews the HTTPS certificate
  itself (Let's Encrypt, falling back to ZeroSSL), redirects http to https, and sets
  `X-Forwarded-Proto`, which Django trusts (`SECURE_PROXY_SSL_HEADER`).
- **Data** lives in `/srv/charity/data` on the server (`DATA_DIR` in `.env`), mounted into the
  container at `/data`: the SQLite database, uploads and the latest backup. It outlives the
  container, so rebuilding or recreating it keeps everything.
- **Logs** are capped at 3 × 10 MB per container, because Docker keeps logs forever by default.
- **`systemd/`** has two timers. Copy them to `/etc/systemd/system/` and enable them:
  - `charity-publish.timer` runs `publish_scheduled` every five minutes. Without it, pages with
    a go-live or expiry time never change.
  - `charity-backup.timer` runs `backup.sh` at 02:30 UTC (or at the next boot if the server was
    off).

Server secrets live in `deploy/aws/.env`, which is gitignored and dockerignored
(`charity/tests/test_deploy.py` checks both). CI checks the deployment too: `docker compose
config` and `caddy validate` must pass.

The choice of one server is recorded in [One EC2 server](../decisions/single-server.md).

## Running the image on your own computer

`compose.yaml` in the project root (not `deploy/aws/`) runs the same Docker image with
production settings, the demo content and a throwaway data volume, behind a small Caddy proxy
that stands in for the live server's. Its secret key and hosts are for your computer only; see
[Getting started](../getting-started/index.md#run-it-as-the-live-site-runs-it).

## On container start

The Docker image's command runs, in order:

1. `manage.py migrate`;
2. `manage.py update_site_url`, which copies `DJANGO_SITE_URL` into the Wagtail `Site` record.
   Every full URL comes from that record: API links, the news feed, the sitemap, canonical and
   social tags;
3. gunicorn, as PID 1, so `docker stop` lets it finish in-flight requests.

## Backups

`backup.sh` runs `manage.py backup_site /data/backups/latest` inside the running container. That
writes a consistent copy of the SQLite database (`db.sqlite3`, through SQLite's backup API, so it
never catches a write halfway through) and an archive of the uploads (`media.tar.gz`). The
script then copies both to S3 under `backups/<UTC time>/`.

The server's IAM role can write and read `backups/` but not delete, so a compromised server
can't wipe the backups. The bucket's lifecycle rule removes them after 30 days.

## Errors and logs

Production's `LOGGING` writes to the web container's output (#78):

- server errors (500s) from `django.request`, with their traceback;
- WARNING and above from `wagtail` and this project's apps, such as a form email that couldn't
  be sent.

On the server, read them with `sudo docker compose logs --tail 200 web` in `deploy/aws/`.
Docker keeps the last 30 MB per container. Nothing is emailed: `ADMINS` is empty. Django's
defaults print nothing with `DEBUG` off, which is why this is configured.

A new app needs its name added to the loggers in `charity/settings/production.py`.

## Email

Email isn't configured on the live server yet (Epic #81). Until it is:

- form submissions are still saved and listed in the admin, and the failed email is logged;
- pages can still be submitted for moderation and approved. The production mail backend,
  `core.mail.SMTPBackend`, reports every failure to connect as a `ConnectionError`, which
  Wagtail's moderation emails skip (#77). Without it, an unreachable mail server showed editors
  a server error and their page wasn't submitted.

The `DJANGO_EMAIL_*` variables in the [settings reference](../reference/settings.md) turn it on.

## Notes for any host

These apply wherever the Docker image runs, not only on the EC2 server.

- **Settings:** production settings (`charity.settings.production`) read configuration from
  `DJANGO_*` environment variables. The Docker image selects them with `DJANGO_SETTINGS_MODULE`;
  anywhere else, set that variable yourself, because `manage.py` and `wsgi.py` fall back to the
  dev settings.
- **Persistent storage:** `DJANGO_DATA_DIR` holds `db.sqlite3` and uploaded media, so it must be
  persistent storage. The Docker image uses a `/data` volume.
- **Uploads:** `core.views.serve_media` serves them when `DJANGO_SERVE_MEDIA` is on (the Docker
  image's default). Turn it off when a web server or object storage serves `/media/`, and have
  that refuse `/media/documents/`; see [Security](security.md#documents-are-only-served-through-wagtails-document-view).
- **Static files** are compressed and served by [WhiteNoise](https://whitenoise.readthedocs.io/),
  with hashed names so browsers never keep stale CSS or JavaScript. No separate web server is
  needed for them.
- **Scheduled publishing** needs `python manage.py publish_scheduled` every few minutes, with the
  same environment as the web process.
- **The Dockerfile** is based on the Wagtail project template. CI builds it and runs Django's
  deployment checks inside the image.
