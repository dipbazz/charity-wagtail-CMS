# Run Lighthouse locally

Reproduce CI's page weight and layout shift checks ([Performance](../topics/performance.md)) on
your own computer, for example to measure an image change before pushing it.

1. Serve the demo site with production settings, as the `lighthouse` job in
   `.github/workflows/ci.yml` does: set the same `DJANGO_*` variables (with a throwaway
   `DJANGO_DATA_DIR`), run `migrate`, `seed_demo` and `collectstatic`, then start gunicorn on
   `127.0.0.1:8000`.
2. Visit each page once, so image renditions exist before anything is measured.
3. Run `npx @lhci/cli@0.15.1 autorun`. It reads the pages and budgets from `lighthouserc.json`
   and writes reports to `.lighthouseci/reports`.

Set `CHROME_PATH` if Chrome isn't found; Microsoft Edge works too.

Lighthouse emulates a phone at 412px and pixel density 1.75, so measure image savings this way,
not in a desktop browser at density 1, which picks smaller files.
