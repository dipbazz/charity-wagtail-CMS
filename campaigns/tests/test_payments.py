"""Which payment providers this installation offers, and how a payment's status is recorded."""

from decimal import Decimal

import pytest
from django.core import checks

from campaigns.models import Payment, PaymentStatus, Pledge
from campaigns.payments import (
    check_payment_keys,
    method_choices,
    provider_for,
    providers_for,
)
from nepal_payments import Status
from nepal_payments.providers.esewa import ESewa
from nepal_payments.providers.khalti import Khalti

ESEWA_KEYS = {"ESEWA_PRODUCT_CODE": "EPAYTEST", "ESEWA_SECRET_KEY": "test-secret"}
KHALTI_KEYS = {"KHALTI_SECRET_KEY": "test-secret-key"}


@pytest.fixture
def both(settings):
    settings.PAYMENT_KEYS = {**ESEWA_KEYS, **KHALTI_KEYS}


class TestProvidersOffered:
    def test_none_until_a_providers_keys_are_set(self, settings):
        settings.PAYMENT_KEYS = {}

        assert providers_for("NPR") == []

    def test_a_provider_once_all_its_keys_are_set(self, settings):
        settings.PAYMENT_KEYS = KHALTI_KEYS

        assert providers_for("NPR") == [Khalti]

    def test_not_a_provider_with_only_some_of_its_keys(self, settings):
        settings.PAYMENT_KEYS = {"ESEWA_PRODUCT_CODE": "EPAYTEST"}

        assert providers_for("NPR") == []

    def test_in_their_suggested_order(self, both):
        assert providers_for("NPR") == [ESewa, Khalti]

    def test_only_those_that_take_the_currency(self, both):
        """eSewa and Khalti take rupees, so a UK charity's pledges in pounds get neither."""
        assert providers_for("GBP") == []

    def test_only_those_that_take_the_amount(self, both):
        assert providers_for("NPR", Decimal(5)) == [ESewa]  # Khalti takes Rs 10 or more

    def test_ready_to_use_with_this_installations_keys(self, settings, both):
        settings.LIVE_PAYMENTS = True

        khalti = provider_for("khalti")

        assert khalti.config == {"SECRET_KEY": "test-secret-key"}
        assert khalti.live is True

    def test_in_their_test_systems_unless_live(self, both):
        assert provider_for("esewa").live is False

    @pytest.mark.parametrize("code", ["khalti", "nosuchpay"])
    def test_none_for_one_not_set_up_or_unknown(self, settings, code):
        settings.PAYMENT_KEYS = ESEWA_KEYS

        assert provider_for(code) is None

    def test_every_provider_can_be_named_on_a_payment(self):
        assert {("esewa", "eSewa"), ("khalti", "Khalti")} <= set(method_choices())


class TestPaymentKeysCheck:
    """`migrate` runs these when the container starts, so a half set-up provider stops it."""

    def test_a_provider_with_only_some_of_its_keys_stops_the_site(self, settings):
        settings.PAYMENT_KEYS = {"ESEWA_PRODUCT_CODE": "EPAYTEST"}

        [error] = check_payment_keys(app_configs=None)

        assert error.level == checks.ERROR
        assert "eSewa" in error.msg
        assert "DJANGO_PAYMENT_ESEWA_SECRET_KEY" in error.hint

    def test_a_key_no_provider_uses_is_a_warning(self, settings):
        settings.PAYMENT_KEYS = {**KHALTI_KEYS, "KHALTY_SECRET_KEY": "typo"}

        [warning] = check_payment_keys(app_configs=None)

        assert warning.level == checks.WARNING
        assert "DJANGO_PAYMENT_KHALTY_SECRET_KEY" in warning.msg

    def test_providers_set_up_in_full_pass(self, both):
        assert check_payment_keys(app_configs=None) == []

    def test_is_registered_with_django(self):
        assert check_payment_keys in checks.registry.registry.get_checks()


@pytest.fixture
def pledge(db, donate_page):
    return Pledge.objects.create(
        page=donate_page, amount=2500, currency="NPR", name="Sita Sharma", email="sita@example.com"
    )


class TestPledgeReference:
    def test_each_pledge_gets_its_own_reference(self, pledge, donate_page):
        other = Pledge.objects.create(
            page=donate_page, amount=1500, currency="NPR", name="Ram", email="ram@example.com"
        )

        assert pledge.reference is not None
        assert other.reference != pledge.reference

    def test_keeps_its_reference_when_saved_again(self, pledge):
        reference = pledge.reference
        pledge.save()

        assert Pledge.objects.get(pk=pledge.pk).reference == reference

    def test_starts_waiting_for_payment(self, pledge):
        assert pledge.payment_status == PaymentStatus.WAITING
        assert pledge.paid_at is None


