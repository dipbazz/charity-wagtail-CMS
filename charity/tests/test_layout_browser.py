"""The page layout every template shares (base.html), in a real browser.

pytest's HTML checks can't see where things end up on screen. Run
`uv run playwright install chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest
from wagtail_factories import ImageFactory

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
    for title in ("About us", "Appeals", "Stories", "Volunteer with us"):
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


@pytest.fixture
def logo_header(demo_header):
    """The demo header with a logo four times as wide as it is tall: the hardest shape for the
    name bar of a 320px phone."""
    site_settings = SiteSettings.for_site(demo_header)
    site_settings.logo = ImageFactory(file__width=1200, file__height=300)
    site_settings.save()
    return demo_header


# The charity's logo (#123) sits beside its name, on the name's own row, tall enough to read the
# lettering in a seal: 5rem on a phone, 6rem where the whole header fits on one line.
@pytest.mark.parametrize(
    ("width", "height", "logo_height"), [(320, 700, 80), (768, 900, 80), (1440, 900, 96)]
)
def test_logo_and_name_are_centred_together_on_their_own_row(
    site_page, logo_header, width, height, logo_height
):
    site_page.set_viewport_size({"width": width, "height": height})
    site_page.goto(SITE + "/")

    logo = box(site_page, ".brand-logo")
    brand = box(site_page, ".brand")
    controls = box(site_page, ".site-header > .container")

    assert logo["height"] == pytest.approx(logo_height, abs=0.5)
    assert logo["x"] >= 16 - 1
    assert logo["x"] + logo["width"] <= width - 16 + 1
    assert brand["y"] + brand["height"] <= controls["y"]
    assert brand["x"] + brand["width"] / 2 == pytest.approx(width / 2, abs=1)
    assert site_page.evaluate("document.documentElement.scrollWidth") == width


# A charity chooses how tall its logo is, from the smallest (2.5rem everywhere) to the largest
# (5rem, and 6rem from 68rem). In between, both heights grow together.
@pytest.mark.parametrize(
    ("size", "phone", "wide"), [(40, 40, 40), (60, 60, 68), (80, 80, 96)], ids=["min", "mid", "max"]
)
def test_the_chosen_size_sets_the_logos_height_on_a_phone_and_a_wide_screen(
    site_page, logo_header, size, phone, wide
):
    site_settings = SiteSettings.for_site(logo_header)
    site_settings.logo_size = size
    site_settings.save()

    for width, expected in ((320, phone), (1440, wide)):
        site_page.set_viewport_size({"width": width, "height": 900})
        site_page.goto(SITE + "/")

        assert box(site_page, ".brand-logo")["height"] == pytest.approx(expected, abs=0.5)
        # The row is at least 44px, the smallest tap target, whatever the logo's height.
        assert box(site_page, ".brand-bar")["height"] == pytest.approx(
            max(expected, 44) + 12, abs=1
        )
        assert site_page.evaluate("document.documentElement.scrollWidth") == width


def test_a_long_name_beside_a_wide_logo_wraps_without_moving_the_controls(site_page, logo_header):
    logo_header.site_name = "Apanga Bal Sikshya Sarokar Kendra Nepal"
    logo_header.save()
    site_page.set_viewport_size({"width": 320, "height": 700})
    site_page.goto(SITE + "/")

    menu = box(site_page, ".menu-toggle")
    donate = box(site_page, ".header-actions .button")
    brand = box(site_page, ".brand")

    assert menu["y"] == pytest.approx(donate["y"], abs=4)
    assert brand["x"] >= 0
    assert brand["x"] + brand["width"] <= 320
    assert site_page.evaluate("document.documentElement.scrollWidth") == 320


@pytest.mark.parametrize(("width", "height"), [(320, 700), (1440, 900)])
def test_the_name_bar_is_the_logo_and_its_padding_and_no_taller(
    site_page, logo_header, width, height
):
    """The row grows to hold the logo, by its padding (0.375rem above and below) and no more."""
    site_page.set_viewport_size({"width": width, "height": height})
    site_page.goto(SITE + "/")

    logo = box(site_page, ".brand-logo")
    name_bar = box(site_page, ".brand-bar")

    assert name_bar["height"] == pytest.approx(logo["height"] + 12, abs=1)


@pytest.mark.parametrize(("width", "height"), [(320, 700), (1440, 900)])
def test_header_with_a_logo_is_the_same_height_in_both_languages(
    site_page, logo_header, width, height
):
    site_page.set_viewport_size({"width": width, "height": height})
    heights = {}
    for path in ("/", "/ne/"):
        site_page.goto(SITE + path)
        assert site_page.locator(".brand-logo").count() == 1
        heights[path] = box(site_page, ".site-header")["height"]

    assert heights["/ne/"] == pytest.approx(heights["/"], abs=0.5)


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


WHITE = "rgb(255, 255, 255)"
NO_FILL = "rgba(0, 0, 0, 0)"


# The header was white on white pages, so it didn't look like a header. Found in review of #122.
@pytest.mark.parametrize("width", [320, 1440])
def test_header_is_set_apart_from_a_white_page(site_page, demo_header, width):
    site_page.set_viewport_size({"width": width, "height": 800})
    site_page.goto(SITE + "/")

    name_bar = site_page.evaluate(
        "getComputedStyle(document.querySelector('.brand-bar')).backgroundColor"
    )
    shadow = site_page.evaluate(
        "getComputedStyle(document.querySelector('.site-header')).boxShadow"
    )

    assert name_bar not in (WHITE, NO_FILL)
    assert shadow != "none"


def style(site_page, selector, prop):
    return site_page.evaluate(
        "([s, p]) => getComputedStyle(document.querySelector(s))[p]", [selector, prop]
    )


# A light name bar is white, like the controls row below it, and a light footer is pale, like
# the page above it, so each is set apart by a line (#134).
def test_a_light_name_bar_and_footer_are_set_apart_by_a_line(site_page, demo_header):
    site_settings = SiteSettings.for_site(demo_header)
    site_settings.name_bar_style = "light"
    site_settings.footer_style = "light"
    site_settings.save()
    site_page.set_viewport_size({"width": 320, "height": 700})
    site_page.goto(SITE + "/")

    assert style(site_page, ".brand-bar", "backgroundColor") == WHITE
    assert style(site_page, ".brand-bar", "borderBottomWidth") == "1px"
    assert style(site_page, ".site-footer", "backgroundColor") not in (WHITE, NO_FILL)
    assert style(site_page, ".site-footer", "borderTopWidth") == "1px"


# A bold current language beside an underlined link read as "the bold one isn't selected". Found
# in review of #122: the current language is filled, the other is an outlined button, no underlines.
def test_the_current_language_is_filled_and_the_other_is_an_outlined_button(site_page, demo_header):
    site_page.set_viewport_size({"width": 1440, "height": 900})
    site_page.goto(SITE + "/")
    current = ".language-switcher a[aria-current]"
    other = ".language-switcher a:not([aria-current])"

    assert style(site_page, current, "backgroundColor") not in (WHITE, NO_FILL)
    assert style(site_page, other, "backgroundColor") in (WHITE, NO_FILL)
    assert style(site_page, other, "borderTopWidth") == "2px"
    for link in (current, other):
        assert style(site_page, link, "textDecorationLine") == "none"


def test_on_a_phone_the_other_language_is_an_outlined_button(site_page, demo_header):
    site_page.set_viewport_size({"width": 320, "height": 700})
    site_page.goto(SITE + "/ne/")
    other = ".language-switcher a:not([aria-current])"

    assert site_page.locator(".language-switcher a:visible").count() == 1
    assert style(site_page, other, "borderTopWidth") == "2px"
    assert style(site_page, other, "textDecorationLine") == "none"
    assert site_page.evaluate("document.documentElement.scrollWidth") == 320
