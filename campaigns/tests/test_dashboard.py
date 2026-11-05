import datetime
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from campaigns.tests.factories import CampaignIndexPageFactory, CampaignPageFactory

TODAY = datetime.date.today()


@pytest.mark.django_db
class TestFundraisingDashboardPanel:
    @pytest.fixture
    def campaigns(self, home_page):
        index = CampaignIndexPageFactory(parent=home_page)
        CampaignPageFactory(
            parent=index,
            title="Flood relief",
            amount_raised=Decimal("10000"),
            end_date=TODAY + datetime.timedelta(days=5),
        )
        CampaignPageFactory(parent=index, title="Clean water", amount_raised=Decimal("2500"))
        CampaignPageFactory(
            parent=index,
            title="Old appeal",
            amount_raised=Decimal("999"),
            start_date=TODAY - datetime.timedelta(days=60),
            end_date=TODAY - datetime.timedelta(days=1),
        )
        CampaignPageFactory(parent=index, title="Draft", amount_raised=Decimal("50"), live=False)

    def test_summarises_open_appeals_on_the_dashboard(self, admin_client, campaigns):
        html = admin_client.get(reverse("wagtailadmin_home")).content.decode()

        assert "Fundraising overview" in html
        assert "Rs 12,500" in html
        assert "2 open appeals" in html

    def test_lists_appeals_closing_within_two_weeks(self, admin_client, campaigns):
        response = admin_client.get(reverse("wagtailadmin_home"))

        html = response.content.decode()
        assert "Closing soon" in html
        assert "Flood relief" in html


def translated(page, locale, **fields):
    """`page`'s published translation into `locale`, with `fields` changed."""
    translation = page.copy_for_translation(locale)
    for name, value in fields.items():
        setattr(translation, name, value)
    translation.save_revision().publish()
    return translation


def closing_soon(html):
    heading = BeautifulSoup(html, "html.parser").find("h3", string="Closing soon")
    return [item.a.get_text(strip=True) for item in heading.find_next("ul").find_all("li")]


@pytest.mark.django_db
class TestTranslatedAppealsCountOnce:
    """An appeal published in both languages is one appeal (#195)."""

    @pytest.fixture
    def appeals(self, home_page, nepali_home_page):
        index = CampaignIndexPageFactory(parent=home_page)
        flood_relief = CampaignPageFactory(
            parent=index,
            title="Flood relief",
            amount_raised=Decimal("10000"),
            end_date=TODAY + datetime.timedelta(days=5),
        )
        CampaignPageFactory(parent=index, title="Clean water", amount_raised=Decimal("2500"))
        nepali_index = translated(index, nepali_home_page.locale)
        translated(flood_relief, nepali_index.locale, title="बाढी राहत")
        return nepali_index

    def test_an_appeal_in_both_languages_counts_once(self, admin_client, appeals):
        html = admin_client.get(reverse("wagtailadmin_home")).content.decode()

        assert "Rs 12,500</strong> raised of Rs 20,000" in html
        assert "2 open appeals" in html

    def test_an_appeal_in_both_languages_closes_soon_once(self, admin_client, appeals):
        html = admin_client.get(reverse("wagtailadmin_home")).content.decode()

        assert closing_soon(html) == ["Flood relief"]

    def test_an_appeal_only_in_the_other_language_still_counts(self, admin_client, appeals):
        CampaignPageFactory(
            parent=appeals,
            title="भूकम्प राहत",
            slug="earthquake-relief",
            amount_raised=Decimal("500"),
            end_date=TODAY + datetime.timedelta(days=3),
        )

        html = admin_client.get(reverse("wagtailadmin_home")).content.decode()

        assert "Rs 13,000</strong> raised of Rs 30,000" in html
        assert "3 open appeals" in html
        assert closing_soon(html) == ["भूकम्प राहत", "Flood relief"]

    def test_the_main_language_is_counted_when_it_is_nepali(self, admin_client, appeals, settings):
        settings.LANGUAGE_CODE = "ne"

        html = admin_client.get(reverse("wagtailadmin_home")).content.decode()

        assert "2 open appeals" in html
        assert closing_soon(html) == ["बाढी राहत"]
