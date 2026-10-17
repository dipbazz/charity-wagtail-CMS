"""eSewa's ePay v2: the payer goes to eSewa with a signed form, and eSewa's status check says
whether they paid.

https://developer.esewa.com.np/pages/Epay
"""

import base64
import hashlib
import hmac
import logging
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from nepal_payments import http
from nepal_payments.base import (
    Outcome,
    PaymentProvider,
    ProviderUnavailable,
    Redirect,
    Started,
    Status,
    UnreadableAnswer,
)

logger = logging.getLogger(__name__)

FORM_URL = {
    False: "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
    True: "https://epay.esewa.com.np/api/epay/main/v2/form",
}
# eSewa's docs give two addresses for each; these are the ones that answer (October 2026).
STATUS_URL = {
    False: "https://rc.esewa.com.np/api/epay/transaction/status/",
    True: "https://epay.esewa.com.np/api/epay/transaction/status/",
}
STATUSES = {
    "COMPLETE": (Status.PAID, "eSewa says it's paid."),
    "PENDING": (Status.WAITING, "eSewa hasn't finished the payment yet."),
    "AMBIGUOUS": (Status.WAITING, "eSewa has the payment on hold and hasn't decided yet."),
    # Some of the money was kept, so it's neither paid in full nor failed: a person must look.
    "PARTIAL_REFUND": (
        Status.WAITING,
        "eSewa refunded part of it. Check what was kept in eSewa's merchant portal.",
    ),
    "NOT_FOUND": (
        Status.FAILED,
        "eSewa has no payment for it: the payer didn't pay, or eSewa's session ran out.",
    ),
    "CANCELED": (Status.FAILED, "The payer cancelled at eSewa. Nothing was taken."),
    "FULL_REFUND": (Status.FAILED, "eSewa refunded it in full."),
}
SIGNED_FIELDS = ("total_amount", "transaction_uuid", "product_code")


class ESewa(PaymentProvider):
    code = "esewa"
    name = "eSewa"
    logo = "esewa.png"  # from eSewa's developer site, for use on white (Logomark Guidelines)
    currencies = frozenset({"NPR"})
    keys = ("PRODUCT_CODE", "SECRET_KEY")
    # eSewa publishes these for its test system ("UAT"). A form signed with them is accepted
    # there, and with anything else refused.
    test_keys = {"PRODUCT_CODE": "EPAYTEST", "SECRET_KEY": "8gBm/:&EnhH.1/q"}
    test_login = {"id": "9711111111", "password": "Nepal@123", "otp": "123456"}
    order = 10
    statuses = STATUSES
    # eSewa refuses a transaction_uuid it has seen: "Duplicate transaction UUID."
    opens_once = True

    @staticmethod
    def sign(message, secret_key):
        """eSewa's signature: HMAC-SHA256 of "name=value,…", in base64."""
        digest = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    def start(self, request):
        if not re.fullmatch(r"[A-Za-z0-9-]+", request.reference):
            raise ValueError("eSewa takes a reference of letters, digits and hyphens only.")
        total = amount_text(request.amount)
        fields = {
            "amount": total,
            "tax_amount": "0",
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "total_amount": total,
            "transaction_uuid": request.reference,
            "product_code": self.config["PRODUCT_CODE"],
            # eSewa adds "?data=…" to the address it returns to, paid or not; check() decides.
            "success_url": request.return_url,
            "failure_url": request.return_url,
            "signed_field_names": ",".join(SIGNED_FIELDS),
        }
        message = ",".join(f"{name}={fields[name]}" for name in SIGNED_FIELDS)
        fields["signature"] = self.sign(message, self.config["SECRET_KEY"])
        return Started(Redirect(FORM_URL[self.live], method="POST", fields=fields))

    def check(self, reference, amount, provider_id=""):
        product_code = self.config["PRODUCT_CODE"]
        query = urlencode(
            {
                "product_code": product_code,
                "total_amount": amount_text(amount),
                "transaction_uuid": reference,
            }
        )
        status, answer = http.request_json(f"{STATUS_URL[self.live]}?{query}")
        if status != 200 or not isinstance(answer, dict):
            raise UnreadableAnswer(f"eSewa's status check answered {status}: {answer!r}")
        if "error_message" in answer:
            raise ProviderUnavailable(f"eSewa's status check: {answer['error_message']}")
        echoed = (answer.get("transaction_uuid"), answer.get("product_code"))
        if echoed != (reference, product_code) or read_amount(answer.get("total_amount")) != amount:
            logger.warning("eSewa answered about another payment than %s: %r", reference, answer)
            raise UnreadableAnswer("eSewa's answer was about another payment.")
        if answer.get("status") not in STATUSES:
            logger.warning("eSewa gave payment %s an unknown status: %r", reference, answer)
            raise UnreadableAnswer(f"eSewa's status {answer.get('status')!r} isn't known.")
        word = answer["status"]
        return Outcome(STATUSES[word][0], provider_reference=answer.get("ref_id") or "", word=word)


def amount_text(amount):
    """An amount as eSewa reads it: "2500", or "2500.5" with paisa."""
    return format(Decimal(amount).normalize(), "f")


def read_amount(value):
    """An amount from eSewa, which may write 2500.0 or "2,500.0"; None if it isn't one."""
    try:
        amount = Decimal(str(value).replace(",", ""))
    except InvalidOperation:
        return None
    # NaN and infinity aren't amounts, and comparing "sNaN" with one raises InvalidOperation.
    return amount if amount.is_finite() else None
