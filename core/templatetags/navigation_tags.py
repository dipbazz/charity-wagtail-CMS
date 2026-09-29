from django import template
from wagtail.models import Site

register = template.Library()


@register.inclusion_tag("includes/main_menu.html", takes_context=True)
def main_menu(context):
    request = context["request"]
    current_page = context.get("page")
    site = Site.find_for_request(request)
    if site is None:
        return {"menu_items": []}

    menu_items = []
    for item in site.root_page.get_children().live().in_menu():
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
