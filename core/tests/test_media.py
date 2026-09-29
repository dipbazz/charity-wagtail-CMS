import pytest


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
