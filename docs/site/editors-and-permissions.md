# Editors and permissions

Who on the charity's team can change what, how publishing works, and how permissions are
granted and tested.

## The team's roles

The charity's team are users in Wagtail's built-in **Editors** and **Moderators** groups, never
superusers. **Editors draft and moderators publish**: an editor submits a page for moderation, and
a moderator approves and publishes it (Wagtail's default moderation workflow). Superusers are for
whoever hosts the site.

| Area | Permission | Editors | Moderators |
|---|---|:---:|:---:|
| **Pages** | Edit and preview | ✅ | ✅ |
| | Submit for moderation | ✅ | ✅ |
| | Approve and publish | ❌ | ✅ |
| | Translate (copies the page into the other language as a draft) | ✅ | ✅ |
| **Testimonials** | Add, change and delete drafts, and translate them (as drafts) | ✅ | ✅ |
| | Publish | ❌ | ✅ |
| | Lock and unlock | ❌ | ✅ |
| **Announcement banner** | Change, in each language (no approval needed) | ✅ | ✅ |
| **Partners** | Add, change, delete and translate | ✅ | ✅ |
| **News categories** | Add, change, delete and translate | ✅ | ✅ |
| **Site settings** (charity number, contact details and the address in each language, Donate page, privacy notice, currency, logo, brand colours) | Change, and preview changes before saving | ❌ | ✅ |
| **Pledges** | View, filter and export | ✅ | ✅ |
| | Add, change or delete | ❌ | ❌ |
| **Form submissions** | View and export (comes with editing the form page) | ✅ | ✅ |
| **Users, groups and sites** | Manage | ❌ | ❌ |

Why the differences:

- **The banner** is direct for editors because an emergency message can't wait for approval.
- **Testimonials** quote real people, so a moderator signs them off.
- **Site settings** hold the charity's identity, including its logo and brand colours, and where the
  Donate button goes.
- **Pledges** come from supporters, so nobody adds or edits them, and only a superuser can delete
  one: they hold personal details, and a pledge deleted by accident loses the record of a gift.

## Publishing

- **Scheduled publishing**: a page can have a go-live and an expiry time. They take effect only
  because the server runs `publish_scheduled` every five minutes
  ([Running the live site](../hosting.md#scheduled-publishing)).
- **Times are Nepal time** (`TIME_ZONE = "Asia/Kathmandu"`), in the admin and for schedules.
- **Moderation emails** go to moderators when a page is submitted. If the mail server is
  unreachable, submitting and approving still work and the failure is logged (#77).

## What the admin adds

Beyond Wagtail's own admin, the team gets:

- a **fundraising panel** on the dashboard ([Appeals and giving](appeals-and-giving.md#appeals));
- **Pledges** in the menu ([Appeals and giving](appeals-and-giving.md#pledges-in-the-admin));
- **Supporters** (partners and testimonials) and **News categories** in the menu;
- the **Highlight** button in rich text ([Pages and content](pages-and-content.md#content-blocks));
- **Translate** on every page ([Languages](languages.md#what-editors-do)).

## How permissions are granted

Wagtail's Editors and Moderators groups only come with permissions for Wagtail's own models.
This site's own models get theirs from **data migrations**, so every new database (including the
test database) gets the same permissions and nobody has to set them by hand:

- `core/migrations/0004_editor_and_moderator_permissions.py`: the banner, partners,
  testimonials and site settings;
- `news/migrations/0004_editor_and_moderator_permissions.py`: news categories;
- `campaigns/migrations/0006_pledge_permissions.py`: viewing pledges;
- `core/migrations/0008_translation_permissions.py`: translating pages.

**A new snippet or setting needs a migration like these, or editors can't see it in the admin.**
Django and Wagtail create permission rows after all migrations have run, so on a new database
they don't exist yet when the migration runs: it must `get_or_create` them.
[Extending the site](../contributing/extending.md#add-a-snippet-or-setting) shows how, and
[the decision record](../decisions.md#group-permissions-granted-in-data-migrations) says why.

## Testing permissions

Test what editors can do as the `editor` fixture, never with `admin_client`: a superuser can do
everything, which hides a missing permission. `core/tests/test_permissions.py` has the pattern;
the root `conftest.py` provides `editor` and `moderator` users in those groups.
