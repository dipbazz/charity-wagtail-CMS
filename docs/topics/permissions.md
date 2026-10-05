# Permissions

Editors draft and moderators publish. This page says who can change what, how those
permissions are granted, and how to test them.

## Who can do what

The charity's team are users in Wagtail's built-in **Editors** and **Moderators** groups, never
superusers.

| Area | Permission | Editors | Moderators |
|---|---|:---:|:---:|
| **Pages** | Edit and preview | ✅ | ✅ |
| | Submit for moderation | ✅ | ✅ |
| | Approve and publish | ❌ | ✅ |
| **Testimonials** | Add, change and delete drafts | ✅ | ✅ |
| | Publish | ❌ | ✅ |
| | Lock and unlock | ❌ | ✅ |
| **Announcement banner** | Change (no approval needed) | ✅ | ✅ |
| **Partners** | Add, change and delete | ✅ | ✅ |
| **News categories** | Add, change and delete | ✅ | ✅ |
| **Site settings** (charity number, donate page, contact details) | Change | ❌ | ✅ |
| **Pledges** (from the Donate page) | View, filter and export | ✅ | ✅ |
| | Add, change or delete | ❌ | ❌ |
| **Users, groups and sites** | Manage | ❌ | ❌ |

Why the differences:

- The **banner** is direct for editors because an emergency message can't wait for approval.
- **Testimonials** quote real people, so a moderator signs them off.
- **Site settings** hold the charity number and the page the Donate button links to, so only
  moderators change them.
- **Pledges** come from supporters on the site, so nobody adds or edits them, and only a
  superuser can delete one: they hold personal details, and a pledge deleted by accident loses
  the record of a donation.

## How permissions are granted

Wagtail's Editors and Moderators groups only come with permissions for Wagtail's own models.
This site's models get theirs from data migrations:

- `core/migrations/0004_editor_and_moderator_permissions.py`: the banner, partners,
  testimonials and site settings;
- `news/migrations/0004_editor_and_moderator_permissions.py`: news categories;
- `campaigns/migrations/0006_pledge_permissions.py`: viewing pledges.

The full discussion is in issue #72.

**A new snippet or setting needs a migration like these**, or editors can't see it in the
admin. Django and Wagtail create permission rows in `post_migrate`, after all migrations have
run, so on a new database they don't exist yet when the migration runs: the migration must
`get_or_create` them. [Add a snippet or setting](../how-to/add-snippet-or-setting.md) shows how,
and [the decision record](../decisions/permissions-in-data-migrations.md) says why it's done
this way.

## Testing permissions

Test what editors can do as the `editor` fixture, not with `admin_client`. A superuser can do
everything, which hides a missing permission. `core/tests/test_permissions.py` has the pattern,
and the root `conftest.py` provides `editor` and `moderator` users in those groups. See
[Testing](../contributing/testing.md).
