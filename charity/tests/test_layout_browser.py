"""The page layout every template shares (base.html), in a real browser.

pytest's HTML checks can't see where things end up on screen. Run
`uv run playwright install chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest

from campaigns.tests.factories import CampaignIndexPageFactory
from conftest import SITE
from core.models import SiteSettings
from home.models import StandardPage

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


# Regression: ISSUE-002 — the header was 6px taller on Nepali pages than on English ones, because
# the line height meant for Nepali paragraphs reached the Menu and Donate buttons and the search
# box, so switching language moved the page. Found by /qa on 2026-10-07 (PR #122).
@pytest.mark.parametrize(("width", "height"), [(320, 700), (1440, 900)])
def test_header_is_the_same_height_in_both_languages(
    site_page, site, home_page, nepali_home_page, width, height
):
    # A site name long enough to wrap at 320px, and a Donate button, as on the demo site.
    site.site_name = "Brightwell Water Trust"
    site.save()
    donate = StandardPage(title="Donate", slug="donate")
    home_page.add_child(instance=donate)
    site_settings = SiteSettings.for_site(site)
    site_settings.donate_page = donate
    site_settings.save()
    site_page.set_viewport_size({"width": width, "height": height})
    heights = {}
    for path in ("/", "/ne/"):
        site_page.goto(SITE + path)
        heights[path] = site_page.locator(".site-header").bounding_box()["height"]

    assert heights["/ne/"] == pytest.approx(heights["/"], abs=0.5)
