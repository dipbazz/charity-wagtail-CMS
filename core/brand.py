"""A charity's brand colours: the main and accent colours chosen in Site settings (#133).

The site makes every other colour it needs from those two (a dark shade for headings, the name
bar and the footer, a hover shade for main buttons, pale tints for panels, borders and the
footer's text) and writes them into each page as CSS custom properties, which replace the
defaults at the top of `charity.css`. A colour that would make text hard to read can't be saved.
"""

import colorsys
import math
import re

from django import forms
from django.core.exceptions import ValidationError

# The stylesheet's own colours, from `:root` in charity.css (a test keeps them the same).
DEFAULT_MAIN = "#0b5563"
DEFAULT_ACCENT = "#f2b134"
TEXT = "#1d2a30"
WHITE = "#ffffff"

# WCAG AA for body text.
MIN_CONTRAST = 4.5

# How much of the main colour is in the pale panels (`--colour-surface`).
SURFACE_TINT = 0.05

HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")


class ColourInput(forms.TextInput):
    """The browser's own colour picker."""

    input_type = "color"


def rgb(colour):
    return tuple(int(colour[i : i + 2], 16) for i in (1, 3, 5))


def hex_colour(channels):
    return "#{:02x}{:02x}{:02x}".format(*(round(channel) for channel in channels))


def luminance(colour):
    """Relative luminance, as WCAG defines it: 0 for black, 1 for white."""

    def linear(channel):
        channel /= 255
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in rgb(colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one, other):
    """The WCAG contrast ratio of two colours, from 1 (the same) to 21 (black and white)."""
    lighter, darker = sorted((luminance(one), luminance(other)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def tint(colour, amount):
    """`colour` mixed into white: 0.05 is a very pale tint, 1 the colour itself."""
    return hex_colour(channel * amount + 255 * (1 - amount) for channel in rgb(colour))


def shade(colour, amount):
    """`colour` mixed into black: 0.7 is a dark shade, 1 the colour itself."""
    return hex_colour(channel * amount for channel in rgb(colour))


def with_lightness(colour, change):
    """`colour` made lighter (a positive `change`, up to 1) or darker, keeping its hue."""
    hue, lightness, saturation = colorsys.rgb_to_hls(*(channel / 255 for channel in rgb(colour)))
    lightness = min(max(lightness + change, 0), 1)
    return hex_colour(channel * 255 for channel in colorsys.hls_to_rgb(hue, lightness, saturation))


def main_shades(main):
    """The custom properties the main colour sets: from the default teal, these amounts give
    shades close to the stylesheet's own."""
    dark = shade(main, 0.7)
    red, green, blue = rgb(dark)

    def see_through(opacity):
        return f"rgb({red} {green} {blue} / {opacity})"

    return {
        "--colour-primary": main,
        "--colour-primary-dark": dark,
        "--colour-surface": tint(main, SURFACE_TINT),
        "--colour-border": tint(main, 0.16),
        "--colour-footer-text": tint(main, 0.15),
        "--colour-footer-meta": tint(main, 0.24),
        "--colour-hero-lead": tint(main, 0.1),
        "--colour-shadow": see_through(0.15),
        "--colour-overlay": see_through(0.75),
        "--colour-overlay-strong": see_through(0.85),
        "--colour-overlay-weak": see_through(0.3),
    }


def text_on(accent):
    """Dark or white text, whichever is easier to read on `accent`."""
    return max((TEXT, WHITE), key=lambda text: contrast(text, accent))


def accent_shades(accent):
    """The custom properties the accent colour sets.

    A main button under the pointer is a darker shade, or a lighter one when the text on it
    would be hard to read on a darker shade (or the accent is black).
    """
    text = text_on(accent)
    hover = with_lightness(accent, -0.1)
    if hover == accent or contrast(text, hover) < MIN_CONTRAST:
        hover = with_lightness(accent, 0.1)
    return {
        "--colour-accent": accent,
        "--colour-accent-hover": hover,
        "--colour-on-accent": text,
        "--colour-highlight": tint(accent, 0.35),
    }


def main_contrast(main):
    """How easy the text the main colour sets is to read where it's hardest: links in it on a
    pale panel.

    White text on it, links on white and the footer's text on its dark shade all read better
    than that, so this one ratio covers them (a test checks every pair).
    """
    return contrast(main, tint(main, SURFACE_TINT))


def accent_contrast(accent):
    """How easy the text on the accent is to read, in the better of dark and white."""
    return contrast(text_on(accent), accent)


def nearest_readable(colour, readability, changes):
    """The closest shade of `colour` that's readable, trying a lightness change of each sign in
    `changes` (1 for lighter, -1 for darker) one step at a time.

    The last step reaches white or black, which both checks pass, so there's always an answer.
    """
    for step in range(1, 101):
        for sign in changes:
            candidate = with_lightness(colour, sign * step / 100)
            if readability(candidate) >= MIN_CONTRAST:
                return candidate


def ratio(value):
    """A contrast ratio for a message, rounded down, so one just short of 4.5 never says 4.5."""
    return f"{math.floor(value * 10) / 10:.1f}"


def validate_hex_colour(colour):
    if not HEX_COLOUR.fullmatch(colour):
        raise ValidationError("Enter a colour as # and six hex digits, like #0b5563.")


def validate_main_colour(colour):
    validate_hex_colour(colour)
    if main_contrast(colour) < MIN_CONTRAST:
        raise ValidationError(
            "Too light to read easily. Links in this colour, and white text on it, need a "
            "contrast of at least 4.5:1, and on the site's pale panels this colour gives "
            "%(ratio)s:1. Try a darker shade, such as %(suggestion)s.",
            params={
                "ratio": ratio(main_contrast(colour)),
                "suggestion": nearest_readable(colour.lower(), main_contrast, (-1,)),
            },
        )


def validate_accent_colour(colour):
    validate_hex_colour(colour)
    if accent_contrast(colour) < MIN_CONTRAST:
        suggestion = nearest_readable(colour.lower(), accent_contrast, (1, -1))
        raise ValidationError(
            "Neither dark nor white text is easy to read on this colour: text on it needs a "
            "contrast of at least 4.5:1, and the better of them gives %(ratio)s:1. Try a "
            "%(direction)s shade, such as %(suggestion)s.",
            params={
                "ratio": ratio(accent_contrast(colour)),
                "direction": "lighter" if luminance(suggestion) > luminance(colour) else "darker",
                "suggestion": suggestion,
            },
        )


def custom_properties(main, accent):
    """The CSS declarations that put a site's brand colours on its pages, or "" for the defaults.

    A colour left at its default writes nothing, so the stylesheet's own shades stay exactly as
    they are. A value that isn't a hex colour (one set outside the admin, which checks it) is
    ignored, so only colours made here reach the page.
    """
    properties = {}
    if HEX_COLOUR.fullmatch(main) and main.lower() != DEFAULT_MAIN:
        properties |= main_shades(main.lower())
    if HEX_COLOUR.fullmatch(accent) and accent.lower() != DEFAULT_ACCENT:
        properties |= accent_shades(accent.lower())
    return ";".join(f"{name}:{value}" for name, value in properties.items())
