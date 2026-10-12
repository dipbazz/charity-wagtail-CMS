"""eSewa's ePay v2: a signed form posted to eSewa, then its status check.

https://developer.esewa.com.np/pages/Epay
"""

from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest

from nepal_payments import (
    PaymentRequest,
    ProviderUnavailable,
    Status,
    get_provider,
)
from nepal_payments.providers.esewa import ESewa

REFERENCE = "0f6d1c2e-1111-4a5b-9c8d-123456789abc"
RETURN_URL = f"https://brightwell.example/donate/payment/{REFERENCE}/"


def request(amount=Decimal(2500), reference=REFERENCE):
    return PaymentRequest(
        reference=reference,
        amount=amount,
        currency="NPR",
        return_url=RETURN_URL,
        website_url="https://brightwell.example/",
        description="A gift to Brightwell Water Trust",
    )


def esewa(live=False):
    return ESewa(live=live, **ESewa.test_keys)


def status_answer(status="COMPLETE", **changes):
    """eSewa's status check answer, as its test system gives it."""
    return {
        "product_code": "EPAYTEST",
        "transaction_uuid": REFERENCE,
        "total_amount": 2500.0,
        "status": status,
        "ref_id": "000AWEO" if status == "COMPLETE" else None,
        **changes,
    }


def test_is_found_by_its_code():
    assert get_provider("esewa") is ESewa


def test_publishes_its_test_systems_keys_and_account():
    """Checked against eSewa's test system, which refuses a form signed with any other key."""
    assert ESewa.test_keys == {"PRODUCT_CODE": "EPAYTEST", "SECRET_KEY": "8gBm/:&EnhH.1/q"}
    assert ESewa.test_login["id"] == "9711111111"


def test_signs_the_way_esewas_example_does():
    """The signed fields from eSewa's own form example, with its test key."""
    message = "total_amount=110,transaction_uuid=241028,product_code=EPAYTEST"

    assert ESewa.sign(message, "8gBm/:&EnhH.1/q") == "i94zsd3oXF6ZsSr/kGqT4sSzYQzjj1W/waxjWyRwaME="


class TestStart:
    def test_posts_a_signed_form_to_esewas_test_system(self):
        redirect = esewa().start(request()).redirect

        assert redirect.method == "POST"
        assert redirect.url == "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
        assert redirect.fields == {
            "amount": "2500",
            "tax_amount": "0",
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "total_amount": "2500",
            "transaction_uuid": REFERENCE,
            "product_code": "EPAYTEST",
            "success_url": RETURN_URL,
            "failure_url": RETURN_URL,
            "signed_field_names": "total_amount,transaction_uuid,product_code",
            "signature": ESewa.sign(
                f"total_amount=2500,transaction_uuid={REFERENCE},product_code=EPAYTEST",
                "8gBm/:&EnhH.1/q",
            ),
        }

    def test_takes_live_payments_on_esewas_own_system(self):
        assert esewa(live=True).start(request()).redirect.url == (
            "https://epay.esewa.com.np/api/epay/main/v2/form"
        )

    @pytest.mark.parametrize(("amount", "sent"), [(Decimal("2500.50"), "2500.5"), (10, "10")])
    def test_writes_amounts_without_needless_decimals(self, amount, sent):
        fields = esewa().start(request(Decimal(amount))).redirect.fields

        assert fields["total_amount"] == fields["amount"] == sent

    def test_needs_no_call_to_esewa_and_gives_no_id_of_its_own(self, provider_server):
        started = esewa().start(request())

        assert provider_server.calls == []
        assert started.provider_id == ""

    @pytest.mark.parametrize("reference", ["has space", "under_score", "ünïcode"])
    def test_refuses_a_reference_esewa_would_turn_down(self, reference):
        """eSewa takes letters, digits and hyphens only."""
        with pytest.raises(ValueError, match="letters, digits and hyphens"):
            esewa().start(request(reference=reference))


class TestCheck:
    def test_asks_esewas_test_system_about_this_payment(self, provider_server):
        provider_server.answer(200, status_answer())

        esewa().check(REFERENCE, Decimal(2500))

        call = provider_server.calls[0]
        url = urlsplit(call.url)
        assert call.method == "GET"
        assert f"{url.scheme}://{url.netloc}{url.path}" == (
            "https://rc.esewa.com.np/api/epay/transaction/status/"
        )
        assert parse_qs(url.query) == {
            "product_code": ["EPAYTEST"],
            "total_amount": ["2500"],
            "transaction_uuid": [REFERENCE],
        }

    def test_asks_esewas_own_system_about_a_live_payment(self, provider_server):
        provider_server.answer(200, status_answer())

        esewa(live=True).check(REFERENCE, Decimal(2500))

        assert provider_server.calls[0].url.startswith(
            "https://epay.esewa.com.np/api/epay/transaction/status/?"
        )

    def test_complete_is_paid_with_esewas_reference(self, provider_server):
        provider_server.answer(200, status_answer("COMPLETE"))

        outcome = esewa().check(REFERENCE, Decimal(2500))

        assert outcome.status is Status.PAID
        assert outcome.provider_reference == "000AWEO"

    @pytest.mark.parametrize(
        ("answer", "status"),
        [
            ("PENDING", Status.WAITING),
            ("AMBIGUOUS", Status.WAITING),  # eSewa: "in a halt state"
            ("PARTIAL_REFUND", Status.WAITING),  # some money kept: a person must look
            ("NOT_FOUND", Status.FAILED),  # never paid, or the session expired
            ("CANCELED", Status.FAILED),
            ("FULL_REFUND", Status.FAILED),
        ],
    )
    def test_every_other_status_is_not_paid(self, provider_server, answer, status):
        provider_server.answer(200, status_answer(answer))

        assert esewa().check(REFERENCE, Decimal(2500)).status is status

    @pytest.mark.parametrize("total", [2500, "2500.0", "2,500.0"])
    def test_reads_the_amount_however_esewa_writes_it(self, provider_server, total):
        provider_server.answer(200, status_answer(total_amount=total))

        assert esewa().check(REFERENCE, Decimal(2500)).status is Status.PAID

    @pytest.mark.parametrize(
        "changes",
        [
            {"transaction_uuid": "someone-elses-payment"},
            {"product_code": "OTHERSHOP"},
            {"total_amount": 25.0},
            {"status": "PAID_IN_FULL"},
        ],
    )
    def test_an_answer_about_another_payment_tells_us_nothing(self, provider_server, changes):
        provider_server.answer(200, status_answer(**changes))

        with pytest.raises(ProviderUnavailable):
            esewa().check(REFERENCE, Decimal(2500))

    def test_esewa_saying_its_unavailable_tells_us_nothing(self, provider_server):
        unavailable = {"code": 0, "error_message": "Service is currently unavailable"}
        provider_server.answer(200, unavailable)

        with pytest.raises(ProviderUnavailable, match="Service is currently unavailable"):
            esewa().check(REFERENCE, Decimal(2500))
