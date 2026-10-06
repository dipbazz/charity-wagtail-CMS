# Management commands

The project's own commands, plus the Wagtail ones the deployment relies on. Run them with
`uv run python manage.py <command>` locally, or
`sudo docker compose exec web python manage.py <command>` on the server.

## `seed_demo` (home)

Builds the fictional demo site: pages, appeals, stories, a form, partners, a testimonial, the
site settings and the announcement banner, plus Nepali translations of the home page, the flood
appeal and its news story, with photos from
`home/management/commands/demo_images/`. Safe to re-run: if appeals already exist it changes
nothing else. It always runs `update_site_url` first, so an existing local database gets working
full URLs. The demo is English-first, so on a site whose main language is Nepali (production's
default) it stops and asks for `DJANGO_LANGUAGE_CODE=en`. See [Demo content](demo-content.md).

## `update_site_url` (core)

Points the default Wagtail `Site` at `settings.SITE_URL`, storing its hostname and port. Safe to
run on every deploy; the Docker image runs it on every start.

`SITE_URL` must be `http(s)://hostname` with an optional port and no path, and `https` only on
port 443, because a Wagtail `Site` has no scheme field: it uses https for port 443 and http for
anything else. Anything else is refused with an error.

## `backup_site <destination>` (core)

Writes `db.sqlite3` (a consistent copy, through SQLite's backup API) and `media.tar.gz` (the
uploads, under `media/`) to a folder. Safe to run while the site serves requests.

- Refuses a destination inside `MEDIA_ROOT`, or every archive would contain the previous
  backups.
- Only knows SQLite.
- Overwrites an earlier backup in the same folder.

`deploy/aws/backup.sh` runs it nightly; see [Deployment](../topics/deployment.md#backups).

## Wagtail commands the deployment uses

| Command | |
|---|---|
| `publish_scheduled` | Publishes and unpublishes pages with a go-live or expiry time. Must run every few minutes (`charity-publish.timer` on the server) |
| `migrate` | Run on every container start |
| `collectstatic` | Run when the Docker image is built |
