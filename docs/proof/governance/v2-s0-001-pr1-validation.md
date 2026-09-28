# V2-S0-001-PR1 validation

Date: 2026-09-28

What this change checked before it was committed, and how. What it decided is in
[the decision that opens a second version](../../governance/v2-authorization.md); this
page is about the checks run over the repository after that page was written.

The change executed nothing against a host: no cluster, runtime, or model was
contacted, nothing was provisioned, and nothing was published. It reads the pack
`v1.0.0` was cut over and adds no evidence to it.

## Eligibility, checked before anything was written

- **The earlier decision is merged.** `main` was at `7d0167d`, the merge of
  `V1-S5-009-PR1`, which carries the defer decision this change supersedes.
- **The release.** The tag `v1.0.0` resolves to `718ad2e`.
- **The gate and the pack.** `python -m tools.evidence_index --gate` exited 0: `FROZEN`
  for `V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack
  `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…`.
- **What the pack covers.** Every file a record cites, the register, and its five
  ledgers. None of the files this change touches is among them, so all three pairs of
  digests could stay where they were, and did.
- **What the earlier record allows.** It says a review "either confirms this record with
  a dated note or replaces it with a new decision; it does not edit the reasoning above
  in place". This change is a new decision, and the earlier page gains only a dated
  note at its top. None of its five review triggers had fired, and the new page says so.

## What changed

- **The decision.** `docs/governance/v2-authorization.md` and the data it is held to,
  `v2-authorization.v1alpha1.json`: the earlier record, with hashes of its data and of
  its page without the note; its five triggers, none fired; the thesis and the five
  earlier findings it starts from; one moved placement; the six earlier gates and three
  of the `revise` option's prerequisites, each with a treatment; eight things the
  version does not take on; three reasons to look at the decision again.
- **The earlier decision.** Its page gains a dated note under its title, three added
  lines. Its data and its test are unchanged.
- **Current surfaces.** The README's roadmap bullet and the governance table's
  "Next version" row said the version was deferred; both now say it is open, link both
  records, and keep the three unmet gates visible. The proof records index lists this
  record. The changelog gains one entry under the unreleased section.
- **Tests.** `tests/testing/test_v2_authorization.py` is new. The test inventory lists
  it, which makes forty-seven documentation modules and forty-nine that defend no claim;
  both counted sentences and the documentation layer's narrative sentence are extended.
- **A pre-existing test defect.** `tests/testing/test_release.py`'s check that every
  story merged into the release is listed read the merges of `HEAD`, so the first story
  merged after the release, `V1-S5-009-PR1`'s pull request, failed it on every full
  clone of `main` since that merge. Continuous integration skips the check, because it
  clones without history, so the failure was never reported. It now reads the merges the
  released commit contains, which the release data already records. No release file is
  changed.

## Traceability: what the story asks, and where the decision answers it

| The story asks that | Answered in |
|---|---|
| A governed decision explicitly revisits, revises, or supersedes the defer outcome | The page's status line and "The decision": it supersedes the outcome and edits none of the earlier record; the test holds the earlier data to its hash and the earlier page to its hash without the note |
| The decision names caller-visible reliability under failure or change as the thesis | "The thesis", which also says the release-change half rests on no V1 result |
| Contract-to-deployment rendering is moved into V2, and the reason is documented | "Contract-to-deployment rendering moves into V2", with three reasons and what does not change |
| Still-unmet gates stay visible and are classified as targets, deferred items, or blockers | "The earlier record's entry gates, and how each is treated": six gates and three prerequisites; the test refuses a gate unmet then and called met now |
| No V1 evidence, tag, release, or historical decision is rewritten | No file in the pack changed, and the gate printed the same three pairs of digests before and after; the earlier record's data is byte for byte as merged; no release file changed; the one edit to a V1 test is to a check's history range, not to what it compares |

The traceability to the story's acceptance criteria was checked by the author and is a
reading; the test checks the decision against the earlier record, not against the
story.

## What the checks caught before the first commit

- **Formatting.** `ruff format --check` refused the new module until it was reformatted.
- **The test's own parser.** Its table reader dropped every table, because it tested
  for a table row before skipping the separator line; and a phrase check missed a
  sentence wrapped inside a blockquote. Both were fixed before any result below.
- **Wording in the test that pointed at unpublished planning.** The first list of
  forbidden phrases named words about who the work is for and where it might run. A
  list of words to refuse says what someone might have written, so it is cut to the
  overclaim and appeal words the earlier record's test refuses, and review carries the
  rest.
- **Mutations.** Twenty-six deliberate corruptions of the data, the page, the earlier
  record, the README, and the governance table were applied one at a time by a script
  kept outside the repository, and the module was run after each with `-x`: the earlier
  record's data or reasoning edited, the note moved, an unmet gate called met, an earlier
  gate state restated, a treatment outside the vocabulary, a gate treatment differing
  between page and data, a duplicated gate row, a wrong unmet count, a misquoted
  prerequisite, a blocker naming nothing, an altered quotation, a wrong digest, a trigger
  said fired against the dates or the register, a trigger dropped, a claim moved, a
  placement moved from somewhere it was not, an unknown finding, a forbidden phrase, a
  stray measurement, a broken fragment, a dropped boundary link, a decision dated after
  the review date, and the README or the governance row left saying deferred. Each was
  refused, and the files were restored after each. With `-x` only the first failing test
  is reported: for twenty-three it is the check written for that corruption; for three —
  the treatment outside the vocabulary, the misquoted prerequisite, and the decision
  dated after the review — it is an agreement check that fails first, because each
  corruption also breaks agreement with the page or the earlier record's note. The script is
  not committed, so this paragraph is its only record; the checks it exercised are the
  module's.

## Commands

From Git Bash at the repository root, with every file of this change staged so that the
suites that read `git ls-files` see it. `uv` ran with `--offline` against its cache; the
lock is unchanged.

```text
uv run --locked --offline ruff format --check .
uv run --locked --offline ruff check .
uv run --locked --offline python -m mypy
uv run --locked --offline python -m pytest tests/testing/test_v2_authorization.py tests/testing/test_v2_investment_decision.py tests/testing/test_test_inventory.py -q -rs
uv run --locked --offline python -m pytest tests/testing tests/security tests/architecture -q
uv run --locked --offline python -m tools.proof_dashboard --check
uv run --locked --offline python -m tools.evidence_index --check
uv run --locked --offline python -m tools.evidence_index --gate
uv run --locked --offline python -m pytest -q
git diff --cached --check
```

## Results

On 2026-09-28, on one Windows host, before the first commit:

| Command | Result |
|---|---|
| `ruff format --check .` | 528 files already formatted, after one reformat of the new module |
| `ruff check .` | All checks passed |
| `python -m mypy` | No issues in 281 source files |
| The decision's, the earlier decision's, the inventory's, and the release's modules, `-rs` | 1165 passed, none skipped |
| `pytest tests/testing tests/security tests/architecture -q` | 10776 passed, 6 skipped, in 12 min 53 s |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `python -m tools.evidence_index --gate` | Exit 0: `FROZEN V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…`: all unchanged from `main` |
| `pytest -q`, the default lane | 15490 passed, 33 skipped, 14 deselected, in 19 min 43 s |
| `git diff --cached --check` | Clean |

The first run of the three documentation suites, before the release module's history
range was corrected, failed that one check and passed everything else. The six skips in
the documentation suites are this host's: two symbolic-link tests the host does not
permit, one signal Windows does not deliver, and three checks against the pinned
collector image, which is not present on this host. The last three are why the default
lane skipped 33 here where `V1-S5-009-PR1`'s run skipped 30; none reads a file this
change touches. The default lane ran before the last two edits to the new module's list
of phrases and the page's sentence describing it; the decision's module and the quick
checks above ran after them.

The Helm and Terraform gates were not run: nothing under `charts/` or `infra/` changed.
No cluster, runtime, or model lane was run, because nothing that executes changed. The
hosted `checks` workflow runs on the pull request and is not quoted here.

## Privacy and publicability

The staged diff's added lines were searched for a drive-letter or home-directory path, a
scratch directory, an e-mail address, a credential-shaped string, the name of any
private planning document, a later story's identifier, and the names of tools,
providers, or prices the change does not need. None is present. The decision describes
where work stops by the boundary rules this repository already publishes, and names no
other project. No model artifact, generated render, built distribution, or machine state
is added.
