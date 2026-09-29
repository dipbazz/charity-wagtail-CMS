from decimal import Decimal

import pytest
from wagtail.models import PageViewRestriction
from wagtail_factories import DocumentFactory, ImageFactory

from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory
from news.tests.factories import NewsIndexPageFactory, NewsPageFactory

pytestmark = pytest.mark.django_db

API = "/api/v2"


@pytest.fixture
def campaign_index(home_page):
    return CampaignIndexPageFactory(parent=home_page)


@pytest.fixture
def campaign(campaign_index):
    page = CampaignPageFactory(
        parent=campaign_index,
        title="Clean water for Kisumu",
        summary="Wells for 12 villages.",
        target_amount=Decimal("10000"),
        amount_raised=Decimal("2500"),
        hero_image=ImageFactory(description="A new well"),
        body=[("heading", {"heading_text": "Why it matters", "size": "h2"})],
    )
    page.donation_amounts.create(amount=10, impact="Clean water for one person")
    page.save_revision().publish()
    return page


class TestCampaignsEndpoint:
    def test_lists_campaigns_with_fundraising_fields(self, client, campaign):
        response = client.get(
            f"{API}/pages/",
            {
                "type": "campaigns.CampaignPage",
                "fields": "summary,target_amount,amount_raised,progress_percent,is_active",
            },
        )

        assert response.status_code == 200
        [item] = response.json()["items"]
        assert item["title"] == "Clean water for Kisumu"
        assert item["summary"] == "Wells for 12 villages."
        assert Decimal(item["target_amount"]) == Decimal("10000")
        assert item["progress_percent"] == 25
        assert item["is_active"] is True

    def test_detail_includes_body_image_rendition_and_donation_amounts(self, client, campaign):
        data = client.get(f"{API}/pages/{campaign.pk}/").json()

        assert data["body"][0]["type"] == "heading"
        assert data["body"][0]["value"]["heading_text"] == "Why it matters"
        assert "fill-800x450" in data["hero_image"]["url"]
        assert data["hero_image"]["alt"] == "A new well"
        assert data["donation_amounts"][0]["amount"] == 10
        assert data["donation_amounts"][0]["impact"] == "Clean water for one person"

    def test_hides_drafts_and_private_pages(self, client, campaign_index):
        CampaignPageFactory(parent=campaign_index, title="Draft appeal", live=False)
        private = CampaignPageFactory(parent=campaign_index, title="Private appeal")
        PageViewRestriction.objects.create(
            page=private, restriction_type=PageViewRestriction.PASSWORD, password="secret"
        )

        response = client.get(f"{API}/pages/", {"type": "campaigns.CampaignPage"})

        assert response.json()["items"] == []


def test_news_endpoint_includes_date_tags_and_categories(client, home_page):
    index = NewsIndexPageFactory(parent=home_page)
    story = NewsPageFactory(parent=index, title="Well opens")
    story.tags.add("water")
    story.save_revision().publish()

    response = client.get(
        f"{API}/pages/", {"type": "news.NewsPage", "fields": "date,introduction,tags"}
    )

    [item] = response.json()["items"]
    assert item["title"] == "Well opens"
    assert item["tags"] == ["water"]


def test_images_and_documents_endpoints(client, db):
    ImageFactory(title="Well photo")
    DocumentFactory(title="Annual report")

    images = client.get(f"{API}/images/").json()["items"]
    documents = client.get(f"{API}/documents/").json()["items"]

    assert [image["title"] for image in images] == ["Well photo"]
    assert [document["title"] for document in documents] == ["Annual report"]


def test_api_is_read_only(client, campaign):
    response = client.post(f"{API}/pages/", {"title": "Hacked"})

    assert response.status_code == 405
