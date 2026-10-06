from wagtail.admin.ui.tables import Column
from wagtail.admin.viewsets.model import ModelViewSet

from campaigns.models import Pledge


class PledgeViewSet(ModelViewSet):
    """Pledges from the Donate page: listed, filtered, read and exported.

    Pledges come from the site, so the team never adds or edits them, and only a superuser can
    delete one (0006_pledge_permissions gives the groups view permission only): a deleted
    pledge loses the record of a donation.
    """

    model = Pledge
    name = "pledges"
    icon = "doc-full"
    add_to_admin_menu = True
    menu_order = 250
    inspect_view_enabled = True
    copy_view_enabled = False

    # Wagtail needs these for its add and edit views, which only a superuser can open.
    form_fields = [
        "appeal",
        "amount",
        "currency",
        "frequency",
        "name",
        "email",
        "phone",
        "address",
        "postcode",
        "message",
        "email_updates",
        "show_on_website",
    ]

    list_display = [
        "created_at",
        "name",
        "display_amount",
        Column("frequency", label="How often", accessor="get_frequency_display"),
        "appeal",
    ]
    list_filter = ["frequency", "appeal", "email_updates", "show_on_website", "created_at"]
    search_fields = ["name", "email"]
    search_backend_name = None  # plain database search; pledges aren't in the site search index

    list_export = [
        "created_at",
        "amount",
        "currency",
        "get_frequency_display",
        "name",
        "email",
        "phone",
        "appeal",
        "address",
        "postcode",
        "message",
        "email_updates",
        "show_on_website",
    ]
    export_headings = {
        "created_at": "Sent",
        "get_frequency_display": "How often",
        "email_updates": "Email updates",
        "show_on_website": "Show on website",
    }
    export_filename = "pledges"
