import datetime
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.urls import reverse
from wagtail.models import PageViewRestriction
from wagtail.test.utils.form_data import inline_formset, nested_form_data, streamfield
from wagtail_factories import ImageFactory

from campaigns.models import CampaignIndexPage, CampaignPage
from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory
from core.models import SiteSettings
from home.models import HomePage, StandardPage

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()


@pytest.fixture
def campaign_index(home_page):
    return CampaignIndexPageFactory(parent=home_page)


def closed_campaign(parent, **kwargs):
    return CampaignPageFactory(
        parent=parent,
        start_date=TODAY - datetime.timedelta(days=90),
        end_date=TODAY - datetime.timedelta(days=1),
        **kwargs,
    )


class TestPageTreeRules:
    def test_campaign_index_lives_under_the_home_page(self, home_page):
        assert CampaignIndexPage.can_create_at(home_page)

    def test_campaigns_live_only_under_the_campaign_index(self, home_page, campaign_index):
        assert CampaignPage.can_create_at(campaign_index)
        assert not CampaignPage.can_create_at(home_page)

    def test_campaigns_have_no_child_pages(self, campaign_index):
        campaign = CampaignPageFactory(parent=campaign_index)

        assert CampaignPage.allowed_subpage_models() == []
        assert not StandardPage.can_create_at(campaign)
        assert not HomePage.can_create_at(campaign)


class TestFundraisingProgress:
    @pytest.mark.parametrize(
        ("target", "raised", "expected"),
        [
            ("10000", "2500", 25),
            ("10000", "0", 0),
            ("10000", "15000", 100),
            ("0", "500", 0),
            ("3000", "1000", 33),
        ],
    )
    def test_progress_percent(self, target, raised, expected):
        campaign = CampaignPage(target_amount=Decimal(target), amount_raised=Decimal(raised))

        assert campaign.progress_percent == expected

    def test_campaign_without_end_date_is_active(self):
        assert CampaignPage(start_date=TODAY, end_date=None).is_active

    def test_campaign_ending_today_is_still_active(self):
        assert CampaignPage(start_date=TODAY, end_date=TODAY).is_active

    def test_campaign_that_has_ended_is_closed(self):
        yesterday = TODAY - datetime.timedelta(days=1)

        assert not CampaignPage(start_date=yesterday, end_date=yesterday).is_active

    def test_end_date_cannot_be_before_start_date(self, campaign_index):
        campaign = CampaignPageFactory.build(
            start_date=TODAY, end_date=TODAY - datetime.timedelta(days=1)
        )

        with pytest.raises(ValidationError) as excinfo:
            campaign.clean()

        assert "end_date" in excinfo.value.message_dict


class TestCampaignPage:
    def test_shows_progress_and_suggested_donations(self, client, campaign_index):
        campaign = CampaignPageFactory(
            parent=campaign_index,
            title="Clean water for Kisumu",
            target_amount=Decimal("10000"),
            amount_raised=Decimal("2500"),
            body=[("heading", {"heading_text": "Why it matters", "size": "h2"})],
        )
        campaign.donation_amounts.create(amount=10, impact="Clean water for one person")
        campaign.donation_amounts.create(amount=250, impact="A hand pump repair")
        campaign.save_revision().publish()

        html = client.get(campaign.url).content.decode()

        assert "Clean water for Kisumu" in html
        assert "Rs 2,500 raised of Rs 10,000" in html
        assert 'style="width: 25%"' in html
        assert "Rs 10<" in html and "Clean water for one person" in html
        assert "Rs 250<" in html and "A hand pump repair" in html
        assert "Why it matters" in html

    def test_donate_button_tells_the_donate_page_which_appeal(
        self, client, site, home_page, campaign_index
    ):
        donate = StandardPage(title="Donate", slug="donate")
        home_page.add_child(instance=donate)
        settings = SiteSettings.for_site(site)
        settings.donate_page = donate
        settings.save()
        campaign = CampaignPageFactory(parent=campaign_index, slug="flood-relief")
        campaign.donation_amounts.create(amount=2500, impact="A hygiene kit for a family")
        campaign.save_revision().publish()

        html = client.get(campaign.url).content.decode()

        assert f'href="{donate.url}?appeal=flood-relief"' in html

    def test_can_preview_the_listing_card(self, campaign_index):
        campaign = CampaignPageFactory(parent=campaign_index, title="Winter appeal")

        assert [mode for mode, _ in campaign.preview_modes] == ["", "card"]
        response = campaign.make_preview_request(preview_mode="card")

        html = response.content.decode()
        assert 'class="card' in html
        assert "Winter appeal" in html

    def test_editor_can_create_a_campaign_with_donation_amounts(self, admin_client, campaign_index):
        url = reverse(
            "wagtailadmin_pages:add", args=("campaigns", "campaignpage", campaign_index.pk)
        )
        data = nested_form_data(
            {
                "title": "Emergency flood appeal",
                "slug": "flood-appeal",
                "summary": "Families have lost their homes.",
                "body": streamfield([]),
                "target_amount": "50000",
                "amount_raised": "0",
                "start_date": TODAY.isoformat(),
                "donation_amounts": inline_formset(
                    [{"amount": "25", "impact": "A hygiene kit for a family"}]
                ),
                "action-publish": "publish",
            }
        )

        response = admin_client.post(url, data)

        assert response.status_code == 302
        campaign = CampaignPage.objects.get(slug="flood-appeal")
        assert campaign.live
        assert campaign.donation_amounts.get().impact == "A hygiene kit for a family"


