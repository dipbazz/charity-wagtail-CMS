# Contributing

How a change gets from an issue to `main`, and the rules every change follows.

```{toctree}
:maxdepth: 1

reviews
testing
performance
security
extending
demo-content
releases
onboarding
writing-docs
```

## Principles

This is one product that many charities run, in Nepal and the UK, and a supporter should find
everything in the same place on each charity's site. So every change is judged by what it does
for all of them, not for the one page or charity that prompted it. When two principles pull
against each other, the earlier one wins.

1. **Every change works for every charity.** A request from one charity becomes a feature or a
   setting that any charity can use, or it waits. No charity gets its own template, CSS, code or
   branch: charities differ only in their content and their settings. A proposal says how it
   works for the second and the fiftieth charity: what they set, what has to migrate, what's
   tested.
2. **Fix the cause, once.** Find where the problem comes from (a token, a component, a template
   tag, a query helper) and fix it there, with a test that catches the same bug anywhere it can
   happen, not only where it was seen. A fix for one page that leaves the same bug on others
   isn't finished.
3. **Standards first, then modern.** Follow the published standard before a fashion: WCAG 2.2 AA,
   the web's conventions (the logo top left goes home, Donate sits top right, the menu and search
   are where people expect them), [the charity site standard](../site/standard.md), and the law on
   giving and personal data in Nepal and the UK. Modern styling is welcome inside those rules,
   through the design tokens and shared components ([Look and feel](../site/look-and-feel.md)),
   never by breaking one. A design proposal names the standard it follows.
4. **Consistent, not uniform** (from the
   [GOV.UK design principles](https://www.gov.uk/guidance/government-design-principles)). Every
   charity's site has the same pages, menu and footer in the same places, so a supporter who has
   used one knows their way around the next. Each looks like its own charity through its brand
   settings: colours, logo, font style, photos and words.
5. **Nothing by hand for each charity.** Every charity adds server memory, editor time, support and
   an upgrade step. Prefer what costs nothing more per charity: defaults that work untouched,
   settings over manual setup, automation over runbooks. A manual step each charity needs when
   it's set up, deployed or upgraded is a bug to automate.

Before proposing a fix, feature or design, answer these in the proposal itself:

- Who else has this problem: every charity, every page of this kind, both languages?
- Where is the shared cause, and what fixes it there?
- Which standard applies, and does the proposal follow it?
- What does it cost each charity, now and at every upgrade?
- Which test stops it coming back?

**No new toolchain without agreement first.** A new language, file type or runtime in the repo or
CI (JavaScript tests run by Node, say) is one more thing every maintainer has to understand and
keep working. Propose it on the issue before building it, with what it catches, what it costs,
and the option of no new tooling ("pytest can't catch this", said in the pull request); never
bundle it into a fix.

## The workflow

1. **Start from an issue** on the [project board](releases.md#the-project-board) with no
   `needs:` label left: its [reviews](reviews.md) come first. Move it to *In progress*. An issue
   is about one day's pull request; a broader one is split into sub-issues, one pull request
   each, when it's filed or at its eng review ([Tiers](reviews.md#tiers-how-much-review-a-change-gets)).
2. **Branch from `main`:** one feature or fix per branch, named `<type>/<issue-number>-<slug>`,
   such as `feat/142-share-gift`, with a [commit type](#commits) and a slug of lowercase letters
   and digits joined by single hyphens. The number shows which issue the branch is for. `gh issue develop 142 --name feat/142-share-gift
   --base main --checkout` makes the branch and links it to the issue; always give `--name`, or
   GitHub names it from the issue's title with no type. `main`, `chore/release-X.Y.Z` and
   `patch/X.Y.x` are named by [Releases](releases.md). pre-commit refuses a commit on any other
   name (`.pre-commit-config.yaml`); `SKIP=branch-name git commit` skips just that check, for a
   branch a tool named.
3. **Work test-first** ([Testing](testing.md)): a failing test, then the code that makes it pass.
4. **Update the docs** in the same pull request when it changes something a docs page describes
   ([Writing docs](writing-docs.md)).
5. **Add a changelog file** in `changelog.d/`, written for the person the
   change affects, or label the pull request `no changelog` if nobody would notice it
   ([Releases](releases.md#the-changelog)).
6. **Run the checks for what you touched** before pushing: its tests
   (`uv run pytest path/to/tests`), and `uv run python manage.py makemigrations --check --dry-run`
   if models changed. ruff runs on every commit through pre-commit (`uv run pre-commit install`,
   once per clone), and CI runs the whole suite on every push.
7. **Open a pull request** against `main`. It gets the milestone of the issue it closes
   automatically (the `Milestone` workflow), unless you set one yourself. Its description is short
   and follows the template: what changed, what to check in the browser before merging, and
   anything the reviewer must act on; the why goes in the commit messages. Pull requests aren't
   stacked on each other. Straight after opening it, check its changelog file (or the
   `no changelog` label), that it has a milestone, its issue's board card in *In review*, the
   docs pages it describes and, if what a charity sends or decides has changed, the onboarding
   pack.
8. **QA:** CI checks every page layout at six widths; the pull request lists what a person must
   check in the browser ([QA](testing.md#qa)).
9. **Reviews:** the pull request gets `needs: code review`, and `needs: qa` or
   `needs: security review` when it needs them. Each comes off when its review is done
   ([Reviews](reviews.md)).
10. **The maintainer merges** once CI is green and no `needs:` label is left.

## Commits

`type(scope): description`: lowercase, imperative, 72 characters or fewer, no trailing period.
pre-commit refuses a longer subject (`.pre-commit-config.yaml`).

- Types: `feat`, `fix`, `perf`, `refactor`, `test`, `chore`, `docs`, `style`, `ci`.
- One logical change per commit; never bundle unrelated changes.
- Before each commit, check the change belongs to this branch's issue; if it doesn't, branch
  from `main` for it.
- The body explains *why*; the diff shows what.
- Include `Closes #N` when the commit fixes an issue.
- A breaking change gets a `!`, e.g. `feat(api)!: change response shape`.

The pull request title follows the same format.

## Code style

- ruff, with a line length of 100, enforces formatting and lint rules (`pyproject.toml`).
- Match the surrounding code: its naming, comment density and idiom.
- Comments explain why, especially where the code works around something (a Wagtail
  limitation, a browser quirk, a past bug with its issue number).
- `logging.getLogger(__name__)` in app code.

## Design rules

- **Mobile first** for every page, block and component: [Look and feel](../site/look-and-feel.md).
- **Small visual choices are cheap to change:** for a detail such as a switcher's style, give one
  recommendation with its reason and ship it; a charity's request can change it later. Options
  and prototypes are for layout that's expensive to change.
- **Fast from the start:** query counts, image weight and behaviour at 320–1440px are measured
  for every new feature: [Performance](performance.md).
- **Accessible:** [Look and feel](../site/look-and-feel.md#accessibility).
- **Secure:** read [Security](security.md) before touching listings, documents,
  images, workflows or deployment.
- **Demo data is fictional,** and every address in it is a reserved domain
  ([Demo content](demo-content.md#the-charity-is-fictional)).
