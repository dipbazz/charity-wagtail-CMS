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
  accepts "1,00,000" or "2500" (a number input would change the amount when scrolled over), up
  to 999,999 (`MAX_AMOUNT`): a bigger gift is arranged with the charity, and an extra zero typed
  by mistake is refused.
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

When Site settings give a **refund policy**, every unpaid pay page shows it under the summary,
headed "Refunds", so a supporter reads it before choosing to pay. With none set, the pages say
nothing about refunds: no site states a policy its charity hasn't.

- **Pay online:** a button for each provider set up here, in their order (eSewa, then Khalti), one
  under another: full width on a phone, then no wider than 24rem. Each shows the provider's own
  logo before "Pay with eSewa" (#201), so a supporter finds their app at a glance. The buttons are
  white with a border in the brand colour and the page's text colour, so the logos sit on the
  white they were drawn for (eSewa's guidelines ask for it) and the text reads on every charity's
  site; every logo has the same 5.25rem × 2rem box, so the words line up. The logo is decorative
  (`alt=""`), so a screen reader hears "Pay with eSewa" once. Logos come with the providers
  (`nepal_payments`, Logos), so a charity sets nothing up. The
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

- **Paid:** thanks ("Your gift of Rs 2,500 has reached us"), then what the gift does ("It pays
  for a hygiene kit for a family.", [Sharing a gift](#sharing-a-gift)), then the provider's
  reference. A monthly gift says "This month's gift … has reached us. We'll be in touch about next
  month.", and a test payment says first "Test payment completed. No money was taken." and nothing
  about what it pays for. Then **Others can help too**, the invitation to share, and a plain link
  to the appeals page, or to the home page on a site without one.
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
  payment whose supporter never came back stays *waiting* until someone on the team presses
  **Check with eSewa now** on the pledge, or the scheduled check in #198 runs.

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
a provider: the return page and the team's check on the pledge (below) use it, and so will the
scheduled one (#198). It also keeps the provider's latest word on the payment (`Payment.word`), so
the list of pledges can say one **needs checking** without reading every step: a provider's
`needs_checking` names its words that mean a person must look, such as eSewa's `PARTIAL_REFUND`.
The pledge's page in the admin shows the history (Pledges in the admin, below).

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
  code shows, each under its name); the code as uploaded with **Save QR code**, a folded "Need help
  saving or scanning the QR code?" (Android, iPhone and computer), "After you scan, your app should
  show *the account name*", and a block headed "Can't scan the QR code? Pay to this account
  instead" with the account name and number (each with a Copy button) and a reminder to use the
  pledge number as the Remarks. From `48rem` the code sits on the left and the rest on the right;
  the source order never changes. It ends with "Paid in your app? Come back to this page, then go
  to step 2" and **Go to step 2**, a GET form that sends the chosen app (`?code=`).
- **Step 2** (`…/qr/paid/`, "Paid? Tell us here"). With two or more codes, "Which app did you pay
  with?", chosen only if step 1 sent one of the codes on the page (`chosen_code()`): a guess could
  send the team to the wrong statement. Then "Give the transaction ID, a screenshot of the
  receipt, or both": the **transaction ID** with two numbered lines before it (open the payment's
  receipt; copy the Transaction ID or Transaction code and paste it here; in Nepali too the ID
  keeps its English name, as the wallets' receipts are in English), and a **Screenshot of the
  receipt** (a JPEG, PNG or WebP image of up to 5 MB). Sending neither says "Enter the transaction
  ID, or add a screenshot of the receipt"; a file that isn't such a picture is refused, and so is
  a screenshot of more than 13 million pixels ("This picture is too large"; a photo from any
  phone camera passes, being decoded straight to a smaller size). Each error
  is under its field (the alert at the top links to each one; a file must be chosen again after a
  mistake), and **I've paid** says "Sending…" while it's sent. Once they've told us, this address
  goes to the checking page (below).

Once the QR code is folded away (Not found, below), the row folds away with it, so opening the
fold shows step 1 as the current step and step 2 as a link, as on a new pledge.

**"I've paid"** (`…/qr/paid/`) moves the pledge from waiting or failed to **To confirm** in one
conditional update (`Pledge.claim_paid()`), and creates the payment only if that changed a row, so
two taps or two tabs make one payment. The payment's method is `qr` and it's always live: it's
real money, so it's never shown as a test and can't be deleted. It keeps the code's name as it was
(`qr_name`), in the site's main language whichever language the supporter read in, so the team
always reads the same name and "by eSewa" survives the code being renamed or removed. The checking
page names the code in the reader's language while it still exists (`Payment.paid_by()`). A pledge that is already
paid, or isn't in rupees, never makes one, and one sent while an online attempt may be paid (Check
your payment, say from a tab opened before it started) goes to the online page instead.

**The pay page's states for QR:**

| State | What it shows |
|---|---|
| To confirm | The **checking page** (`…/checking/`), which every pay address and **Pay with** go to (`HELD`): "Thank you. You've told us you paid Rs 2,500 by eSewa on 15 October …", what they sent ("You sent us the transaction ID …", "… and a screenshot of the receipt", or "You sent us a screenshot of the receipt"), then **Others can help too** ([Sharing a gift](#sharing-a-gift)), "Questions? Call us and give your pledge number, 482 913:" with the charity's phone, "There's nothing more to do here" and a plain link to the appeals (or the home page). The thanks says the gift, so there's no summary, and nothing else can be paid until the team marks it paid or not found: no steps, no QR, no **Pay another way**. Title "Checking your payment". Opened in any other state, it goes to the pay page. A later way the team checks by hand gets this page too |
| Not found | A problem message: "We haven't found your payment yet. If money has left your account, don't pay again", with the phone. The QR and I've paid are folded under "I didn't pay: scan the QR code", and **Pay another way** is open |
| Paid | Thanks, with the reference the team entered, and the invitation to share, on every pay address |
| Received a different amount | "We received Rs 2,000 from you by eSewa.", and the invitation to share |

The choices send a pledge in To confirm to the checking page, and one in Not found to the QR
page (`STATE_ROUTES`).

**The team confirms from the pledge** (Pledges → open one). Each payment is listed with its steps
(the supporter said they paid, marked paid by …). Someone with **Can confirm payments**
(`campaigns.confirm_payment`, given to Moderators; editors still only read pledges) sees two
actions on a QR payment, and only on one: **Mark as paid** takes the date received, the amount
received and the reference from the statement (the supporter's transaction ID to start with), set
once, as the payment becomes paid. The date can't be after today or before the pledge was sent (a
Bikram Sambat year such as 2083 is refused), and the amount can't be more than a pledge can be (999,999). A different amount marks the pledge paid and makes the pay page
say it received that amount. **Not found** fails the payment; it can still be marked paid later
if it turns up. Each adds a step with who did it. eSewa and Khalti payments can't be marked by
hand, and `Payment.ask()` returns nothing for a QR payment, so a scheduled check (#198) never
touches one.

**The receipt screenshot** shows on the payment, linked to full size, only to people with **Can
confirm payments**; editors read "Sent. Only people who can confirm payments can see it." It's
saved afresh at most 2000px on its longest side under a name of the site's own, kept in
`STORAGES["receipts"]` where no address serves it, and deleted when the payment is marked paid or
not found, with its pledge, or after 30 days if nobody has checked it (`delete_old_receipts`; the
payment stays To confirm). It isn't backed up. The rules are in
[Security](../contributing/security.md#a-supporters-upload-is-private-and-short-lived).

### One try too many

Each internet connection may send only so many new pledges, start so many payments, say "I've
paid" so many times and come back from a provider so many times in five minutes
([Security](../contributing/security.md#one-connection-can-only-try-so-often)). A supporter
paying normally, with a retry or two, never gets near it. Over the limit nothing is saved and no
provider is asked, the answer is HTTP 429 with `Retry-After`, and the words never say "blocked"
or "too many", since people share a connection:

- **The pledge form and QR's "I've paid"** come back filled in (only a screenshot must be chosen
  again), with a notice at the top in the neutral box, focused as the page opens: "Your pledge
  hasn't been sent yet. We've had a lot of tries from your internet connection just now. Wait 5
  minutes, then press Continue to payment again. Your answers are still here." (naming the form's
  own button). The QR notice adds "If money has left your account, don't pay again." and the
  charity's phone.
- **Starting a payment, or coming back from one again** (the first time back is always asked),
  shows `campaigns/pay/wait.html`: "Please wait
  5 minutes", the same don't-pay-again line and phone, and **Back to your pledge**, to the pay
  page, which is never limited and opens on what became of paying.

The wait it names is the window from settings, in whole minutes rounded up. There's no countdown
and nothing retries by itself.

### How paying works, above the form

The page writes this itself, in the reader's language, from the same `ways_to_pay()` as the pay
page, so it's true on every site: "After you send this form, you can pay with eSewa or Khalti, or
in person.", naming the providers set up there, and "or in person" only when paying in person is
offered; "you can pay with eSewa or Khalti, by scanning our QR code or in person." when the
charity has QR codes; "you can pay in person." with no provider; or, with no way to pay, that no payment is
taken on the website yet and the charity will be in touch. The editors' **payment notice** follows it, for anything a charity wants to add, such as
bank details for a transfer. Until #93 every Donate page had a default notice saying no payment was
taken; a migration removed it wherever it hadn't been changed.

## Sharing a gift

Supporters sharing their own gift is how a charity reaches new people: friends see someone they
know give, and give too (#100). So once a supporter has told us they've paid, the thanks (and the
checking page, while the team checks a QR payment) end with **Others can help too**
(`pay/includes/share.html`). A pledge that's waiting, failed or not found offers nothing: it isn't a
gift yet. One rule decides what's shown and shared, `campaigns/sharing.py`, which the recent
supporters list (#99) will use too.

**What the thanks say the gift does** comes from what editors already wrote, so there's nothing new
to fill in: the appeal's suggested amount that matches what was received ("It pays for a hygiene kit
for a family.", the editor's words starting lower case unless the first word is in capitals), else
the appeal's summary. For wherever it's needed most, the Donate page's matching amount, else "It
helps wherever the need is greatest." A test payment says nothing of it: no money moved.

**Others can help too** is an invitation, not showing off. In order:

- One sentence about the cause: "Clean water for Kisumu still needs support. If you tell your
  friends, their gifts can help as well."; once the appeal has reached its target, "… has reached
  its target. Your friends can still help: every gift goes further."; for wherever it's needed most
  or a closed appeal, "Our work still needs support. …".
- The pledge form's own consent, **Show my gift on this website**, with the same help text, ticked
  if they agreed on the form, and **Save** (outlined). Saving (`…/show-gift/`) reloads the page at
  the section, moves focus to its heading and says "Your page for friends is ready" (or "… has been
  taken down"). It's refused, changing nothing, before they've told us they've paid and while the
  team has taken the page down; the box is then replaced by "Our team has taken your page down. If
  you'd like it back, call us:" and the charity's phone. When they ticked or unticked it, on the
  form or here, is kept (`show_on_website_changed_at`). A pledge ticked before gift pages has no
  time kept: it agreed to "Once your gift reaches us", so nothing is shown while a QR payment is
  checked and the box starts unticked there; ticking it agrees in today's words.
- **Tell your friends**: the phone's own share sheet (Web Share), so WhatsApp, Viber, Messenger and
  Instagram are all there. It's shown only where the browser has one (most phones, few desktops).
- **WhatsApp**, **Facebook** and **Copy link**, a row of text links at least 44px tall, which work
  without the share sheet; Copy link needs JavaScript, and says "Copied" or, if the browser won't
  copy, gives the link to copy by hand. Links open in the same tab. No third-party scripts.

**What's shared:** with consent, the gift's page (below); without it, or once it's down, the appeal,
or the Donate page for wherever it's needed most (a private or unpublished appeal counts as that),
with no name. Never the pay page: its address pays the pledge. The message names the appeal and the
charity and never the amount: "I've just given to Clean water for Kisumu with Brightwell. They still
need help. If you can, you could give too:", without "They still need help." once the target is
reached or the appeal has closed.

**The gift's page** (`/donate/gifts/<code>/`) is under the Donate page the pledge was sent from, at
the pledge's **gift code**: 72 random bits, never the reference and never a number to count up from.
It reads in each language under that page's translation (`/ne/donate/gifts/<code>/`), with the
appeal's translation, and the language switcher and `hreflang` links keep the gift.
It's laid out like an appeal: "Asha is supporting Clean water for Kisumu" (or "… is supporting
Brightwell"), "Gave Rs 1,500 on 18 October 2026" ("Gives Rs 500 a month"), the appeal's summary,
progress and photo, **Give to this appeal** (the Donate page with the appeal chosen) and "Read about
this appeal". It's kept out of search (`noindex`) and has its own link preview: base.html's
`social_meta` block, which the page fills with its own address, title, the summary and the appeal's
social image (else the Donate page's). It shows nothing else about the supporter.

| State | Thanks or checking page | The gift's page |
|---|---|---|
| Paid, appeal open | As above | As above |
| Appeal closed | No change | "This appeal closed on …", **Give where it's needed most**, and "See our open appeals" when any are open: a friend always has a way to give |
| No appeal, or a private or unpublished one | Wherever it's needed most | "… is supporting Brightwell", **Give** |
| Test payment | As usual | "Test gift: no money was taken" first |
| QR payment being checked | The share section on the checking page | The name, no amount: "Paid by QR on 18 October 2026. Our team is checking it." |
| Received a different amount | As usual | The amount received |
| QR not found; waiting, failed or not confirmed | Nothing to share | Goes to the appeal |
| Consent withdrawn, or taken down by the team | Box unticked, or the note to call | Goes to the appeal, as shares do |

A gift's page that isn't shown goes (302, as it may be shown again) to the appeal, or the Donate
page for wherever it's needed most: a friend with a link shared before can still give, and sees no
name. An unknown code is page not found.

**Accepted risk:** while a QR payment is being checked, the name typed on the form is public, so
until spam protection (#104) someone could put any name on a page under the charity's name. The
team's **Stop showing on the website** (below) takes it down at once.

## Pledges in the admin

**Pledges** in the admin menu lists every pledge: when it was sent, the name, amount, how often,
the appeal and its **payment** (waiting, **to confirm** for a QR payment the supporter says they
made, paid or failed; **Paid (test)** when a provider's test
system took it, which anyone can do with a public test account, so no money moved; **Needs
checking** when a person must look: money received for an amount the pledge doesn't ask for, or a
provider saying it refunded part of a payment, `Pledge.needs_checking()`). The list, the export
and the pledge's page say the same. The team can
filter (by how often, appeal, payment, each consent and date), open one
to read it, and export the list to CSV or Excel. **Search** finds a pledge by name, email or
mobile number, and by anything on a line of a provider's or bank's statement: a payment's
reference (with or without its hyphens), the provider's ID for it, its transaction ID or the one
the supporter gave. Each pledge has a six-digit **pledge number**
(shown "482 913"), picked at random when it's saved, which the supporter gives when paying in person
and the team can search for with or without its space. It's never a way in: the pay page stays at
the pledge's reference. The list and the export show it. The export adds when each pledge was paid and
**paid with** what: the provider and its transaction ID, to match against the provider's
statements, marked "(test)" when it ran in a provider's test system and no money moved. Anything a
supporter typed that a spreadsheet would run as a formula (it starts with `=`) is exported as
text, with a `'` in front in a CSV file
([Security](../contributing/security.md#exports-show-what-visitors-typed-as-text)).

**A pledge's page** (`PledgeInspectView`, `campaigns/admin/pledge_inspect.html`) leads with what
the team acts on, in Wagtail's own panels and status tags so it looks like the rest of the admin:

- **At the top:** the amount, how often and the appeal ("Wherever it's needed most" for none),
  when it was sent and its pledge number, then its payment status with one sentence on how or why
  not: "Paid with eSewa on 14 Oct 2026, 3:42 p.m., transaction 000AWEO" (adding "Made in eSewa's
  test system: no money moved." for a test), what the supporter sent for one to confirm, when an
  unfinished payment started, the provider's sentence for a failed one ("The payer cancelled at
  eSewa. Nothing was taken."), "Not paid online yet.", or why it needs checking.
- **Contact:** email and mobile number as `mailto:` and `tel:` links, the address and postcode;
  an empty one isn't shown.
- **Message and consents:** the supporter's message, marked as a quote, then each consent on its
  own line with a tick or a cross after "Email updates: Yes" or "Show on website: No". The tick
  and cross are in the text colour, not green and red: "No" is the supporter's choice, not an
  error. With "Show on website: Yes", a link to **Their page for friends** while it's up, and
  **Stop showing on the website** (below).
- **Payments**, newest first, with the site's time zone named once ("Times are Asia/Kathmandu
  time (UTC+5:45)"), as a timeline: a line down the left with each payment a circle on it,
  holding Wagtail's arrow, and its details under the line beside it. The paid one, or else the
  latest, is open; every other one is a line that opens on tap. Each shows when it started; for a provider's, whether it was live or in the test
  system, our reference, the provider's ID and its transaction ID; for a QR payment, the code, the
  supporter's transaction ID and screenshot, and the reference from the statement. Then **What
  happened**, its steps in order with seconds, each in plain words ("Sent to eSewa.", "Came back
  to the site.", the provider's sentence for its answer) with the provider's own word and who did
  it beneath. A payment from before steps were recorded says "Steps weren't recorded for payments
  started before version 0.5.0", with when it was last updated.

Left out, as nobody acts on them: the internal ID, the Donate page, the submission ID and the pay
page's address, which would let whoever reads it pay the pledge. The page fetches the pledge, its
payments, their steps and who did them in a fixed number of queries, however many there are.

**Check with eSewa now** (or Khalti, or any provider) shows under a payment that's waiting, or
failed after reaching the provider (it may still turn out paid), when the provider is set up for
the system the payment was made in. Anyone who can read pledges can press it: it asks the provider
through `Payment.ask()`, just as the pay page does, adds the answer as a step with their name, and
says what the provider answered. It never marks a payment by hand, and it's refused within 30
seconds of the last time anyone asked about that payment, as each ask can wait up to 10 seconds for
the provider ([Security](../contributing/security.md#a-payment-is-paid-only-when-its-provider-says-so)).

**Stop showing on the website** takes a gift's page for friends down at once, for a made-up name,
say ([Sharing a gift](#sharing-a-gift)). Editors and moderators can press it (**Can stop showing a
gift on the website**, `campaigns/migrations/0017_gift_sharing.py`), after a page that asks first.
It sticks: the supporter's box is replaced by a note to call, and only the team's **Show again**
puts it back, if the supporter still agrees. Both are logged in the pledge's history, which opens
for anyone who can read pledges (`PledgeHistoryView`), and the pledge's page links to it as "Who
took it down, and when".

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
- **Show my gift on this website** (`show_on_website`): the only consent to show a supporter in
  public, on their gift's page for friends (#100) and in the recent supporters list (#99), in its
  own words: "Once you've told us you've paid, we'll show your name, the appeal and the date on a
  page you can share, and in our list of recent supporters; the amount once your gift reaches us.
  Nothing else about you is shown." `campaigns/sharing.py` holds that rule, and the team can take
  a gift down whatever was ticked.
- **The message** may hold personal details (who a gift is in memory of). It's for the team only
  and is never shown on the site.
- **Payment providers** get nothing about the supporter from the site: only the amount, our
  reference and what the gift is for. The supporter gives the provider their own details on its
  page.
- **A receipt screenshot** can show the supporter's name, account and balance. Only people who
  can confirm payments see it, and it's kept until the payment is checked, 30 days at most.

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
