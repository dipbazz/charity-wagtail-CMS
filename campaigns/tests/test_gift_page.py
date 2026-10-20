"""A gift's public page (#100): what friends see when a supporter shares that they've given.

What it may show comes from campaigns/sharing.py (test_sharing.py); these test the page itself.
"""

import datetime

import pytest
from bs4 import BeautifulSoup
from django.utils import dateformat, timezone
from wagtail_factories import ImageFactory

from campaigns.models import CampaignPage, Frequency, Pledge
from campaigns.tests.test_sharing import pledge_in

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(days=1)


def soup(response):
    return BeautifulSoup(response.content, "html.parser")


def text(response):
    return " ".join(soup(response).get_text().split())


def long_date(moment):
    """A date as the page writes it, "18 October 2026", in the site's time zone."""
    if isinstance(moment, datetime.datetime):
        moment = timezone.localtime(moment)
    return dateformat.format(moment, "j F Y")


def link(page, words):
    """The link whose text starts with `words` (it may end with an arrow), or None."""
    return next((a for a in page.find_all("a") if a.get_text(strip=True).startswith(words)), None)


def meta(response, prop):
    tag = soup(response).find("meta", attrs={"property": prop})
    return tag["content"] if tag else None


def gift_path(donate_page, pledge):
    return f"{donate_page.url}gifts/{pledge.gift_code}/"


@pytest.fixture(autouse=True)
def charity(site):
    """The charity's name, as the page names it with no appeal to name."""
    site.site_name = "Brightwell"
    site.save()


@pytest.fixture
def appeal(appeals):
    return CampaignPage.objects.get(slug="flood-relief")


@pytest.fixture
def gift(donate_page, appeal):
    """Asha's paid gift to Flood relief, with her agreement to show it."""
    return pledge_in("paid", donate_page, appeal)


class TestAGiftShown:
    def test_names_the_supporter_and_the_appeal(self, client, donate_page, gift):
        page = soup(client.get(gift_path(donate_page, gift)))

        assert page.h1.get_text(strip=True) == "Asha Gurung is supporting Flood relief"
        assert page.title.get_text(" ", strip=True).startswith(
            "Asha Gurung is supporting Flood relief"
        )

    def test_says_what_they_gave_and_when(self, client, donate_page, gift):
        paid_on = long_date(gift.paid_at)

        assert f"Gave Rs 2,500 on {paid_on}" in text(client.get(gift_path(donate_page, gift)))

    def test_a_monthly_gift_says_a_month(self, client, donate_page, appeal):
        gift = pledge_in("paid", donate_page, appeal, frequency=Frequency.MONTHLY)

        page = text(client.get(gift_path(donate_page, gift)))

        assert "Gives Rs 2,500 a month" in page
        assert "Gave" not in page

    def test_a_different_amount_received_shows_what_arrived(self, client, donate_page, appeal):
        gift = pledge_in("received", donate_page, appeal)

        page = text(client.get(gift_path(donate_page, gift)))

        assert "Gave Rs 2,500 on" in page
        assert "5,000" not in page

    def test_shows_the_appeal_and_its_progress(self, client, donate_page, gift, appeal):
        page = soup(client.get(gift_path(donate_page, gift)))

        assert appeal.summary in page.get_text()
        assert page.find(class_="progress")["aria-valuenow"] == "25"
        assert "Rs 2,500 raised of Rs 10,000" in page.get_text(" ", strip=True)

    def test_asks_friends_to_give_to_the_appeal(self, client, donate_page, gift):
        page = soup(client.get(gift_path(donate_page, gift)))

        give = page.find("a", class_="button")
        assert give.get_text(strip=True) == "Give to this appeal"
        assert give["href"] == "/donate/?appeal=flood-relief"
        assert link(page, "Read about this appeal")["href"] == "/appeals/flood-relief/"

    def test_shows_the_appeals_photo(self, client, donate_page, appeal):
        appeal.hero_image = ImageFactory(description="A family at a well")
        appeal.save_revision().publish()
        gift = pledge_in("paid", donate_page, appeal)

        img = soup(client.get(gift_path(donate_page, gift))).find("img")

        assert img["alt"] == "A family at a well"

    def test_shows_nothing_else_about_the_supporter(self, client, donate_page, appeal):
        gift = pledge_in(
            "paid",
            donate_page,
            appeal,
            address="Ward 4, Biratnagar",
            message="In memory of my mother",
        )

        page = client.get(gift_path(donate_page, gift)).content.decode()

        for private in ("asha@example.com", "Biratnagar", "In memory", gift.display_number()):
            assert private not in page

    def test_never_shows_the_pay_pages_reference(self, client, donate_page, gift):
        page = client.get(gift_path(donate_page, gift)).content.decode()

        assert str(gift.reference) not in page
        assert gift.reference.hex not in page

    def test_is_kept_out_of_search_engines(self, client, donate_page, gift):
        robots = soup(client.get(gift_path(donate_page, gift))).find(
            "meta", attrs={"name": "robots"}
        )

        assert robots["content"] == "noindex"


