import runpy

import pytest
from django.core.exceptions import ImproperlyConfigured

MODULE = "charity.settings.production"


def load_settings():
    """Execute the settings module in isolation and return its globals."""
    return runpy.run_module(MODULE)


@pytest.fixture(autouse=True)
def allowed_hosts(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.org")


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
