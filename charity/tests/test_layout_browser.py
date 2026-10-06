"""The page layout every template shares (base.html), in a real browser.

pytest's HTML checks can't see where things end up on screen. Run
`uv run playwright install chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest

from conftest import SITE

pytestmark = [pytest.mark.browser, pytest.mark.django_db]


# Regression: on short pages the footer stopped partway up the window, leaving a white strip
# below it (#37).
@pytest.mark.parametrize(("width", "height"), [(375, 812), (1440, 900)])
def test_footer_reaches_the_bottom_of_the_window_on_a_short_page(site_page, width, height):
    site_page.set_viewport_size({"width": width, "height": height})
    site_page.goto(SITE + "/search/?query=zzqx")

    footer = site_page.locator(".site-footer").bounding_box()

    assert footer["y"] + footer["height"] == pytest.approx(height, abs=1)
