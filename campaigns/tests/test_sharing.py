"""What a gift's public page may show, and what a supporter shares (#100): campaigns/sharing.py.

One rule decides it, here and later in the recent supporters list (#99), so it's tested state by
state: every pay page state, with and without consent, taken down by the team or not, test
payment or real.
"""

import datetime
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import RequestFactory
from wagtail.models import PageViewRestriction

from campaigns import sharing
from campaigns.models import CampaignPage, PaymentStatus, Pledge
from campaigns.tests.test_qr import make_code

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()

# Every state a pledge's pay page can be in (Pledge.pay_page_state()), with a real or a test
# payment where it matters.
STATES = [
    "ready",
    "check-first",
    "failed",
    "not-started",
    "paid",
    "paid (test)",
    "received",
    "to-confirm",
    "not-found",
]


def pledge_in(state, donate_page, appeal=None, show=True, **fields):
    """A pledge for Rs 2,500 whose pay page is in `state` (one of STATES)."""
    pledge = Pledge.objects.create(
        page=donate_page,
        appeal=appeal,
        amount=2500,
        currency="NPR",
        name="Asha Gurung",
        email="asha@example.com",
        show_on_website=show,
        **fields,
    )
    if state in ("check-first", "failed", "not-started", "paid", "paid (test)", "received"):
        payment = pledge.start_payment("esewa", live=state != "paid (test)")
        if state == "failed":
            payment.provider_id = "esewa-id"  # it reached eSewa, so it may still turn out paid
            payment.save()
        if state in ("failed", "not-started"):
            payment.record(PaymentStatus.FAILED)
        if state == "received":
            # Changed after the attempt started: the money still arrived, for the old amount.
            Pledge.objects.filter(pk=pledge.pk).update(amount=5000)
        if state.startswith("paid") or state == "received":
            payment.record(PaymentStatus.PAID, "ESW-1")
    if state in ("to-confirm", "not-found"):
        claimed = pledge.claim_paid(make_code("eSewa"), "TXN-8841")
        if state == "not-found":
            claimed.mark_not_found(by=None)
    fetched = Pledge.objects.select_related("appeal", "page").prefetch_related("payments")
    pledge = fetched.get(pk=pledge.pk)
    assert pledge.pay_page_state() == state.removesuffix(" (test)")
    return pledge


@pytest.fixture
def appeal(appeals):
    return CampaignPage.objects.get(slug="flood-relief")


@pytest.fixture
def request_():
    return RequestFactory().get("/")


class TestGiftView:
    @pytest.mark.parametrize("state", STATES)
    def test_without_consent_nothing_is_shown(self, donate_page, state):
        assert sharing.gift_view(pledge_in(state, donate_page, show=False)) == sharing.HIDDEN

    @pytest.mark.parametrize("state", STATES)
    def test_taken_down_by_the_team_nothing_is_shown(self, donate_page, state):
        pledge = pledge_in(state, donate_page, hidden_by_team=True)

        assert sharing.gift_view(pledge) == sharing.HIDDEN

    @pytest.mark.parametrize(
        ("state", "view"),
        [
            ("ready", sharing.HIDDEN),
            ("check-first", sharing.HIDDEN),
            ("failed", sharing.HIDDEN),
            ("not-started", sharing.HIDDEN),
            # Paid, at whatever amount was received; a test payment is shown, marked as a test.
            ("paid", sharing.SHOWN),
            ("paid (test)", sharing.SHOWN),
            ("received", sharing.SHOWN),
            # They've told us they paid by QR: their name, never the amount until it's checked.
            ("to-confirm", sharing.CHECKING),
            ("not-found", sharing.HIDDEN),
        ],
    )
    def test_with_consent_only_once_they_say_theyve_paid(self, donate_page, state, view):
        assert sharing.gift_view(pledge_in(state, donate_page)) == view

    @pytest.mark.parametrize("state", STATES)
    def test_sharing_is_offered_once_they_say_theyve_paid(self, donate_page, state):
        """With or without consent: without it, the share just has no name on it."""
        pledge = pledge_in(state, donate_page, show=False)

        offered = state in ("paid", "paid (test)", "received", "to-confirm")
        assert sharing.offers_sharing(pledge) is offered

    @pytest.mark.parametrize(
        ("state", "view"),
        [("to-confirm", sharing.HIDDEN), ("paid", sharing.SHOWN), ("received", sharing.SHOWN)],
    )
    def test_agreed_in_the_old_words_only_once_the_gift_reaches_us(self, donate_page, state, view):
        """Before #100 the box said "Once your gift reaches us": those pledges have no time of
        agreeing, and show nothing while a QR payment is checked."""
        pledge = pledge_in(state, donate_page)
        pledge.show_on_website_changed_at = None

        assert sharing.gift_view(pledge) == view

    def test_reads_payments_as_fetched(self, donate_page, django_assert_num_queries):
        """So #99's list can prefetch them."""
        pledge = pledge_in("paid", donate_page)

        with django_assert_num_queries(0):
            sharing.gift_view(pledge)


