"""Paying a pledge online (#93): from the pledge form to a provider and back.

The flow is tested with FakePay (conftest.py), so it holds for any provider; eSewa and Khalti each
get one journey end to end at the bottom, with their servers stood in for.
"""

import datetime
import re
import uuid
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Locale

from campaigns.models import CampaignIndexPage, Payment, PaymentStatus, Pledge, StepKind
from core.models import SiteSettings, SiteSettingsText
from nepal_payments import (
    Outcome,
    ProviderRefused,
    ProviderUnavailable,
    Redirect,
    Status,
    UnreadableAnswer,
    http,
)

pytestmark = pytest.mark.django_db

VALID = {
    "amount": "2500",
    "other_amount": "",
    "frequency": "one-off",
    "name": "Sita Sharma",
    "email": "sita@example.com",
    "phone_country": "NP",
    "phone": "",
    "appeal": "flood-relief",
    "address": "",
    "postcode": "",
}


def send_pledge(client, donate_page, **changes):
    return client.post(donate_page.url, {**VALID, **changes})


def soup(response):
    return BeautifulSoup(response.content, "html.parser")


def text(response):
    return " ".join(soup(response).get_text().split())


@pytest.fixture
def pledge(client, donate_page, fake_provider):
    """A pledge just sent, with FakePay set up to take it."""
    send_pledge(client, donate_page)
    return Pledge.objects.get()


def pay_url(donate_page, pledge):
    return f"{donate_page.url}pay/{pledge.reference}/"


def start(client, donate_page, pledge, method="fakepay"):
    return client.post(f"{pay_url(donate_page, pledge)}{method}/")


def return_url(donate_page, payment):
    return f"{donate_page.url}payment/{payment.reference}/"


def kinds(payment):
    return [step.kind for step in payment.steps.all()]


def pay_buttons(response):
    return [button.get_text(strip=True) for button in soup(response).select("form button")]


class TestAfterSendingAPledge:
    def test_goes_to_its_pay_page_when_a_provider_can_take_it(self, client, donate_page, pledge):
        response = send_pledge(client, donate_page, name="Ram")

        assert response.status_code == 303
        ram = Pledge.objects.get(name="Ram")
        assert response["Location"] == pay_url(donate_page, ram)

    def test_goes_to_the_thank_you_page_when_none_is_set_up(self, client, donate_page, settings):
        settings.PAYMENT_KEYS = {}

        response = send_pledge(client, donate_page)

        assert response["Location"] == donate_page.url + "thank-you/"

    def test_goes_to_the_thank_you_page_for_an_amount_none_takes(
        self, client, donate_page, fake_provider
    ):
        response = send_pledge(client, donate_page, amount="other", other_amount="5")

        assert response["Location"] == donate_page.url + "thank-you/"


