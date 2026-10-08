# Images

How photos are stored, protected and served at the right size.

## The image model

The site uses its own image model, `core.CustomImage` (set as `WAGTAILIMAGES_IMAGE_MODEL`), with
two extra fields:

- **`credit`**: the photographer or source, shown as a caption under the image.
- **`consent_confirmed`**: a safeguarding flag. Editors tick it once consent has been recorded
  for everyone identifiable in the photo.

Alt text comes from the image's `description`, so it's written once in the admin and used
everywhere the image appears.

The images API only lists consented images (`ConsentedImagesAPIViewSet` in `charity/api.py`),
because the API exposes every image's original file, including ones never used on a page. Keep
any new image endpoint consistent with that. See [Security](../contributing/security.md).

## Responsive photos

Photos use Wagtail's `{% picture %}` tag with `format-{avif,webp,jpeg}`, several widths and a
`sizes` attribute that matches the CSS layout:

- **List the largest size first.** The `<img>` takes its `width` and `height` from the first
  filter, and a smaller one stops it filling its column.
- **Lazy-load everything below the first screen.**
- `picture { display: contents }` in `charity.css` makes grid and flex rules apply to the `<img>`
  as if the `<picture>` weren't there. `<source>` elements are hidden explicitly, or they become
  empty grid rows.

Partner logos stay PNG, through `{% image %}`.

## The homepage banner

The homepage banner uses `{% hero_picture %}` (`core/templatetags/picture_tags.py`), because
Wagtail's `{% picture %}` can't switch crops by screen width:

- Phones get a square crop (480 and 800px), which fills a banner that is about as tall as it is
  wide. Wider screens get the wide crop (1200 and 1600px).
- The phone crops sit under a 75% dark overlay, which hides the detail a higher quality keeps,
  so they're compressed harder: the 800px AVIF drops from 110 KB to 50 KB with no visible change.
- It's the largest thing on the first screen, so templates mark it `fetchpriority="high"`.

## Card listings

Listings that show cards (appeals, news, the homepage's featured appeals) wrap their queryset in
`core.images.with_card_images()`, which prefetches the card renditions in one query. Its filters
(`CARD_IMAGE_FILTERS`) must match the `{% picture %}` filters in the card templates, or each card
runs a query of its own. The listing tests and the [query budgets](../contributing/performance.md) catch that.

## Measuring image weight

Page weight is measured by the Lighthouse job at phone emulation (412px, pixel density 1.75).
Measure image savings that way, not in a desktop browser at density 1, which picks smaller files.
See [Performance](../contributing/performance.md).
