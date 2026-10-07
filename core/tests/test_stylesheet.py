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


def rules():
    """(selector, declarations) for every rule, comments removed."""
    css = re.sub(r"/\*.*?\*/", "", STYLESHEET.read_text(encoding="utf-8"), flags=re.S)
    return [(selector.strip(), body) for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def test_letter_spacing_and_capitals_are_kept_off_nepali_text():
    """Letter spacing splits Devanagari conjuncts, and Devanagari has no capitals (#118).

    So a rule may only set them on English text, with a `:lang(en)` selector.
    """
    assert [
        selector
        for selector, body in rules()
        if re.search(r"letter-spacing|text-transform", body) and ":lang(en)" not in selector
    ] == []


def test_nepali_text_uses_the_devices_own_devanagari_font():
    # No web font: each platform's Devanagari font, named so the browser doesn't pick an old one.
    font = re.search(r"--font:([^;]+);", STYLESHEET.read_text(encoding="utf-8")).group(1)

    for name in ("Noto Sans Devanagari", "Kohinoor Devanagari", "Nirmala UI"):
        assert f'"{name}"' in font
    assert "@font-face" not in STYLESHEET.read_text(encoding="utf-8")


def test_nepali_text_has_room_for_marks_above_and_below_the_letters():
    line_heights = {
        selector: float(re.search(r"line-height:\s*([\d.]+)", body).group(1))
        for selector, body in rules()
        if ":lang(ne)" in selector and "line-height" in body
    }

    assert line_heights.get("body:lang(ne)", 0) >= 1.8
    assert min(line_heights.values()) >= 1.4