class TestPayPage:
    def test_shows_the_gift_and_nothing_about_the_giver(self, client, donate_page, pledge):
        page = text(client.get(pay_url(donate_page, pledge)))

        assert "Pay your gift" in page
        assert "Rs 2,500" in page
        assert "Flood relief" in page
        assert "Sita" not in page
        assert "sita@example.com" not in page

    def test_a_gift_for_wherever_its_needed_most_says_so(self, client, donate_page, fake_provider):
        send_pledge(client, donate_page, appeal="")

        page = text(client.get(pay_url(donate_page, Pledge.objects.get())))

        assert "Wherever it's needed most" in page

    def test_a_monthly_gift_pays_this_months_gift(self, client, donate_page, fake_provider):
        send_pledge(client, donate_page, frequency="monthly")

        page = text(client.get(pay_url(donate_page, Pledge.objects.get())))

        assert "Rs 2,500 a month" in page
        assert "this month's gift" in page

    def test_offers_each_provider_set_up_here(self, client, donate_page, pledge):
        response = client.get(pay_url(donate_page, pledge))

        form = soup(response).find("button", string="Pay with Fake Pay").find_parent("form")
        assert form["method"] == "post"
        assert form["action"] == f"{pay_url(donate_page, pledge)}fakepay/"
        assert form.find("input", attrs={"name": "csrfmiddlewaretoken"})

    def test_names_whose_page_the_payer_will_pay_on(self, client, donate_page, pledge, settings):
        settings.PAYMENT_KEYS = {**settings.PAYMENT_KEYS, "KHALTI_SECRET_KEY": "test-key"}

        page = text(client.get(pay_url(donate_page, pledge)))

        assert "You'll pay on the secure page of Khalti or Fake Pay, then come back here." in page

    def test_never_shows_a_test_account(self, client, donate_page, pledge):
        """It pushed the pay buttons down, and handed anyone a way to make test payments: the
        team finds the test accounts in the docs instead."""
        page = text(client.get(pay_url(donate_page, pledge)))

        assert "9800000001" not in page  # FakePay's test account

    def test_says_when_no_money_moves(self, client, donate_page, pledge):
        """Before a charity goes live, a real supporter can reach this page: one sentence, so the
        buttons stay where they are."""
        section = soup(client.get(pay_url(donate_page, pledge))).find(id="pay-online").parent

        assert "Online payments are in test mode here: no money will be taken." in " ".join(
            section.get_text().split()
        )

    def test_says_nothing_of_test_mode_once_live(self, client, donate_page, pledge, settings):
        settings.LIVE_PAYMENTS = True

        assert "test mode" not in text(client.get(pay_url(donate_page, pledge)))

    def test_is_kept_out_of_search_engines(self, client, donate_page, pledge):
        robots = soup(client.get(pay_url(donate_page, pledge))).find(
            "meta", attrs={"name": "robots"}
        )

        assert robots["content"] == "noindex"

    def test_loads_the_donate_pages_stylesheet(self, client, donate_page, pledge):
        links = soup(client.get(pay_url(donate_page, pledge))).find_all("link", rel="stylesheet")

        assert any(link["href"].endswith("/donate.css") for link in links)

    def test_stays_within_its_query_budget(
        self, client, donate_page, pledge, django_assert_max_num_queries
    ):
        """What every page with a header spends (charity/tests/test_query_budgets.py), plus two:
        the pledge with its appeal, and its payments."""
        client.get(pay_url(donate_page, pledge))  # the first visit fills caches

        with django_assert_max_num_queries(14):
            client.get(pay_url(donate_page, pledge))

    def test_an_unknown_pledge_isnt_found(self, client, donate_page, fake_provider):
        assert client.get(f"{donate_page.url}pay/{uuid.uuid4()}/").status_code == 404


class TestWhatScreenReadersHearFirst:
    """Each state has its own page title, and its message comes straight after the heading,
    ready for donate.js to move focus to it, so it's the first thing read."""

    STATES = {
        "ready": "Pay your gift",
        "check first": "Check your payment",
        "failed": "Try paying again",
        "paid": "Thank you",
    }

    @pytest.fixture
    def page_in(self, client, donate_page, pledge):
        def page_in(state):
            if state == "check first":
                pledge.start_payment("fakepay", live=False)
            elif state == "failed":
                pledge.start_payment("fakepay", live=False).record(Status.FAILED)
            elif state == "paid":
                pledge.start_payment("fakepay", live=False).record(Status.PAID, "FAKE-1")
            return soup(client.get(pay_url(donate_page, pledge)))

        return page_in

    @pytest.mark.parametrize("state", STATES)
    def test_each_state_has_its_own_title(self, page_in, state):
        assert page_in(state).title.get_text(" ", strip=True).startswith(self.STATES[state])

    @pytest.mark.parametrize("state", ["check first", "failed", "paid"])
    def test_the_message_comes_first_and_takes_focus(self, page_in, state):
        message = page_in(state).find("h1").find_next_sibling()

        assert message.has_attr("data-focus-on-load")
        assert message["tabindex"] == "-1"

    def test_with_nothing_to_say_nothing_takes_focus(self, page_in):
        assert page_in("ready").find(attrs={"data-focus-on-load": True}) is None


class TestPayInPerson:
    def test_gives_the_charitys_address_and_phone(self, client, site, donate_page, pledge):
        site_settings = SiteSettings.for_site(site)
        site_settings.phone = "+977 1-4567890"
        site_settings.texts = [
            SiteSettingsText(locale=Locale.get_default(), address="Ward 4\nThamel, Kathmandu")
        ]
        site_settings.save()

        section = soup(client.get(pay_url(donate_page, pledge))).find(id="pay-in-person").parent

        assert section.find("address").get_text(" ", strip=True) == "Ward 4 Thamel, Kathmandu"
        assert section.find("a", href="tel:+97714567890").get_text() == "+977 1-4567890"

    def test_without_them_says_well_be_in_touch(self, client, donate_page, pledge):
        section = soup(client.get(pay_url(donate_page, pledge))).find(id="pay-in-person").parent

        assert "we'll contact you about how to pay" in section.get_text()

    def test_can_finish_without_paying_online(self, client, donate_page, pledge):
        section = soup(client.get(pay_url(donate_page, pledge))).find(id="pay-in-person").parent

        assert section.find("a", href=donate_page.url + "thank-you/")


