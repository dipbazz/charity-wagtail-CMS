# Onboarding a charity

What we ask a new charity for, and how they send it, comes from one place: the pack in
[`onboarding/`](https://github.com/dipbazz/Charity-wagtail-CMS/tree/main/onboarding). Each charity
gets its own copy in Google Drive, made from the pack, and is sent **two links**: its guide and its
form. Both links stay the same while the pack changes underneath them, so a charity never holds an
old copy, and we never send a guide or form as a file.

## What's in the pack

| File | What it is |
|---|---|
| `guide.md` | The guide the charity reads: the plan, how its site is arranged (the [charity site standard](../site/standard.md)), and what to send |
| `questions.csv` | One row per question in the form, in the order the form asks them; rows with `In form` set to `No` are our own steps, tracked but not asked |
| `form-script.gs` | The Apps Script bound to each charity's tracker Sheet: it updates the tracker and guide from the pack and builds the form |
| `tests/` | Tests for `form-script.gs` (never uploaded; see [Changing the script](#changing-the-script)) |

The guide and questions use placeholders, filled in for each charity when they are uploaded:
`{name_ne}`, `{name_en}`, `{domain}`, `{version}` (the release the pack comes from) and `{demo_url}`
(the demo site in the README). Any other text in braces fails the tests, so don't use braces
in the pack.

In `questions.csv`, **Answer type** is `short`, `long`, `choice`, `checkboxes`, `photo` or `upload`;
**Options** holds a choice's options separated by `|` (a last option `Other` lets the charity write
their own), or for an upload the number of files and, after a `;`, what kind (`5; PDF or photos`).
Questions and form sections are written "English / नेपाली". A question's **ID** must never be
reused for a different question: the tracker matches rows by ID and keeps their answers.

## Where each charity's copy lives

In the charity Google account, in `Charities/<domain>/`:

- `<NAME> content tracker`: the Sheet, with the script bound to it (Extensions > Apps Script), and
  the Drive API turned on under Services. Its tabs are Requirements, Responses and Form links.
- `<NAME> website guide`: the guide, a Google Doc.
- `<NAME> website content`: the form, built by the script.
- `guide.md` and `questions.csv`: the last pack uploaded.

`<NAME>` is the Sheet's name without "content tracker", for example `CCDCE`.

## Starting a new charity

1. Create a new Sheet in `Charities/<domain>/` named `<NAME> content tracker`, with this header
   row and nothing else: `ID, Step, Section, Question, Help, Answer type, Options, In form, Owner,
   Notes, Status, Answers, Last answer, Date asked, Form item ID`. Paste `form-script.gs` into
   Extensions > Apps Script, add the Drive API under Services, save and reload the Sheet. Don't
   copy another charity's tracker: the copy brings that charity's form and responses with it. (If
   one is copied by mistake, the script still builds a new form rather than editing the other
   charity's.)
2. Fill in the placeholders in `guide.md` and `questions.csv` and upload both to the folder.
3. In the Sheet, run **Website form > Update from the pack**. It creates the guide, fills
   Requirements and builds the form. Add the upload questions it lists by hand in the form
   editor (the script can't create them), then run **Build or update the form**.
4. Send the charity the two links from the **Form links** tab, then run **Mark form questions as
   asked today**.

## Updating a charity's guide and form

A pull request that changes what a charity must send or decide (the standard, a page's fields, a
setting a charity fills in) updates the pack in the same pull request. When a version is released,
for each charity still sending content:

1. Upload the new `guide.md` and `questions.csv` (placeholders filled) to its folder.
2. Run **Update from the pack**. It rewrites the guide under the same link, merges the questions
   by ID and rebuilds the form. Answers already received are kept; a question taken out of the
   pack leaves the form but stays in the tracker if it was answered. Add any upload questions it
   lists.
3. Tell the charity what changed in one line. The links they have already show the new version.

## Changing the script

`form-script.gs` runs inside Google Sheets, so its tests are JavaScript, run by Node:
`onboarding/tests/form-script.test.js` runs the script against fake Apps Script services
(`onboarding/tests/fakes.js`), in its own CI step. Run them with
`node --test onboarding/tests/form-script.test.js`. When a real service refuses something the
fakes allowed, teach the fakes that rule first, so the test fails the way the Sheet did, then fix
the script. Try a change once by hand on a copy of a tracker before anyone pastes it into a
charity's Sheet. Apps Script can't create upload questions, and a
Sheets table refuses some formatting, so the script skips those steps rather than failing.
