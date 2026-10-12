"""What every provider gets from PaymentProvider: its keys, test or live, and which payments it
can take."""

from decimal import Decimal

import pytest

from nepal_payments import Outcome, PaymentProvider, Redirect, Started, Status


class TwoKeyPay(PaymentProvider):
    code = "twokeypay"
    name = "Two Key Pay"
    currencies = frozenset({"NPR"})
    min_amount = Decimal(10)
    max_amount = Decimal(100_000)
    keys = ("MERCHANT_CODE", "SECRET_KEY")

    def start(self, request):
        return Started(Redirect("https://pay.example.com/"))

    def check(self, reference, amount, provider_id=""):
        return Outcome(Status.WAITING)


def test_takes_its_keys_and_starts_in_test_mode():
    provider = TwoKeyPay(MERCHANT_CODE="M-1", SECRET_KEY="s3cret")

    assert provider.config == {"MERCHANT_CODE": "M-1", "SECRET_KEY": "s3cret"}
    assert provider.live is False


def test_live_mode_is_asked_for_by_name():
    assert TwoKeyPay(live=True, MERCHANT_CODE="M-1", SECRET_KEY="s3cret").live is True


@pytest.mark.parametrize(
    ("given", "missing"),
    [
        ({}, "MERCHANT_CODE, SECRET_KEY"),
        ({"MERCHANT_CODE": "M-1"}, "SECRET_KEY"),
        ({"MERCHANT_CODE": "M-1", "SECRET_KEY": ""}, "SECRET_KEY"),
    ],
)
def test_refuses_to_start_without_every_key(given, missing):
    with pytest.raises(ValueError, match=f"^Two Key Pay needs {missing}.$"):
        TwoKeyPay(**given)


def test_refuses_a_key_it_doesnt_use():
    """A misspelt key would otherwise be ignored while the right one stays missing."""
    with pytest.raises(TypeError, match="SECRET"):
        TwoKeyPay(MERCHANT_CODE="M-1", SECRET_KEY="s3cret", SECRET="typo")


def test_never_shows_its_keys():
    provider = TwoKeyPay(MERCHANT_CODE="M-1", SECRET_KEY="s3cret")

    assert "s3cret" not in repr(provider)


@pytest.mark.parametrize(
    ("currency", "amount", "accepted"),
    [
        ("NPR", Decimal(10), True),
        ("NPR", Decimal(100_000), True),
        ("NPR", Decimal("9.99"), False),
        ("NPR", Decimal(100_001), False),
        ("GBP", Decimal(500), False),
    ],
)
def test_accepts_only_its_currencies_and_amounts(currency, amount, accepted):
    assert TwoKeyPay.accepts(currency, amount) is accepted


def test_with_no_upper_limit_any_amount_above_the_minimum_is_accepted():
    unlimited = type("Unlimited", (TwoKeyPay,), {"code": "unlimited", "max_amount": None})

    assert unlimited.accepts("NPR", Decimal(10_000_000))


def test_a_status_is_also_its_text():
    """So a project can store it as it is."""
    assert Status.PAID == "paid"
    assert [status.value for status in Status] == ["waiting", "paid", "failed"]