class TestStartingAPayment:
    def test_sends_the_payer_to_the_provider(self, client, donate_page, pledge):
        response = start(client, donate_page, pledge)

        assert response.status_code == 303
        assert response["Location"] == "https://pay.example.com/fakepay/"

    def test_records_the_attempt_and_the_providers_id(self, client, donate_page, pledge):
        start(client, donate_page, pledge)

        payment = Payment.objects.get()
        assert (payment.method, payment.amount, payment.currency) == ("fakepay", 2500, "NPR")
        assert payment.status == PaymentStatus.WAITING
        assert payment.provider_id == "fake-id"
        assert payment.live is False

    def test_tells_the_provider_where_to_send_the_payer_back(
        self, client, donate_page, pledge, fake_provider
    ):
        start(client, donate_page, pledge)

        payment = Payment.objects.get()
        [request] = fake_provider.started
        assert request.reference == str(payment.reference)
        assert request.amount == Decimal(2500)
        assert request.currency == "NPR"
        assert request.return_url == "http://testserver" + return_url(donate_page, payment)
        assert request.website_url == "http://testserver/"
        assert "Flood relief" in request.description

    def test_a_live_payment_is_recorded_as_live(self, client, donate_page, pledge, settings):
        settings.LIVE_PAYMENTS = True

        start(client, donate_page, pledge)

        assert Payment.objects.get().live is True

    def test_a_provider_that_takes_a_form_gets_one_that_sends_itself(
        self, client, donate_page, pledge, fake_provider
    ):
        fake_provider.redirect = Redirect(
            "https://pay.example.com/form/", method="POST", fields={"amount": "2500", "sig": "x"}
        )

        response = start(client, donate_page, pledge)

        # Post/Redirect/Get: Back from the provider reloads a page, never resends a form.
        payment = Payment.objects.get()
        assert response.status_code == 303
        assert response["Location"] == f"{return_url(donate_page, payment)}go/"
        response = client.get(response["Location"])
        assert response.status_code == 200
        form = soup(response).find("form", attrs={"data-auto-submit": True})
        assert form["action"] == "https://pay.example.com/form/"
        assert form["method"] == "post"
        sent = {field["name"]: field["value"] for field in form.find_all("input")}
        assert sent == {"amount": "2500", "sig": "x"}  # and never our CSRF token
        assert form.find("button").get_text(strip=True) == "Continue to Fake Pay"
        status = soup(response).find(attrs={"role": "status"}, string=re.compile("Taking"))
        assert status.get_text(strip=True) == (
            "Taking you to Fake Pay. If nothing happens, press the button."
        )

    def test_once_paid_the_providers_form_isnt_sent_again(
        self, client, donate_page, pledge, fake_provider
    ):
        fake_provider.redirect = Redirect("https://pay.example.com/form/", method="POST")
        go = start(client, donate_page, pledge)["Location"]
        Payment.objects.get().record(Status.PAID, "FAKE-1")

        response = client.get(go)

        assert response["Location"] == pay_url(donate_page, pledge)

    def test_once_paid_another_way_the_providers_form_isnt_sent_again(
        self, client, donate_page, pledge, fake_provider
    ):
        """Back through history to a form not sent yet, after paying with another provider,
        would take the money twice."""
        fake_provider.redirect = Redirect("https://pay.example.com/form/", method="POST")
        go = start(client, donate_page, pledge)["Location"]
        pledge.start_payment("fakepay", live=False).record(Status.PAID, "FAKE-2")

        response = client.get(go)

        assert response.status_code == 303
        assert response["Location"] == pay_url(donate_page, pledge)

    def test_money_received_for_an_older_amount_isnt_asked_for_again(
        self, client, donate_page, pledge
    ):
        payment = pledge.start_payment("fakepay", live=False)
        Pledge.objects.filter(pk=pledge.pk).update(amount=5000)  # changed since, in the admin
        payment.record(Status.PAID, "FAKE-1")

        response = start(client, donate_page, pledge)

        assert response["Location"] == pay_url(donate_page, pledge)
        assert Payment.objects.count() == 1

    def test_a_second_tap_goes_back_to_the_same_attempt(
        self, client, donate_page, pledge, fake_provider
    ):
        """Two tabs, no JavaScript to hold the button, or a resent form: two attempts could both
        be paid."""
        start(client, donate_page, pledge)

        response = start(client, donate_page, pledge)

        payment = Payment.objects.get()
        assert len(fake_provider.started) == 1
        assert response["Location"] == f"{return_url(donate_page, payment)}go/"
        response = client.get(response["Location"])
        assert response.status_code == 303
        assert response["Location"] == "https://pay.example.com/fakepay/"

    def test_a_second_tap_sends_the_same_form_again(
        self, client, donate_page, pledge, fake_provider
    ):
        fake_provider.redirect = Redirect(
            "https://pay.example.com/form/", method="POST", fields={"sig": "x"}
        )
        first = start(client, donate_page, pledge)["Location"]

        second = start(client, donate_page, pledge)["Location"]

        assert second == first
        assert len(fake_provider.started) == 1

    def test_after_ten_minutes_a_new_attempt_starts(
        self, client, donate_page, pledge, fake_provider
    ):
        """By then the provider's page may have expired."""
        start(client, donate_page, pledge)
        Payment.objects.update(created_at=timezone.now() - datetime.timedelta(minutes=11))

        start(client, donate_page, pledge)

        assert Payment.objects.count() == 2
        assert len(fake_provider.started) == 2

    @pytest.mark.parametrize(
        "other", [{"method": "khalti"}, {"live": True}], ids=["another provider", "live"]
    )
    def test_an_attempt_another_way_isnt_reused(
        self, client, donate_page, pledge, fake_provider, other
    ):
        waiting = pledge.start_payment(**{"method": "fakepay", "live": False, **other})
        Payment.objects.filter(pk=waiting.pk).update(
            provider_form={"url": "https://pay.example.com/old/", "method": "GET", "fields": {}}
        )

        start(client, donate_page, pledge)

        assert Payment.objects.count() == 2
        assert len(fake_provider.started) == 1

    def test_only_by_sending_the_form(self, client, donate_page, pledge):
        response = client.get(f"{pay_url(donate_page, pledge)}fakepay/")

        assert response.status_code == 405
        assert not Payment.objects.exists()

    @pytest.mark.parametrize("method", ["esewa", "nosuchpay"])
    def test_a_provider_not_set_up_here_isnt_found(self, client, donate_page, pledge, method):
        assert start(client, donate_page, pledge, method).status_code == 404
        assert not Payment.objects.exists()

    def test_a_paid_pledge_isnt_paid_again(self, client, donate_page, pledge):
        pledge.start_payment("fakepay", live=False).record(Status.PAID, "FAKE-1")

        response = start(client, donate_page, pledge)

        assert response["Location"] == pay_url(donate_page, pledge)
        assert Payment.objects.count() == 1

    def test_a_provider_that_cant_be_reached_lets_the_payer_try_again(
        self, client, donate_page, pledge, fake_provider
    ):
        fake_provider.failure = ProviderUnavailable("Fake Pay is down.")

        response = start(client, donate_page, pledge)

        assert response["Location"] == pay_url(donate_page, pledge)
        assert Payment.objects.get().status == PaymentStatus.FAILED
        page = client.get(pay_url(donate_page, pledge))
        assert "We couldn't reach Fake Pay just now. Try again in a few minutes." in text(page)
        assert "didn't go through" not in text(page)
        assert "Pay with Fake Pay" in pay_buttons(page)

    def test_a_provider_that_cant_be_reached_suggests_the_others(
        self, client, donate_page, pledge, fake_provider, settings
    ):
        settings.PAYMENT_KEYS = {**settings.PAYMENT_KEYS, "KHALTI_SECRET_KEY": "test-key"}
        fake_provider.failure = ProviderUnavailable("Fake Pay is down.")

        page = client.get(start(client, donate_page, pledge)["Location"])

        assert (
            "We couldn't reach Fake Pay just now. Try Khalti, or try again in a few minutes."
            in (text(page))
        )

    def test_records_that_the_payer_was_sent_to_the_provider(self, client, donate_page, pledge):
        start(client, donate_page, pledge)

        assert kinds(Payment.objects.get()) == [StepKind.SENT]

    @pytest.mark.parametrize(
        ("error", "kind"),
        [
            (ProviderUnavailable("Fake Pay is down."), StepKind.UNREACHABLE),
            (UnreadableAnswer("Fake Pay answered nonsense."), StepKind.UNREADABLE),
            (ProviderRefused("Fake Pay refused the key."), StepKind.REFUSED),
        ],
        ids=["unreachable", "unreadable", "refused"],
    )
    def test_records_why_it_couldnt_start(
        self, client, donate_page, pledge, fake_provider, error, kind
    ):
        fake_provider.failure = error

        start(client, donate_page, pledge)

        assert kinds(Payment.objects.get()) == [kind]


