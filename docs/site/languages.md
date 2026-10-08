# Languages

The site is in **Nepali and English**. Each charity chooses the language its site opens in, and a
page can be written in one language, or both, without waiting for the other. In Nepal most
supporters read Nepali first, and writing everything twice isn't realistic for a small charity, so
one-language pages must always work.

Code: `core/languages.py` (which language versions of a page exist), `core/templatetags/language_tags.py`
(the switch and `hreflang` links), `core/middleware.py` (addresses and fallback), `core/sitemaps.py`,
`core/apps.py` (creates the languages), settings in `charity/settings/base.py`, and the site's own
Nepali words in `locale/ne/` ([below](#menus-buttons-and-messages)).

## What readers see

- **The main language is at `/`** and the other is under its prefix: on a Nepali charity's site
  English pages are at `/en/…`; on the Brightwell demo, which opens in English, Nepali pages are at
  `/ne/…`.
- **A language switch in the header of every page** goes to the same page in the other language,
  or to that language's home page if this page isn't translated, so it never leads to a "page not
  found". The language being read is filled and the other outlined; on a phone only the other is
  shown. It appears once both languages have a published home page.
- **Menus, listings and search show the language being read.** A page only in one language is
  listed only in that language.
- **The site's own words are in the language being read too:** the header and footer, buttons, the
  pledge form with its labels and errors, search, pagination, "Page not found". Editors' content
  (titles, page text, the banner, testimonials) is shown as written until
  [#117](https://github.com/dipbazz/Charity-wagtail-CMS/issues/117).
- **An address with no page in that language** (such as `/ne/news/` before the news page is
  translated) redirects to the same address in the main language, if a page is there.

## What editors do

- **Write a page in one language** by adding it under that language's home page. The page
  explorer labels each home page with its language, and a page's status panel (ⓘ) shows its
  language, its translations and **Switch locales** to open one.
- **Translate a page** with **Translate** (on the page, or in the explorer's More menu): Wagtail
  copies it, with its images and blocks, into the other language as a draft. Rewrite the text,
  keep the slug, and submit it for moderation as usual. A language is greyed out until the page
  above is translated; the form links to that page's Translate.
- **Slugs stay in English** in both languages, so a page's two addresses differ only by the prefix
  (`/appeals/flood-relief/` and `/ne/appeals/flood-relief/`). A Nepali title leaves the slug
  empty, so type an English one.
- **Promote a search result in each language**: a promoted page shows only in its own language,
  so add one promotion per language. A promoted link to another website shows in both.
- **The admin stays in English**: Wagtail has no Nepali translation of its admin.

## How it works

- **One page tree per language** (Wagtail's built-in translation, `WAGTAIL_I18N_ENABLED`), each
  under its own home page. A translation is a separate page linked to the original
  (`translation_key`); in code, `page.copy_for_translation(locale)` then publish.
  Not `wagtail-localize`: its segment-by-segment translation suits teams of translators, and here
  the same person usually writes both versions.
- **Translate** comes from `wagtail.contrib.simple_translation`. Its option to copy every new page
  into every language is off, because one-language pages must stay possible. It only offers
  languages that exist as Wagtail locales, and Wagtail creates only the main one, so `core` creates
  a locale for each language after every `migrate`.
- **English-only slugs** (`WAGTAIL_ALLOW_UNICODE_SLUGS = False`): Django's slug check rejects
  Devanagari vowel signs and the virama, and the admin would drop them from a slug made from a
  Nepali title (धारा मर्मत becomes धर-मरमत).

### Addresses

- `LANGUAGE_CODE` is the main language; the other is served under its prefix through
  `i18n_patterns(prefix_default_language=False)` (`charity/urls.py`). The admin, API, documents,
  media, sitemap and robots.txt have no prefix.
- So the address alone sets a response's language. The middleware leaves out
  `Vary: Accept-Language`, which would make caches keep a copy of each page per browser language.
- The fallback redirect (302) is in the same middleware. The home page also refuses to serve a
  language that has no published home page of its own, or Wagtail would serve the main language's
  pages under the other's address.
- `LANGUAGE_CODE` must be exactly `en` or `ne`. A variant such as `en-gb` would put even the main
  language under a prefix, so English uses British date and number formats through
  `FORMAT_MODULE_PATH` (`charity/formats/en/`) instead.

### Keeping each language to itself

**Any page query visitors see, other than a page's own children, filters by the page's language**
(`locale_id`), or Nepali and English pages mix. Children (`child_of`) are already in one
language; the home page's appeals, the Donate page's appeal list and the menu filter explicitly.
This rule has caused a bug before.

**A link to a chosen page follows the reader's language**: an appeal's Donate button and the
privacy notice links go to the chosen page's published translation in the language being read,
else to the page itself. Done by hand, because Wagtail's `.localized` costs a query even on a
main-language page.

### Menus, buttons and messages

The site's own words are marked for translation and translated in one catalog,
`locale/ne/LC_MESSAGES/django.po` (English is the words in the code, so it needs no catalog).
Django's own Nepali catalog already covers its built-in form errors ("This field is required.")
and the month names in dates, so those need nothing from us.

**Marking text.** Any text a visitor reads, or their screen reader, is marked:

- Templates: `{% translate "Search" %}` for a phrase, `{% blocktranslate trimmed with n=items.number %}Page {{ n }}{% endblocktranslate %}`
  for a sentence with a value in it (a filter with an argument, such as `date:"j F Y"`, goes in
  the `with`), and `{% blocktranslate count %}` for "1 result" / "2 results". Keep a sentence in
  one piece: Nepali word order differs, so never build it from translated fragments.
- Python: `gettext_lazy` for text that's set once when the code loads (a form's `labels`, a
  class attribute) and `gettext` inside a method that runs per request.
- Scripts: `charity.js` writes no words of its own. Its text comes from `data-` attributes the
  template fills in (the "Copy link" button's `data-copied`, the message box's `data-count-text`),
  so it needs no download of its own and the page stays within its weight budget.
- **Not marked: the admin.** Editors work in English, so model field names, help texts and panel
  headings stay as they are. The pledge form words itself in `campaigns/forms.py` rather than
  taking its labels from the `Pledge` model, so the model's English stays for the admin; the
  countries in Site settings stay English the same way (`phone_country_choices(translate=True)` is
  the supporters' list).

**Amounts** keep Latin digits and their lakh or western grouping in both languages ("Rs 46,87,500"):
Nepali digits are a separate piece of work.

**Adding or changing a word:**

1. Mark it as above.
2. `uv run python manage.py makemessages -l ne --ignore ".venv" --ignore "docs" --ignore "static" --ignore "media" --no-location --no-wrap`
   adds the new text to the `.po` file with an empty `msgstr`.
3. Write the Nepali in the `.po` file. Don't leave an entry empty or `fuzzy`: the tests fail. Keep
   `%(name)s` and `{name}` placeholders exactly as they are.
4. `uv run python manage.py compilemessages --ignore ".venv" --ignore "docs" --ignore "node_modules"`
   writes the `.mo` file the site reads.
5. Commit both files.

**The compiled `.mo` file is committed,** so running the site, the tests and building the Docker
image need no GNU gettext tools; only whoever edits the `.po` file does. A test compares the two
and fails if the `.mo` is out of date (it skips where gettext isn't installed, and runs in CI).

**A test fails if visible text isn't marked.** `charity/tests/test_translations.py` reads every
public template and fails on a word outside `{% translate %}` / `{% blocktranslate %}`, or in an
`aria-label`, `placeholder`, `title` or `alt` attribute. (Templates only the admin shows, in
`previews/` and `admin/` folders, are skipped.) It can't see Python strings: mark those as you
write them. Wording needs a Nepali speaker's eye: have one read the `.po` file before a release.

### The switch, `hreflang` and the sitemap

`{% language_versions %}` finds, in one query, each language's published home page and the
published translations of the page being read. The header's switch uses it, and so does
`<head>`: a page that has a translation gets `<link rel="alternate" hreflang>` for each version,
with `x-default` for the main language, so search engines show people the page in their
language. The sitemap lists the same alternates. Search keeps its query when switching.

### Search in Nepali

`/ne/search/` searches Nepali pages only, and so do its promotions. SQLite's full-text search
already splits Devanagari into words with their vowel signs and joined letters, so Nepali words
are found without extra setup.

## Nepali text on screen

Devanagari needs more room than English:

- **The phone's own Devanagari font, no download.** The font list names the Latin system fonts,
  then Noto Sans Devanagari (Android), Kohinoor Devanagari (iPhone and Mac) and Nirmala UI
  (Windows). The Latin fonts have no Devanagari letters, so the browser takes those from the next
  font.
- **More line height**, because vowel signs sit above and below the letters: 1.8 for Nepali body
  text and 1.45 for headings, against 1.6 and 1.2 for English. Buttons and form fields hold one
  line and keep 1.6, and the charity's name keeps the main language, so the header is the same
  height in both languages.
- **No letter spacing or capitals transform on Nepali text**: spacing breaks joined letters apart,
  and Devanagari has no capitals. A rule may set them only for English (`:lang(en)`);
  `core/tests/test_stylesheet.py` checks this.

## Choosing the main language

- **Production** reads `DJANGO_LANGUAGE_CODE`: `ne` (the default) or `en`. Choose it before adding
  content, because changing it later changes every page's address.
- **Development** opens in English, like the demo content. To see a site Nepali-first, put
  `DJANGO_LANGUAGE_CODE=ne` in `.env.local` (copy `.env.local.example`).
- **Tests** always run with English as the main language, so Nepali test pages are under `/ne/`
  ([Testing](../contributing/testing.md#languages-in-tests)).
- **The demo content is English-first**: `seed_demo` refuses to run on a Nepali-first site.

## Not yet

- The banner, testimonials, partners and footer's contact details in the reader's language (#117).
- Nepali digits (०१२…) and Bikram Sambat dates.
