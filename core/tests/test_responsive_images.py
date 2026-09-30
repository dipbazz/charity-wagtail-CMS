"""Images come in the size and format each screen needs, and don't make the page jump."""

import pytest
from bs4 import BeautifulSoup
from django.template import Context, Template
from wagtail_factories import ImageFactory

from core import blocks, models
from core.blocks import CaptionedImageBlock, PartnersBlock

pytestmark = pytest.mark.django_db


def parse(html):
    return BeautifulSoup(html, "html.parser")


def widths(srcset):
    return sorted(int(candidate.split()[-1].rstrip("w")) for candidate in srcset.split(", "))


def source_types(picture):
    return [source["type"] for source in picture.find_all("source")]


def render_hero(image):
    template = Template(
        '{% load picture_tags %}{% hero_picture image class="hero-image" fetchpriority="high" %}'
    )
    return parse(template.render(Context({"image": image})))


class TestHeroPicture:
    def test_phones_get_a_square_crop_and_wider_screens_a_banner(self):
        picture = render_hero(ImageFactory(file__width=2000, file__height=1500)).picture

        phone, *other = picture.find_all("source")
        assert phone["media"] == "(max-width: 39.99rem)"
        assert widths(phone["srcset"]) == [480, 800]
        assert (phone["width"], phone["height"]) == ("800", "800")

        img = picture.img
        assert widths(img["srcset"]) == [1200, 1600]
        assert (img["width"], img["height"]) == ("1600", "700")

    def test_phone_crops_are_compressed_harder_than_the_wide_banner(self):
        # On phones the banner sits under a 75% dark overlay that hides the detail a higher
        # quality would keep; on wider screens the photo shows clearly on the right.
        picture = render_hero(ImageFactory(file__width=2000, file__height=1500)).picture
        phone = [s["srcset"] for s in picture.find_all("source", media=True)]
        wide = [s["srcset"] for s in picture.find_all("source", media=False)]
        wide.append(picture.img["srcset"])

        qualities = ("avifquality-40", "webpquality-50", "jpegquality-50")
        assert [[quality in s for quality in qualities] for s in phone] == [
            [True, False, False],
            [False, True, False],
            [False, False, True],
        ]
        assert not any("quality-" in s for s in wide)

    def test_offers_avif_and_webp_before_the_jpeg_fallback(self):
        picture = render_hero(ImageFactory(file__width=2000, file__height=1500)).picture

        assert source_types(picture) == [
            "image/avif",
            "image/webp",
            "image/jpeg",  # phones without AVIF or WebP still get the square crop
            "image/avif",
            "image/webp",
        ]
        assert picture.img["src"].endswith(".jpg")

    def test_loads_first_and_is_never_lazy(self):
        img = render_hero(ImageFactory()).img

        assert img["fetchpriority"] == "high"
        assert "loading" not in img.attrs
        assert img["class"] == ["hero-image"]
        assert img["sizes"] == "100vw"

    def test_keeps_the_images_alt_text(self):
        img = render_hero(ImageFactory(description="Villagers at the new tap stand")).img

        assert img["alt"] == "Villagers at the new tap stand"

    def test_renders_nothing_without_an_image(self):
        assert str(render_hero(None)) == ""


class TestBlockImages:
    def test_captioned_image_is_lazy_loaded_in_modern_formats(self):
        block = CaptionedImageBlock()
        image = ImageFactory(file__width=1600, file__height=1200, credit="Photo: Amara Okafor")

        html = parse(block.render(block.to_python({"image": image.pk, "caption": "The well"})))

        assert source_types(html.picture) == ["image/avif", "image/webp"]
        img = html.picture.img
        assert img["loading"] == "lazy"
        assert widths(img["srcset"]) == [480, 800, 1000]
        # The <img> keeps its full size, so it fills the column; the browser picks a smaller file.
        assert (img["width"], img["height"]) == ("1000", "750")
        assert "Photo: Amara Okafor" in html.figcaption.text

    def test_testimonial_photo_is_lazy_loaded_in_modern_formats(self):
        testimonial = models.Testimonial(
            quote="The new well means my daughter is back at school.",
            name="Grace",
            photo=ImageFactory(file__width=600, file__height=600),
        )
        testimonial.save()
        testimonial.save_revision().publish()
        testimonial.refresh_from_db()

        html = parse(blocks.TestimonialBlock().render(testimonial))

        assert source_types(html.picture) == ["image/avif", "image/webp"]
        img = html.picture.img
        assert img["loading"] == "lazy"
        assert (img["width"], img["height"]) == ("120", "120")
        assert "testimonial-photo" in img["class"]

    def test_partner_logos_stay_png_with_their_size_and_load_lazily(self):
        models.Partner.objects.create(
            name="Rivers Foundation", logo=ImageFactory(file__width=480, file__height=160)
        )
        block = PartnersBlock()

        img = parse(block.render(block.to_python({"heading": "Our partners"}))).img

        assert img["loading"] == "lazy"
        assert (img["width"], img["height"]) == ("240", "80")
        assert img.parent.name != "picture"