class TestComingBack:
    @pytest.fixture
    def payment(self, client, donate_page, pledge):
        start(client, donate_page, pledge)
        return Payment.objects.get()

    def test_a_paid_payment_says_thank_you(self, client, donate_page, pledge, settings):
        settings.LIVE_PAYMENTS = True
        payment = pledge.start_payment("fakepay", live=True)

        response = client.get(return_url(donate_page, payment))

        assert response.status_code == 303
        assert response["Location"] == pay_url(donate_page, pledge)
        pledge.refresh_from_db()
        assert pledge.payment_status == PaymentStatus.PAID
        assert pledge.paid_at is not None
        page = client.get(pay_url(donate_page, pledge))
        assert soup(page).find(class_="lead").get_text() == "Your gift of Rs 2,500 has reached us."
        assert "FAKE-123" in text(page)
        assert "test" not in text(page).lower()
        assert pay_buttons(page) == []

    def test_a_test_payment_says_first_that_no_money_was_taken(
        self, client, donate_page, pledge, payment
    ):
        """Not "has reached us": it hasn't."""
        client.get(return_url(donate_page, payment))

        page = client.get(pay_url(donate_page, pledge))

        lead = soup(page).find(class_="lead").get_text()
        assert lead == "Test payment completed. No money was taken."
        assert "reached us" not in text(page)

    def test_a_monthly_gift_thanks_for_this_month(
        self, client, donate_page, fake_provider, settings
    ):
        """Only this month's gift is paid: nothing is set up for next month."""
        settings.LIVE_PAYMENTS = True
        send_pledge(client, donate_page, frequency="monthly")
        pledge = Pledge.objects.get()
        client.get(return_url(donate_page, pledge.start_payment("fakepay", live=True)))

        page = client.get(pay_url(donate_page, pledge))

        assert soup(page).find(class_="lead").get_text() == (
            "This month's gift of Rs 2,500 has reached us. We'll be in touch about next month."
        )

    def test_thanks_lead_to_the_appeals(self, client, donate_page, pledge, payment):
        client.get(return_url(donate_page, payment))

        page = soup(client.get(pay_url(donate_page, pledge)))

        assert page.find("a", string="See all our appeals")["href"] == "/appeals/"

    def test_thanks_lead_home_on_a_site_with_no_appeals_page(
        self, client, donate_page, pledge, payment
    ):
        """Not a dead end."""
        CampaignIndexPage.objects.get().unpublish()
        client.get(return_url(donate_page, payment))

        page = soup(client.get(pay_url(donate_page, pledge)))

        assert page.find("a", string="Back to the home page")["href"] == "/"

    def test_records_coming_back_and_what_the_provider_said(
        self, client, donate_page, payment, fake_provider
    ):
        fake_provider.outcome = Outcome(Status.FAILED, word="CANCELLED")

        client.get(return_url(donate_page, payment))

        assert [(step.kind, step.word) for step in payment.steps.all()] == [
            (StepKind.SENT, ""),
            (StepKind.CAME_BACK, ""),
            (StepKind.ASKED, "CANCELLED"),
        ]

    def test_coming_back_to_a_paid_payment_records_nothing_more(self, client, donate_page, payment):
        """Nothing is asked once it's paid, and a reload isn't news."""
        client.get(return_url(donate_page, payment))

        client.get(return_url(donate_page, payment))

        assert kinds(payment) == [StepKind.SENT, StepKind.CAME_BACK, StepKind.ASKED]

    def test_asks_the_provider_with_our_own_reference_and_amount(
        self, client, donate_page, payment, fake_provider
    ):
        client.get(return_url(donate_page, payment))

        assert fake_provider.checked == [(str(payment.reference), Decimal(2500), "fake-id")]

    def test_what_the_browser_brings_back_changes_nothing(
        self, client, donate_page, pledge, payment, fake_provider
    ):
        """Anyone can type a return address with "status=Completed" in it."""
        fake_provider.outcome = Outcome(Status.WAITING)

        client.get(return_url(donate_page, payment) + "?status=Completed&data=e30=")

        assert Pledge.objects.get().payment_status == PaymentStatus.WAITING

    def test_a_cancelled_payment_can_be_tried_again(
        self, client, donate_page, pledge, payment, fake_provider
    ):
        fake_provider.outcome = Outcome(Status.FAILED)

        client.get(return_url(donate_page, payment))

        page = client.get(pay_url(donate_page, pledge))
        assert "Fake Pay says your payment didn't go through." in text(page)
        assert "Pay with Fake Pay" in pay_buttons(page)

    def test_a_failed_payment_can_still_be_checked(
        self, client, donate_page, pledge, payment, fake_provider
    ):
        """eSewa can say "not found" before it says "complete": "no money was taken" isn't
        known, and paying again would pay twice."""
        fake_provider.outcome = Outcome(Status.FAILED)
        client.get(return_url(donate_page, payment))

        page = client.get(pay_url(donate_page, pledge))

        assert "no money was taken" not in text(page)
        assert "If money has left your account, don't pay again." in text(page)
        check = soup(page).find("a", href=return_url(donate_page, payment))
        assert check.get_text(strip=True) == "Check my Fake Pay payment"

    def test_checking_a_failed_payment_again_says_what_it_found(
        self, client, donate_page, pledge, payment, fake_provider
    ):
        fake_provider.outcome = Outcome(Status.FAILED)
        client.get(return_url(donate_page, payment))

        page = client.get(return_url(donate_page, payment), follow=True)

        assert (
            "We asked Fake Pay again just now, and it still says your payment didn't go through."
            in text(page)
        )

    def test_a_failed_payment_found_paid_later_says_thank_you(
        self, client, donate_page, pledge, payment, fake_provider
    ):
        fake_provider.outcome = Outcome(Status.FAILED)
        client.get(return_url(donate_page, payment))
        fake_provider.outcome = Outcome(Status.PAID, "FAKE-123")

        page = client.get(return_url(donate_page, payment), follow=True)

        assert Pledge.objects.get().payment_status == PaymentStatus.PAID
        assert soup(page).find(class_="lead").get_text() == (
            "Test payment completed. No money was taken."
        )

    def test_a_payment_that_never_started_says_no_money_was_taken(
        self, client, donate_page, pledge, fake_provider
    ):
        """The provider was never reached, so this one is known."""
        fake_provider.failure = ProviderUnavailable("Fake Pay is down.")
        start(client, donate_page, pledge)
        client.get(pay_url(donate_page, pledge))  # the one-off "couldn't reach" message

        page = client.get(pay_url(donate_page, pledge))

        assert "didn't go through, and no money was taken" in text(page)
        assert not soup(page).find("a", string=re.compile("Check my"))

    def test_an_older_attempt_failing_leaves_a_newer_one_to_check(
        self, client, donate_page, pledge, fake_provider
    ):
        """Said to have failed, with no way to check the newer attempt, the payer pays again."""
        older = pledge.start_payment("fakepay", live=False)
        newer = pledge.start_payment("fakepay", live=False)
        fake_provider.outcome = Outcome(Status.FAILED)

        client.get(return_url(donate_page, older))

        assert Pledge.objects.get().payment_status == PaymentStatus.WAITING
        page = client.get(pay_url(donate_page, pledge))
        assert "didn't go through" not in text(page)
        assert soup(page).find("a", href=return_url(donate_page, newer))

    def test_a_provider_that_cant_be_reached_leaves_it_waiting(
        self, client, donate_page, pledge, payment, fake_provider
    ):
        fake_provider.failure = ProviderUnavailable("Fake Pay is down.")

        response = client.get(return_url(donate_page, payment))

        assert response["Location"] == pay_url(donate_page, pledge)
        assert Payment.objects.get().status == PaymentStatus.WAITING

    @pytest.mark.parametrize(
        "outcome, found",
        [
            (Outcome(Status.WAITING), "We asked Fake Pay just now, and it hasn't confirmed"),
            (ProviderUnavailable("Fake Pay is down."), "We couldn't reach Fake Pay just now."),
        ],
        ids=["still waiting", "unreachable"],
    )
    def test_says_what_checking_found_once(
        self, client, site, donate_page, pledge, payment, fake_provider, outcome, found
    ):
        """Otherwise checking looks like nothing happened, and the payer may pay again."""
        site_settings = SiteSettings.for_site(site)
        site_settings.phone = "+977 1-4567890"
        site_settings.save()
        if isinstance(outcome, Outcome):
            fake_provider.outcome = outcome
        else:
            fake_provider.failure = outcome

        page = client.get(return_url(donate_page, payment), follow=True)

        assert found in text(page)
        assert "If money has left your account, don't pay again" in text(page)
        message = soup(page).find(string=re.compile("don't pay again")).find_parent("div")
        assert message.find("a", href="tel:+97714567890")
        assert found not in text(client.get(pay_url(donate_page, pledge)))

    def test_says_nothing_of_a_check_before_one(self, client, donate_page, pledge, payment):
        page = text(client.get(pay_url(donate_page, pledge)))

        assert "Did you finish paying with Fake Pay?" in page
        assert "don't pay again" not in page

    def test_a_message_for_the_admin_isnt_shown_or_lost(
        self, admin_client, donate_page, pledge, payment, fake_provider
    ):
        """Messages are one-off and shared with the admin: the pay page takes only its own."""
        fake_provider.outcome = Outcome(Status.WAITING)
        paid = Pledge.objects.create(page=donate_page, amount=500, currency="NPR", name="Ram")
        paid.start_payment("khalti", live=True).record(Status.PAID, "GFq9PFS7")
        admin_client.post(reverse("pledges:delete", args=[paid.pk]))  # refused, with a message

        page = text(admin_client.get(return_url(donate_page, payment), follow=True))
        admin = BeautifulSoup(
            admin_client.get(reverse("pledges:index")).content, "html.parser"
        ).get_text()

        assert "We asked Fake Pay just now" in page
        assert "can't be deleted" not in page
        assert "can't be deleted" in admin

    @pytest.mark.parametrize("case", ["provider gone", "other mode", "khalti with no pidx"])
    def test_a_payment_that_cant_be_checked_is_left_waiting(
        self, client, donate_page, pledge, fake_provider, settings, monkeypatch, case
    ):
        """No provider is asked when it's no longer set up, or set up for the other system (test
        or live), whose keys can't look up this payment; and a provider that can't look it up
        without its own ID (Khalti's pidx, missing when starting failed) is no error."""
        asked = []
        monkeypatch.setattr(http, "request_json", lambda url, **kwargs: asked.append(url))
        if case == "khalti with no pidx":
            settings.PAYMENT_KEYS = {**settings.PAYMENT_KEYS, "KHALTI_SECRET_KEY": "test-key"}
            payment = pledge.start_payment("khalti", live=False)
        else:
            payment = pledge.start_payment("fakepay", live=False)
        if case == "provider gone":
            settings.PAYMENT_KEYS = {}
        if case == "other mode":
            settings.LIVE_PAYMENTS = True

        response = client.get(return_url(donate_page, payment))

        assert response["Location"] == pay_url(donate_page, pledge)
        assert Payment.objects.get().status == PaymentStatus.WAITING
        assert fake_provider.checked == []
        assert asked == []

    def test_a_payment_still_waiting_offers_a_check_before_paying_again(
        self, client, donate_page, pledge, payment
    ):
        page = soup(client.get(pay_url(donate_page, pledge)))

        check = page.find("a", href=return_url(donate_page, payment))
        assert check.get_text(strip=True) == "Check my Fake Pay payment"

    def test_while_one_may_be_paid_paying_again_is_folded_away(
        self, client, donate_page, pledge, payment
    ):
        """Checking leads, so nobody pays twice; someone who didn't pay opens the pay buttons."""
        page = soup(client.get(pay_url(donate_page, pledge)))

        check = page.find("a", href=return_url(donate_page, payment))
        folded = page.find("details")
        assert "button-large" in check["class"]
        assert folded.find("summary").get_text(strip=True) == "I didn't pay: choose a way to pay"
        assert not folded.has_attr("open")
        assert folded.find("button", string="Pay with Fake Pay")
        assert check in folded.find_all_previous("a")

    def test_with_nothing_to_check_the_pay_buttons_are_open(self, client, donate_page, pledge):
        page = soup(client.get(pay_url(donate_page, pledge)))

        assert page.find("details") is None
        assert page.find("button", string="Pay with Fake Pay")

    def test_once_paid_the_provider_isnt_asked_again(
        self, client, donate_page, payment, fake_provider
    ):
        for _ in range(2):
            client.get(return_url(donate_page, payment))

        assert len(fake_provider.checked) == 1
        assert Pledge.objects.get().payment_status == PaymentStatus.PAID

    # Regression: ISSUE-002 — after the pledge was changed in the admin, paying the attempt for
    # the old amount thanked the payer for the new one. Found by /qa on 2026-10-12.
    def test_paying_what_the_pledge_no_longer_says_isnt_thanked_for_it(
        self, client, donate_page, pledge, payment
    ):
        Pledge.objects.filter(pk=pledge.pk).update(amount=10000)

        client.get(return_url(donate_page, payment))

        response = client.get(pay_url(donate_page, pledge))
        page = text(response)
        assert "has reached us" not in page
        # What was received, and no way to pay again: a person sorts out the difference.
        assert "We received Rs 2,500 from you by Fake Pay (reference FAKE-123)." in page
        assert "Our team will be in touch." in page
        assert pay_buttons(response) == []
        assert soup(response).find(id="pay-in-person") is None

    def test_an_unknown_payment_isnt_found(self, client, donate_page, fake_provider):
        assert client.get(f"{donate_page.url}payment/{uuid.uuid4()}/").status_code == 404


