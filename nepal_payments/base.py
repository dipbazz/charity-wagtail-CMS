"""The contract every payment provider meets, and the plain values that cross it.

A provider is one class in its own file in `providers/`. It never touches the caller's database
or settings: the caller gives it keys and a `PaymentRequest`, stores what it gets back, and asks
again with `check()` when the payer returns or later.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar


class Status(StrEnum):
    """What a provider says about a payment. Only PAID means the money arrived."""

    WAITING = "waiting"  # started but not finished, or the provider hasn't decided yet
    PAID = "paid"
    FAILED = "failed"  # cancelled, expired, refused or refunded: no money was kept


class PaymentError(Exception):
    """A provider couldn't do what was asked."""


class ProviderUnavailable(PaymentError):
    """The provider couldn't be reached, or answered with something that can't be read. Nothing
    is known about the payment: leave it as it was, and ask again later."""


class UnreadableAnswer(ProviderUnavailable):
    """The provider answered, but not with anything that can be read: not JSON, a status it isn't
    known to use, or an answer about another payment. Handled as ProviderUnavailable, but told
    apart from a provider that couldn't be reached at all."""


class ProviderRefused(PaymentError):
    """The provider turned the request down, e.g. a wrong key or an amount below its minimum.
    Asking again won't help."""


@dataclass(frozen=True)
class PaymentRequest:
    """What a provider needs to start taking a payment."""

    # The caller's own ID for this attempt, unique across attempts: letters, digits and hyphens,
    # such as a UUID. Providers send it back, and some refuse one they've seen before.
    reference: str
    amount: Decimal  # in the currency's main unit: rupees, not paisa
    currency: str  # ISO 4217, e.g. "NPR"
    # Where the provider sends the payer back, paid or not. Some providers add a query string,
    # so carry anything the caller needs in the path.
    return_url: str
    website_url: str  # the caller's site, which some providers show or check
    description: str  # what the payment is for, which some providers show to the payer


@dataclass(frozen=True)
class Redirect:
    """Where to send the payer: a link to follow (GET), or a form to post (POST) with `fields`."""

    url: str
    method: str = "GET"
    fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Started:
    redirect: Redirect
    # The provider's own ID for this attempt, if it gives one (Khalti's pidx). Keep it, and pass
    # it to check().
    provider_id: str = ""


@dataclass(frozen=True)
class Outcome:
    status: Status
    # The provider's transaction ID once paid, to find the payment in its statements.
    provider_reference: str = ""
    # The provider's own word for the status, one of its `statuses`, to match its records.
    word: str = ""


class PaymentProvider(ABC):
    """A payment gateway. Subclass it in a file of its own in `providers/`.

    Set the class attributes, then write `start()` and `check()`. Reach the provider only through
    `nepal_payments.http.request_json`, so tests can stand in for it.
    """

    code: ClassVar[str]  # permanent: callers store it with payments; lowercase letters, digits
    name: ClassVar[str]  # the brand, as payers know it
    currencies: ClassVar[frozenset[str]] = frozenset({"NPR"})
    min_amount: ClassVar[Decimal] = Decimal(1)
    max_amount: ClassVar[Decimal | None] = None
    # The keys the merchant gets from the provider, such as ("SECRET_KEY",).
    keys: ClassVar[tuple[str, ...]] = ()
    # Keys for the provider's test system that it publishes itself, if any, so it can be tried
    # with no account of one's own.
    test_keys: ClassVar[dict[str, str]] = {}
    # An account on the provider's test system that anyone may pay with, as the provider
    # publishes it: {"id": …, "password": …, "mpin": …, "otp": …}.
    test_login: ClassVar[dict[str, str]] = {}
    order: ClassVar[int] = 100  # where it suggests it's listed among providers, lowest first
    # Whether the page `start()` sends the payer to takes them only once, such as a signed form
    # the provider refuses to take twice (eSewa's). Paying again then needs a new payment; a link
    # that stays open (Khalti's) can be followed again.
    opens_once: ClassVar[bool] = False
    # Every word the provider answers `check()` with: what it means, and a sentence for the people
    # who follow payments up, e.g. {"CANCELED": (Status.FAILED, "The payer cancelled at eSewa.")}.
    # A word not in here is an answer that can't be read.
    statuses: ClassVar[dict[str, tuple[Status, str]]] = {}
    # The words in `statuses` that mean a person must look, such as a partial refund: some money
    # was kept, so the payment is neither paid in full nor failed.
    needs_checking: ClassVar[frozenset[str]] = frozenset()

    def __init__(self, *, live=False, **keys):
        """`live=True` takes real money; otherwise the provider's test system is used."""
        unknown = set(keys) - set(self.keys)
        if unknown:
            raise TypeError(f"{self.name} has no key {', '.join(sorted(unknown))}.")
        missing = [key for key in self.keys if not keys.get(key)]
        if missing:
            raise ValueError(f"{self.name} needs {', '.join(missing)}.")
        self.live = live
        self.config = {key: keys[key] for key in self.keys}

    def __repr__(self):
        return f"<{type(self).__name__} {'live' if self.live else 'test'}>"

    @classmethod
    def describe(cls, word):
        """The sentence for one of the provider's words; "" for a word it isn't known to use."""
        known = cls.statuses.get(word)
        return known[1] if known else ""

    @classmethod
    def accepts(cls, currency, amount):
        """Whether this provider can take this amount in this currency."""
        return (
            currency in cls.currencies
            and amount >= cls.min_amount
            and (cls.max_amount is None or amount <= cls.max_amount)
        )

    @abstractmethod
    def start(self, request: PaymentRequest) -> Started:
        """Begin taking a payment: where to send the payer, and the provider's ID if any.

        Raises ProviderUnavailable or ProviderRefused when it can't begin.
        """

    @abstractmethod
    def check(self, reference: str, amount: Decimal, provider_id: str = "") -> Outcome:
        """Ask the provider what became of a payment, by the caller's reference and amount and
        the provider's ID from `start()`. Never decided from what the payer's browser brings
        back, which anyone could change.

        Raises ProviderUnavailable when the provider can't be reached, or UnreadableAnswer (a
        kind of it) when what it answered can't be read.
        """
