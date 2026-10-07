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


class TestPrivacyNoticeLink:
    def test_footer_links_to_the_chosen_privacy_notice(self, client, privacy_notice):
        html = client.get("/").content.decode()

        assert f'<a href="{privacy_notice.url}">Privacy notice</a>' in html

    def test_no_link_without_a_privacy_notice(self, client, home_page):
        assert "Privacy notice" not in client.get("/").content.decode()

    def test_no_link_to_an_unpublished_privacy_notice(self, client, privacy_notice):
        privacy_notice.unpublish()

        assert "Privacy notice" not in client.get("/").content.decode()

    def test_nepali_page_links_to_the_nepali_privacy_notice(
        self, client, privacy_notice, nepali_home_page, nepali_locale
    ):
        translation = privacy_notice.copy_for_translation(nepali_locale)
        translation.save_revision().publish()

        html = client.get("/ne/").content.decode()

        assert f'<a href="{translation.url}">Privacy notice</a>' in html

    def test_nepali_page_links_to_the_main_notice_until_it_is_translated(
        self, client, privacy_notice, nepali_home_page
    ):
        html = client.get("/ne/").content.decode()

        assert f'<a href="{privacy_notice.url}">Privacy notice</a>' in html


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


def test_site_settings_open_in_the_admin(admin_client, site):
    url = reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk])

    assert admin_client.get(url).status_code == 200
