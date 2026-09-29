from django.db import models
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
