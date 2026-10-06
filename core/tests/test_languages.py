import datetime
import importlib

import pytest
from django.apps import apps
from django.utils import formats, translation
from wagtail.models import Locale

from core.apps import create_content_locales

pytestmark = pytest.mark.django_db

migration = importlib.import_module("core.migrations.0007_english_locale_without_region")


def test_migration_renames_the_british_english_locale(home_page):
    Locale.objects.filter(pk=home_page.locale_id).update(language_code="en-gb")

    migration.drop_region_from_english(apps, schema_editor=None)

    home_page.refresh_from_db()
    assert home_page.locale.language_code == "en"


def test_migration_leaves_other_locales_alone(nepali_locale):
    migration.drop_region_from_english(apps, schema_editor=None)

    assert sorted(Locale.objects.values_list("language_code", flat=True)) == ["en", "ne"]


def test_english_dates_stay_british():
    with translation.override("en"):
        assert formats.date_format(datetime.date(2026, 10, 6), "SHORT_DATE_FORMAT") == "06/10/2026"


def test_times_are_nepal_time(settings):
    # Scheduled publishing and every time shown in the admin follow the charity's clock.
    assert settings.TIME_ZONE == "Asia/Kathmandu"


def test_every_content_language_has_a_locale():
    # Editors can only translate a page into a language that has a Locale. A new site has only
    # its main language's, so migrate creates the rest.
    assert sorted(Locale.objects.values_list("language_code", flat=True)) == ["en", "ne"]


def test_a_language_added_later_gets_a_locale(settings):
    settings.WAGTAIL_CONTENT_LANGUAGES = [*settings.WAGTAIL_CONTENT_LANGUAGES, ("hi", "हिन्दी")]

    create_content_locales()
    create_content_locales()

    assert Locale.objects.filter(language_code="hi").count() == 1
