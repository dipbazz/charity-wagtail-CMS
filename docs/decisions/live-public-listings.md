# Public listings filter `.live().public()`

**Status:** in use (since #47, fixed by #66)

## Context

Wagtail lets editors put a page behind a password, a login or a group restriction. `.live()`
only drops drafts, so a restricted page still showed up in listings that used it: its title,
summary and image appeared on the homepage, the appeals and news listings and the RSS feed, to
anyone.

## Decision

Every public listing filters `.live().public()`: search, the sitemap, the API, the news listings
and feed, the appeals page and the homepage. Tests check each one.

The main menu is the exception. It shows whatever editors tick "Show in menus" for, because an
editor may want a members-only page in the menu, and the page itself still asks for its password
or login.

## Consequences

- `.public()` costs one query per listing (it reads the restrictions), which the query budgets
  allow for.
- Any new listing must do the same; [Security](../topics/security.md) and the
  [page type guide](../how-to/add-page-type.md) say so.
