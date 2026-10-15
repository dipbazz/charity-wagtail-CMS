import re

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from wagtail.admin.ui.tables import Column
from wagtail.admin.views.generic import DeleteView, EditView, IndexView, InspectView
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.snippets.views.snippets import SnippetViewSet

from campaigns.forms import MarkPaidForm
from campaigns.models import Payment, Pledge, QRCode
from core.exports import VisitorTextExportMixin


class PledgeIndexView(VisitorTextExportMixin, IndexView):
    def get_base_queryset(self):
        # The export's "Paid with" reads each pledge's payments: fetched together, not one by one.
        return super().get_base_queryset().prefetch_related("payments")

    def search_queryset(self, queryset):
        """Names and emails as typed, and a pledge number with or without its space ("482 913"
        as it's shown and read out, "482913" as it's written in a payment's remarks)."""
        found = super().search_queryset(queryset)
        if self.is_searching:
            digits = re.sub(r"\s", "", self.search_query)
            if re.fullmatch(r"\d{6}", digits):
                found = found | queryset.filter(number=digits)
        return found


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


CONFIRM_PERMISSION = "campaigns.confirm_payment"


class PledgeInspectView(InspectView):
    """The pledge, then its payments with what happened to each. A payment the team confirms (a
    QR payment) is marked paid or not found here, by people who may confirm payments."""

    template_name = "campaigns/admin/pledge_inspect.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payments"] = self.object.payments.prefetch_related("steps__by")
        context["can_confirm"] = self.request.user.has_perm(CONFIRM_PERMISSION)
        context["today"] = timezone.localdate()
        return context


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
    inspect_view_class = PledgeInspectView

    def get_urlpatterns(self):
        return [
            *super().get_urlpatterns(),
            path(
                "<int:pk>/payments/<int:payment_pk>/mark-paid/",
                self.mark_paid_view,
                name="mark_paid",
            ),
            path(
                "<int:pk>/payments/<int:payment_pk>/not-found/",
                self.not_found_view,
                name="not_found",
            ),
        ]

    @staticmethod
    def confirmable_payment(request, pk, payment_pk):
        """The payment, if this person may confirm payments (a 403 otherwise). Only payments the
        team confirms are ever changed here: a provider's are never marked by hand."""
        if not request.user.has_perm(CONFIRM_PERMISSION):
            raise PermissionDenied
        return get_object_or_404(
            Payment.objects.select_related("pledge"), pk=payment_pk, pledge_id=pk
        )

    @method_decorator(require_POST)
    def mark_paid_view(self, request, pk, payment_pk):
        payment = self.confirmable_payment(request, pk, payment_pk)
        form = MarkPaidForm(request.POST)
        if not form.is_valid():
            problems = "; ".join(f"{name}: {', '.join(e)}" for name, e in form.errors.items())
            messages.error(request, f"Not marked paid. {problems}")
        elif payment.mark_paid(
            request.user,
            form.cleaned_data["received_on"],
            form.cleaned_data["amount"],
            form.cleaned_data["reference"],
        ):
            messages.success(request, "Marked paid.")
        else:
            messages.error(request, "This payment can't be marked paid: it may already be paid.")
        return redirect(reverse("pledges:inspect", args=[pk]))

    @method_decorator(require_POST)
    def not_found_view(self, request, pk, payment_pk):
        payment = self.confirmable_payment(request, pk, payment_pk)
        if payment.mark_not_found(request.user):
            messages.success(request, "Marked not found.")
        else:
            messages.error(request, "This payment can't be marked not found.")
        return redirect(reverse("pledges:inspect", args=[pk]))

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
        "display_number",
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
    search_fields = ["name", "email", "number"]
    search_backend_name = None  # plain database search; pledges aren't in the site search index

    list_export = [
        "created_at",
        "number",
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
        "number": "Pledge number",
        "get_frequency_display": "How often",
        "email_updates": "Email updates",
        "show_on_website": "Show on website",
        "get_payment_status_display": "Payment",
        "paid_at": "Paid",
        "paid_with": "Paid with",
    }
    export_filename = "pledges"


class QRCodeViewSet(SnippetViewSet):
    """The charity's QR codes, listed like any other records: an Add button when there are none,
    and each row opens its edit page. Only moderators have the permissions (see
    0014_qr_payments), so an editor never sees them. Wagtail's history for each
    code says who added, changed or removed it, and when. Drag a row to put a code first."""

    model = QRCode
    icon = "image"
    menu_label = "QR codes"
    add_to_admin_menu = True
    menu_order = 260
    list_display = ["name", "account_name", "account_number"]
