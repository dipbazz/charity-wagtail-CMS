"""The per-visitor limits on the Donate page's routes that write or call a provider (#226): what
counts, what a supporter sees over the limit, and that nothing is saved or asked then. The
counting itself is core/tests/test_limits.py's."""

import copy
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from campaigns.models import Payment, PaymentStatus, Pledge, StepKind
from campaigns.tests.test_pay import VALID, pay_url, send_pledge, soup, start, text
from campaigns.tests.test_qr import card, make_code, qr_url
from core.models import SiteSettings
from nepal_payments import Outcome, ProviderUnavailable, Status

pytestmark = pytest.mark.django_db


@pytest.fixture
def limits(settings, monkeypatch):
    """Set one action's limit; the others keep their defaults. Tried as a window starts."""
    settings.LIMITS_WINDOW = 300
    monkeypatch.setattr("core.limits.wait_seconds", lambda: 300)
    settings.LIMITS = {"pledge": 10, "start_payment": 10, "qr_paid": 5, "payment_return": 30}

    def set_limit(action, limit):
        settings.LIMITS = {**settings.LIMITS, action: limit}

    return set_limit


@pytest.fixture
def phone(site):
    site_settings = SiteSettings.for_site(site)
    site_settings.phone = "+977 1-4567890"
    site_settings.save()


def return_url(donate_page, payment):
    return f"{donate_page.url}payment/{payment.reference}/"


def assert_stopped(response):
    assert response.status_code == 429
    assert response["Retry-After"] == "300"
    assert "no-cache" in response["Cache-Control"]


def assert_counts_down(response):
    """The wait in minutes and seconds, which donate.js shows and counts down; the minutes in
    the words are what's left as the page is made, for a browser without JavaScript. Only the
    end is said to screen readers, not each second."""
    countdown = soup(response).select_one("[data-countdown]")
    assert countdown["data-countdown"] == "300" and countdown.has_attr("hidden")
    ticking = countdown.select_one("[data-countdown-left]")
    assert ticking["aria-hidden"] == "true"
    assert " ".join(ticking.get_text().split()) == "Time left:"
    assert countdown.select_one("[data-countdown-time]")
    done = countdown.select_one("[data-countdown-done]")
    assert done["role"] == "status" and done.get_text() == ""
    assert done["data-done-text"] == "You can try again now."


def shown_words(element):
    """Its words as a browser without JavaScript shows them: not what starts hidden."""
    element = copy.copy(element)
    for hidden in element.select("[hidden]"):
        hidden.decompose()
    return " ".join(element.get_text().split())


def notice(response):
    """The neutral box saying to wait, not a red box saying what to check."""
    return soup(response).select_one(".payment-message:not(.is-problem)[data-focus-on-load]")


class TestThePledgeForm:
    def test_over_the_limit_saves_nothing_and_keeps_the_answers(
        self, client, donate_page, fake_provider, limits
    ):
        limits("pledge", 0)

        response = send_pledge(client, donate_page)

        assert_stopped(response)
        assert not Pledge.objects.exists()
        assert soup(response).find("input", {"name": "name"})["value"] == "Sita Sharma"
        box = notice(response)
        assert box["role"] == "alert" and box["tabindex"] == "-1"
        assert shown_words(box) == (
            "Your pledge hasn't been sent yet "
            "We've had a lot of tries from your internet connection just now. Wait 5 minutes, "
            "then press Continue to payment again. Your answers are still here."
        )
        assert_counts_down(response)

    def test_names_the_form_s_own_button_when_there_s_no_way_to_pay(
        self, client, donate_page, limits
    ):
        limits("pledge", 0)

        response = send_pledge(client, donate_page)

        assert "then press Send my pledge again." in text(response)

    def test_a_mistake_is_shown_again_without_counting(self, client, donate_page, limits):
        limits("pledge", 0)

        response = send_pledge(client, donate_page, email="not-an-email")

        assert response.status_code == 200
        assert notice(response) is None

    def test_sending_the_same_copy_again_updates_its_pledge_without_counting(
        self, client, donate_page, limits
    ):
        sent = {"submission_id": "5f0c6c1e-1d7b-4d0f-9a43-0b1e2f3a4b5c"}
        send_pledge(client, donate_page, **sent)
        limits("pledge", 0)

        response = send_pledge(client, donate_page, name="Sita S.", **sent)

        assert response.status_code == 303
        assert Pledge.objects.get().name == "Sita S."

    def test_a_blocked_send_costs_no_more_queries_than_a_mistake(
        self, client, donate_page, fake_provider, limits, django_assert_max_num_queries
    ):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        send_pledge(client, donate_page, email="not-an-email")  # fills caches
        with CaptureQueriesContext(connection) as mistake:
            send_pledge(client, donate_page, email="not-an-email")
        limits("pledge", 0)

        with django_assert_max_num_queries(len(mistake)):
            send_pledge(client, donate_page)


