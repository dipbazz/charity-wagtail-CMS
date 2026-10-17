from .base import *

SECRET_KEY = "test-secret-key-not-for-production"
DEBUG = False
ALLOWED_HOSTS = ["localhost", "testserver"]

# Hashing passwords properly is deliberately slow; tests don't need that.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Keep uploaded test files out of the real media and receipts directories. A new dict, not
# base's changed in place, which the production settings tests load too.
STORAGES = {
    **STORAGES,
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "receipts": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}

MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
