"""Khalti's web checkout (KPG-2): initiate from the server, send the payer to Khalti, then look the
payment up.

https://docs.khalti.com/khalti-epayment/
"""

from decimal import Decimal

import pytest

from nepal_payments import (
    PaymentRequest,
    ProviderRefused,
    Status,
    UnreadableAnswer,
    get_provider,
)
from nepal_payments.providers.khalti import Khalti

REFERENCE = "0f6d1c2e-1111-4a5b-9c8d-123456789abc"
RETURN_URL = f"https://brightwell.example/donate/payment/{REFERENCE}/"
PIDX = "bZQLD9wRVWo4CdESSfuSsB"


def request(amount=Decimal(2500)):
    return PaymentRequest(
        reference=REFERENCE,
        amount=amount,
        currency="NPR",
        return_url=RETURN_URL,
        website_url="https://brightwell.example/",
        description="A gift to Brightwell Water Trust",
    )


def khalti(live=False):
    return Khalti(live=live, SECRET_KEY="test-secret-key")


def started_answer(**changes):
    return {
        "pidx": PIDX,
        "payment_url": f"https://test-pay.khalti.com/?pidx={PIDX}",
        "expires_at": "2026-10-12T16:26:16.471649+05:45",
        "expires_in": 1800,
        **changes,
    }


def lookup_answer(status="Completed", **changes):
    return {
        "pidx": PIDX,
        "total_amount": 250000,
        "status": status,
        "transaction_id": "GFq9PFS7b2iYvL8Lir9oXe" if status == "Completed" else None,
        "fee": 0,
        "refunded": False,
        **changes,
    }


def test_is_found_by_its_code():
    assert get_provider("khalti") is Khalti


def test_its_payment_link_can_be_opened_again():
    """Khalti's link stays open for a while, so a payer who leaves can go back to it."""
    assert Khalti.opens_once is False


def test_takes_rupees_from_rs_10():
    """Khalti refuses less than 1000 paisa."""
    assert Khalti.accepts("NPR", Decimal(10))
    assert not Khalti.accepts("NPR", Decimal("9.99"))


def test_publishes_its_test_account_but_each_merchant_needs_its_own_key():
    assert Khalti.test_login == {"id": "9800000000", "mpin": "1111", "otp": "987654"}
    assert Khalti.test_keys == {}


class TestStart:
    def test_asks_khaltis_test_system_to_start_a_payment(self, provider_server):
        provider_server.answer(200, started_answer())

        khalti().start(request())

        call = provider_server.calls[0]
        assert call.method == "POST"
        assert call.url == "https://dev.khalti.com/api/v2/epayment/initiate/"
        assert call.headers == {"Authorization": "Key test-secret-key"}
        assert call.data == {
            "return_url": RETURN_URL,
            "website_url": "https://brightwell.example/",
            "amount": 250000,
            "purchase_order_id": REFERENCE,
            "purchase_order_name": "A gift to Brightwell Water Trust",
        }

    def test_sends_khalti_nothing_about_the_payer(self, provider_server):
        provider_server.answer(200, started_answer())

        khalti().start(request())

        assert "customer_info" not in provider_server.calls[0].data

    def test_takes_live_payments_on_khaltis_own_system(self, provider_server):
        provider_server.answer(
            200, started_answer(payment_url=f"https://pay.khalti.com/?pidx={PIDX}")
        )

        khalti(live=True).start(request())

        assert provider_server.calls[0].url == "https://khalti.com/api/v2/epayment/initiate/"

    def test_sends_rupees_and_paisa_as_paisa(self, provider_server):
        provider_server.answer(200, started_answer())

        khalti().start(request(Decimal("2500.50")))

        assert provider_server.calls[0].data["amount"] == 250050

    def test_sends_the_payer_to_khalti_and_keeps_khaltis_id(self, provider_server):
        provider_server.answer(200, started_answer())

        started = khalti().start(request())

        assert started.redirect.method == "GET"
        assert started.redirect.url == f"https://test-pay.khalti.com/?pidx={PIDX}"
        assert started.provider_id == PIDX

    @pytest.mark.parametrize(
        ("live", "payment_url"),
        [
            (False, f"http://test-pay.khalti.com/?pidx={PIDX}"),
            (False, f"https://pay.example.com/?pidx={PIDX}"),
            (False, f"https://test-pay.khalti.com.example.com/?pidx={PIDX}"),
            (False, f"https://pay.khalti.com/?pidx={PIDX}"),  # live, in test mode
            (True, f"https://test-pay.khalti.com/?pidx={PIDX}"),  # test, in live mode
            # Regression: ISSUE-008 — Python read this as Khalti's page, but a browser reads the
            # backslash as a slash and goes to example.com. Found by /qa on 2026-10-12.
            (False, f"https://example.com\\@test-pay.khalti.com/?pidx={PIDX}"),
        ],
    )
    def test_sends_the_payer_nowhere_but_khaltis_own_page(self, provider_server, live, payment_url):
        provider_server.answer(200, started_answer(payment_url=payment_url))

        with pytest.raises(UnreadableAnswer, match="payment page"):
            khalti(live).start(request())

    def test_a_refused_payment_says_why(self, provider_server):
        provider_server.answer(
            400,
            {
                "amount": ["Amount should be greater than Rs. 10, that is 1000 paisa."],
                "error_key": "validation_error",
            },
        )

        with pytest.raises(ProviderRefused, match="greater than Rs. 10"):
            khalti().start(request())

    def test_a_wrong_key_is_refused(self, provider_server):
        provider_server.answer(401, {"detail": "Invalid token.", "status_code": 401})

        with pytest.raises(ProviderRefused, match="Invalid token"):
            khalti().start(request())

    @pytest.mark.parametrize("answer", [{}, {"pidx": PIDX}, {"payment_url": "https://x/"}])
    def test_an_answer_without_a_payment_page_tells_us_nothing(self, provider_server, answer):
        provider_server.answer(200, answer)

        with pytest.raises(UnreadableAnswer):
            khalti().start(request())


