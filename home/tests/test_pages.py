import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from wagtail.models import Page
from wagtail.test.utils.form_data import nested_form_data, rich_text, streamfield
from wagtail_factories import ImageFactory

from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory
from home.models import HomePage, StandardPage

pytestmark = pytest.mark.django_db


def add_standard_page(parent, **kwargs):
    page = StandardPage(title=kwargs.pop("title", "About us"), **kwargs)
    parent.add_child(instance=page)
    page.save_revision().publish()
    return page


class TestPageTreeRules:
    def test_there_can_only_be_one_home_page(self, home_page):
        assert not HomePage.can_create_at(home_page)
        assert not HomePage.can_create_at(Page.get_first_root_node())

    def test_standard_pages_live_under_home_or_other_standard_pages(self, home_page):
        about = add_standard_page(home_page)

        assert StandardPage.can_create_at(home_page)
        assert StandardPage.can_create_at(about)


class TestHomePage:
    def test_renders_hero_content(self, client, home_page):
        home_page.hero_heading = "Clean water for everyone"
        home_page.hero_text = "Every £10 brings safe water to one person for a year."
        home_page.hero_image = ImageFactory(description="A child drinking water")
        home_page.hero_cta_text = "Donate now"
        home_page.save_revision().publish()

        html = client.get("/").content.decode()

        assert "Clean water for everyone" in html
        assert "Every £10 brings safe water" in html
        assert 'alt="A child drinking water"' in html
        assert "Donate now" in html

    def test_renders_streamfield_body(self, client, home_page):
        home_page.body = [("heading", {"heading_text": "How we work", "size": "h2"})]
        home_page.save_revision().publish()

        assert "How we work" in client.get("/").content.decode()

    def test_appeal_titles_sit_under_the_current_appeals_heading(self, client, home_page):
        appeals = CampaignIndexPageFactory(parent=home_page)
        CampaignPageFactory(parent=appeals, title="Well building")

        soup = BeautifulSoup(client.get("/").content, "html.parser")

        assert soup.select_one(".featured-campaigns h2").text == "Current appeals"
        assert [h3.text for h3 in soup.select(".campaign-card h3")] == ["Well building"]

    def test_lists_only_appeals_in_its_own_language(self, client, home_page, nepali_home_page):
        appeals = CampaignIndexPageFactory(parent=home_page)
        CampaignPageFactory(parent=appeals, title="Well building")
        nepali_appeals = appeals.copy_for_translation(nepali_home_page.locale)
        nepali_appeals.save_revision().publish()
        CampaignPageFactory(parent=nepali_appeals, title="इनार निर्माण")

        def appeal_titles(path):
            soup = BeautifulSoup(client.get(path).content, "html.parser")
            return [h3.text for h3 in soup.select(".campaign-card h3")]

        assert appeal_titles("/") == ["Well building"]
        assert appeal_titles("/ne/") == ["इनार निर्माण"]


class TestStandardPage:
    def test_renders_introduction_and_body(self, client, home_page):
        page = add_standard_page(
            home_page,
            title="Our story",
            introduction="Founded in 2004 by a group of engineers.",
            body=[("quote", {"text": "Start small, stay local.", "attribution": "Founder"})],
        )

        html = client.get(page.url).content.decode()

        assert "Our story" in html
        assert "Founded in 2004" in html
        assert "Start small, stay local." in html

    def test_editor_can_create_a_standard_page_in_the_admin(self, admin_client, home_page):
        url = reverse("wagtailadmin_pages:add", args=("home", "standardpage", home_page.pk))
        data = nested_form_data(
            {
                "title": "Our team",
                "slug": "our-team",
                "introduction": "Meet the people behind the work.",
                "body": streamfield(
                    [("paragraph", rich_text("<p>We are twelve staff and 300 volunteers.</p>"))]
                ),
                "action-publish": "publish",
            }
        )

        response = admin_client.post(url, data)

        assert response.status_code == 302
        page = StandardPage.objects.get(slug="our-team")
        assert page.live
        assert page.body[0].block_type == "paragraph"
