"""Sharing that you've given, from the thank-you and checking pages (#100): the share section,
the box that shows the gift on its page for friends, and saving it.

What may be shown and shared comes from campaigns/sharing.py (test_sharing.py).
"""

import pytest
from bs4 import BeautifulSoup

from campaigns import sharing
from campaigns.forms import SHOW_GIFT_HELP, SHOW_GIFT_LABEL
from campaigns.models import CampaignPage, Pledge
from campaigns.tests.test_sharing import STATES, pledge_in
from core.models import SiteSettings

pytestmark = pytest.mark.django_db

SHARING_STATES = ["paid", "paid (test)", "received", "to-confirm"]


def soup(response):
    return BeautifulSoup(response.content, "html.parser")


def words(element):
    return " ".join(element.get_text().split())


def pay_url(donate_page, pledge, tail=""):
    return f"{donate_page.url}pay/{pledge.reference}/{tail}"


def page_for(client, donate_page, pledge):
    """The page a pledge's pay address shows: thanks, or the checking page."""
    return soup(client.get(pay_url(donate_page, pledge), follow=True))


def show_gift(client, donate_page, pledge, shown=True):
    data = {"show_on_website": "on"} if shown else {}
    return client.post(pay_url(donate_page, pledge, "show-gift/"), data)


@pytest.fixture(autouse=True)
def charity(site):
    site.site_name = "Brightwell"
    site.save()


@pytest.fixture
def phone(site):
    site_settings = SiteSettings.for_site(site)
    site_settings.phone = "+977 1-4567890"
    site_settings.save()


@pytest.fixture
def appeal(appeals):
    return CampaignPage.objects.get(slug="flood-relief")


class TestTheShareSection:
    @pytest.mark.parametrize("state", SHARING_STATES)
    def test_is_offered_once_theyve_told_us_theyve_paid(self, client, donate_page, state):
        page = page_for(client, donate_page, pledge_in(state, donate_page, show=False))

        assert page.find("h2", string="Others can help too") is not None

    @pytest.mark.parametrize("state", [s for s in STATES if s not in SHARING_STATES])
    def test_isnt_offered_before(self, client, donate_page, fake_provider, state):
        page = page_for(client, donate_page, pledge_in(state, donate_page))

        assert page.find(class_="share-gift") is None
        assert "Tell your friends" not in page.get_text()

    def test_comes_after_the_reference_on_the_thank_you_page(self, client, donate_page):
        page = page_for(client, donate_page, pledge_in("paid", donate_page))

        reference = page.find("p", string="eSewa reference: ESW-1")
        assert reference.find_next("section") is page.find(class_="share-gift")

    def test_comes_after_what_they_sent_on_the_checking_page(self, client, donate_page, phone):
        page = page_for(client, donate_page, pledge_in("to-confirm", donate_page))

        sent = page.find("p", string="You sent us the transaction ID TXN-8841.")
        section = page.find(class_="share-gift")
        assert sent.find_next_sibling() is section
        assert section.find_next_sibling("p").get_text().startswith("Questions?")

    def test_invites_friends_to_an_appeal_that_needs_help(self, client, donate_page, appeal):
        section = page_for(client, donate_page, pledge_in("paid", donate_page, appeal)).find(
            class_="share-gift"
        )

        assert (
            "Flood relief still needs support. If you tell your friends, their gifts can help as "
            "well." in words(section)
        )

    def test_once_the_target_is_reached_says_every_gift_goes_further(
        self, client, donate_page, appeal
    ):
        appeal.amount_raised = appeal.target_amount
        appeal.save_revision().publish()

        section = page_for(client, donate_page, pledge_in("paid", donate_page, appeal)).find(
            class_="share-gift"
        )

        assert (
            "Flood relief has reached its target. Your friends can still help: every gift goes "
            "further." in words(section)
        )

    def test_for_wherever_its_needed_most_invites_friends_to_the_work(self, client, donate_page):
        section = page_for(client, donate_page, pledge_in("paid", donate_page)).find(
            class_="share-gift"
        )

        assert (
            "Our work still needs support. If you tell your friends, their gifts can help as well."
            in words(section)
        )


