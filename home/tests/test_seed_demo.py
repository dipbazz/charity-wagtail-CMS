import pytest
from django.core.management import CommandError, call_command
from wagtail.models import Locale, Page

from campaigns.models import CampaignPage, DonatePage
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


def test_donate_page_takes_pledges_for_the_appeals(seeded, client):
    donate = SiteSettings.for_site(seeded).donate_page.specific

    assert isinstance(donate, DonatePage)
    assert donate.donation_amounts.count() >= 3
    html = client.get(donate.url, {"appeal": "flood-relief"}).content.decode()
    assert "Flash flood relief in Nepal" in html
    assert "Where every Rs 100 goes" in html


def test_amounts_are_in_rupees_on_every_page(seeded, client):
    assert SiteSettings.for_site(seeded).currency == "NPR"
    pages = Page.objects.live().filter(depth__gt=1)

    pounds = [page.url for page in pages if "£" in client.get(page.url).content.decode()]

    assert pounds == []


def test_every_live_page_renders(seeded, client):
    pages = Page.objects.live().filter(depth__gt=1)

    failures = {page.url: client.get(page.url).status_code for page in pages}

    assert failures and all(code == 200 for code in failures.values()), failures


def test_every_photo_is_a_credited_real_photograph(seeded):
    photos = core_models.CustomImage.objects.exclude(pk__in=Partner.objects.values("logo"))

    assert photos.count() >= 5
    for photo in photos:
        assert photo.file.name.endswith(".jpg"), photo.title
        assert photo.credit.startswith("Photo: "), photo.title
        assert " / Unsplash" in photo.credit or " / Pexels" in photo.credit, photo.title
        assert photo.description, photo.title
        assert photo.width <= 1600, photo.title


def test_stock_photos_are_not_marked_as_consented(seeded):
    # Stock licences cover copyright, not consent from the people pictured.
    assert not core_models.CustomImage.objects.filter(consent_confirmed=True).exists()


def test_each_partner_has_its_own_logo(seeded):
    partners = Partner.objects.all()

    assert all(partner.logo for partner in partners)
    assert len({partner.logo_id for partner in partners}) == partners.count()
    for partner in partners:
        assert partner.logo.description == f"{partner.name} logo"


def test_flood_appeal_points_people_to_a_real_relief_fund(seeded, client):
    flood = CampaignPage.objects.get(slug="flood-relief", locale__language_code="en")

    html = client.get(flood.url).content.decode()

    assert "Nepal" in flood.title
    assert "demo charity" in html
    assert "https://rescue.opmcm.gov.np/donations" in html
    # The photo isn't of this flood, so the page has to say so.
    assert "Representative image" in html
    assert "Nepal" in AnnouncementBanner.load().message


def test_translates_the_home_page_an_appeal_and_a_story_into_nepali(seeded, client):
    nepali = Locale.objects.get(language_code="ne")
    flood = CampaignPage.objects.get(slug="flood-relief", locale__language_code="en")
    nepali_flood = flood.get_translation(nepali)
    [nepali_story] = NewsPage.objects.live().filter(locale=nepali)

    assert seeded.root_page.get_translation(nepali).live
    assert nepali_flood.live
    assert nepali_flood.url == "/ne/appeals/flood-relief/"
    assert "बाढी" in nepali_flood.title
    assert NewsPage.objects.filter(
        translation_key=nepali_story.translation_key, locale__language_code="en"
    ).exists()
    # The Nepali appeal is honest about the demo too, and points to the same relief fund.
    html = client.get(nepali_flood.url).content.decode()
    assert "https://rescue.opmcm.gov.np/donations" in html


def test_running_twice_does_not_duplicate_content(seeded):
    page_count = Page.objects.count()

    call_command("seed_demo", verbosity=0)

    assert Page.objects.count() == page_count


def test_explains_how_to_seed_a_site_whose_main_language_is_nepali(
    home_page, nepali_locale, settings
):
    # A new deployment opens in Nepali, so its home page is in the Nepali locale.
    settings.LANGUAGE_CODE = "ne"
    home_page.locale = nepali_locale
    home_page.save()

    with pytest.raises(CommandError, match="DJANGO_LANGUAGE_CODE=en"):
        call_command("seed_demo", verbosity=0)

    assert not CampaignPage.objects.exists()


def test_points_the_site_at_the_site_url_even_when_content_exists(site, settings):
    call_command("seed_demo", verbosity=0)
    settings.SITE_URL = "http://localhost:9000"

    call_command("seed_demo", verbosity=0)

    site.refresh_from_db()
    assert site.root_url == "http://localhost:9000"
