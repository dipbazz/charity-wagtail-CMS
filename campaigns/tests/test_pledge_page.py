"""A pledge's own page in the admin (Pledges → open one): who, how much and whether it's paid at
the top, then the contact details, the message and consents, and each payment with what happened
to it, and the team's check with the provider.

Logged in as group members, not superusers: the charity's team are editors and moderators.
"""

import datetime

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from campaigns.models import CampaignPage, Frequency, Payment, PaymentStatus, Pledge, StepKind
from nepal_payments import Outcome, ProviderUnavailable, Status

pytestmark = pytest.mark.django_db


@pytest.fixture
def pledge(donate_page):
    return Pledge.objects.create(
        page=donate_page,
        appeal=CampaignPage.objects.get(slug="flood-relief"),
        amount=2500,
        currency="NPR",
        frequency=Frequency.MONTHLY,
        name="Asha Gurung",
        email="asha@example.org",
        phone="+9779841234567",
        address="Ward 4, Biratnagar",
        message="Please use it for the school tap.",
        email_updates=True,
    )


@pytest.fixture
def team(client, editor):
    client.force_login(editor)
    return editor


def inspect_url(pledge):
    return reverse("pledges:inspect", args=[pledge.pk])


def open_page(client, pledge):
    return BeautifulSoup(client.get(inspect_url(pledge)).content, "html.parser")


def text(element):
    return " ".join(element.get_text(" ", strip=True).split())


def answer(page):
    """The line at the top that says whether it's paid, and why not."""
    return text(page.select_one(".pledge-answer"))


def section(page, heading):
    """The panel with this heading."""
    title = page.find(lambda tag: tag.name == "h2" and text(tag).startswith(heading))
    return title.find_parent("section")


def qr_payment(pledge, status=PaymentStatus.TO_CONFIRM, **fields):
    """A payment by the charity's own QR code, as the supporter's "I've paid" makes one."""
    Pledge.objects.filter(pk=pledge.pk).update(payment_status=status)
    payment = pledge.payments.create(
        method="qr",
        amount=pledge.amount,
        currency=pledge.currency,
        status=status,
        live=True,
        qr_name="Fonepay (bank)",
        **fields,
    )
    payment.add_step(StepKind.CLAIMED)
    return payment


class TestTheTop:
    def test_says_who_how_much_how_often_and_for_what(self, client, team, pledge):
        Pledge.objects.filter(pk=pledge.pk).update(number="482913")

        lead = text(open_page(client, pledge).select_one(".pledge-lead"))

        assert "Rs 2,500 · Monthly · Flood relief" in lead
        assert "Sent" in lead
        assert "Pledge number 482 913" in lead

    def test_a_pledge_for_no_appeal_says_where_it_goes(self, client, team, pledge):
        Pledge.objects.filter(pk=pledge.pk).update(appeal=None)

        lead = text(open_page(client, pledge).select_one(".pledge-lead"))

        assert "Wherever it's needed most" in lead

    def test_not_paid_yet(self, client, team, pledge):
        assert answer(open_page(client, pledge)) == "Waiting Not paid online yet."

    def test_paid_says_how_when_and_the_transaction(self, client, team, pledge):
        pledge.start_payment("esewa", live=True).record(Status.PAID, "000AWEO")

        said = answer(open_page(client, pledge))

        assert said.startswith("Paid with eSewa on ")
        assert said.endswith(", transaction 000AWEO")
        assert "test" not in said

    def test_paid_in_a_test_system_says_no_money_moved(self, client, team, pledge):
        """Anyone can pay there with the provider's public test account."""
        pledge.start_payment("esewa", live=False).record(Status.PAID, "000AWEO")

        said = answer(open_page(client, pledge))

        assert said.startswith("Paid (test) with eSewa")
        assert "Made in eSewa's test system: no money moved." in said

    def test_waiting_for_the_provider(self, client, team, pledge):
        pledge.start_payment("khalti", live=False)

        said = answer(open_page(client, pledge))

        assert said.startswith("Waiting Started with Khalti on ")
        assert said.endswith("not confirmed yet.")

    def test_failed_says_what_the_provider_said(self, client, team, pledge):
        payment = pledge.start_payment("esewa", live=False)
        payment.provider_form = {"url": "https://example.com/"}
        payment.save()
        Payment.objects.filter(pk=payment.pk).update(word="CANCELED")
        payment.record(Status.FAILED)

        assert answer(open_page(client, pledge)) == (
            "Failed The payer cancelled at eSewa. Nothing was taken."
        )

    def test_failed_before_reaching_the_provider_took_no_money(self, client, team, pledge):
        pledge.start_payment("khalti", live=False).record(Status.FAILED)

        assert answer(open_page(client, pledge)) == (
            "Failed The payment couldn't start at Khalti, so no money was taken."
        )

    def test_to_confirm_says_what_the_supporter_sent(self, client, team, pledge):
        qr_payment(pledge, supporters_reference="TXN-8841")

        assert answer(open_page(client, pledge)) == (
            "To confirm The supporter says they paid by Fonepay (bank), transaction TXN-8841."
            " Find it in your statement, then mark it paid or not found."
        )

    def test_not_found_by_the_team(self, client, team, pledge):
        qr_payment(pledge, supporters_reference="TXN-8841").mark_not_found(by=None)

        assert answer(open_page(client, pledge)) == (
            "Failed Your team couldn't find the payment by Fonepay (bank) in its statement."
        )

    def test_received_another_amount_needs_checking(self, client, team, pledge):
        payment = qr_payment(pledge, supporters_reference="TXN-8841")
        payment.mark_paid(None, timezone.localdate(), 2000, "RBB-77")

        assert answer(open_page(client, pledge)) == (
            "Needs checking Rs 2,000 was received, but the pledge is for Rs 2,500."
        )


