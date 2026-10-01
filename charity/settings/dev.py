from .base import *

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


try:
    from .local import *
except ImportError:
    pass
