from django.db import models
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


class FormField(AbstractFormField):
    page = ParentalKey("FormPage", on_delete=models.CASCADE, related_name="form_fields")


class FormPage(AbstractEmailForm):
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

    def send_mail(self, form):
        """Email the team, with Reply-To set to the sender so staff can answer directly."""
        email_fields = [
            field.clean_name for field in self.get_form_fields() if field.field_type == "email"
        ]
        reply_to = [form.cleaned_data[name] for name in email_fields if form.cleaned_data.get(name)]
        send_mail(
            self.subject,
            self.render_email(form),
            [address.strip() for address in self.to_address.split(",")],
            self.from_address,
            reply_to=reply_to[:1] or None,
        )
