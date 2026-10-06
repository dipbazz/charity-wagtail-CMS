from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.documents.api.v2.views import DocumentsAPIViewSet
from wagtail.images.api.v2.views import ImagesAPIViewSet


class LocalizedPagesAPIViewSet(PagesAPIViewSet):
    """Pages, with each page's language read in the same query.

    Every page in a listing shows its language (`meta.locale`), which otherwise costs one query
    per page.
    """

    def get_queryset(self):
        return super().get_queryset().select_related("locale")


class ConsentedImagesAPIViewSet(ImagesAPIViewSet):
    """Only list images whose safeguarding consent has been recorded.

    The images endpoint exposes every image's original file, including ones never used on a page,
    so an editor's upload must not become public before consent is confirmed.
    """

    def get_queryset(self):
        return super().get_queryset().filter(consent_confirmed=True)


# Read-only JSON API for the pages, images and documents editors publish,
# e.g. for a mobile app or a partner's website.
api_router = WagtailAPIRouter("wagtailapi")
api_router.register_endpoint("pages", LocalizedPagesAPIViewSet)
api_router.register_endpoint("images", ConsentedImagesAPIViewSet)
api_router.register_endpoint("documents", DocumentsAPIViewSet)
