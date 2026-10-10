# Performance

Pages have to stay fast on a phone on a slow connection, so every feature is measured from the
start (database queries, page weight, layout at 320–1440px) and CI fails a pull request that
makes pages slower.

## Database query budgets

`charity/tests/test_query_budgets.py` sets the most queries each kind of page may run on the full
demo site, with a comment saying what each extra query is for. A change that adds queries fails
with the page and the count.

- Raise a budget only on purpose, in the same pull request, and say why in that comment.
- Lower it when a change saves queries.
- The listing tests in `campaigns` and `news` also count queries with the `cold_cache_queries`
  fixture, as on a just-started server with image renditions looked up in the database, so a
  missing prefetch shows up as one query per card. The usual cause is a card listing not wrapped
  in `with_card_images()` ([Images](../site/images.md#card-listings)).

## Page weight and layout shift

A Lighthouse job in CI serves the demo site with production settings behind gunicorn and checks
the home page, the appeals page, an appeal and the news page as a phone would (412px wide, pixel
density 1.75). Budgets are in `lighthouserc.json`:

- **Fail the build:** image bytes per page, total bytes per page, and layout shift (CLS above 0.1).
- **Only warn:** largest paint (LCP above 4 seconds) and the performance score (below 0.8), because
  timings vary on shared CI machines.

**Images are what makes a page heavy, so their budget is strict:** about 5% above the page's image
weight today, so an extra or larger photo fails. HTML, CSS and JavaScript weigh 16–20KB on every
page, so they share one fixed allowance: **each page's total budget is its image budget plus
25,000 bytes** (`charity/tests/test_lighthouse_budgets.py` keeps it that way). A template or
stylesheet change therefore never needs a budget edit; raise the allowance only if the markup and
CSS have genuinely grown, and say why.

The charity's [logo](../site/look-and-feel.md#the-logo) is one more image on every page, so each
image budget includes the demo logo's 1.6KB (#123). A real charity's logo costs about as much, as
the header serves it as a copy no larger than 320 by 80 pixels.

Each run's reports are attached as the `lighthouse-reports` artifact.

## Measure page weight locally

1. Start the site from the Docker image with the demo content
   ([Getting started](../getting-started/index.md#run-it-as-the-live-site-runs-it)):
   `docker compose up --build`. This works on Windows too, where gunicorn doesn't run outside
   Docker.
2. Visit `/`, `/appeals/`, `/appeals/flood-relief/` and `/stories/` on <http://localhost:8090> once, so
   image renditions exist before anything is measured.
3. Run Lighthouse on those pages (the addresses are given here because CI's are on port 8000):

   ```bash
   npx @lhci/cli@0.15.1 autorun --collect.url=http://localhost:8090/ --collect.url=http://localhost:8090/appeals/ --collect.url=http://localhost:8090/appeals/flood-relief/ --collect.url=http://localhost:8090/stories/
   ```

   Reports go to `.lighthouseci/reports`. Set `CHROME_PATH` if Chrome isn't found; Edge works too.

Measure image savings this way, not in a desktop browser at pixel density 1, which picks smaller
files.

## While developing

`runserver` shows [django-debug-toolbar](https://django-debug-toolbar.readthedocs.io/) on every
page, with the SQL queries, templates and timings behind it. It's a development dependency only.
