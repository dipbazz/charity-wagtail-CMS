import colorsys
import itertools
import re

import pytest
from django.core.exceptions import ValidationError

from core.brand import (
    DEFAULT_ACCENT,
    DEFAULT_LOGO_SIZE,
    DEFAULT_MAIN,
    LOGO_MAX,
    LOGO_MIN,
    MIN_CONTRAST,
    TEXT,
    WHITE,
    accent_contrast,
    accent_shades,
    contrast,
    custom_properties,
    logo_heights,
    luminance,
    main_contrast,
    main_shades,
    validate_accent_colour,
    validate_main_colour,
)
from core.tests.test_stylesheet import rules

# A main and an accent colour a charity might choose: crimson and blue.
MAIN = "#8e1b3b"
ACCENT = "#1f6feb"

# Every 17th step of each channel: 4,096 colours from black to white.
GRID = [
    "#{:02x}{:02x}{:02x}".format(*channels)
    for channels in itertools.product(range(0, 256, 17), repeat=3)
]


def root():
    """The stylesheet's tokens, such as {"--colour-primary": "#0b5563"}."""
    (body,) = [body for selector, body in rules() if selector == ":root"]
    return {name: value.strip() for name, value in re.findall(r"(--[\w-]+)\s*:([^;]+);", body)}


def hue(colour):
    return colorsys.rgb_to_hls(*(int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)))[0]


def test_the_defaults_are_the_stylesheets_own_colours():
    tokens = root()

    assert tokens["--colour-primary"] == DEFAULT_MAIN
    assert tokens["--colour-accent"] == DEFAULT_ACCENT
    assert tokens["--colour-text"] == TEXT


def test_the_default_colours_write_nothing_so_the_site_looks_as_it_did():
    assert custom_properties(DEFAULT_MAIN, DEFAULT_ACCENT) == ""


def test_every_property_the_brand_writes_replaces_a_stylesheet_token():
    """A misspelt name would be a property nothing reads, so that colour wouldn't change."""
    written = main_shades(MAIN).keys() | accent_shades(ACCENT).keys()

    assert written - root().keys() == set()


class TestLogoSize:
    """How tall the logo is (#123): from small, the size it was first drawn at, to large."""

    def test_the_default_is_the_middle_of_the_range(self):
        assert DEFAULT_LOGO_SIZE == (LOGO_MIN + LOGO_MAX) // 2 == 60

    def test_the_default_size_is_the_stylesheets_own(self):
        tokens = root()

        assert (tokens["--logo-height"], tokens["--logo-height-wide"]) == logo_heights(
            DEFAULT_LOGO_SIZE
        )

    def test_the_smallest_size_is_the_same_on_every_screen(self):
        """The first logo was 2.5rem tall everywhere; the largest is taller on a wide screen."""
        assert logo_heights(LOGO_MIN) == ("2.5rem", "2.5rem")
        assert logo_heights(LOGO_MAX) == ("5rem", "6rem")

    def test_in_between_both_heights_grow_in_proportion(self):
        assert logo_heights(60) == ("3.75rem", "4.25rem")
        assert logo_heights(50) == ("3.125rem", "3.375rem")

    def test_the_default_size_writes_nothing_so_the_site_looks_as_it_did(self):
        assert custom_properties(DEFAULT_MAIN, DEFAULT_ACCENT, DEFAULT_LOGO_SIZE) == ""
        assert custom_properties(DEFAULT_MAIN, DEFAULT_ACCENT) == ""

    def test_the_largest_size_is_written_like_any_other(self):
        css = custom_properties(DEFAULT_MAIN, DEFAULT_ACCENT, LOGO_MAX)

        assert css == "--logo-height:5rem;--logo-height-wide:6rem"

    def test_another_size_writes_both_heights_and_leaves_the_colours_alone(self):
        css = custom_properties(DEFAULT_MAIN, DEFAULT_ACCENT, 50)

        assert css == "--logo-height:3.125rem;--logo-height-wide:3.375rem"

    def test_it_is_written_beside_the_colours(self):
        css = custom_properties(MAIN, ACCENT, LOGO_MIN)

        assert f"--colour-primary:{MAIN};" in css
        assert css.endswith("--logo-height:2.5rem;--logo-height-wide:2.5rem")

    def test_every_property_it_writes_replaces_a_stylesheet_token(self):
        css = custom_properties(DEFAULT_MAIN, DEFAULT_ACCENT, LOGO_MIN)
        written = {declaration.split(":")[0] for declaration in css.split(";")}

        assert written - root().keys() == set()

    @pytest.mark.parametrize("size", [LOGO_MIN - 1, LOGO_MAX + 1, 0, -5, "big", None, True])
    def test_a_size_outside_the_range_is_ignored(self, size):
        """Only a change made outside the admin, which checks it, could save one."""
        assert custom_properties(DEFAULT_MAIN, DEFAULT_ACCENT, size) == ""


