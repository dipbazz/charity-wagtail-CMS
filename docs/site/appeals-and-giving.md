# Appeals and giving

How the charity raises money on the site: appeals, the Donate page, pledges, paying them, and the
team's view of them. A supporter sends a *pledge* (a promise), then pays it online with a payment
provider the charity has set up (eSewa or Khalti, in rupees), pays in person, or arranges payment
with the team ([Paying a pledge](#paying-a-pledge)). Appeal totals are still typed in by editors,
not counted from pledges.

Code: `campaigns/` (models, `forms.py` for the pledge form, `payments.py` for the payment providers
this site offers, `views.py` for the admin's Pledges, `wagtail_hooks.py` for the dashboard panel),
`nepal_payments/` (the providers themselves), `core/money.py`, `core/phone.py`. How often a
supporter gives is the `Frequency` choices in `campaigns/models.py`, shared by the model, the form
and anything that acts on pledges: compare with `Frequency.MONTHLY`, never the string.

## Appeals

**The appeals page** lists every live, public appeal under it, newest start date first, nine per
page, as cards. Filters at the top show **All appeals**, **Open appeals** (`?status=active`) and
**Past appeals** (`?status=closed`). A card shows the photo, title, summary, "Rs … raised of
Rs …" with a progress bar, and "This appeal has closed" when it has.

**An appeal is open** until the end of its end date; with no end date it's ongoing. (An appeal
whose start date is still to come counts as open.)

**An appeal page** shows, top to bottom:

1. the title, summary, progress and either "Appeal closes 16 October 2026", "Ongoing appeal" or
   "This appeal closed on …. Thank you to everyone who gave.", beside the photo and its credit;
2. **What your gift can do**: up to four suggested amounts, each with what it pays for
   ("Rs 2,500: a hygiene kit for a family"), and a **Donate to this appeal** button. Shown only
   while the appeal is open and has suggested amounts. The button goes to the Donate page in the
   appeal's language (else the main one) with this appeal preselected;
3. the body.

Editors fill an appeal in on four tabs: Content (summary of at most 300 characters, photo, body),
Fundraising (target, amount raised, start and end dates, suggested amounts), Promote and
Settings. An end date before the start date can't be saved. Previews show the page and the
listing card. Progress is the amount raised as a share of the target, capped at 100%.

The admin's dashboard shows a **fundraising panel**: how many appeals are open, their total raised
of their total target, and those closing within 14 days, so fundraisers see where things stand
as soon as they log in.

## Donate page

The page every Donate button leads to: one per home page, so one per language. Top to bottom: an
introduction, a **payment notice** (how paying works on this site, in a sentence the page writes
itself, then anything the charity adds: [Paying a pledge](#how-paying-works-above-the-form)),
the pledge form, then a body for anything else, such as a table of where the money goes.

- **Links can preselect** an appeal and an amount: `/donate/?appeal=flood-relief&amount=2500`.
  Either can be left out, and an appeal or amount that isn't on offer is ignored.
- **The appeals offered** are the open, public appeals in the page's language, by title, after
  "Wherever it's needed most" (the default).
- **After sending**, the pledge is saved and the browser is redirected (303) to the pledge's
  [pay page](#paying-a-pledge) when a payment provider here takes its currency and amount, and
  otherwise to `/donate/thank-you/`, which shows the page's thank-you text and a link to the
  appeals. Reloading either saves nothing. Previews show the page and the thank-you page.

## The pledge form

Built to be quick on a phone and honest about what it asks (`campaigns/forms.py`, `PledgeForm`,
a form generated from the `Pledge` model, so what each field accepts comes from one place). In
order:

- **How much**: the page's suggested amounts (up to six) as large cards with what each pays for,
  and **Other amount**, which reveals **Your own amount**: a text box with a number keypad that
  accepts "1,00,000" or "2500" (a number input would change the amount when scrolled over).
- **How often**: one-off or monthly. **Monthly** reveals an optional **mobile number**, a country
  and a number, for a monthly reminder on WhatsApp or by text. It's checked and stored as an
  international number, and only numbers that can receive a message are accepted
  ([phonenumbers](../decisions.md#phone-numbers-with-phonenumbers)); a one-off gift never keeps one.
- **Which appeal**, and **a message** for the team (at most 1,000 characters, with a "10/1000
  characters" count that turns amber near the limit).
- **Your details**: name and email; address and postcode, marked "(optional)" in grey.
- **Your choices**: two separate consents, both unticked unless the supporter ticks them:
  emails about the charity's work, and showing their gift on the site. Each tick box sits inside
  its label, so the whole row can be tapped.
- "How we use your details" (the privacy notice), then **Send my pledge**, or **Continue to
  payment** when the pay page comes next.

Fields revealed by a choice are shown and hidden with CSS alone, so the form works without
JavaScript. If something is wrong, a summary at the top lists each problem as a link to its field.

**Sending the same form twice updates one pledge.** Each copy of the form carries a one-time ID;
sending it again, even after going back and changing something, updates that pledge instead of
adding another. Because going back can reload the form with a new ID while the browser refills
what was typed, the Donate page's own script (`donate.js`) remembers the ID it sent and puts it
back. **A pledge someone has started paying is never changed this way:** each attempt to pay is
for the pledge as it was, and a paid pledge records money received, so sending its copy again
starts a new pledge.

## Paying a pledge

**The pay page** (`/donate/pay/<reference>/`) comes straight after the form when a payment
provider set up on this site takes the pledge's currency and amount. Its address is the pledge's
own random reference, so only the person who sent the pledge has it, and it's kept out of search
engines. It shows the gift (amount, how often, appeal; never the giver's name or details), then:

- **Pay online:** a button for each provider set up here, in their order (eSewa, then Khalti). The
  supporter pays on the provider's own page and is sent back here. Khalti's page is a link;
  eSewa's takes a signed form, which the site keeps on the payment and sends from its own page
  (`/donate/payment/<reference>/go/`), reached by a redirect after the button's POST. Back from
  eSewa then reloads a page fetched with GET, never "confirm form resubmission", and once the
  payment is no longer waiting that page goes to the pay page instead of sending the form again.
- **Pay in person:** the office address and phone from Site settings, "tell us your name when you
  pay"; without them, a promise to be in touch. "I'll pay later" goes to the thank-you page.

A monthly pledge pays this month's gift. Later months aren't collected online: eSewa and Khalti
take one-off payments only (monthly reminders are #90).

**Only the provider says whether a payment went through,** asked by the server. When the supporter
comes back (`/donate/payment/<reference>/`), the site asks the provider about that payment by its
own reference and amount. What the browser brings back is never read, because anyone could
change it. Then the pay page shows one of three things:

- **Paid:** thanks ("Your gift of Rs 2,500 has reached us") with the provider's reference.
- **Failed or cancelled:** no money was taken, and the buttons again. When the provider couldn't
  even start the payment, the page says so instead: "We couldn't reach Khalti just now. Try
  eSewa, or try again in a few minutes."
- **Not confirmed yet** (the provider is still deciding, or couldn't be reached): a large button
  to check before paying again, so nobody pays twice. The pay buttons are folded away under "I
  didn't pay: choose a way to pay". Just after a check, the page says once what it found ("We
  asked Khalti just now, and it hasn't confirmed your payment yet", or "We couldn't reach Khalti
  just now"), with "If money has left your account, don't pay again" and the charity's phone. A
  payment whose supporter never came back stays *waiting* until the scheduled check in #198.

Each attempt is a `Payment`: the provider, the amount, our reference (sent to the provider), the
provider's own IDs, and whether it ran in the provider's test system. A pledge's **payment status**
(waiting, paid or failed) and the time it was paid follow from its payments, and only
`Payment.record()` changes them. Paid never goes back. A payment pays its pledge only if it was for
the pledge's amount and currency: a pledge changed after an attempt started (in the admin, say)
stays unpaid until someone looks. Its pay page then says what was received ("We received Rs 2,500
from you by Khalti (reference …). Our team will be in touch.") and offers no way to pay again.

**Which providers are offered** is each installation's own setting: a provider is offered once all
its keys are set ([Running the live site](../hosting.md#paying-pledges-online)), and only for the
currencies it takes, so a UK charity's pledges in pounds get neither eSewa nor Khalti. Payments use
the providers' test systems, where no money moves, until real money is switched on.

**Trying a payment before going live:** in a test system, sign in on the provider's page with its
public test account. The pay page doesn't show these: it pushed the pay buttons down, and
supporters don't need them.

| Provider | Test account |
|---|---|
| eSewa | eSewa ID `9711111111`, password `Nepal@123`, OTP `123456` |
| Khalti | Khalti ID `9800000000`, MPIN `1111`, OTP `987654` |

They're each provider's `test_login` in `nepal_payments/providers/`, from the provider's own
developer docs. The providers
are in `nepal_payments/`, a package that knows nothing of this site; adding one is adding a file
([Extending the site](../contributing/extending.md#add-a-payment-provider)).

### How paying works, above the form

The page writes this itself, in the reader's language, so it's true on every site:
"After you send this form, you can pay with eSewa or Khalti, or in person.", naming the providers
set up there, or, with none, that no payment is taken on the website yet and the charity will be
in touch. The editors' **payment notice** follows it, for anything a charity wants to add, such as
bank details for a transfer. Until #93 every Donate page had a default notice saying no payment was
taken; a migration removed it wherever it hadn't been changed.

## Pledges in the admin

**Pledges** in the admin menu lists every pledge: when it was sent, the name, amount, how often,
the appeal and its **payment** (waiting, paid or failed; **Paid (test)** when a provider's test
system took it, which anyone can do with a public test account, so no money moved). The team can
filter (by how often, appeal, payment, each consent and date), search by name or email, open one
to read it, and export the list to CSV or Excel. The export adds when each pledge was paid and
**paid with** what: the provider and its transaction ID, to match against the provider's
statements, marked "(test)" when it ran in a provider's test system and no money moved. Anything a
supporter typed that a spreadsheet would run as a formula (it starts with `=`) is exported as
text, with a `'` in front in a CSV file
([Security](../contributing/security.md#exports-show-what-visitors-typed-as-text)).

Nobody adds or edits a pledge (they come from supporters), and only a superuser can delete one:
it holds personal details, and a pledge deleted by accident loses the record of a donation. Not
even a superuser can delete a pledge paid with real money, since its payment is the site's only
record of the gift (provider, transaction ID and time); one paid only in a provider's test system
can be deleted, to clear out testing.

## Money

Every amount is a whole number in the currency chosen in Site settings, shown by
`{% money amount %}` with that currency's symbol and grouping: Nepalese rupees by default,
grouped the Nepali way (**Rs 46,87,500**, lakhs and crores), or pounds (**£4,687,500**). A pledge
stores the currency it was sent in. Templates never write a symbol themselves.

## Personal data and consent

Pledges hold names, email addresses, optional home addresses and, for monthly gifts, mobile
numbers; volunteer sign-ups hold whatever their form asks. Editors and moderators can read and
export pledges, and anyone who can edit a form page can read and export its submissions. Give
admin access only to people who may see supporters' details, and don't leave exported files in
shared folders.

Each consent means exactly what its words say, and nothing more:

- **The mobile number** is consent to a monthly reminder on WhatsApp or by text. Use it for
  nothing else.
- **Email updates** (`email_updates`): only email supporters who ticked it, and give every email
  a way to stop (sending is planned under #81).
- **Show my gift on this website** (`show_on_website`): the only consent to list a supporter in
  public, and then only their name, amount, appeal and date, once the gift has arrived (#99).
- **The message** may hold personal details (who a gift is in memory of). It's for the team only
  and is never shown on the site.
- **Payment providers** get nothing about the supporter from the site: only the amount, our
  reference and what the gift is for. The supporter gives the provider their own details on its
  page.

## Privacy notice

Because the forms collect names and contact details, the site links to a privacy notice from the
footer of every page and, as "How we use your details", just before every form's send button.

- The notice is an ordinary page an editor writes and publishes (a standard page, left out of the
  menu), then chooses in **Site settings → Privacy notice**.
- Until a *published* page is chosen there are no links, so a draft never leads to a "page not
  found".
- On a page in the other language, the links go to the notice's translation once it's published,
  and to the main notice until then.
- The demo's notice is example text that describes what the site stores. A charity must replace
  it with its own before going live: only the charity can say who looks after the details, for
  how long and how to ask for them.

The lookup costs one query per page (two on the other language's pages) and happens only when a
template uses it (`core/context_processors.py`).
