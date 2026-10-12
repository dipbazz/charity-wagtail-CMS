"""What every provider in providers/ must do. A new provider file is checked by these tests with
none of them written again; its own API gets a test file of its own (test_<code>.py)."""

import re
from decimal import Decimal

import pytest

from nepal_payments import PaymentError, PaymentRequest, ProviderUnavailable, Status, all_providers

each_provider = pytest.mark.parametrize(
    "provider", list(all_providers().values()), ids=lambda provider: provider.code
)

REQUEST = PaymentRequest(
    reference="0f6d1c2e-1111-4a5b-9c8d-123456789abc",
    amount=Decimal(2500),
    currency="NPR",
    return_url="https://brightwell.example/donate/payment/0f6d1c2e-1111-4a5b-9c8d-123456789abc/",
    website_url="https://brightwell.example/",
    description="A gift to Brightwell Water Trust",
)
# Answers a provider can't make sense of: whatever it does, it mustn't say "paid".
UNREADABLE = [
    (200, {}),
    (200, []),
    (200, "Completed"),
    (200, {"status": None}),
    (404, {"detail": "Not found."}),
    (401, {"detail": "Invalid token."}),
]


def set_up(provider, live=False):
    return provider(live=live, **{key: f"test-{key.lower()}" for key in provider.keys})


@each_provider
def test_describes_itself(provider):
    assert re.fullmatch(r"[a-z][a-z0-9]*", provider.code)
    assert provider.name.strip()
    assert provider.currencies
    assert all(re.fullmatch(r"[A-Z]{3}", currency) for currency in provider.currencies)
    assert isinstance(provider.min_amount, Decimal) and provider.min_amount > 0
    assert provider.keys
    assert all(re.fullmatch(r"[A-Z][A-Z0-9_]*", key) for key in provider.keys)
    assert set(provider.test_keys) <= set(provider.keys)
    assert all(isinstance(value, str) for value in provider.test_login.values())


@each_provider
def test_needs_its_keys(provider):
    with pytest.raises(ValueError, match=provider.keys[0]):
        provider()


@each_provider
def test_sends_the_payer_only_to_a_secure_page(provider, provider_server):
    for status, body in UNREADABLE:
        provider_server.answer(status, body)
        try:
            started = set_up(provider).start(REQUEST)
        except PaymentError:
            continue
        assert started.redirect.url.startswith("https://")
        assert started.redirect.method in ("GET", "POST")


@each_provider
@pytest.mark.parametrize(("status", "body"), UNREADABLE)
def test_never_says_paid_for_an_answer_it_cant_read(provider, provider_server, status, body):
    provider_server.answer(status, body)

    try:
        outcome = set_up(provider).check(REQUEST.reference, REQUEST.amount, provider_id="abc123")
    except PaymentError:
        return
    assert outcome.status is not Status.PAID


@each_provider
def test_says_so_when_it_cant_reach_the_provider(provider, provider_server):
    """So the caller leaves the payment as it was, rather than marking it failed."""
    provider_server.fail()

    with pytest.raises(ProviderUnavailable):
        set_up(provider).check(REQUEST.reference, REQUEST.amount, provider_id="abc123")


@each_provider
def test_test_mode_never_uses_the_live_system(provider, provider_server):
    def addresses(live):
        used = set()
        provider_server.calls.clear()
        provider_server.answers.extend([(200, {})] * 4)
        try:
            used.add(set_up(provider, live).start(REQUEST).redirect.url)
        except PaymentError:
            pass
        try:
            set_up(provider, live).check(REQUEST.reference, REQUEST.amount, provider_id="abc123")
        except PaymentError:
            pass
        provider_server.answers.clear()
        return used | {call.url.split("?")[0] for call in provider_server.calls}

    test, live = addresses(live=False), addresses(live=True)

    assert test and live
    assert test.isdisjoint(live)
