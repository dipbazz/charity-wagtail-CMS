"""Fixtures shared by the Donate page's tests and its browser tests."""

import datetime

import pytest
from wagtail.models import PageViewRestriction

from campaigns.tests.factories import (
    CampaignIndexPageFactory,
    CampaignPageFactory,
    DonatePageFactory,
)

TODAY = datetime.date.today()


@pytest.fixture
def appeals(home_page):
    index = CampaignIndexPageFactory(parent=home_page, title="Appeals", slug="appeals")
    CampaignPageFactory(parent=index, title="Flood relief", slug="flood-relief")
    CampaignPageFactory(
        parent=index,
        title="Last year's appeal",
        slug="last-year",
        start_date=TODAY - datetime.timedelta(days=400),
        end_date=TODAY - datetime.timedelta(days=30),
    )
    private = CampaignPageFactory(parent=index, title="Trustees' appeal", slug="trustees")
    PageViewRestriction.objects.create(
        page=private, restriction_type=PageViewRestriction.PASSWORD, password="trustees"
    )
    return index


@pytest.fixture
def donate_page(home_page, appeals):
    page = DonatePageFactory(
        parent=home_page,
        body=[("paragraph", "<p>Where every Rs 100 goes</p>")],
    )
    page.donation_amounts.create(amount=2500, impact="A hygiene kit for a family")
    page.donation_amounts.create(amount=10000, impact="Water purification for a month")
    page.save_revision().publish()
    return page