class TestContact:
    def test_email_and_phone_are_links(self, client, team, pledge):
        contact = section(open_page(client, pledge), "Contact")

        assert contact.find("a", href="mailto:asha@example.org")
        assert contact.find("a", href="tel:+9779841234567")
        assert "Ward 4, Biratnagar" in text(contact)

    def test_empty_details_arent_shown(self, client, team, pledge):
        contact = section(open_page(client, pledge), "Contact")

        assert "Postcode" not in text(contact)


class TestMessageAndConsents:
    def test_shows_the_message_and_both_consents(self, client, team, pledge):
        shown = text(section(open_page(client, pledge), "Message and consents"))

        assert "Please use it for the school tap." in shown
        assert "Email updates: Yes" in shown
        assert "Show on website: No" in shown

    def test_each_consent_on_its_own_line_with_a_tick_or_a_cross(self, client, team, pledge):
        """A shape to scan by as well as the word, never colour alone (WCAG 1.4.1): "No" is the
        supporter's choice, not an error, so it isn't red."""
        consents = section(open_page(client, pledge), "Message and consents").select(
            ".pledge-consents li"
        )

        assert [(text(c), c.svg.use["href"]) for c in consents] == [
            ("Email updates: Yes", "#icon-check"),
            ("Show on website: No", "#icon-cross"),
        ]

    def test_a_message_is_shown_as_text(self, client, team, pledge):
        """Anyone can send a pledge, so what they type never runs on the team's page."""
        Pledge.objects.filter(pk=pledge.pk).update(message="<script>alert(1)</script>")

        html = client.get(inspect_url(pledge)).content.decode()

        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


class TestWhatIsLeftOut:
    def test_nothing_the_team_doesnt_act_on(self, client, team, pledge):
        html = client.get(inspect_url(pledge)).content.decode()
        page = BeautifulSoup(html, "html.parser")

        for label in ("Submission", "Page", "Reference"):
            assert not page.find("dt", string=label)

    def test_never_the_pay_pages_address(self, client, team, pledge):
        """Whoever has it can pay the pledge and read its summary: it stays with the supporter."""
        html = client.get(inspect_url(pledge)).content.decode()

        assert str(pledge.reference) not in html


