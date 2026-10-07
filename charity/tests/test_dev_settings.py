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


def test_development_refuses_a_main_language_the_site_isnt_written_in(monkeypatch):
    monkeypatch.setenv("DJANGO_LANGUAGE_CODE", "en-gb")

    with pytest.raises(ImproperlyConfigured, match="DJANGO_LANGUAGE_CODE"):
        runpy.run_module(MODULE)


@pytest.mark.parametrize("module", ["dev", "production"])
def test_no_settings_module_reads_a_hidden_local_file(module):
    with open(f"charity/settings/{module}.py", encoding="utf-8") as source:
        assert ".local" not in source.read()
