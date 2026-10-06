import io
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
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
    ImageFactory(title="Well photo", consent_confirmed=True)
    DocumentFactory(title="Annual report")

    images = client.get(f"{API}/images/").json()["items"]
    documents = client.get(f"{API}/documents/").json()["items"]

    assert [image["title"] for image in images] == ["Well photo"]
    assert [document["title"] for document in documents] == ["Annual report"]


class TestImageConsent:
    """Photos of people must not be published until consent has been recorded."""

    def test_images_without_consent_are_not_listed(self, client, db):
        ImageFactory(title="Consented", consent_confirmed=True)
        ImageFactory(title="Awaiting consent", consent_confirmed=False)

        images = client.get(f"{API}/images/").json()["items"]

        assert [image["title"] for image in images] == ["Consented"]

    def test_image_without_consent_has_no_detail_or_download_url(self, client, db):
        image = ImageFactory(consent_confirmed=False)

        response = client.get(f"{API}/images/{image.pk}/")

        assert response.status_code == 404


def test_links_point_at_the_site_url(client, settings, campaign):
    settings.SITE_URL = "https://brightwell.example"
    call_command("update_site_url", stdout=io.StringIO())

    [item] = client.get(f"{API}/pages/", {"type": "campaigns.CampaignPage"}).json()["items"]

    assert item["meta"]["html_url"] == f"https://brightwell.example{campaign.url}"
    assert item["meta"]["detail_url"] == f"https://brightwell.example{API}/pages/{campaign.pk}/"


def test_api_is_read_only(client, campaign):
    response = client.post(f"{API}/pages/", {"title": "Hacked"})

    assert response.status_code == 405


class TestLanguages:
    def test_pages_can_be_listed_in_one_language(self, client, home_page, nepali_home_page):
        nepali = client.get(f"{API}/pages/", {"locale": "ne"}).json()["items"]
        english = client.get(f"{API}/pages/", {"locale": "en"}).json()["items"]

        assert [(page["title"], page["meta"]["locale"]) for page in nepali] == [("गृहपृष्ठ", "ne")]
        assert [page["meta"]["locale"] for page in english] == ["en"]

    def test_reading_each_page_s_language_costs_no_query_per_page(self, client, campaign_index):
        for _ in range(3):
            CampaignPageFactory(parent=campaign_index)

        with CaptureQueriesContext(connection) as queries:
            client.get(f"{API}/pages/", {"type": "campaigns.CampaignPage"})

        sql = [query["sql"] for query in queries.captured_queries]
        assert not [q for q in sql if q.startswith('SELECT "wagtailcore_locale"')]
