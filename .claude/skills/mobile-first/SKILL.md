---
name: mobile-first
description: How to style this site mobile first. Use before writing or changing any CSS in charity.css, any template markup that affects layout, or any new page type, block or component, and when reviewing a styling change.
---

# Mobile-first styling

Plain HTML is already responsive. With no CSS at all, a page reads top to bottom, text wraps
and images shrink to fit, at any width. That unstyled page is the phone layout. Our CSS starts
from it and adds layout as the screen gets wider. It never builds a desktop layout and then
squeezes it down.

Most supporters visit on a phone, often on a slow connection, so the phone layout is the main
design, not an afterthought.

## Order of work

1. **Markup first.** Write semantic HTML in the order a phone visitor reads it: heading, the
   point of the page, then the call to action. Check that it makes sense with no CSS (see
   "Checking" below).
2. **Phone styles next, with no media query.** Style for a 320px screen. These base rules are
   the layout, not a fallback.
3. **Wider screens last.** Add a `@media (min-width: …rem)` block only where the content looks
   wrong because there's spare room, for example a line of text that runs too long or a grid
   that could fit a second column. Put a comment above it saying why it starts at that width,
   as the header query in `charity.css` does.

## Rules

- **`min-width` queries in `rem` only.** No `max-width` width queries, and no `px` breakpoints.
  `rem` breakpoints follow the visitor's text size. `core/tests/test_stylesheet.py` enforces
  this. Queries that aren't about width (`prefers-reduced-motion`, `print`) are fine.
- **Breakpoints come from the content, not from devices.** Don't add "tablet" or "desktop"
  queries in advance. Today there are two: `64rem` (hero gradient) and `68rem` (header on one
  line). Reuse one of these when it fits, rather than adding a value that is almost the same.
- **Prefer layouts that need no breakpoint:**
  - Grids: `grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr))`. The
    `min(100%, …)` stops the column overflowing a 320px screen.
  - Rows: `display: flex; flex-wrap: wrap; gap: …`.
  - Type: `clamp()` for headings, as `.hero h1` does.
  - Line length: `max-width` in `ch` on text (about 60–75ch for body copy). A `max-width`
    property is fine; only `max-width` *media queries* are banned.
- **The same content on every screen.** Don't hide content on phones with `display: none`. If
  something doesn't fit, change its layout. Hiding is only for controls that are swapped for
  another one, such as the header's Menu button.
- **Source order is reading order.** Don't use `order` or grid placement to change the order
  of content in a way that would differ from the keyboard and screen reader order.
- **Fluid sizes, not fixed ones.** Containers use `max-width` plus padding, never a fixed
  `width`. Images and embeds stay within `max-width: 100%`.
- **Touch first.** Tap targets are at least 44px (`2.75rem`). Nothing depends on hover. Form
  inputs keep at least a `1rem` font size so iOS doesn't zoom in on focus.
- **Use the design tokens** in `:root` (colours, radius, container, font). Add a token instead
  of repeating a raw value.
- **Works without CSS or JS.** Controls that need JS start `hidden` and the JS shows them (see
  `charity.js`). Forms and links work with no styling.
- **Images:** the `sizes` attribute describes the phone layout first. Follow the `{% picture %}`
  rules in `docs/topics/images.md`.

## Checking

Check every styling change at these widths: **320, 375, 412, 768, 1024 and 1440px**. At each
one, look for:

- no horizontal scrolling (`document.documentElement.scrollWidth <= innerWidth`);
- no text or buttons overlapping or cut off;
- tap targets of at least 44px;
- a visible focus outline when tabbing through.

Then turn the CSS off and check that the page still reads in a sensible order and that its
links and forms still work. With `/browse`, run this on the page:

```js
document.querySelectorAll('link[rel="stylesheet"], style').forEach((el) => (el.disabled = true))
```

Run `uv run pytest core/tests/test_stylesheet.py` after editing `charity.css`.

## Reviewing

A styling change isn't ready if:

- it adds a `max-width` media query, or a breakpoint in `px`;
- the base (unqueried) rules only look right on a large screen;
- it hides content on phones;
- it hasn't been checked at 320px.