class TestPayments:
    def test_none_yet(self, client, team, pledge):
        payments = section(open_page(client, pledge), "Payments")

        assert "No online payment yet." in text(payments)

    def test_each_payment_with_its_references_newest_first(self, client, team, pledge):
        failed = pledge.start_payment("khalti", live=False)
        failed.record(Status.FAILED)
        paid = pledge.start_payment("esewa", live=False)
        Payment.objects.filter(pk=paid.pk).update(provider_id="esewa-id")
        paid.record(Status.PAID, "000AWEO")
        Payment.objects.filter(pk=failed.pk).update(
            created_at=timezone.now() - datetime.timedelta(minutes=5)
        )

        payments = section(open_page(client, pledge), "Payments (2)")
        attempts = payments.select("details")

        assert [text(a.summary).split(" · ")[0] for a in attempts] == ["eSewa", "Khalti"]
        shown = text(attempts[0])
        assert str(paid.reference) in shown
        assert "esewa-id" in shown
        assert "eSewa's transaction ID 000AWEO" in shown
        assert "Made in eSewa's test system: no money moved." in shown

    def test_the_paid_one_is_open_and_the_others_folded(self, client, team, pledge):
        pledge.start_payment("esewa", live=False).record(Status.PAID, "000AWEO")
        pledge.start_payment("khalti", live=False)

        attempts = section(open_page(client, pledge), "Payments").select("details")

        assert [a.has_attr("open") for a in attempts] == [False, True]

    def test_each_payments_line_shows_it_opens(self, client, team, pledge):
        """Wagtail's own arrow, as on everything else that folds in the admin."""
        pledge.start_payment("esewa", live=False)

        line = section(open_page(client, pledge), "Payments").select_one("details summary")

        assert line.svg.use["href"] == "#icon-arrow-right"

    def test_the_latest_is_open_when_none_is_paid(self, client, team, pledge):
        pledge.start_payment("esewa", live=False).record(Status.FAILED)
        pledge.start_payment("khalti", live=False)

        attempts = section(open_page(client, pledge), "Payments").select("details")

        assert [a.has_attr("open") for a in attempts] == [True, False]

    def test_says_what_happened_in_order_with_the_providers_word(
        self, client, team, pledge, fake_provider
    ):
        payment = pledge.start_payment("fakepay", live=False)
        payment.add_step(StepKind.SENT)
        payment.add_step(StepKind.CAME_BACK)
        payment.ask()

        steps = section(open_page(client, pledge), "Payments").select("ol.payment-steps > li")

        assert [text(step.select_one(".step-what")) for step in steps] == [
            "Sent to Fake Pay.",
            "Came back to the site.",
            "Fake Pay says it's paid. DONE",
        ]

    def test_says_who_did_a_step(self, client, team, pledge, moderator):
        moderator.first_name, moderator.last_name = "Sita", "Sharma"
        moderator.save()
        qr_payment(pledge, supporters_reference="TXN-8841").mark_paid(
            moderator, timezone.localdate(), 2500, "RBB-77"
        )

        steps = section(open_page(client, pledge), "Payments").select("ol.payment-steps > li")

        assert text(steps[-1]).endswith("Marked paid. by Sita Sharma")

    def test_names_the_time_zone_once(self, client, team, pledge, settings):
        pledge.start_payment("esewa", live=False)

        shown = text(section(open_page(client, pledge), "Payments"))

        assert shown.count("Times are Asia/Kathmandu time (UTC+5:45).") == 1

    def test_a_payment_from_before_steps_were_recorded_says_so(self, client, team, pledge):
        pledge.start_payment("esewa", live=False)

        shown = text(section(open_page(client, pledge), "Payments"))

        assert "Steps weren't recorded for payments started before version 0.5.0." in shown
        assert "Updated" in shown

    def test_doesnt_ask_once_per_payment_or_step(self, client, team, pledge, fake_provider):
        def queries():
            with CaptureQueriesContext(connection) as captured:
                client.get(inspect_url(pledge))
            return len(captured)

        pledge.start_payment("fakepay", live=False).ask(by=team)
        one = queries()
        for _ in range(3):
            payment = pledge.start_payment("fakepay", live=False)
            payment.add_step(StepKind.SENT)
            payment.ask(by=team)

        assert queries() == one


