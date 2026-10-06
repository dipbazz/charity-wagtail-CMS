import datetime
import importlib

import pytest
from django.apps import apps
from django.utils import formats, translation
from wagtail.models import Locale

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