class TestStartingAPayment:
    @pytest.fixture
    def pledge(self, client, donate_page, fake_provider):
        send_pledge(client, donate_page)
        return Pledge.objects.get()

    def test_over_the_limit_asks_no_provider_and_says_how_long_to_wait(
        self, client, donate_page, pledge, fake_provider, limits, phone
    ):
        limits("start_payment", 0)

        response = start(client, donate_page, pledge)

        assert_stopped(response)
        assert not Payment.objects.exists()
        assert fake_provider.started == []
        page = soup(response)
        assert page.title.get_text().strip().startswith("Please wait 5 minutes")
        assert page.h1.get_text() == "Please wait 5 minutes"
        first = page.select_one("main p[data-focus-on-load]")
        assert " ".join(first.get_text().split()) == (
            "We've had a lot of tries from your internet connection just now. After the wait, go "
            "back to your pledge."
        )
        assert (
            "If money has left your account, don't pay again. Call us and we'll look into it:"
            in text(response)
        )
        assert page.find("a", href="tel:+97714567890")
        back = page.find("a", string="Back to your pledge")
        assert back["href"] == pay_url(donate_page, pledge)
        assert_counts_down(response)

    def test_going_back_to_the_attempt_just_started_isn_t_counted(
        self, client, donate_page, pledge, fake_provider, limits
    ):
        start(client, donate_page, pledge)
        limits("start_payment", 0)

        response = start(client, donate_page, pledge)

        assert response.status_code == 303
        assert "/go/" in response["Location"]
        assert len(fake_provider.started) == 1

    def test_a_paid_pledge_goes_to_its_thanks_without_counting(
        self, client, donate_page, pledge, limits
    ):
        pledge.start_payment("fakepay", live=False).record(PaymentStatus.PAID, "FAKE-1")
        limits("start_payment", 0)

        assert start(client, donate_page, pledge).status_code == 303

    def test_the_way_to_the_provider_s_page_is_never_counted(
        self, client, donate_page, pledge, fake_provider, limits
    ):
        start(client, donate_page, pledge)
        payment = Payment.objects.get()
        limits("start_payment", 0)
        limits("payment_return", 0)

        response = client.get(f"{donate_page.url}payment/{payment.reference}/go/")

        assert response.status_code == 303
        assert response["Location"] == fake_provider.redirect.url


class TestComingBackFromTheProvider:
    @pytest.fixture
    def payment(self, client, donate_page, fake_provider):
        send_pledge(client, donate_page)
        start(client, donate_page, Pledge.objects.get())
        return Payment.objects.get()

    def test_the_first_return_is_always_asked(
        self, client, donate_page, payment, fake_provider, limits
    ):
        """A payer who really paid is never left unconfirmed by others on their connection.
        Each payment comes back first only once, and starting one is counted."""
        limits("payment_return", 0)
        fake_provider.outcome = Outcome(Status.PAID, "FAKE-123", word="DONE")

        response = client.get(return_url(donate_page, payment))

        assert response.status_code == 303
        assert len(fake_provider.checked) == 1
        assert Pledge.objects.get().has_paid_payment()

    def test_over_the_limit_a_later_check_asks_no_provider(
        self, client, donate_page, payment, fake_provider, limits
    ):
        fake_provider.outcome = Outcome(Status.WAITING, "", word="PENDING")
        client.get(return_url(donate_page, payment))
        limits("payment_return", 0)

        response = client.get(return_url(donate_page, payment))

        assert_stopped(response)
        assert len(fake_provider.checked) == 1
        assert payment.steps.filter(kind=StepKind.CAME_BACK).count() == 1
        assert soup(response).h1.get_text() == "Please wait 5 minutes"

    def test_the_wait_page_is_never_indexed_and_stays_within_the_pay_pages_budget(
        self, client, donate_page, payment, fake_provider, limits, django_assert_max_num_queries
    ):
        """The pay pages' 15 (test_pay.py). Starting a payment spends three more before it
        knows a try is one too many: the payments it checks for one paid, held or to go back to."""
        fake_provider.outcome = Outcome(Status.WAITING, "", word="PENDING")
        client.get(return_url(donate_page, payment))  # the first return, and fills caches
        limits("payment_return", 0)
        client.get(return_url(donate_page, payment))

        with django_assert_max_num_queries(15):
            response = client.get(return_url(donate_page, payment))

        assert soup(response).find("meta", attrs={"name": "robots"})["content"] == "noindex"

    def test_a_paid_payment_isn_t_counted(self, client, donate_page, payment, limits):
        payment.record(PaymentStatus.PAID, "FAKE-1")
        limits("payment_return", 0)

        assert client.get(return_url(donate_page, payment)).status_code == 303


