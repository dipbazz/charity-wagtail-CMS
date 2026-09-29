import os

from .base import *

DEBUG = False

# Fail loudly at startup rather than run with a missing secret.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

WAGTAILADMIN_BASE_URL = os.environ.get("WAGTAILADMIN_BASE_URL", WAGTAILADMIN_BASE_URL)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# Start short and raise once HTTPS is confirmed everywhere; browsers cache HSTS for this long.
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", 3600))
# HSTS for subdomains and preload are hard to undo and can break other services on the
# charity's domain (shops, donation platforms), so they are a per-deployment decision.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ManifestStaticFilesStorage is recommended in production, to prevent
# outdated JavaScript / CSS assets being served from cache
# (e.g. after a Wagtail upgrade).
# See https://docs.djangoproject.com/en/6.1/ref/contrib/staticfiles/#manifeststaticfilesstorage
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

try:
    from .local import *
except ImportError:
    pass