class TestItsLinkPreview:
    """What a chat app or Facebook shows for the link: the gift page's own, not the Donate
    page's (base.html's social meta block)."""

    def test_is_for_the_gift_page(self, client, donate_page, gift):
        response = client.get(gift_path(donate_page, gift))
        url = f"http://localhost{gift_path(donate_page, gift)}"

        assert meta(response, "og:url") == url
        assert soup(response).find("link", rel="canonical")["href"] == url

    def test_names_the_supporter_and_says_what_the_appeal_is(self, client, donate_page, gift):
        response = client.get(gift_path(donate_page, gift))

        assert meta(response, "og:title") == "Asha Gurung is supporting Flood relief"
        assert meta(response, "og:description") == gift.appeal.summary

    def test_shows_the_appeals_social_image(self, client, donate_page, appeal):
        appeal.social_image = ImageFactory()
        appeal.save_revision().publish()
        gift = pledge_in("paid", donate_page, appeal)

        image = meta(client.get(gift_path(donate_page, gift)), "og:image")

        assert "fill-1200x630" in image

    def test_without_an_appeal_photo_the_donate_pages_image(self, client, donate_page, gift):
        donate_page.social_image = ImageFactory(title="Donate photo")
        donate_page.save_revision().publish()

        image = meta(client.get(gift_path(donate_page, gift)), "og:image")

        assert image and "fill-1200x630" in image

    def test_other_pages_keep_their_own(self, client, donate_page):
        assert meta(client.get(donate_page.url), "og:url") == "http://localhost/donate/"


class TestATestGift:
    def test_says_first_that_no_money_was_taken(self, client, donate_page, appeal):
        gift = pledge_in("paid (test)", donate_page, appeal)

        page = soup(client.get(gift_path(donate_page, gift)))

        note = page.find(class_="payment-message")
        assert note.get_text(strip=True) == "Test gift: no money was taken"
        assert note.find_next("h1") is not None

    def test_a_real_gift_says_nothing_of_tests(self, client, donate_page, gift):
        assert "test" not in text(client.get(gift_path(donate_page, gift))).lower()


class TestAQRPaymentBeingChecked:
    def test_names_the_supporter_without_the_amount(self, client, donate_page, appeal):
        gift = pledge_in("to-confirm", donate_page, appeal)
        claimed_on = long_date(gift.payments.get().created_at)

        page = text(client.get(gift_path(donate_page, gift)))

        assert "Asha Gurung is supporting Flood relief" in page
        assert f"Paid by QR on {claimed_on}. Our team is checking it." in page
        assert "Gave" not in page

    def test_shows_the_amount_once_the_team_finds_it(self, client, donate_page, appeal):
        gift = pledge_in("to-confirm", donate_page, appeal)
        gift.payments.get().mark_paid(None, TODAY, 2500, "TXN-8841")

        assert "Gave Rs 2,500 on" in text(client.get(gift_path(donate_page, gift)))


