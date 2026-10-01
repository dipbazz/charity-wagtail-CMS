from django import template
from django.forms.utils import flatatt
from django.utils.safestring import mark_safe
from wagtail.images.models import Filter, Picture
from wagtail.images.shortcuts import get_renditions_or_not_found

register = template.Library()

# On phones the banner is about as tall as it is wide, so a square crop fills it without being
# stretched; wider screens get the wide crop. Wagtail's {% picture %} can't switch crops by
# screen width, so this tag builds the <picture> itself.
# The phone crops sit under a 75% dark overlay, which hides the detail a higher quality keeps, so
# they're compressed harder: the 800px AVIF drops from 110 KB to 50 KB with no visible change.
HERO_PHONE_FILTERS = [
    *Filter.expand_spec("fill-{480x480,800x800}|format-avif|avifquality-40"),
    *Filter.expand_spec("fill-{480x480,800x800}|format-webp|webpquality-50"),
    *Filter.expand_spec("fill-{480x480,800x800}|format-jpeg|jpegquality-50"),
]
HERO_WIDE_FILTERS = Filter.expand_spec("fill-{1200x525,1600x700}|format-{avif,webp,jpeg}")
HERO_PHONE_MEDIA = "(max-width: 39.99rem)"
MIME_TYPES = {fmt.name: fmt.mime_type for fmt in Picture.source_format_order}


def source(renditions, fmt, **attrs):
    largest = renditions[-1]
    attrs |= {
        "type": MIME_TYPES[fmt],
        "srcset": Picture.get_width_srcset(renditions),
        "sizes": "100vw",
        "width": largest.width,
        "height": largest.height,
    }
    return f"<source{flatatt(attrs)}>"


@register.simple_tag
def hero_picture(image, **attrs):
    """A full-width banner in AVIF, WebP and JPEG; keyword arguments become <img> attributes."""
    if not image:
        return ""
    renditions = get_renditions_or_not_found(image, HERO_PHONE_FILTERS + HERO_WIDE_FILTERS)
    phone = Picture({spec: renditions[spec] for spec in HERO_PHONE_FILTERS}).formats
    wide = Picture({spec: renditions[spec] for spec in HERO_WIDE_FILTERS}).formats

    sources = [source(phone[fmt], fmt, media=HERO_PHONE_MEDIA) for fmt in ("avif", "webp", "jpeg")]
    sources += [source(wide[fmt], fmt) for fmt in ("avif", "webp")]
    fallback = wide["jpeg"]
    img = fallback[-1].img_tag(
        {"srcset": Picture.get_width_srcset(fallback), "sizes": "100vw", **attrs}
    )
    return mark_safe(f"<picture>{''.join(sources)}{img}</picture>")  # noqa: S308 - attributes are escaped by flatatt