class TestPayment:
    def test_starting_one_takes_the_pledges_amount(self, pledge):
        payment = pledge.start_payment("khalti", live=False)

        assert (payment.method, payment.amount, payment.currency) == ("khalti", 2500, "NPR")
        assert payment.status == PaymentStatus.WAITING
        assert payment.live is False
        assert payment.reference

    def test_a_new_attempt_after_a_failed_one_is_waiting_again(self, pledge):
        pledge.start_payment("esewa", live=False).record(Status.FAILED)

        pledge.start_payment("khalti", live=False)

        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.WAITING

    def test_paid_marks_the_pledge_paid(self, pledge):
        payment = pledge.start_payment("esewa", live=False)

        assert payment.record(Status.PAID, "000AWEO") is True

        payment.refresh_from_db()
        assert payment.status == PaymentStatus.PAID
        assert payment.provider_reference == "000AWEO"
        pledge.refresh_from_db()
        assert pledge.payment_status == PaymentStatus.PAID
        assert pledge.paid_at is not None

    def test_recording_paid_twice_changes_nothing_more(self, pledge):
        payment = pledge.start_payment("esewa", live=False)
        payment.record(Status.PAID, "000AWEO")
        paid_at = Pledge.objects.get(pk=pledge.pk).paid_at

        assert payment.record(Status.PAID, "000AWEO") is False
        assert Pledge.objects.get(pk=pledge.pk).paid_at == paid_at

    @pytest.mark.parametrize("later", [Status.FAILED, Status.WAITING])
    def test_paid_never_goes_back(self, pledge, later):
        payment = pledge.start_payment("esewa", live=False)
        payment.record(Status.PAID, "000AWEO")

        assert payment.record(later) is False

        assert Payment.objects.get(pk=payment.pk).status == PaymentStatus.PAID
        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.PAID

    def test_failed_marks_the_pledge_failed(self, pledge):
        pledge.start_payment("khalti", live=False).record(Status.FAILED)

        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.FAILED

    def test_a_failed_attempt_doesnt_undo_a_paid_pledge(self, pledge):
        pledge.start_payment("esewa", live=False).record(Status.PAID, "000AWEO")

        pledge.start_payment("khalti", live=False).record(Status.FAILED)

        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.PAID

    def test_a_failed_attempt_can_still_turn_out_paid(self, pledge):
        """eSewa sends a payer back to the same address paid or not; it may confirm later."""
        payment = pledge.start_payment("esewa", live=False)
        payment.record(Status.FAILED)

        assert payment.record(Status.PAID, "000AWEO") is True
        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.PAID

    # Regression: ISSUE-002 — a Rs 1,000 attempt marked its pledge paid after the pledge was
    # changed to Rs 10,000 in the admin. Found by /qa on 2026-10-12.
    @pytest.mark.parametrize("change", [{"amount": 10000}, {"currency": "GBP"}])
    def test_paid_for_what_the_pledge_no_longer_says_leaves_it_unpaid(self, pledge, change):
        """An attempt pays its pledge only if it was for what the pledge says now. One changed
        after the attempt started (an admin's edit, or a resent form racing the start) waits for
        a person to look."""
        payment = pledge.start_payment("esewa", live=False)
        Pledge.objects.filter(pk=pledge.pk).update(**change)

        assert payment.record(Status.PAID, "000AWEO") is True

        assert Payment.objects.get(pk=payment.pk).status == PaymentStatus.PAID
        pledge.refresh_from_db()
        assert pledge.payment_status == PaymentStatus.WAITING
        assert pledge.paid_at is None

    def test_still_waiting_changes_nothing(self, pledge):
        payment = pledge.start_payment("esewa", live=False)

        assert payment.record(Status.WAITING) is False
        assert Payment.objects.get(pk=payment.pk).status == PaymentStatus.WAITING

    def test_a_new_provider_needs_no_migration(self):
        """The choices are a function, which migrations keep by name, not its list."""
        _, _, _, kwargs = Payment._meta.get_field("method").deconstruct()

        assert kwargs["choices"] is method_choices

    def test_statuses_are_the_payment_packages(self):
        assert [status.value for status in Status] == PaymentStatus.values
