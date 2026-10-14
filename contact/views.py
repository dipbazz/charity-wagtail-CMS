from wagtail.contrib.forms.views import SubmissionsListView

from core.exports import VisitorTextExportMixin


class FormSubmissionsListView(VisitorTextExportMixin, SubmissionsListView):
    """A form's submissions in the admin, exported with what visitors typed as text."""
