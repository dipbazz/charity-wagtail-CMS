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


def test_a_summary_link_shows_the_question_and_its_mistake_on_a_phone(site_page, volunteer_form):
    """A plain #id jump puts the box at the top of the screen, its label and mistake above it."""
    site_page.set_viewport_size({"width": 320, "height": 700})
    site_page.goto(SITE + volunteer_form.url)
    site_page.get_by_role("button", name="Send").click()

    site_page.locator(".error-summary a").nth(1).click()

    expect(site_page.get_by_label("Email address")).to_be_focused()
    field = site_page.locator(".field").filter(has=site_page.get_by_label("Email address"))
    expect(field.locator("label")).to_be_in_viewport(ratio=1)
    expect(field.locator(".errorlist")).to_be_in_viewport(ratio=1)
