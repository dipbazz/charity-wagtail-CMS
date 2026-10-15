"""The QR page in a real browser: what only happens there (CSS choosing a code, the copy buttons).

pytest's HTML checks in test_qr.py can't see these. Run `uv run playwright install chromium`
once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest
from playwright.sync_api import expect

from campaigns.models import Pledge
from campaigns.tests.test_qr import make_code
from conftest import SITE

pytestmark = [pytest.mark.browser, pytest.mark.django_db]

# http://testserver isn't a secure origin, so the browser has no clipboard. This gives the page
# one that remembers what it was asked to copy.
FAKE_CLIPBOARD = """
Object.defineProperty(navigator, "clipboard", {
    value: { writeText: async (text) => { window.copiedText = text; } },
});
"""


@pytest.fixture
def qr_page(site_page, donate_page):
    make_code("eSewa", account_name="BRIGHTWELL WATER", account_number="9801234567")
    make_code("Fonepay (bank)", account_name="BRIGHTWELL WATER TRUST")
    pledge = Pledge.objects.create(
        page=donate_page, amount=2500, currency="NPR", name="Sita", email="sita@example.com"
    )
    site_page.goto(f"{SITE}{donate_page.url}pay/{pledge.reference}/qr/")
    return site_page


class TestChoosingAnApp:
    def test_shows_only_the_chosen_code(self, qr_page):
        expect(qr_page.locator(".qr-card").nth(0)).to_be_visible()
        expect(qr_page.locator(".qr-card").nth(1)).to_be_hidden()

        qr_page.locator(".qr-choice .amount-option", has_text="Fonepay (bank)").click()

        expect(qr_page.locator(".qr-card").nth(0)).to_be_hidden()
        expect(qr_page.locator(".qr-card").nth(1)).to_be_visible()

    def test_the_chosen_codes_is_the_one_sent(self, qr_page):
        qr_page.locator(".qr-choice .amount-option", has_text="Fonepay (bank)").click()

        chosen = qr_page.locator(".qr-choice input:checked").get_attribute("value")

        assert (
            chosen
            == qr_page.locator(".qr-card").nth(1).get_attribute("aria-labelledby").split("-")[-1]
        )


class TestCopyButtons:
    def test_appear_only_with_javascript_with_their_hint(self, qr_page):
        expect(qr_page.locator("[data-copy-hint]")).to_be_visible()
        expect(qr_page.get_by_role("button", name="Copy amount")).to_be_visible()

    def test_copy_the_plain_value_and_say_so(self, site_page, donate_page):
        site_page.add_init_script(FAKE_CLIPBOARD)
        make_code("eSewa")
        pledge = Pledge.objects.create(
            page=donate_page, amount=2500, currency="NPR", name="Sita", email="sita@example.com"
        )
        site_page.goto(f"{SITE}{donate_page.url}pay/{pledge.reference}/qr/")

        site_page.get_by_role("button", name="Copy amount").click()

        assert site_page.evaluate("window.copiedText") == "2500"
        expect(site_page.locator("[data-copy-status=qr-copy]")).to_have_text("Amount copied")
        expect(site_page.get_by_role("button", name="Copy amount")).to_have_class(
            "copy-icon-button is-copied"
        )
        site_page.get_by_role("button", name="Copy remarks").click()
        assert site_page.evaluate("window.copiedText") == pledge.number

    def test_say_what_to_do_when_the_browser_has_no_clipboard(self, qr_page):
        qr_page.get_by_role("button", name="Copy amount").click()

        expect(qr_page.locator("[data-copy-status=qr-copy]")).to_have_text(
            "Press and hold the value to copy it."
        )
