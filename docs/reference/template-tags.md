# Template tags and templates

## Template tags (`core/templatetags/`)

| Library | Tag | |
|---|---|---|
| `language_tags` | `{% language_versions as languages %}` | Where the reader can switch language to (`languages.links`) and the page's `hreflang` alternates (`languages.alternates`), in one query. Each link goes to the page's live translation, or to that language's home page if there isn't one; search keeps its query. `links` is empty when the site has content in one language only; `alternates` is empty for a page in one language only. `base.html` calls it once for the header and `<head>` |
| `money_tags` | `{% money amount %}` | A whole amount with the symbol of the currency chosen in Site settings, grouped that currency's way: `Rs 46,87,500` (lakhs and crores) or `£4,687,500`. Use it for every amount; never write a currency symbol in a template |
| `navigation_tags` | `{% main_menu %}` | The site's top-level live pages with "Show in menus" ticked, with `aria-current="page"` on the current page and `"true"` on its section. Renders `includes/main_menu.html` |
| `picture_tags` | `{% hero_picture image attr=value ... %}` | The homepage banner: a square crop for phones and a wide crop for larger screens, in AVIF, WebP and JPEG. Keyword arguments become `<img>` attributes. See [Images](../topics/images.md#the-homepage-banner) |
| `seo_tags` | `{% absolute_url url %}` | Makes a URL absolute for the current request; already-absolute URLs pass through |

## Site-wide settings in templates

The `wagtail.contrib.settings` context processor makes settings available as
`settings.core.SiteSettings` and `settings.core.AnnouncementBanner`.

`core.context_processors.privacy_page` gives every template `privacy_page`: the privacy notice
chosen in Site settings, in the language being read once it's translated, or `None` until one
is chosen and published. It's looked up only when a template uses it, and once per request: one
query, plus one on a page in the other language.

## Shared templates (`charity/templates/`)

| Template | |
|---|---|
| `base.html` | Every page: title, meta and social tags, `hreflang` alternates, the `js` class script, skip link, header, main, footer, `charity.js` |
| `includes/header.html` | The announcement banner; the site name, centred on a row of its own; then the Menu button, main menu and search on the left, and the language switcher and Donate button on the right |
| `includes/main_menu.html` | Rendered by `{% main_menu %}` |
| `includes/footer.html` | Organisation details and social links from `SiteSettings`, and the privacy notice link |
| `includes/privacy_link.html` | "How we use your details", linking to the privacy notice; forms include it just before their send button |
| `includes/streamfield.html` | Renders a StreamField: `{% include "includes/streamfield.html" with stream=page.body %}` |
| `includes/social_meta.html` | Canonical link, Open Graph and Twitter card tags |
| `includes/pagination.html` | Previous and next links for paginated listings |
| `404.html`, `500.html` | Error pages |

Block templates are in `core/templates/core/blocks/`; page templates in each app's
`templates/<app>/`.
