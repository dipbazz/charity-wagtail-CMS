"""Payment providers' keys come from DJANGO_PAYMENT_<PROVIDER>_<KEY> variables, so a new provider
needs no settings code (docs/hosting.md)."""

from charity.settings.payments import payment_keys


def test_reads_each_providers_keys_by_their_names():
    environ = {
        "DJANGO_PAYMENT_ESEWA_PRODUCT_CODE": "EPAYTEST",
        "DJANGO_PAYMENT_ESEWA_SECRET_KEY": "s3cret",
        "DJANGO_PAYMENT_IMEPAY_MERCHANT_CODE": "IME-1",
    }

    assert payment_keys(environ) == {
        "ESEWA_PRODUCT_CODE": "EPAYTEST",
        "ESEWA_SECRET_KEY": "s3cret",
        "IMEPAY_MERCHANT_CODE": "IME-1",
    }


def test_ignores_every_other_variable():
    environ = {
        "DJANGO_LIVE_PAYMENTS": "true",
        "DJANGO_SECRET_KEY": "not-a-payment-key",
        "PAYMENT_KHALTI_SECRET_KEY": "no-django-prefix",
    }

    assert payment_keys(environ) == {}


def test_an_empty_variable_is_a_key_not_set():
    """As env.example leaves them, so a copied file doesn't set up half a provider."""
    assert payment_keys({"DJANGO_PAYMENT_KHALTI_SECRET_KEY": ""}) == {}
