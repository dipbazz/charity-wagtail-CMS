"""Payment providers' keys from the environment, read the same way by every settings module.

Not a settings module itself: `dev.py` and `production.py` use it.
"""

PREFIX = "DJANGO_PAYMENT_"


def payment_keys(environ):
    """Every DJANGO_PAYMENT_<PROVIDER>_<KEY> variable as {"<PROVIDER>_<KEY>": value}: for
    example DJANGO_PAYMENT_KHALTI_SECRET_KEY gives "KHALTI_SECRET_KEY". So a new provider needs no
    code here. An empty variable is a key not set.
    """
    return {
        name.removeprefix(PREFIX): value
        for name, value in environ.items()
        if name.startswith(PREFIX) and value
    }
