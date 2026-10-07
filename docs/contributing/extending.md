# Extending the site

The three bigger changes that come up most: a new page type, a new snippet or setting, and a new
content block. Each is done test-first ([Testing](testing.md)) and in the app it belongs to
([the dependency rule](../site/overview.md#apps-and-what-they-own)).

## Add a page type

A new kind of page, such as an events listing. Copy the shape of an existing one:
`home.StandardPage` is the simplest, `campaigns.CampaignPage` the fullest.

1. **Choose the app.** The feature's own app, or a new one; never `core`, which has no page types.
   A new app goes in `INSTALLED_APPS` and in production's loggers
   ([Overview](../site/overview.md#logging)), and gets a `tests/` package.
2. **Write the tests first:** a factory based on `wagtail_factories.PageFactory`; the page renders
   under its allowed parent (`home_page` fixture); it can't be created anywhere else; editing it
   through the real admin as the `editor` fixture, with Wagtail's form-data helpers (as in
   `campaigns/tests/test_campaigns.py`); and for a listing, that private pages stay out and the
   query count doesn't grow per item (`cold_cache_queries`).
3. **Write the model.** Mix in `SocialMetaMixin` (sharing image on the Promote tab, falling back to
   a `hero_image` field); give it `body = StreamField(BaseStreamBlock(), blank=True)` so editors get
   the same blocks as everywhere; images are a nullable `ForeignKey` to `core.CustomImage` with
   `on_delete=SET_NULL`; add `search_fields` (and `api_fields` if it belongs in the API); set
   `parent_page_types` and `subpage_types` so it only goes where it makes sense. Then
   `makemigrations`.
4. **Any listing of it filters `.live().public()`** and, for visitors, by language (`locale_id`),
   unless it's `child_of(self)` ([Security](security.md), [Languages](../site/languages.md#keeping-each-language-to-itself)).
   Cards with photos wrap the queryset in `with_card_images()`
   ([Images](../site/images.md#card-listings)).
5. **Write the template** in `<app>/templates/<app>/<model_name>.html`, extending `base.html` and
   rendering the body with `{% include "includes/streamfield.html" with stream=page.body %}`.
   Style it mobile first (load the `mobile-first` skill).
6. **Measure it:** add the page to `BUDGETS` in `charity/tests/test_query_budgets.py` at the count
   it runs now, add an example to `seed_demo` if the demo should have one, and add its address to
   `PATHS` in `charity/tests/test_demo_layout_browser.py` so CI checks it at six widths.
7. **Document it** in the [page tree](../site/overview.md#the-page-tree) and the page of
   [The site](../site/index.md) it belongs to.

## Add a snippet or setting

A **snippet** is reusable content that isn't a page (like partners or testimonials); a
**setting** is site-wide configuration (like Site settings or the banner). Both need one step
that's easy to miss: **a data migration that gives the Editors and Moderators groups their
permissions**, or editors can't see the new item in the admin.

1. **Write the tests first:** the model and how it renders, and what editors and moderators can
   do with it, logged in as the `editor` and `moderator` fixtures, never as a superuser (follow
   `core/tests/test_permissions.py`). The permission tests fail until the migration exists.
2. **Write the model and register it.** A snippet is registered with a `SnippetViewSet` in the
   app's `wagtail_hooks.py`; add `DraftStateMixin`, `RevisionMixin`, `LockableMixin` and
   `PreviewableMixin` (as testimonials have) when the content needs sign-off before going live. A
   setting subclasses `BaseSiteSetting` (one per site) or `BaseGenericSetting` (one for the whole
   install) with `@register_setting`, and templates read it as `settings.<app>.<ModelName>`.
   Shared ones go in `core`, feature ones in their app. Then `makemigrations`.
3. **Grant the permissions in a data migration**, modelled on
   `core/migrations/0004_editor_and_moderator_permissions.py`. What matters:
   - it must **`get_or_create`** the permission rows, because on a new database Django and Wagtail
     create them only after every migration has run;
   - it depends on `wagtailcore.0002_initial_data`, which creates the groups, and skips a group
     that doesn't exist;
   - a setting needs only `change`; a snippet with drafts also has `publish`, `lock` and `unlock`,
     which go to moderators only if editors should draft and moderators publish.

   Decide what each group may do from the table in
   [Editors and permissions](../site/editors-and-permissions.md), and add the new row there.
   Why it's a migration: [Decisions](../decisions.md#group-permissions-granted-in-data-migrations).
4. **Document it** on the page of [The site](../site/index.md) it belongs to.

## Add a content block

Every page body uses `BaseStreamBlock` (`core/blocks.py`), so a block added there is offered on
every page type at once.

1. **Write the tests first** in `core/tests/test_blocks.py`: the block renders what it should (its
   `render()` with raw data), any validation, and add it to
   `test_base_stream_block_offers_every_content_block`, which lists every block by name.
2. **Write the block** as a `StructBlock` with an icon and a template in
   `core/templates/core/blocks/`, and add it to `BaseStreamBlock` where it should appear in the
   editor's menu. Rich text uses `RICH_TEXT_FEATURES`. Validation goes in `clean()`, raising
   `StructBlockValidationError` with per-field errors so the editor sees which field is wrong (as
   the call-to-action block does). Extra template context goes in `get_context()`; a block that
   picks a snippet subclasses `SnippetChooserBlock`. A change to `BaseStreamBlock` changes every
   page's body, so `makemigrations` writes one migration per app with a StreamField.
3. **Keep it fast and safe:** a block that queries the database runs that query on every page
   it's on, so use `select_related` and check the [query budgets](performance.md); a block that
   lists pages filters `.live().public()` and by language. Images use `{% picture %}` with `sizes`
   matching the layout ([Images](../site/images.md)), and the template is styled mobile first.
4. **Document it** in the block table in [Pages and content](../site/pages-and-content.md#content-blocks).
