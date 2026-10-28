# The charity site standard

Every charity's site on this platform has the same structure, so a supporter who has used one
finds everything in the same place on the next. Each charity still looks like itself, through its
[brand settings](look-and-feel.md#brand-colours), its words and its photos. The standard was
agreed on 11 October 2026 ([Decisions](../decisions.md#one-standard-structure-for-every-charity))
and is being built in [#191](https://github.com/dipbazz/Charity-wagtail-CMS/issues/191); until
then the site differs from it as [listed below](#whats-built-so-far).

## Why

- **People expect a site to work like the ones they already use** (Jakob's Law), so a familiar
  structure is quicker to use than a clever one. GOV.UK's name for the idea is "be consistent, not
  uniform".
- **Donors look first for what a charity does and where the money goes.** In Nielsen Norman
  Group's study of donation sites, only 43% of sites showed their goals on the home page, only 4%
  said where a gift would go, and 17% of the time people couldn't find where to give.
- **Charities don't do this on their own.** On 11 October 2026 the site was compared with seven
  charity sites: the two Nepali ones named their menus differently and barely showed who they
  were, while the best international ones showed their registration, accounts and ratings on
  every page.
- **It already works elsewhere:** UK councils share LocalGov Drupal, US federal websites share the
  US Web Design System, and Nepal's municipal websites share one theme.

## The header

On every page, one bar: the logo and name on the left, linking to the home page; **Donate** on the
right, always on screen; the language switch; and the menu, behind a Menu button on phones. The
announcement banner, when it's on, sits above the bar.

## The menu

The standard sections come first, always in this order and with these names. The Nepali names are
still to be checked with charities.

| Section | नेपाली | What it holds |
|---|---|---|
| About us | हाम्रो बारेमा | What the charity does and where, who runs it (board and staff), its registration, and **Reports and accounts**: annual reports and audited accounts |
| Appeals | सहयोग अपिल | Open appeals with their progress, then past appeals |
| Stories | कथाहरू | News and stories, by category |
| Get involved | सहभागी हुनुहोस् | Volunteering, fundraising, partnering, giving goods or time |
| Contact | सम्पर्क | Address, phone, email, a map link and a message form |
| **Donate** (the button) | दान दिनुहोस् | Every way to give, what a gift does, where the money goes, tax relief |

- The names come from the standard and are translated in `locale/ne`, not taken from page titles,
  so an editor can't rename, reorder or remove a standard section.
- **A charity can add its own pages** after the standard sections, or under one of them. How many
  extra menu items fit is decided in
  [#171](https://github.com/dipbazz/Charity-wagtail-CMS/issues/171).

## The footer

On every page: the charity's name; one **registration line** (in Nepal, the District
Administration Office registration number and district, the Social Welfare Council affiliation
number and the PAN; in the UK, the registered charity number); the address, phone and email;
social links; and links to Reports and accounts, the privacy notice, the accessibility statement
and Contact.

## Pages every site has

Home, About us (with who runs the charity, and Reports and accounts under it), Appeals, Stories,
Get involved (with the volunteer form under it), Contact, Donate, the privacy notice and the
accessibility statement, in each of the site's languages. A new site starts with all of them in its
main language, as drafts with placeholder text that tells the editor what to write, and with a home
page in each language. The other language's pages are made with Translate
([Languages](languages.md#what-editors-do)) once each main page is written and published. A page
with placeholder text can't be published. The charity's own pages go alongside.

## The home page

In this order:

1. The charity's mission in one sentence, with Donate.
2. Open appeals.
3. What a gift does, and where the money goes.
4. Stories.
5. Recent supporters.
6. Get involved.
7. Partners and the registration line.

## The Donate page

Every way to give (eSewa, Khalti, QR, bank transfer, card, whichever the charity takes), where the
money goes, the pledge form, and a line on tax relief when it applies: in Nepal, a gift to an
organisation the Inland Revenue Department has approved can be deducted from the donor's taxable
income, up to Rs 1,00,000 or 5% of it (Income Tax Act 2058, section 12); in the UK, Gift Aid. It
links to Reports and accounts.

## What's fixed and what each charity sets

| The same for every charity | Each charity's own | Never for one charity |
|---|---|---|
| Page types and where they go; menu sections, names and order; where Donate sits and its colour role; what the footer shows; forms and their consent wording; accessibility; the page-weight budget; the language switch | Name, logo and its size, main and accent colours, light or dark name bar and footer, font style, photos, every word, which optional parts are on (volunteering, partners), domain, payment details | Its own templates, CSS or code; menu items outside the standard and its own pages; a branch or a version of its own |

## How it's kept

- **A new site starts with the standard pages** in its main language and a home page in each
  language, from one command
  ([#175](https://github.com/dipbazz/Charity-wagtail-CMS/issues/175)). Placeholder text is one
  line in square brackets starting "[Write:", and no page carrying it can go live.
- **Tests fail when a site drifts from the standard**, such as a missing or reordered menu section.
  Each issue that builds a part adds its test.
- **Changing the standard means changing this page,** in a pull request of its own, and every
  charity's site gets the change at the next release. A request from one charity becomes a change
  for every charity, or waits ([Principles](../contributing/index.md#principles)).
- **What we ask a new charity for follows this page:** the onboarding pack's guide and questions
  describe the same menu, and a test fails when a menu section here has no guide section or
  question there ([Onboarding a charity](../contributing/onboarding.md)).

## What's built so far

Delete this section once [#191](https://github.com/dipbazz/Charity-wagtail-CMS/issues/191) is done.

| Part | Today | Issue |
|---|---|---|
| Header | The name on a row of its own above the controls row; it scrolls away | [#176](https://github.com/dipbazz/Charity-wagtail-CMS/issues/176), [#139](https://github.com/dipbazz/Charity-wagtail-CMS/issues/139) |
| Menu | Whichever pages an editor ticks "Show in menus" for, in tree order, named by their titles | [#171](https://github.com/dipbazz/Charity-wagtail-CMS/issues/171) |
| Footer | Name, address, contact details, social links, privacy link and a UK charity number | [#172](https://github.com/dipbazz/Charity-wagtail-CMS/issues/172), [#167](https://github.com/dipbazz/Charity-wagtail-CMS/issues/167), [#170](https://github.com/dipbazz/Charity-wagtail-CMS/issues/170) |
| About us | A standard page, written freely | [#169](https://github.com/dipbazz/Charity-wagtail-CMS/issues/169), [#170](https://github.com/dipbazz/Charity-wagtail-CMS/issues/170) |
| Appeals and Stories | Built | |
| Get involved | A volunteer form at `/volunteer/` | [#168](https://github.com/dipbazz/Charity-wagtail-CMS/issues/168) |
| Contact and accessibility statement | Missing | [#167](https://github.com/dipbazz/Charity-wagtail-CMS/issues/167) |
| Home page | Banner, current appeals, then any blocks | [#173](https://github.com/dipbazz/Charity-wagtail-CMS/issues/173) |
| Donate page | Introduction, payment notice, pledge form, then any blocks | [#174](https://github.com/dipbazz/Charity-wagtail-CMS/issues/174) |
| A new site's pages | None: `seed_demo` builds only the fictional demo. A page with placeholder text can't go live | [#175](https://github.com/dipbazz/Charity-wagtail-CMS/issues/175) |

## Where the code is

The header and footer are in `charity/templates/base.html` and its includes, the menu is
`{% main_menu %}` (`core/templatetags/navigation_tags.py`), the footer's details are Site settings
(`core/models.py`), and the page types are in `home`, `campaigns`, `news` and `contact`, each with
its own rules on where it may go ([Overview](overview.md#the-page-tree)).

## Sources

- [Nielsen Norman Group's donation study](https://www.nonprofitpro.com/article/nielsen-norman-group-releases-new-study-nonprofit-web-sites-estimates-organizations-could-double-online-donations-405368/), as reported by NonProfit PRO
- [Jakob's Law](https://lawsofux.com/jakobs-law/) and the [GOV.UK design principles](https://www.gov.uk/guidance/government-design-principles)
- [Charity Navigator's accountability checks](https://www.charitynavigator.org/about-us/our-methodology/ratings/accountability-finance), which look on a charity's website for its board, staff and audited accounts
- [Charities Act 2011, section 39](https://www.legislation.gov.uk/ukpga/2011/25/section/39) and [Nepal's Income Tax Act 2058, section 12](https://nepallaws.com/Laws/income-tax-act-2058-2002/chapter-4-exemptible-amounts-and-other-exemptions/section-12-donation-gift-given-to-organizations-entitled-to-tax-exemption)
- [LocalGov Drupal](https://www.localdigital.gov.uk/funded-project/localgov-drupal-improving-code-sharing-between-councils-alpha) and the [US Web Design System](https://designsystem.digital.gov/about/key-benefits/)
