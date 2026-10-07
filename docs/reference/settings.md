# Settings and environment variables

The settings modules, the project's own settings, and the environment variables production
reads.

## Settings modules

| Module | Used by | Differences from `base` |
|---|---|---|
| `charity.settings.base` | the others | Apps, middleware, templates, Wagtail settings, SQLite at `BASE_DIR / "db.sqlite3"` |
| `charity.settings.dev` | `manage.py` and `wsgi.py` by default | `DEBUG = True`, any host, `SERVE_MEDIA = True`, console mailer, django-debug-toolbar for `127.0.0.1`. Opens in English unless `DJANGO_LANGUAGE_CODE=ne`, in the shell or in `.env.local` (copy `.env.example`) |
| `charity.settings.test` | pytest (`pyproject.toml`) | `DEBUG = False`, MD5 password hashing, `InMemoryStorage` for media, locmem mailer |
| `charity.settings.production` | the Docker image (`DJANGO_SETTINGS_MODULE`) | Everything below from the environment; HTTPS and secure cookies; WhiteNoise; logging to stderr |

Django 6.1 configures email with `MAILERS`, not `EMAIL_BACKEND`.

## Project settings

| Setting | |
|---|---|
| `SITE_URL` | The site's public address, without a trailing slash. `update_site_url` copies it into the default Wagtail `Site`, which every full URL is built from. Defaults to `http://localhost:8000` |
| `WAGTAILADMIN_BASE_URL` | Set to `SITE_URL`; used in admin emails |
| `SERVE_MEDIA` | When on, `core.views.serve_media` serves uploads (never `documents/`). Off in `base`, on in `dev`, from `DJANGO_SERVE_MEDIA` in production |
| `WAGTAILIMAGES_IMAGE_MODEL` | `core.CustomImage`. Hard to change once images exist |
| `WAGTAILSEARCH_BACKENDS` | Wagtail's database backend |
| `WAGTAILDOCS_EXTENSIONS` | Allowed document types: csv, docx, key, odt, pdf, pptx, rtf, txt, xlsx, zip |
| `WAGTAILDOCS_MAX_UPLOAD_SIZE` | 10 MB |
| `LANGUAGE_CODE` | The main language, served at `/`. `en` in development and tests, where the Brightwell demo is English-first; production reads `DJANGO_LANGUAGE_CODE`, Nepali by default. It must match a code in `LANGUAGES` exactly; a variant such as `en-gb` would put every page under a prefix |
| `LANGUAGES`, `WAGTAIL_CONTENT_LANGUAGES` | Nepali (`ne`) and English (`en`). The language that isn't the main one is served under its prefix, `/en/` or `/ne/` |
| `WAGTAIL_I18N_ENABLED` | On: one page tree per language. See [Architecture](../topics/architecture.md#languages) |
| `FORMAT_MODULE_PATH` | `charity.formats`, which keeps British date and number formats for `en` |
| `TIME_ZONE` | `Asia/Kathmandu` (scheduled publishing and admin times are Nepal time) |

## Production environment variables

Production settings (`charity.settings.production`) read these. The Docker image selects those
settings with `DJANGO_SETTINGS_MODULE`; anywhere else, set that variable yourself, because
`manage.py` and `wsgi.py` fall back to the dev settings.

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Required; the app refuses to start without it |
| `DJANGO_ALLOWED_HOSTS` | Required; comma-separated hostnames. The app refuses to start without it, because otherwise every request gets a bare 400 Bad Request |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins, e.g. `https://brightwell.example` |
| `DJANGO_SITE_URL` | Required; the public address, e.g. `https://brightwell.example`. The Docker image copies it into Wagtail's Site record on every start (`manage.py update_site_url`), which all full URLs are built from: API links, the news feed, the sitemap, canonical and social tags. Admin emails use it too |
| `DJANGO_SECURE_HSTS_SECONDS` | HSTS duration; defaults to one hour until HTTPS is confirmed |
| `DJANGO_LANGUAGE_CODE` | The language the site opens in at `/`: `ne` (the default) or `en` for an English-first site such as the Brightwell demo. Anything else stops the app starting. Choose it before adding content: changing it later changes every page's address |
| `DJANGO_EMAIL_HOST` | SMTP server for form notifications and workflow emails. If it's unreachable, form submissions are still saved, pages can still be submitted and approved, and the error is logged |
| `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USE_TLS` | Defaults: `587` and `true` |
| `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD` | SMTP credentials |
| `DJANGO_DEFAULT_FROM_EMAIL` | Sender address for workflow and error emails |
| `DJANGO_DATA_DIR` | Directory for `db.sqlite3` and uploaded media; must be persistent storage. The Docker image uses a `/data` volume |
| `DJANGO_SERVE_MEDIA` | `true` serves uploads from Django (the Docker image's default). Turn it off when a web server or object storage serves `/media/`, and have it refuse `/media/documents/` (see [Security](../topics/security.md#documents-are-only-served-through-wagtails-document-view)) |
| `WEB_CONCURRENCY` | gunicorn's number of workers |

Other production behaviour:

- **HTTPS:** `SECURE_SSL_REDIRECT`, secure session and CSRF cookies, and
  `SECURE_PROXY_SSL_HEADER` trusting `X-Forwarded-Proto` from the proxy in front. HSTS for
  subdomains and preload are left off (their checks are silenced), because they're hard to undo
  and can break other services on the charity's domain.
- **Email:** the mailer is `core.mail.SMTPBackend`, Django's SMTP backend reporting every
  failure to connect as a `ConnectionError`, with a 10-second timeout, so an unreachable mail
  server doesn't stop moderation (#77). See [Deployment](../topics/deployment.md#email).
- **Static files:** WhiteNoise with `CompressedManifestStaticFilesStorage`.
- **Logging:** see [Deployment](../topics/deployment.md#errors-and-logs).

## The AWS deployment's `.env`

`deploy/aws/compose.yaml` builds the variables above from a shorter `.env` on the server (copy
`deploy/aws/env.example`):

| Variable | |
|---|---|
| `SITE_HOST` | Required; the public hostname. Becomes `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` and `DJANGO_SITE_URL`, and Caddy's certificate name |
| `DJANGO_SECRET_KEY` | Required |
| `BACKUP_BUCKET` | The S3 bucket `backup.sh` writes to |
| `DATA_DIR` | Where the database, uploads and backups live on the server; default `/srv/charity/data` |
| `DJANGO_SECURE_HSTS_SECONDS` | Raise to a year (31536000) once HTTPS has worked for a while |
| `WEB_CONCURRENCY` | Default 2; each worker takes roughly 100–150 MB |
