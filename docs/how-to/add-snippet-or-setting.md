# Add a snippet or setting

A snippet is reusable content that isn't a page, such as `Partner` or `Testimonial`. A setting
is site-wide configuration, such as `SiteSettings` or `AnnouncementBanner`. Both need one step
that's easy to miss: **a data migration that gives the Editors and Moderators groups their
permissions**, or editors can't see the new item in the admin.

## 1. Write the tests first

- the model and how it renders, in the app's `tests/` package;
- what editors and moderators can do with it, logged in as the `editor` and `moderator`
  fixtures, never as a superuser (follow `core/tests/test_permissions.py`). These tests fail
  until the permissions migration exists.

## 2. Write the model and register it

**A snippet** is a model registered with a `SnippetViewSet` in the app's `wagtail_hooks.py`.
`core/wagtail_hooks.py` groups `Partner` and `Testimonial` under "Supporters";
`news/wagtail_hooks.py` adds `NewsCategory` to the menu on its own. Add `DraftStateMixin`,
`RevisionMixin`, `LockableMixin` and `PreviewableMixin` (as `Testimonial` does) when the content
needs sign-off before it goes live.

**A setting** subclasses `BaseSiteSetting` (one per site, like `SiteSettings`) or
`BaseGenericSetting` (one for the whole install, like `AnnouncementBanner`) and is registered
with `@register_setting`. Templates read it as `settings.<app>.<ModelName>`.

Shared snippets and settings go in `core`; ones that belong to a feature go in that app.

Then `uv run python manage.py makemigrations <app>`.

## 3. Grant the permissions in a data migration

Decide what each group may do (see the table in [Permissions](../topics/permissions.md)), then
write a migration like `core/migrations/0004_editor_and_moderator_permissions.py`:

```python
from django.db import migrations

GROUPS = ["Editors", "Moderators"]
ACTIONS = ["add", "change", "delete"]


def grant_permissions(apps, schema_editor):
    """Django creates permissions after every migration has run (post_migrate), so on a new
    database they don't exist yet. Create any that are missing, as Django would."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    Event = apps.get_model("events", "Event")

    content_type, _ = ContentType.objects.get_or_create(app_label="events", model="event")
    permissions = [
        Permission.objects.get_or_create(
            content_type=content_type,
            codename=f"{action}_event",
            defaults={"name": f"Can {action} {Event._meta.verbose_name_raw}"},
        )[0]
        for action in ACTIONS
    ]
    for group in Group.objects.filter(name__in=GROUPS):
        group.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0001_initial"),
        # Creates the Editors and Moderators groups.
        ("wagtailcore", "0002_initial_data"),
    ]

    operations = [migrations.RunPython(grant_permissions, migrations.RunPython.noop)]
```

- It must **`get_or_create`** the permission rows, because on a new database Django and Wagtail
  haven't created them yet when migrations run.
- It depends on `wagtailcore.0002_initial_data`, which creates the groups.
- A setting only needs `change`. A snippet with drafts also has `publish`, `lock` and `unlock`;
  give those to moderators only if editors should draft and moderators publish.

[Why permissions live in data migrations](../decisions/permissions-in-data-migrations.md).

## 4. Document it

Add it to the [models reference](../reference/models.md) and the permissions table in
[Permissions](../topics/permissions.md).
