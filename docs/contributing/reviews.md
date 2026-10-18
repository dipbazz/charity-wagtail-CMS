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

## Which reviews an issue or pull request needs

When an issue is filed, or a pull request opened, give it a label for each review it needs. The
`Reviews` workflow adds `needs: code review` to every new pull request, and `needs: qa` when it
changes templates, CSS or JavaScript; add `needs: security review` by hand.

| Label | Decides | Needed when | Run with |
|---|---|---|---|
| `needs: product review` | Whether it's worth building, and how much of it | A new epic or feature track, scope that isn't clear, or a change to what charities must send or decide | `/plan-ceo-review` (hold or reduce scope), after `/office-hours` for a raw idea |
| `needs: design review` | What people see and do: layout, states, wording, accessibility | It adds or changes what visitors or editors see: a page type, block, template, menu, form or admin screen | `/plan-design-review` |
| `needs: eng review` | Data, architecture, edge cases and the tests to write | Models or migrations, payments, personal data, permissions, a new dependency, or work spanning more than one pull request | `/plan-eng-review` |
| `needs: investigation` | A bug's cause, before anyone fixes it | A bug whose cause isn't known | `/investigate` |
| `needs: security review` | Whether the change opens a hole | A pull request touching forms, uploads, payments, permissions, settings or dependencies, or closing an issue labelled `security` | `/cso --diff --base main` |
| `needs: code review` | Bugs that tests and CI don't catch | Every pull request | `/code-review high <pull request number>` |
| `needs: qa` | Whether it works and looks right in the browser | A pull request that changes templates, CSS or JavaScript | `/qa-only`, then the person checks the pages its description lists |

The first four go on issues and are done before coding; the last three go on pull requests and
are done before merging. Each builds on the one before, so they run in the table's order:
product, design, then engineering on an issue; security, code review, then QA on a pull request,
with the person's QA check last.

## When a review is done

1. **Post its decisions as one comment on the issue,** headed `## <Kind> review decisions
   (<date>)`. Say that they win where they differ from the issue's text, then what changes,
   what's newly needed, the order of work, and any issues filed. The next person to pick up the
   issue starts from that comment, so nothing decided lives only in a local report.
2. **Remove the label:** `gh issue edit <n> --remove-label "needs: design review"`.

A pull request's labels come off when the review finds nothing left to fix: `needs: code review`
and `needs: security review` once their findings are fixed, and `needs: qa` by the person who
checked the pages. Fixing a review's own findings doesn't need that review again. Any other
change pushed after a review, such as a fix QA asked for, puts back the label of each earlier
review whose ground it changes.

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
