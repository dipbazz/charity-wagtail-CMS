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
    ProviderUnavailable,
    Redirect,
    Started,
    Status,
)

logger = logging.getLogger(__name__)

API_URL = {False: "https://dev.khalti.com/api/v2/", True: "https://khalti.com/api/v2/"}
# The only pages the payer is sent to. An initiate answer naming any other is refused.
PAYMENT_PAGE_HOST = {False: "test-pay.khalti.com", True: "pay.khalti.com"}
STATUSES = {
    "Completed": Status.PAID,
    "Pending": Status.WAITING,
    "Initiated": Status.WAITING,
    # Some of the money was kept, so it's neither paid in full nor failed: a person must look.
    "Partially Refunded": Status.WAITING,
    "Refunded": Status.FAILED,
    "Expired": Status.FAILED,
    "User canceled": Status.FAILED,
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
            raise ProviderUnavailable(f"Khalti's answer had no payment page: {answer!r}")
        page = urlsplit(answer["payment_url"])
        if (page.scheme, page.hostname) != ("https", PAYMENT_PAGE_HOST[self.live]):
            logger.warning("Khalti named an unexpected payment page: %r", answer)
            raise ProviderUnavailable("Khalti named a payment page that isn't its own.")
        return Started(Redirect(answer["payment_url"]), provider_id=answer["pidx"])

    def check(self, reference, amount, provider_id=""):
        if not provider_id:
            raise ValueError("Khalti looks payments up by the pidx that start() gave.")
        # Khalti answers an expired or cancelled payment with 400, and the same JSON.
        status, answer = self.post("epayment/lookup/", {"pidx": provider_id})
        if not isinstance(answer, dict) or answer.get("status") not in STATUSES:
            raise ProviderUnavailable(f"Khalti's lookup answered {status}: {answer!r}")
        if answer.get("pidx") != provider_id or answer.get("total_amount") != paisa(amount):
            logger.warning("Khalti answered about another payment than %s: %r", reference, answer)
            raise ProviderUnavailable("Khalti's answer was about another payment.")
        outcome = STATUSES[answer["status"]]
        if outcome is Status.PAID and answer.get("refunded"):
            outcome = Status.FAILED
        return Outcome(outcome, provider_reference=answer.get("transaction_id") or "")


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
