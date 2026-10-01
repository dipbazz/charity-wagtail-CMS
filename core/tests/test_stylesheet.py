import re
from pathlib import Path

STYLESHEET = Path(__file__).resolve().parents[2] / "charity" / "static" / "css" / "charity.css"


def media_queries():
    return re.findall(r"@media\s*([^{]+)\{", STYLESHEET.read_text(encoding="utf-8"))


def test_stylesheet_is_written_mobile_first():
    """Base styles are the phone layout; wider screens only add to them.

    So every width query is a `min-width` in rem, which also follows the visitor's text size.
    A `max-width` query would mean the phone layout is an override of the desktop one.
    """
    width_queries = [query.strip() for query in media_queries() if "width" in query]

    assert width_queries, "expected the stylesheet to have breakpoints"
    assert [
        query for query in width_queries if not re.fullmatch(r"\(min-width: [\d.]+rem\)", query)
    ] == []
