import datetime
from decimal import Decimal

import pytest
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
