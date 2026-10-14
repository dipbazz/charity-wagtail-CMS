"""Khalti's web checkout (KPG-2): the server asks Khalti to start a payment, the payer pays on
Khalti's page, and Khalti's lookup says whether they paid.

https://docs.khalti.com/khalti-epayment/
"""

import logging
from decimal import Decimal
from urllib.parse import urlsplit

from nepal_payments import http
from nepal_payments.base import (
    Outcome,
    PaymentProvider,
    ProviderRefused,
    Redirect,
    Started,
    Status,
    UnreadableAnswer,
)

logger = logging.getLogger(__name__)

API_URL = {False: "https://dev.khalti.com/api/v2/", True: "https://khalti.com/api/v2/"}
# The only pages the payer is sent to. An initiate answer naming any other is refused.
PAYMENT_PAGE_HOST = {False: "test-pay.khalti.com", True: "pay.khalti.com"}
STATUSES = {
    "Completed": (Status.PAID, "Khalti says it's paid."),
    "Pending": (Status.WAITING, "Khalti hasn't finished the payment yet."),
    "Initiated": (Status.WAITING, "The payer hasn't paid on Khalti's page yet."),
    # Some of the money was kept, so it's neither paid in full nor failed: a person must look.
    "Partially Refunded": (
        Status.WAITING,
        "Khalti refunded part of it. Check what was kept in Khalti's merchant dashboard.",
    ),
    "Refunded": (Status.FAILED, "Khalti refunded it."),
    "Expired": (Status.FAILED, "The payment expired at Khalti before it was paid."),
    "User canceled": (Status.FAILED, "The payer cancelled at Khalti. Nothing was taken."),
}


class Khalti(PaymentProvider):
    code = "khalti"
    name = "Khalti"
    currencies = frozenset({"NPR"})
    min_amount = Decimal(10)
    # Even its test system needs a merchant's own key, from test-admin.khalti.com.
    keys = ("SECRET_KEY",)
    test_login = {"id": "9800000000", "mpin": "1111", "otp": "987654"}
    order = 20
    statuses = STATUSES

    def post(self, path, data):
        """Khalti's (status, answer), refusing the call if Khalti doesn't accept the key."""
        status, answer = http.request_json(
            API_URL[self.live] + path,
            method="POST",
            data=data,
            headers={"Authorization": f"Key {self.config['SECRET_KEY']}"},
        )
        if status == 401:
            logger.error("Khalti refused the secret key: %r", answer)
            raise ProviderRefused(f"Khalti refused the secret key: {details(answer)}")
        return status, answer

    def start(self, request):
        status, answer = self.post(
            "epayment/initiate/",
            {
                "return_url": request.return_url,
                "website_url": request.website_url,
                "amount": paisa(request.amount),
                "purchase_order_id": request.reference,
                "purchase_order_name": request.description,
            },
        )
        if 400 <= status < 500:
            raise ProviderRefused(f"Khalti didn't start the payment: {details(answer)}")
        if not isinstance(answer, dict) or not (answer.get("pidx") and answer.get("payment_url")):
            raise UnreadableAnswer(f"Khalti's answer had no payment page: {answer!r}")
        page = urlsplit(answer["payment_url"])
        # The whole host part, not .hostname: Python takes "example.com\@test-pay.khalti.com"
        # to be Khalti, while a browser reads the backslash as a slash and goes to example.com.
        if (page.scheme, page.netloc.lower()) != ("https", PAYMENT_PAGE_HOST[self.live]):
            logger.warning("Khalti named an unexpected payment page: %r", answer)
            raise UnreadableAnswer("Khalti named a payment page that isn't its own.")
        return Started(Redirect(answer["payment_url"]), provider_id=answer["pidx"])

    def check(self, reference, amount, provider_id=""):
        if not provider_id:
            raise ValueError("Khalti looks payments up by the pidx that start() gave.")
        # Khalti answers an expired or cancelled payment with 400, and the same JSON.
        status, answer = self.post("epayment/lookup/", {"pidx": provider_id})
        if not isinstance(answer, dict) or answer.get("status") not in STATUSES:
            raise UnreadableAnswer(f"Khalti's lookup answered {status}: {answer!r}")
        if answer.get("pidx") != provider_id or answer.get("total_amount") != paisa(amount):
            logger.warning("Khalti answered about another payment than %s: %r", reference, answer)
            raise UnreadableAnswer("Khalti's answer was about another payment.")
        word = answer["status"]
        # Khalti may still say "Completed" of a payment it has refunded.
        if word == "Completed" and answer.get("refunded"):
            word = "Refunded"
        return Outcome(
            STATUSES[word][0], provider_reference=answer.get("transaction_id") or "", word=word
        )


def paisa(amount):
    """Khalti counts in paisa: Rs 2,500.50 is 250050."""
    in_paisa = Decimal(amount) * 100
    if in_paisa != in_paisa.to_integral_value():
        raise ValueError(f"{amount} has fractions of a paisa.")
    return int(in_paisa)


def details(answer):
    """Khalti's reason, from its "detail" or its field errors."""
    if not isinstance(answer, dict):
        return repr(answer)
    if "detail" in answer:
        return str(answer["detail"])
    return "; ".join(
        f"{field}: {' '.join(map(str, errors)) if isinstance(errors, list) else errors}"
        for field, errors in answer.items()
        if field not in ("error_key", "status_code")
    )
