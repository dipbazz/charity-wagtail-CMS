"""The page layout every template shares (base.html), in a real browser.

pytest's HTML checks can't see where things end up on screen. Run
`uv run playwright install chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest

from campaigns.tests.factories import CampaignIndexPageFactory, DonatePageFactory
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


@pytest.fixture
def demo_header(site, home_page, nepali_home_page):
    """The demo site's header: its name, a Donate button, and pages in both languages."""
    site.site_name = "Brightwell Water Trust"
    site.save()
    donate = StandardPage(title="Donate", slug="donate")
    home_page.add_child(instance=donate)
    site_settings = SiteSettings.for_site(site)
    site_settings.donate_page = donate
    site_settings.save()
    for title in ("About us", "Appeals", "News", "Volunteer with us"):
        home_page.add_child(instance=StandardPage(title=title, show_in_menus=True))
    return site


def box(site_page, selector):
    return site_page.locator(selector).bounding_box()


# Regression: ISSUE-002 — the header was 6px taller on Nepali pages than on English ones, because
# the line height meant for Nepali paragraphs reached the Menu and Donate buttons and the search
# box, so switching language moved the page. Found by /qa on 2026-10-07 (PR #122).
@pytest.mark.parametrize(("width", "height"), [(320, 700), (1440, 900)])
def test_header_is_the_same_height_in_both_languages(site_page, demo_header, width, height):
    site_page.set_viewport_size({"width": width, "height": height})
    heights = {}
    for path in ("/", "/ne/"):
        site_page.goto(SITE + path)
        heights[path] = box(site_page, ".site-header")["height"]

    assert heights["/ne/"] == pytest.approx(heights["/"], abs=0.5)


@pytest.mark.parametrize(("width", "height"), [(320, 700), (1440, 900)])
def test_charity_name_is_centred_on_its_own_row_above_the_controls(
    site_page, demo_header, width, height
):
    site_page.set_viewport_size({"width": width, "height": height})
    site_page.goto(SITE + "/")

    name = box(site_page, ".brand")
    controls = box(site_page, ".site-header > .container")

    assert name["y"] + name["height"] <= controls["y"]
    assert name["x"] + name["width"] / 2 == pytest.approx(width / 2, abs=1)


def test_phone_has_menu_and_donate_at_the_ends_and_the_other_language_between(
    site_page, demo_header
):
    site_page.set_viewport_size({"width": 320, "height": 700})
    site_page.goto(SITE + "/")

    menu = box(site_page, ".menu-toggle")
    donate = box(site_page, ".header-actions .button")
    languages = site_page.locator(".language-switcher a")
    other = site_page.get_by_role("link", name="नेपाली")

    assert [languages.nth(n).is_visible() for n in range(languages.count())] == [True, False]
    language = other.bounding_box()
    assert menu["x"] == pytest.approx(16, abs=1)
    assert donate["x"] + donate["width"] == pytest.approx(320 - 16, abs=1)
    assert (
        menu["x"] + menu["width"] < language["x"] < language["x"] + language["width"] < donate["x"]
    )
    assert menu["y"] == pytest.approx(donate["y"], abs=4)
    assert site_page.evaluate("document.documentElement.scrollWidth") == 320


@pytest.mark.parametrize("width", [1088, 1440])
def test_wide_screen_puts_menu_left_and_both_languages_then_donate_right(
    site_page, demo_header, width
):
    site_page.set_viewport_size({"width": width, "height": 900})
    site_page.goto(SITE + "/")

    first_item = site_page.locator(".main-nav a").first.bounding_box()
    search = box(site_page, ".search-form")
    nepali = site_page.get_by_role("link", name="नेपाली").bounding_box()
    english = site_page.get_by_role("link", name="English").bounding_box()
    donate = box(site_page, ".header-actions .button")
    row = box(site_page, ".site-header > .container")

    assert first_item["x"] < search["x"] < nepali["x"] < english["x"] < donate["x"]
    assert donate["x"] + donate["width"] == pytest.approx(row["x"] + row["width"] - 16, abs=1)
    for item in (first_item, nepali, english, donate):
        assert item["y"] + item["height"] / 2 == pytest.approx(row["y"] + row["height"] / 2, abs=2)
    assert site_page.evaluate("document.documentElement.scrollWidth") == width


def test_a_long_charity_name_wraps_without_moving_the_controls(site_page, demo_header):
    demo_header.site_name = "Apanga Bal Sikshya Sarokar Kendra Nepal"
    demo_header.save()
    site_page.set_viewport_size({"width": 320, "height": 700})
    site_page.goto(SITE + "/")

    menu = box(site_page, ".menu-toggle")
    donate = box(site_page, ".header-actions .button")

    assert menu["y"] == pytest.approx(donate["y"], abs=4)
    assert site_page.evaluate("document.documentElement.scrollWidth") == 320


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
