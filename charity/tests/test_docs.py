"""The docs site must stay navigable."""

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"


def toctrees(page):
    text = (DOCS / page).read_text(encoding="utf-8")
    return re.findall(r"```\{toctree\}\n(.*?)```", text, flags=re.DOTALL)


def test_the_home_page_table_of_contents_feeds_the_sidebar():
    """sphinx-wagtail-theme builds its sidebar menu from visible tables of contents only
    (toctree(includehidden=False)), so a hidden one on the home page leaves every page's sidebar
    empty.
    """
    # Regression: QA on PR #85 found the docs sidebar empty on every page.
    trees = toctrees("index.md")

    assert trees, "expected the home page to have a table of contents"
    assert [tree for tree in trees if ":hidden:" in tree] == []
