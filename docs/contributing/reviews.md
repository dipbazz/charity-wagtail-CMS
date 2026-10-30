# Reviews

Some decisions are cheap before the code is written and expensive after it: what a page shows,
how the data is shaped, whether a feature is worth building at all. Others need a second look
before a change reaches every charity's site. Each of these is a review, and a `needs: …` label
says which reviews an issue or pull request still owes.

**An issue with a `needs:` label isn't started, and a pull request with one isn't merged.** The
`Reviews` workflow (`.github/workflows/reviews.yml`) fails a pull request while it, or an issue
it closes, still carries one.

## Tools

The reviews are run with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), its
built-in `/code-review` skill, and the [gstack](https://github.com/garrytan/gstack) skills. To
use them, install Claude Code, then gstack by following
[gstack's install steps](https://github.com/garrytan/gstack#install--about-30-seconds) (it needs
Git and Bun, and Node.js on Windows). gstack's "team mode" isn't used: it would commit gstack into
this repo.

The tools make reviews quicker but aren't required. Without them, do the same review by hand
against the questions below and post the result the same way: the labels and the workflow work
the same either way.

## Tiers: how much review a change gets

Most changes are small, and three reviews on a typo cost more than they catch. Each issue gets a
tier once, when it's filed (an idea, when its product review decides to build it,
[From idea to issue](releases.md#from-idea-to-issue)) and before any pull request for it is
opened, and the tier decides its
reviews. Mark the issue (never the pull request) with a label: `tier: light` or `tier: high risk`;
no label means standard. **High risk wins:** a change to high-risk code is high risk however
small, so a one-line fix in the payments code isn't light.

| Tier | When | Reviews |
|---|---|---|
| Light | Docs, wording, CI or tooling, a small CSS fix, a bug fix with its test | Pull request: `/code-review medium`. No `/qa-only`: CI's layout checks cover six widths, and the person checks the pages the pull request lists |
| Standard | A normal feature or visible change | Issue: design review if it changes what people see. Pull request: `/code-review high`, then `/qa-only` if it changes what people see |
| High risk | Payments, personal data, permissions, uploads, a new dependency, or a `security` issue | Issue: eng review, and product review if the scope isn't clear. Pull request: security review, code review, then QA |

The `Reviews` workflow reads the tier from the issues a pull request closes. It adds
`needs: security review` when any of them is high risk, and leaves out `needs: qa` only when every
one is light. If a tier changes after the pull request is opened, re-run its `Reviews` check.

**One pull request, about one day.** An issue too broad for that becomes a parent issue with
sub-issues, each one pull request (for example the model, then the view, then the template). Split
it when it's filed, or at its eng review.

**Re-review only for new risk.** A fix pushed after a review puts back only the label of an earlier
review whose ground it changes, and only when it touches high-risk code: a CSS fix from QA never
puts back the security review.

## Which reviews an issue or pull request needs

When an issue is filed, or a pull request opened, give it a label for each review its tier and
the table below call for. The tier table above decides which issues are high risk; the rows
below don't repeat its list. The `Reviews` workflow adds `needs: code review` to every new pull
request, `needs: security review` to a high-risk one, and `needs: qa` when it changes templates,
CSS or JavaScript and isn't light.

| Label | Decides | Needed when | Run with |
|---|---|---|---|
| `needs: product review` | Whether it's worth building, and how much of it | Scope that isn't clear, a new epic or feature track, or a change to what charities must send or decide | `/plan-ceo-review` (hold or reduce scope), after `/office-hours` for a raw idea ([From idea to issue](releases.md#from-idea-to-issue)) |
| `needs: design review` | What people see and do: layout, states, wording, accessibility | It adds or changes what visitors or editors see: a page type, block, template, menu, form or admin screen | `/plan-design-review` |
| `needs: eng review` | Data, architecture, edge cases and the tests to write | A high-risk issue, or work at any tier spanning more than one pull request (to split it) | `/plan-eng-review` |
| `needs: investigation` | A bug's cause, before anyone fixes it | A bug whose cause isn't known | `/investigate` |
| `needs: security review` | Whether the change opens a hole | A high-risk pull request. The release's whole-code `/cso` covers the rest | `/cso --diff --base main` |
| `needs: code review` | Bugs that tests and CI don't catch | Every pull request | `/code-review high <pull request number>` (`medium` for a light one) |
| `needs: qa` | Whether it works and looks right in the browser | A standard or high-risk pull request that changes templates, CSS or JavaScript | `/qa-only`, then the person checks the pages its description lists |

The first four go on issues and are done before coding; the last three go on pull requests and
are done before merging. Each builds on the one before, so they run in the table's order:
product, design, then engineering on an issue; security, code review, then QA on a pull request,
with the person's QA check last.

## When a review is done

**The result goes where the label is,** as one comment, so nothing lives only in a local report.
Then the label comes off the same place.

| The label was on | Comment there | Label comes off |
|---|---|---|
| **An issue** (product, design, eng, investigation) | `## <Kind> review decisions (<date>)`: say that they win where they differ from the issue's text, then what changes, what's newly needed, the order of work, and any issues filed. The person who builds it starts from this comment. | Once the comment is posted: `gh issue edit <n> --remove-label "needs: design review"` |
| **A pull request** (security, code review, QA) | `## <Kind> review (<date>)`: what was found, and for each finding the commit that fixed it or why it stays. If nothing was found, say so. | Once every finding is fixed or answered: `gh pr edit <n> --remove-label "needs: code review"`. The person who checked the pages removes `needs: qa`. |

Fixing a review's own findings doesn't need that review again. Any other change pushed after a
review, such as a fix QA asked for, puts back the label of an earlier review only for new risk
(see [Tiers](#tiers-how-much-review-a-change-gets)).

Run one review per session: it ends with its comment, which hands over to the next, so a fresh
session starts from that comment rather than a long history.

Removing a label from an issue doesn't re-run the check on its open pull request. Re-run the
`Reviews` check from the pull request's Checks tab, or push.

## Find what's waiting

```bash
gh issue list -l "needs: design review" --json number,title,milestone
gh pr list -l "needs: code review"
```

## At each release

A release adds reviews over the whole code, not one change:

- a security audit of the whole code (`/cso`);
- a sweep for tests that cost more than they protect (`/test-audit`), and for code worth sharing
  between apps (`/deslop-shared-libs`);
- after deploying, a check of the live site against the version before (`/canary`).

What they find becomes issues, labelled like any other ([Cutting a release](releases.md#cutting-a-release)).
