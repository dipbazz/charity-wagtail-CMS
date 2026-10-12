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
| `esewa` | [eSewa ePay v2](https://developer.esewa.com.np/pages/Epay) | NPR | `PRODUCT_CODE`, `SECRET_KEY` | Works with no account: `ESewa.test_keys` are eSewa's published test keys. Pay with eSewa ID 9711111111, password Nepal@123, token 123456 |
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
or `Status.FAILED` (cancelled, expired or refunded). When the gateway can't be reached it raises
`ProviderUnavailable`: nothing is known, so leave the payment as it was and ask again later.
`start()` raises `ProviderUnavailable`, or `ProviderRefused` when the gateway turns the request
down (a wrong key, an amount below its minimum).

Every provider can say which payments it takes, so a page can offer only those that apply:
`Khalti.accepts("NPR", Decimal(5))` is `False` (Khalti's minimum is Rs 10).

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

       def start(self, request): ...  # return Started(Redirect(...), provider_id=...)
       def check(self, reference, amount, provider_id=""): ...  # return Outcome(...)
   ```

   Reach the gateway only through `http.request_json` (import the module, `from nepal_payments
   import http`, and call `http.request_json`), so tests can stand in for it. Use
   `self.config[...]` for the keys and `self.live` to choose between its test and live
   addresses.
2. **Run the tests.** `tests/test_contract.py` checks every provider it finds, yours included:
   - it describes itself;
   - it needs its keys;
   - it sends the payer only to an `https` page;
   - it never says *paid* for an answer it can't read;
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
- **A provider sends the payer only to an `https` page** on its gateway.
- **No payer's personal details** are sent to gateways unless a gateway requires them.
