"""The site's own words (menus, buttons, messages) in Nepali (#116).

Editors' content is a separate matter (#117): these tests read what the templates say. The
appeals and the pledge form are in `campaigns/tests/test_nepali.py`.
"""

import pytest
from bs4 import BeautifulSoup
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.utils import translation

from core.models import SiteSettings
from core.money import format_money
from news.tests.factories import NewsIndexPageFactory

pytestmark = pytest.mark.django_db


def visible_text(response):
    return BeautifulSoup(response.content, "html.parser").get_text(" ", strip=True)


def translated(page, locale):
    translation_ = page.copy_for_translation(locale)
    translation_.save_revision().publish()
    return translation_


class TestEnglishIsUnchanged:
    def test_the_header_and_footer_stay_english(self, client, home_page, privacy_notice):
        html = client.get("/").content.decode()

        assert ">Menu</button>" in html
        assert "Skip to content" in html
        assert 'placeholder="Search"' in html
        assert ">Privacy notice</a>" in html


class TestPagesInNepali:
    def test_the_header_in_nepali(self, client, nepali_home_page, privacy_notice):
        html = client.get("/ne/").content.decode()

        assert ">मेनु</button>" in html
        assert "मुख्य सामग्रीमा जानुहोस्" in html
        assert 'placeholder="खोज्नुहोस्"' in html
        assert 'aria-label="मुख्य"' in html

    def test_the_footer_in_nepali(self, client, nepali_home_page, privacy_notice, home_page):
        settings = SiteSettings.for_site(home_page.get_site())
        settings.charity_number = "1234567"
        settings.save()

        text = visible_text(client.get("/ne/"))

        assert "गोपनीयता सूचना" in text
        assert "दर्ता भएको परोपकारी संस्था नम्बर 1234567।" in text
        assert "Registered" not in text

    def test_search_in_nepali(self, client, nepali_home_page):
        response = client.get("/ne/search/", {"query": "नभेटिने"})

        assert "“नभेटिने” का लागि कुनै नतिजा फेला परेन।" in visible_text(response)
        assert "No results" not in visible_text(response)
        assert "“नभेटिने” को खोज नतिजा" in response.content.decode()

    def test_a_search_result_count_in_nepali(self, client, nepali_home_page):
        text = visible_text(client.get("/ne/search/", {"query": "गृहपृष्ठ"}))

        assert "नतिजा" in text
        assert "result" not in text

    def test_page_not_found_in_nepali(self, client, nepali_home_page):
        response = client.get("/ne/nothing-lives-here/")

        assert response.status_code == 404
        text = visible_text(response)
        assert "पृष्ठ फेला परेन" in text
        assert "माफ गर्नुहोस्, यो पृष्ठ फेला पार्न सकिएन।" in text
        assert "Page not found" not in text

    def test_the_news_feed_copy_button_in_nepali(self, client, nepali_home_page, home_page):
        index = NewsIndexPageFactory(parent=home_page, slug="news")
        nepali_index = translated(index, nepali_home_page.locale)

        button = BeautifulSoup(client.get(nepali_index.url).content, "html.parser").find(
            "button", {"data-copy": "feed-url"}
        )

        # charity.js shows these, so they travel in the markup in the reader's language.
        assert button.text == "लिङ्क कपी गर्नुहोस्"
        assert button["data-copied"] == "कपी भयो"
        assert "लिङ्क कपी भयो" in button["data-copied-status"]
        assert "Ctrl+C" in button["data-copy-failed-status"]

    def test_the_server_error_page_in_nepali(self):
        with translation.override("ne"):
            html = render_to_string("500.html")

        assert "सर्भरमा आन्तरिक त्रुटि" in html
        assert '<html lang="ne"' in html

    def test_pagination_in_nepali(self):
        request = RequestFactory().get("/ne/news/")
        items = Paginator(range(30), 10).page(2)

        with translation.override("ne"):
            html = render_to_string("includes/pagination.html", {"items": items}, request)

        assert "पृष्ठ 2 / 3" in html
        assert ">अघिल्लो</a>" in html
        assert ">अर्को</a>" in html


class TestWhatStaysTheSame:
    def test_amounts_keep_latin_digits_and_their_grouping(self):
        with translation.override("ne"):
            assert format_money(4687500, "NPR") == "Rs 46,87,500"
            assert format_money(4687500, "GBP") == "£4,687,500"
