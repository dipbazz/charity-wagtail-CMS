import pytest
from django.core.management import call_command
from wagtail.models import Page

from campaigns.models import CampaignPage
from contact.models import FormPage

# Imported via the module: a name starting with "Test" would be collected by pytest.
from core import models as core_models
from core.models import AnnouncementBanner, Partner, SiteSettings
from news.models import NewsPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(site):
    call_command("seed_demo", verbosity=0)
    site.refresh_from_db()
    return site


def test_creates_a_complete_charity_site(seeded):
    assert seeded.site_name
    assert CampaignPage.objects.live().count() >= 3
    assert CampaignPage.objects.live().closed().exists()
    assert NewsPage.objects.live().count() >= 3
    assert FormPage.objects.live().exists()
    assert Partner.objects.exists()
    assert core_models.Testimonial.objects.filter(live=True).exists()


def test_configures_site_settings_and_menu(seeded, client):
    settings = SiteSettings.for_site(seeded)
    assert settings.charity_number
    assert settings.donate_page is not None
    assert AnnouncementBanner.load().enabled
    assert seeded.root_page.get_children().live().in_menu().count() >= 3


def test_every_live_page_renders(seeded, client):
    pages = Page.objects.live().filter(depth__gt=1)

    failures = {page.url: client.get(page.url).status_code for page in pages}

    assert failures and all(code == 200 for code in failures.values()), failures


def test_running_twice_does_not_duplicate_content(seeded):
    page_count = Page.objects.count()

    call_command("seed_demo", verbosity=0)

    assert Page.objects.count() == page_count


def test_points_the_site_at_the_site_url_even_when_content_exists(site, settings):
    call_command("seed_demo", verbosity=0)
    settings.SITE_URL = "http://localhost:9000"

    call_command("seed_demo", verbosity=0)

    site.refresh_from_db()
    assert site.root_url == "http://localhost:9000"
