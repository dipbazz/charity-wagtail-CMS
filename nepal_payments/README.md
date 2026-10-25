# nepal_payments

Take payments through Nepal's payment gateways from any Python project: Django, Flask, FastAPI
or a plain script. It needs nothing but the standard library.

Each gateway is a **provider**: one class in its own file in `providers/`, which the package finds
by itself. Adding a gateway means adding one file.

> **Status:** built inside [Charity Wagtail CMS](https://github.com/dipbazz/Charity-wagtail-CMS)
> and moving to a repository of its own, published on PyPI (#196). Until then the name and API
> may change.

## Providers

| Code | Gateway | Currencies | Keys | Test system |
|---|---|---|---|---|
| `esewa` | [eSewa ePay v2](https://developer.esewa.com.np/pages/Epay) | NPR | `PRODUCT_CODE`, `SECRET_KEY` | Works with no account: `ESewa.test_keys` are eSewa's published test keys. Pay with eSewa ID 9711111111, password Nepal@123, OTP 123456 |
| `khalti` | [Khalti web checkout (KPG-2)](https://docs.khalti.com/khalti-epayment/) | NPR, from Rs 10 | `SECRET_KEY` | Needs a merchant's own test key from [test-admin.khalti.com](https://test-admin.khalti.com) (sign-in OTP 987654). Pay with Khalti ID 9800000000, MPIN 1111, OTP 987654 |

## How a payment works

Every gateway here sends the payer to its own page and back, so taking a payment is three steps:

1. **Start:** give the provider a `PaymentRequest`. It answers with a `Redirect`, a link to follow
   (`GET`) or a form to post (`POST`) to the gateway's page, and sometimes its own ID for the
   attempt (`provider_id`). Keep that ID with your record of the payment.
2. **Send the payer there.** For a `GET`, redirect. For a `POST`, show a form with the
   redirect's `fields` (it can submit itself with a line of JavaScript, with a button for when it
   can't).
3. **Check:** when the payer comes back to your `return_url`, or later, ask the provider with
   `check()`. **Only `check()` says whether a payment was made.** What the payer's browser brings
   back can be changed by anyone, so it's never used.

```python
from decimal import Decimal

from nepal_payments import PaymentRequest, Status, get_provider

Khalti = get_provider("khalti")
khalti = Khalti(live=False, SECRET_KEY="…")  # live=True takes real money

started = khalti.start(
    PaymentRequest(
        reference="4c1f…",  # your own ID for this attempt, unique: letters, digits, hyphens
        amount=Decimal(2500),  # rupees, not paisa
        currency="NPR",
        return_url="https://example.org/payments/4c1f…/",  # carry your ID in the path
        website_url="https://example.org/",
        description="A gift",
    )
)
# Store started.provider_id, then send the payer to started.redirect.

outcome = khalti.check("4c1f…", Decimal(2500), provider_id=started.provider_id)
if outcome.status is Status.PAID:
    ...  # outcome.provider_reference finds the payment in the gateway's statements
```

`check()` answers `Status.PAID`, `Status.WAITING` (not finished, or the gateway hasn't decided)
or `Status.FAILED` (cancelled, expired or refunded), with the gateway's own word for it
(`outcome.word`, such as `CANCELED`). Each provider's `statuses` lists every word it answers with,
what it means and a sentence for the people who follow payments up:
`ESewa.describe("CANCELED")` is "The payer cancelled at eSewa. Nothing was taken."
`needs_checking` names the words that mean a person must look, such as eSewa's `PARTIAL_REFUND`:
some money was kept, so the payment is neither paid in full nor failed.

When the gateway can't be reached it raises `ProviderUnavailable`: nothing is known, so leave the
payment as it was and ask again later. When it answers with something that can't be read (not
JSON, a word it isn't known to use, an answer about another payment) it raises `UnreadableAnswer`,
a kind of `ProviderUnavailable`, so the two can be told apart. `start()` raises either, or
`ProviderRefused` when the gateway turns the request down (a wrong key, an amount below its
minimum). An error's message can quote the gateway's answer: log it, but don't store it or show
it to anyone.

Every provider can say which payments it takes, so a page can offer only those that apply:
`Khalti.accepts("NPR", Decimal(5))` is `False` (Khalti's minimum is Rs 10).

## Logos

Every provider brings its own logo, so a page can show it on the provider's button and a payer
finds their app at a glance. `ESewa.logo_file()` is its path. The files are in
`static/payment-logos/` (`LOGOS`), a folder holding nothing else, so a web framework can serve it
as it is: in Django, add `LOGOS.parent` to `STATICFILES_DIRS` and the logo is at
`payment-logos/<file>`.

Each is the provider's own, unchanged. Use them only to say a payment can be made with that
provider, never recolour, stretch, crop, outline or add effects to them, and replace a file only
with a newer one from the same source.

| File | Source | Taken |
|---|---|---|
| `esewa.png` | `https://developer.esewa.com.np/assets/img/esewa-logo-dark.png`, the logo on eSewa's developer site (597 × 228, transparent) | 17 Oct 2026 |
| `khalti.svg` | `https://khalti-static.s3.ap-south-1.amazonaws.com/cloudfront-cdn/jamara/web19/images/khalti-logo.svg`, the logo at the top of khalti.com (red, since the merger with IME Pay in 2025) | 17 Oct 2026 |

**eSewa's rules** ([Logomark Guidelines](https://cdn.esewa.com.np/ui/notice/Logo_Guidelines.pdf)):
the full-colour logo on white or a light background (green `#3cc850`, off-black `#111111`, the
inside of the "e" always white), white only on a photo, never all black; clear space of about two
small "e"s around it; never skewed, stretched, rotated, recoloured, outlined, shadowed or
rearranged. In text the name is **eSewa** (**इसेवा** in Nepali), never "Esewa", "e-Sewa" or
"ESEWA".

**Khalti** publishes no logo guide since the merger, so the same care applies: unchanged, on
white, with space around it. Its merchant terms ask merchants to show its logo. The "Khalti by
IME" wordmark linked from khalti.com wasn't available (403) on 17 Oct 2026: take it when Khalti
publishes brand assets.

## Add a provider

1. **Create `providers/<code>.py`** with one `PaymentProvider` subclass:

   ```python
   class IMEPay(PaymentProvider):
       code = "imepay"  # permanent: stored with payments; lowercase letters and digits
       name = "IME Pay"  # the brand, as payers know it
       currencies = frozenset({"NPR"})
       min_amount = Decimal(10)
       keys = ("MERCHANT_CODE", "API_USER", "API_PASSWORD")
       test_login = {}  # an account on its test system anyone may use, if it publishes one
       order = 30  # where it's suggested in a list of providers
       opens_once = False  # True if its page takes the payer only once (eSewa's form)
       statuses = {  # every word its check answers with: what it means, and a sentence
           "SUCCESS": (Status.PAID, "IME Pay says it's paid."),
           "CANCELLED": (Status.FAILED, "The payer cancelled at IME Pay. Nothing was taken."),
       }
       needs_checking = frozenset()  # its words that mean a person must look, if any
       logo = "imepay.svg"  # its own logo, unchanged, in static/payment-logos/ (see Logos)

       def start(self, request): ...  # return Started(Redirect(...), provider_id=...)
       def check(self, reference, amount, provider_id=""): ...  # return Outcome(...)
   ```

   `check()` returns `Outcome(status, provider_reference=…, word=…)` with the gateway's own word,
   and raises `UnreadableAnswer` for a word not in `statuses`. Reach the gateway only through
   `http.request_json` (import the module, `from nepal_payments import http`, and call
   `http.request_json`), so tests can stand in for it. Use `self.config[...]` for the keys and
   `self.live` to choose between its test and live addresses.
2. **Run the tests.** `tests/test_contract.py` checks every provider it finds, yours included:
   - it describes itself;
   - it needs its keys;
   - it sends the payer only to an `https` page;
   - it gives every word in `statuses` a meaning and a sentence, and every word in
     `needs_checking` is one of them and never means paid;
   - it brings its own logo, an SVG or PNG in `static/payment-logos/`;
   - it never says *paid* for an answer it can't read, and raises `UnreadableAnswer` for one;
   - it raises `ProviderUnavailable` when the gateway can't be reached;
   - its test mode never touches the live system.
3. **Write `tests/test_<code>.py`** for the gateway's own API: the request it sends, and each
   status it can answer. The `provider_server` fixture answers in place of the gateway and
   records what was sent.
4. **Add a row to the table above.**

Nothing else changes: no registry to edit, no settings, no migration.

A project can also add a provider of its own without changing this package, with
`register(MyProvider)` (it works as a class decorator).

## Security

- **A payment is paid only when `check()` says so,** asked server to server with your own
  stored reference and amount. Never from the redirect back.
- **Keys stay with the caller.** Providers keep them in memory, never log or show them
  (`repr()` leaves them out), and send them only to their gateway over HTTPS.
- **Redirects aren't followed.** A gateway's API answers where it's asked; a redirect would
  carry the key, and the say on whether a payment is paid, to whatever address it names.
- **A provider sends the payer only to an `https` page** on its gateway.
- **No payer's personal details** are sent to gateways unless a gateway requires them.
