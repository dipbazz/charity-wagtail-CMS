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
changed in one place (a charity's own brand colours, #131, rely on this).
`core/tests/test_stylesheet.py` fails on a hex code, a colour function or a colour name anywhere
outside `:root`, and on a `var(--…)` that `:root` doesn't define. Add a token when a value is
missing, and use one rather than a raw value for anything else.

| Token | Value | Used for |
|---|---|---|
| `--colour-primary` | teal `#0b5563` | Links, outlined buttons, selected filters |
| `--colour-primary-dark` | dark teal `#073b45` | Headings, the name bar at the top, the footer |
| `--colour-accent` | amber `#f2b134` | Main buttons (Donate, Give), progress bars, the banner, the focus outline |
| `--colour-accent-hover` | darker amber `#e09a12` | A main button under the pointer |
| `--colour-text` | `#1d2a30` | Body text |
| `--colour-on-dark` | white | Text on the teals: the name bar, filled buttons and filters, footer links, the home page banner |
| `--colour-on-accent` | the text colour | Text on amber: main buttons and the announcement banner |
| `--colour-muted` | `#5b6b72` | Dates, counts, help text |
| `--colour-background` | white | The page, the header's controls row, cards, the Menu button |
| `--colour-surface` | `#f4f7f6` | Unselected filter pills, quiet panels |
| `--colour-border` | `#d7e0de` | Borders, the progress bar's track |
| `--colour-error` | `#b3261e` | Form errors |
| `--colour-warning-text`, `--colour-warning-surface` | `#7a5300`, `#fff6df` | A character count near its limit |
| `--colour-highlight` | pale amber `#fde7b4` | Text an editor highlights in rich text |
| `--colour-footer-text`, `--colour-footer-meta` | `#d9e6e4`, `#c3d6d3` | The footer's text and its quieter lines |
| `--colour-hero-lead` | `#e6f0ef` | The home page banner's intro text |
| `--colour-shadow` | dark teal at 15% | The header's shadow |
| `--colour-overlay`, `--colour-overlay-strong`, `--colour-overlay-weak` | dark teal at 75%, 85%, 30% | The home page banner's overlay on the photo |
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
- **Footer**: dark teal with pale text; on a short page it sits at the bottom of the window.

## Header

Two rows. The charity's name is centred on a dark teal row of its own, so a long name (and later
a logo, #123) never crowds the controls, and the header and footer frame the page. Below it, on a
white row with a soft shadow that lifts it off a white page:

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
- a visible focus outline (3px amber) on everything you can tab to;
- tap targets of at least 44px (2.75rem), checked by CI on every kind of page;
- alt text on every image, taken from the image's description in the admin;
- text that passes WCAG AA contrast.

## Images in templates

Photos are served as AVIF, WebP and JPEG at several widths. [Images](images.md) has the rules for
`{% picture %}`, the home page banner and card listings.
