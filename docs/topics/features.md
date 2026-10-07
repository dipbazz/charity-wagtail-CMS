# What the site does

What editors can do in the admin, and the Wagtail features behind each part.

| Area | What it does | Wagtail features |
|---|---|---|
| Page building | Compose pages from headings, rich text, images with photo credits, quotes, impact statistics, calls to action, video, tables, document downloads, testimonials and partner logos | `StreamField`, `StructBlock`, `ListBlock`, custom block validation and templates |
| Appeals | Target, amount raised, dates and suggested gifts; progress bars; open/closed filters; homepage features open appeals | Page models, `InlinePanel` + `Orderable`, `TabbedInterface`, custom `PageQuerySet`, preview modes |
| News | Stories with tags and editor-managed categories; tag, category and RSS URLs | `RoutablePageMixin`, `ClusterTaggableManager`, `ParentalManyToManyField` |
| Donating | Suggested amounts and a pledge form (one-off or monthly, the appeal, optional mobile number for monthly gifts, optional address, an optional message for the team, and opt-in consent to email updates and to being listed on the site) that preselects the appeal a supporter came from; pledges listed under Pledges in the admin, with filters (including by each consent) and CSV/Excel export. No payment is taken yet | A `Pledge` model and `ModelForm`, `ModelViewSet` (listing, filters, export), `InlinePanel` |
| Forms | Build volunteer and enquiry forms, receive email (Reply-To the sender), export submissions to CSV | `wagtail.contrib.forms` |
| Supporters | Partners (drag to reorder) and testimonials with drafts, revisions, locking and preview | Snippets, `SnippetViewSet(Group)`, `DraftStateMixin`, `RevisionMixin`, `PreviewableMixin` |
| Site-wide | Charity number, contact details, donate page, currency, default phone country, social links, emergency-appeal banner | `wagtail.contrib.settings` (site and generic settings) |
| Images | Photo credit and a safeguarding consent flag on every image, which keeps unconsented images out of the API; focal-point crops; alt text from the image description | Custom image model, renditions, custom API viewset |
| Languages | Pages in Nepali, English or both; each site opens in Nepali unless it chooses English, and the other language is under `/en/` or `/ne/`. Listings, menus and search show the language being read, and a switcher in the header of every page goes to the same page in the other language (or its home page). Editors write a page in one language and copy it into the other with **Translate** when they want to | `WAGTAIL_I18N_ENABLED`, `Locale`, `wagtail.contrib.simple_translation`, Django's `i18n_patterns` |
| Search | Full-text search over page content in the language being read, Nepali words included, excluding drafts and private pages; editor-pinned results | `search_fields`, `wagtail.contrib.search_promotions` |
| SEO | Sitemap, robots.txt, canonical and Open Graph tags, social sharing image, redirects (including automatic ones on slug change) | `wagtail.contrib.sitemaps`, `wagtail.contrib.redirects`, promote panels |
| Headless | Read-only JSON for pages, images and documents, e.g. for a mobile app | `wagtail.api.v2` |
| Admin | "Highlight" rich text button, fundraising dashboard panel, moderation workflow, scheduled publishing | Hooks, Draftail features, dashboard components, workflows |

| Campaign page | Admin dashboard |
|---|---|
| ![Campaign page](../screenshots/campaign.png) | ![Admin dashboard](../screenshots/admin-dashboard.png) |

## Writing in two languages

Each page can be in Nepali, English or both. Publish in the language you have; nothing on the site
waits for the other one. Until a page in the site's main language is translated, readers of the
other language are sent to it. A page only in the other language is listed only in that
language.

- **To write a page in one language,** add it under that language's home page: the Nepali pages
  sit under the Nepali home page. The page explorer labels the two home pages with their
  language, and a page's status panel (the ⓘ button, in the explorer or while editing) shows its
  language, which translations it has, and **Switch locales** to open one.
- **To translate a page,** open it and choose **Translate** (or **Translate** in the page
  explorer's "More" menu), then the language. Wagtail copies the page, with its images and
  blocks, into the other language as a draft and opens it. Rewrite the text, keep the slug, and
  submit it for moderation as usual.
- **Slugs are always in English,** in both languages, so a page's two addresses differ only by
  `/ne/` (`/appeals/flood-relief/` and `/ne/appeals/flood-relief/`). A Nepali title leaves the
  slug empty, so type an English one.
- **Readers switch language at the top of any page.** It goes to the same page in the other
  language once that's published, and to the other language's home page until then. The
  switcher appears once both languages have a published home page.
- **Promote a search result in each language.** Search shows only pages in the language being
  read, and so do promoted results: to promote the flood appeal for "बाढी" and for "flood", add a
  promotion for each, pointing at the page in that language. A promoted link to another website
  shows in both languages.
- **Translate the parent page first.** A language is greyed out when the page above isn't
  translated yet; the form links to that page's Translate.

Editors draft and moderators publish; [Permissions](permissions.md) says who can change what.
The [models reference](../reference/models.md) lists the fields behind each feature.
