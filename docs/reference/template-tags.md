# Template tags and templates

## Template tags (`core/templatetags/`)

| Library | Tag | |
|---|---|---|
| `navigation_tags` | `{% main_menu %}` | The site's top-level live pages with "Show in menus" ticked, with `aria-current="page"` on the current page and `"true"` on its section. Renders `includes/main_menu.html` |
| `picture_tags` | `{% hero_picture image attr=value ... %}` | The homepage banner: a square crop for phones and a wide crop for larger screens, in AVIF, WebP and JPEG. Keyword arguments become `<img>` attributes. See [Images](../topics/images.md#the-homepage-banner) |
| `seo_tags` | `{% absolute_url url %}` | Makes a URL absolute for the current request; already-absolute URLs pass through |

## Site-wide settings in templates

The `wagtail.contrib.settings` context processor makes settings available as
`settings.core.SiteSettings` and `settings.core.AnnouncementBanner`.

## Shared templates (`charity/templates/`)

| Template | |
|---|---|
| `base.html` | Every page: title, meta and social tags, the `js` class script, skip link, header, main, footer, `charity.js` |
| `includes/header.html` | The announcement banner, site name, Menu button, main menu and Donate button |
| `includes/main_menu.html` | Rendered by `{% main_menu %}` |
| `includes/footer.html` | Organisation details and social links from `SiteSettings` |
| `includes/streamfield.html` | Renders a StreamField: `{% include "includes/streamfield.html" with stream=page.body %}` |
| `includes/social_meta.html` | Canonical link, Open Graph and Twitter card tags |
| `includes/pagination.html` | Previous and next links for paginated listings |
| `404.html`, `500.html` | Error pages |

Block templates are in `core/templates/core/blocks/`; page templates in each app's
`templates/<app>/`.
