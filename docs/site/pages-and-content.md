# Pages and content

Everything editors write and visitors read, apart from appeals and the Donate page
([Appeals and giving](appeals-and-giving.md)). Each section says what the page or feature does,
why, and where its code is.

## Every page

Every page shares one layout (`charity/templates/base.html`):

- **Announcement banner** (when switched on), then the **header**: the charity's name on a row of
  its own, then Menu, the main menu and search, the language switch and Donate
  ([Look and feel](look-and-feel.md#header)).
- **Main content**, with a "Skip to content" link before the header.
- **Footer**: the charity's name, address, email, phone and social links, the privacy notice
  link, and "© year, name. Registered charity number …", all from Site settings. On a short page
  it sits at the bottom of the window.
- In `<head>`: the title (the page's SEO title or title, then "| site name"), its search
  description, social sharing tags and links to its translations
  ([SEO and sharing](#seo-and-sharing)).

The **main menu** is the home page's children with "Show in menus" ticked, in the language being
read, marking the current page and section for screen readers (`{% main_menu %}`,
`core/templatetags/navigation_tags.py`).

## Home page

The first thing a visitor sees, so it leads with the charity's message and its open appeals
(`home/models.py`, `HomePage`):

- **A banner**: a photo with the heading (the page title if left blank), a line of text and a
  button to a chosen page. Phones get a square crop of the photo and wider screens a wide one
  ([Images](images.md#the-homepage-banner)).
- **Current appeals**: the three newest open appeals (by start date) that are public and in the
  page's language, as cards. Hidden when there are none.
- **The body**: any content blocks.

## Standard pages

General pages such as About us or the privacy notice: a title, an introduction and a body of
content blocks. They go under the home page or another standard page, so editors can build
sections (`home/models.py`, `StandardPage`).

## Content blocks

Every page body is a StreamField of the same blocks, so editors compose pages the same way
everywhere (`core/blocks.py`, `BaseStreamBlock`; templates in `core/templates/core/blocks/`):

| Block | What editors get |
|---|---|
| Heading | Heading text at level 2, 3 or 4 |
| Paragraph | Rich text: headings, bold, italic, a pale amber **Highlight**, links, document links and lists. Highlight is this site's own button (`core/wagtail_hooks.py`), for the one phrase a reader mustn't miss |
| Image | A photo with an optional caption; its credit shows under it |
| Quote | Quote text and an optional attribution |
| Call to action | A title, text and a button to a page **or** a web address, never both and never neither (checked when saving) |
| Impact statistics | An optional heading and one to four figures with labels, such as "412 wells built" |
| Video | A YouTube or Vimeo link, embedded |
| Table | A table editors fill in |
| Document | A download link for an uploaded document, with optional link text |
| Testimonial | A chosen testimonial (below) |
| Partners | Every partner's logo, with an optional heading |

## Partners and testimonials

Reusable content that isn't a page, under **Supporters** in the admin (`core/models.py`,
`core/wagtail_hooks.py`):

- **Partners**: organisations that fund or work with the charity: name, website and logo. Editors
  drag them into order; the Partners block shows them all, each in the language being read.
- **Testimonials**: a quote from a beneficiary, volunteer or supporter, with their name, role and
  photo. They quote real people, so they have drafts, revisions, locking and preview, and a
  moderator publishes them ([Editors and permissions](editors-and-permissions.md)).

Both are translated with **Translate**, and a page shows each in its own language, else in the
main language ([Languages](languages.md#snippets-and-settings-text)).

## Site settings and the banner

Settings that apply to every page, under **Settings** in the admin (`core/models.py`):

- **Site settings** (moderators only, because they hold the charity's identity): charity number,
  contact email, phone and address (shown in the footer; the address is written in each
  language); the **Donate page** the header's button goes to; the **privacy notice** ([Appeals and giving](appeals-and-giving.md#privacy-notice));
  the **currency** every amount is shown in ([Money](appeals-and-giving.md#money)); the
  **default phone country** for mobile numbers on forms; Facebook, Instagram and LinkedIn
  links (each shown in the footer only when set); and, on the **Brand** tab, the charity's main
  and accent colours ([Look and feel](look-and-feel.md#brand-colours)) and a light or dark name
  bar and footer ([Look and feel](look-and-feel.md#a-light-or-dark-name-bar-and-footer)). A
  change shows on every page as soon as it's saved, so its preview panel shows it on real pages
  first ([Look and feel](look-and-feel.md#seeing-a-brand-change-before-it-goes-live)).
- **Announcement banner**: one message, written in each language, on or off, optionally linking
  to a page, shown across the top of every page in amber. Editors change it directly, without
  approval, because an emergency appeal can't wait.

Both are per Site. Text that differs between languages is in rows, one per language, in the same
form, and links to chosen pages go to their translation in the language being read
([Languages](languages.md#snippets-and-settings-text)).

## Forms

Editors build forms themselves, such as volunteer sign-up or an enquiry form, with Wagtail's form
builder (`contact/models.py`, `FormPage`): an introduction, the fields, a thank-you message, and
who is emailed about each submission.

- The email's **Reply-To** is the sender's email field, so the team can answer directly.
- If the email can't be sent, the error is logged and the visitor still sees the thank-you page:
  the submission is already saved, and the team reads and exports submissions (CSV) in the admin.
- "How we use your details" links to the privacy notice just before the Send button.

## News

Stories the charity publishes, with editor-managed categories and free tags (`news/models.py`):

- **The news page** lists stories newest first, ten per page, as cards, with a row of category
  filters ("All news" and each category).
- **Tag and category pages** (`/news/tag/<tag>/`, `/news/category/<slug>/`) show the same
  listing, filtered, with the filter in the heading.
- **A story** shows the news page's name and the date, the title, an introduction, a photo with
  its credit, the body, then its categories and tags as links to those pages.
- **The RSS feed** (`/news/feed/`) has the latest 20 stories. A "Follow our news" box on the news
  page gives its address with a Copy link button, for readers who use a feed app.
- Categories are managed under **News categories** in the admin and translated with
  **Translate**. A slug is unique in each language, and a translation keeps it, so
  `/news/category/stories/` and `/ne/news/category/stories/` are the same category. A translated
  story keeps the original's categories and shows them in the language being read.

## Search

A search box in the header and a search page (`search/views.py`):

- Results are live, public pages **in the language being read**, ten per page. Each shows its
  title and its search description, else its summary, else its introduction.
- **Promoted results**: editors pin a page for a search term, per language; a promoted link to
  another website shows in both languages. Promotions show above the results.
- Every search is logged, so editors can see what people look for and promote answers.
- Search pages aren't indexed by search engines (robots.txt).

## SEO and sharing

So pages are found, and look right when shared:

- **Canonical link** and **Open Graph** tags on every page; a shared page shows its sharing image
  (set on the Promote tab, else the page's own photo) cropped to 1200×630, with a large Twitter
  card (`core/models.py`, `SocialMetaMixin`; `includes/social_meta.html`).
- **Sitemap** (`/sitemap.xml`): every live, public page in every language, with each page's
  translations as alternates ([Languages](languages.md)).
- **robots.txt** keeps search engines out of the admin and search, and links the sitemap.
- **Redirects**: editors add their own, and Wagtail adds one automatically when a page's slug
  changes, so old links keep working.

Every full URL (feed, sitemap, canonical, API) comes from the Wagtail Site record, which
`update_site_url` sets from `SITE_URL` ([Running the live site](../hosting.md)).

## URLs

| URL | |
|---|---|
| `/admin/` | The Wagtail admin |
| `/django-admin/` | Django's admin, for superusers only |
| `/en/…` or `/ne/…` | Pages and search in the site's second language ([Languages](languages.md#addresses)) |
| `/search/?query=…` | Search |
| `/donate/?appeal=<slug>&amount=<n>` | The Donate page with an appeal and amount preselected ([Appeals and giving](appeals-and-giving.md#donate-page)) |
| `/donate/thank-you/` | Where a sent pledge lands; opening or reloading it saves nothing |
| `/news/tag/…`, `/news/category/…`, `/news/feed/` | News listings and the RSS feed |
| `/documents/<id>/<filename>` | Document downloads, through Wagtail's view, which checks a private collection's password or login |
| `/media/<path>` | Uploads, when Django serves them; never documents ([Security](../contributing/security.md)) |
| `/sitemap.xml`, `/robots.txt` | As above |
| `/api/v2/` | The API (below) |
| `/__debug__/` | django-debug-toolbar, in development only |

Everything else is a page in the [page tree](overview.md#the-page-tree). The admin, API,
documents, media, sitemap and robots.txt have no language prefix (`charity/urls.py`).

## The API

A read-only [Wagtail API v2](https://docs.wagtail.org/en/stable/advanced_topics/api/v2/usage.html)
of what editors publish, for a mobile app or a partner's website (`charity/api.py`):

| Endpoint | |
|---|---|
| `/api/v2/pages/` | Live, public pages in every language. Filter with `?type=campaigns.CampaignPage` or `?locale=ne`, and ask for fields with `?fields=*`. Each page's language is in `meta.locale` |
| `/api/v2/images/` | **Only images whose consent is confirmed**, because the endpoint hands out every image's original file, including ones never used on a page ([Images](images.md)) |
| `/api/v2/documents/` | Documents |

Appeals add `summary`, `hero_image` (an 800×450 rendition), `body`, `target_amount`,
`amount_raised`, `progress_percent`, `start_date`, `end_date`, `is_active` and
`donation_amounts` (each `amount` and `impact`). Stories add `date`, `introduction`, `hero_image`
(800×450), `body`, `tags` and `category_names`.

## Error pages

"Page not found" (404) uses the site's layout. The server error page (500) is a standalone
HTML page with no template tags, because it must render even when the database or a template
is what failed (`charity/templates/`).