class TestCheckWithTheProviderNow:
    """Anyone who can read pledges asks the provider about a payment, as the pay page does, and
    the answer is a step with their name."""

    def check_url(self, payment):
        return reverse("pledges:check", args=[payment.pledge_id, payment.pk])

    @pytest.fixture
    def payment(self, pledge, fake_provider):
        return pledge.start_payment("fakepay", live=False)

    def test_offered_on_a_payment_that_may_still_change(self, client, team, pledge, payment):
        page = open_page(client, pledge)

        button = page.find("button", string="Check with Fake Pay now")
        assert button.find_parent("form")["action"] == self.check_url(payment)
        assert button.find_parent("form")["method"] == "post"

    def test_records_the_answer_and_who_asked(self, client, team, pledge, payment, fake_provider):
        fake_provider.outcome = Outcome(Status.PAID, "FAKE-123", word="DONE")

        response = client.post(self.check_url(payment), follow=True)

        assert response.redirect_chain[-1][0] == inspect_url(pledge)
        assert "Fake Pay says it's paid." in text(BeautifulSoup(response.content, "html.parser"))
        step = payment.steps.get()
        assert (step.kind, step.word, step.by) == (StepKind.ASKED, "DONE", team)
        assert Pledge.objects.get(pk=pledge.pk).payment_status == PaymentStatus.PAID

    def test_says_when_the_provider_couldnt_be_reached(
        self, client, team, pledge, payment, fake_provider
    ):
        fake_provider.failure = ProviderUnavailable("Timed out")

        response = client.post(self.check_url(payment), follow=True)

        shown = text(BeautifulSoup(response.content, "html.parser"))
        assert "Couldn't reach Fake Pay. Try again in a few minutes." in shown

    def test_not_again_within_30_seconds(self, client, team, pledge, payment, fake_provider):
        """Each press can wait up to 10 seconds for the provider: a second press is refused."""
        fake_provider.outcome = Outcome(Status.WAITING, word="PENDING")
        client.post(self.check_url(payment))

        response = client.post(self.check_url(payment), follow=True)

        assert len(fake_provider.checked) == 1
        shown = text(BeautifulSoup(response.content, "html.parser"))
        assert "Fake Pay was asked less than 30 seconds ago" in shown

    def test_again_after_30_seconds(self, client, team, payment, fake_provider):
        fake_provider.outcome = Outcome(Status.WAITING, word="PENDING")
        client.post(self.check_url(payment))
        payment.steps.update(at=timezone.now() - datetime.timedelta(seconds=31))

        client.post(self.check_url(payment))

        assert len(fake_provider.checked) == 2

    def test_not_offered_on_a_paid_payment(self, client, team, pledge, payment):
        payment.record(Status.PAID, "FAKE-123")

        assert not open_page(client, pledge).find("button", string="Check with Fake Pay now")

    def test_a_paid_payment_isnt_asked(self, client, team, payment, fake_provider):
        payment.record(Status.PAID, "FAKE-123")

        client.post(self.check_url(payment))

        assert fake_provider.checked == []

    def test_not_offered_when_the_provider_isnt_set_up_for_it(
        self, client, team, pledge, payment, settings
    ):
        settings.LIVE_PAYMENTS = True  # its keys are for the test system it was made in

        assert not open_page(client, pledge).find("button", string="Check with Fake Pay now")

    def test_never_a_payment_the_team_confirms(self, client, moderator, pledge, fake_provider):
        payment = qr_payment(pledge, supporters_reference="TXN-8841")
        client.force_login(moderator)

        page = open_page(client, pledge)
        client.post(self.check_url(payment))

        assert not page.find("button", string="Check with QR code now")
        assert list(payment.steps.values_list("kind", flat=True)) == [StepKind.CLAIMED]

    def test_it_is_a_post(self, client, team, payment, fake_provider):
        assert client.get(self.check_url(payment)).status_code == 405
        assert fake_provider.checked == []

    def test_only_a_payment_of_that_pledge(self, client, team, payment, donate_page):
        """Another pledge's number in the address finds nothing, rather than its payment."""
        other = Pledge.objects.create(page=donate_page, amount=1500, currency="NPR", name="Ram")

        response = client.post(reverse("pledges:check", args=[other.pk, payment.pk]))

        assert response.status_code == 404

    def test_not_for_someone_who_cant_read_pledges(
        self, client, django_user_model, payment, fake_provider
    ):
        """An admin login with no access to pledges, such as one only for the image library."""
        user = django_user_model.objects.create_user(username="photos", password="x")
        user.user_permissions.add(Permission.objects.get(codename="access_admin"))
        client.force_login(user)

        client.post(self.check_url(payment))

        assert fake_provider.checked == []

    def test_a_visitor_is_sent_to_log_in(self, client, payment, fake_provider):
        response = client.post(self.check_url(payment))

        assert response.status_code == 302
        assert response.url.startswith(reverse("wagtailadmin_login"))
        assert fake_provider.checked == []


