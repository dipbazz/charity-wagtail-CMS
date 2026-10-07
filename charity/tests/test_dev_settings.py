import runpy

import pytest
from django.core.exceptions import ImproperlyConfigured

MODULE = "charity.settings.dev"


def test_development_opens_in_english_unless_set(monkeypatch):
    monkeypatch.delenv("DJANGO_LANGUAGE_CODE", raising=False)

    assert runpy.run_module(MODULE)["LANGUAGE_CODE"] == "en"


def test_development_can_open_in_nepali(monkeypatch):
    monkeypatch.setenv("DJANGO_LANGUAGE_CODE", "ne")

    assert runpy.run_module(MODULE)["LANGUAGE_CODE"] == "ne"


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    """Point the settings at a temporary folder, so a real .env.local on this machine is ignored."""
    monkeypatch.setattr("charity.settings.base.BASE_DIR", tmp_path)
    monkeypatch.delenv("DJANGO_LANGUAGE_CODE", raising=False)
    return tmp_path / ".env.local"


def test_development_reads_its_language_from_env_local(env_file):
    env_file.write_text("# comment\nDJANGO_LANGUAGE_CODE=ne\n", encoding="utf-8")

    assert runpy.run_module(MODULE)["LANGUAGE_CODE"] == "ne"


def test_a_real_environment_variable_beats_env_local(env_file, monkeypatch):
    env_file.write_text("DJANGO_LANGUAGE_CODE=ne\n", encoding="utf-8")
    monkeypatch.setenv("DJANGO_LANGUAGE_CODE", "en")

    assert runpy.run_module(MODULE)["LANGUAGE_CODE"] == "en"


def test_development_starts_without_an_env_local(env_file):
    assert runpy.run_module(MODULE)["LANGUAGE_CODE"] == "en"


def test_development_refuses_a_main_language_the_site_isnt_written_in(monkeypatch):
    monkeypatch.setenv("DJANGO_LANGUAGE_CODE", "en-gb")

    with pytest.raises(ImproperlyConfigured, match="DJANGO_LANGUAGE_CODE"):
        runpy.run_module(MODULE)


def test_production_never_reads_env_local():
    with open("charity/settings/production.py", encoding="utf-8") as source:
        assert "env.local" not in source.read()


@pytest.mark.parametrize("module", ["dev", "production"])
def test_no_settings_module_reads_a_hidden_local_file(module):
    with open(f"charity/settings/{module}.py", encoding="utf-8") as source:
        assert ".local" not in source.read()
