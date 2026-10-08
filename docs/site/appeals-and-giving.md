# Appeals and giving

How the charity raises money on the site: appeals, the Donate page, pledges and the team's view
of them. **No payment is taken yet.** A supporter sends a *pledge* (a promise), and the team gets
in touch to arrange payment; taking payments online is planned (#92). So appeal totals are typed
in by editors, not counted from pledges.

Code: `campaigns/` (models, `forms.py` for the pledge form, `views.py` for the admin's Pledges,
`wagtail_hooks.py` for the dashboard panel), `core/money.py`, `core/phone.py`. How often a supporter
gives is the `Frequency` choices in `campaigns/models.py`, shared by the model, the form and anything
that acts on pledges: compare with `Frequency.MONTHLY`, never the string.

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
introduction, a **payment notice** (how paying works and what happens next; it has a default),
the pledge form, then a body for anything else, such as a table of where the money goes.

- **Links can preselect** an appeal and an amount: `/donate/?appeal=flood-relief&amount=2500`.
  Either can be left out, and an appeal or amount that isn't on offer is ignored.
- **The appeals offered** are the open, public appeals in the page's language, by title, after
  "Wherever it's needed most" (the default).
- **After sending**, the pledge is saved and the browser is redirected (303) to
  `/donate/thank-you/`, which shows the page's thank-you text and a link to the appeals. Reloading
  the thank-you page saves nothing. Previews show the page and the thank-you page.

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
- "How we use your details" (the privacy notice), then **Send my pledge**.

Fields revealed by a choice are shown and hidden with CSS alone, so the form works without
JavaScript. If something is wrong, a summary at the top lists each problem as a link to its field.

**Sending the same form twice updates one pledge.** Each copy of the form carries a one-time ID;
sending it again, even after going back and changing something, updates that pledge instead of
adding another. Because going back can reload the form with a new ID while the browser refills
what was typed, the Donate page's own script (`donate.js`) remembers the ID it sent and puts it
back.

## Pledges in the admin

**Pledges** in the admin menu lists every pledge: when it was sent, the name, amount, how often
and the appeal. The team can filter (by how often, appeal, each consent and date), search by name
or email, open one to read it, and export the list to CSV or Excel.

Nobody adds or edits a pledge (they come from supporters), and only a superuser can delete one:
it holds personal details, and a pledge deleted by accident loses the record of a donation.

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