def test_a_main_colour_writes_its_shades_and_leaves_the_accent_alone():
    css = custom_properties(MAIN, DEFAULT_ACCENT)

    assert f"--colour-primary:{MAIN};" in css
    assert "--colour-accent" not in css


def test_an_accent_colour_writes_its_shades_and_leaves_the_main_colour_alone():
    css = custom_properties(DEFAULT_MAIN, ACCENT)

    assert f"--colour-accent:{ACCENT};" in css
    assert "--colour-primary" not in css


def test_a_colour_is_written_in_lower_case():
    assert f"--colour-primary:{MAIN};" in custom_properties(MAIN.upper(), DEFAULT_ACCENT)


@pytest.mark.parametrize(("colour", "shades"), [(MAIN, main_shades), (ACCENT, accent_shades)])
def test_every_shade_is_the_chosen_colours_own_hue(colour, shades):
    """Darker or paler, but never another colour, such as the default teal.

    Within a few degrees: rounding to whole numbers turns the palest tints a little.
    """
    of_it = [
        value
        for name, value in shades(colour).items()
        if value.startswith("#") and name != "--colour-on-accent"
    ]

    assert [hue(shade) for shade in of_it] == pytest.approx([hue(colour)] * len(of_it), abs=0.03)


def test_the_dark_shade_is_darker_and_the_panels_paler_than_the_main_colour():
    shades = main_shades(MAIN)

    assert luminance(shades["--colour-primary-dark"]) < luminance(MAIN)
    assert luminance(shades["--colour-surface"]) > luminance(shades["--colour-border"]) > 0.6


def test_the_header_shadow_and_the_photo_overlay_are_the_dark_shade_see_through():
    shades = main_shades(MAIN)
    dark = shades["--colour-primary-dark"]
    red, green, blue = (int(dark[i : i + 2], 16) for i in (1, 3, 5))

    for name in ("--colour-shadow", "--colour-overlay", "--colour-overlay-weak"):
        assert shades[name].startswith(f"rgb({red} {green} {blue} / ")


@pytest.mark.parametrize(
    ("accent", "text"),
    [
        (DEFAULT_ACCENT, TEXT),
        ("#1f3a93", WHITE),  # navy
        ("#909090", TEXT),  # the darkest grey dark text is readable on (4.6:1)
        ("#747474", WHITE),  # the lightest grey white text is readable on (4.7:1)
    ],
)
def test_text_on_the_accent_is_dark_or_white_whichever_is_easier_to_read(accent, text):
    assert accent_shades(accent)["--colour-on-accent"] == text


def test_every_main_colour_that_can_be_saved_keeps_all_its_text_readable():
    """One check guards every text the main colour sets: links in it on its pale panels.

    That includes a light name bar and footer (#134): the name in the dark shade on white, and
    the footer's text, links and quieter lines on a panel.
    """
    muted = root()["--colour-muted"]
    problems = []
    for main in (colour for colour in GRID if main_contrast(colour) >= MIN_CONTRAST):
        shades = main_shades(main)
        pairs = {
            "white text on it": (WHITE, main),
            "links on white": (main, WHITE),
            "links on a panel": (main, shades["--colour-surface"]),
            "white text on the dark shade": (WHITE, shades["--colour-primary-dark"]),
            "the dark shade on white": (shades["--colour-primary-dark"], WHITE),
            "footer text": (shades["--colour-footer-text"], shades["--colour-primary-dark"]),
            "footer's quieter lines": (
                shades["--colour-footer-meta"],
                shades["--colour-primary-dark"],
            ),
            "text on a panel": (TEXT, shades["--colour-surface"]),
            "quieter text on a panel": (muted, shades["--colour-surface"]),
        }
        problems += [f"{main}: {name}" for name, pair in pairs.items() if contrast(*pair) < 4.5]

    assert problems == []


