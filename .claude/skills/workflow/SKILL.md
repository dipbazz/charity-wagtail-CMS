---
name: workflow
description: How this project runs its reviews with gstack and Claude Code, label by label. Use when filing an issue, starting work on an issue, opening a pull request, finishing a review, or when the last issue of a milestone closes; and whenever asked which issues or pull requests need a review.
---

# Workflow: reviews and their labels

`docs/contributing/reviews.md` says **which** reviews an issue or pull request needs and when;
read it for the criteria. This skill says **how** to run each one here.

## Find what's waiting

Never scan every issue to answer "what needs a review?". Ask for the label:

```bash
gh issue list -l "needs: design review" --json number,title,milestone
gh pr list -l "needs: code review" --json number,title
```

## Filing an issue

Use the issue forms. Then add a label for each review the issue needs, by the criteria in
`reviews.md`: `gh issue edit <n> --add-label "needs: design review"`. Say which labels you
added and why, in one line each.

## Starting an issue

`gh issue view <n> --json labels`. If any `needs:` label is on it, run that review before
branching: product first, then design, then eng. If the skill isn't installed, stop and tell the
user to install gstack (`reviews.md#tools`); never skip the review.

| Label | Run | Here |
|---|---|---|
| `needs: product review` | `/plan-ceo-review` | Hold-scope or reduction mode, not expansion. `/office-hours` first only for a raw idea. |
| `needs: design review` | `/plan-design-review` | The design system is the tokens in `charity.css` plus the `mobile-first` skill and `docs/site/standard.md`; there's no DESIGN.md. Skip AI image mockups. |
| `needs: eng review` | `/plan-eng-review` | Its test plan feeds `/qa-only` later. |
| `needs: investigation` | `/investigate` | It writes the fix and test together: commit the test that fails first, then the fix, per bug. |

For every gstack review: decline its copy into `docs/designs/` and its TODOS.md entries (work
that's deferred becomes a GitHub issue), and keep the full report in `~/.gstack`.

## Finishing a review

1. Post the decisions on the issue, in the format in `reviews.md` ("When a review is done").
2. Remove the label.
3. Suggest `/clear` before building: the comment carries the decisions.

## Opening a pull request

Add `needs: code review` to every pull request, `needs: qa` when templates, CSS or JavaScript
changed, and `needs: security review` when it touches forms, uploads, payments, permissions,
settings or dependencies, or closes a `security` issue. The `Reviews` check stays red until
they're gone.

Run them in this order, since an edit after a review makes it out of date:

1. `needs: security review`: `/cso --diff --base main`. Fix open findings test-first, then remove
   the label.
2. `needs: qa`: `/qa-only` (never `/qa` or `/design-review`: they commit their own fixes, several
   per commit). Fix each bug it reports test-first, one per commit. Write the user's
   `PR-<n>-checks.local.md`. **The user removes this label** after ticking the checks.
3. `needs: code review`: Claude Code's `/code-review high <pr>`, last. Fix findings test-first
   (not `--fix`), push, and re-run it if the fixes were more than trivial. Remove the label when
   nothing is left.

## When a milestone's last issue closes

Suggest cutting the release (`docs/contributing/releases.md`), including the release reviews in
`reviews.md` ("At each release"): `/cso`, `/test-audit`, `/deslop-shared-libs`, and `/canary`
on the live site after deploying (decline its rollback option; deploys go by tag).
