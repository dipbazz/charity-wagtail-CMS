from django import forms
from django.db import models
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import (
    FieldPanel,
    InlinePanel,
    MultiFieldPanel,
    ObjectList,
    TabbedInterface,
)
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.images.models import AbstractImage, AbstractRendition, Image
from wagtail.models import (
    DraftStateMixin,
    LockableMixin,
    Orderable,
    Page,
    PreviewableMixin,
    RevisionMixin,
    TranslatableMixin,
)
from wagtail.search import index

from core.brand import (
    DEFAULT_ACCENT,
    DEFAULT_MAIN,
    ColourInput,
    Tone,
    custom_properties,
    validate_accent_colour,
    validate_main_colour,
)
from core.languages import main_language, reading_language
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


class TextInEachLanguage(models.Model):
    """One language's text for a setting, which Wagtail can't translate itself (#117).

    A setting has one row per language. Its text in the language being read comes from
    `TextInEachLanguageMixin.text_in_reading_language`.
    """

    locale = models.ForeignKey(
        "wagtailcore.Locale", on_delete=models.PROTECT, related_name="+", verbose_name="language"
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.locale.get_display_name()


class TextInEachLanguageMixin:
    """For a setting whose `texts` are `TextInEachLanguage` rows."""

    def text_in_reading_language(self, field):
        """`field` from the row in the language being read, else from the main language's row.

        A blank field counts as missing. One query for the rows, kept for the rest of the request
        (Wagtail keeps a setting per request).
        """
        if not hasattr(self, "_texts_by_language"):
            self._texts_by_language = {
                text.locale.language_code: text for text in self.texts.select_related("locale")
            }
        for language in (reading_language(), main_language()):
            value = getattr(self._texts_by_language.get(language), field, "")
            if value:
                return value
        return ""


@register_setting(icon="cog")
class SiteSettings(TextInEachLanguageMixin, ClusterableModel, BaseSiteSetting):
    """Organisation details that appear site-wide, editable per Site."""

    charity_number = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
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
    main_colour = models.CharField(
        max_length=7,
        default=DEFAULT_MAIN,
        validators=[validate_main_colour],
        help_text="Links and outlined buttons, and in a darker shade headings, the name bar at the "
        "top and the footer. White text goes on it, so it must be dark enough to read.",
    )
    accent_colour = models.CharField(
        max_length=7,
        default=DEFAULT_ACCENT,
        validators=[validate_accent_colour],
        help_text="The Donate button and other main buttons, progress bars and the announcement "
        "banner. The text on it is dark or white, whichever is easier to read.",
    )
    name_bar_style = models.CharField(
        "name bar",
        max_length=5,
        choices=Tone.choices,
        default=Tone.DARK,
        help_text="The row with your charity's name at the top of every page.",
    )
    footer_style = models.CharField(
        "footer",
        max_length=5,
        choices=Tone.choices,
        default=Tone.DARK,
        help_text="Your charity's details at the bottom of every page.",
    )

    organisation_panels = [
        MultiFieldPanel(
            [
                FieldPanel("charity_number"),
                FieldPanel("contact_email"),
                FieldPanel("phone"),
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
        InlinePanel(
            "texts",
            heading="Text in each language",
            label="Language",
            help_text="Shown to readers of that language; the main language's is used until "
            "another language has its own.",
        ),
    ]
    brand_panels = [
        MultiFieldPanel(
            [
                FieldPanel("main_colour", widget=ColourInput),
                FieldPanel("accent_colour", widget=ColourInput),
            ],
            heading="Colours",
            help_text="The site makes its other shades from these two. Every page uses them as "
            "soon as you save.",
        ),
        MultiFieldPanel(
            [
                FieldPanel("name_bar_style", widget=forms.RadioSelect),
                FieldPanel("footer_style", widget=forms.RadioSelect),
            ],
            heading="Header and footer",
            help_text="Choose light if your logo is drawn for a white background. Text stays "
            "easy to read either way.",
        ),
    ]
    edit_handler = TabbedInterface(
        [
            ObjectList(organisation_panels, heading="Organisation"),
            ObjectList(brand_panels, heading="Brand"),
        ]
    )

    class Meta:
        verbose_name = "Site settings"

    @property
    def brand_css(self):
        """CSS custom properties for the chosen brand colours, or "" for the stylesheet's own."""
        return custom_properties(self.main_colour, self.accent_colour)

    @property
    def address(self):
        return self.text_in_reading_language("address")

    @property
    def social_links(self):
        links = [
            ("Facebook", self.facebook_url),
            ("Instagram", self.instagram_url),
            ("LinkedIn", self.linkedin_url),
        ]
        return [(name, url) for name, url in links if url]


class SiteSettingsText(TextInEachLanguage):
    settings = ParentalKey(SiteSettings, on_delete=models.CASCADE, related_name="texts")
    address = models.TextField(blank=True, help_text="Shown in the footer of every page.")

    panels = [FieldPanel("locale"), FieldPanel("address")]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["settings", "locale"], name="one_site_settings_text_per_language"
            )
        ]


@register_setting(icon="warning")
class AnnouncementBanner(TextInEachLanguageMixin, ClusterableModel, BaseSiteSetting):
    """A banner shown on every page, e.g. for an emergency appeal."""

    enabled = models.BooleanField(default=False)
    link_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Readers of another language go to its translation, once it's published.",
    )

    panels = [
        FieldPanel("enabled"),
        FieldPanel("link_page"),
        InlinePanel(
            "texts",
            heading="Message in each language",
            label="Language",
            help_text="Readers of a language with no message of its own see the main language's.",
        ),
    ]

    class Meta:
        verbose_name = "Announcement banner"

    @property
    def message(self):
        return self.text_in_reading_language("message")


class AnnouncementBannerText(TextInEachLanguage):
    banner = ParentalKey(AnnouncementBanner, on_delete=models.CASCADE, related_name="texts")
    message = models.CharField(max_length=255)

    panels = [FieldPanel("locale"), FieldPanel("message")]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["banner", "locale"], name="one_banner_text_per_language"
            )
        ]


class Partner(TranslatableMixin, Orderable):
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

    class Meta(TranslatableMixin.Meta):
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class Testimonial(
    TranslatableMixin,
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
        # The admin's language filter narrows the listing before searching it.
        index.FilterField("locale"),
    ]

    class Meta(TranslatableMixin.Meta):
        pass

    def __str__(self):
        return f"{self.name}: {self.quote[:40]}"

    def copy_for_translation(self, locale, exclude_fields=None):
        """A translation starts as an unpublished draft, as a translated page does.

        Wagtail copies the latest revision with its live status, so a translation of a published
        testimonial would go live at once, with any changes still waiting for a moderator.
        """
        translation = super().copy_for_translation(locale, exclude_fields)
        translation.live = False
        translation.has_unpublished_changes = True
        translation.live_revision = None
        translation.first_published_at = translation.last_published_at = None
        translation.locked = False
        translation.locked_at = translation.locked_by = None
        return translation

    def get_preview_template(self, request, mode_name):
        return "core/previews/testimonial.html"
