# Changelog

Every notable change to the site, for the people who edit it, host it or work on it. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) as defined for this site in
[Versions and releases](docs/contributing/releases.md).

Each pull request adds its line under **Unreleased**. A release moves those lines under a new
version number.

## [Unreleased]

### Added

- The Donate page now has suggested amounts and a pledge form: one-off or monthly, which appeal
  to support, and an optional mobile number for a monthly reminder.
  It says plainly that no payment is taken online yet, preselects the appeal you came from, and
  pledges are listed under Pledges in the admin, with filters and CSV/Excel export
  ([#89](https://github.com/dipbazz/Charity-wagtail-CMS/pull/89)).
- The pledge form asks for an optional message with your gift (with a count of the characters
  typed, which turns amber near the 1000 limit), and has two separate tick boxes, both unticked: email updates about the charity's projects and appeals, and showing your gift
  (name, amount, appeal and date) on the website once it's received. The team can filter and
  export pledges by each consent under Pledges
  ([#101](https://github.com/dipbazz/Charity-wagtail-CMS/pull/101)).
- Browser tests (Playwright) for what only happens in a browser, such as focus, scrolling and
  fields that appear on a choice. Run `uv run playwright install chromium` once
  ([#89](https://github.com/dipbazz/Charity-wagtail-CMS/pull/89)).

### Changed

- Amounts across the site (appeal targets, suggested gifts, the dashboard) are shown in the
  currency chosen in Site settings: Nepalese rupees by default, grouped the Nepali way
  (Rs 46,87,500), or pounds sterling
  ([#89](https://github.com/dipbazz/Charity-wagtail-CMS/pull/89)).

### Fixed

- On the Appeals and News pages, the filter you've chosen stands out from the others, and
  screen readers say which one is selected
  ([#35](https://github.com/dipbazz/Charity-wagtail-CMS/issues/35)).
- Appeal titles on the Appeals page are now the level below the page heading, so screen readers
  no longer hear a skipped level and Wagtail's accessibility check stops warning editors about it
  ([#43](https://github.com/dipbazz/Charity-wagtail-CMS/issues/43)).
- On short pages, such as a search that finds nothing, the footer now reaches the bottom of the
  window instead of stopping partway up with a white strip below it
  ([#37](https://github.com/dipbazz/Charity-wagtail-CMS/issues/37)).
- The appeal and news filters and a story's tags are now big enough to tap easily on a phone
  (44px tall instead of 27px) ([#108](https://github.com/dipbazz/Charity-wagtail-CMS/pull/108)).

## [0.1.0] - 2026-10-05

The first tracked release. It collects everything built before versioning started.

### Added

- Pages built from content blocks: headings, rich text, images with photo credits, quotes,
  impact statistics, calls to action, video, tables, document downloads, testimonials and
  partner logos ([#1](https://github.com/dipbazz/Charity-wagtail-CMS/pull/1)).
- Site settings for the charity number, contact details, donate page and social links, an
  emergency announcement banner, and a main menu
  ([#2](https://github.com/dipbazz/Charity-wagtail-CMS/pull/2),
  [#4](https://github.com/dipbazz/Charity-wagtail-CMS/pull/4)).
- Partners, and testimonials with drafts, revisions, locking and preview
  ([#3](https://github.com/dipbazz/Charity-wagtail-CMS/pull/3)).
- Fundraising appeals with a target, amount raised, dates, suggested gifts, progress bars and
  open and past filters; the homepage features open appeals
  ([#5](https://github.com/dipbazz/Charity-wagtail-CMS/pull/5)).
- News with tags, editor-managed categories and an RSS feed, and a "Follow our news" section
  ([#6](https://github.com/dipbazz/Charity-wagtail-CMS/pull/6),
  [#25](https://github.com/dipbazz/Charity-wagtail-CMS/pull/25)).
- Forms editors build themselves, with email notifications that reply to the sender and CSV
  export of submissions ([#7](https://github.com/dipbazz/Charity-wagtail-CMS/pull/7)).
- Site search with results editors can pin to the top
  ([#8](https://github.com/dipbazz/Charity-wagtail-CMS/pull/8)).
- Sitemap, robots.txt, canonical and social sharing tags, a sharing image per page, and
  redirects ([#10](https://github.com/dipbazz/Charity-wagtail-CMS/pull/10)).
- A read-only JSON API for pages, images and documents
  ([#11](https://github.com/dipbazz/Charity-wagtail-CMS/pull/11)).
- A "Highlight" button in rich text, and a fundraising panel on the admin dashboard
  ([#12](https://github.com/dipbazz/Charity-wagtail-CMS/pull/12)).
- `seed_demo`, which builds a fictional water charity with licensed photos and partner logos
  ([#13](https://github.com/dipbazz/Charity-wagtail-CMS/pull/13),
  [#44](https://github.com/dipbazz/Charity-wagtail-CMS/pull/44)).
- Smaller images for phones, in AVIF and WebP, with a square homepage banner that's compressed
  harder under its dark overlay
  ([#62](https://github.com/dipbazz/Charity-wagtail-CMS/pull/62),
  [#64](https://github.com/dipbazz/Charity-wagtail-CMS/pull/64)).
- A single-server deployment with Docker Compose, automatic HTTPS from Caddy, scheduled
  publishing, and nightly backups to S3 made by the new `backup_site` command
  ([#70](https://github.com/dipbazz/Charity-wagtail-CMS/pull/70)).
- Checks on every pull request: lint, migrations, Django's deployment checks and the tests,
  then query budgets and Lighthouse page-weight budgets
  ([#9](https://github.com/dipbazz/Charity-wagtail-CMS/pull/9),
  [#61](https://github.com/dipbazz/Charity-wagtail-CMS/pull/61)).
- Issue forms for bugs, features and docs
  ([#28](https://github.com/dipbazz/Charity-wagtail-CMS/pull/28),
  [#41](https://github.com/dipbazz/Charity-wagtail-CMS/pull/41)).
- A documentation site for people and AI agents
  ([#85](https://github.com/dipbazz/Charity-wagtail-CMS/pull/85)).
- This changelog, version numbers, milestones on the project board and a release process
  ([#87](https://github.com/dipbazz/Charity-wagtail-CMS/issues/87)).

### Changed

- The Docker image moved to Debian 13 "trixie" and dropped unused packages
  ([#24](https://github.com/dipbazz/Charity-wagtail-CMS/pull/24)).
- The demo charity uses reserved example domains for every address
  ([#27](https://github.com/dipbazz/Charity-wagtail-CMS/pull/27)).

### Fixed

- The Docker image runs the production settings
  ([#16](https://github.com/dipbazz/Charity-wagtail-CMS/pull/16)).
- Production sends email, and saves form submissions even when the mail server is down
  ([#18](https://github.com/dipbazz/Charity-wagtail-CMS/pull/18)).
- Production serves static files and uploads, and keeps the database and uploads in a
  persistent data folder ([#19](https://github.com/dipbazz/Charity-wagtail-CMS/pull/19)).
- Production refuses to start without its allowed hostnames, instead of rejecting every
  request ([#20](https://github.com/dipbazz/Charity-wagtail-CMS/pull/20)).
- Links in the API, news feed, sitemap and sharing tags use the site's real address, not
  localhost ([#26](https://github.com/dipbazz/Charity-wagtail-CMS/pull/26)).
- The header search box is the same size on every page
  ([#42](https://github.com/dipbazz/Charity-wagtail-CMS/pull/42)).
- On phones the header menu sits behind a Menu button instead of wrapping onto several lines,
  and it's collapsed before the page is first drawn, so nothing jumps
  ([#45](https://github.com/dipbazz/Charity-wagtail-CMS/pull/45),
  [#68](https://github.com/dipbazz/Charity-wagtail-CMS/pull/68)).
- Editors can change the announcement banner and manage partners, testimonials and news
  categories ([#73](https://github.com/dipbazz/Charity-wagtail-CMS/pull/73)).
- Editors can submit pages for moderation when the mail server can't be reached
  ([#79](https://github.com/dipbazz/Charity-wagtail-CMS/pull/79)).
- Server errors and warnings are written to the container log
  ([#80](https://github.com/dipbazz/Charity-wagtail-CMS/pull/80)).

### Security

- The images API hides images whose safeguarding consent isn't confirmed
  ([#17](https://github.com/dipbazz/Charity-wagtail-CMS/pull/17)).
- Documents in private collections can no longer be downloaded from `/media/` without their
  password ([#49](https://github.com/dipbazz/Charity-wagtail-CMS/pull/49)).
- Password- and login-protected stories and appeals stay out of listings, the homepage and the
  news feed ([#66](https://github.com/dipbazz/Charity-wagtail-CMS/pull/66)).
- Every CI action is pinned to a commit, and Dependabot proposes updates
  ([#69](https://github.com/dipbazz/Charity-wagtail-CMS/pull/69)).

[Unreleased]: https://github.com/dipbazz/Charity-wagtail-CMS/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dipbazz/Charity-wagtail-CMS/releases/tag/v0.1.0
