import re
from pathlib import Path

import pytest
from PIL import ImageColor

CSS = Path(__file__).resolve().parents[2] / "charity" / "static" / "css"
# Every page loads charity.css, which holds the design tokens. A page's own stylesheet, such as
# donate.css, only uses them, and is checked by the same rules.
MAIN = CSS / "charity.css"
STYLESHEETS = sorted(CSS.glob("*.css"))
each_stylesheet = pytest.mark.parametrize("stylesheet", STYLESHEETS, ids=lambda path: path.name)


def media_queries(stylesheet):
    return re.findall(r"@media\s*([^{]+)\{", stylesheet.read_text(encoding="utf-8"))


@each_stylesheet
def test_stylesheet_is_written_mobile_first(stylesheet):
    """Base styles are the phone layout; wider screens only add to them.

    So every width query is a `min-width` in rem, which also follows the visitor's text size.
    A `max-width` query would mean the phone layout is an override of the desktop one.
    """
    width_queries = [query.strip() for query in media_queries(stylesheet) if "width" in query]

    assert [
        query for query in width_queries if not re.fullmatch(r"\(min-width: [\d.]+rem\)", query)
    ] == []


def test_breakpoints_are_found():
    """So the check above can't pass by finding no queries at all."""
    assert [query for query in media_queries(MAIN) if "width" in query]


def rules(stylesheet):
    """(selector, declarations) for every rule, comments removed."""
    css = re.sub(r"/\*.*?\*/", "", stylesheet.read_text(encoding="utf-8"), flags=re.S)
    return [(selector.strip(), body) for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


COLOUR_CODE = re.compile(
    r"#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\(", re.IGNORECASE
)
# A whole word, so "tan" is found in "border: 1px solid tan" but not in "var(--colour-tan)".
WORD = re.compile(r"(?<![\w-])[a-z]+(?![\w-])", re.IGNORECASE)


def is_colour_word(word):
    try:
        ImageColor.getrgb(word)
    except ValueError:
        return False
    return True


def writes_a_colour(value):
    return bool(COLOUR_CODE.search(value)) or any(is_colour_word(w) for w in WORD.findall(value))


@each_stylesheet
def test_every_colour_outside_root_is_a_design_token(stylesheet):
    """Rules read their colours from `:root` with `var(--…)`, never write one of their own (#132).

    A colour written into a rule can't be changed from one place, so a charity's brand colours
    (#131) would reach most of the site and miss the rest.
    """
    assert [
        f"{selector} {{ {declaration.strip()} }}"
        for selector, body in rules(stylesheet)
        if selector != ":root"
        for declaration in body.split(";")
        if writes_a_colour(declaration.partition(":")[2])
    ] == []


@each_stylesheet
def test_every_token_a_rule_uses_is_defined_in_root(stylesheet):
    """A misspelt token isn't an error in CSS: the declaration is silently dropped."""
    defined = {
        name
        for selector, body in rules(MAIN)
        if selector == ":root"
        for name in re.findall(r"(--[\w-]+)\s*:", body)
    }
    used = {name for _, body in rules(stylesheet) for name in re.findall(r"var\((--[\w-]+)", body)}

    assert used - defined == set()


@each_stylesheet
def test_only_the_main_stylesheet_defines_tokens(stylesheet):
    """One `:root`, so each token has one value and a page's stylesheet can't redefine it."""
    roots = [selector for selector, _ in rules(stylesheet) if selector == ":root"]

    assert len(roots) == (1 if stylesheet == MAIN else 0)


@each_stylesheet
def test_letter_spacing_and_capitals_are_kept_off_nepali_text(stylesheet):
    """Letter spacing splits Devanagari conjuncts, and Devanagari has no capitals (#118).

    So a rule may only set them on English text, with a `:lang(en)` selector.
    """
    assert [
        selector
        for selector, body in rules(stylesheet)
        if re.search(r"letter-spacing|text-transform", body) and ":lang(en)" not in selector
    ] == []


def test_nepali_text_uses_the_devices_own_devanagari_font():
    # No web font: each platform's Devanagari font, named so the browser doesn't pick an old one.
    font = re.search(r"--font:([^;]+);", MAIN.read_text(encoding="utf-8")).group(1)

    for name in ("Noto Sans Devanagari", "Kohinoor Devanagari", "Nirmala UI"):
        assert f'"{name}"' in font
    for stylesheet in STYLESHEETS:
        assert "@font-face" not in stylesheet.read_text(encoding="utf-8")


def test_nepali_text_has_room_for_marks_above_and_below_the_letters():
    line_heights = {
        selector: float(re.search(r"line-height:\s*([\d.]+)", body).group(1))
        for stylesheet in STYLESHEETS
        for selector, body in rules(stylesheet)
        if ":lang(ne)" in selector and "line-height" in body
    }

    assert line_heights.get("body:lang(ne)", 0) >= 1.8
    assert min(line_heights.values()) >= 1.4
