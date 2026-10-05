from decimal import ROUND_HALF_UP, Decimal

# Currency code: (name shown to admins, symbol shown before amounts, digit grouping).
# "lakh" groups the Nepali and Indian way (46,87,500); "western" in threes (4,687,500).
CURRENCIES = {
    "NPR": ("Nepalese rupee", "Rs ", "lakh"),
    "GBP": ("Pound sterling", "£", "western"),
}
CURRENCY_CHOICES = [
    (code, f"{name} ({symbol.strip()})") for code, (name, symbol, _) in CURRENCIES.items()
]


def group_digits(number, grouping):
    """Put commas in a whole number: in threes, or for lakh the last three then pairs."""
    digits = str(number)
    if grouping == "western" or len(digits) <= 3:
        return f"{number:,}"
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while head:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(pairs + [tail])


def format_money(amount, currency):
    """A whole amount with its currency symbol and digit grouping, e.g. "Rs 46,87,500"."""
    _, symbol, grouping = CURRENCIES[currency]
    whole = int(Decimal(str(amount)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return f"{symbol}{group_digits(whole, grouping)}"
