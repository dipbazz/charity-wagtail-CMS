"""Take payments through Nepal's payment gateways, from any Python project.

Each gateway is a provider: one class in its own file in `providers/`, found by itself. Start a
payment with `start()`, send the payer where it says, then ask `check()` what became of it. See
README.md.
"""

from nepal_payments.base import (
    Outcome,
    PaymentError,
    PaymentProvider,
    PaymentRequest,
    ProviderRefused,
    ProviderUnavailable,
    Redirect,
    Started,
    Status,
    UnreadableAnswer,
)
from nepal_payments.registry import all_providers, get_provider, register

__all__ = [
    "Outcome",
    "PaymentError",
    "PaymentProvider",
    "PaymentRequest",
    "ProviderRefused",
    "ProviderUnavailable",
    "Redirect",
    "Started",
    "Status",
    "UnreadableAnswer",
    "all_providers",
    "get_provider",
    "register",
]
