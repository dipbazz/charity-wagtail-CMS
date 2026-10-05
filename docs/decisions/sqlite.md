# SQLite as the database

**Status:** in use

## Context

The site serves one small charity: a handful of editors, and visitors who mostly read pages.
Every extra service (a database server, its upgrades, its backups, its bill) is something the
charity has to pay for or someone has to look after.

## Decision

Use SQLite, in one file next to the uploads (`DJANGO_DATA_DIR`), with Wagtail's database search
backend.

## Consequences

- Nothing to install or run besides the app: development, CI and the live server all use the
  same database engine.
- A backup is one consistent file, made with SQLite's backup API while the site keeps serving
  (`backup_site`).
- The site runs on **one machine** with a persistent disk. It can't be spread across several
  servers or run on platforms whose disks don't persist; see [One EC2 server](single-server.md).
- Moving to PostgreSQL later means changing `DATABASES`, teaching `backup_site` another engine
  (it refuses anything but SQLite), and choosing a search backend.
