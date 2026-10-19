"""Which payment providers this installation offers, and how a payment's status is recorded."""

import re
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib.staticfiles import finders
from django.core import checks
from django.db import IntegrityError
from django.utils import timezone

from campaigns.models import Payment, PaymentStatus, PaymentStep, Pledge, StepKind
from campaigns.payments import (
    check_payment_keys,
    is_team_confirmed,
    logo_for,
    method_choices,
    provider_for,
    providers_for,
    ways_to_pay,
)
from nepal_payments import (
    Outcome,
    ProviderRefused,
    ProviderUnavailable,
    Status,
    UnreadableAnswer,
)
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

    def test_so_can_the_methods_the_team_confirms(self):
        assert ("qr", "QR code") in method_choices()
        assert is_team_confirmed("qr")
        assert not is_team_confirmed("esewa")

    def test_a_methods_name_isnt_a_provider(self):
        """Nothing can be asked about a QR payment, and nobody can start one with a provider."""
        assert provider_for("qr") is None


class TestLogos:
    """Each provider's logo, as its pay button shows it (#201)."""

    @pytest.mark.parametrize(
        ("provider", "address", "size"),
        [
            (ESewa, "/static/payment-logos/esewa.png", (597, 228)),
            (Khalti, "/static/payment-logos/khalti.svg", (412, 206)),
        ],
    )
    def test_its_address_and_size(self, provider, address, size):
        """The size goes on the <img>, so nothing on the page moves while it loads."""
        logo = logo_for(provider)

        assert logo["url"] == address
        assert (logo["width"], logo["height"]) == size

    def test_is_served_as_a_static_file(self):
        """From the provider's own folder, so a new provider's logo needs no copy anywhere."""
        found = finders.find("payment-logos/esewa.png")

        assert found and Path(found) == ESewa.logo_file()

    def test_an_svg_without_a_size_is_measured_by_its_view_box(self, tmp_path, monkeypatch):
        logo = tmp_path / "plain.svg"
        logo.write_text('<svg viewBox="0 0 300 100" xmlns="http://www.w3.org/2000/svg"></svg>')
        plain = type("Plain", (ESewa,), {"logo": "plain.svg"})
        monkeypatch.setattr(plain, "logo_file", classmethod(lambda cls: logo))

        assert (logo_for(plain)["width"], logo_for(plain)["height"]) == (300, 100)


def office(address="", phone="", takes_gifts_in_person=True):
    """What ways_to_pay() reads of Site settings."""
    return SimpleNamespace(
        address=address, phone=phone, takes_gifts_in_person=takes_gifts_in_person
    )


class TestWaysToPay:
    """Only a way that works is offered. "Not ready to pay yet" isn't one: it's always there."""

    def test_online_when_a_provider_takes_the_pledge(self, settings):
        settings.PAYMENT_KEYS = KHALTI_KEYS

        assert ways_to_pay(providers_for("NPR", Decimal(2500)), office()) == ["online"]

    def test_not_online_for_an_amount_no_provider_takes(self, settings):
        settings.PAYMENT_KEYS = KHALTI_KEYS

        assert ways_to_pay(providers_for("NPR", Decimal(5)), office()) == []

    def test_not_online_in_a_currency_no_provider_takes(self, settings):
        settings.PAYMENT_KEYS = KHALTI_KEYS

        assert ways_to_pay(providers_for("GBP", Decimal(25)), office()) == []

    @pytest.mark.parametrize(
        "where",
        [{"address": "Ward 4, Thamel"}, {"phone": "+977 1-4567890"}],
        ids=["address", "phone"],
    )
    def test_in_person_with_an_office_address_or_phone(self, settings, where):
        settings.PAYMENT_KEYS = {}

        assert ways_to_pay(providers_for("NPR", Decimal(2500)), office(**where)) == ["in-person"]

    def test_not_in_person_at_an_office_that_takes_no_gifts(self, settings):
        """A charity can show its office in the footer without taking money there."""
        settings.PAYMENT_KEYS = {}
        where = office("Ward 4, Thamel", "+977 1-4567890", takes_gifts_in_person=False)

        assert ways_to_pay(providers_for("NPR", Decimal(2500)), where) == []

    def test_not_in_person_without_an_office_to_pay_at(self, settings):
        settings.PAYMENT_KEYS = {}

        assert ways_to_pay(providers_for("NPR", Decimal(2500)), office()) == []

    def test_both_online_first(self, settings):
        settings.PAYMENT_KEYS = KHALTI_KEYS

        assert ways_to_pay(providers_for("NPR", Decimal(2500)), office(phone="+977 1-4567890")) == [
            "online",
            "in-person",
        ]

    def test_qr_after_online_and_before_in_person(self, settings):
        settings.PAYMENT_KEYS = KHALTI_KEYS
        where = office(phone="+977 1-4567890")

        ways = ways_to_pay(providers_for("NPR", Decimal(2500)), where, qr_codes=["a code"])

        assert ways == ["online", "qr", "in-person"]

    def test_qr_alone_with_no_provider_set_up(self, settings):
        settings.PAYMENT_KEYS = {}

        assert ways_to_pay(providers_for("NPR", Decimal(2500)), office(), ["a code"]) == ["qr"]

    def test_any_amount_when_none_is_given(self, settings):
        """The Donate page says how paying works before anyone chooses an amount."""
        settings.PAYMENT_KEYS = KHALTI_KEYS

        assert ways_to_pay(providers_for("NPR", None), office()) == ["online"]


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


