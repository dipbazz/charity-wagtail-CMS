"""The Donate form in a real browser: what only happens there (CSS show and hide, scripts).

pytest's HTML checks in test_donate.py can't see these. Run `uv run playwright install chromium`
once; `uv run pytest -m "not browser"` leaves them out.
"""

import re

import pytest
from playwright.sync_api import expect

from campaigns.models import Pledge
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


class TestSendingAgain:
    # Regression: going back from the thank-you page showed the filled-in form, and sending it
    # again added a second pledge. Found in review of #110 on 2026-10-06.
    def test_going_back_and_sending_again_keeps_one_pledge(self, donate_form):
        amount_card(donate_form, "Rs 2,500").click()
        donate_form.get_by_label("Your name").fill("Sita Sharma")
        donate_form.get_by_label("Email address").fill("sita@example.com")
        send = donate_form.get_by_role("button", name="Send my pledge")

        send.click()
        expect(donate_form).to_have_url(re.compile(r"/thank-you/$"))
        donate_form.go_back()
        expect(donate_form.get_by_label("Your name")).to_have_value("Sita Sharma")
        send.click()
        expect(donate_form).to_have_url(re.compile(r"/thank-you/$"))

        assert Pledge.objects.count() == 1

    def test_opening_the_donate_page_again_starts_a_new_pledge(self, donate_form, donate_page):
        for _ in range(2):
            donate_form.goto(SITE + donate_page.url)
            amount_card(donate_form, "Rs 2,500").click()
            donate_form.get_by_label("Your name").fill("Sita Sharma")
            donate_form.get_by_label("Email address").fill("sita@example.com")
            donate_form.get_by_role("button", name="Send my pledge").click()
            expect(donate_form).to_have_url(re.compile(r"/thank-you/$"))

        assert Pledge.objects.count() == 2


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


class TestMessageCount:
    """Typing stops at 1000 characters (maxlength), so a count shows how many are left before
    a supporter mistakes the limit for a frozen phone. Asked for in review of #101."""

    @pytest.fixture
    def message(self, donate_form):
        return donate_form.locator("#id_message")

    def count(self, page):
        return page.locator(".char-count")

    def test_shows_how_many_characters_are_typed(self, donate_form, message):
        expect(self.count(donate_form)).to_have_text("0/1000 characters")

        message.fill("In memory")
        message.press_sequentially("!")

        expect(self.count(donate_form)).to_have_text("10/1000 characters")

    def test_is_quiet_until_950_characters(self, donate_form, message):
        message.fill("x" * 949)

        expect(self.count(donate_form)).not_to_have_class(re.compile("is-near-limit"))
        expect(message).not_to_have_class(re.compile("is-near-limit"))

    def test_turns_yellow_from_950_characters(self, donate_form, message):
        message.fill("x" * 949)
        message.press_sequentially("x")

        expect(self.count(donate_form)).to_have_text("950/1000 characters")
        expect(self.count(donate_form)).to_have_class(re.compile("is-near-limit"))
        expect(message).to_have_class(re.compile("is-near-limit"))
        expect(message).to_have_css("border-top-color", "rgb(242, 177, 52)")  # --colour-accent

    def test_typing_stops_at_1000_characters(self, donate_form, message):
        message.fill("x" * 999)
        message.press_sequentially("yz")

        expect(message).to_have_value("x" * 999 + "y")
        expect(self.count(donate_form)).to_have_text("1000/1000 characters")

    def test_screen_readers_hear_when_the_limit_is_near_and_reached(self, donate_form, message):
        status = donate_form.locator("#id_message_count_status")
        expect(status).to_have_attribute("role", "status")
        expect(self.count(donate_form)).to_have_attribute("aria-hidden", "true")

        message.fill("x" * 949)
        message.press_sequentially("x")
        expect(status).to_have_text("You have 50 characters left.")

        message.fill("x" * 999)
        message.press_sequentially("x")
        expect(status).to_have_text("You've reached the limit of 1000 characters.")


class TestMessageCountInNepali:
    """The count's words come from the page, so a Nepali page counts in Nepali (#116)."""

    @pytest.fixture
    def nepali_form(self, site_page, donate_page, nepali_home_page):
        translation = donate_page.copy_for_translation(nepali_home_page.locale)
        translation.save_revision().publish()
        site_page.goto(SITE + translation.url)
        return site_page

    def test_counts_and_warns_in_nepali(self, nepali_form):
        message = nepali_form.locator("#id_message")
        status = nepali_form.locator("#id_message_count_status")
        expect(nepali_form.locator(".char-count")).to_have_text("0/1000 अक्षर")

        message.fill("x" * 949)
        message.press_sequentially("x")
        expect(nepali_form.locator(".char-count")).to_have_text("950/1000 अक्षर")
        expect(status).to_have_text("तपाईंसँग 50 अक्षर बाँकी छन्।")

        message.fill("x" * 999)
        message.press_sequentially("x")
        expect(status).to_have_text("तपाईं 1000 अक्षरको सीमामा पुग्नुभयो।")
