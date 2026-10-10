"""Site settings in the Wagtail admin, in a real browser.

Run `uv run playwright install chromium` once; `uv run pytest -m "not browser"` leaves these out.
"""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from conftest import SITE

pytestmark = [pytest.mark.browser, pytest.mark.django_db]


# Regression: a refused brand colour reloaded Site settings on the Organisation tab, so the
# message on the Brand tab was out of sight. Found by the owner while testing #152.
def test_a_refused_brand_colour_shows_its_message(site_page, client, moderator, site):
    client.force_login(moderator)
    site_page.goto(SITE + reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk]))
    site_page.get_by_role("tab", name="Brand").click()
    site_page.locator("#id_main_colour").fill("#f2b134")

    site_page.get_by_role("button", name="Save").click()

    expect(site_page.get_by_text("Too light to read easily")).to_be_visible()
