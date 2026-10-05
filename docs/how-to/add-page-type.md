# Add a page type

A new kind of page editors can create, such as an events listing. Follow the existing page types:
`home.StandardPage` is the simplest, `campaigns.CampaignPage` the fullest.

## 1. Decide which app it belongs to

A page type lives in the feature app it belongs to, or in a new app for a new feature. Never in
`core`: `core` has no page types and must not import the feature apps
([the dependency rule](../topics/architecture.md#the-dependency-rule)).

For a new app, add it to `INSTALLED_APPS` in `charity/settings/base.py` and to the list of
loggers in `charity/settings/production.py`, and give it a `tests/` package.

## 2. Write the tests first

In the app's `tests/` package, following its existing style:

- a factory in `tests/factories.py`, based on `wagtail_factories.PageFactory`;
- the page renders under its allowed parent, using the `home_page` fixture;
- it can't be created anywhere else (`parent_page_types`, `subpage_types`, `max_count`);
- editing it through the real admin, logged in as the `editor` fixture, with Wagtail's
  form-data helpers (`wagtail.test.utils.form_data`, as in `campaigns/tests/test_campaigns.py`);
- if it has a listing, that private pages stay out of it and its query count doesn't grow per
  item (`cold_cache_queries`).

## 3. Write the model

```python
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index

from core.blocks import BaseStreamBlock
from core.models import SocialMetaMixin


class EventPage(SocialMetaMixin, Page):
    ...
    body = StreamField(BaseStreamBlock(), blank=True)

    content_panels = Page.content_panels + [...]

    parent_page_types = ["events.EventIndexPage"]
    subpage_types = []

    search_fields = Page.search_fields + [index.SearchField("body")]
```

- **`SocialMetaMixin`** adds the social sharing image to the Promote tab. A `hero_image` field is
  used as the default sharing image.
- **`BaseStreamBlock`** gives editors the same content blocks as every other page.
- **Images** are `ForeignKey("core.CustomImage", null=True, blank=True,
  on_delete=models.SET_NULL, related_name="+")`.
- **`search_fields`** so site search finds it, and **`api_fields`** if it should be in the API.
- Set **`parent_page_types`** and **`subpage_types`** so it only goes where it makes sense.

Then `uv run python manage.py makemigrations <app>`.

## 4. Listings filter `.live().public()`

Any listing of these pages (an index page, the homepage, a feed) must filter
`.live().public()`, not just `.live()`, or pages behind a password or login leak into it. See
[Security](../topics/security.md#public-listings-filter-livepublic). If the listing shows cards
with images, wrap the queryset in `with_card_images()` and match its filters in the card
template ([Images](../topics/images.md#card-listings)).

## 5. Write the template

The template goes in `<app>/templates/<app>/<model_name>.html` and extends `base.html`. Render
the body with `{% include "includes/streamfield.html" with stream=page.body %}`, as the other
page templates do. Style it mobile first: load the `mobile-first` skill and read
[Front end](../topics/front-end.md).

## 6. Measure it

- Add the new page to `BUDGETS` in `charity/tests/test_query_budgets.py`, at the count it runs
  now.
- If `seed_demo` should show it, add an example there. The seed smoke test then renders it.
- Check it at 320, 375, 412, 768, 1024 and 1440px.

## 7. Document it

Add the page type to the [page tree](../topics/architecture.md#page-tree) and the
[models reference](../reference/models.md), and to the
[editor guide](../editor-guide/index.md) once that exists.
