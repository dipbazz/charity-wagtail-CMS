"""Form pages in a real browser: what only happens there (scripts).

pytest's HTML checks in test_form_page.py can't see these. Run `uv run playwright install
--with-deps chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest
from playwright.sync_api import expect

from conftest import SITE

pytestmark = [pytest.mark.browser, pytest.mark.django_db]


def test_a_send_with_mistakes_focuses_the_error_summary(site_page, volunteer_form):
    """charity.js focuses it as the page opens (#167), so a screen reader reads it first."""
    site_page.goto(SITE + volunteer_form.url)

    site_page.get_by_role("button", name="Send").click()

    expect(site_page.locator(".error-summary")).to_be_focused()
