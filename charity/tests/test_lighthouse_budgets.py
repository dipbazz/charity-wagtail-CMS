"""The page-weight budgets in lighthouserc.json follow one rule, so a template or CSS change
doesn't need a budget edit: images get a strict budget of their own, and everything else (HTML,
CSS, JavaScript) shares one fixed allowance on top of it."""

import json
from pathlib import Path

import pytest

# Today's HTML, CSS and JavaScript weigh 16-20KB on every page; this leaves room to grow.
OTHER_ALLOWANCE = 25_000

CONFIG = json.loads(Path("lighthouserc.json").read_text(encoding="utf-8"))
PAGES = [
    entry["assertions"]
    for entry in CONFIG["ci"]["assert"]["assertMatrix"]
    if "resource-summary:total:size" in entry["assertions"]
]


def budget(assertions, audit):
    return assertions[audit][1]["maxNumericValue"]


def test_every_checked_page_has_a_total_and_an_image_budget():
    assert len(PAGES) == 4
    assert all("resource-summary:image:size" in page for page in PAGES)


@pytest.mark.parametrize(
    "page", PAGES, ids=lambda page: str(budget(page, "resource-summary:image:size"))
)
def test_total_budget_is_the_image_budget_plus_the_fixed_allowance(page):
    total = budget(page, "resource-summary:total:size")
    images = budget(page, "resource-summary:image:size")

    assert total == images + OTHER_ALLOWANCE
