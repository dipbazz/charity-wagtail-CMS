from django.contrib import messages
from django.shortcuts import redirect
from wagtail.admin.ui.tables import Column
from wagtail.admin.views.generic import DeleteView, EditView, IndexView
from wagtail.admin.viewsets.model import ModelViewSet

from campaigns.models import Pledge
from core.exports import VisitorTextExportMixin


class PledgeIndexView(VisitorTextExportMixin, IndexView):
    def get_base_queryset(self):
        # The export's "Paid with" reads each pledge's payments: fetched together, not one by one.
        return super().get_base_queryset().prefetch_related("payments")


class PledgeEditView(EditView):
    """Keeps the amount and currency once someone has started paying the pledge: the payment was
    for them, so a changed one still marked paid would disagree with the provider's statement.
    The rest (a mistyped email, say) can still be put right. A disabled field ignores what's
    posted for it."""

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.object.payments.exists():
            for name in ("amount", "currency"):
                field = form.fields[name]
                field.disabled = True
                field.help_text = "Can't be changed: someone has started paying this pledge."
        return form


class PledgeDeleteView(DeleteView):
    """Refuses a pledge paid with real money: its payment is the site's only record of the gift
    (provider, transaction ID and time). Unpaid pledges and ones paid in a provider's test system
    can still be deleted, to clear out testing. Wagtail checks permission before get() and post().
    """

    def get(self, request, *args, **kwargs):
        return self.refuse() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.refuse() or super().post(request, *args, **kwargs)

    def refuse(self):
        if not self.object.received_money():
            return None
        messages.error(
            self.request,
            "This pledge was paid with real money, so it can't be deleted: its payment is the "
            "site's only record of the gift.",
        )
        return redirect("pledges:inspect", self.object.pk)


class PledgeViewSet(ModelViewSet):
    """Pledges from the Donate page: listed, filtered, read and exported.

    Pledges come from the site, so the team never adds or edits them, and only a superuser can
    delete one (0006_pledge_permissions gives the groups view permission only): a deleted
    pledge loses the record of a donation. Not even a superuser can delete one paid with real
    money (PledgeDeleteView), or change the amount of one someone has started paying
    (PledgeEditView).
    """

    model = Pledge
    name = "pledges"
    icon = "doc-full"
    add_to_admin_menu = True
    menu_order = 250
    inspect_view_enabled = True
    copy_view_enabled = False
    index_view_class = PledgeIndexView
    edit_view_class = PledgeEditView
    delete_view_class = PledgeDeleteView

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
        Column("payment_status", label="Payment", accessor="payment_display"),
    ]
    list_filter = [
        "frequency",
        "appeal",
        "payment_status",
        "email_updates",
        "show_on_website",
        "created_at",
    ]
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
        "get_payment_status_display",
        "paid_at",
        "paid_with",
    ]
    export_headings = {
        "created_at": "Sent",
        "get_frequency_display": "How often",
        "email_updates": "Email updates",
        "show_on_website": "Show on website",
        "get_payment_status_display": "Payment",
        "paid_at": "Paid",
        "paid_with": "Paid with",
    }
    export_filename = "pledges"
