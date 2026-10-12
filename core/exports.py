"""Spreadsheet exports of what visitors typed, which a spreadsheet shows as text and never runs.

Excel, LibreOffice and Google Sheets read a cell that starts with = as a formula (in a CSV, + - @
and a leading tab or carriage return too). Wagtail's exports write text as it is, so a pledge
"from" =HYPERLINK("https://…?"&B2) could send other donors' details away when the team opens the
export (CWE-1236).
"""

import re

# What makes a CSV cell a formula (OWASP's list). A plain number, such as +9779841234567, is safe.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
NUMBER = re.compile(r"[+-]?\d+(\.\d+)?")


def as_text(value):
    """A CSV cell that a spreadsheet shows as text: a leading ' if it would start a formula."""
    if isinstance(value, str) and value.startswith(FORMULA_START) and not NUMBER.fullmatch(value):
        return "'" + value
    return value


class VisitorTextExportMixin:
    """For a Wagtail view with a spreadsheet export (SpreadsheetExportMixin) of what visitors
    typed. Put it first among the view's bases."""

    def preprocess_field_value(self, field, value, export_format):
        value = super().preprocess_field_value(field, value, export_format)
        return as_text(value) if export_format == self.FORMAT_CSV else value

    def generate_xlsx_row(self, worksheet, row_dict, date_format=None):
        for cell in super().generate_xlsx_row(worksheet, row_dict, date_format):
            # openpyxl makes any text that starts with = a formula. A text cell shows it as typed.
            if cell.data_type == "f":
                cell.data_type = "s"
            yield cell
