"""The page layout every template shares (base.html), in a real browser.

pytest's HTML checks can't see where things end up on screen. Run
`uv run playwright install chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest

from campaigns.tests.factories import CampaignIndexPageFactory, DonatePageFactory
from conftest import SITE

pytestmark = [pytest.mark.browser, pytest.mark.django_db]


# Regression: ISSUE-001 — the appeal and news filter links were 27px tall, under the 44px tap
# target. Found by /qa on 2026-10-06 (PR #106).
def test_filter_links_are_big_enough_to_tap(site_page, home_page):
    appeals = CampaignIndexPageFactory(parent=home_page)
    site_page.set_viewport_size({"width": 375, "height": 812})
    site_page.goto(SITE + appeals.url)

    filters = site_page.locator(".tag-list a")

    assert filters.count() == 3
    for box in (filters.nth(n).bounding_box() for n in range(filters.count())):
        assert box["height"] >= 44


# Regression: on short pages the footer stopped partway up the window, leaving a white strip
# below it (#37).
@pytest.mark.parametrize(("width", "height"), [(375, 812), (1440, 900)])
def test_footer_reaches_the_bottom_of_the_window_on_a_short_page(site_page, width, height):
    site_page.set_viewport_size({"width": width, "height": height})
    site_page.goto(SITE + "/search/?query=zzqx")

    footer = site_page.locator(".site-footer").bounding_box()

    assert footer["y"] + footer["height"] == pytest.approx(height, abs=1)


# Regression: ISSUE-002 — the privacy notice links were 22px (footer) and 27px (forms) tall, under
# the 44px tap target, as were the footer's email and social links.
# Found by /qa on 2026-10-07 (PR #125).
def test_footer_and_form_links_are_big_enough_to_tap(site_page, home_page, privacy_notice):
    donate = DonatePageFactory(parent=home_page)
    site_page.set_viewport_size({"width": 375, "height": 812})
    site_page.goto(SITE + donate.url)

    links = site_page.locator(".site-footer li a, .privacy-link a")

    assert links.count() == 2
    for box in (links.nth(n).bounding_box() for n in range(links.count())):
        assert box["height"] >= 44
