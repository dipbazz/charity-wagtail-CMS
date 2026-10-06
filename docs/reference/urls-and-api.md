# URLs and the API

## URLs (`charity/urls.py`)

| URL | |
|---|---|
| `/admin/` | Wagtail admin |
| `/django-admin/` | Django admin (superusers only) |
| `/documents/<id>/<filename>` | Wagtail's document view, which checks a private collection's password or login |
| `/api/v2/` | Read-only JSON API (below) |
| `/search/?query=…` | Site search, with editor-pinned results ([promotions](https://docs.wagtail.org/en/stable/reference/contrib/searchpromotions.html)); logs each query for editors |
| `/sitemap.xml` | Sitemap of live, public pages |
| `/robots.txt` | Disallows `/admin/`, `/django-admin/` and `/search/`; links the sitemap |
| `/media/<path>` | Uploads, through `core.views.serve_media` when `SERVE_MEDIA` is on; never `documents/` |
| `/__debug__/` | django-debug-toolbar, in development only |
| `/donate/?appeal=<slug>&amount=<n>` | The Donate page with an appeal and an amount preselected; either can be left out, and ones not on offer are ignored |
| `/donate/thank-you/` | Where the pledge form redirects once a pledge is saved. Opening or reloading it saves nothing |
| everything else | Wagtail's page serving: the [page tree](../topics/architecture.md#page-tree), including the news index's own routes (`/news/tag/…`, `/news/category/…`, `/news/feed/`) |

## API (`charity/api.py`)

A read-only [Wagtail API v2](https://docs.wagtail.org/en/stable/advanced_topics/api/v2/usage.html)
for the pages, images and documents editors publish, for example for a mobile app or a partner's
website.

| Endpoint | |
|---|---|
| `/api/v2/pages/` | Live, public pages. Filter by type with `?type=campaigns.CampaignPage` and ask for fields with `?fields=*` |
| `/api/v2/images/` | **Only images with `consent_confirmed`** (`ConsentedImagesAPIViewSet`), because the endpoint exposes every image's original file |
| `/api/v2/documents/` | Documents |

Page types add their own fields to the API (`api_fields`):

- `CampaignPage`: `summary`, `hero_image` (an 800×450 rendition), `body`, `target_amount`,
  `amount_raised`, `progress_percent`, `start_date`, `end_date`, `is_active`, and
  `donation_amounts` (`amount`, `impact`).
- `NewsPage`: `date`, `introduction`, `hero_image` (800×450), `body`, `tags`, `category_names`.

Full URLs in API responses come from the Wagtail `Site` record, which `update_site_url` sets from
`SITE_URL`.
