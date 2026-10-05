from django.template.defaultfilters import floatformat

# Currency code: (name shown to admins, symbol shown before amounts).
CURRENCIES = {
    "NPR": ("Nepalese rupee", "Rs "),
    "GBP": ("Pound sterling", "£"),
}
CURRENCY_CHOICES = [
    (code, f"{name} ({symbol.strip()})") for code, (name, symbol) in CURRENCIES.items()
]


def format_money(amount, currency):
    """A whole amount with its currency symbol and thousands grouping, e.g. "Rs 1,500"."""
    symbol = CURRENCIES[currency][1]
    return f"{symbol}{floatformat(amount, '0g')}"
