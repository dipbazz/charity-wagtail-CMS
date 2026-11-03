"""The charity number becomes the registration line, in every language's words (#172).

Each test migrates back to before it, writes settings as a site had them then, and migrates
forward again. Migrations change tables, which SQLite can't do inside the transaction a normal
test runs in, so these tests commit to the database, which is emptied after each one.
"""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from wagtail.models import Locale, Page, Site
from wagtail.test.utils.form_data import inline_formset, nested_form_data

from core.brand import DEFAULT_ACCENT, DEFAULT_LOGO_SIZE, DEFAULT_MAIN

BEFORE = [("core", "0020_sitesettingstext_every_language_help")]
ENGLISH = "Registered charity number 1234567."
NEPALI = "दर्ता भएको परोपकारी संस्था नम्बर 1234567।"

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def old_apps():
    """The models as they were before #172, with the database migrated back to match them.

    An earlier test of this kind may have emptied the database, so first make what the data
    migrations and `core` made: both languages and a default Site.
    """
    for code in ("en", "ne"):
        Locale.objects.get_or_create(language_code=code)
    if not Site.objects.filter(is_default_site=True).exists():
        root = Page.get_first_root_node() or Page.add_root(instance=Page(title="Root"))
        Site.objects.create(hostname="localhost", root_page=root, is_default_site=True)
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    executor.migrate(BEFORE)
    executor.loader.build_graph()
    yield executor.loader.project_state(BEFORE).apps
    executor = MigrationExecutor(connection)
    executor.migrate(latest)


def migrate_forward():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def old_settings(old_apps, number):
    site = Site.objects.get(is_default_site=True)
    return old_apps.get_model("core", "SiteSettings").objects.create(
        site_id=site.pk, charity_number=number
    )


def registration_lines():
    from core.models import SiteSettingsText

    return dict(SiteSettingsText.objects.values_list("locale__language_code", "registration_line"))


def test_a_number_joins_each_languages_row_in_its_words(old_apps):
    settings = old_settings(old_apps, " 1234567 ")
    text = old_apps.get_model("core", "SiteSettingsText")
    for code, address in (("en", "1 Example Street"), ("ne", "1 एक्जाम्पल स्ट्रिट")):
        text.objects.create(
            settings=settings,
            locale_id=Locale.objects.get(language_code=code).pk,
            address=address,
        )

    migrate_forward()

    from core.models import SiteSettingsText

    assert registration_lines() == {"en": ENGLISH, "ne": NEPALI}
    assert sorted(SiteSettingsText.objects.values_list("address", flat=True)) == [
        "1 Example Street",
        "1 एक्जाम्पल स्ट्रिट",
    ]


def test_a_number_with_no_rows_gets_a_row_for_each_language(old_apps):
    old_settings(old_apps, "1234567")

    migrate_forward()

    assert registration_lines() == {"en": ENGLISH, "ne": NEPALI}


@pytest.mark.parametrize("number", ["", "   "])
def test_no_number_writes_nothing(old_apps, number):
    old_settings(old_apps, number)

    migrate_forward()

    assert registration_lines() == {}


def test_the_next_save_is_accepted_unchanged(old_apps, client, django_user_model):
    """A superuser saves, since emptying the database after an earlier test of this kind removes
    the moderators' group; who may save is tested in test_permissions.py."""
    from core.models import SiteSettings

    old_settings(old_apps, "1234567")
    migrate_forward()
    site = Site.objects.get(is_default_site=True)
    rows = [
        {"id": text.pk, "locale": text.locale_id, "registration_line": text.registration_line}
        for text in SiteSettings.for_site(site).texts.all()
    ]
    client.force_login(django_user_model.objects.create_superuser("admin", password="pw"))
    url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])
    form = {
        "currency": "NPR",
        "phone_country": "NP",
        "main_colour": DEFAULT_MAIN,
        "accent_colour": DEFAULT_ACCENT,
        "name_bar_style": "dark",
        "logo_size": DEFAULT_LOGO_SIZE,
        "footer_style": "dark",
        "font_style": "modern",
        "texts": inline_formset(rows, initial=len(rows)),
    }

    response = client.post(url, nested_form_data(form))

    assert response.status_code == 302
