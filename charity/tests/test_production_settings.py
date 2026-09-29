import runpy

import pytest

MODULE = "charity.settings.production"


def load_settings():
    """Execute the settings module in isolation and return its globals."""
    return runpy.run_module(MODULE)


def test_refuses_to_start_without_a_secret_key(monkeypatch):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)

    with pytest.raises(KeyError, match="DJANGO_SECRET_KEY"):
        load_settings()


def test_reads_secrets_and_hosts_from_the_environment(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.org, www.example.org")

    settings = load_settings()

    assert settings["SECRET_KEY"] == "from-env"
    assert settings["ALLOWED_HOSTS"] == ["example.org", "www.example.org"]


def test_is_locked_down(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")

    settings = load_settings()

    assert settings["DEBUG"] is False
    assert settings["SESSION_COOKIE_SECURE"] is True
    assert settings["CSRF_COOKIE_SECURE"] is True


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
