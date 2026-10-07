# Run Lighthouse locally

Reproduce CI's page weight and layout shift checks ([Performance](../topics/performance.md)) on
your own computer, for example to measure an image change before pushing it.

1. Start the site from the Docker image, with production settings and the demo content
   ([Getting started](../getting-started/index.md#run-it-as-the-live-site-runs-it)):
   `docker compose up --build`. This works on Windows, where gunicorn doesn't run outside Docker.
2. Visit each page once, so image renditions exist before anything is measured: `/`, `/appeals/`,
   `/appeals/flood-relief/` and `/news/` on <http://localhost:8090>.
3. Run Lighthouse on those four pages. `lighthouserc.json` holds the budgets and the header that
   makes Django treat the request as https; the page addresses are passed here because CI's are
   on port 8000:

   ```bash
   npx @lhci/cli@0.15.1 autorun      --collect.url=http://localhost:8090/      --collect.url=http://localhost:8090/appeals/      --collect.url=http://localhost:8090/appeals/flood-relief/      --collect.url=http://localhost:8090/news/
   ```

   Reports go to `.lighthouseci/reports`.

Without Docker, set the `DJANGO_*` variables of the `lighthouse` job in `.github/workflows/ci.yml`,
run `migrate`, `seed_demo` and `collectstatic`, and start gunicorn on port 8000 (Linux and macOS
only); then run `npx @lhci/cli@0.15.1 autorun` with no flags.

Set `CHROME_PATH` if Chrome isn't found; Microsoft Edge works too.

Lighthouse emulates a phone at 412px and pixel density 1.75, so measure image savings this way,
not in a desktop browser at density 1, which picks smaller files.
