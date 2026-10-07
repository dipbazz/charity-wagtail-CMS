# Front end

One CSS file (`charity/static/css/charity.css`), one JavaScript file
(`charity/static/js/charity.js`) and Django templates. No build step.

## Mobile first

HTML with no CSS already works on any screen, so that is where every design starts:

1. semantic markup in reading order;
2. then styles for a 320px phone, with no media query;
3. then `min-width` queries, in `rem`, that add layout only where a wider screen needs it.

Never design for desktop and override down with `max-width` queries.
`core/tests/test_stylesheet.py` fails on any width query that isn't `min-width` in `rem`.

Most supporters visit on a phone, often on a slow connection, so the phone layout is the main
design. The `mobile-first` skill in `.claude/skills/mobile-first/SKILL.md` has the full rules
and the widths to check every change at (320, 375, 412, 768, 1024 and 1440px). Read it before
writing or reviewing any CSS or layout markup.

## Design tokens

`charity.css` defines its colours, radius, container width and font as custom properties in
`:root` (`--colour-primary`, `--radius`, `--container`, `--font` and so on). Use a token rather
than repeating a raw value, and add a token when a new value will be reused.

## Nepali text

Nepali is written in Devanagari, which needs more room than English:

- **The device's own Devanagari font, no download.** `--font` lists the Latin system fonts, then
  Noto Sans Devanagari (Android), Kohinoor Devanagari (iPhone and Mac) and Nirmala UI (Windows).
  The Latin fonts have no Devanagari letters, so the browser takes those from the next font.
- **More line height.** Vowel signs sit above and below the letters, so `body:lang(ne)` has a
  line height of 1.8 and headings 1.45, against 1.6 and 1.2 for English.
- **No `letter-spacing` or `text-transform` on Nepali text.** Spacing breaks conjunct letters
  apart, and Devanagari has no capitals. A rule may set them only for `:lang(en)`;
  `core/tests/test_stylesheet.py` checks this.

## JavaScript as an enhancement

`charity.js` adds progressive enhancements, such as the copy-feed-link button on the news page.
Every page works without it:

- Controls that need JavaScript start `hidden` in the HTML, and the script shows them.
- The one exception is anything that changes layout above the fold, such as the mobile Menu
  button. An inline script in `base.html`'s `<head>` adds a `js` class to `<html>` before the
  first paint, and the CSS keys off that, so the page doesn't jump when `charity.js` runs at the
  end of the body. If `charity.js` fails to download, its `onerror` removes the class again, so
  the menu opens back up.
- Elements that only make sense with JavaScript are created by it. A `<textarea>` with
  `data-char-count` and a `maxlength` gets a "10/1000 characters" count below it, which
  turns amber (`--colour-warning-text`, `--colour-warning-surface`) from 95% of the limit,
  with a hidden status message that tells screen readers only when the limit is near and
  when it's reached. Without JavaScript, `maxlength` still stops typing at the limit.
- Some scripts only make the server's work more reliable. The pledge form's hidden
  `submission_id` lets the server update a pledge when the same copy of the form is sent again.
  Going back from the thank-you page can reload the form with a new ID while the browser refills
  what was typed, so `donate.js`, which only the Donate page loads, remembers the ID it sent (in
  `sessionStorage`) and puts it back when the page is reached with Back or Forward. Scripts for
  one page go in their own file like this, so other pages stay within their weight budgets.

## Accessibility

Accessibility is a requirement, not a polish step:

- a skip link to the main content;
- a language switcher named in each language's own script (`lang` and `hreflang` on each link,
  `aria-current="page"` on the language being read), inside a `<nav>` labelled "Language";
- `aria-current` on the menu item for the current page or section (`{% main_menu %}`), and
  `aria-current="page"` on the selected listing filter (Appeals status, News category), which
  `.tag-list a[aria-current]` fills and makes bold;
- a visible focus outline on everything you can tab to;
- tap targets of at least 44px (`2.75rem`);
- alt text on every image, taken from the image's description in the admin.

## Images in templates

Photos are served as AVIF, WebP and JPEG at several widths. [Images](images.md) has the rules
for `{% picture %}`, `{% hero_picture %}` and card listings.
