import sqlite3
import tarfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        "Write a consistent copy of the SQLite database (db.sqlite3) and an archive of the "
        "uploads (media.tar.gz) to a folder. Safe to run while the site is serving requests."
    )

    def add_arguments(self, parser):
        parser.add_argument("destination", type=Path, help="Folder to write the backup to.")

    def handle(self, *args, destination, **options):
        destination = destination.resolve()
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if destination.is_relative_to(media_root):
            raise CommandError(
                f"Back up to a folder outside MEDIA_ROOT ({media_root}), "
                "or every archive would contain the previous backups."
            )
        destination.mkdir(parents=True, exist_ok=True)

        database = destination / "db.sqlite3"
        self.copy_database(database)
        uploads = destination / "media.tar.gz"
        with tarfile.open(uploads, "w:gz") as archive:
            if media_root.is_dir():
                archive.add(media_root, arcname="media")

        self.stdout.write(f"Backed up the database to {database} and the uploads to {uploads}")

    def copy_database(self, path):
        """Copy through SQLite's backup API, which never sees a half-written transaction.

        A plain file copy of a database that's being written to can be unusable.
        """
        if connection.vendor != "sqlite":
            raise CommandError("backup_site only knows how to back up SQLite.")
        connection.ensure_connection()
        path.unlink(missing_ok=True)
        target = sqlite3.connect(path)
        try:
            connection.connection.backup(target)
        finally:
            target.close()
