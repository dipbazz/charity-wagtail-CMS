from django import template
from wagtail.models import Page, Site

register = template.Library()


@register.inclusion_tag("includes/main_menu.html", takes_context=True)
def main_menu(context):
    request = context["request"]
    current_page = context.get("page")
    site = Site.find_for_request(request)
    if site is None:
        return {"menu_items": []}

    # The menu is the home page's children, in the language being read. Each language's home page
    # sits at the site root's depth, so a page's own home page is the start of its tree path; that
    # saves looking up the translation. Without a page (search), use the request's language.
    home = site.root_page
    if current_page is None:
        home_path = home.localized.path
    else:
        home_path = current_page.path[: home.depth * Page.steplen]
    children = Page.objects.filter(depth=home.depth + 1, path__startswith=home_path)

    menu_items = []
    for item in children.live().in_menu().order_by("path"):
        if current_page is None:
            state = None
        elif current_page.pk == item.pk:
            state = "page"
        elif current_page.is_descendant_of(item):
            state = "true"
        else:
            state = None
        menu_items.append({"page": item, "aria_current": state})
    return {"menu_items": menu_items}
