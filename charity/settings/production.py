import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

# Fail loudly at startup rather than run with a missing secret.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")]
ALLOWED_HOSTS = [h for h in ALLOWED_HOSTS if h]
if not ALLOWED_HOSTS:
    # Otherwise every request is rejected with a bare 400 Bad Request.
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS to the site's comma-separated hostnames.")
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

# The language the site opens in at /: Nepali unless a site sets "en". The other one is under
# /en/ or /ne/. A code outside LANGUAGES, even a variant such as en-gb, would move every page
# under a prefix and break existing links, so it stops the site starting instead.
LANGUAGE_CODE = os.environ.get("DJANGO_LANGUAGE_CODE", "ne")
if LANGUAGE_CODE not in dict(LANGUAGES):
    raise ImproperlyConfigured(
        f"Set DJANGO_LANGUAGE_CODE to one of {', '.join(dict(LANGUAGES))}, not {LANGUAGE_CODE!r}."
    )

SITE_URL = os.environ["DJANGO_SITE_URL"].rstrip("/")
WAGTAILADMIN_BASE_URL = SITE_URL

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# Start short and raise once HTTPS is confirmed everywhere; browsers cache HSTS for this long.
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", 3600))
# HSTS for subdomains and preload are hard to undo and can break other services on the
# charity's domain (shops, donation platforms), so they are a per-deployment decision.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Form notifications and moderation workflow emails.
MAILERS = {
    "default": {
        # SMTP that lets the moderation workflow carry on, without its email, when the mail
        # server can't be reached.
        "BACKEND": "core.mail.SMTPBackend",
        "OPTIONS": {
            "host": os.environ.get("DJANGO_EMAIL_HOST", "localhost"),
            "port": int(os.environ.get("DJANGO_EMAIL_PORT", 587)),
            "username": os.environ.get("DJANGO_EMAIL_HOST_USER", ""),
            "password": os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", ""),
            "use_tls": os.environ.get("DJANGO_EMAIL_USE_TLS", "true").lower() == "true",
            # Sending happens inside the request, so a hung mail server must not hold a worker.
            "timeout": 10,
        },
    }
}
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "webmaster@localhost")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Errors and warnings go to stderr, which Docker keeps (`docker compose logs web`). Django's
# defaults print nothing with DEBUG off and email ADMINS instead, which is empty, so server
# errors left no trace (#78). Request errors are logged at ERROR only: 404s are WARNINGs and
# would bury them.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "stderr": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "loggers": {
        "django.request": {"handlers": ["stderr"], "level": "ERROR"},
        **{
            name: {"handlers": ["stderr"], "level": "WARNING"}
            for name in [
                "wagtail",
                "charity",
                "core",
                "home",
                "campaigns",
                "news",
                "contact",
                "search",
            ]
        },
    },
}

# Settings below build new objects rather than mutating the ones imported from base, which
# other settings modules share.

# WhiteNoise serves static files from the app itself, compressed and with far-future cache headers.
# Manifest storage gives each file a hashed name, so browsers never keep stale CSS / JavaScript
# (e.g. after a Wagtail upgrade).
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# The SQLite database and editors' uploads live together in one directory that must outlive the
# app's code, e.g. a mounted volume.
DATA_DIR = Path(os.environ.get("DJANGO_DATA_DIR", BASE_DIR))
DATABASES = {"default": {**DATABASES["default"], "NAME": DATA_DIR / "db.sqlite3"}}
MEDIA_ROOT = DATA_DIR / "media"
# Turn on when no web server or object storage serves MEDIA_URL in front of the app.
SERVE_MEDIA = os.environ.get("DJANGO_SERVE_MEDIA", "false").lower() == "true"
