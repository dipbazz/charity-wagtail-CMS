"""The site's two languages: the main one at /, the other under its prefix (#113)."""

import pytest
from django.core.cache import cache
from django.urls import clear_url_caches
from wagtail.models import Locale

from home.models import StandardPage

pytestmark = pytest.mark.django_db


def add_page(parent, title, slug):
    page = StandardPage(title=title, slug=slug)
    parent.add_child(instance=page)
    page.save_revision().publish()
    return page


def translate(page, locale, title):
    translation = page.copy_for_translation(locale)
    translation.title = title
    translation.save_revision().publish()
    return translation


def html_lang(response):
    html = response.content.decode()
    start = html.index("<html")
    return html[start : html.index(">", start) + 1]


class TestEnglishAsTheMainLanguage:
    def test_english_pages_keep_their_addresses(self, client, home_page, nepali_home_page):
        about = add_page(home_page, "About us", "about-us")

        assert home_page.url == "/"
        assert about.url == "/about-us/"
        assert client.get("/about-us/").status_code == 200

    def test_nepali_pages_are_served_under_ne(self, client, home_page, nepali_home_page):
        about = add_page(home_page, "About us", "about-us")
        hamro_barema = translate(about, nepali_home_page.locale, "हाम्रो बारेमा")

        assert nepali_home_page.url == "/ne/"
        assert hamro_barema.url == "/ne/about-us/"
        assert "गृहपृष्ठ" in client.get("/ne/").content.decode()
        assert "हाम्रो बारेमा" in client.get("/ne/about-us/").content.decode()

    def test_a_page_missing_in_nepali_falls_back_to_english(
        self, client, home_page, nepali_home_page
    ):
        add_page(home_page, "About us", "about-us")

        response = client.get("/ne/about-us/")

        assert response.status_code == 302
        assert response["Location"] == "/about-us/"

    def test_english_isnt_also_served_under_en(self, client, home_page):
        assert client.get("/en/").status_code == 404

    def test_html_lang_names_the_language_of_the_page(self, client, home_page, nepali_home_page):
        assert 'lang="en"' in html_lang(client.get("/"))
        assert 'lang="ne"' in html_lang(client.get("/ne/"))


class TestNepaliAsTheMainLanguage:
    @pytest.fixture(autouse=True)
    def nepali_first(self, settings, home_page, nepali_locale):
        """A Nepali charity's site: its home page is Nepali, with an English translation."""
        settings.LANGUAGE_CODE = "ne"
        # Django caches reversed URLs, prefixes included, and Wagtail caches each site's root
        # paths by language: both were built for English as the main language.
        clear_url_caches()
        cache.clear()
        home_page.locale = nepali_locale
        home_page.title = "गृहपृष्ठ"
        home_page.save_revision().publish()
        yield home_page
        clear_url_caches()

    def test_nepali_is_served_at_the_root(self, client):
        response = client.get("/")

        assert "गृहपृष्ठ" in response.content.decode()
        assert 'lang="ne"' in html_lang(response)

    def test_english_is_served_under_en(self, client, nepali_first):
        english = translate(nepali_first, Locale.objects.get(language_code="en"), "Home")

        assert english.url == "/en/"
        response = client.get("/en/")
        assert "Home" in response.content.decode()
        assert 'lang="en"' in html_lang(response)

    def test_english_without_a_translation_falls_back_to_nepali(self, client):
        response = client.get("/en/")

        assert response.status_code == 302
        assert response["Location"] == "/"
