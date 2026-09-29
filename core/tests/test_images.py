import pytest
from django.conf import settings
from wagtail.images import get_image_model
from wagtail_factories import ImageFactory

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
