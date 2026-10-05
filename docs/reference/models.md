# Models

Every model the site defines, by app. The [page tree](../topics/architecture.md#page-tree) shows
where each page type can go.

## core

### `CustomImage` and `CustomRendition`

The site's image model (`WAGTAILIMAGES_IMAGE_MODEL = "core.CustomImage"`), with renditions in
`CustomRendition`.

| Field | |
|---|---|
| `credit` | Photographer or source, shown as a caption under the image |
| `consent_confirmed` | Ticked once consent is recorded for everyone identifiable. The images API only lists consented images |

Alt text comes from Wagtail's `description` field. See [Images](../topics/images.md).

### `SocialMetaMixin`

An abstract mixin for page models. Adds `social_image` to the Promote tab, used by
`includes/social_meta.html` for Open Graph and Twitter tags. `get_social_image()` falls back to
the page's `hero_image`.

### `SiteSettings`

A per-site setting (`BaseSiteSetting`), read in templates as `settings.core.SiteSettings`.
Moderators only.

| Field | |
|---|---|
| `charity_number`, `contact_email`, `phone`, `address` | Shown in the footer |
| `donate_page` | The page the header's Donate button links to |
| `currency` | Shown with every amount (`{% money %}`): `NPR` (Nepalese rupee, the default, grouped in lakhs and crores: `Rs 46,87,500`) or `GBP`. Codes and symbols are in `core/money.py` |
| `phone_country` | The country selected by default for phone numbers on forms (default Nepal). The list is `PHONE_COUNTRIES` in `core/phone.py` |
| `facebook_url`, `instagram_url`, `linkedin_url` | Social links; `social_links` lists the ones that are set |

### `AnnouncementBanner`

A generic setting (`BaseGenericSetting`, one for the whole install): the site-wide emergency
banner, read as `settings.core.AnnouncementBanner`. Fields `enabled`, `message`, `link_page`.
Editors change it directly, without moderation.

### `Partner` (snippet)

An organisation that funds or works with the charity. `Orderable`, so editors drag to reorder.
Fields `name`, `url`, `logo`. Shown by the `partners` block. Under "Supporters" in the admin.

### `Testimonial` (snippet)

A quote from a beneficiary, volunteer or supporter, with drafts, revisions, locking and preview
(`DraftStateMixin`, `RevisionMixin`, `LockableMixin`, `PreviewableMixin`), because quotes from
real people need sign-off. Fields `quote`, `name`, `role`, `photo`. Under "Supporters" in the
admin; editors draft, moderators publish.

### StreamField blocks

`BaseStreamBlock` (`core/blocks.py`) is the body of every page type. Templates are in
`core/templates/core/blocks/`.

| Block | What it is |
|---|---|
| `heading` | Heading text and a level (H2–H4) |
| `paragraph` | Rich text with `RICH_TEXT_FEATURES`: h2, h3, bold, italic, the custom `mark` highlight, links, document links and lists |
| `image` | An image with an optional caption |
| `quote` | Quote text and an optional attribution |
| `call_to_action` | Title, text and a button to either a page or a URL (exactly one; validated) |
| `impact_stats` | An optional heading and 1–4 figures with labels |
| `embed` | A YouTube or Vimeo link |
| `table` | Wagtail's table block |
| `document` | A document download with optional link text |
| `testimonial` | Chooses a `Testimonial` snippet |
| `partners` | Every partner, with an optional heading |

The "Highlight" (`mark`) rich text button is registered in `core/wagtail_hooks.py`.

## home

### `HomePage`

The site root (max 1). Hero fields (`hero_heading`, `hero_text`, `hero_image`, `hero_cta_text`,
`hero_cta_page`) and a `body`. Its context adds `featured_campaigns`: the three newest open,
public appeals.

### `StandardPage`

A general-purpose page such as About or Donate: `introduction` and `body`. Goes under the
`HomePage` or another `StandardPage`.

## campaigns

### `CampaignIndexPage`

The appeals listing (max 1, under the `HomePage`), nine per page, filtered by `?status=active`
(open appeals) or `?status=closed` (past appeals).

### `CampaignPage`

An appeal, with its editor split into Content, Fundraising, Promote and Settings tabs
(`TabbedInterface`).

| Field | |
|---|---|
| `summary` | Shown on listing cards and in search (max 300 characters) |
| `hero_image`, `body` | |
| `target_amount`, `amount_raised` | |
| `start_date`, `end_date` | A blank end date means ongoing. The end can't be before the start |

- `progress_percent` (0–100) and `is_active` are properties.
- `CampaignPage.objects` is a `CampaignPageQuerySet` with `.active()` and `.closed()`.
- Preview modes: `""` (the full page) and `"card"` (the listing card).
- In the API with its fundraising fields and donation amounts.

### `DonationAmount` and `DonatePageAmount`

A suggested gift: `amount`, a whole number in the site's currency, and its `impact` (what it pays
for). `DonationAmount` is on a `CampaignPage` (inline, up to four) and `DonatePageAmount` on the
`DonatePage` (up to six); both extend the abstract `AbstractDonationAmount`.

### `DonatePage`

The page every Donate button leads to (max 1, under the `HomePage`): suggested amounts and a
pledge form. It's a `wagtail.contrib.forms` form page, so pledges are listed under Forms in the
admin and export to CSV, but its fields are fixed in `campaigns/forms.py` (`PledgeForm`), not
built by editors. No payment is taken.

| Field | |
|---|---|
| `introduction` | Shown under the title |
| `donation_amounts` | The suggested amounts (`DonatePageAmount`) |
| `payment_notice` | Above the form: how payment works and what happens next. Has a default |
| `offer_gift_aid` | UK charities only: adds the Gift Aid declaration, which then requires a home address and postcode |
| `body` | Below the form, e.g. a table of where the money goes |
| `thank_you_text` | Shown after someone sends the form, with a link to the appeals |

The form asks for an amount (a suggested one or the supporter's own), one-off or monthly, the
appeal (open, public appeals, or "Wherever it's needed most"), name, email, an optional mobile
number (checked and stored in E.164 by `core.phone`, for a future monthly reminder on WhatsApp
or by text), address and postcode. A pledge is stored with the site's currency code and the
appeal's title.

`?appeal=<slug>&amount=<n>` preselects an appeal and an amount; an appeal page's "Donate to this
appeal" button adds `?appeal=`.

The fundraising dashboard panel (`campaigns/wagtail_hooks.py`) shows open appeals' totals and
those closing within 14 days.

## news

### `NewsIndexPage`

The news listing (max 1, under the `HomePage`), ten per page. Routable
(`RoutablePageMixin`):

| URL | |
|---|---|
| `/news/` | All stories |
| `/news/tag/<tag>/` | Stories with a tag |
| `/news/category/<slug>/` | Stories in a category |
| `/news/feed/` | RSS feed of the latest 20 stories |

### `NewsPage`

A story: `date`, `introduction`, `hero_image`, `body`, `tags` (free tags) and `categories`
(chosen from `NewsCategory`). In the API with `category_names`.

### `NewsCategory` (snippet)

`name` and `slug`, managed under "News categories" in the admin menu.

## contact

### `FormPage`

A form editors build themselves (`wagtail.contrib.forms`), such as volunteer sign-up: `intro`,
the form fields, `thank_you_text`, and the email notification's addresses and subject. Goes under
the `HomePage` or a `StandardPage`.

`FormPage.send_mail` sets Reply-To to the sender's email field, so staff can answer directly.
Mail errors are logged, not shown to the visitor: the submission is already saved in the admin.
