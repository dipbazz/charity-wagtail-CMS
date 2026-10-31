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
  which Django trusts. It refuses a request over 12 MB (the admin's images and documents are up
  to 10 MB, a receipt screenshot 5 MB): Django writes an upload to a temporary file before any
  form checks its size, so without a limit one request could fill the disk. Any other host's web
  server needs the same limit.
- **Data** lives in `/srv/charity/data` on the server, mounted into the container at `/data`: the
  SQLite database, uploads, supporters' receipt screenshots (`receipts/`, readable by the
  container's user only) and the latest backup. It outlives the container, so rebuilding keeps
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
| `DJANGO_PAYMENT_<PROVIDER>_<KEY>` | A payment provider's merchant keys, such as `DJANGO_PAYMENT_KHALTI_SECRET_KEY` ([Paying pledges online](#paying-pledges-online)). A provider is offered once all its keys are set; an empty value is a key not set |
| `DJANGO_LIVE_PAYMENTS` | `true` takes real money. Anything else, or nothing, uses the providers' test systems |
| `WEB_CONCURRENCY` | gunicorn's number of workers (each takes roughly 100–150 MB) |

The AWS setup builds these from a shorter `deploy/aws/.env`:

| Variable | |
|---|---|
| `SITE_HOST` | **Required**: the public hostname. Becomes the allowed host, the CSRF origin, the site URL and Caddy's certificate name |
| `DJANGO_SECRET_KEY` | **Required** |
| `BACKUP_BUCKET` | The S3 bucket backups go to |
| `DATA_DIR` | Where the data lives on the server; default `/srv/charity/data` |
| `DJANGO_LANGUAGE_CODE` | The language the site opens in: `ne` (the default) or `en` |
| `DJANGO_SECURE_HSTS_SECONDS` | Raise to a year (31536000) once HTTPS has worked for a while |
| `WEB_CONCURRENCY` | Default 2 |
| `DJANGO_PAYMENT_<PROVIDER>_<KEY>`, `DJANGO_LIVE_PAYMENTS` | As above. The `web` service reads the whole `.env` (`env_file` in `compose.yaml`), so a new provider's keys need no change to `compose.yaml` |

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
| `delete_old_receipts` | Deletes the receipt screenshots supporters sent with a QR payment more than 30 days ago that nobody has marked paid or not found (the payment stays To confirm), and any screenshot file that old that no payment points at. `backup.sh` runs it after the backup, every night |
| `seed_demo` | Builds the demo charity ([Demo content](contributing/demo-content.md)). Safe to re-run: if appeals exist it adds nothing, but it always runs `update_site_url`. Refuses a Nepali-first site, because the demo is English-first |
| `new_site --name-ne <name> --name-en <name> [--email <address>] [--phone <number>]` | Sets up a new charity's site in one transaction: the standard pages that exist today as drafts in the main language, a live home page in each language, the Site's name, Site settings' names, the contact details given, and the Donate and privacy choosers. Lists each page, then what's still to do. Restart the site afterwards (with Docker, `docker compose restart web`): the running site keeps its list of home pages in its own memory for up to an hour, so until then the second language's home page redirects to the main one and the language switcher stays hidden. Refuses, changing nothing and exiting non-zero, when any page exists under either home page, or when the email or phone given isn't one. Nothing made up is written: a charity's address, registration and payment details stay empty ([The charity site standard](site/standard.md#how-its-kept)) |
| `publish_scheduled` | Wagtail's, wrapped by `core`: publishes and unpublishes pages with a go-live or expiry time, except a page that can't go live and a privacy notice that forms link to. Each of those is left as it is with its time cleared, a warning in the log and a History entry ([Pages and content](site/pages-and-content.md#what-stops-a-page-going-live)). `--dryrun` lists what it would do |

## Scheduled publishing

Go-live and expiry times only take effect because `publish_scheduled` runs every five minutes
(`charity-publish.timer`). Any host needs the same, with the same environment as the web process.

## Backups

`backup.sh` runs `backup_site /data/backups/latest` inside the running container, copies the
database and uploads archive to S3 under `backups/<UTC time>/`, then runs `delete_old_receipts`.
The clean-up comes last so a failure there can't stop the backup; it still fails the run, which
`journalctl -u charity-backup.service` shows. The server's IAM role can write and read `backups/`
but not delete, so a compromised server can't wipe them; the bucket's lifecycle rule removes them
after 30 days.

**Receipt screenshots aren't backed up.** They're kept in `receipts/` beside `media/` in the data
directory, which no address serves and the uploads archive doesn't include, so a deleted
screenshot is gone for good, as the privacy notice promises. A restore onto a new server, or after
the data directory is lost, loses the screenshots nobody has checked yet. Their payments are still
To confirm, with the transaction ID if the supporter gave one; for the rest, find the payment by
its pledge number in your statement.

## Errors and logs

Production logs to the web container's output (#78): server errors with their traceback, and
warnings and errors from Wagtail and this project's apps, such as a form email that couldn't be
sent. Django's defaults print nothing with debug off, which is why this is configured. Nothing is
emailed.

Read them on the server with `sudo docker compose logs --tail 200 web` in `deploy/aws/`. A new app
needs its name added to the loggers in `charity/settings/production.py`.

A line such as `WARNING core.limits: Too many tries at pledge from one connection: over 10 in 300
seconds.` means one connection hit a limit on the public pages; many of them at once is a flood,
an odd one a busy appeal ([Security](contributing/security.md#one-connection-can-only-try-so-often)).

## The visitor's address

The limits count per visitor, by the address Caddy sends as `X-Real-IP` (`header_up X-Real-IP
{client_ip}` in `deploy/aws/Caddyfile`, and in the Caddy config in `compose.yaml`). Caddy
replaces any `X-Real-IP` a visitor sends. Any other web server in front of the site must set the
same header the same way: without it nothing is limited, and the logs say
`No HTTP_X_REAL_IP on the request` once every five minutes.

Behind Cloudflare (or any other proxy), tell Caddy to trust it, and `{client_ip}` becomes the
visitor's address again with no change to Django: a global `servers` block with
`trusted_proxies static <Cloudflare's ranges>` and `client_ip_headers CF-Connecting-IP`.

## Paying pledges online

Each charity's installation offers the payment providers it has merchant accounts for
([Paying a pledge](site/appeals-and-giving.md#paying-a-pledge)). A provider is offered once all
its keys are set, as `DJANGO_PAYMENT_<PROVIDER>_<KEY>`. With only some of them set, Django's
checks stop the site starting (`migrate` runs them as the container starts), so a provider half set
up can't go unnoticed; a key that matches no provider, such as a misspelling, is a warning.

| Provider | Keys | Where the charity gets them |
|---|---|---|
| eSewa | `DJANGO_PAYMENT_ESEWA_PRODUCT_CODE`, `DJANGO_PAYMENT_ESEWA_SECRET_KEY` | A merchant agreement with eSewa. Its test system's keys are published (`EPAYTEST`), and development uses them unless others are set |
| Khalti | `DJANGO_PAYMENT_KHALTI_SECRET_KEY` | admin.khalti.com for live payments; test-admin.khalti.com for its test system |

A provider added later lists its keys here.

**Test or live:** payments use each provider's test system, where no money moves, until
`DJANGO_LIVE_PAYMENTS=true`, and the pay page says so while they do. Set it only together with the
charity's live merchant keys: test keys don't work on the live systems, nor live keys on the test
ones. Payments made in a test system are marked "(test)" in the admin's export, and aren't checked
with the live system later.

The keys are secrets: they go in the server's `.env` only, never in git, a chat or the admin.

**A slow provider:** starting a Khalti payment, and checking any payment when the payer comes
back, asks the provider while the payer waits. The site gives up after 10 seconds without a word
from the provider (`TIMEOUT` in `nepal_payments/http.py`). That's a limit on each wait, not on the
whole answer: a provider that answers very slowly, a little at a time, can take longer, and
looking up its address has no limit of its own. Each of the site's two web workers
(`WEB_CONCURRENCY`) answers one visitor at a time, so if eSewa or Khalti stops answering and two
payers come back within those seconds, every visitor to the site waits until one of them is done. Nothing is lost: the payment
stays waiting, and the payer can check it again from the pay page. With a charity's few payments
a day this is rare enough to leave as it is; a third worker would take another 100–150 MB.

### Turn on real money

For each charity, once, when it's ready to take real payments. Until the last step its site keeps
using the test systems, so nothing here can take money early.

1. **The charity has a merchant account** with each provider it will offer, and its live keys:
   eSewa's product code and secret key from its merchant agreement, Khalti's live secret key from
   admin.khalti.com. Offer only the providers it has an account with.
2. **Try each provider in test mode on the live site,** with its test keys set (the table above
   says where they come from): pay a pledge with the provider's test account
   ([Paying a pledge](site/appeals-and-giving.md#paying-a-pledge)) and check that **Pledges**
   lists it as **Paid (test)**.
3. **In one edit of `deploy/aws/.env`,** replace each provider's test keys with its live keys and
   set `DJANGO_LIVE_PAYMENTS=true`. Never one without the other: test keys don't work on the live
   systems, nor live keys on the test ones, so every payment would fail.
4. **Apply it:** `sudo docker compose up -d` in `deploy/aws/` (the `web` container is recreated
   with the new `.env`), then `sudo docker compose logs --tail 100 web`. A provider with only some
   of its keys stops the site starting, with `campaigns.E001` in the log.
5. **Make one small real payment** with each provider (Khalti takes Rs 10 or more), and check that
   **Pledges** lists it as **Paid**, without "(test)", and that its transaction ID matches the
   provider's merchant portal. The pledge can't be deleted afterwards (it's the record of real
   money); refund it from the provider's portal if the charity wants the money back.

**To go back to test mode,** set `DJANGO_LIVE_PAYMENTS=false`, put the test keys back, and run step
4 again. Payments started in live mode aren't checked against the test systems, so any still
waiting must be looked up in the provider's merchant portal.

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
by `sudo systemctl daemon-reload`. A changed `Caddyfile` takes effect only after
`sudo docker compose exec -w /etc/caddy caddy caddy reload` (`up -d` leaves Caddy running with the
old one). A new variable in `env.example` must be added to the server's
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
published or uploaded after the backup's time is gone. `receipts/` isn't in the backup: on the
same server it's left as it was, and on a new one the screenshots nobody had checked are lost
(see Backups).

**To move the site to another host**, put `db.sqlite3` and the unpacked `media/` folder in the
directory mounted as `/data`, then start the image with the environment variables above.
