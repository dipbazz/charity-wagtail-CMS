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
# What to serve each as, by the extension clean_image() gives it.
UPLOAD_CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
# Formats saved as another: a phone camera's JPEG often carries a second, smaller picture, which
# Pillow reads as MPO. Only the first is kept.
SAVED_AS = {"MPO": "JPEG"}
# The file names those come with: a JPEG is as often called .jpeg as .jpg.
UPLOAD_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# A small file can still decode to a huge picture, which would fill the server's memory: each
# million pixels decoded takes about 4 MB while it's re-saved. The most a moderator's QR card may
# decode to (a big scan); a visitor's upload passes a lower limit of its own (`max_pixels`).
MAX_UPLOAD_PIXELS = 40_000_000
NOT_AN_IMAGE = gettext_lazy("Upload a JPEG, PNG or WebP image of up to 5 MB.")
TOO_MANY_PIXELS = gettext_lazy("This picture is too large: upload a smaller one.")
# What a re-saved picture keeps from its upload: its colours, and a palette PNG's see-through one.
PICTURE_INFO = ("icc_profile", "transparency")


def clean_image(upload, widths, max_pixels=MAX_UPLOAD_PIXELS):
    """Re-save an uploaded image, once for each width in `widths` (its longest side, in pixels).

    Returns the file extension and a `ContentFile` for each width, in the upload's own format (a
    PNG stays a lossless PNG) and never larger than the upload. Saving it afresh drops everything
    but the picture: location and camera details, and anything hidden in the file's other bytes.
    Raises `ValidationError` for a file that isn't a JPEG, PNG or WebP picture, is over 5 MB, or
    decodes to more than `max_pixels`. Only the smaller copies are kept, never the upload.

    It holds one decoded copy at a time: turned upright in place, then made smaller in place,
    largest width first. A JPEG is decoded straight to a half, a quarter or an eighth of its size
    (at least the largest width, and under twice it), so a big photo is never held whole and
    passes a limit its full size wouldn't. A PNG or WebP can only be decoded whole.
    """
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(NOT_AN_IMAGE, code="invalid_image")
    try:
        # Not closed when done: closing throws the decoded picture away. Pillow didn't open the
        # upload, so it leaves it to its owner.
        picture = Image.open(upload)
        image_format = SAVED_AS.get(picture.format, picture.format)
        if image_format not in UPLOAD_FORMATS:
            raise ValidationError(NOT_AN_IMAGE, code="invalid_image")
        # Only a JPEG's reader can do this; it sets the size it will decode to.
        scale = max(widths) / max(picture.size)
        if scale < 1:
            fitted = (max(1, round(picture.width * scale)), max(1, round(picture.height * scale)))
            picture.draft(None, fitted)
        if picture.width * picture.height > max_pixels:
            raise ValidationError(TOO_MANY_PIXELS, code="too_many_pixels")
        picture.load()  # decodes it all, so a cut-off or disguised file fails here
        ImageOps.exif_transpose(picture, in_place=True)
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
        raise ValidationError(NOT_AN_IMAGE, code="invalid_image") from error
    if image_format == "JPEG" and picture.mode not in ("RGB", "L", "CMYK"):
        picture = picture.convert("RGB")
    if image_format == "WEBP" and picture.mode not in ("RGB", "RGBA"):
        picture = picture.convert("RGBA")
    # Saving copies some of what was read with the picture, such as a JPEG's comment (free text
    # anyone can write in the file). Only what the picture needs to look the same is kept.
    picture.info = {key: picture.info[key] for key in PICTURE_INFO if key in picture.info}

    files = {}
    for width in sorted(set(widths), reverse=True):
        picture.thumbnail((width, width), Image.Resampling.LANCZOS)  # never enlarges
        saved = io.BytesIO()
        options = {"quality": 90} if image_format in ("JPEG", "WEBP") else {}
        picture.save(saved, format=image_format, optimize=image_format != "WEBP", **options)
        files[width] = ContentFile(saved.getvalue())
    return UPLOAD_FORMATS[image_format], [files[width] for width in widths]


def check_upload(upload):
    """A field validator: a new upload must be a picture `clean_image()` can re-save. A file
    already stored isn't read again."""
    if not getattr(upload, "_committed", True):
        clean_image(upload, widths=(1,))
