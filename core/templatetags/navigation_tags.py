from django import template

register = template.Library()


@register.inclusion_tag("includes/main_menu.html", takes_context=True)
def main_menu(context):
    """The standard's menu sections that have a published, public page (`chosen_pages`), each
    marked when it's the page being read or holds it (#171)."""
    current_page = context.get("page")
    menu_items = []
    for section in context.get("menu_sections") or []:
        page = section.page
        if current_page is None:
            state = None
        elif current_page.pk == page.pk:
            state = "page"
        elif current_page.path.startswith(page.path):
            state = "true"
        else:
            state = None
        menu_items.append({"name": section.name, "page": page, "aria_current": state})
    return {"menu_items": menu_items}
