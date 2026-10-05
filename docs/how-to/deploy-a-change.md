# Deploy a change

How a merged change reaches the live server set up from `deploy/aws/`
([Deployment](../topics/deployment.md) describes that setup). Today it's done by hand on the
server; issue #76 plans deploying from GitHub, with a backup and an approval each time.

## Before you start

- The change is merged to `main` and CI passed on it.
- If the change has a migration that alters existing data, take a backup first:
  `sudo systemctl start charity-backup.service`, then check it with
  `journalctl -u charity-backup.service -n 20 --no-pager`.

## Deploy

On the server:

```bash
cd /srv/charity/app && sudo git pull
cd deploy/aws && sudo docker compose build && sudo docker compose up -d
sudo docker image prune -f       # remove the previous image, so the disk doesn't fill up
```

`up -d` replaces the web container, with a few seconds of downtime. On start it runs any new
migrations and `update_site_url`, then starts gunicorn.

Building on a small instance takes several minutes and needs swap, or it can stop with "Killed"
(out of memory).

## Check it

```bash
sudo docker compose ps                    # both containers up?
sudo docker compose logs --tail 100 web   # migrations, gunicorn start, any errors
```

Then open the site and the pages the change touched. If something is wrong, `git checkout` the
previous commit and build again; if a migration changed data, [restore the
backup](restore-a-backup.md).

## Changes to the timers or Compose file

- A changed file in `deploy/aws/systemd/` has to be copied to `/etc/systemd/system/` again,
  followed by `sudo systemctl daemon-reload`.
- A new setting in `.env` (see `env.example`) has to be added to the server's `.env` by hand
  before `up -d`; Compose stops with a message if a required one is missing.
