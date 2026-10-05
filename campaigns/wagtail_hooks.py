import datetime

from django.db.models import Sum
from wagtail import hooks
from wagtail.admin.ui.components import Component

from campaigns.models import CampaignPage
from campaigns.views import PledgeViewSet

CLOSING_SOON_DAYS = 14


class FundraisingPanel(Component):
    """Dashboard summary of open appeals, so fundraisers see progress as soon as they log in."""

    name = "fundraising"
    template_name = "campaigns/admin/fundraising_panel.html"
    order = 50

    def get_context_data(self, parent_context):
        context = super().get_context_data(parent_context)
        today = datetime.date.today()
        open_appeals = CampaignPage.objects.live().active()
        totals = open_appeals.aggregate(raised=Sum("amount_raised"), target=Sum("target_amount"))
        context.update(
            {
                # The money tag reads the currency from the request's Site settings.
                "request": parent_context["request"],
                "open_count": open_appeals.count(),
                "total_raised": totals["raised"] or 0,
                "total_target": totals["target"] or 0,
                "closing_soon": open_appeals.filter(
                    end_date__lte=today + datetime.timedelta(days=CLOSING_SOON_DAYS)
                ).order_by("end_date"),
            }
        )
        return context


@hooks.register("construct_homepage_panels")
def add_fundraising_panel(request, panels):
    panels.append(FundraisingPanel())


@hooks.register("register_admin_viewset")
def register_pledge_viewset():
    return PledgeViewSet()
