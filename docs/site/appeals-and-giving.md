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
  [pay page](#paying-a-pledge) when there's a way to pay it here (straight to that way's page when
  there's only one), and otherwise to `/donate/thank-you/`, which shows the page's **thank-you
  text** and a link to the appeals. So the thank-you text only shows on a site with no way to pay
  yet, and its help text says so. Reloading any of them saves nothing. Previews show the page and
  the thank-you page.

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
  payment** when there's a way to pay on the site.

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

**The pay page** (`/donate/pay/<reference>/`) comes straight after the form, and asks "How would
you like to pay?". Its address is the pledge's own random reference, so only the person who sent
the pledge has it. Each way to pay has its own page under it, so the supporter chooses first and
then reads only about the way they chose:

| Way | Page | Offered when |
|---|---|---|
| **Pay online** | `…/online/` | a provider set up here takes the pledge's currency and amount |
| **Scan our QR code** | `…/qr/` | the charity has added a QR code (QR codes in the admin menu) and the pledge is in rupees |
| **Pay in person** | `…/in-person/` | Site settings tick **We take gifts at our office** and give an office address or phone |
| **Not ready to pay yet?** | `…/later/` | always (it isn't a way to pay, so it never counts as one) |

`ways_to_pay()` (`campaigns/payments.py`) decides which ways are offered, for the pay page, the
form's redirect and the sentence above the form, so they can't disagree. It's given the providers
that take the pledge, the same list the pay buttons come from, and the charity's QR codes
(`DonatePage.qr_codes_for()`, none for a pledge that isn't in rupees). With only one way, the
form and the pay page go straight to its page, which then says "Your pledge is saved."; with
none, the form goes to the thank-you page. A way that isn't offered goes back to the choices,
unless it's dealing with the pledge: the online page still shows a payment that may have gone
through after the provider's keys were removed, without buttons to pay again.

Every page (the choices and each way's) shows the same summary first: the gift (amount, how
often, appeal; never the giver's name or details) and the **pledge number** ("482 913"), then
its own content. Each has its own title, is kept out of search engines, and ends with **Pay
another way**: a row for each other way, then Not ready to pay yet (folded away while an online
payment may be paid, below). The phone's Back button goes
back to the choices. Once the pledge is paid, every address says thank you, so a page left open
or a link kept to pay later never offers paying again.

- **Pay online:** a button for each provider set up here, in their order (eSewa, then Khalti). The
  supporter pays on the provider's own page and is sent back here. Khalti's page is a link;
  eSewa's takes a signed form, which the site keeps on the payment and sends from its own page
  (`/donate/payment/<reference>/go/`), reached by a redirect after the button's POST. Back from
  eSewa then reloads a page fetched with GET, never "confirm form resubmission". Once the
  payment is no longer waiting, or any attempt has paid the pledge (say with Khalti, after
  backing out of eSewa), that page goes to the pay page instead of sending the form again.
  Pressing the same provider's button again within 10 minutes (a second tap, a second tab, or no
  JavaScript to hold the button) goes back to the attempt just started, its form or its link,
  rather than starting another that could also be paid. After that, or with another provider, a
  new attempt starts. So too once eSewa's form has been shown: eSewa takes each form only once
  and refuses it again as a "Duplicate transaction UUID" (#213), so its "Taking you to eSewa"
  page, reached again with Back, goes to the pay page, where the payment can be checked. A
  provider says this with `opens_once`. The buttons post to `…/online/<provider>/`, so no
  provider's code can clash with a way's name.
- **Scan our QR code:** see [Paying by QR code](#paying-by-qr-code) below.
- **Pay in person:** what to do at the counter, as numbered steps: come to the office (the
  address from Site settings, with "Call us before you come" and the phone), pay in cash and give
  the pledge number, and ask for a receipt. The setting is off until a charity says on the
onboarding form (DO01) that it takes gifts at its office: many show their office in the footer
but take no money there. With a phone but no address, the first step is "Call
  us to arrange paying". It then says "This page won't change after you pay: your receipt is your
  record" and "There's nothing more to do here", with a link to the appeals. It promises nothing
  the site can't do: recording a cash payment in the admin is #209.
- **Not ready to pay yet?:** the pay page's link, with a **Copy link** button (shown only with
  JavaScript; without it the link can be selected), to come back and pay later. The monthly
  reminder choice joins it in #199.

A monthly pledge pays this month's gift. Later months aren't collected online: eSewa and Khalti
take one-off payments only (monthly reminders are #90).

**Only the provider says whether a payment went through,** asked by the server. When the supporter
comes back (`/donate/payment/<reference>/`), the site asks the provider about that payment by its
own reference and amount. What the browser brings back is never read, because anyone could
change it. Then the **online page** shows one of three things (the choices send a pledge in one of
the last two straight there, where the check is):

- **Paid:** thanks ("Your gift of Rs 2,500 has reached us") with the provider's reference. A
  monthly gift says "This month's gift … has reached us. We'll be in touch about next month.",
  and a test payment says first "Test payment completed. No money was taken." It leads to the
  appeals page, or to the home page on a site without one.
- **Failed or cancelled:** "eSewa says your payment didn't go through.", with "If money has left
  your account, don't pay again", the charity's phone, a **Check my eSewa payment** button and the
  pay buttons again. It doesn't say no money was taken: eSewa can say "not found" before it says
  "complete", and checking again records it as paid then (checking again with no change says
  so once). Only when the provider couldn't even start the payment is no money known to be
  taken: the page says "We couldn't reach Khalti just now. Try eSewa, or try again in a few
  minutes.", and afterwards "Your payment didn't go through, and no money was taken."
- **Not confirmed yet** (the provider is still deciding, or couldn't be reached): a large button
  to check before paying again, so nobody pays twice. The pay buttons and **Pay another way** are
  folded away under "I didn't pay: choose a way to pay", and every other way's page (`in-person/`,
  `later/`) goes to the online page. Just after a check, the page says once what it found ("We
  asked Khalti just now, and it hasn't confirmed your payment yet", or "We couldn't reach Khalti
  just now"), with "If money has left your account, don't pay again" and the charity's phone. A
  payment whose supporter never came back stays *waiting* until the scheduled check in #198.

Each attempt is a `Payment`: the provider, the amount, our reference (sent to the provider), the
provider's own IDs, and whether it ran in the provider's test system. A pledge's **payment status**
(waiting, paid or failed) and the time it was paid follow from its payments, and only
`Payment.record()` changes them. Paid never goes back. A failed attempt marks the pledge failed
only when none of its other attempts is waiting or paid, so the newer one can still be checked.
A payment pays its pledge only if it was for
the pledge's amount and currency: a pledge changed after an attempt started stays unpaid until
someone looks. (The admin no longer lets that happen: see Pledges below. This is a safety net.) Its pay page then says what was received ("We received Rs 2,500
from you by Khalti (reference …). Our team will be in touch.") and offers no way to pay again.

**Each payment keeps a history of what happened to it** (`PaymentStep`), so the team can answer
"did my payment go through?" without the provider's portal: sent to the provider (or why it
couldn't start), came back to the site, and each time the site asked the provider, with its
answer or why there wasn't one (couldn't reach it, answer not understood, refused, couldn't ask).
An answer keeps the provider's own word, such as eSewa's `CANCELED`; each provider's `statuses`
give that word a sentence for the team ("The payer cancelled at eSewa. Nothing was taken.").
Every check adds a step, even with the same answer. `Payment.ask()` is the one place the site asks
a provider: the return page uses it, and so will the team's check and the scheduled one (#198).
The admin shows the history from #96's second part.

**Which providers are offered** is each installation's own setting: a provider is offered once all
its keys are set ([Running the live site](../hosting.md#paying-pledges-online)), and only for the
currencies it takes, so a UK charity's pledges in pounds get neither eSewa nor Khalti. Payments use
the providers' test systems, where no money moves, until real money is switched on. Until then the
pay page adds one sentence after "You'll pay on the secure page of …": "Online payments are in
test mode here: no money will be taken.", so a real supporter who finds the site before it goes
live isn't misled.

**Trying a payment before going live:** in a test system, sign in on the provider's page with its
public test account. The pay page doesn't show these: they pushed the pay buttons down, and
supporters don't need them.

| Provider | Test account |
|---|---|
| eSewa | eSewa ID `9711111111`, password `Nepal@123`, OTP `123456` |
| Khalti | Khalti ID `9800000000`, MPIN `1111`, OTP `987654` |

They're each provider's `test_login` in `nepal_payments/providers/`, from the provider's own
developer docs. The providers
are in `nepal_payments/`, a package that knows nothing of this site; adding one is adding a file
([Extending the site](../contributing/extending.md#add-a-payment-provider)).

### Paying by QR code

Many small charities have only a QR code from their bank or a wallet, not an eSewa or Khalti
merchant account, and it's how most people in Nepal pay. A charity's own (static) QR code carries
no reference the site could look up, so **the site can't check it**: the team does, by hand.

**The QR codes** are listed under **QR codes** in the admin menu, like pledges or partners: the
table, an Add button when there are none, and each row opens its edit page. Each has a name in
each language ("Fonepay (bank)"; a blank translation shows the main language's), an image, the
**account name** exactly as the app shows it after scanning, and an optional account or wallet
number for people who can't scan. Drag a row to put a code first. Only **Moderators** can add,
change or remove them (`campaigns/migrations/0014_qr_payments.py`): an editor who
could change one would send gifts to another account. For the same reason the image is stored on
the code, not in the image library, where an editor could replace it. It's re-saved on upload
(`core/images.clean_image()`), in its own format, as one file of at most 1600px (to save and scan)
and one of at most 800px (shown, through `srcset`), without location data and refusing anything
that isn't a JPEG, PNG or WebP of up to 5 MB; both files go when the code is replaced or removed.
Wagtail's history for each code says who added, changed or removed it, and when.

**Paying by QR is two pages, one per step**, both headed "Scan our QR code" with a row of the two
steps under the heading ("Scan the QR code", "Paid? Tell us"): the step you're on has a filled
circle and `aria-current="step"`, the other is a link to its page.

- **Step 1** (`…/qr/`, "Pay with your app"). The gift summary, which here (and only here,
  `summary.html` with `copyable`) says "Your gift amount" and "Pledge number (use this as
  Remarks)", each with an icon Copy button that copies the plain value ("2500", "482913") and
  appears only with JavaScript. Then how it's checked ("We check QR payments by hand: your gift
  shows as received once it reaches us"); with two or more codes, "Which app will you pay with?" as
  radio cards (the first chosen) that show one code at a time with CSS `:has()` (without it every
  code shows, each under its name); the code as uploaded with **Save image**, a folded "Need help
  saving or scanning the image?" (Android, iPhone and computer), "After you scan, your app should
  show *the account name*", and a block headed "Can't scan the QR code? Pay to this account
  instead" with the account name and number (each with a Copy button) and a reminder to use the
  pledge number as the Remarks. From `48rem` the code sits on the left and the rest on the right;
  the source order never changes. It ends with "Paid in your app? Come back to this page, then go
  to step 2" and **Go to step 2**, a GET form that sends the chosen app (`?code=`).
- **Step 2** (`…/qr/paid/`, "Paid? Tell us here"). With two or more codes, "Which app did you pay
  with?", chosen only if step 1 sent one of the codes on the page (`chosen_code()`): a guess could
  send the team to the wrong statement. Then the **transaction ID** with two numbered lines before
  it (open the payment's receipt; copy the ID and paste it here), each error under its field (the
  alert at the top links to each one), and **I've paid**, which says "Sending…" while it's sent.
  Once they've told us, this address goes back to step 1, which says thank you. Receipt
  screenshots come with #197's second part.

Once they've said they paid, the row ticks step 2 and stops being links, because step 1 is folded
away (see the states below). Not found ticks nothing.

**"I've paid"** (`…/qr/paid/`) moves the pledge from waiting or failed to **To confirm** in one
conditional update (`Pledge.claim_paid()`), and creates the payment only if that changed a row, so
two taps or two tabs make one payment. The payment's method is `qr` and it's always live: it's
real money, so it's never shown as a test and can't be deleted. It keeps the code's name as it was
(`qr_name`), so "by eSewa" survives the code being renamed or removed. A pledge that is already
paid, or isn't in rupees, never makes one.

**The pay page's states for QR:**

| State | What the QR page shows |
|---|---|
| To confirm | "Thank you. You've told us you paid Rs 2,500 by eSewa on 15 October …", what they sent, the charity's phone, "There's nothing more to do here" and the appeals link. The QR and I've paid are folded under "I didn't pay: scan the QR code"; the online page folds its buttons too. **Pay another way** stays open. Title "Checking your payment" |
| Not found | A problem message: "We haven't found your payment yet. If money has left your account, don't pay again", with the phone. The QR and I've paid are folded the same way |
| Paid | Thanks, with the reference the team entered, on every pay address |
| Received a different amount | "We received Rs 2,000 from you by eSewa." |

The choices send a pledge in To confirm or Not found to the QR page (`STATE_WAYS`).

**The team confirms from the pledge** (Pledges → open one). Each payment is listed with its steps
(the supporter said they paid, marked paid by …). Someone with **Can confirm payments**
(`campaigns.confirm_payment`, given to Moderators; editors still only read pledges) sees two
actions on a QR payment, and only on one: **Mark as paid** takes the date received, the amount
received and the reference from the statement (the supporter's transaction ID to start with), set
once, as the payment becomes paid. A different amount marks the pledge paid and makes the pay page
say it received that amount. **Not found** fails the payment; it can still be marked paid later
if it turns up. Each adds a step with who did it. eSewa and Khalti payments can't be marked by
hand, and `Payment.ask()` returns nothing for a QR payment, so a scheduled check (#198) never
touches one.

### How paying works, above the form

The page writes this itself, in the reader's language, from the same `ways_to_pay()` as the pay
page, so it's true on every site: "After you send this form, you can pay with eSewa or Khalti, or
in person.", naming the providers set up there, and "or in person" only when paying in person is
offered; "you can pay with eSewa or Khalti, by scanning our QR code or in person." when the
charity has QR codes; "you can pay in person." with no provider; or, with no way to pay, that no payment is
taken on the website yet and the charity will be in touch. The editors' **payment notice** follows it, for anything a charity wants to add, such as
bank details for a transfer. Until #93 every Donate page had a default notice saying no payment was
taken; a migration removed it wherever it hadn't been changed.

## Pledges in the admin

**Pledges** in the admin menu lists every pledge: when it was sent, the name, amount, how often,
the appeal and its **payment** (waiting, **to confirm** for a QR payment the supporter says they
made, paid or failed; **Paid (test)** when a provider's test
system took it, which anyone can do with a public test account, so no money moved). The team can
filter (by how often, appeal, payment, each consent and date), search by name or email, open one
to read it, and export the list to CSV or Excel. Each pledge has a six-digit **pledge number**
(shown "482 913"), picked at random when it's saved, which the supporter gives when paying in person
and the team can search for with or without its space. It's never a way in: the pay page stays at
the pledge's reference. The list and the export show it. The export adds when each pledge was paid and
**paid with** what: the provider and its transaction ID, to match against the provider's
statements, marked "(test)" when it ran in a provider's test system and no money moved. Anything a
supporter typed that a spreadsheet would run as a formula (it starts with `=`) is exported as
text, with a `'` in front in a CSV file
([Security](../contributing/security.md#exports-show-what-visitors-typed-as-text)).

Nobody adds or edits a pledge (they come from supporters), and only a superuser can delete one:
it holds personal details, and a pledge deleted by accident loses the record of a donation. Not
even a superuser can delete a pledge paid with real money, since its payment is the site's only
record of the gift (provider, transaction ID and time); one paid only in a provider's test system
can be deleted, to clear out testing. A superuser can correct a pledge (a mistyped email, say),
but once someone has started paying it its amount and currency can't be changed: the payment
was for them, and a changed amount still marked paid would disagree with the provider's
statement.

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
