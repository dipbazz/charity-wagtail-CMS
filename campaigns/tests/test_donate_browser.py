"""The Donate form in a real browser: what only happens there (CSS show and hide, scripts).

pytest's HTML checks in test_donate.py can't see these. Run `uv run playwright install chromium`
once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest
from playwright.sync_api import expect

from conftest import SITE

pytestmark = [pytest.mark.browser, pytest.mark.django_db]


@pytest.fixture
def donate_form(site_page, donate_page):
    site_page.goto(SITE + donate_page.url)
    return site_page


def amount_card(page, label):
    return page.locator(".amount-option", has_text=label)


class TestRevealedFields:
    def test_own_amount_and_mobile_number_start_hidden(self, donate_form):
        expect(donate_form.locator("#id_other_amount")).to_be_hidden()
        expect(donate_form.locator("#id_phone")).to_be_hidden()

    def test_other_amount_shows_your_own_amount(self, donate_form):
        amount_card(donate_form, "Other amount").click()

        expect(donate_form.locator("#id_other_amount")).to_be_visible()

    def test_monthly_shows_the_mobile_number(self, donate_form):
        donate_form.get_by_label("Monthly").check()

        expect(donate_form.locator("#id_phone")).to_be_visible()

    def test_choosing_a_card_clears_a_typed_own_amount(self, donate_form):
        amount_card(donate_form, "Other amount").click()
        donate_form.locator("#id_other_amount").fill("4000")

        amount_card(donate_form, "Rs 2,500").click()

        expect(donate_form.locator("#id_other_amount")).to_be_hidden()
        expect(donate_form.locator("#id_other_amount")).to_have_value("")
