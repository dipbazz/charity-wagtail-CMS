"""Admin panels for the site's own models."""

from django.utils.html import format_html, format_html_join
from django.utils.text import get_text_list
from wagtail.admin.panels import HelpPanel, TabbedInterface
from wagtail.models import Page

from core.menu import NOT_PUBLIC, NOT_PUBLISHED, NOT_SET, SECTIONS, menu_sections, private_paths

# What the Menu tab says about the sections the menu leaves out, by status: for one, for several.
MENU_NOTICES = {
    NOT_SET: (
        "The menu leaves it out until you choose a published page.",
        "The menu leaves them out until you choose a published page for each.",
    ),
    NOT_PUBLISHED: (
        "The menu leaves it out until it's published.",
        "The menu leaves them out until they're published.",
    ),
    NOT_PUBLIC: (
        "The menu leaves it out while it's behind a password or a login.",
        "The menu leaves them out while they're behind a password or a login.",
    ),
}


class MenuNoticesPanel(HelpPanel):
    """Site settings → Menu's notices: each section the menu leaves out, and why (#171)."""

    class BoundPanel(HelpPanel.BoundPanel):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.content = self.notices()

        def notices(self):
            ids = [getattr(self.instance, f"{section.setting}_id") for section in SECTIONS]
            pages = Page.objects.in_bulk([pk for pk in ids if pk is not None])
            found = {
                section.setting: pages.get(pk) for section, pk in zip(SECTIONS, ids, strict=True)
            }
            sections = menu_sections(self.instance, found, private_paths() if pages else [])
            lines = []
            for status, (one, several) in MENU_NOTICES.items():
                names = [str(each.name) for each in sections if each.status == status]
                if names:
                    label = status[0].upper() + status[1:]
                    why = one if len(names) == 1 else several
                    lines.append((label, get_text_list(names, "and"), why))
            return format_html_join(
                "", '<p class="help-block help-warning">{}: {}. {}</p>', lines
            ) or format_html("<p>{}</p>", "Every section is in the menu.")


class TabsOpeningOnErrors(TabbedInterface):
    """Tabs that open on the first one with a mistake in it when a save is refused.

    Wagtail opens the first tab and only counts the errors on the others, so a refused colour
    on the Brand tab of Site settings came back on the Organisation tab, out of sight. The tabs
    script opens the panel this names, unless the address names one.
    """

    class BoundPanel(TabbedInterface.BoundPanel):
        @property
        def attrs(self):
            tab = self.first_tab_with_errors()
            if tab is None:
                return super().attrs
            return {**super().attrs, "data-w-tabs-active-panel-id-value": f"tab-{tab}"}

        def first_tab_with_errors(self):
            if self.form is None or not self.form.is_bound:
                return None
            for child, identifier in self.visible_children_with_identifiers:
                options = child.panel.get_form_options()
                fields = options.get("fields", [])
                formsets = [self.form.formsets[name] for name in options.get("formsets", {})]
                if any(name in self.form.errors for name in fields) or any(
                    any(formset.errors) or formset.non_form_errors() for formset in formsets
                ):
                    return identifier
            return None