class TestEsewaEndToEnd:
    def test_pays_with_esewa(self, client, donate_page, settings, monkeypatch):
        settings.PAYMENT_KEYS = {"ESEWA_PRODUCT_CODE": "EPAYTEST", "ESEWA_SECRET_KEY": "s3cret"}
        send_pledge(client, donate_page)
        pledge = Pledge.objects.get()

        go = start(client, donate_page, pledge, "esewa")["Location"]
        form = soup(client.get(go)).find("form", attrs={"data-auto-submit": True})
        payment = Payment.objects.get()
        assert form["action"] == "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
        assert form.find("input", attrs={"name": "transaction_uuid"})["value"] == str(
            payment.reference
        )

        answer = {
            "product_code": "EPAYTEST",
            "transaction_uuid": str(payment.reference),
            "total_amount": 2500.0,
            "status": "COMPLETE",
            "ref_id": "000AWEO",
        }
        monkeypatch.setattr(http, "request_json", lambda url, **kwargs: (200, answer))
        # eSewa comes back with ?data=…, which is never read.
        client.get(return_url(donate_page, payment) + "?data=eyJzdGF0dXMiOiJDT01QTEVURSJ9")

        payment.refresh_from_db()
        assert payment.status == PaymentStatus.PAID
        assert payment.provider_reference == "000AWEO"
        assert Pledge.objects.get().payment_status == PaymentStatus.PAID


