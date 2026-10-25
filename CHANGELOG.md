# Changelog

Every notable change to the site, for the people who edit it, host it or work on it. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) as defined for this site in
[Versions and releases](docs/contributing/releases.md).

Each pull request adds its line under **Unreleased**. A release moves those lines under a new
version number.

## [Unreleased]

## [0.5.0] - 2026-10-25

### Upgrade notes

- Nothing changes until a charity takes payments. Then set each provider's merchant keys in the
  server's `deploy/aws/.env` as `DJANGO_PAYMENT_<PROVIDER>_<KEY>` (the keys are listed in Running the
  live site), and `DJANGO_LIVE_PAYMENTS=true` only together with live keys. The `web` service now
  reads the whole `.env`, and a provider with only some of its keys stops the site starting
  ([#93](https://github.com/dipbazz/Charity-wagtail-CMS/issues/93)).
- Caddy now refuses any request over 12 MB, so nobody can fill the server's disk with one upload
  ([#217](https://github.com/dipbazz/Charity-wagtail-CMS/pull/217)), and sends each visitor's
  address to the site, which the new limits count by
  ([#226](https://github.com/dipbazz/Charity-wagtail-CMS/issues/226)). After deploying, run
  `sudo docker compose exec -w /etc/caddy caddy caddy reload` in `deploy/aws/`: `up -d` keeps Caddy
  on its old configuration, and until it's reloaded nothing is limited and the logs say
  `No HTTP_X_REAL_IP on the request`.
- The nightly backup now deletes old receipt screenshots after it has copied the backup to S3
  ([#217](https://github.com/dipbazz/Charity-wagtail-CMS/pull/217)).

### Added

- Whoever sets up a charity sends it one guide and one form, both made from the onboarding pack in `onboarding/` and kept up to date under the same links, so a charity never works from an old copy ([#203](https://github.com/dipbazz/Charity-wagtail-CMS/issues/203)).
- Supporters can pay their pledge straight after sending it: with eSewa or Khalti where the charity
  has set them up, or in person at the charity's office, with its address and phone from Site
  settings. Whether a payment went through comes from eSewa or Khalti themselves, so a payment can't
  be faked, and a failed or cancelled one can be tried again. Payments use eSewa's and Khalti's test
  systems, where no money moves, until a charity goes live, and the pay page and a test payment's
  thank-you say so.
  The team sees in **Pledges** whether each pledge is paid, can filter by it, and gets the provider's
  reference in the export. A pledge paid with real money can't be deleted, even by a superuser
  ([#93](https://github.com/dipbazz/Charity-wagtail-CMS/issues/93)).
- Supporters can pay a pledge by scanning the charity's own QR code. The new **QR codes** page in the
  admin lists them, with an **Add** button when there are none; each has a name in each language, an
  image, and the account name the app shows after scanning. Only moderators can change them. The
  **Scan our QR code** has two steps, each on its own page. Step 1 shows the amount and the pledge
  number to copy into the app's Remarks, the QR as uploaded with a **Save QR code** link, the account
  name to check after scanning, and the account to pay instead if scanning doesn't work. Step 2,
  **I've paid**, takes the transaction ID from the receipt, and the pledge shows **To confirm**: it
  can't be paid another way until it's checked, so nobody pays twice. Meanwhile each of its pay
  addresses thanks the supporter and gives the pledge number to call about. The site can't check a QR payment, so a moderator finds it in the wallet or bank statement and marks it
  paid or not found from the pledge, which also shows each payment's history. Moderators get the new
  **Can confirm payments** permission for this. A charity with a QR code but no eSewa or Khalti
  account can now take gifts on its own site
  ([#197](https://github.com/dipbazz/Charity-wagtail-CMS/issues/197)).
- Every pledge has a six-digit **pledge number**, shown on its pay pages as "482 913". A supporter
  paying at the office gives it, so the team finds their pledge without guessing between two people
  with the same name. Search for it in **Pledges**, with or without the space; the list and the
  export show it ([#202](https://github.com/dipbazz/Charity-wagtail-CMS/issues/202)).
- A pledge's page in the admin now leads with what the team acts on: the amount, how often and the
  appeal, then whether it's paid and how ("Paid with eSewa on 14 Oct, transaction 000AWEO") or why
  not, the contact details with email and phone as links, the message and consents, and each payment
  with what happened to it, step by step, in plain words. **Check with eSewa now** (or Khalti) asks
  the provider about a payment that hasn't finished, so "did my payment go through?" can be
  answered without the provider's portal. Pledges a person must look at (money received for another
  amount, or part refunded) say **Needs checking** in the list, the export and on the page, and
  search now finds a pledge by mobile number or by a reference or transaction ID from a statement
  ([#96](https://github.com/dipbazz/Charity-wagtail-CMS/issues/96)).
- Supporters who pay by QR code can send a screenshot of their app's receipt with **I've paid**,
  instead of the transaction ID or as well as it: either one is enough now. A screenshot, or a
  photo from any phone camera, of up to 5 MB is taken, and only a copy at most 2000 pixels across
  is kept; a screenshot over 13 megapixels is refused, so no upload can run the server out of
  memory. People who can confirm
  payments see the screenshot on the pledge in the admin; editors only read that one was sent. The
  website saves each screenshot afresh, keeps it where no web address reaches it, and deletes it
  once the payment is marked paid or not found, or after 30 days at most. Screenshots aren't backed
  up. Add a line to your privacy notice saying so (the demo's notice has the wording). A phone
  camera's JPEG that was refused as "not a JPEG, PNG or WebP image" is now accepted, for QR codes
  too ([#197](https://github.com/dipbazz/Charity-wagtail-CMS/issues/197)).
- Site settings have a new **Refund policy**, written in each language like the address. Once it's
  filled in, every pay page shows it under "Refunds", below the gift, so supporters read it before
  choosing to pay. Left empty, the pay pages say nothing about refunds
  ([#202](https://github.com/dipbazz/Charity-wagtail-CMS/issues/202)).
- After paying, supporters can tell their friends. The thank-you page says what their gift does, then
  invites them to share with **Tell your friends** (their phone's own share menu), WhatsApp, Facebook
  or a link to copy. If they agreed to show their gift, friends get a page of its own: "Asha is
  supporting Clean water for Kisumu", what she gave, the appeal's progress and a button to give too.
  Without that agreement the share has no name and leads to the appeal. Supporters can change their
  mind on the thank-you page, and the pledge form's consent now says exactly when their name and
  amount are shown. Editors and moderators can take a gift's page down from the pledge with **Stop
  showing on the website** (a new permission both groups have), and only they can show it again.
  Meanwhile, links already shared lead to the appeal
  ([#100](https://github.com/dipbazz/Charity-wagtail-CMS/issues/100)).

### Changed

- After sending a pledge, supporters choose how to pay first, and each way has its own page: **Pay
  online** (eSewa and Khalti), **Pay in person**, and **Not ready to pay yet?**, which gives the link
  to come back and pay later. Paying in person lists what to do at the counter, a step at a time, and
  is offered only when Site settings tick the new **We take gifts at our office** and give an office
  address or phone; the Donate page's sentence about how to pay says "or in person" only then too. With only one way to pay, the form goes straight
  to it. The Donate page's thank-you text now shows only on a site with no way to pay yet
  ([#202](https://github.com/dipbazz/Charity-wagtail-CMS/issues/202)).
- The Donate page now says how paying works on its own site, in Nepali and English: with the
  providers set up there and in person, or that no payment is taken online yet. A charity's own
  payment notice follows it, for anything to add such as bank details. Notices still holding the old
  default text ("No payment is taken on this website yet") were removed, and the button reads
  **Continue to payment** when a payment step follows
  ([#93](https://github.com/dipbazz/Charity-wagtail-CMS/issues/93)).
- The **Pay with eSewa** and **Pay with Khalti** buttons now show each provider's own logo, so
  supporters find their app at a glance instead of reading each button. The buttons are white with a
  border in the charity's colour, one under another, and keep the logo while they say "Opening
  eSewa…". A charity has nothing to set up: the logos come with the providers
  ([#201](https://github.com/dipbazz/Charity-wagtail-CMS/issues/201)).
- A pledge on the Donate page can be for up to 999,999 in the site's currency (it was 99,999,999),
  so an extra zero typed by mistake is refused. A bigger gift is arranged with the charity directly
  ([#214](https://github.com/dipbazz/Charity-wagtail-CMS/pull/214)).
- Site settings now save the address and the refund policy only when each is written for every
  language, or for none, so readers of each language are told the same. If your address is in one
  language only, the next save asks for it in the others. The charity's name can still be in one
  language ([#202](https://github.com/dipbazz/Charity-wagtail-CMS/issues/202)).

### Fixed

- Buttons such as Search and Send are in the site's font, like links styled as buttons, rather than
  the browser's own ([#93](https://github.com/dipbazz/Charity-wagtail-CMS/issues/93)).
- With JavaScript off, the **Copy link** buttons on "Not ready to pay yet?" and the news feed no longer
  show and then do nothing when pressed; the link can be selected and copied by hand
  ([#100](https://github.com/dipbazz/Charity-wagtail-CMS/issues/100)).

### Security

- Exported pledges and form submissions show what supporters typed as text. A name such as
  `=HYPERLINK(…)` could run as a formula when the team opened the export in Excel or Google Sheets,
  and send other supporters' details away ([#200](https://github.com/dipbazz/Charity-wagtail-CMS/pull/200)).
- One internet connection can now send only so many new pledges, start so many payments, say "I've
  paid" so many times and come back from a provider so many times in five minutes, so a script can't
  fill a charity's Pledges list, get its merchant account throttled or fill the server's disk. A
  supporter paying normally never notices; one try too many is asked to wait a few minutes, with
  their answers kept and nothing saved ([#226](https://github.com/dipbazz/Charity-wagtail-CMS/issues/226)).

## [0.4.0] - 2026-10-11

### Added

- Moderators can give the site their charity's own colours: a main and an accent colour in
  **Site settings → Brand**, from which the site makes its other shades, on every page. A colour
  that would make text hard to read can't be saved, and the message suggests a shade of it that
  works. A site that doesn't choose looks exactly as before
  ([#133](https://github.com/dipbazz/Charity-wagtail-CMS/issues/133)).
- Moderators can see changes to Site settings, such as new brand colours, on real pages before
  saving them: the preview panel shows the home page, the Donate page or the Nepali home page with
  the unsaved choices, and visitors see nothing until they're saved
  ([#136](https://github.com/dipbazz/Charity-wagtail-CMS/issues/136)).
- Moderators can choose a font style in **Site settings → Brand → Font style**: modern, which is
  what the site uses now, traditional, with a serif font like a printed book, or friendly, with
  rounded letters. Each uses fonts already on visitors' phones, so pages load as fast as before, and
  Nepali text keeps its own fonts. The preview (the phone icon at the top right) shows a style on
  the site's pages before you save, and a site that doesn't choose keeps its font
  ([#135](https://github.com/dipbazz/Charity-wagtail-CMS/issues/135)).
- Moderators can choose a light or dark name bar at the top of every page, and a light or dark
  footer, in **Site settings → Brand → Header and footer**, so a logo drawn for a white background
  has one. Text stays easy to read either way, and a site that doesn't choose keeps its dark name
  bar and footer ([#134](https://github.com/dipbazz/Charity-wagtail-CMS/issues/134)).
- Moderators can write the charity's name in each language in **Site settings → Text in each
  language**, next to the address, for a charity whose Nepali and English names differ. Readers see
  the name in their language in the header, the footer, the browser tab and link previews, and the
  main language's name until another language has its own. A site that hasn't written one keeps
  the name it was set up with ([#157](https://github.com/dipbazz/Charity-wagtail-CMS/issues/157)).
- Moderators can add the charity's logo in **Site settings → Brand → Logo**, and it shows beside
  the charity's name at the top of every page, in both languages. A slider sets how big it is,
  from small to large enough to read the lettering in a seal or a crest, and the preview follows
  it before anything is saved. A long name wraps beside the logo instead of crowding the page, and
  a site without a logo looks exactly as before
  ([#123](https://github.com/dipbazz/Charity-wagtail-CMS/issues/123)).

## [0.3.0] - 2026-10-08

### Upgrade notes

- **Sites now open in Nepali unless they say otherwise.** An English-first site, such as the
  Brightwell demo server, must add `DJANGO_LANGUAGE_CODE=en` to `deploy/aws/.env` before
  upgrading; without it, its home page stops being found. Choose a site's language before adding
  content, because changing it later changes every page's address.
- Scheduled publishing and the admin now use Nepal time (`Asia/Kathmandu`). Pages already
  scheduled keep their moment, but the admin now shows it in Nepal time.
- **`charity/settings/local.py` is no longer read.** To open your local site in Nepali, set
  `DJANGO_LANGUAGE_CODE=ne` in a new `.env.local` file (copy `.env.local.example`); development opens in
  English otherwise. You can delete the old file.

### Added

- Pages can now be read in Nepali as well as English. Each site opens in its main language, and
  pages in the other language are under `/ne/` (or `/en/` on a Nepali site). Menus, the home
  page's appeals and the Donate page's appeals show only pages in the language being read. A
  page that isn't translated yet sends Nepali readers to the English page (or the other way
  round on a Nepali site) instead of a "page not found"
  ([#120](https://github.com/dipbazz/Charity-wagtail-CMS/pull/120)).
- Editors can publish a page in one language and translate it later: **Translate** on any page
  copies it, with its images and blocks, into the other language as a draft to rewrite and
  submit. Slugs stay in English, so a page's Nepali address is its English one under `/ne/`. On
  a translated appeal, the Donate button goes to the Donate page in the same language
  once that's translated too
  ([#121](https://github.com/dipbazz/Charity-wagtail-CMS/pull/121)).
- Supporters can read how their details are used before they send them: choose a privacy notice
  page in **Site settings → Privacy notice**, and the footer of every page links to it, as does
  "How we use your details" just before the pledge form's and every form page's send button. The
  demo site adds an example notice; replace it with your charity's own before going live.
- The charity's name now has a dark row of its own at the top of every page, centred, so a long name
  fits on a phone and the header stands out from white pages. The language switcher looks like two
  buttons: the current language filled, the other outlined. Below it, the menu is on the left, and the language and Donate are on the right
  ([#122](https://github.com/dipbazz/Charity-wagtail-CMS/pull/122)).
- Readers can switch between नेपाली and English from the header of every page. It opens the same
  page in the other language, or that language's home page if the page isn't translated yet. Search
  engines are told which pages are translations of each other, so they show people the page in
  their language
  ([#122](https://github.com/dipbazz/Charity-wagtail-CMS/pull/122)).
- You can run the live site's Docker image on your own computer, with the demo content, using
  `docker compose up --build`. Page weight can be measured with Lighthouse before pushing.
- The menus, buttons, forms and messages are now in Nepali when someone reads the site in Nepali:
  the header and footer, the Donate page with its pledge form, its labels and errors, search, the
  "Copy link" button and "Page not found". Amounts keep their lakh grouping
  ([#116](https://github.com/dipbazz/Charity-wagtail-CMS/issues/116)).
- Search finds pages in the language being read, including Nepali words, and editors can promote
  a different result for each language
  ([#122](https://github.com/dipbazz/Charity-wagtail-CMS/pull/122)).
- Nepali text uses the phone's own Devanagari font and has more space between lines, so vowel
  signs above and below the letters no longer touch the lines next to them
  ([#122](https://github.com/dipbazz/Charity-wagtail-CMS/pull/122)).
- The announcement banner, the footer's address, testimonials, partners and news categories can be
  written in Nepali and English, and readers see them in the language they're reading, or in the
  site's main language until a translation exists. Editors translate partners, testimonials and
  categories with **Translate**, as for pages, and write the banner and address in each language in
  their settings. On a Nepali page the Donate button and the banner's link go to the Nepali version
  of their page once it's published. Each Site now has its own banner
  ([#117](https://github.com/dipbazz/Charity-wagtail-CMS/issues/117)).

### Changed

- Page-weight limits now cap each page's images strictly and give its HTML, CSS and
  JavaScript one fixed allowance, so ordinary template and style changes no longer fail the
  Lighthouse check.
- Contributors add their changelog entry as a small file in `changelog.d/` instead of editing
  `CHANGELOG.md`, so two open pull requests no longer conflict there; a release merges the files into
  `CHANGELOG.md`.
- The documentation is reorganised by feature: each part of the site (pages and content, appeals and
  giving, languages, images, look and feel, editors and permissions) and running the live site is
  explained on one page, well enough to rebuild it, so a question no longer needs five or six pages.

### Fixed

- Refreshing the Donate page's thank-you page no longer sends the pledge again. Going back to the
  form and sending it again, even with changes, updates the same pledge instead of adding
  another, so the team doesn't get duplicate pledges
  ([#110](https://github.com/dipbazz/Charity-wagtail-CMS/pull/110)).
- Appeal pages no longer scroll sideways on the smallest phones (320px wide)
  ([#125](https://github.com/dipbazz/Charity-wagtail-CMS/pull/125)).
- On a 320px phone the home page no longer scrolls sideways, and the news page's Copy link
  button and the Donate page's dropdowns and fields are big enough to tap on every device.

## [0.2.0] - 2026-10-06

The giving journey: suggested amounts and a pledge form on the Donate page, amounts in Nepalese
rupees or pounds, and accessibility and layout fixes.

### Upgrade notes

- Amounts are now shown in the currency chosen in **Site settings**, which is Nepalese rupees
  unless you change it. If your appeal targets and suggested amounts are in pounds, choose
  pounds sterling there after upgrading.
- The migrations, which run when the container starts, add a table for pledges and settings
  for the currency and the mobile number's country, and let the Editors and Moderators groups
  view pledges. Pledges hold supporters' names and contact details, so check who is in those
  groups. Existing pages and content aren't changed.

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

[Unreleased]: https://github.com/dipbazz/Charity-wagtail-CMS/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/dipbazz/Charity-wagtail-CMS/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/dipbazz/Charity-wagtail-CMS/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/dipbazz/Charity-wagtail-CMS/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/dipbazz/Charity-wagtail-CMS/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dipbazz/Charity-wagtail-CMS/releases/tag/v0.1.0
