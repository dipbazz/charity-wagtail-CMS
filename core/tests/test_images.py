import io

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from wagtail.images import get_image_model
from wagtail_factories import ImageFactory

from core.images import clean_image
from core.models import CustomImage, CustomRendition


def test_project_uses_the_custom_image_model():
    assert settings.WAGTAILIMAGES_IMAGE_MODEL == "core.CustomImage"
    assert get_image_model() is CustomImage


def test_credit_and_consent_are_editable_in_the_admin():
    assert {"credit", "consent_confirmed"} <= set(CustomImage.admin_form_fields)


@pytest.mark.django_db
def test_image_stores_photographer_credit_and_consent():
    image = ImageFactory(credit="Photo: Amara Okafor", consent_confirmed=True)
    image.refresh_from_db()

    assert image.credit == "Photo: Amara Okafor"
    assert image.consent_confirmed is True


@pytest.mark.django_db
def test_consent_is_not_assumed():
    assert ImageFactory().consent_confirmed is False


@pytest.mark.django_db
def test_renditions_are_stored_in_the_custom_rendition_model():
    image = ImageFactory()

    rendition = image.get_rendition("fill-100x100")

    assert isinstance(rendition, CustomRendition)
    assert (rendition.width, rendition.height) == (100, 100)


@pytest.mark.django_db
def test_image_description_is_used_as_alt_text():
    image = ImageFactory(description="Children collecting clean water")

    html = image.get_rendition("width-200").img_tag()

    assert 'alt="Children collecting clean water"' in html


class TestCleanImage:
    """Re-saving an upload that doesn't come from the image library (a QR card, a receipt)."""

    @staticmethod
    def upload(image_format="PNG", size=(2400, 1200), name="card", exif=None, mode="RGB"):
        picture = Image.new(mode, size, "white")
        saved = io.BytesIO()
        extra = {"exif": exif} if exif else {}
        picture.save(saved, format=image_format, **extra)
        return SimpleUploadedFile(name, saved.getvalue())

    def test_saves_each_width_in_the_uploads_own_format(self):
        extension, files = clean_image(self.upload("PNG"), widths=(1600, 800))

        assert extension == "png"
        sizes = [Image.open(io.BytesIO(file.read())) for file in files]
        assert [(each.format, each.size) for each in sizes] == [
            ("PNG", (1600, 800)),
            ("PNG", (800, 400)),
        ]

    @pytest.mark.parametrize("image_format", ["JPEG", "WEBP"])
    def test_keeps_a_jpeg_or_webp_as_one(self, image_format):
        _, files = clean_image(self.upload(image_format), widths=(1600,))

        assert Image.open(io.BytesIO(files[0].read())).format == image_format

    def test_saves_a_phone_cameras_jpeg_as_a_plain_jpeg(self):
        # Many phone cameras add a second, smaller picture to each JPEG, which Pillow reads as MPO.
        saved = io.BytesIO()
        first, second = Image.new("RGB", (400, 300), "white"), Image.new("RGB", (40, 30))
        first.save(saved, format="MPO", save_all=True, append_images=[second])
        assert Image.open(io.BytesIO(saved.getvalue())).format == "MPO"

        extension, files = clean_image(SimpleUploadedFile("photo.jpg", saved.getvalue()), (800,))

        assert extension == "jpg"
        assert Image.open(io.BytesIO(files[0].read())).format == "JPEG"

    def test_never_enlarges_a_small_image(self):
        _, files = clean_image(self.upload(size=(300, 300)), widths=(1600, 800))

        assert [Image.open(io.BytesIO(file.read())).size for file in files] == [(300, 300)] * 2

    def test_drops_the_location_and_camera_details(self):
        exif = Image.Exif()
        exif[0x010F] = "Camera Maker"  # Make
        photo = self.upload("JPEG", exif=exif.tobytes())
        assert b"Camera Maker" in photo.read()
        photo.seek(0)

        _, files = clean_image(photo, widths=(800,))

        assert b"Camera Maker" not in files[0].read()

    def test_turns_a_sideways_photo_upright(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # rotated: displayed turned a quarter
        photo = self.upload("JPEG", size=(400, 200), exif=exif.tobytes())

        _, files = clean_image(photo, widths=(800,))

        assert Image.open(io.BytesIO(files[0].read())).size == (200, 400)

    @pytest.mark.parametrize(
        "upload",
        [
            SimpleUploadedFile("note.png", b"not a picture at all"),
            SimpleUploadedFile("card.png", b"<svg xmlns='http://www.w3.org/2000/svg'/>"),
        ],
        ids=["text", "svg"],
    )
    def test_refuses_what_isnt_a_picture(self, upload):
        with pytest.raises(ValidationError):
            clean_image(upload, widths=(800,))

    def test_refuses_a_format_that_isnt_allowed(self):
        with pytest.raises(ValidationError):
            clean_image(self.upload("GIF"), widths=(800,))

    def test_refuses_a_file_that_is_cut_off(self):
        whole = self.upload("PNG").read()

        with pytest.raises(ValidationError):
            clean_image(SimpleUploadedFile("card.png", whole[: len(whole) // 2]), widths=(800,))

    def test_refuses_a_file_over_5_mb(self):
        big = SimpleUploadedFile("card.png", b"\x89PNG" + b"0" * (5 * 1024 * 1024))

        with pytest.raises(ValidationError):
            clean_image(big, widths=(800,))

    def test_refuses_one_that_would_decode_to_too_many_pixels(self):
        huge = self.upload("PNG", size=(7000, 7000), mode="1")

        with pytest.raises(ValidationError):
            clean_image(huge, widths=(800,))

    def test_refuses_more_pixels_than_the_caller_allows(self):
        # A receipt allows far fewer than a QR card: a small file can decode to a picture that
        # fills the server's memory.
        upload = self.upload("PNG", size=(2000, 2000), mode="1")

        with pytest.raises(ValidationError) as refused:
            clean_image(upload, widths=(800,), max_pixels=3_000_000)

        assert refused.value.messages == ["This picture is too large: upload a smaller one."]

    def test_returns_each_width_in_the_order_asked(self):
        _, files = clean_image(self.upload(size=(2400, 1200)), widths=(800, 1600))

        assert [Image.open(io.BytesIO(file.read())).size for file in files] == [
            (800, 400),
            (1600, 800),
        ]
