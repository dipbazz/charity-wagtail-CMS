import datetime
import re
import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.decorators import method_decorator
from django.utils.formats import date_format
from django.views.decorators.http import require_POST
from wagtail.admin.ui.tables import Column
from wagtail.admin.views.generic import DeleteView, EditView, IndexView, InspectView
from wagtail.admin.views.generic.history import HistoryView
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.log_actions import log
from wagtail.snippets.views.snippets import IndexView as SnippetIndexView
from wagtail.snippets.views.snippets import SnippetViewSet

from campaigns import sharing
from campaigns.forms import MAX_AMOUNT, MarkPaidForm
from campaigns.models import ASK_AGAIN_AFTER, Payment, PaymentStatus, Pledge, QRCode
from core.exports import VisitorTextExportMixin
from core.images import UPLOAD_CONTENT_TYPES


class PledgeIndexView(VisitorTextExportMixin, IndexView):
    def get_base_queryset(self):
        # The export's "Paid with" reads each pledge's payments: fetched together, not one by one.
        return super().get_base_queryset().prefetch_related("payments")

    def search_queryset(self, queryset):
        """Names, emails and phone numbers as typed, a pledge number with or without its space
        ("482 913" as it's shown and read out, "482913" as it's written in a payment's remarks),
        and anything on a line of a provider's or bank's statement: a payment's reference (with
        or without its hyphens), the provider's ID, or a transaction ID."""
        found = super().search_queryset(queryset)
        if not self.is_searching:
            return found
        typed = self.search_query.strip()
        digits = re.sub(r"\s", "", typed)
        if re.fullmatch(r"\d{6}", digits):
            found = found | queryset.filter(number=digits)
        payments = (
            Q(provider_id=typed)
            | Q(provider_reference__iexact=typed)
            | Q(supporters_reference__iexact=typed)
        )
        if re.fullmatch(r"[0-9a-fA-F]{32}", typed.replace("-", "")):
            payments |= Q(reference=uuid.UUID(typed.replace("-", "")))
        paid = Payment.objects.filter(payments).values("pledge_id")
        return found | queryset.filter(pk__in=paid)


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
STOP_SHOWING_PERMISSION = "campaigns.stop_showing_gift"


def when(moment):
    """A time as the pledge's page shows it, in the site's time zone: "14 Oct 2026, 3:38 p.m."."""
    return date_format(timezone.localtime(moment), "j M Y, g:i a")


def time_zone_name():
    """The site's time zone, named once on the pledge's page: "Asia/Kathmandu time (UTC+5:45)"."""
    offset = timezone.localtime().utcoffset()
    sign = "-" if offset < datetime.timedelta(0) else "+"
    hours, seconds = divmod(abs(int(offset.total_seconds())), 3600)
    return f"{timezone.get_current_timezone_name()} time (UTC{sign}{hours}:{seconds // 60:02d})"


def paid_how(payment):
    """The provider or QR code a payment was made with."""
    return payment.qr_name or payment.get_method_display()


def payment_reason(pledge, payments):
    """The sentence after the pledge's payment status (Pledge.payment_display()) at the top of
    its page: how it was paid, or why it isn't. `payments` are its payments, newest first."""
    if reason := pledge.needs_checking():
        return reason
    if paid := pledge.paid_payment():
        made = f"with {paid_how(paid)} on {when(pledge.paid_at or paid.updated_at)}"
        if paid.provider_reference:
            made += f", transaction {paid.provider_reference}"
        if not paid.live:
            made += f". Made in {paid.get_method_display()}'s test system: no money moved."
        return made
    if claimed := next((p for p in payments if p.status == PaymentStatus.TO_CONFIRM), None):
        sent = f"The supporter says they paid by {paid_how(claimed)}"
        if claimed.supporters_reference:
            sent += f", transaction {claimed.supporters_reference}"
        if claimed.receipt:
            sent += ", and sent a screenshot of the receipt"
        return f"{sent}. Find it in your statement, then mark it paid or not found."
    if not payments:
        return "Not paid online yet."
    latest = payments[0]
    if latest.status == PaymentStatus.WAITING:
        return f"Started with {paid_how(latest)} on {when(latest.created_at)}, not confirmed yet."
    if latest.team_confirms:
        return f"Your team couldn't find the payment by {paid_how(latest)} in its statement."
    if not latest.reached_provider():
        return f"The payment couldn't start at {paid_how(latest)}, so no money was taken."
    return latest.word_sentence() or f"{paid_how(latest)} didn't confirm the payment."


class PledgeInspectView(InspectView):
    """The pledge as the team acts on it: who, how much and whether it's paid; the contact
    details; the message and consents; then its payments with what happened to each. A payment
    the team confirms (a QR payment) is marked paid or not found here, by people who may confirm
    payments; one a provider answers for can be checked with the provider."""

    template_name = "campaigns/admin/pledge_inspect.html"

    def get_page_subtitle(self):
        return self.object.name  # the amount and how often lead the page

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetched once and shared, so the answer, the payments and their steps make no more
        # queries however many there are.
        pledge = (
            Pledge.objects.select_related("page")
            .prefetch_related(Prefetch("payments", Payment.objects.prefetch_related("steps__by")))
            .get(pk=self.object.pk)
        )
        payments = list(pledge.payments.all())
        paid = pledge.paid_payment()
        word = pledge.payment_display()
        shown = pledge.page and sharing.gift_view(pledge) != sharing.HIDDEN
        context.update(
            # Their page for friends (#100), while it's up, for the team to see what it shows.
            gift_url=sharing.gift_url(pledge, self.request) if shown else "",
            can_stop_showing=self.request.user.has_perm(STOP_SHOWING_PERMISSION),
            pledge=pledge,
            payments=payments,
            # The paid one is open, or else the latest; every other one is folded.
            open_payment=paid or (payments[0] if payments else None),
            payment_word=word,
            # Filled in for paid, so it stands out from the states that need something done.
            payment_word_class="w-status--primary" if word.startswith("Paid") else "",
            payment_reason=payment_reason(pledge, payments),
            time_zone=time_zone_name(),
            can_confirm=self.request.user.has_perm(CONFIRM_PERMISSION),
            today=timezone.localdate(),
            max_amount=MAX_AMOUNT,
        )
        return context