class TestWhenTheyAgreed:
    """A pledge made with the box ticked anywhere (the form, the admin, the demo) records when,
    so it's never taken for one agreed in the old words."""

    def test_a_pledge_made_with_consent_records_when(self, donate_page):
        assert pledge_in("ready", donate_page).show_on_website_changed_at is not None

    def test_a_pledge_made_without_it_doesnt(self, donate_page):
        assert pledge_in("ready", donate_page, show=False).show_on_website_changed_at is None


class TestTheAppealShown:
    def test_a_live_public_appeal(self, donate_page, appeal):
        assert sharing.appeal_shown(pledge_in("paid", donate_page, appeal)) == appeal

    def test_none_for_wherever_its_needed_most(self, donate_page):
        assert sharing.appeal_shown(pledge_in("paid", donate_page)) is None

    def test_none_for_a_private_appeal(self, donate_page, appeals):
        private = CampaignPage.objects.get(slug="trustees")

        assert sharing.appeal_shown(pledge_in("paid", donate_page, private)) is None

    def test_none_for_an_unpublished_appeal(self, donate_page, appeal):
        appeal.unpublish()

        assert sharing.appeal_shown(pledge_in("paid", donate_page, appeal)) is None

    def test_none_under_a_private_appeals_page(self, donate_page, appeal, appeals):
        PageViewRestriction.objects.create(page=appeals, restriction_type="login")

        assert sharing.appeal_shown(pledge_in("paid", donate_page, appeal)) is None


class TestImpactLine:
    """What the gift does, from what editors already wrote: no new field to fill in."""

    def test_the_appeals_suggested_amount_that_matches(self, donate_page, appeal):
        appeal.donation_amounts.create(amount=2500, impact="A hygiene kit for a family")
        pledge = pledge_in("paid", donate_page, appeal)

        assert (
            sharing.impact_line(pledge, appeal, "NPR") == "It pays for a hygiene kit for a family."
        )

    def test_keeps_a_first_word_in_capitals(self, donate_page, appeal):
        appeal.donation_amounts.create(amount=2500, impact="UV filters for a school")
        pledge = pledge_in("paid", donate_page, appeal)

        assert sharing.impact_line(pledge, appeal, "NPR") == "It pays for UV filters for a school."

    def test_else_the_appeals_summary(self, donate_page, appeal):
        appeal.donation_amounts.create(amount=6000, impact="A handwashing station")
        pledge = pledge_in("paid", donate_page, appeal)

        assert sharing.impact_line(pledge, appeal, "NPR") == appeal.summary

    def test_matches_the_amount_received(self, donate_page, appeal):
        """Paid for what the pledge asked before it was changed: what arrived is what it does."""
        appeal.donation_amounts.create(amount=5000, impact="Two hygiene kits")
        appeal.donation_amounts.create(amount=2500, impact="A hygiene kit for a family")
        pledge = pledge_in("received", donate_page, appeal)

        assert (
            sharing.impact_line(pledge, appeal, "NPR") == "It pays for a hygiene kit for a family."
        )

    def test_only_in_the_sites_currency(self, donate_page, appeal):
        """Suggested amounts are in the site's currency: £2,500 received isn't Rs 2,500."""
        appeal.donation_amounts.create(amount=2500, impact="A hygiene kit for a family")
        pledge = pledge_in("paid", donate_page, appeal)
        pledge.payments.update(currency="GBP")
        pledge = Pledge.objects.prefetch_related("payments").get(pk=pledge.pk)

        assert sharing.impact_line(pledge, appeal, "NPR") == appeal.summary

    def test_wherever_its_needed_most_uses_the_donate_pages_amounts(self, donate_page):
        pledge = pledge_in("paid", donate_page)

        assert sharing.impact_line(pledge, None, "NPR") == "It pays for a hygiene kit for a family."

    def test_else_a_sentence_about_the_need(self, donate_page):
        pledge = pledge_in("paid", donate_page)
        Pledge.objects.filter(pk=pledge.pk).update(amount=3000)
        pledge.payments.update(amount=3000)
        pledge = Pledge.objects.prefetch_related("payments").get(pk=pledge.pk)

        assert sharing.impact_line(pledge, None, "NPR") == "It helps wherever the need is greatest."

    def test_a_private_appeal_counts_as_wherever_its_needed_most(self, donate_page, appeals):
        private = CampaignPage.objects.get(slug="trustees")
        private.donation_amounts.create(amount=2500, impact="Something for the trustees")
        pledge = pledge_in("paid", donate_page, private)

        line = sharing.impact_line(pledge, sharing.appeal_shown(pledge), "NPR")

        assert line == "It pays for a hygiene kit for a family."