class TestTheAppealsState:
    def test_once_the_target_is_reached_friends_can_still_give(self, client, donate_page, appeal):
        appeal.amount_raised = appeal.target_amount
        appeal.save_revision().publish()
        gift = pledge_in("paid", donate_page, appeal)

        page = soup(client.get(gift_path(donate_page, gift)))

        assert page.find("a", class_="button").get_text(strip=True) == "Give to this appeal"

    def test_once_closed_friends_can_give_where_its_needed_most(self, client, donate_page, appeal):
        gift = pledge_in("paid", donate_page, appeal)
        CampaignPage.objects.filter(pk=appeal.pk).update(end_date=YESTERDAY)

        page = soup(client.get(gift_path(donate_page, gift)))

        closed = f"This appeal closed on {long_date(YESTERDAY)}. Thank you to everyone who gave."
        assert closed in page.get_text(" ", strip=True)
        give = page.find("a", class_="button")
        assert give.get_text(strip=True) == "Give where it's needed most"
        assert give["href"] == "/donate/"
        assert link(page, "Give to this appeal") is None

    def test_once_closed_points_to_the_open_appeals_if_any(self, client, donate_page, appeal):
        gift = pledge_in("paid", donate_page, appeal)
        CampaignPage.objects.filter(pk=appeal.pk).update(end_date=YESTERDAY)
        # Last year's appeal is closed too, and the trustees' appeal is open but private.
        assert link(soup(client.get(gift_path(donate_page, gift))), "See our open appeals") is None

        CampaignPage.objects.get(slug="trustees").get_view_restrictions().delete()

        page = soup(client.get(gift_path(donate_page, gift)))
        assert link(page, "See our open appeals")["href"] == "/appeals/?status=active"

    @pytest.mark.parametrize("how", ["private", "unpublished", "deleted", "none"])
    def test_without_an_appeal_to_show_names_the_charity(self, client, donate_page, appeals, how):
        appeal = None if how == "none" else CampaignPage.objects.get(slug="flood-relief")
        if how == "private":
            appeal = CampaignPage.objects.get(slug="trustees")
        gift = pledge_in("paid", donate_page, appeal)
        if how == "unpublished":
            appeal.unpublish()
        if how == "deleted":
            appeal.delete()

        page = soup(client.get(gift_path(donate_page, gift)))

        assert page.h1.get_text(strip=True) == "Asha Gurung is supporting Brightwell"
        give = page.find("a", class_="button")
        assert give.get_text(strip=True) == "Give"
        assert give["href"] == "/donate/"
        assert page.find(class_="progress") is None
        for appeal_text in ("Trustees", "Flood relief", "Read about this appeal"):
            assert appeal_text not in page.get_text()


class TestAGiftNotShown:
    """Its address goes to the appeal, else the Donate page, so a name is never left up once it
    shouldn't be, and a friend with a link shared before can still give. Not for good: it may
    be shown again."""

    @pytest.mark.parametrize("state", ["ready", "check-first", "failed", "not-found"])
    def test_until_theyve_told_us_theyve_paid(self, client, donate_page, appeal, state):
        gift = pledge_in(state, donate_page, appeal)

        response = client.get(gift_path(donate_page, gift))

        assert response.status_code == 302
        assert response["Location"] == "/appeals/flood-relief/"

    def test_without_consent(self, client, donate_page, appeal):
        gift = pledge_in("paid", donate_page, appeal, show=False)

        assert client.get(gift_path(donate_page, gift))["Location"] == "/appeals/flood-relief/"

    def test_once_the_supporter_withdraws_it(self, client, donate_page, gift):
        Pledge.objects.filter(pk=gift.pk).update(show_on_website=False)

        assert client.get(gift_path(donate_page, gift))["Location"] == "/appeals/flood-relief/"

    def test_once_the_team_takes_it_down(self, client, donate_page, gift):
        Pledge.objects.filter(pk=gift.pk).update(hidden_by_team=True)

        response = client.get(gift_path(donate_page, gift))

        assert response.status_code == 302
        assert response["Location"] == "/appeals/flood-relief/"
        assert "Asha" not in client.get(response["Location"]).content.decode()

    @pytest.mark.parametrize("how", ["private", "none"])
    def test_without_an_appeal_to_show_the_donate_page(self, client, donate_page, appeals, how):
        appeal = CampaignPage.objects.get(slug="trustees") if how == "private" else None
        gift = pledge_in("paid", donate_page, appeal, hidden_by_team=True)

        assert client.get(gift_path(donate_page, gift))["Location"] == "/donate/"

    def test_for_an_unknown_code(self, client, donate_page):
        assert client.get(f"{donate_page.url}gifts/not-a-gift-code/").status_code == 404

    def test_never_at_its_pay_pages_reference(self, client, donate_page, gift):
        assert client.get(f"{donate_page.url}gifts/{gift.reference}/").status_code == 404
