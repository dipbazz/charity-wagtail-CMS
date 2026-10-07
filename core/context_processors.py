from django.utils import translation
from django.utils.functional import SimpleLazyObject
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.models import Page

from core.models import SiteSettings


def privacy_page(request):
    """The privacy notice chosen in Site settings, for the footer and forms to link to.

    In the language being read once it's translated, else the chosen page; None until a page is
    chosen and published. Looked up only when a template uses it, and once per request: one query
    in the notice's own language, one more in another.
    """

    def find():
        settings = SiteSettings.for_request(request)
        if settings.privacy_page_id is None:
            return None
        page = Page.objects.select_related("locale").filter(pk=settings.privacy_page_id).first()
        if page is None:
            return None
        language = get_supported_content_language_variant(translation.get_language())
        if page.locale.language_code != language:
            translated = (
                page.get_translations().live().filter(locale__language_code=language).first()
            )
            if translated is not None:
                return translated
        return page if page.live else None

    return {"privacy_page": SimpleLazyObject(find)}
