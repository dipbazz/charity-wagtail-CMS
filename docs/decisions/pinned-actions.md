# Workflow actions pinned to commits

**Status:** in use (since #48, done in #69)

## Context

A GitHub Actions workflow that uses `owner/action@v1` runs whatever code that tag points to on
the day. Tags can be moved, and in 2025 a compromised action (tj-actions/changed-files) did
exactly that, running attackers' code in every workflow that used it.

## Decision

Pin every action to a full commit SHA, with the version in a comment:

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
```

`charity/tests/test_workflows.py` fails on any `uses:` that isn't pinned this way. Dependabot
(`.github/dependabot.yml`) opens one grouped pull request a week when an action has a new
release, updating the SHA and the comment together. The Caddy image in
`deploy/aws/compose.yaml` is pinned to a digest for the same reason, and Dependabot watches it
too.

## Consequences

- CI runs exactly the action code that was reviewed.
- Updates arrive as pull requests to review, rather than silently.
- Adding an action means looking up its commit SHA.
