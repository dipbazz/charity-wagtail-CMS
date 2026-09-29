import pytest
from django.urls import reverse

from core.models import AnnouncementBanner, SiteSettings
from home.models import StandardPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def site_settings(site):
    settings = SiteSettings.for_site(site)
    settings.charity_number = "1234567"
    settings.contact_email = "hello@brightwell.example"
    settings.instagram_url = "https://instagram.example/brightwell"
    settings.save()
    return settings


def test_footer_shows_charity_details_from_site_settings(client, home_page, site_settings):
    html = client.get("/").content.decode()

    assert "Registered charity number 1234567" in html
    assert 'href="mailto:hello@brightwell.example"' in html
    assert 'href="https://instagram.example/brightwell"' in html


def test_header_donate_button_links_to_the_chosen_donate_page(client, home_page, site_settings):
    donate = StandardPage(title="Donate", slug="donate")
    home_page.add_child(instance=donate)
    site_settings.donate_page = donate
    site_settings.save()

    html = client.get("/").content.decode()

    assert f'class="button" href="{donate.url}"' in html


def test_no_donate_button_without_a_donate_page(client, home_page, site_settings):
    assert 'class="button" href=' not in client.get("/").content.decode()


class TestAnnouncementBanner:
    def test_hidden_by_default(self, client, home_page):
        assert "announcement" not in client.get("/").content.decode()

    def test_shown_on_every_page_when_enabled(self, client, home_page):
        banner = AnnouncementBanner.load()
        banner.enabled = True
        banner.message = "Emergency appeal: flood relief"
        banner.save()

        html = client.get("/").content.decode()

        assert 'class="announcement"' in html
        assert "Emergency appeal: flood relief" in html


def test_editors_can_edit_site_settings_in_the_admin(admin_client, site):
    url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])

    assert admin_client.get(url).status_code == 200
