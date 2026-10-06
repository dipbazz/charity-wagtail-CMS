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


class TestYourOwnAmount:
    # Regression: scrolling over "Your own amount" changed the amount (a number input), and
    # choosing "Other amount" didn't move the cursor there. Found in review of #89 on 2026-10-05.
    def test_scrolling_over_it_does_not_change_the_amount(self, donate_form):
        amount_card(donate_form, "Other amount").click()
        own_amount = donate_form.locator("#id_other_amount")
        own_amount.fill("4000")

        own_amount.hover()
        for _ in range(3):
            donate_form.mouse.wheel(0, 120)

        expect(own_amount).to_have_value("4000")

    def test_clicking_other_amount_puts_the_cursor_in_it(self, donate_form):
        amount_card(donate_form, "Other amount").click()

        expect(donate_form.locator("#id_other_amount")).to_be_focused()

    def test_arrow_keys_through_the_amounts_keep_focus_on_the_choices(self, donate_form):
        donate_form.locator("#id_amount_0").focus()
        for _ in range(2):
            donate_form.keyboard.press("ArrowDown")

        other = donate_form.locator('input[name="amount"][value="other"]')
        expect(other).to_be_checked()
        expect(other).to_be_focused()


class TestChoices:
    # Regression: each tick box sat on its own line above its label, and only the 20px box
    # could be tapped. Found while building #98 on 2026-10-06.
    @pytest.mark.parametrize("name", ["email_updates", "show_on_website"])
    def test_on_a_phone_the_box_sits_beside_its_label_in_a_row_you_can_tap(self, donate_form, name):
        donate_form.set_viewport_size({"width": 320, "height": 800})
        box = donate_form.locator(f'input[name="{name}"]')
        row = donate_form.locator(f'label[for="id_{name}"]')
        text = row.locator("span")

        box_at, row_at, text_at = box.bounding_box(), row.bounding_box(), text.bounding_box()
        assert text_at["x"] > box_at["x"] + box_at["width"]
        assert abs(text_at["y"] - box_at["y"]) < box_at["height"]
        assert row_at["height"] >= 44
        assert row_at["width"] > 250

        text.click()
        expect(box).to_be_checked()
