"""Sharing that you've given (#100) in a real browser: what only happens there (the phone's share
sheet, copying the link, where focus goes once the box is saved).

pytest's HTML checks in test_share_after_paying.py can't see these. Run
`uv run playwright install chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest
from playwright.sync_api import expect

from campaigns.tests.test_qr_browser import FAKE_CLIPBOARD
from campaigns.tests.test_sharing import pledge_in
from conftest import SITE

pytestmark = [pytest.mark.browser, pytest.mark.django_db]

# A phone's share sheet, which remembers what it was asked to share. Desktop Chromium may or may
# not have one, so each test says which it has.
FAKE_SHARE_SHEET = """
Navigator.prototype.share = async function (data) { window.sharedData = data; };
Navigator.prototype.canShare = () => true;
"""
NO_SHARE_SHEET = "delete Navigator.prototype.share; delete Navigator.prototype.canShare;"
# A browser that refuses to copy, as one can on plain http.
NO_CLIPBOARD = """
Object.defineProperty(navigator, "clipboard", {
    value: { writeText: async () => { throw new Error("refused"); } },
});
"""


@pytest.fixture
def thanks(site_page, site, donate_page):
    """Opens the thank-you page of Asha's paid gift, once the test has set up the browser."""
    site.site_name = "Brightwell"
    site.save()
    pledge = pledge_in("paid", donate_page)

    def open_it(*scripts):
        for script in scripts:
            site_page.add_init_script(script)
        site_page.goto(f"{SITE}{donate_page.url}pay/{pledge.reference}/")
        return site_page

    open_it.gift_url = f"http://localhost{donate_page.url}gifts/{pledge.gift_code}/"
    return open_it


class TestTellYourFriends:
    def test_opens_the_phones_share_sheet_with_the_message_and_link(self, thanks):
        page = thanks(FAKE_SHARE_SHEET)

        page.get_by_role("button", name="Tell your friends").click()

        shared = page.evaluate("window.sharedData")
        assert shared["url"] == thanks.gift_url
        assert shared["text"].startswith("I've just given to")
        assert shared["title"] == "Asha Gurung is supporting Brightwell"

    def test_isnt_offered_without_a_share_sheet(self, thanks):
        page = thanks(NO_SHARE_SHEET)

        expect(page.get_by_role("button", name="Tell your friends")).to_be_hidden()
        expect(page.get_by_role("link", name="WhatsApp")).to_be_visible()


class TestCopyLink:
    def test_copies_the_link_and_says_so(self, thanks):
        page = thanks(FAKE_CLIPBOARD)

        page.get_by_role("button", name="Copy link").click()

        assert page.evaluate("window.copiedText") == thanks.gift_url
        expect(page.locator(".share-links button")).to_have_text("Copied ✓")
        expect(page.locator("[data-copy-status=share-link]")).to_have_text("Link copied.")

    def test_gives_the_link_to_copy_by_hand_when_the_browser_wont(self, thanks):
        page = thanks(NO_CLIPBOARD)

        page.get_by_role("button", name="Copy link").click()

        expect(page.locator("[data-copy-status=share-link]")).to_have_text(
            f"Copy this link: {thanks.gift_url}"
        )


class TestSavingTheBox:
    def test_focus_moves_to_the_share_section(self, thanks):
        page = thanks()
        page.get_by_label("Show my gift on this website").uncheck()

        page.get_by_role("button", name="Save").click()

        expect(page.get_by_role("heading", name="Others can help too")).to_be_focused()
        expect(page.get_by_role("status").first).to_have_text(
            "Your page for friends has been taken down."
        )
