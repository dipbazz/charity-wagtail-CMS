"""Admin panels for the site's own models."""

from wagtail.admin.panels import TabbedInterface


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