class TestTheShareLinks:
    """WhatsApp, Facebook and Copy link work without the phone's share sheet; Tell your friends
    opens it (donate.js). No scripts from anyone else."""

    def links(self, client, donate_page, pledge):
        return page_for(client, donate_page, pledge).find(class_="share-gift")

    def test_with_consent_share_the_gifts_page(self, client, donate_page, appeal):
        pledge = pledge_in("paid", donate_page, appeal)
        section = self.links(client, donate_page, pledge)
        url = f"http://localhost{donate_page.url}gifts/{pledge.gift_code}/"
        text = sharing.share_text(pledge, appeal, "Brightwell")

        assert section.find("a", string="WhatsApp")["href"] == sharing.whatsapp_link(text, url)
        assert section.find("a", string="Facebook")["href"] == sharing.facebook_link(url)
        assert section.find("button", attrs={"data-copy-value": url}).get_text() == "Copy link"
        share = section.find("button", attrs={"data-share": True})
        assert (share["data-share-url"], share["data-share-text"]) == (url, text)
        assert share["data-share-title"] == "Asha Gurung is supporting Flood relief"

    def test_without_consent_share_the_appeal_with_no_name(self, client, donate_page, appeal):
        pledge = pledge_in("paid", donate_page, appeal, show=False)
        section = self.links(client, donate_page, pledge)

        share = section.find("button", attrs={"data-share": True})
        assert share["data-share-url"] == "http://localhost/appeals/flood-relief/"
        assert share["data-share-title"] == "Flood relief"
        assert "Asha" not in str(section.find_all(["a", "button"]))

    def test_tell_your_friends_and_copy_link_wait_for_javascript(self, client, donate_page):
        section = self.links(client, donate_page, pledge_in("paid", donate_page))

        assert section.find("button", string="Tell your friends").has_attr("hidden")
        assert section.find("button", string="Copy link").has_attr("hidden")

    def test_links_open_in_the_same_tab(self, client, donate_page):
        section = self.links(client, donate_page, pledge_in("paid", donate_page))

        assert all(not link.has_attr("target") for link in section.find_all("a"))

    @pytest.mark.parametrize("state", SHARING_STATES)
    @pytest.mark.parametrize("show", [True, False])
    def test_never_share_the_pay_pages_reference(self, client, donate_page, appeal, state, show):
        pledge = pledge_in(state, donate_page, appeal, show=show)
        section = self.links(client, donate_page, pledge)

        shared = [link["href"] for link in section.find_all("a")]
        for button in section.find_all("button", attrs={"type": "button"}):
            shared += [value for name, value in button.attrs.items() if name.startswith("data-")]
        for value in shared:
            assert str(pledge.reference) not in value
            assert pledge.reference.hex not in value


class TestTheThanks:
    """What must not change, and the two changes: what the gift does, and the appeals as a plain
    link."""

    def test_the_lead_still_says_what_happened_and_takes_focus(self, client, donate_page):
        page = page_for(client, donate_page, pledge_in("paid", donate_page))

        lead = page.find(class_="lead")
        assert lead.get_text() == "Your gift of Rs 2,500 has reached us."
        assert lead.has_attr("data-focus-on-load")

    def test_then_says_what_the_gift_does(self, client, donate_page):
        page = page_for(client, donate_page, pledge_in("paid", donate_page))

        assert page.find(class_="lead").find_next("p").get_text() == (
            "It pays for a hygiene kit for a family."
        )

    def test_a_test_payment_doesnt_say_what_it_pays_for(self, client, donate_page):
        """No money moved, so it pays for nothing."""
        page = page_for(client, donate_page, pledge_in("paid (test)", donate_page))

        assert "It pays for" not in page.get_text()

    def test_money_received_for_another_amount_says_what_that_does(self, client, donate_page):
        page = page_for(client, donate_page, pledge_in("received", donate_page))

        assert "It pays for a hygiene kit for a family." in page.get_text()

    def test_the_appeals_are_a_plain_link(self, client, donate_page):
        page = page_for(client, donate_page, pledge_in("paid", donate_page))

        appeals = page.find("a", string="See all our appeals")
        assert appeals["href"] == "/appeals/"
        assert "button" not in appeals.get("class", [])


class TestTheShowMyGiftBox:
    """One consent, in the pledge form's own words: ticked if they agreed there."""

    @pytest.mark.parametrize("agreed", [True, False])
    def test_starts_as_they_left_it_on_the_form(self, client, donate_page, agreed):
        page = page_for(client, donate_page, pledge_in("paid", donate_page, show=agreed))

        box = page.find("input", attrs={"name": "show_on_website"})
        assert box.has_attr("checked") is agreed

    def test_says_exactly_what_the_form_says(self, client, donate_page):
        page = page_for(client, donate_page, pledge_in("paid", donate_page))

        box = page.find("input", attrs={"name": "show_on_website"})
        assert words(box.find_parent("label")) == SHOW_GIFT_LABEL
        assert page.find(id=box["aria-describedby"]).get_text(strip=True) == SHOW_GIFT_HELP
        assert box.find_next("button").get_text(strip=True) == "Save"

    def test_on_the_checking_page_too(self, client, donate_page):
        page = page_for(client, donate_page, pledge_in("to-confirm", donate_page))

        assert page.find("input", attrs={"name": "show_on_website"}) is not None

    def test_once_the_team_takes_the_page_down_says_to_call(self, client, donate_page, phone):
        page = page_for(client, donate_page, pledge_in("paid", donate_page, hidden_by_team=True))

        section = page.find(class_="share-gift")
        assert section.find("input", attrs={"name": "show_on_website"}) is None
        assert "Our team has taken your page down. If you'd like it back, call us:" in words(
            section
        )
        assert section.find("a", href="tel:+97714567890").get_text() == "+977 1-4567890"

    def test_without_a_phone_just_says_its_down(self, client, donate_page):
        page = page_for(client, donate_page, pledge_in("paid", donate_page, hidden_by_team=True))

        section = words(page.find(class_="share-gift"))
        assert "Our team has taken your page down." in section
        assert "call us" not in section