class TestStopShowingOnTheWebsite:
    """The team's answer to a made-up name on a gift's page for friends (#100): editors and
    moderators take it down, and only they can put it back."""

    @pytest.fixture
    def gift(self, donate_page):
        from campaigns.tests.test_sharing import pledge_in

        return pledge_in("paid", donate_page, CampaignPage.objects.get(slug="flood-relief"))

    def gift_page(self, client, gift):
        return client.get(f"{gift.page.url}gifts/{gift.gift_code}/")

    @pytest.mark.parametrize("member", ["editor", "moderator"])
    def test_offered_on_a_gift_shown_on_the_website(self, client, request, gift, member):
        client.force_login(request.getfixturevalue(member))

        page = section(open_page(client, gift), "Message and consents")

        stop = page.find("a", string="Stop showing on the website")
        assert stop["href"] == reverse("pledges:stop_showing", args=[gift.pk])
        friends = page.find("a", string="Their page for friends")
        assert friends["href"] == f"http://localhost{gift.page.url}gifts/{gift.gift_code}/"

    def test_not_offered_without_consent(self, client, team, pledge):
        page = section(open_page(client, pledge), "Message and consents")

        assert page.find("a", string="Stop showing on the website") is None

    def test_asks_first(self, client, team, gift):
        response = client.get(reverse("pledges:stop_showing", args=[gift.pk]))
        page = BeautifulSoup(response.content, "html.parser")

        assert response.status_code == 200
        assert "Asha Gurung" in text(page.find("h1"))
        assert page.find("button", string="Yes, stop showing it") is not None
        assert not Pledge.objects.get(pk=gift.pk).hidden_by_team

    def test_takes_the_page_down_at_once(self, client, team, gift):
        response = client.post(reverse("pledges:stop_showing", args=[gift.pk]))

        assert response.status_code == 302
        assert response.url == inspect_url(gift)
        assert Pledge.objects.get(pk=gift.pk).hidden_by_team
        assert self.gift_page(client, gift).status_code == 302  # to the appeal

    def test_says_where_friends_go_now(self, client, team, gift):
        response = client.get(reverse("pledges:stop_showing", args=[gift.pk]))

        assert "page not found" not in response.content.decode()
        assert "goes to the appeal" in text(BeautifulSoup(response.content, "html.parser"))

    def test_says_so_on_the_pledge(self, client, team, gift):
        client.post(reverse("pledges:stop_showing", args=[gift.pk]))

        page = section(open_page(client, gift), "Message and consents")

        assert "Taken down by your team" in text(page)
        assert page.find("button", string="Show again") is not None
        assert page.find("a", string="Their page for friends") is None
        history = page.find("a", string="Who took it down, and when")
        assert history["href"] == reverse("pledges:history", args=[gift.pk])

    def test_is_logged_in_the_pledges_history(self, client, team, gift):
        client.post(reverse("pledges:stop_showing", args=[gift.pk]))
        client.post(reverse("pledges:show_again", args=[gift.pk]))

        history = client.get(reverse("pledges:history", args=[gift.pk])).content.decode()

        assert "Stopped showing on the website" in history
        assert "Shown again on the website" in history
        assert team.get_username() in history

    def test_show_again_puts_it_back(self, client, team, gift):
        client.post(reverse("pledges:stop_showing", args=[gift.pk]))

        client.post(reverse("pledges:show_again", args=[gift.pk]))

        assert not Pledge.objects.get(pk=gift.pk).hidden_by_team
        assert self.gift_page(client, gift).status_code == 200

    def test_show_again_only_by_sending_the_form(self, client, team, gift):
        Pledge.objects.filter(pk=gift.pk).update(hidden_by_team=True)

        assert client.get(reverse("pledges:show_again", args=[gift.pk])).status_code == 405
        assert Pledge.objects.get(pk=gift.pk).hidden_by_team

    @pytest.mark.parametrize("action", ["stop_showing", "show_again"])
    def test_not_for_someone_who_only_reads_pledges(self, client, django_user_model, gift, action):
        user = django_user_model.objects.create_user(username="reader", password="x")
        user.user_permissions.add(
            Permission.objects.get(codename="access_admin"),
            Permission.objects.get(codename="view_pledge"),
        )
        client.force_login(user)
        Pledge.objects.filter(pk=gift.pk).update(hidden_by_team=action == "show_again")

        response = client.post(reverse(f"pledges:{action}", args=[gift.pk]))

        # Wagtail sends someone without permission back to the dashboard.
        assert response.status_code == 302
        assert response.url == reverse("wagtailadmin_home")
        assert Pledge.objects.get(pk=gift.pk).hidden_by_team is (action == "show_again")
        page = section(open_page(client, gift), "Message and consents")
        assert page.find("a", string="Stop showing on the website") is None
        assert page.find("button", string="Show again") is None
