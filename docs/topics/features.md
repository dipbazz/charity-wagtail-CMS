# What the site does

What editors can do in the admin, and the Wagtail features behind each part.

| Area | What it does | Wagtail features |
|---|---|---|
| Page building | Compose pages from headings, rich text, images with photo credits, quotes, impact statistics, calls to action, video, tables, document downloads, testimonials and partner logos | `StreamField`, `StructBlock`, `ListBlock`, custom block validation and templates |
| Appeals | Target, amount raised, dates and suggested gifts; progress bars; open/closed filters; homepage features open appeals | Page models, `InlinePanel` + `Orderable`, `TabbedInterface`, custom `PageQuerySet`, preview modes |
| News | Stories with tags and editor-managed categories; tag, category and RSS URLs | `RoutablePageMixin`, `ClusterTaggableManager`, `ParentalManyToManyField` |
| Donating | Suggested amounts and a pledge form (one-off or monthly, the appeal, optional mobile number for monthly gifts, optional address) that preselects the appeal a supporter came from; pledges listed under Pledges in the admin, with filters and CSV/Excel export. No payment is taken yet | A `Pledge` model and `ModelForm`, `ModelViewSet` (listing, filters, export), `InlinePanel` |
| Forms | Build volunteer and enquiry forms, receive email (Reply-To the sender), export submissions to CSV | `wagtail.contrib.forms` |
| Supporters | Partners (drag to reorder) and testimonials with drafts, revisions, locking and preview | Snippets, `SnippetViewSet(Group)`, `DraftStateMixin`, `RevisionMixin`, `PreviewableMixin` |
| Site-wide | Charity number, contact details, donate page, currency, default phone country, social links, emergency-appeal banner | `wagtail.contrib.settings` (site and generic settings) |
| Images | Photo credit and a safeguarding consent flag on every image, which keeps unconsented images out of the API; focal-point crops; alt text from the image description | Custom image model, renditions, custom API viewset |
| Search | Full-text search over page content, excluding drafts and private pages; editor-pinned results | `search_fields`, `wagtail.contrib.search_promotions` |
| SEO | Sitemap, robots.txt, canonical and Open Graph tags, social sharing image, redirects (including automatic ones on slug change) | `wagtail.contrib.sitemaps`, `wagtail.contrib.redirects`, promote panels |
| Headless | Read-only JSON for pages, images and documents, e.g. for a mobile app | `wagtail.api.v2` |
| Admin | "Highlight" rich text button, fundraising dashboard panel, moderation workflow, scheduled publishing | Hooks, Draftail features, dashboard components, workflows |

| Campaign page | Admin dashboard |
|---|---|
| ![Campaign page](../screenshots/campaign.png) | ![Admin dashboard](../screenshots/admin-dashboard.png) |

Editors draft and moderators publish; [Permissions](permissions.md) says who can change what.
The [models reference](../reference/models.md) lists the fields behind each feature.
