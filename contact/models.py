import logging

from django.db import models
from django.http import HttpResponseRedirect
from modelcluster.fields import ParentalKey
from wagtail.admin.mail import send_mail
from wagtail.admin.panels import (
    FieldPanel,
    FieldRowPanel,
    InlinePanel,
    MultiFieldPanel,
)
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.fields import RichTextField

from core.honeypot import HoneypotFormMixin
from core.publishing import FormPageForm, PublishGuardMixin

logger = logging.getLogger(__name__)


class FormField(AbstractFormField):
    page = ParentalKey("FormPage", on_delete=models.CASCADE, related_name="form_fields")


class EmailFormPage(HoneypotFormMixin, PublishGuardMixin, AbstractEmailForm):
    """What every form page does (#167): drop a filled hidden box, email the team with Reply-To
    set to the sender, keep the send when the mail server is down, go on to `?sent` after it,
    answer a send with mistakes with 422, and export what visitors typed as text. Abstract, so
    it has no table of its own.

    A type declares what the base can't: its field model, with a ParentalKey to it and
    related_name="form_fields", and its own form and landing templates, since what the page shows
    around the form is the type's."""

    collects_personal_details = True
    base_form_class = FormPageForm

    class Meta:
        abstract = True

    def serve(self, request, *args, **kwargs):
        if request.method in ("GET", "HEAD") and "sent" in request.GET:
            return self.render_landing_page(request, None, *args, **kwargs)
        response = super().serve(request, *args, **kwargs)
        # Not sent: the form again, with what is wrong with it (422), as on every form.
        if request.method == "POST" and response.status_code == 200:
            response.status_code = 422
        return response

    def render_landing_page(self, request, form_submission=None, *args, **kwargs):
        """After a send, go on to `?sent` (303, so the browser asks for it again with GET): a
        reload then can't send it twice. Opening `?sent`, or the admin's preview, only thanks.
        The address is the one the form was sent to, which works where get_url() gives None."""
        if request.method == "POST":
            return HttpResponseRedirect(f"{request.path}?sent", status=303)
        return super().render_landing_page(request, form_submission, *args, **kwargs)

    def get_submissions_list_view_class(self):
        from contact.views import FormSubmissionsListView  # admin views need the models loaded

        return FormSubmissionsListView

    def reply_to_address(self, form):
        """The sender's address for Reply-To, or None: the first email field they filled in."""
        email_fields = [
            field.clean_name for field in self.get_form_fields() if field.field_type == "email"
        ]
        filled = [form.cleaned_data[name] for name in email_fields if form.cleaned_data.get(name)]
        return filled[0] if filled else None

    def send_mail(self, form):
        """Email the team, with Reply-To set to the sender so staff can answer directly."""
        reply_to = self.reply_to_address(form)
        try:
            send_mail(
                self.subject,
                self.render_email(form),
                [address.strip() for address in self.to_address.split(",")],
                self.from_address,
                reply_to=[reply_to] if reply_to else None,
            )
        except OSError:
            # The submission is already saved and listed in the admin, so a mail outage
            # shouldn't show the sender an error page and make them submit again.
            logger.exception("Could not email the submission for form page %s", self.pk)


class FormPage(EmailFormPage):
    """A form editors build themselves, e.g. volunteer sign-up or general enquiries."""

    intro = RichTextField(blank=True)
    thank_you_text = RichTextField(blank=True)

    content_panels = AbstractEmailForm.content_panels + [
        FormSubmissionsPanel(),
        FieldPanel("intro"),
        InlinePanel("form_fields", label="Form fields"),
        FieldPanel("thank_you_text"),
        MultiFieldPanel(
            [
                FieldRowPanel([FieldPanel("from_address"), FieldPanel("to_address")]),
                FieldPanel("subject"),
            ],
            heading="Email notification",
        ),
    ]

    parent_page_types = ["home.HomePage", "home.StandardPage"]
    subpage_types = []