class TestShareLink:
    """Where a share sends friends: never the pay page, whose reference pays the pledge."""

    def test_the_gift_page_once_its_shown(self, donate_page, appeal, request_):
        pledge = pledge_in("paid", donate_page, appeal)

        url = sharing.share_url(pledge, appeal, request_)

        assert url == f"http://localhost{donate_page.url}gifts/{pledge.gift_code}/"

    def test_the_gift_page_while_a_qr_payment_is_checked(self, donate_page, appeal, request_):
        pledge = pledge_in("to-confirm", donate_page, appeal)

        assert sharing.share_url(pledge, appeal, request_).endswith(f"/gifts/{pledge.gift_code}/")

    def test_without_consent_the_appeal(self, donate_page, appeal, request_):
        pledge = pledge_in("paid", donate_page, appeal, show=False)

        assert (
            sharing.share_url(pledge, appeal, request_) == "http://localhost/appeals/flood-relief/"
        )

    def test_without_consent_or_appeal_the_donate_page(self, donate_page, request_):
        pledge = pledge_in("paid", donate_page, show=False)

        assert sharing.share_url(pledge, None, request_) == "http://localhost/donate/"

    def test_once_the_team_takes_it_down_the_appeal(self, donate_page, appeal, request_):
        pledge = pledge_in("paid", donate_page, appeal, hidden_by_team=True)

        assert sharing.share_url(pledge, appeal, request_).endswith("/appeals/flood-relief/")

    @pytest.mark.parametrize("state", STATES)
    @pytest.mark.parametrize("show", [True, False])
    def test_never_carries_the_pay_pages_reference(
        self, donate_page, appeal, request_, state, show
    ):
        pledge = pledge_in(state, donate_page, appeal, show=show)
        url = sharing.share_url(pledge, appeal, request_)
        text = sharing.share_text(pledge, appeal, "Brightwell")

        for shared in (url, sharing.whatsapp_link(text, url), sharing.facebook_link(url)):
            assert str(pledge.reference) not in shared
            assert pledge.reference.hex not in shared


class TestShareText:
    """An invitation to help the cause, never showing off: no amount."""

    def test_names_the_appeal_and_says_it_still_needs_help(self, donate_page, appeal):
        text = sharing.share_text(pledge_in("paid", donate_page, appeal), appeal, "Brightwell")

        assert text == (
            "I've just given to Flood relief with Brightwell. They still need help. If you can, "
            "you could give too:"
        )

    def test_once_the_target_is_reached_doesnt_say_it_needs_help(self, donate_page, appeal):
        appeal.amount_raised = appeal.target_amount
        text = sharing.share_text(pledge_in("paid", donate_page, appeal), appeal, "Brightwell")

        assert (
            text
            == "I've just given to Flood relief with Brightwell. If you can, you could give too:"
        )

    def test_once_the_appeal_has_closed_doesnt_say_it_needs_help(self, donate_page, appeal):
        appeal.end_date = TODAY - datetime.timedelta(days=1)
        text = sharing.share_text(pledge_in("paid", donate_page, appeal), appeal, "Brightwell")

        assert "They still need help." not in text

    def test_wherever_its_needed_most_names_the_charity(self, donate_page):
        text = sharing.share_text(pledge_in("paid", donate_page), None, "Brightwell")

        assert text == (
            "I've just given to Brightwell. They still need help. If you can, you could give too:"
        )

    @pytest.mark.parametrize("state", ["paid", "received", "to-confirm"])
    def test_never_says_the_amount(self, donate_page, appeal, state):
        text = sharing.share_text(pledge_in(state, donate_page, appeal), appeal, "Brightwell")

        assert "2,500" not in text and "5,000" not in text


class TestShareLinks:
    def test_whatsapp_gets_the_message_and_the_link(self):
        link = sharing.whatsapp_link("I've just given.", "https://brightwell.example/gifts/x/")

        assert link.startswith("https://wa.me/?")
        assert parse_qs(urlparse(link).query) == {
            "text": ["I've just given. https://brightwell.example/gifts/x/"]
        }

    def test_facebook_gets_the_link(self):
        link = sharing.facebook_link("https://brightwell.example/gifts/x/")

        assert link.startswith("https://www.facebook.com/sharer/sharer.php?")
        assert parse_qs(urlparse(link).query) == {"u": ["https://brightwell.example/gifts/x/"]}


class TestTargetReached:
    @pytest.mark.parametrize(
        ("raised", "target", "reached"),
        [("2500", "10000", False), ("10000", "10000", True), ("12000", "10000", True)],
    )
    def test_once_raised_meets_the_target(self, appeal, raised, target, reached):
        appeal.amount_raised, appeal.target_amount = Decimal(raised), Decimal(target)

        assert appeal.target_reached is reached

    def test_never_without_a_target(self, appeal):
        appeal.amount_raised, appeal.target_amount = Decimal("0"), Decimal("0")

        assert appeal.target_reached is False
