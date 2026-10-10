# Look and feel

How the site looks and why, and the rules every page, block and component follows. Code: one
stylesheet (`charity/static/css/charity.css`), `charity/static/js/charity.js` on every page,
`charity/static/js/donate.js` on the Donate page, and Django templates. No build step.

## Mobile first

Most supporters visit on a phone, often on a slow connection, so the phone layout is the main
design. HTML with no CSS already works on any screen, so that's where every design starts:

1. semantic markup in reading order;
2. styles for a 320px phone, with no media query;
3. `min-width` queries, in `rem`, that add layout only where a wider screen needs it.

Never design for desktop and override down with `max-width` queries;
`core/tests/test_stylesheet.py` fails on any width query that isn't `min-width` in `rem`. The
`mobile-first` skill (`.claude/skills/mobile-first/SKILL.md`) has the full rules; read it before
writing or reviewing any CSS or layout markup. CI checks every kind of page at 320, 375, 412,
768, 1024 and 1440px ([Testing](../contributing/testing.md#qa)).

There are two breakpoints, each chosen by the content: **64rem**, where the home page banner
switches its dark overlay for a gradient, and **68rem**, where the whole header fits on one line.

## The design

The values are custom properties in `:root` at the top of the stylesheet. **Every colour is a
token:** a rule reads it with `var(--…)` and never writes a colour of its own, so a colour can be
changed in one place, which is how a charity's [brand colours](#brand-colours) reach every page.
`core/tests/test_stylesheet.py` fails on a hex code, a colour function or a colour name anywhere
outside `:root`, and on a `var(--…)` that `:root` doesn't define. Add a token when a value is
missing, and use one rather than a raw value for anything else. A new token that should follow
a brand colour is also made in `core/brand.py`.

The colours below are the defaults, the demo charity's teal and amber, which a charity's own
replace.

| Token | Value | Used for |
|---|---|---|
| `--colour-primary` | teal `#0b5563` | Links, outlined buttons, selected filters |
| `--colour-primary-dark` | dark teal `#073b45` | Headings, the name bar at the top and the footer when they're dark, the name on a light name bar |
| `--colour-accent` | amber `#f2b134` | Main buttons (Donate, Give), progress bars, the banner, the focus outline |
| `--colour-accent-hover` | darker amber `#e09a12` | A main button under the pointer |
| `--colour-text` | `#1d2a30` | Body text |
| `--colour-on-dark` | white | Text on the teals: the name bar, filled buttons and filters, footer links, the home page banner |
| `--colour-on-accent` | the text colour | Text on amber: main buttons and the announcement banner |
| `--colour-muted` | `#5b6b72` | Dates, counts, help text |
| `--colour-background` | white | The page, the header's controls row, a light name bar, cards, the Menu button |
| `--colour-surface` | `#f4f7f6` | Unselected filter pills, quiet panels, a light footer |
| `--colour-border` | `#d7e0de` | Borders, the progress bar's track, the line under a light name bar and above a light footer |
| `--colour-error` | `#b3261e` | Form errors |
| `--colour-warning-text`, `--colour-warning-surface` | `#7a5300`, `#fff6df` | A character count near its limit |
| `--colour-highlight` | pale amber `#fde7b4` | Text an editor highlights in rich text |
| `--colour-footer-text`, `--colour-footer-meta` | `#d9e6e4`, `#c3d6d3` | A dark footer's text and its quieter lines |
| `--colour-hero-lead` | `#e6f0ef` | The home page banner's intro text |
| `--colour-shadow` | dark teal at 15% | The header's shadow |
| `--colour-overlay`, `--colour-overlay-strong`, `--colour-overlay-weak` | dark teal at 75%, 85%, 30% | The home page banner's overlay on the photo |
| `--logo-height`, `--logo-height-wide` | 5rem, 6rem | The logo's height on a phone and from 68rem: the largest a charity can [choose](#the-logo) |
| `--radius` | 6px | Buttons, cards, fields |
| `--container` | 1120px | Page width; reading pages use 760px |
| `--font` | the device's own fonts | No downloads ([Nepali text](languages.md#nepali-text-on-screen)) |

Body text is 1.0625rem with a line height of 1.6; headings are dark teal at 1.2.

**Components:**

- **Buttons**: amber with dark text for the main action; a larger size for calls to action; at
  least 44px tall.
- **Cards** (appeals, stories): a white box with a border, photo on top, in a grid that fits as
  many 18rem columns as the screen allows.
- **Progress**: "Rs … raised of Rs …" above a rounded amber bar on a grey track.
- **Filter pills** (appeal status, news categories): rounded, grey; the selected one filled teal
  and bold, so it doesn't rely on colour alone.
- **The home page banner**: the photo under a 75% dark teal overlay on phones, so white text stays
  readable over any photo; from 64rem a gradient, darker on the left behind the text, lets the
  photo show on the right. The heading scales from 2.2rem to 3.5rem with the screen.
- **Footer**: dark teal with pale text, or [light](#a-light-or-dark-name-bar-and-footer); on a
  short page it sits at the bottom of the window.

## Brand colours

A charity chooses its [logo](#the-logo) and two colours in **Site settings → Brand** (moderators
only, like the rest of Site settings). The colours are a **main colour**, the teal by default,
and an **accent colour**, the amber. `core/brand.py` makes the other shades from them, and
`base.html` writes them into each page's `<head>`, after the stylesheet, as a `<style>` that
replaces those tokens (about 450 bytes with both chosen). Every page uses a new colour as soon
as it's saved, so the admin [previews it on real pages first](#seeing-a-brand-change-before-it-goes-live).

| From | Token | Made by |
|---|---|---|
| Main colour | `--colour-primary` | The colour itself |
| | `--colour-primary-dark` | Mixing it into black (70% of it) |
| | `--colour-surface`, `--colour-hero-lead`, `--colour-footer-text`, `--colour-border`, `--colour-footer-meta` | Mixing it into white (5%, 10%, 15%, 16% and 24% of it) |
| | `--colour-shadow`, `--colour-overlay`, `--colour-overlay-strong`, `--colour-overlay-weak` | The dark shade, see-through |
| Accent colour | `--colour-accent` | The colour itself |
| | `--colour-on-accent` | The text colour or white, whichever has more contrast on it |
| | `--colour-accent-hover` | 10% darker, or 10% lighter if the text on it would then fail 4.5:1 (or the accent is black) |
| | `--colour-highlight` | Mixing it into white (35% of it) |

The other colours (text, quieter text, errors, warnings, white) are the same for every charity.

**A colour that makes text hard to read can't be saved.** Text needs a contrast of at least
4.5:1 (WCAG AA), and the admin checks it:

- **Main colour:** links in it on the pale panels (`--colour-surface`) must reach 4.5:1. That's
  where it's hardest to read, so white text on it, links on white and the footer's text pass too
  (`core/tests/test_brand.py` checks every pair for 4,096 colours). So `#767676`, which is 4.5:1 on
  white, is refused: on a panel it's 4.3:1.
- **Accent colour:** dark or white text, whichever reads better on it, must reach 4.5:1. Mid tones
  that neither does are refused.

The message gives the colour's contrast and suggests the nearest shade of it that passes: darker
for the main colour, lighter or darker for the accent.

**A colour left at its default writes nothing,** so a site that hasn't chosen looks exactly as
the stylesheet says. (The shades made from the teal and amber are close to the stylesheet's own
but not the same.) The defaults in `core/brand.py` must match `:root`, which a test checks. A
value that isn't a `#rrggbb` code, which only a change outside the admin could save, is ignored.

### A light or dark name bar and footer

Under **Site settings → Brand → Header and footer**, the name bar at the top and the footer are
each **dark** (the default) or **light**, so a logo can sit on the background it was drawn for:
a dark logo disappears on the dark name bar. The template adds `is-light` to `.brand-bar` or
`.site-footer`, and the stylesheet does the rest with the same tokens, so brand colours apply
either way.

| | Dark | Light |
|---|---|---|
| Name bar | White name on the dark shade | The name in the dark shade on white, with a line (`--colour-border`) between it and the white controls row |
| Footer | Pale text and white links on the dark shade | Body text and links in the main colour on a pale panel (`--colour-surface`), with a line above it |

Both stay readable whatever main colour is saved: the dark shade on white and body text on a
panel are among the pairs `core/tests/test_brand.py` checks for every colour, and
`charity/tests/test_demo_layout_browser.py` measures the contrast of each combination in the
browser. The controls row below the name bar stays white, so the Menu button and language
switch don't change.

### Seeing a brand change before it goes live

A saved brand, logo and logo size are on every page at once, and Wagtail can't keep settings as
drafts, so Site settings has the same **preview panel** as a page. The phone icon at the top right opens it
next to the form. It shows a real page drawn with the form as it stands, unsaved, and redraws
it as the form changes. **Preview mode** chooses the page:

| Preview mode | Why | Listed |
|---|---|---|
| Home page | The longest page, with the most of the brand: the banner over its photo, cards, progress bars, buttons, the footer | Always |
| Donate page | The pledge form and its main buttons | When a Donate page is chosen |
| Nepali home page | The other language's text, in its own fonts | For each other language with a published home page (English home page when Nepali is the main language) |

Visitors see nothing until **Save**, so a mistake is undone by changing it back or leaving
without saving. A colour that can't be saved can't be previewed either: the panel says the
preview is out of date until it's fixed. The panel previews the whole form, so a change on the
Organisation tab, such as the address, shows too. Editors can't preview Site settings, as they
can't change them.

How it works: `SiteSettings` is a `PreviewableMixin`, which Wagtail's settings views support.
Wagtail puts the unsaved settings on the preview's request, where `{{ settings.core.SiteSettings }}`
and `SiteSettings.for_request` find them in place of the saved ones. `SiteSettings.serve_preview`
then draws the chosen page with the page's own `serve_preview`, in the page's language: its
address would set the language, but the preview's address isn't the page's. The tests are in
`core/tests/test_settings.py` (`TestPreview`) and, in a browser, `test_settings_browser.py`.

What it can't do: a change can't be kept as a draft to finish later, sent for approval or
scheduled, and there's no history of earlier brands to go back to. [Decisions](../decisions.md#brand-previews-in-site-settings)
says why that was chosen over a brand with drafts.

## The logo

A moderator chooses the charity's logo in **Site settings → Brand → Logo**: an image from the
library, optional, previewed like the colours
([seeing a brand change](#seeing-a-brand-change-before-it-goes-live)). It's `SiteSettings.logo`
and sits in the header's name row, inside the link to the home page, in front of the name:

- **The name is always shown beside it,** so the logo is decorative (`alt=""`) and a screen
  reader hears the name once. The image's description in the admin is still worth writing: it's
  what the logo is called wherever else the image is used.
- **Its size is chosen,** with a slider under the logo in the same panel, from **40px** to
  **80px** tall on a phone, 80 unless the charity chooses. A seal or a crest has lettering in it
  that needs the larger sizes; a plain mark may look better small. The smallest is 2.5rem on
  every screen. The largest is 5rem on a phone and **6rem** from 68rem, where the header's other
  query is, because the name bar has room to spare; in between, both heights grow together
  (`core.brand.logo_heights`). The name bar grows to hold the logo, and no more.
- **It's written like the colours:** a size other than the largest adds `--logo-height` and
  `--logo-height-wide` to the page's `<style>` in `<head>`, so the stylesheet's own largest size
  is what a site that hasn't chosen gets, and the
  [preview](#seeing-a-brand-change-before-it-goes-live) follows the slider as it moves. The
  number beside the slider is its height on a phone.
- **A wide logo shrinks, not crowds.** One that's wide for its height shrinks inside its box
  (`object-fit: contain`, at most 9rem wide, 16rem from 68rem) so it can't push a long name off a
  320px screen; the name wraps beside it. A logo with a background of its own, as most from a
  leaflet or a Facebook page have, gets the corners of a button.
- **A small copy, in the modern formats.** The template uses `{% picture %}` with
  `max-384x192` and AVIF, WebP and PNG, twice the largest size it's drawn at, for a dense phone
  screen. `max` never enlarges, so a small logo stays as it is. The `width` and `height`
  attributes give the browser the shape before the file arrives, so the name bar doesn't shift
  as it loads.
- **No logo, no change:** the header shows the name alone, as it did.
- **No extra query:** the logo is read with the settings (`select_related`), and its renditions
  come from Wagtail's cache after the first visit.
- **PNG, JPEG or WebP,** not SVG: [Decisions](../decisions.md#the-logo-is-a-raster-image-not-an-svg)
  says why. Draw it for the name bar it will sit on: a logo in dark colours disappears on the
  default dark bar, so such a charity chooses a
  [light name bar](#a-light-or-dark-name-bar-and-footer).

`seed_demo` draws a logo for the demo charity: a drop of water on an amber disc, which shows on
a dark bar and a light one. `charity/tests/test_layout_browser.py` checks the logo's height at
the smallest, a middle and the largest size, its place on the name's row, that the name bar is
the logo and its padding and no taller, that a long name beside a wide logo doesn't scroll a
320px screen sideways, and that the header's height is the same in both languages;
`core/tests/test_settings_browser.py` that the preview follows the slider.

## Header

Two rows. The charity's name, with its [logo](#the-logo) beside it if it has one, is centred on
a row of its own, dark teal unless the charity
[chooses light](#a-light-or-dark-name-bar-and-footer), so a long name never crowds the controls,
and the header and footer frame the page. Below it, on a white row with a soft shadow that lifts
it off a white page:

- **On a phone:** Menu on the left; the other language and Donate on the right, Donate last, so
  Menu and Donate sit at the two ends. Menu opens the main menu and search below.
- **From 68rem:** the main menu and search on the left; both languages, joined as one switch, then
  Donate on the right.

The language switch looks like the Menu button, not like a link: the language being read is
filled and the other outlined, so a reader can't mistake the one to switch to for the one
they're on. `charity/tests/test_layout_browser.py` checks the header's layout and that it's the
same height in both languages. (A lighter switch, #138, and keeping the header in reach on scroll,
#139, are planned.)

## JavaScript as an enhancement

Every page works without JavaScript:

- Controls that need it start `hidden` and the script shows them, such as the news page's Copy
  link button.
- **The exception is anything that changes layout above the fold**, such as the phone's Menu
  button. A one-line script in `<head>` adds a `js` class to `<html>` before the page is drawn and
  the CSS keys off it, so the page doesn't jump when `charity.js` runs at the end. If `charity.js`
  fails to download, the class is removed again, so the menu opens back up.
- **Elements that only make sense with JavaScript are created by it**: a message box gets a
  "10/1000 characters" count, amber from 95% of the limit, with a hidden status message that tells
  screen readers only when the limit is near and reached. Without JavaScript, `maxlength` still
  stops typing at the limit.
- **Scripts for one page go in their own file** (like `donate.js`), so other pages stay within
  their weight budgets.

## Accessibility

A requirement, not a polish step. Every page has:

- a skip link to the main content;
- `aria-current` on the menu item for the current page or section, and on the selected filter;
- the language switch named in each language's own script, with `lang` and `hreflang` on each
  link, inside a `<nav>` labelled "Language";
- a visible focus outline (3px, in the accent colour) on everything you can tab to;
- tap targets of at least 44px (2.75rem), checked by CI on every kind of page;
- alt text on every image, taken from the image's description in the admin;
- text that passes WCAG AA contrast, whatever [brand colours](#brand-colours) are chosen.

## Images in templates

Photos are served as AVIF, WebP and JPEG at several widths. [Images](images.md) has the rules for
`{% picture %}`, the home page banner and card listings.
