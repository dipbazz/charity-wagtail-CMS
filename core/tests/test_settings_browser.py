"""Site settings in the Wagtail admin, in a real browser.

Run `uv run playwright install chromium` once; `uv run pytest -m "not browser"` leaves these out.
"""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from conftest import SITE
from core.brand import DEFAULT_MAIN
from core.models import SiteSettings

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


def test_the_preview_shows_an_unsaved_colour(site_page, client, moderator, site, home_page):
    """Wagtail's own preview panel sends the unsaved form and shows a page drawn with it (#136)."""
    client.force_login(moderator)
    site_page.goto(SITE + reverse("wagtailsettings:edit", args=["core", "sitesettings", site.pk]))
    site_page.get_by_role("tab", name="Brand").click()
    site_page.locator("#id_main_colour").fill("#8e1b3b")

    site_page.get_by_role("button", name="Toggle preview").click()

    # The name bar is the main colour's dark shade: #8e1b3b at 70%.
    name_bar = site_page.frame_locator("#w-preview-iframe").locator(".brand-bar")
    expect(name_bar).to_have_css("background-color", "rgb(99, 19, 41)")
    assert SiteSettings.for_site(site).main_colour == DEFAULT_MAIN
