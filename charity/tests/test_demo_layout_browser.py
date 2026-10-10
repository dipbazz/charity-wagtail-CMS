"""Every kind of demo page at the six widths the QA pass checks, in a real browser.

This is the mechanical half of QA: a page that scrolls sideways, or a control too small to tap,
fails here on every pull request. What needs eyes (wording, whether a page looks right) is listed
under "Check before merging" in the pull request. Run `uv run playwright install chromium` once;
`uv run pytest -m "not browser"` leaves these out.
"""

import re

import pytest

from conftest import SITE
from core.brand import contrast
from core.models import SiteSettings

pytestmark = [pytest.mark.browser, pytest.mark.django_db]

WIDTHS = [320, 375, 412, 768, 1024, 1440]

# One page of each kind, in both languages where the demo has both.
PATHS = [
    "/",
    "/about/",
    "/appeals/",
    "/appeals/flood-relief/",
    "/stories/",
    "/donate/",
    "/volunteer/",
    "/search/?query=water",
    "/ne/",
    "/ne/appeals/flood-relief/",
    "/ne/donate/",
]

# What a thumb taps. Text links inside a paragraph are exempt: they're as tall as the line.
TAP_TARGETS = (
    ".site-footer a, .tag-list a, .pagination a, .button, button, summary, select,"
    " input:not([type=checkbox]):not([type=radio]):not([type=hidden])"
)

# The measurements the checks need, taken in the page in one go.
MEASURE = """
(selector) => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    small: [...document.querySelectorAll(selector)]
        .filter((el) => el.offsetParent !== null)
        .map((el) => [el, el.getBoundingClientRect()])
        .filter(([, box]) => box.width > 0 && box.height < 43.5)
        .map(([el, box]) => `${el.tagName.toLowerCase()}.${el.className}`.trim()
            + ` "${el.textContent.trim().slice(0, 30)}" is ${Math.round(box.height)}px tall`),
})
"""


def layout_problems(site_page, path):
    """Where `path` scrolls sideways or has a control too small to tap, at each width."""
    problems = []
    for width in WIDTHS:
        site_page.set_viewport_size({"width": width, "height": 800})
        site_page.goto(SITE + path)
        found = site_page.evaluate(MEASURE, TAP_TARGETS)
        if found["scrollWidth"] > found["innerWidth"]:
            problems.append(f"{width}px: scrolls sideways ({found['scrollWidth']}px wide)")
        problems += [f"{width}px: {item}" for item in found["small"]]
    return problems


@pytest.mark.parametrize("path", PATHS)
def test_page_fits_and_can_be_tapped_at_every_width(site_page, demo_site, path):
    problems = layout_problems(site_page, path)

    assert not problems, f"{path}\n" + "\n".join(problems)


# Each text in the name bar and the footer, its colour, and the fill behind it: its own, or the
# nearest ancestor's.
TEXT_AND_FILL = """
(selector) => [...document.querySelectorAll(selector)].map((el) => {
    let filled = el;
    while (getComputedStyle(filled).backgroundColor === "rgba(0, 0, 0, 0)") {
        filled = filled.parentElement;
    }
    return [
        `${el.tagName.toLowerCase()} "${el.textContent.trim().slice(0, 30)}"`,
        getComputedStyle(el).color,
        getComputedStyle(filled).backgroundColor,
    ];
})
"""
NAME_BAR_AND_FOOTER_TEXT = ".brand, .site-footer :is(p, address, li, a)"


def hex_colour(computed):
    """A computed colour, such as "rgb(11, 85, 99)", as "#0b5563"."""
    return "#{:02x}{:02x}{:02x}".format(*(int(n) for n in re.findall(r"\d+", computed)[:3]))


# A light or dark name bar and footer (#134): every combination fits and can be tapped at every
# width, in both languages, and the text on each stays readable.
@pytest.mark.parametrize("footer", ["dark", "light"])
@pytest.mark.parametrize("name_bar", ["dark", "light"])
def test_a_light_or_dark_name_bar_and_footer_fit_and_stay_readable(
    site_page, demo_site, name_bar, footer
):
    site_settings = SiteSettings.for_site(demo_site)
    site_settings.name_bar_style = name_bar
    site_settings.footer_style = footer
    site_settings.save()
    problems = []
    for path in ("/", "/ne/"):
        problems += [f"{path} {item}" for item in layout_problems(site_page, path)]
        assert site_page.locator(".brand-bar.is-light").count() == (name_bar == "light")
        assert site_page.locator(".site-footer.is-light").count() == (footer == "light")
        for text, colour, fill in site_page.evaluate(TEXT_AND_FILL, NAME_BAR_AND_FOOTER_TEXT):
            ratio = contrast(hex_colour(colour), hex_colour(fill))
            if ratio < 4.5:
                problems.append(f"{path} {text}: contrast {ratio:.1f}:1")

    assert not problems, "\n".join(problems)
