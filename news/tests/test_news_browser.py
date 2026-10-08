"""The news page's "Copy link" button in a real browser (#116): its words come from the page."""

import pytest
from playwright.sync_api import expect

from conftest import SITE
from news.tests.factories import NewsIndexPageFactory

pytestmark = [pytest.mark.browser, pytest.mark.django_db]


@pytest.fixture
def news_index(home_page):
    return NewsIndexPageFactory(parent=home_page, slug="news")


class TestCopyLink:
    # http://testserver isn't a secure origin, so the browser has no clipboard: the button falls
    # back to telling the reader to copy the selected link themselves.
    def test_tells_the_reader_what_to_do_in_english(self, site_page, news_index):
        site_page.goto(SITE + news_index.url)

        site_page.get_by_role("button", name="Copy link").click()

        expect(site_page.locator("[data-copy-status]")).to_have_text(
            "Press Ctrl+C (or ⌘+C) to copy the selected link."
        )

    def test_tells_the_reader_what_to_do_in_nepali(self, site_page, news_index, nepali_home_page):
        nepali_index = news_index.copy_for_translation(nepali_home_page.locale)
        nepali_index.save_revision().publish()
        site_page.goto(SITE + nepali_index.url)

        site_page.get_by_role("button", name="लिङ्क कपी गर्नुहोस्").click()

        expect(site_page.locator("[data-copy-status]")).to_have_text(
            "छानिएको लिङ्क कपी गर्न Ctrl+C (वा ⌘+C) थिच्नुहोस्।"
        )