class TestCheck:
    def test_looks_up_the_payment_by_khaltis_id(self, provider_server):
        provider_server.answer(200, lookup_answer())

        khalti().check(REFERENCE, Decimal(2500), provider_id=PIDX)

        call = provider_server.calls[0]
        assert call.method == "POST"
        assert call.url == "https://dev.khalti.com/api/v2/epayment/lookup/"
        assert call.headers == {"Authorization": "Key test-secret-key"}
        assert call.data == {"pidx": PIDX}

    def test_looks_up_a_live_payment_on_khaltis_own_system(self, provider_server):
        provider_server.answer(200, lookup_answer())

        khalti(live=True).check(REFERENCE, Decimal(2500), provider_id=PIDX)

        assert provider_server.calls[0].url == "https://khalti.com/api/v2/epayment/lookup/"

    def test_completed_is_paid_with_khaltis_transaction_id(self, provider_server):
        provider_server.answer(200, lookup_answer("Completed"))

        outcome = khalti().check(REFERENCE, Decimal(2500), provider_id=PIDX)

        assert outcome.status is Status.PAID
        assert outcome.provider_reference == "GFq9PFS7b2iYvL8Lir9oXe"
        assert outcome.word == "Completed"

    @pytest.mark.parametrize(
        ("http_status", "answer", "status"),
        [
            (200, "Pending", Status.WAITING),
            (200, "Initiated", Status.WAITING),
            (200, "Partially Refunded", Status.WAITING),  # some money kept: a person must look
            (200, "Refunded", Status.FAILED),
            (400, "Expired", Status.FAILED),  # Khalti answers these two with 400
            (400, "User canceled", Status.FAILED),
        ],
    )
    def test_every_other_status_is_not_paid(self, provider_server, http_status, answer, status):
        provider_server.answer(http_status, lookup_answer(answer))

        outcome = khalti().check(REFERENCE, Decimal(2500), provider_id=PIDX)

        assert outcome.status is status
        assert outcome.word == answer

    def test_a_refunded_payment_isnt_paid(self, provider_server):
        """Nor described as completed: its sentence would say it's paid."""
        provider_server.answer(200, lookup_answer("Completed", refunded=True))

        outcome = khalti().check(REFERENCE, Decimal(2500), provider_id=PIDX)

        assert outcome.status is Status.FAILED
        assert outcome.word == "Refunded"

    @pytest.mark.parametrize(
        "changes",
        [{"total_amount": 25000}, {"pidx": "someone-elses-payment"}, {"status": "Done"}],
    )
    def test_an_answer_about_another_payment_tells_us_nothing(self, provider_server, changes):
        provider_server.answer(200, lookup_answer(**changes))

        with pytest.raises(UnreadableAnswer):
            khalti().check(REFERENCE, Decimal(2500), provider_id=PIDX)

    def test_a_payment_khalti_doesnt_know_tells_us_nothing(self, provider_server):
        provider_server.answer(404, {"detail": "Not found.", "error_key": "validation_error"})

        with pytest.raises(UnreadableAnswer):
            khalti().check(REFERENCE, Decimal(2500), provider_id=PIDX)

    def test_a_wrong_key_is_refused(self, provider_server):
        provider_server.answer(401, {"detail": "Invalid token.", "status_code": 401})

        with pytest.raises(ProviderRefused, match="Invalid token"):
            khalti().check(REFERENCE, Decimal(2500), provider_id=PIDX)

    def test_needs_the_id_khalti_gave_when_it_started(self):
        with pytest.raises(ValueError, match="pidx"):
            khalti().check(REFERENCE, Decimal(2500))
