"""An appeal page in a real browser: where its parts end up on screen, and its edit page in the
admin.

pytest's HTML checks in test_campaigns.py can't see these. Run `uv run playwright install
--with-deps chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory
from conftest import SITE

pytestmark = [pytest.mark.browser, pytest.mark.django_db]


# Regression: ISSUE-001 — on a 320px phone the appeal's header grid kept a 20rem column inside
# the padded container, so every appeal page scrolled sideways.
# Found by /qa on 2026-10-07 (PR #125).
def test_appeal_page_fits_a_320px_phone(site_page, home_page):
    appeal = CampaignPageFactory(parent=CampaignIndexPageFactory(parent=home_page))
    site_page.set_viewport_size({"width": 320, "height": 800})
    site_page.goto(SITE + appeal.url)

    assert site_page.evaluate("document.documentElement.scrollWidth") <= 320


# Regression: scrolling over an amount in the admin changed it (a number input), so an editor
# scrolling the page could change an appeal's target without noticing (#97).
def test_scrolling_over_an_amount_in_the_admin_leaves_it(site_page, client, editor, home_page):
    appeal = CampaignPageFactory(parent=CampaignIndexPageFactory(parent=home_page))
    client.force_login(editor)
    site_page.goto(SITE + reverse("wagtailadmin_pages:edit", args=[appeal.pk]))
    site_page.get_by_role("tab", name="Fundraising").click()
    target = site_page.locator("#id_target_amount")
    target.fill("50000")

    target.hover()
    for _ in range(3):
        site_page.mouse.wheel(0, 120)

    expect(target).to_have_value("50000")
