import datetime
import importlib

import pytest
from django.apps import apps
from django.utils import formats, translation
from wagtail.models import Locale

from core.apps import create_content_locales
from core.languages import in_reading_language
from core.models import Partner

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


class TestInReadingLanguage:
    """Snippets in the reader's language, falling back to the main language's (#117)."""

    @pytest.fixture
    def partners(self, nepali_locale):
        translated = Partner.objects.create(name="Water Foundation", sort_order=1)
        nepali = translated.copy_for_translation(nepali_locale)
        nepali.name = "जल फाउन्डेसन"
        nepali.save()
        english_only = Partner.objects.create(name="Local Council", sort_order=2)
        nepali_only = Partner.objects.create(name="गाउँ समिति", sort_order=3, locale=nepali_locale)
        return {
            "translated": translated,
            "nepali": nepali,
            "english_only": english_only,
            "nepali_only": nepali_only,
        }

    def test_nepali_readers_get_each_snippet_in_nepali_or_else_in_english(self, partners):
        with translation.override("ne"):
            found = in_reading_language(Partner.objects.all())

        assert found == [partners["nepali"], partners["english_only"], partners["nepali_only"]]

    def test_english_readers_get_english_and_not_snippets_only_in_nepali(self, partners):
        with translation.override("en"):
            found = in_reading_language(Partner.objects.all())

        assert found == [partners["translated"], partners["english_only"]]

    def test_costs_one_query(self, partners, django_assert_num_queries):
        with translation.override("ne"), django_assert_num_queries(1):
            in_reading_language(Partner.objects.all())
