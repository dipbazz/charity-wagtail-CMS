import runpy

import pytest
from django.core.exceptions import ImproperlyConfigured

MODULE = "charity.settings.production"


def load_settings():
    """Execute the settings module in isolation and return its globals."""
    return runpy.run_module(MODULE)


@pytest.fixture(autouse=True)
def required_environment(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "brightwell.example")
    monkeypatch.setenv("DJANGO_SITE_URL", "https://brightwell.example")


def test_refuses_to_start_without_a_site_url(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.delenv("DJANGO_SITE_URL")

    with pytest.raises(KeyError, match="DJANGO_SITE_URL"):
        load_settings()


def test_site_url_is_the_base_for_admin_email_links(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_SITE_URL", "https://brightwell.example/")

    settings = load_settings()

    assert settings["SITE_URL"] == "https://brightwell.example"
    assert settings["WAGTAILADMIN_BASE_URL"] == "https://brightwell.example"


def test_refuses_to_start_without_a_secret_key(monkeypatch):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)

    with pytest.raises(KeyError, match="DJANGO_SECRET_KEY"):
        load_settings()


def test_reads_secrets_and_hosts_from_the_environment(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "brightwell.example, www.brightwell.example")

    settings = load_settings()

    assert settings["SECRET_KEY"] == "from-env"
    assert settings["ALLOWED_HOSTS"] == ["brightwell.example", "www.brightwell.example"]


@pytest.mark.parametrize("value", [None, "", " , "])
def test_refuses_to_start_without_allowed_hosts(monkeypatch, value):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    if value is None:
        monkeypatch.delenv("DJANGO_ALLOWED_HOSTS")
    else:
        monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", value)

    with pytest.raises(ImproperlyConfigured, match="DJANGO_ALLOWED_HOSTS"):
        load_settings()


def test_is_locked_down(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")

    settings = load_settings()

    assert settings["DEBUG"] is False
    assert settings["SESSION_COOKIE_SECURE"] is True
    assert settings["CSRF_COOKIE_SECURE"] is True
    assert "debug_toolbar" not in settings["INSTALLED_APPS"]


def test_forces_https_with_a_cautious_default_hsts(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.delenv("DJANGO_SECURE_HSTS_SECONDS", raising=False)

    settings = load_settings()

    assert settings["SECURE_SSL_REDIRECT"] is True
    assert settings["SECURE_HSTS_SECONDS"] == 3600


def test_hsts_duration_is_configurable(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_SECURE_HSTS_SECONDS", "31536000")

    assert load_settings()["SECURE_HSTS_SECONDS"] == 31536000


def test_sends_email_through_the_configured_smtp_server(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_EMAIL_HOST", "smtp.brightwell.example")
    monkeypatch.setenv("DJANGO_EMAIL_HOST_USER", "website")
    monkeypatch.setenv("DJANGO_EMAIL_HOST_PASSWORD", "hunter2")
    monkeypatch.setenv("DJANGO_DEFAULT_FROM_EMAIL", "website@brightwell.example")

    settings = load_settings()

    mailer = settings["MAILERS"]["default"]
    assert mailer["BACKEND"] == "django.core.mail.backends.smtp.EmailBackend"
    assert mailer["OPTIONS"]["host"] == "smtp.brightwell.example"
    assert mailer["OPTIONS"]["port"] == 587
    assert mailer["OPTIONS"]["username"] == "website"
    assert mailer["OPTIONS"]["password"] == "hunter2"
    assert mailer["OPTIONS"]["use_tls"] is True
    # A hung mail server must not hold a web worker indefinitely.
    assert mailer["OPTIONS"]["timeout"]
    assert settings["DEFAULT_FROM_EMAIL"] == "website@brightwell.example"


def test_smtp_port_and_tls_are_configurable(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_EMAIL_PORT", "25")
    monkeypatch.setenv("DJANGO_EMAIL_USE_TLS", "false")

    options = load_settings()["MAILERS"]["default"]["OPTIONS"]

    assert options["port"] == 25
    assert options["use_tls"] is False


def test_serves_compressed_static_files_itself(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")

    settings = load_settings()

    assert settings["MIDDLEWARE"][:2] == [
        "django.middleware.security.SecurityMiddleware",
        "whitenoise.middleware.WhiteNoiseMiddleware",
    ]
    assert (
        settings["STORAGES"]["staticfiles"]["BACKEND"]
        == "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )


def test_database_and_uploads_live_in_the_data_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_DATA_DIR", str(tmp_path))

    settings = load_settings()

    assert settings["DATABASES"]["default"]["NAME"] == tmp_path / "db.sqlite3"
    assert settings["MEDIA_ROOT"] == tmp_path / "media"


def test_serving_uploads_from_django_is_opt_in(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.delenv("DJANGO_SERVE_MEDIA", raising=False)
    assert load_settings()["SERVE_MEDIA"] is False

    monkeypatch.setenv("DJANGO_SERVE_MEDIA", "true")
    assert load_settings()["SERVE_MEDIA"] is True