class TestKhaltiEndToEnd:
    def test_pays_with_khalti(self, client, donate_page, settings, monkeypatch):
        settings.PAYMENT_KEYS = {"KHALTI_SECRET_KEY": "test-secret-key"}
        send_pledge(client, donate_page)
        pledge = Pledge.objects.get()
        answers = iter(
            [
                (200, {"pidx": "PIDX1", "payment_url": "https://test-pay.khalti.com/?pidx=PIDX1"}),
                (
                    200,
                    {
                        "pidx": "PIDX1",
                        "total_amount": 250000,
                        "status": "Completed",
                        "transaction_id": "GFq9PFS7",
                        "fee": 0,
                        "refunded": False,
                    },
                ),
            ]
        )
        monkeypatch.setattr(http, "request_json", lambda url, **kwargs: next(answers))

        response = start(client, donate_page, pledge, "khalti")

        assert response["Location"] == "https://test-pay.khalti.com/?pidx=PIDX1"
        payment = Payment.objects.get()
        client.get(return_url(donate_page, payment) + "?pidx=PIDX1&status=Completed")

        payment.refresh_from_db()
        assert payment.status == PaymentStatus.PAID
        assert payment.provider_reference == "GFq9PFS7"
        assert Pledge.objects.get().payment_status == PaymentStatus.PAID
