# Group permissions granted in data migrations

**Status:** in use (since #72, done in #73)

## Context

The charity's team are in Wagtail's Editors and Moderators groups, not superusers. Those groups
only come with permissions for Wagtail's own models, so editors couldn't see the announcement
banner, partners, testimonials or news categories at all. Granting permissions by hand in the
admin would have to be repeated on every new database, and nothing would notice if it were
forgotten.

## Decision

Grant this site's permissions to the groups in data migrations
(`core/migrations/0004_editor_and_moderator_permissions.py`,
`news/migrations/0004_editor_and_moderator_permissions.py`), and test them as an `editor` and a
`moderator` user, never as a superuser (`core/tests/test_permissions.py`).

Editors draft and moderators publish, as with pages. The banner is direct for editors because an
emergency message can't wait for approval; testimonials quote real people, so a moderator signs
them off; site settings are moderators' only.

## Consequences

- Every new database, including the test database, gets the same permissions.
- Django and Wagtail create permission rows in `post_migrate`, after all migrations have run, so
  these migrations must `get_or_create` the rows they grant.
- **A new snippet or setting needs a migration like these**, or editors can't see it;
  [Add a snippet or setting](../how-to/add-snippet-or-setting.md) shows how.
- A site that renamed or deleted a group skips it rather than failing.
