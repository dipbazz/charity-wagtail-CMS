---
name: workflow
description: How this project runs its reviews with gstack and Claude Code, label by label. Use when filing an issue, starting work on an issue, opening a pull request, finishing a review, or when the last issue of a milestone closes; and whenever asked which issues or pull requests need a review.
---

# Workflow: reviews and their labels

`docs/contributing/reviews.md` is the source for **which** review an issue or pull request needs,
the command that runs it, the order, and when a label comes off. Read it first. This skill adds
only what's particular to running them here with Claude Code.

## Find what's waiting

Never scan every issue to answer "what needs a review?". Ask for the label, with the commands
under "Find what's waiting" in `reviews.md`, and list titles only.

## Filing an issue

Use the issue forms. Then add a label for each review the issue needs, by the criteria in
`reviews.md` (`gh issue edit <n> --add-label "needs: design review"`), and say in one line each
which labels you added and why.

## Starting an issue

`gh issue view <n> --json labels`. If any `needs:` label is on it, run that review before
branching, with the command `reviews.md` names. If the skill isn't installed, stop and tell the
user to install gstack (`reviews.md#tools`); never skip the review.

| Review | Particular to this project |
|---|---|
| product | Hold-scope or reduction mode, never expansion. |
| design | The design system is the tokens in `charity.css`, the `mobile-first` skill and `docs/site/standard.md`; there's no DESIGN.md. Skip AI image mockups. |
| eng | Its test plan feeds `/qa-only` later. |
| investigation | It writes the fix and the test together: commit them as one bug per commit, having seen the test fail without the fix. |

For every gstack review: decline its copy into `docs/designs/` and its TODOS.md entries (deferred
work becomes a GitHub issue), and keep the full report in `~/.gstack`.

## Finishing a review

1. Post the result as one comment where the label is: the issue for an issue's review, the pull
   request for a pull request's, in the format in `reviews.md` ("When a review is done").
2. Remove the label from that same place. If an open pull request closes the issue, re-run its
   `Reviews` check (`gh run rerun` on its latest `Reviews` run), since removing an issue's label
   doesn't.
3. After an issue's review, suggest `/clear` before building: the comment carries the decisions.

## Opening a pull request

The `Reviews` workflow adds `needs: code review`, and `needs: qa` for templates, CSS or
JavaScript. Add `needs: security review` yourself when `reviews.md` says so. Then, in the order
`reviews.md` gives:

1. **Security:** fix open findings test-first, comment the result on the pull request, then
   remove the label.
2. **Code review:** Claude Code's `/code-review`, not gstack's `/review`. Fix findings test-first,
   not with `--fix`, comment the result on the pull request, then remove the label.
3. **QA:** `/qa-only`, never `/qa` or `/design-review`, which commit their own fixes, several per
   commit. Fix each bug it reports test-first, one per commit, putting back any earlier label
   whose ground the fix changes. Write the user's `PR-<n>-checks.local.md`. **The user removes
   `needs: qa`** after ticking the checks.

## When a milestone's last issue closes

Suggest cutting the release (`docs/contributing/releases.md`), including the release reviews
under "At each release" in `reviews.md`. With `/canary` on the live site, decline its rollback
option: deploys go by tag.