class TestSavingIt:
    def test_ticked_shows_the_gift_and_records_when(self, client, donate_page):
        pledge = pledge_in("paid", donate_page, show=False)

        response = show_gift(client, donate_page, pledge)

        assert response.status_code == 303
        assert response["Location"] == pay_url(donate_page, pledge) + "#share"
        pledge.refresh_from_db()
        assert pledge.show_on_website is True
        assert pledge.show_on_website_changed_at is not None
        assert client.get(f"{donate_page.url}gifts/{pledge.gift_code}/").status_code == 200

    def test_says_the_page_is_ready_and_moves_focus_there(self, client, donate_page):
        pledge = pledge_in("paid", donate_page, show=False)

        page = soup(show_gift_and_follow(client, donate_page, pledge))

        heading = page.find("h2", string="Others can help too")
        assert heading.has_attr("data-focus-on-load")
        assert not page.find(class_="lead").has_attr("data-focus-on-load")
        status = heading.find_next("p")
        assert status["role"] == "status"
        assert status.get_text() == "Your page for friends is ready."

    def test_says_it_once(self, client, donate_page):
        pledge = pledge_in("paid", donate_page, show=False)
        show_gift_and_follow(client, donate_page, pledge)

        assert "is ready" not in page_for(client, donate_page, pledge).get_text()

    def test_unticked_takes_the_page_down(self, client, donate_page):
        pledge = pledge_in("paid", donate_page)

        page = soup(show_gift_and_follow(client, donate_page, pledge, shown=False))

        assert Pledge.objects.get(pk=pledge.pk).show_on_website is False
        assert "Your page for friends has been taken down." in page.get_text()
        assert client.get(f"{donate_page.url}gifts/{pledge.gift_code}/").status_code == 404

    def test_saving_the_same_choice_keeps_when_it_was_made(self, client, donate_page):
        pledge = pledge_in("paid", donate_page)
        agreed_at = pledge.show_on_website_changed_at

        show_gift(client, donate_page, pledge)

        assert Pledge.objects.get(pk=pledge.pk).show_on_website_changed_at == agreed_at

    def test_agreed_in_the_old_words_the_box_starts_unticked(self, client, donate_page):
        """They agreed to their name once the gift reaches us, not while it's checked."""
        pledge = pledge_in("to-confirm", donate_page)
        Pledge.objects.filter(pk=pledge.pk).update(show_on_website_changed_at=None)

        box = page_for(client, donate_page, pledge).find("input", attrs={"name": "show_on_website"})

        assert not box.has_attr("checked")

    def test_ticking_it_again_agrees_in_the_new_words(self, client, donate_page):
        pledge = pledge_in("to-confirm", donate_page)
        Pledge.objects.filter(pk=pledge.pk).update(show_on_website_changed_at=None)

        show_gift(client, donate_page, pledge)

        assert Pledge.objects.get(pk=pledge.pk).show_on_website_changed_at is not None
        assert client.get(f"{donate_page.url}gifts/{pledge.gift_code}/").status_code == 200

    def test_from_the_checking_page_goes_back_there(self, client, donate_page):
        pledge = pledge_in("to-confirm", donate_page, show=False)

        response = show_gift(client, donate_page, pledge)

        assert response["Location"] == pay_url(donate_page, pledge, "checking/") + "#share"
        assert Pledge.objects.get(pk=pledge.pk).show_on_website is True

    @pytest.mark.parametrize("state", [s for s in STATES if s not in SHARING_STATES])
    def test_is_refused_before_theyve_told_us_theyve_paid(self, client, donate_page, state):
        pledge = pledge_in(state, donate_page, show=False)

        show_gift(client, donate_page, pledge)

        assert Pledge.objects.get(pk=pledge.pk).show_on_website is False

    def test_is_refused_once_the_team_has_taken_it_down(self, client, donate_page):
        pledge = pledge_in("paid", donate_page, hidden_by_team=True)

        show_gift(client, donate_page, pledge, shown=False)
        show_gift(client, donate_page, pledge)

        pledge.refresh_from_db()
        assert pledge.hidden_by_team is True
        assert client.get(f"{donate_page.url}gifts/{pledge.gift_code}/").status_code == 404

    def test_only_by_sending_the_form(self, client, donate_page):
        pledge = pledge_in("paid", donate_page, show=False)

        assert client.get(pay_url(donate_page, pledge, "show-gift/")).status_code == 405

    def test_an_unknown_pledge_isnt_found(self, client, donate_page):
        pledge = Pledge(reference="00000000-0000-4000-8000-000000000000")

        assert show_gift(client, donate_page, pledge).status_code == 404


def show_gift_and_follow(client, donate_page, pledge, shown=True):
    response = show_gift(client, donate_page, pledge, shown)
    return client.get(response["Location"].removesuffix("#share"))
