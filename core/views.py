import posixpath

from django.conf import settings
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.views.static import serve


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /django-admin/",
        "Disallow: /search/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def serve_media(request, path):
    """Serve editors' uploads for small deployments with nothing else in front of the app.

    Streams files from MEDIA_ROOT; busy sites should put a web server or object storage in front.
    Documents are left out: only Wagtail's document view (/documents/<id>/<filename>) checks a
    collection's privacy, and it reads the file itself, so it never needs this view.
    """
    if not settings.SERVE_MEDIA or _top_level_folder(path) == "documents":
        raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT)


def _top_level_folder(path):
    # Resolve the path the way serve() does, so "./documents/x" or "images/../documents/x" can't
    # slip past. Windows and macOS disks also ignore case, and Windows reads backslashes as
    # slashes and drops trailing dots and spaces, so "Documents.\x" means "documents/x" there.
    normalised = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
    return normalised.split("/", 1)[0].rstrip(". ").casefold()