class TestPledgeNumber:
    """The short number a supporter reads out or writes in a payment's remarks, and the team
    searches for. Never a way in: the pay page stays at the reference."""

    def test_each_pledge_gets_its_own_six_digit_number(self, pledge, donate_page):
        other = Pledge.objects.create(
            page=donate_page, amount=1500, currency="NPR", name="Ram", email="ram@example.com"
        )

        assert re.fullmatch(r"[1-9]\d{5}", pledge.number)
        assert other.number != pledge.number

    def test_keeps_its_number_when_saved_again(self, pledge):
        number = pledge.number
        pledge.save()

        assert Pledge.objects.get(pk=pledge.pk).number == number

    def test_is_shown_in_two_groups_of_three(self, pledge):
        pledge.number = "482913"

        assert pledge.display_number() == "482 913"

    def test_a_number_already_taken_is_never_given_again(self, pledge, donate_page, monkeypatch):
        numbers = iter([pledge.number, "482913"])
        monkeypatch.setattr("campaigns.models.new_pledge_number", lambda: next(numbers))

        other = Pledge.objects.create(page=donate_page, amount=1500, currency="NPR", name="Ram")

        assert other.number == "482913"

    def test_gives_up_after_ten_numbers_taken(self, pledge, donate_page, monkeypatch):
        monkeypatch.setattr("campaigns.models.new_pledge_number", lambda: pledge.number)

        with pytest.raises(IntegrityError):
            Pledge.objects.create(page=donate_page, amount=1500, currency="NPR", name="Ram")

    def test_any_other_clash_is_passed_on_without_trying_again(
        self, pledge, donate_page, monkeypatch
    ):
        """The pledge form sends the same copy twice on a double click, and finds the first
        pledge by its submission ID when saving the second clashes."""
        tried = []
        monkeypatch.setattr(
            "campaigns.models.new_pledge_number", lambda: tried.append(1) or "482913"
        )
        pledge.submission_id = uuid.uuid4()
        pledge.save()
        twin = Pledge(page=donate_page, amount=2500, currency="NPR", name="Sita")
        twin.submission_id = pledge.submission_id

        with pytest.raises(IntegrityError):
            twin.save()

        assert len(tried) == 1


