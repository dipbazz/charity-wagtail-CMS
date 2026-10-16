from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    """Files kept on the server's disk that no address serves, such as the receipt screenshots
    supporters send: only a view that checks who is asking reads them out. Keep its `location`
    outside MEDIA_ROOT, which the web server and the uploads' backup both take whole. Only the
    site's own user can read the files."""

    def __init__(self, **kwargs):
        kwargs.setdefault("file_permissions_mode", 0o600)
        kwargs.setdefault("directory_permissions_mode", 0o700)
        super().__init__(**kwargs)

    def url(self, name):
        raise ValueError("A private file has no URL: serve it from a view that checks permission.")
