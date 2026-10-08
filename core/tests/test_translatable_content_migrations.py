"""Content written before it could be translated is unchanged by the migrations for #117.

Each test migrates back to before them, writes content as the site had it then, and migrates
forward again. Migrations change tables, which SQLite can't do inside the transaction a normal
test runs in, so these tests commit to the database, which is emptied after each one.
"""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from wagtail.models import Locale, Page, Site

BEFORE = [
    ("core", "0009_sitesettings_privacy_page"),
    ("news", "0004_editor_and_moderator_permissions"),
]

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def old_apps():
    """The models as they were before #117, with the database migrated back to match them.

    An earlier test of this kind may have emptied the database, so first make what the data
    migrations made: the main language and a default Site.
    """
    Locale.objects.get_or_create(language_code="en")
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


def test_partners_testimonials_and_categories_stay_in_the_main_language(old_apps):
    old_apps.get_model("core", "Partner").objects.create(name="Water Foundation", sort_order=1)
    old_apps.get_model("core", "Partner").objects.create(name="Local Council", sort_order=2)
    old_apps.get_model("core", "Testimonial").objects.create(
        quote="The well is open.", name="Grace", live=True
    )
    old_apps.get_model("news", "NewsCategory").objects.create(name="Stories", slug="stories")

    migrate_forward()

    from core.models import Partner, Testimonial
    from news.models import NewsCategory

    english = Locale.objects.get(language_code="en")
    partners = list(Partner.objects.all())
    assert [(p.name, p.locale) for p in partners] == [
        ("Water Foundation", english),
        ("Local Council", english),
    ]
    # Each has its own translation key, so each is translated on its own.
    assert partners[0].translation_key != partners[1].translation_key
    testimonial = Testimonial.objects.get()
    assert (testimonial.quote, testimonial.live, testimonial.locale) == (
        "The well is open.",
        True,
        english,
    )
    category = NewsCategory.objects.get()
    assert (category.name, category.slug, category.locale) == ("Stories", "stories", english)


def test_address_and_banner_become_the_main_language_s_text(old_apps):
    site = Site.objects.get(is_default_site=True)
    old_apps.get_model("core", "SiteSettings").objects.create(
        site_id=site.pk, address="1 Example Street\nBirmingham", phone="0123 456 7890"
    )
    old_apps.get_model("core", "AnnouncementBanner").objects.create(
        enabled=True, message="Flood appeal: give now"
    )

    migrate_forward()

    from core.models import AnnouncementBanner, SiteSettings

    site_settings = SiteSettings.for_site(site)
    assert site_settings.phone == "0123 456 7890"
    assert site_settings.address == "1 Example Street\nBirmingham"
    banner = AnnouncementBanner.for_site(site)
    assert banner.enabled
    assert banner.message == "Flood appeal: give now"
    assert banner.texts.get().locale.language_code == "en"


def test_every_site_keeps_showing_the_banner(old_apps):
    default = Site.objects.get(is_default_site=True)
    other = Site.objects.create(hostname="other.example", root_page_id=default.root_page_id)
    old_apps.get_model("core", "AnnouncementBanner").objects.create(
        enabled=True, message="Flood appeal: give now"
    )

    migrate_forward()

    from core.models import AnnouncementBanner

    for site in (default, other):
        assert AnnouncementBanner.for_site(site).message == "Flood appeal: give now"
