import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import Prefetch
from django.utils.translation import gettext_lazy
from PIL import Image, ImageOps
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


# What a visitor or a moderator may upload straight to the server, outside the image library: the
# formats browsers and phones all make, and nothing a viewer would have to run (SVG).
UPLOAD_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
# The file names those come with: a JPEG is as often called .jpeg as .jpg.
UPLOAD_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# A small file can still decode to a huge picture, which would fill the server's memory.
MAX_UPLOAD_PIXELS = 40_000_000
NOT_AN_IMAGE = gettext_lazy("Upload a JPEG, PNG or WebP image of up to 5 MB.")


def clean_image(upload, widths):
    """Re-save an uploaded image, once for each width in `widths` (its longest side, in pixels).

    Returns the file extension and a `ContentFile` for each width, in the upload's own format (a
    PNG stays a lossless PNG) and never larger than the upload. Saving it afresh drops everything
    but the picture: location and camera details, and anything hidden in the file's other bytes.
    Raises `ValidationError` for a file that isn't a JPEG, PNG or WebP picture, or is too big.
    """
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(NOT_AN_IMAGE, code="invalid_image")
    try:
        with Image.open(upload) as opened:
            image_format = opened.format
            if image_format not in UPLOAD_FORMATS or (
                opened.width * opened.height > MAX_UPLOAD_PIXELS
            ):
                raise ValidationError(NOT_AN_IMAGE, code="invalid_image")
            opened.load()  # decodes it all, so a cut-off or disguised file fails here
            picture = ImageOps.exif_transpose(opened)
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
        raise ValidationError(NOT_AN_IMAGE, code="invalid_image") from error
    if image_format == "JPEG" and picture.mode not in ("RGB", "L", "CMYK"):
        picture = picture.convert("RGB")
    if image_format == "WEBP" and picture.mode not in ("RGB", "RGBA"):
        picture = picture.convert("RGBA")

    files = []
    for width in widths:
        smaller = picture.copy()
        smaller.thumbnail((width, width), Image.Resampling.LANCZOS)  # never enlarges
        saved = io.BytesIO()
        options = {"quality": 90} if image_format in ("JPEG", "WEBP") else {}
        smaller.save(saved, format=image_format, optimize=image_format != "WEBP", **options)
        files.append(ContentFile(saved.getvalue()))
    return UPLOAD_FORMATS[image_format], files


def check_upload(upload):
    """A field validator: a new upload must be a picture `clean_image()` can re-save. A file
    already stored isn't read again."""
    if not getattr(upload, "_committed", True):
        clean_image(upload, widths=(1,))
