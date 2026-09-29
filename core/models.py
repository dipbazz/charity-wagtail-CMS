from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, BaseSiteSetting, register_setting
from wagtail.images.models import AbstractImage, AbstractRendition, Image


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
            ],
            heading="Organisation",
        ),
        FieldPanel("donate_page"),
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