def test_every_accent_colour_that_can_be_saved_keeps_all_its_text_readable():
    problems = []
    for accent in (colour for colour in GRID if accent_contrast(colour) >= MIN_CONTRAST):
        shades = accent_shades(accent)
        text = shades["--colour-on-accent"]
        pairs = {
            "text on it": (text, accent),
            "text on it under the pointer": (text, shades["--colour-accent-hover"]),
            "highlighted text": (TEXT, shades["--colour-highlight"]),
        }
        problems += [f"{accent}: {name}" for name, pair in pairs.items() if contrast(*pair) < 4.5]

    assert problems == []


def test_a_buttons_hover_shade_differs_from_the_button():
    # Darker, or lighter when dark text on a darker shade would be hard to read, or for black.
    for accent in (DEFAULT_ACCENT, ACCENT, "#909090", "#000000"):
        assert accent_shades(accent)["--colour-accent-hover"] != accent


@pytest.mark.parametrize(
    "colour",
    [
        DEFAULT_MAIN,
        MAIN,
        "#727272",  # the lightest grey that passes: 4.5:1 on the pale panels
    ],
)
def test_a_main_colour_dark_enough_to_read_is_accepted(colour):
    validate_main_colour(colour)


@pytest.mark.parametrize(
    "colour",
    [
        "#737373",  # one step lighter than the lightest that passes
        "#767676",  # 4.5:1 on white, but only 4.3:1 on the site's pale panels
        DEFAULT_ACCENT,  # white text on amber
    ],
)
def test_a_main_colour_too_light_to_read_is_rejected(colour):
    with pytest.raises(ValidationError):
        validate_main_colour(colour)


def test_the_message_for_a_light_main_colour_says_why_and_suggests_a_darker_shade():
    with pytest.raises(ValidationError) as error:
        validate_main_colour("#737373")

    (message,) = error.value.messages
    assert "4.4:1" in message
    assert "at least 4.5:1" in message
    suggestion = re.search(r"such as (#[0-9a-f]{6})", message).group(1)
    validate_main_colour(suggestion)
    assert luminance(suggestion) < luminance("#737373")


@pytest.mark.parametrize(
    "colour",
    [DEFAULT_ACCENT, ACCENT, "#909090", "#747474", "#ffffff", "#000000"],
)
def test_an_accent_colour_that_dark_or_white_text_is_readable_on_is_accepted(colour):
    validate_accent_colour(colour)


@pytest.mark.parametrize(
    "colour",
    [
        "#8c8c8c",  # just too dark for dark text, and too light for white text
        "#787878",  # just too light for white text, and too dark for dark text
        "#0077dd",  # a mid blue
    ],
)
def test_an_accent_colour_no_text_is_readable_on_is_rejected(colour):
    with pytest.raises(ValidationError):
        validate_accent_colour(colour)


@pytest.mark.parametrize(("colour", "direction"), [("#8c8c8c", "lighter"), ("#787878", "darker")])
def test_the_message_for_a_mid_tone_accent_suggests_the_nearest_shade_that_passes(
    colour, direction
):
    with pytest.raises(ValidationError) as error:
        validate_accent_colour(colour)

    (message,) = error.value.messages
    assert "at least 4.5:1" in message
    suggestion = re.search(rf"a {direction} shade, such as (#[0-9a-f]{{6}})", message).group(1)
    validate_accent_colour(suggestion)


@pytest.mark.parametrize("value", ["red", "#0b556", "#0b55634", "0b5563", "#0b556g"])
@pytest.mark.parametrize("validate", [validate_main_colour, validate_accent_colour])
def test_a_colour_must_be_a_hex_code(validate, value):
    with pytest.raises(ValidationError, match="six"):
        validate(value)


def test_a_value_that_isnt_a_colour_never_reaches_the_page():
    """The admin only saves hex codes; a value set any other way is ignored, not written out."""
    assert custom_properties("#000;}</style><script>", "red") == ""


def test_the_brand_adds_well_under_a_kilobyte_to_a_page():
    assert len(custom_properties(MAIN, ACCENT).encode()) < 1024
