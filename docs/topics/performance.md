# Performance

Pages have to stay fast on a phone, so new features are measured from the start (query counts,
image weight, behaviour at 320–1440px), and CI fails a pull request that makes pages slower.

## Database query budgets

`charity/tests/test_query_budgets.py` sets the most queries each kind of page may run on the
full demo site. A change that adds queries fails with the page and the count.

- Raise a budget only on purpose, in the same pull request, and say why.
- Lower it when a change saves queries.
- The listing tests in `campaigns` and `news` add a check of their own with the
  `cold_cache_queries` fixture. It counts queries as on a just-started server, with image
  renditions looked up in the database, so a missing prefetch shows up as one query per card.

The usual cause of a new query per item is a card listing that isn't wrapped in
`with_card_images()`; see [Images](images.md#card-listings).

## Page weight and layout shift

A Lighthouse CI job loads `seed_demo` into production settings behind gunicorn, then checks the
homepage, the appeals page, an appeal and the news page with Lighthouse's phone emulation
(412px, pixel density 1.75). Budgets are in `lighthouserc.json`:

- **Fail the build:** total bytes and image bytes per page, and layout shift (CLS above 0.1).
- **Only warn:** largest paint (LCP above 4 seconds) and the performance score (below 0.8),
  because timings vary on shared CI machines.

The reports are attached to each run as the `lighthouse-reports` artifact.
[Run Lighthouse locally](../how-to/run-lighthouse.md) shows how to reproduce a run.

## While developing

`runserver` shows [django-debug-toolbar](https://django-debug-toolbar.readthedocs.io/) on every
page, with the SQL queries, templates and timings behind it. It's a dev dependency only, so
production and test settings leave it out.