class TestGiftCode:
    """The address of a gift's public page (#100): random, so nobody can guess one or count up
    to the next, and never the pay page's reference."""

    def test_each_pledge_gets_its_own_unguessable_code(self, pledge, donate_page):
        other = Pledge.objects.create(page=donate_page, amount=1500, currency="NPR", name="Ram")

        assert re.fullmatch(r"[A-Za-z0-9_-]{12}", pledge.gift_code)  # 72 random bits
        assert other.gift_code != pledge.gift_code
        assert str(pledge.reference) not in pledge.gift_code

    def test_keeps_its_code_when_saved_again(self, pledge):
        code = pledge.gift_code
        pledge.save()

        assert Pledge.objects.get(pk=pledge.pk).gift_code == code

    def test_a_code_already_taken_is_never_given_again(self, pledge, donate_page, monkeypatch):
        codes = iter([pledge.gift_code, "new-gift-code"])
        monkeypatch.setattr("campaigns.models.new_gift_code", lambda: next(codes))

        other = Pledge.objects.create(page=donate_page, amount=1500, currency="NPR", name="Ram")

        assert other.gift_code == "new-gift-code"
        assert other.number != pledge.number


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

    def test_statuses_are_the_payment_packages_and_the_one_only_the_team_gives(self):
        assert [status.value for status in Status] + ["to-confirm"] == sorted(
            PaymentStatus.values, key=lambda value: value == "to-confirm"
        )


class TestNeedsChecking:
    """A pledge a person must look at, worked out from its payments: the list, the export and
    the pledge's page say "Needs checking", with why."""

    def test_money_received_for_an_amount_the_pledge_no_longer_asks(self, pledge):
        payment = pledge.start_payment("esewa", live=False)
        Pledge.objects.filter(pk=pledge.pk).update(amount=10000)
        payment.record(Status.PAID, "000AWEO")

        pledge = Pledge.objects.get(pk=pledge.pk)

        assert pledge.payment_display() == "Needs checking"
        assert pledge.needs_checking() == "Rs 2,500 was received, but the pledge is for Rs 10,000."

    def test_the_team_received_another_amount(self, pledge):
        payment = pledge.payments.create(
            method="qr", amount=2500, currency="NPR", status=PaymentStatus.TO_CONFIRM, live=True
        )
        payment.mark_paid(None, timezone.localdate(), 2000, "RBB-77")

        pledge = Pledge.objects.get(pk=pledge.pk)

        assert pledge.payment_display() == "Needs checking"
        assert pledge.needs_checking() == "Rs 2,000 was received, but the pledge is for Rs 2,500."

    def test_the_provider_refunded_part_of_it(self, pledge, fake_provider):
        fake_provider.outcome = Outcome(Status.WAITING, word="PART_REFUNDED")
        pledge.start_payment("fakepay", live=False).ask()

        pledge = Pledge.objects.get(pk=pledge.pk)

        assert pledge.payment_display() == "Needs checking"
        assert pledge.needs_checking() == "Fake Pay refunded part of it."

    def test_not_a_pledge_paid_in_full(self, pledge):
        pledge.start_payment("esewa", live=True).record(Status.PAID, "000AWEO")

        pledge = Pledge.objects.get(pk=pledge.pk)

        assert pledge.needs_checking() == ""
        assert pledge.payment_display() == "Paid"

    def test_not_a_pledge_nobody_has_paid(self, pledge):
        assert pledge.needs_checking() == ""
        assert pledge.payment_display() == "Waiting"


def steps(payment):
    return [(step.kind, step.word, step.by) for step in payment.steps.all()]