class TestCampaignIndexPage:
    def test_lists_live_campaigns_only(self, client, campaign_index):
        CampaignPageFactory(parent=campaign_index, title="Published appeal")
        CampaignPageFactory(parent=campaign_index, title="Draft appeal", live=False)

        html = client.get(campaign_index.url).content.decode()

        assert "Published appeal" in html
        assert "Draft appeal" not in html

    def test_filters_by_status(self, client, campaign_index):
        CampaignPageFactory(parent=campaign_index, title="Well building")
        closed_campaign(campaign_index, title="Winter appeal 2024")

        def titles(status):
            response = client.get(campaign_index.url, {"status": status})
            return [campaign.title for campaign in response.context["campaigns"]]

        assert titles("active") == ["Well building"]
        assert titles("closed") == ["Winter appeal 2024"]
        assert sorted(titles("nonsense")) == ["Well building", "Winter appeal 2024"]

    @pytest.mark.parametrize(
        ("status", "selected"),
        [(None, "All appeals"), ("active", "Open appeals"), ("closed", "Past appeals")],
    )
    def test_marks_the_selected_filter(self, client, campaign_index, status, selected):
        query = {"status": status} if status else {}
        html = client.get(campaign_index.url, query).content
        filters = BeautifulSoup(html, "html.parser").find("nav", {"aria-label": "Filter appeals"})

        assert [link.text for link in filters.select('a[aria-current="page"]')] == [selected]

    def test_appeal_titles_are_one_level_below_the_page_title(self, client, campaign_index):
        CampaignPageFactory(parent=campaign_index, title="Well building")

        soup = BeautifulSoup(client.get(campaign_index.url).content, "html.parser")

        assert [h2.text for h2 in soup.select(".campaign-card h2")] == ["Well building"]
        assert not soup.select(".campaign-card h3")

    def test_paginates_campaigns(self, client, campaign_index):
        for n in range(CampaignIndexPage.campaigns_per_page + 1):
            CampaignPageFactory(parent=campaign_index, title=f"Appeal {n:02d}")

        first = client.get(campaign_index.url)
        second = client.get(campaign_index.url, {"page": 2})

        assert len(first.context["campaigns"]) == CampaignIndexPage.campaigns_per_page
        assert len(second.context["campaigns"]) == 1

    def test_invalid_page_number_falls_back_to_the_first_page(self, client, campaign_index):
        CampaignPageFactory(parent=campaign_index)

        response = client.get(campaign_index.url, {"page": "abc"})

        assert response.status_code == 200
        assert response.context["campaigns"].number == 1


def test_home_page_features_up_to_three_active_campaigns(client, home_page, campaign_index):
    for n in range(4):
        CampaignPageFactory(parent=campaign_index, title=f"Active appeal {n}")
    closed_campaign(campaign_index, title="Closed appeal")

    response = client.get("/")

    featured = response.context["featured_campaigns"]
    assert len(featured) == 3
    assert all(campaign.is_active for campaign in featured)
    assert "Closed appeal" not in response.content.decode()


class TestPrivateCampaigns:
    """An appeal behind a password or a login is still being prepared, so lists must hide it."""

    @pytest.fixture
    def private_campaigns(self, campaign_index):
        CampaignPageFactory(parent=campaign_index, title="Open public appeal")
        closed_campaign(campaign_index, title="Closed public appeal")
        return [
            CampaignPageFactory(parent=campaign_index, title="Open private appeal"),
            closed_campaign(campaign_index, title="Closed private appeal"),
        ]

    @pytest.fixture(params=[PageViewRestriction.PASSWORD, PageViewRestriction.LOGIN])
    def restricted(self, request, private_campaigns):
        for campaign in private_campaigns:
            PageViewRestriction.objects.create(
                page=campaign, restriction_type=request.param, password="trustees"
            )

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("", ["Closed public appeal", "Open public appeal"]),
            ("active", ["Open public appeal"]),
            ("closed", ["Closed public appeal"]),
        ],
    )
    def test_are_left_out_of_the_appeals_page(
        self, client, campaign_index, restricted, status, expected
    ):
        response = client.get(campaign_index.url, {"status": status})

        assert sorted(campaign.title for campaign in response.context["campaigns"]) == expected
        assert "private appeal" not in response.content.decode()

    def test_are_left_out_of_the_home_page(self, client, home_page, restricted):
        response = client.get("/")

        assert [campaign.title for campaign in response.context["featured_campaigns"]] == [
            "Open public appeal"
        ]
        assert "private appeal" not in response.content.decode()


class TestCardImages:
    def test_cards_offer_small_modern_images_that_load_lazily(self, client, campaign_index):
        photo = ImageFactory(file__width=1600, file__height=900, description="A family at a well")
        CampaignPageFactory(parent=campaign_index, hero_image=photo)

        html = BeautifulSoup(client.get(campaign_index.url).content, "html.parser")

        picture = html.select_one(".campaign-card picture")
        assert [source["type"] for source in picture.find_all("source")] == [
            "image/avif",
            "image/webp",
        ]
        img = picture.img
        assert img["srcset"].count("w, ") == 1  # two widths
        # The <img> keeps its full size, so it fills the card; the browser picks a smaller file.
        assert (img["width"], img["height"]) == ("640", "360")
        assert img["loading"] == "lazy"
        assert img["alt"] == "A family at a well"

    @pytest.mark.parametrize("listing", ["home page", "appeals page"])
    def test_card_images_add_no_query_per_card(self, cold_cache_queries, campaign_index, listing):
        path = "/" if listing == "home page" else campaign_index.url

        CampaignPageFactory(parent=campaign_index, hero_image=ImageFactory())
        with_one_card = cold_cache_queries(path)
        for _ in range(2):
            CampaignPageFactory(parent=campaign_index, hero_image=ImageFactory())

        assert cold_cache_queries(path) == with_one_card
