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

Use the issue forms. Choose its tier (`reviews.md`, "Tiers") and label it `tier: light` or
`tier: high risk` (none for standard). Split work bigger than one day's pull request into
sub-issues now (API calls in the board memory). Then add a label for each review the tier and
`reviews.md` call for (`gh issue edit <n> --add-label "needs: design review"`), and say in one
line each which labels you added and why.

## Starting an issue

`gh issue view <n> --json labels`. If any `needs:` label is on it, run that review before
branching, with the command `reviews.md` names. If the skill isn't installed, stop and tell the
user to install gstack (`reviews.md#tools`); never skip the review.

Then branch with `gh issue develop <n> --name <type>/<n>-<slug> --base main --checkout`, always
with `--name` (the branch rule is in `docs/contributing/index.md`, step 2).

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
3. Suggest `/clear` before the next review or building: one review per session, and the comment
   carries the decisions.

## Opening a pull request

Straight after opening it, check each of these (`docs/contributing/index.md`, step 7); CI checks
only the first:

- [ ] A `changelog.d/<slug>.<group>.md` file, or the `no changelog` label.
- [ ] A milestone: the `Milestone` workflow copies the closing issue's; set it by hand if not.
- [ ] Its issue's board card is in *In review*.
- [ ] Each docs page the change describes is updated.
- [ ] The onboarding pack (`onboarding/`), if what a charity sends or decides has changed.

Then whatever `CLAUDE.local.md` lists for this maintainer's own files, if there is one.

The `Reviews` workflow adds `needs: code review`, `needs: security review` for a high-risk
issue, and `needs: qa` for templates, CSS or JavaScript unless every closed issue is light. Then, in the order
`reviews.md` gives:

Before running a review asked for by name, check `gh pr view <n> --json labels` and the existing
review comments. If its label is gone, or an earlier review it depends on is still owed, say so
and ask before running it.

1. **Security:** fix open findings test-first, comment the result on the pull request, then
   remove the label.
2. **Code review:** Claude Code's `/code-review` (`medium` for `tier: light`), not gstack's `/review`. Fix findings test-first,
   not with `--fix`, comment the result on the pull request, then remove the label.
3. **QA:** `/qa-only`, never `/qa` or `/design-review`, which commit their own fixes, several per
   commit. Fix each bug it reports test-first, one per commit, putting back any earlier label
   whose ground the fix changes. **The user removes `needs: qa`** after the pull request's "Check before merging".

## When a milestone's last issue closes

Suggest cutting the release (`docs/contributing/releases.md`), including the release reviews
under "At each release" in `reviews.md`. With `/canary` on the live site, decline its rollback
option: deploys go by tag.