class TestSayingItsPaidByQR:
    @pytest.fixture
    def code(self):
        return make_code("eSewa", account_number="9801234567")

    @pytest.fixture
    def pledge(self, donate_page):
        return Pledge.objects.create(
            page=donate_page, amount=2500, currency="NPR", name="Sita", email="sita@example.com"
        )

    def test_over_the_limit_saves_nothing_and_keeps_the_transaction_id(
        self, client, donate_page, pledge, code, limits, phone
    ):
        limits("qr_paid", 0)

        response = client.post(
            qr_url(donate_page, pledge, "paid/"),
            {
                "code": code.pk,
                "transaction_id": "TXN-8841",
                "receipt": SimpleUploadedFile("receipt.png", card().read()),
            },
        )

        assert_stopped(response)
        assert not Payment.objects.exists()
        page = soup(response)
        assert page.find("input", {"name": "transaction_id"})["value"] == "TXN-8841"
        box = notice(response)
        assert box["role"] == "alert" and box["tabindex"] == "-1"
        assert shown_words(box) == (
            "We haven't got your message yet: we've had a lot of tries from your internet "
            "connection just now. Wait 5 minutes, then choose your screenshot again if you're "
            "sending one, and press I've paid. If money has left your account, don't pay "
            "again. Call us and we'll look into it: +977 1-4567890"
        )
        assert_counts_down(response)

    def test_a_mistake_is_shown_again_without_counting(
        self, client, donate_page, pledge, code, limits
    ):
        limits("qr_paid", 0)

        response = client.post(qr_url(donate_page, pledge, "paid/"), {"transaction_id": ""})

        assert response.status_code == 422
        assert notice(response) is None


class TestTheWaitIsOneReading:
    """The window can end between two readings of the clock. Whatever a page says about the wait
    (its words, its countdown, Retry-After) comes from one reading, so they agree."""

    @pytest.fixture
    def window_ends_after_one_second(self, limits, monkeypatch):
        reads = iter([1])
        monkeypatch.setattr("core.limits.wait_seconds", lambda: next(reads, 300))

    def assert_agrees(self, response):
        assert response["Retry-After"] == "1"
        assert soup(response).select_one("[data-countdown]")["data-countdown"] == "1"
        assert re.search(r"[Ww]ait 1 minute\b", text(response))

    def test_the_pledge_form(self, client, donate_page, limits, window_ends_after_one_second):
        limits("pledge", 0)

        self.assert_agrees(send_pledge(client, donate_page))

    def test_the_wait_page(
        self, client, donate_page, fake_provider, limits, window_ends_after_one_second
    ):
        send_pledge(client, donate_page)
        limits("start_payment", 0)

        self.assert_agrees(start(client, donate_page, Pledge.objects.get()))

    def test_the_qr_form(self, client, donate_page, limits, window_ends_after_one_second):
        code = make_code("eSewa", account_number="9801234567")
        pledge = Pledge.objects.create(
            page=donate_page, amount=2500, currency="NPR", name="Sita", email="sita@example.com"
        )
        limits("qr_paid", 0)

        response = client.post(
            qr_url(donate_page, pledge, "paid/"), {"code": code.pk, "transaction_id": "TXN-8841"}
        )

        self.assert_agrees(response)


def test_a_supporter_paying_normally_never_waits(client, donate_page, fake_provider, settings):
    """With the defaults: the pledge, a provider that couldn't start, a second try, back from the
    provider before it's done, two more checks, and paid."""
    assert settings.LIMITS_WINDOW == 300
    responses = [send_pledge(client, donate_page)]
    pledge = Pledge.objects.get()
    fake_provider.failure = ProviderUnavailable("down")
    responses.append(start(client, donate_page, pledge))
    fake_provider.failure = None
    responses.append(start(client, donate_page, pledge))
    payment = Payment.objects.filter(status=PaymentStatus.WAITING).get()
    fake_provider.outcome = Outcome(Status.WAITING, "", word="PENDING")
    responses += [client.get(return_url(donate_page, payment)) for _ in range(3)]
    fake_provider.outcome = Outcome(Status.PAID, "FAKE-123", word="DONE")
    responses.append(client.get(return_url(donate_page, payment)))

    assert [r.status_code for r in responses if r.status_code == 429] == []
    assert Pledge.objects.get().has_paid_payment()


def test_nothing_else_is_counted(client, donate_page, fake_provider, settings):
    """Reading the pay pages, or sending the pledge form with a mistake, never adds up."""
    settings.LIMITS = dict.fromkeys(settings.LIMITS, 0)
    send_pledge(client, donate_page, **{**VALID, "email": "x"})

    assert client.get(donate_page.url).status_code == 200
