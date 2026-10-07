"""An appeal page in a real browser: where its parts end up on screen.

pytest's HTML checks in test_campaigns.py can't see these. Run `uv run playwright install
chromium` once; `uv run pytest -m "not browser"` leaves them out.
"""

import pytest

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
