import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from wagtail.documents import get_document_model
from wagtail.models import Collection, CollectionViewRestriction


@pytest.fixture
def uploaded_file(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "original_images").mkdir()
    (tmp_path / "original_images" / "well.jpg").write_bytes(b"jpeg bytes")
    return "/media/original_images/well.jpg"


def test_uploads_are_not_served_by_django_by_default(client, db, uploaded_file):
    assert client.get(uploaded_file).status_code == 404


def test_uploads_are_served_when_enabled(client, db, settings, uploaded_file):
    settings.SERVE_MEDIA = True

    response = client.get(uploaded_file)

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"jpeg bytes"


@pytest.fixture
def private_document(db, settings, tmp_path):
    """A document in a password-protected collection, stored on disk as in production."""
    settings.MEDIA_ROOT = tmp_path
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    }
    settings.SERVE_MEDIA = True
    trustees = Collection.get_first_root_node().add_child(name="Trustees")
    restriction = CollectionViewRestriction.objects.create(
        collection=trustees, restriction_type=CollectionViewRestriction.PASSWORD, password="pw"
    )
    document = get_document_model()(title="Trustee minutes", collection=trustees)
    document.file.save("trustee-minutes.txt", ContentFile(b"confidential"))
    document.restriction = restriction
    return document


def body(response):
    return b"".join(response.streaming_content)


@pytest.mark.parametrize(
    "path",
    [
        "documents/trustee-minutes.txt",
        "./documents/trustee-minutes.txt",
        "images/../documents/trustee-minutes.txt",
        "Documents/trustee-minutes.txt",
        "documents\trustee-minutes.txt",
        "documents./trustee-minutes.txt",
    ],
)
def test_documents_are_never_served_from_media(client, private_document, path):
    """Only Wagtail's document view checks collection privacy, so /media/ mustn't bypass it."""
    assert client.get(f"/media/{path}").status_code == 404


def test_private_document_downloads_from_its_link_after_the_password(client, private_document):
    assert b"confidential" not in client.get(private_document.url).content

    client.post(
        reverse("wagtaildocs_authenticate_with_password", args=[private_document.restriction.id]),
        {"password": "pw", "return_url": private_document.url},
    )

    assert body(client.get(private_document.url)) == b"confidential"


def test_public_document_downloads_from_its_link(client, private_document):
    public = get_document_model()(title="Annual report")
    public.file.save("annual-report.txt", ContentFile(b"report"))

    assert body(client.get(public.url)) == b"report"
