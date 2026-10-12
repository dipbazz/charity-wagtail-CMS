import os

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from nepal_payments.providers.esewa import ESewa

from .base import *
from .payments import payment_keys

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-1ebbk2))yq4@^+$mr5(c#ks()bc1=hu!d8lycz0k$2p2arkx6b"

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

# Serve uploads through core.views.serve_media, as the Docker image does.
SERVE_MEDIA = True

MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}

# Debug toolbar: the queries, templates and timings behind each page, shown to requests from this
# machine. It's a dev dependency only, so production and test settings leave it out.
INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]
INTERNAL_IPS = ["127.0.0.1"]

# Settings for local machine only: copy .env.local.example to .env.local (gitignored) and edit it. A
# variable already set in the shell wins over the file.
load_dotenv(BASE_DIR / ".env.local")

# Development opens in English, like the demo content and the tests. Set DJANGO_LANGUAGE_CODE=ne to
# see the site the way a Nepali charity's visitors will; it's checked as production checks it.
LANGUAGE_CODE = os.environ.get("DJANGO_LANGUAGE_CODE", "en")
if LANGUAGE_CODE not in dict(LANGUAGES):
    raise ImproperlyConfigured(
        f"Set DJANGO_LANGUAGE_CODE to one of {', '.join(dict(LANGUAGES))}, not {LANGUAGE_CODE!r}."
    )

# Paying pledges, in the providers' test systems: eSewa publishes its test keys, so it works here
# with nothing set up. Khalti's needs your own test key, from test-admin.khalti.com, as
# DJANGO_PAYMENT_KHALTI_SECRET_KEY in .env.local.
PAYMENT_KEYS = {
    **{f"ESEWA_{key}": value for key, value in ESewa.test_keys.items()},
    **payment_keys(os.environ),
}
