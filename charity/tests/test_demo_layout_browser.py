"""Every kind of demo page at the six widths the QA pass checks, in a real browser.

This is the mechanical half of QA: a page that scrolls sideways, or a control too small to tap,
fails here on every pull request. What needs eyes (wording, whether a page looks right) is listed
under "Check before merging" in the pull request. Run `uv run playwright install chromium` once;
`uv run pytest -m "not browser"` leaves these out.
"""

import pytest

from conftest import SITE

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


@pytest.mark.parametrize("path", PATHS)
def test_page_fits_and_can_be_tapped_at_every_width(site_page, demo_site, path):
    problems = []
    for width in WIDTHS:
        site_page.set_viewport_size({"width": width, "height": 800})
        site_page.goto(SITE + path)
        found = site_page.evaluate(MEASURE, TAP_TARGETS)
        if found["scrollWidth"] > found["innerWidth"]:
            problems.append(f"{width}px: scrolls sideways ({found['scrollWidth']}px wide)")
        problems += [f"{width}px: {item}" for item in found["small"]]

    assert not problems, f"{path}\n" + "\n".join(problems)
