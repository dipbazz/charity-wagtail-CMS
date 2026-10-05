# Issues and the project board

## Issues

Open issues with the forms in `.github/ISSUE_TEMPLATE/`: bug, feature or docs. Write them from
the point of view of the person using the site or the admin: what they're trying to do and what
gets in their way, not the code change.

Labels:

| Label | |
|---|---|
| `P1`, `P2`, `P3` | Priority: P1 is urgent, P3 can wait |
| `bug`, `enhancement`, `documentation` | Kind of change |
| `accessibility`, `security` | Areas that need extra care in review |
| `epic` | A feature track (below) |

## Epics

Each feature track is an issue labelled `epic` and titled `Epic: …`, with the work as its
sub-issues. It says the goal, why it matters, how the work is split and when it's done.
Attach every new issue to an epic.

Docs for a new feature aren't separate sub-issues: the feature's pull request updates its own
docs page, under that feature's epic.

## The project board

The [project board](https://github.com/users/dipbazz/projects/1) plans the work. New and
updated issues in the repo are added to it automatically.

| Field | |
|---|---|
| Status | Backlog → Ready → In progress → In review → Done |
| Iteration | Two-week sprints |
| Priority | Mirrors the `P1`–`P3` labels |

- Move an issue to *In progress* when you start it, and to *In review* when its pull request is
  open.
- An epic is *In progress* while any of its sub-issues is being worked on or done, and *Done*
  when all of them are closed.
- Merged pull requests and closed issues go to *Done*.
