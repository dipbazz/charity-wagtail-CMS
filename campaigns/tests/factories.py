import datetime
from decimal import Decimal

import factory
from wagtail_factories import PageFactory

from campaigns.models import CampaignIndexPage, CampaignPage, DonatePage


class CampaignIndexPageFactory(PageFactory):
    title = "Campaigns"
    slug = "campaigns"

    class Meta:
        model = CampaignIndexPage


class CampaignPageFactory(PageFactory):
    title = factory.Sequence(lambda n: f"Campaign {n}")
    summary = "Help us bring clean water to rural communities."
    target_amount = Decimal("10000")
    amount_raised = Decimal("2500")
    start_date = factory.LazyFunction(lambda: datetime.date.today() - datetime.timedelta(days=30))
    end_date = None

    class Meta:
        model = CampaignPage


class DonatePageFactory(PageFactory):
    title = "Donate"
    slug = "donate"
    introduction = "Every gift helps a community get safe water that lasts."
    payment_notice = "<p>No payment is taken online yet. We'll be in touch about how to pay.</p>"
    thank_you_text = "<p>Thank you for your pledge.</p>"

    class Meta:
        model = DonatePage
