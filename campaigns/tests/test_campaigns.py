import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from wagtail.test.utils.form_data import inline_formset, nested_form_data, streamfield

from campaigns.models import CampaignIndexPage, CampaignPage
from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory
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
        assert "£2,500 raised of £10,000" in html
        assert 'style="width: 25%"' in html
        assert "£10" in html and "Clean water for one person" in html
        assert "£250" in html and "A hand pump repair" in html
        assert "Why it matters" in html

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
