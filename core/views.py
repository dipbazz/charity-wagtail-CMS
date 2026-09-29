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
    """
    if not settings.SERVE_MEDIA:
        raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT)
