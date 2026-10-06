import logging
import logging.config
import runpy

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import Client
from django.urls import path

MODULE = "charity.settings.production"


def load_settings():
    """Execute the settings module in isolation and return its globals."""
    return runpy.run_module(MODULE)


def broken_view(request):
    raise RuntimeError("the view broke")


# Used by tests marked with this module as their URLconf.
urlpatterns = [path("broken/", broken_view)]


@pytest.fixture(autouse=True)
def required_environment(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "brightwell.example")
    monkeypatch.setenv("DJANGO_SITE_URL", "https://brightwell.example")


@pytest.fixture
def use_production_logging(monkeypatch):
    """Return a function that configures logging as production does; undo it afterwards.

    Tests call it in their body: pytest swaps the captured stderr between fixture setup and the
    test, and a handler made earlier would write to the old one.
    """
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    # No LOGGING setting leaves Django's defaults in place.
    config = load_settings().get("LOGGING", {"version": 1, "disable_existing_loggers": False})
    loggers = [logging.getLogger(name) for name in [None, *config.get("loggers", {})]]
    saved = [(lg, lg.handlers[:], lg.level, lg.propagate, lg.disabled) for lg in loggers]
    yield lambda: logging.config.dictConfig(config)
    for logger, handlers, level, propagate, disabled in saved:
        logger.handlers, logger.propagate, logger.disabled = handlers, propagate, disabled
        logger.setLevel(level)


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


def test_main_language_is_nepali_unless_set(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.delenv("DJANGO_LANGUAGE_CODE", raising=False)

    assert load_settings()["LANGUAGE_CODE"] == "ne"


def test_an_english_site_sets_english_as_the_main_language(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_LANGUAGE_CODE", "en")

    assert load_settings()["LANGUAGE_CODE"] == "en"


@pytest.mark.parametrize("value", ["en-gb", "hi", ""])
def test_refuses_a_main_language_the_site_isnt_written_in(monkeypatch, value):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_LANGUAGE_CODE", value)

    with pytest.raises(ImproperlyConfigured, match="DJANGO_LANGUAGE_CODE"):
        load_settings()


def test_sends_email_through_the_configured_smtp_server(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    monkeypatch.setenv("DJANGO_EMAIL_HOST", "smtp.brightwell.example")
    monkeypatch.setenv("DJANGO_EMAIL_HOST_USER", "website")
    monkeypatch.setenv("DJANGO_EMAIL_HOST_PASSWORD", "hunter2")
    monkeypatch.setenv("DJANGO_DEFAULT_FROM_EMAIL", "website@brightwell.example")

    settings = load_settings()

    mailer = settings["MAILERS"]["default"]
    assert mailer["BACKEND"] == "core.mail.SMTPBackend"
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


def test_request_errors_are_written_to_stderr(use_production_logging, capsys):
    use_production_logging()
    # With DEBUG off, Django's default logging only emails these to ADMINS, which is empty (#78).
    logging.getLogger("django.request").error("Internal Server Error: /about/")

    assert "Internal Server Error: /about/" in capsys.readouterr().err


@pytest.mark.parametrize("logger", ["wagtail.admin", "contact.models", "core.views"])
def test_warnings_from_wagtail_and_this_project_are_written_to_stderr(
    use_production_logging, capsys, logger
):
    use_production_logging()

    logging.getLogger(logger).warning("Mail connection error, notification sending skipped")

    assert "Mail connection error" in capsys.readouterr().err


@pytest.mark.urls(__name__)
def test_a_failing_request_writes_its_traceback_to_stderr(use_production_logging, capsys):
    use_production_logging()

    response = Client(raise_request_exception=False).get("/broken/")

    assert response.status_code == 500
    err = capsys.readouterr().err
    assert "Internal Server Error: /broken/" in err
    assert "Traceback" in err
    assert "RuntimeError: the view broke" in err


def test_every_app_in_this_project_has_its_warnings_logged(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    settings = load_settings()

    own_apps = {app for app in settings["INSTALLED_APPS"] if (settings["BASE_DIR"] / app).is_dir()}

    assert own_apps
    assert own_apps <= settings["LOGGING"]["loggers"].keys()
