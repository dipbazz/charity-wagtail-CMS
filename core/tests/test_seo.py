import re

import pytest
from django.urls import reverse
from wagtail.contrib.redirects.models import Redirect
from wagtail_factories import ImageFactory

from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory
from home.models import HomePage, StandardPage

pytestmark = pytest.mark.django_db


def meta_content(html, prop):
    match = re.search(rf'<meta property="{prop}" content="([^"]*)"', html)
    return match.group(1) if match else None


class TestSitemap:
    def test_lists_live_pages_with_full_urls(self, client, home_page):
        home_page.add_child(instance=StandardPage(title="About us", slug="about"))
        home_page.add_child(instance=StandardPage(title="Draft", slug="draft", live=False))

        response = client.get("/sitemap.xml")

        assert response.status_code == 200
        body = response.content.decode()
        assert "<loc>http://localhost/about/</loc>" in body
        assert "/draft/" not in body

    def test_lists_pages_in_every_language(self, client, home_page, nepali_home_page):
        about = StandardPage(title="About us", slug="about")
        home_page.add_child(instance=about)
        about.copy_for_translation(nepali_home_page.locale).save_revision().publish()

        body = client.get("/sitemap.xml").content.decode()

        assert "<loc>http://localhost/about/</loc>" in body
        assert "<loc>http://localhost/ne/</loc>" in body
        assert "<loc>http://localhost/ne/about/</loc>" in body


def test_robots_txt_blocks_admin_and_points_to_the_sitemap(client, home_page):
    response = client.get("/robots.txt")

    assert response["Content-Type"].startswith("text/plain")
    body = response.content.decode()
    assert "Disallow: /admin/" in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


class TestSocialMeta:
    def test_page_has_canonical_url_and_open_graph_text(self, client, home_page):
        page = StandardPage(
            title="About us",
            slug="about",
            seo_title="About our charity",
            search_description="Who we are and how we work.",
        )
        home_page.add_child(instance=page)

        html = client.get(page.url).content.decode()

        assert '<link rel="canonical" href="http://localhost/about/">' in html
        assert meta_content(html, "og:title") == "About our charity"
        assert meta_content(html, "og:description") == "Who we are and how we work."
        assert meta_content(html, "og:url") == "http://localhost/about/"

    def test_social_image_is_used_for_open_graph(self, client, home_page):
        home_page.social_image = ImageFactory()
        home_page.save_revision().publish()

        og_image = meta_content(client.get("/").content.decode(), "og:image")

        assert og_image.startswith("http://")
        assert "fill-1200x630" in og_image

    def test_campaign_hero_image_is_the_fallback_social_image(self, client, home_page):
        index = CampaignIndexPageFactory(parent=home_page)
        campaign = CampaignPageFactory(parent=index, hero_image=ImageFactory())

        assert campaign.get_social_image() == campaign.hero_image
        assert meta_content(client.get(campaign.url).content.decode(), "og:image")

    def test_editors_set_the_social_image_on_the_promote_tab(self, admin_client, home_page):
        promote_fields = [getattr(panel, "field_name", None) for panel in HomePage.promote_panels]
        edit_url = reverse("wagtailadmin_pages:edit", args=[home_page.pk])

        assert "social_image" in promote_fields
        assert 'name="social_image"' in admin_client.get(edit_url).content.decode()


class TestRedirects:
    def test_editor_created_redirect_is_permanent(self, client, home_page):
        page = StandardPage(title="Donate", slug="donate")
        home_page.add_child(instance=page)
        Redirect.objects.create(old_path="/give", redirect_page=page)

        response = client.get("/give")

        assert response.status_code == 301
        assert response["Location"] == page.url

    def test_renaming_a_page_redirects_its_old_url(
        self, client, home_page, django_capture_on_commit_callbacks
    ):
        page = StandardPage(title="Volunteer", slug="volunteer")
        home_page.add_child(instance=page)
        page.save_revision().publish()

        # Wagtail creates the redirect in an on_commit hook; tests never commit, so run it here.
        with django_capture_on_commit_callbacks(execute=True):
            page.slug = "get-involved"
            page.save_revision().publish()

        response = client.get("/volunteer/")
        assert response.status_code == 301
        assert response["Location"].endswith("/get-involved/")
