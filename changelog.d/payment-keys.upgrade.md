Nothing changes until a charity takes payments. Then set each provider's merchant keys in the
server's `deploy/aws/.env` as `DJANGO_PAYMENT_<PROVIDER>_<KEY>` (the keys are listed in Running the
live site), and `DJANGO_LIVE_PAYMENTS=true` only together with live keys. The `web` service now
reads the whole `.env`, and a provider with only some of its keys stops the site starting
([#93](https://github.com/dipbazz/Charity-wagtail-CMS/issues/93)).
