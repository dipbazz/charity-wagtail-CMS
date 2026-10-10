import pytest
from django.core.management import call_command
from wagtail.models import Locale, Page

from campaigns.forms import PledgeForm
from campaigns.models import CampaignPage, DonatePage
from contact.models import FormPage

# Imported via the module: a name starting with "Test" would be collected by pytest.
from core import models as core_models
from core.models import AnnouncementBanner, Partner, SiteSettings
from news.models import NewsPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(demo_site):
    return demo_site


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
    assert AnnouncementBanner.for_site(seeded).enabled
    assert seeded.root_page.get_children().live().in_menu().count() >= 3


def test_gives_the_charity_a_logo_in_the_header(seeded, client):
    logo = SiteSettings.for_site(seeded).logo

    assert logo is not None
    assert "brand-logo" in client.get("/").content.decode()


def test_adds_a_placeholder_privacy_notice_linked_from_every_page(seeded, client):
    privacy = SiteSettings.for_site(seeded).privacy_page
    html = client.get(privacy.url).content.decode()

    assert privacy.live and not privacy.show_in_menus
    assert "Example text" in html and "before going live" in html
    assert f'<a href="{privacy.url}">Privacy notice</a>' in client.get("/").content.decode()


# Regression: ISSUE-003 — the notice called a tick box "Email updates", which the pledge form
# labels "Email me stories from our projects and appeals that need help".
# Found by /qa on 2026-10-07 (PR #125).
def test_privacy_notice_names_the_tick_boxes_as_the_pledge_form_does(seeded):
    body = str(SiteSettings.for_site(seeded).privacy_page.specific.body)
    labels = PledgeForm.Meta.labels

    assert f"<b>{labels['email_updates']}</b>" in body
    assert f"<b>{labels['show_on_website']}</b>" in body


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
    logos = [*Partner.objects.values_list("logo", flat=True), SiteSettings.for_site(seeded).logo_id]
    photos = core_models.CustomImage.objects.exclude(pk__in=logos)

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
    assert "Nepal" in AnnouncementBanner.for_site(seeded).message


def test_translates_the_home_page_an_appeal_and_a_story_into_nepali(seeded, client):
    nepali = Locale.objects.get(language_code="ne")
    flood = CampaignPage.objects.get(slug="flood-relief", locale__language_code="en")
    nepali_flood = flood.get_translation(nepali)
    nepali_story = flood_story_in(nepali)

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


def test_translates_the_donate_page_with_its_suggested_amounts(seeded, client):
    nepali = Locale.objects.get(language_code="ne")
    donate = DonatePage.objects.get(locale__language_code="en")
    nepali_donate = donate.get_translation(nepali)

    assert nepali_donate.live
    assert nepali_donate.url == "/ne/donate/"
    assert nepali_donate.donation_amounts.count() == 3
    assert donate.donation_amounts.first().impact == "Safe water for one person for a year"
    html = client.get(nepali_donate.url).content.decode()
    assert "परिवारका लागि सरसफाइ सामग्रीको किट" in html
    # Brightwell takes no money, so its Nepali notice links to the same relief fund.
    assert "https://rescue.opmcm.gov.np/donations" in html


def test_calls_the_news_section_stories(seeded):
    from news.models import NewsCategory, NewsIndexPage

    index = NewsIndexPage.objects.get(locale__language_code="en")

    assert (index.title, index.url) == ("Stories", "/stories/")
    assert index.get_translation(Locale.objects.get(language_code="ne")).title == "कथाहरू"
    assert set(
        NewsCategory.objects.filter(locale__language_code="en").values_list("name", flat=True)
    ) == {
        "Success stories",
        "Field updates",
    }


def test_translates_the_banner_address_testimonial_and_categories(seeded, client):
    """Nepali pages show the demo's Nepali text, and its English partners as a fallback (#117)."""
    html = client.get("/ne/").content.decode()

    assert "आपतकालीन अपिल" in html
    assert "एक्जाम्पल स्ट्रिट" in html
    assert "नयाँ इनारले" in html
    # The partners aren't translated, so Nepali readers see the English ones.
    assert f'alt="{Partner.objects.first().name} logo"' in html
    stories = client.get("/ne/stories/").content.decode()
    assert "सफलताका कथा" in stories


def flood_story_in(locale):
    english = NewsPage.objects.get(locale__language_code="en", slug__contains="bhote-koshi")
    return english.get_translation(locale)


def test_adds_a_news_story_in_nepali_only(seeded, client):
    nepali = Locale.objects.get(language_code="ne")
    [story] = [
        page
        for page in NewsPage.objects.live().filter(locale=nepali)
        if not page.get_translations().exists()
    ]

    assert story.get_parent().specific.locale == nepali
    assert client.get(story.url).status_code == 200


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
