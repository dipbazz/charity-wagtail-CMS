from django.db.models import Prefetch
from wagtail.images import get_image_model
from wagtail.images.models import Filter

# Must match the {% picture %} filters in the campaign and news card templates, or each card
# falls back to a query of its own.
CARD_IMAGE_FILTERS = Filter.expand_spec("fill-{640x360,320x180}|format-{avif,webp,jpeg}")


def with_card_images(pages):
    """Fetch the card image renditions for a listing of pages in one query, not one per card."""
    renditions = (
        get_image_model().get_rendition_model().objects.filter(filter_spec__in=CARD_IMAGE_FILTERS)
    )
    return pages.select_related("hero_image").prefetch_related(
        Prefetch("hero_image__renditions", queryset=renditions, to_attr="prefetched_renditions")
    )
