import io
import sqlite3
import tarfile

import pytest
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command

# The SQLite backup API copies what has been committed, so the data must really be committed.
pytestmark = pytest.mark.django_db(transaction=True)


def backup_site(destination):
    call_command("backup_site", str(destination), stdout=io.StringIO())


def test_copies_the_database_while_the_site_is_running(tmp_path):
    """A plain file copy of a live SQLite database can catch it half-written; this can't."""
    Group.objects.create(name="Trustees")

    backup_site(tmp_path)

    with sqlite3.connect(tmp_path / "db.sqlite3") as backup:
        names = [row[0] for row in backup.execute("SELECT name FROM auth_group")]
    assert "Trustees" in names


def test_archives_the_uploaded_files(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    (settings.MEDIA_ROOT / "original_images").mkdir(parents=True)
    (settings.MEDIA_ROOT / "original_images" / "well.jpg").write_bytes(b"photo")
    destination = tmp_path / "backup"

    backup_site(destination)

    with tarfile.open(destination / "media.tar.gz") as archive:
        assert archive.extractfile("media/original_images/well.jpg").read() == b"photo"


def test_backs_up_a_site_with_no_uploads_yet(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "no-media-yet"

    backup_site(tmp_path / "backup")

    with tarfile.open(tmp_path / "backup" / "media.tar.gz") as archive:
        assert archive.getnames() == []


def test_replaces_the_previous_backup(tmp_path):
    (tmp_path / "db.sqlite3").write_bytes(b"yesterday")
    Group.objects.create(name="Volunteers")

    backup_site(tmp_path)

    with sqlite3.connect(tmp_path / "db.sqlite3") as backup:
        names = [row[0] for row in backup.execute("SELECT name FROM auth_group")]
    assert "Volunteers" in names


def test_refuses_to_back_up_into_the_uploads_folder(settings, tmp_path):
    """The archive would then contain the backups, growing with every run."""
    settings.MEDIA_ROOT = tmp_path / "media"

    with pytest.raises(CommandError, match="outside"):
        backup_site(settings.MEDIA_ROOT / "backups")
