# One EC2 server with Docker Compose

**Status:** in use (since #70)

## Context

The site needed a public address with HTTPS, persistent storage for the SQLite database and
uploads, scheduled publishing and off-site backups (#30). The first idea was a platform such as
Fly.io, Railway or Render.

## Decision

Run the existing Docker image on a single Linux server (an AWS EC2 instance), with Docker
Compose and Caddy in front, as set up in `deploy/aws/`:

- Caddy gets and renews the HTTPS certificate itself, so there's no load balancer or certificate
  service to set up.
- The database and uploads live on the server's disk (`/srv/charity/data`), which outlives the
  container.
- systemd timers run `publish_scheduled` every five minutes and a nightly backup to S3.
- The server's IAM role can write backups but not delete them, so a compromised server can't
  wipe them.

## Consequences

- One server fits [SQLite](sqlite.md): one machine, one disk.
- The setup is portable: the site is one Docker image plus a data folder, so it can move to any
  host with Docker.
- Deploying is a manual step on the server ([Deploy a change](../how-to/deploy-a-change.md))
  until #76 deploys from GitHub.
- A deploy restarts the web container, with a few seconds of downtime.
- The server's operating system, Docker and disk space are ours to look after.