class TestAskingTheProvider:
    """Payment.ask(), the one way the site asks a provider about a payment: from the payer's
    return, the team's check and a scheduled check alike. Each ask is a step in its history."""

    @pytest.fixture
    def payment(self, pledge, fake_provider):
        return pledge.start_payment("fakepay", live=False)

    def test_records_the_answer_with_the_providers_word(self, payment, fake_provider):
        fake_provider.outcome = Outcome(Status.FAILED, word="CANCELLED")

        outcome = payment.ask()

        assert outcome.status is Status.FAILED
        assert Payment.objects.get(pk=payment.pk).status == PaymentStatus.FAILED
        assert steps(payment) == [(StepKind.ASKED, "CANCELLED", None)]

    def test_asks_with_our_own_reference_and_amount(self, payment, fake_provider):
        payment.ask()

        assert fake_provider.checked == [(str(payment.reference), Decimal(2500), "")]

    def test_every_ask_is_a_step_even_with_the_same_answer(self, payment, fake_provider):
        """So the history shows each time someone asked, though nothing changed."""
        fake_provider.outcome = Outcome(Status.WAITING, word="PENDING")

        payment.ask()
        payment.ask()

        assert steps(payment) == [(StepKind.ASKED, "PENDING", None)] * 2

    def test_records_who_asked(self, payment, django_user_model):
        sita = django_user_model.objects.create_user(username="sita")

        payment.ask(by=sita)

        assert steps(payment) == [(StepKind.ASKED, "DONE", sita)]

    def test_never_stores_a_word_the_provider_isnt_known_to_use(self, payment, fake_provider):
        """Only a provider's known words are stored: anything else could be the payer's own
        details."""
        fake_provider.outcome = Outcome(Status.WAITING, word="Paid by 9841234567")

        payment.ask()

        assert steps(payment) == [(StepKind.ASKED, "", None)]

    @pytest.mark.parametrize(
        ("error", "kind"),
        [
            (ProviderUnavailable("Timed out asking for 9841234567"), StepKind.UNREACHABLE),
            (UnreadableAnswer("Answered {'mobile': '9841234567'}"), StepKind.UNREADABLE),
            (ProviderRefused("Refused 9841234567's payment"), StepKind.REFUSED),
            (ValueError("Needs 9841234567's pidx"), StepKind.NOT_ASKED),
        ],
        ids=["unreachable", "unreadable", "refused", "can't ask"],
    )
    def test_an_error_is_a_step_without_its_text(self, payment, fake_provider, error, kind):
        """An error's text can quote the provider's reply, which can hold the payer's details:
        it goes to the log, never into the history."""
        fake_provider.failure = error

        assert payment.ask() is None

        assert steps(payment) == [(kind, "", None)]
        assert "9841234567" not in str(list(PaymentStep.objects.values()))
        assert Payment.objects.get(pk=payment.pk).status == PaymentStatus.WAITING

    @pytest.mark.parametrize("case", ["provider gone", "other mode"])
    def test_a_provider_that_cant_be_asked_isnt(self, payment, fake_provider, settings, case):
        """One no longer set up, or set up for the other system (test or live), whose keys can't
        look up this payment."""
        if case == "provider gone":
            settings.PAYMENT_KEYS = {}
        else:
            settings.LIVE_PAYMENTS = True

        assert payment.ask() is None

        assert fake_provider.checked == []
        assert steps(payment) == [(StepKind.NOT_ASKED, "", None)]

    def test_keeps_the_providers_latest_word(self, payment, fake_provider):
        """So the list of pledges can say one needs checking without reading every step."""
        fake_provider.outcome = Outcome(Status.WAITING, word="PENDING")
        payment.ask()
        fake_provider.outcome = Outcome(Status.FAILED, word="CANCELLED")
        payment.ask()

        assert Payment.objects.get(pk=payment.pk).word == "CANCELLED"

    def test_an_answer_with_an_unknown_word_forgets_the_last_one(self, payment, fake_provider):
        fake_provider.outcome = Outcome(Status.WAITING, word="PART_REFUNDED")
        payment.ask()
        fake_provider.outcome = Outcome(Status.WAITING, word="Paid by 9841234567")
        payment.ask()

        assert Payment.objects.get(pk=payment.pk).word == ""

    def test_no_answer_keeps_the_last_word(self, payment, fake_provider):
        fake_provider.outcome = Outcome(Status.WAITING, word="PENDING")
        payment.ask()
        fake_provider.failure = ProviderUnavailable("Timed out")
        payment.ask()

        assert Payment.objects.get(pk=payment.pk).word == "PENDING"

    def test_steps_are_kept_in_the_order_they_happened(self, payment):
        payment.add_step(StepKind.SENT)
        payment.add_step(StepKind.CAME_BACK)
        payment.ask()

        assert [kind for kind, _, _ in steps(payment)] == [
            StepKind.SENT,
            StepKind.CAME_BACK,
            StepKind.ASKED,
        ]
