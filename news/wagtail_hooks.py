from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from news.models import NewsCategory


class NewsCategoryViewSet(SnippetViewSet):
    model = NewsCategory
    icon = "tag"
    menu_label = "News categories"
    add_to_admin_menu = True
    menu_order = 310
    list_display = ["name", "slug"]


register_snippet(NewsCategoryViewSet)
