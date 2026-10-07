from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, BaseSiteSetting, register_setting
from wagtail.images.models import AbstractImage, AbstractRendition, Image
from wagtail.models import (
    DraftStateMixin,
    LockableMixin,
    Orderable,
    Page,
    PreviewableMixin,
    RevisionMixin,
)
from wagtail.search import index

from core.money import CURRENCY_CHOICES
from core.phone import phone_country_choices


class CustomImage(AbstractImage):
    """Wagtail image with the extra metadata a charity needs to publish photos responsibly."""

    credit = models.CharField(
        max_length=255,
        blank=True,
        help_text="Photographer or source, shown alongside the image.",
    )
    consent_confirmed = models.BooleanField(
        default=False,
        help_text="Tick once consent has been recorded for everyone identifiable in the photo.",
    )

    admin_form_fields = Image.admin_form_fields + ("credit", "consent_confirmed")


class SocialMetaMixin(models.Model):
    """Adds a social sharing image to a page's Promote tab."""

    social_image = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Shown when the page is shared on social media. Defaults to the main image.",
    )

    promote_panels = Page.promote_panels + [FieldPanel("social_image")]

    class Meta:
        abstract = True

    def get_social_image(self):
        return self.social_image or getattr(self, "hero_image", None)


class CustomRendition(AbstractRendition):
    image = models.ForeignKey(CustomImage, on_delete=models.CASCADE, related_name="renditions")

    class Meta:
        unique_together = (("image", "filter_spec", "focal_point_key"),)


@register_setting(icon="cog")
class SiteSettings(BaseSiteSetting):
    """Organisation details that appear site-wide, editable per Site."""

    charity_number = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    donate_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Linked from the Donate button in the site header.",
    )
    privacy_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="privacy notice",
        help_text=(
            "Says how supporters' details are used. Linked from the footer and next to every "
            "form's send button, once it's published."
        ),
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="NPR",
        help_text="Shown with every amount on the site, such as appeal targets and gifts.",
    )
    phone_country = models.CharField(
        max_length=2,
        choices=phone_country_choices,
        default="NP",
        help_text="The country selected by default for phone numbers on forms.",
    )
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("charity_number"),
                FieldPanel("contact_email"),
                FieldPanel("phone"),
                FieldPanel("address"),
                FieldPanel("currency"),
                FieldPanel("phone_country"),
            ],
            heading="Organisation",
        ),
        FieldPanel("donate_page"),
        FieldPanel("privacy_page"),
        MultiFieldPanel(
            [FieldPanel("facebook_url"), FieldPanel("instagram_url"), FieldPanel("linkedin_url")],
            heading="Social media",
        ),
    ]

    class Meta:
        verbose_name = "Site settings"

    @property
    def social_links(self):
        links = [
            ("Facebook", self.facebook_url),
            ("Instagram", self.instagram_url),
            ("LinkedIn", self.linkedin_url),
        ]
        return [(name, url) for name, url in links if url]


@register_setting(icon="warning")
class AnnouncementBanner(BaseGenericSetting):
    """A banner shown on every page, e.g. for an emergency appeal."""

    enabled = models.BooleanField(default=False)
    message = models.CharField(max_length=255, blank=True)
    link_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    panels = [FieldPanel("enabled"), FieldPanel("message"), FieldPanel("link_page")]

    class Meta:
        verbose_name = "Announcement banner"


class Partner(Orderable):
    """An organisation that funds or works with the charity."""

    name = models.CharField(max_length=255)
    url = models.URLField(blank=True)
    logo = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    panels = [FieldPanel("name"), FieldPanel("url"), FieldPanel("logo")]

    def __str__(self):
        return self.name


class Testimonial(
    PreviewableMixin,
    LockableMixin,
    DraftStateMixin,
    RevisionMixin,
    index.Indexed,
    models.Model,
):
    """A quote from a beneficiary, volunteer or supporter.

    Uses drafts and revisions because quotes from real people need sign-off before going live.
    """

    quote = models.TextField()
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True, help_text="e.g. Volunteer, Kisumu")
    photo = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    panels = [FieldPanel("quote"), FieldPanel("name"), FieldPanel("role"), FieldPanel("photo")]

    search_fields = [
        index.SearchField("quote"),
        index.SearchField("name"),
        index.AutocompleteField("name"),
    ]

    def __str__(self):
        return f"{self.name}: {self.quote[:40]}"

    def get_preview_template(self, request, mode_name):
        return "core/previews/testimonial.html"
