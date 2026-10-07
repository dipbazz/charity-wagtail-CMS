"""The language switcher in the header and the hreflang links in <head> (#115)."""

import re

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


def switcher_html(client, path):
    html = client.get(path).content.decode()
    start = html.index('<nav class="language-switcher"')
    return html[start : html.index("</nav>", start)]


def switcher_links(client, path):
    """{language name: link href} from the switcher."""
    links = re.findall(r'<a href="([^"]*)"[^>]*>([^<]*)</a>', switcher_html(client, path))
    return {name: href for href, name in links}


def alternates(client, path):
    html = client.get(path).content.decode()
    head = html[: html.index("</head>")]
    return dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', head))


@pytest.fixture
def about(home_page):
    return add_page(home_page, "About us", "about")


@pytest.fixture
def hamro_barema(about, nepali_home_page):
    return translate(about, nepali_home_page.locale, "हाम्रो बारेमा")


class TestSwitcher:
    def test_goes_to_the_same_page_in_the_other_language(self, client, hamro_barema):
        assert switcher_links(client, "/about/") == {"नेपाली": "/ne/about/", "English": "/about/"}
        assert switcher_links(client, "/ne/about/") == {"नेपाली": "/ne/about/", "English": "/about/"}

    def test_goes_to_the_other_home_page_from_a_page_in_one_language_only(
        self, client, about, nepali_home_page
    ):
        assert switcher_links(client, "/about/")["नेपाली"] == "/ne/"

    def test_names_each_language_in_its_own_language_and_marks_the_current_one(
        self, client, hamro_barema
    ):
        html = switcher_html(client, "/ne/about/")

        assert '<a href="/ne/about/" lang="ne" hreflang="ne" aria-current="page">नेपाली</a>' in html
        assert '<a href="/about/" lang="en" hreflang="en">English</a>' in html

    def test_is_a_labelled_navigation_landmark(self, client, hamro_barema):
        assert 'aria-label="Language"' in switcher_html(client, "/about/")

    def test_keeps_the_search_query(self, client, home_page, nepali_home_page):
        links = switcher_links(client, "/search/?query=water")

        assert links["नेपाली"] == "/ne/search/?query=water"

    def test_goes_to_the_other_home_page_from_a_missing_page(
        self, client, home_page, nepali_home_page
    ):
        response = client.get("/no-such-page/")

        assert response.status_code == 404
        assert switcher_links(client, "/no-such-page/")["नेपाली"] == "/ne/"

    def test_is_hidden_when_the_site_has_one_language(self, client, about):
        assert "language-switcher" not in client.get("/about/").content.decode()

    def test_is_hidden_while_the_other_home_page_is_a_draft(self, client, about, nepali_locale):
        nepali_home = about.get_parent().copy_for_translation(nepali_locale)
        nepali_home.save_revision()

        assert "language-switcher" not in client.get("/about/").content.decode()

    def test_skips_a_translation_that_is_a_draft(self, client, about, nepali_home_page):
        about.copy_for_translation(nepali_home_page.locale).save_revision()

        assert switcher_links(client, "/about/")["नेपाली"] == "/ne/"


class TestSwitcherOnANepaliFirstSite:
    @pytest.fixture(autouse=True)
    def nepali_first(self, settings, home_page, nepali_locale):
        settings.LANGUAGE_CODE = "ne"
        clear_url_caches()
        cache.clear()
        home_page.locale = nepali_locale
        home_page.title = "गृहपृष्ठ"
        home_page.save_revision().publish()
        yield home_page
        clear_url_caches()

    def test_english_is_under_en(self, client, nepali_first):
        translate(nepali_first, Locale.objects.get(language_code="en"), "Home")

        assert switcher_links(client, "/") == {"नेपाली": "/", "English": "/en/"}


class TestAlternates:
    def test_lists_every_language_of_a_translated_page_with_full_urls(self, client, hamro_barema):
        expected = {
            "ne": "http://localhost/ne/about/",
            "en": "http://localhost/about/",
            "x-default": "http://localhost/about/",
        }

        assert alternates(client, "/about/") == expected
        assert alternates(client, "/ne/about/") == expected

    def test_are_left_out_for_a_page_in_one_language_only(self, client, about, nepali_home_page):
        assert alternates(client, "/about/") == {}

    def test_are_left_out_of_search(self, client, home_page, nepali_home_page):
        assert alternates(client, "/search/?query=water") == {}