class PledgeHistoryView(HistoryView):
    """A pledge's history, for anyone who can read pledges, not only those who can change them:
    the team acts on pledges (Stop showing on the website, #100) without editing them."""

    any_permission_required = ["view", "add", "change", "delete"]


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
    history_view_class = PledgeHistoryView

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
            path(
                "<int:pk>/payments/<int:payment_pk>/receipt/",
                self.receipt_view,
                name="receipt",
            ),
            path(
                "<int:pk>/payments/<int:payment_pk>/check/",
                self.check_view,
                name="check",
            ),
            path("<int:pk>/stop-showing/", self.stop_showing_view, name="stop_showing"),
            path("<int:pk>/show-again/", self.show_again_view, name="show_again"),
        ]

    @staticmethod
    def gift_to_show_or_not(request, pk):
        """The pledge, if this person may take its gift's page down or put it back (a 403
        otherwise): editors and moderators."""
        if not request.user.has_perm(STOP_SHOWING_PERMISSION):
            raise PermissionDenied
        return get_object_or_404(Pledge, pk=pk)

    def stop_showing_view(self, request, pk):
        """Stop showing on the website (#100): takes the gift's page for friends down at once,
        say for a made-up name, after asking first. It sticks: the supporter's box is replaced by
        a note to call, and only Show again puts it back. Logged in the pledge's history."""
        pledge = self.gift_to_show_or_not(request, pk)
        if request.method == "POST":
            # Logged only if it changed: sent twice, or from a tab left open, it's one entry.
            if Pledge.objects.filter(pk=pk, hidden_by_team=False).update(hidden_by_team=True):
                log(instance=pledge, action="campaigns.stop_showing", user=request.user)
            messages.success(request, f"{pledge.name}'s gift isn't shown on the website now.")
            return redirect("pledges:inspect", pk)
        return TemplateResponse(
            request,
            "campaigns/admin/stop_showing.html",
            {
                "pledge": pledge,
                "page_title": "Stop showing on the website",
                "page_subtitle": pledge.name,
                "header_icon": "doc-full",
            },
        )

    @method_decorator(require_POST)
    def show_again_view(self, request, pk):
        """Show again: undoes Stop showing on the website. The page is up again if the supporter
        still agrees to it. Logged in the pledge's history."""
        pledge = self.gift_to_show_or_not(request, pk)
        if Pledge.objects.filter(pk=pk, hidden_by_team=True).update(hidden_by_team=False):
            log(instance=pledge, action="campaigns.show_again", user=request.user)
        messages.success(request, f"{pledge.name}'s gift can be shown on the website again.")
        return redirect("pledges:inspect", pk)

    @method_decorator(require_POST)
    def check_view(self, request, pk, payment_pk):
        """Check with <provider> now: asks the provider about the payment as the pay page does,
        for anyone who can read pledges, and adds the answer to its steps with their name. Not
        again within ASK_AGAIN_AFTER: each ask can wait for the provider."""
        if not request.user.has_perm("campaigns.view_pledge"):
            raise PermissionDenied
        payment = get_object_or_404(Payment, pk=payment_pk, pledge_id=pk)
        name = payment.get_method_display()
        if not payment.can_be_checked():
            messages.error(request, f"This payment can't be checked with {name}.")
        elif payment.asked_recently():
            messages.warning(
                request,
                f"{name} was asked less than {ASK_AGAIN_AFTER.seconds} seconds ago. Wait a "
                "moment, then check again.",
            )
        elif outcome := payment.ask(by=request.user):
            said = payment.word_sentence()
            messages.success(request, said or f"{name} says it's {outcome.status}.")
        else:
            messages.error(
                request,
                f"{payment.steps.last().sentence()} Try again in a few minutes.",
            )
        return redirect(reverse("pledges:inspect", args=[pk]))

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
        form = MarkPaidForm(request.POST, pledge=payment.pledge)
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

    def receipt_view(self, request, pk, payment_pk):
        """The supporter's screenshot of their receipt, for people who may confirm payments
        only: nothing else serves it. Never cached, so it's gone from the browser too once it's
        deleted."""
        payment = self.confirmable_payment(request, pk, payment_pk)
        if not payment.receipt:
            raise Http404
        try:
            file = payment.receipt.open("rb")
        except FileNotFoundError as missing:
            raise Http404 from missing
        extension = payment.receipt.name.rpartition(".")[2]
        response = FileResponse(file, content_type=UPLOAD_CONTENT_TYPES[extension])
        add_never_cache_headers(response)
        return response

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
    search_fields = ["name", "email", "phone", "number"]
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
        "payment_display",
        "paid_at",
        "paid_with",
    ]
    export_headings = {
        "created_at": "Sent",
        "number": "Pledge number",
        "get_frequency_display": "How often",
        "email_updates": "Email updates",
        "show_on_website": "Show on website",
        "payment_display": "Payment",
        "paid_at": "Paid",
        "paid_with": "Paid with",
    }
    export_filename = "pledges"


class QRCodeIndexView(SnippetIndexView):
    def get_table(self, object_list):
        # Each row's name: all of them in one query, not one per code.
        return super().get_table(QRCode.with_names(object_list))


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
    index_view_class = QRCodeIndexView
    list_display = ["name", "account_name", "account_number"]
