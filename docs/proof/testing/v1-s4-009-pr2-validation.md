# V1-S4-009-PR2 change validation

Date: 2026-09-17

Change: [the generated V1 proof dashboard](../dashboard.md), the generator behind
it under [`tools/proof_dashboard/`](../../../tools/proof_dashboard/),
[the suite that regenerates it and holds it to the register](../../../tests/testing/test_proof_dashboard.py),
the row that suite adds to [the test inventory](../../testing/test-inventory.v1alpha1.json)
and [its document](../../testing/test-inventory.md), the surface the page is
declared to be in
[the claim and evidence register](../../testing/claim-evidence-matrix.v1alpha1.json)
and [its document](../../testing/claim-evidence-matrix.md), the entry point the page
gains in [the README](../../../README.md), the checkout rule it gains in
[`.gitattributes`](../../../.gitattributes), and the pointers added to
[the evidence index](../README.md) and [the testing index](../../testing/README.md).

Classification: **local static evidence.** Evidence class `local-static`. Every
result below was produced on one Windows host by running commands over files in
this repository. No cluster was selected or contacted, no model was loaded, no
runtime was started, no request was served, no Prometheus or Grafana was asked
anything, no container was built or run, and no job was executed on the
continuous-integration service.

**No product behaviour changed.** Nothing under `src/`, `charts/`, `infra/`,
`deploy/`, or `scripts/` is touched. The addition under `tools/` is a document
generator: it reads two paths and writes one, and the only file it may write is
`docs/proof/dashboard.md`.

Claim boundary: the page states no claim of its own. Every status, certification
level, evidence label, provider, environment, evidence link, and limitation on it
is read from the register at render time, and every count on it is computed from
the register's own rows. The page is declared in the register as a surface that
makes no capability claim, for that reason. **No certification level is raised, no
status is promoted, and no new measurement is made by this change.**

**What this record does not establish.** It is not evidence that any statement on
the page is true. It establishes that the page is derived rather than asserted.
Whether a record says what the row citing it says it says is a reading; the
register carries that limitation and the page inherits it whole.

## Environment

| Component | Version |
|---|---|
| Windows | 11 Enterprise 10.0.26200 |
| Shell | GNU bash 5.2.26(1)-release (x86_64-pc-msys), Git Bash |
| Python, host | 3.12.6 |
| Python, locked environment | 3.12.12 |
| `uv` | 0.9.16 (a63e5b62e 2025-12-06) |
| `pytest` | 8.4.2 |
| `ruff` | 0.16.4 |
| `mypy` | 2.3.1 (compiled: yes) |
| Git | 2.45.1.windows.1 |
| Branch | `feat/v1-s4-009-proof-dashboard` |
| Base | `main` at `4cb257617a97f0d062af21a5dd311f77dc6aa5f5` |

No Docker engine, Helm, Terraform, `kubectl`, `promtool`, or Grafana was used.
`shellcheck` is not installed on this host and no shell script changed, so it is
recorded as not run rather than as passing.

## What the page holds

| Fact | Value |
|---|---|
| Source of every status and count | `docs/testing/claim-evidence-matrix.v1alpha1.json` |
| Claims in the register | 58 |
| Distinct claims appearing on the page | 51 |
| Capability groups | 11 |
| Claims shown under a capability group | 41 — 34 certified, 6 not claimed, 1 deferred |
| Claims listed under *what V1 does not claim* | 17 — 8 planned, 8 not claimed, 1 deferred |
| Certified claims in no capability group | 7, counted in every total on the page and read in the register |
| Distinct evidence records linked | 41, each resolving from `docs/proof/` |
| Rules applied before the page renders | 11 |
| Page size | 303 lines |

The seven certified claims that no capability group names are counted in the status,
level, label, and provider tables and are not shown as rows. That is stated on the
page in its own limitations rather than left for a reader to discover by subtracting.

Every claim the register does not certify is on the page, and the list is derived
rather than selected: `uncertified_claims` returns every row whose status is not
`certified`, so a claim that stops being certified joins the table without anybody
adding it. That is the one direction a proof page is tempted to be incomplete in.

## Commands, and what they returned

Run from the repository root, in Git Bash.

| Command | Result |
|---|---|
| `python -m tools.proof_dashboard` | `OK       58 claims satisfy 11 dashboard rules` |
| `python -m tools.proof_dashboard --json` | `[]`, exit 0 |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.proof_dashboard --page` | the committed page's bytes exactly, LF and UTF-8 |
| `python -m pytest tests/testing/test_proof_dashboard.py -q` | `118 passed, 7 skipped` |
| `python -m pytest tests/testing/test_claim_evidence_matrix.py -q` | `1795 passed` |
| `python -m pytest tests/testing/test_test_inventory.py -q` | `846 passed` |
| `python -m pytest tests/testing -q` | `3824 passed, 7 skipped` |
| `uv run --locked ruff format --check .` | `452 files already formatted` |
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked python -m mypy` | `Success: no issues found in 254 source files` |
| `uv run --locked python -m pytest -q` | `11664 passed, 37 skipped, 14 deselected in 578.21s`, on the final tree; the same command on the tree as first committed, before the independent review's corrections, read `11656 passed, 37 skipped, 14 deselected in 499.92s` |
| `git diff --check main...HEAD` | no output, exit 0 |
| `git ls-files -z '*.md' \| xargs -0 grep -n '[[:blank:]]$'` | no match |
| `git ls-files -z '*.md' \| xargs -0 grep -n "$(printf '\t')"` | no match |
| the POSIX link check CONTRIBUTING publishes | the same two pre-existing reports `V1-S4-009-PR1` recorded, unchanged by this branch |

The seven skips in the dashboard suite are the seven certified claims no capability
group names: the per-record link check skips them by name rather than passing
silently over them.

## What the rules refuse

Eleven rules are applied to the register before a page is produced, and no mode of
the command reaches the renderer past a finding. Each is driven, in the suite, over a
register or a capability selection corrupted to break it — the practice
`V1-S4-009-PR1` adopted after a review found one of its ten rules had no control at
all. Two of the eleven, and four of the branches below, exist because the independent
review of this change found them missing; see the section after this one.

| Rule | Driven over |
|---|---|
| `a-capability-names-only-claims-the-register-holds` | a group naming a claim identifier the register does not hold |
| `a-capability-group-shows-at-least-one-claim` | a group naming nothing |
| `no-claim-is-shown-under-two-capabilities` | a group repeating a claim another group already shows |
| `a-certified-claim-cites-a-record-that-exists` | four corruptions: a certified row citing a template, one citing nothing, one citing a path outside `docs/proof/`, and one citing a record that does not exist |
| `a-planned-or-deferred-claim-cites-no-record` | the deferred capacity claim, given a record |
| `an-evidence-label-is-one-the-register-defines` | a row given an evidence label the register does not define |
| `a-level-may-not-exceed-its-labels-ceiling` | a `mock` row raised to `C2` |
| `a-cell-value-fits-in-one-table-row` | a limitation, and a label meaning, written across two lines |
| `a-real-behaviour-capability-rests-on-real-evidence` | the real-completion claim moved onto `mock` evidence |
| `a-real-cluster-result-names-its-provider` | the in-cluster serving claim stripped of its provider |
| `a-displayed-status-is-one-the-register-defines` | a row given the status `shipped`, and a register that keeps the name `certified` while withdrawing its permission to publish |

Two further controls sit beside them. One promotes `an-alert-reaches-somebody` from
`not-claimed` to `certified` in a private copy of the register and asserts the
rendered page changes — the check that the page is derived rather than described; a
page written by hand would not notice. The other promotes the deferred capacity claim
and asserts that `--page`, `--check`, and `--write` each exit 1, print `REFUSED` on
standard error, render nothing, and leave the committed page untouched.

## What an independent review found after the first commit

The page itself survived: every count on it was recomputed from the register by the
reviewer and every one matched, and each rule named a control that genuinely drove it
to fire. What did not survive was the hand-written prose around it, which is where
this project's counts have always drifted.

### A count this change got wrong, and one it inherited

`docs/testing/test-inventory.md` opens each layer section with a written-out module
count. Two of the seven were wrong:

| Layer | The document said | The data held |
|---|---|---|
| `architecture-inventory` | Eighteen | 19 |
| `documentation` | Thirty-two | 33 |

The second is this change's own. `V1-S4-009-PR1` added a module and wrote
"thirty-first" when thirty-two existed; this branch added the thirty-third and wrote
"thirty-second", because adding one to a wrong number keeps it wrong. The first was
already wrong on `main` and has nothing to do with this change except that the check
added here refuses it.

Both are corrected, and
[`tests/testing/test_test_inventory.py`](../../../tests/testing/test_test_inventory.py)
now recomputes every layer's count from the data and holds the sentence to it. That
document narrates its own drift six times across two layers, each time recording
"it is not machine-checked, which is why it drifted" as the explanation. The
explanation is now false, which was the point.

A second unchecked count was found beside it, in
[the register's own document](../../testing/claim-evidence-matrix.md): the sentence
counting the surfaces that make no capability claim, which this change moved from
seven to eight. It was correct and unwatched. It is now checked.

### Two rules, and four branches, that were not being watched

- The refusal for an evidence label the register does not define was being reported
  under the ceiling rule's identifier, so one rule appeared to be watching two
  different failures and one of them had no control. It is now its own rule.
- Nothing refused a line break inside a value the page prints into a table cell. A
  pipe is escaped on the way in and a line break cannot be: the row would end and the
  rest of the value would leave the table silently. No register value carries one
  today, which is the argument for checking it rather than against. It is now a rule.
- The citation rule has four failure branches and two controls. The two without them
  were the ones that would catch a path outside `docs/proof/` and a record somebody
  deleted — failures a reader of the page could not possibly notice. All four are now
  driven.
- The per-capability check compared a row's values against the whole page rather than
  against that capability's own section, so a row rendered under the wrong heading
  would have passed it. It is now scoped to the section.

### A claim about newlines that was not true

`.gitattributes` and this record both said the generator writes LF on every platform
and that the committed page is compared with what `python -m tools.proof_dashboard
--page` prints. The first half was true of `--write` and false of `--page`: Python
translates a line feed to the platform's line ending on the way to a text stream, so
on this Windows host `--page` emitted CRLF — and, worse, CP-1252, which turned em dashes
in the register into a replacement byte. The comparison the repository actually
performs never went through `--page`, so nothing was broken; the sentence describing
it was. `--page` now pins both its encoding and its newline, a test asserts its bytes
equal the committed file's, and the claim is true rather than corrected away.

## What this change does not add

The story's own boundary, restated so that a later reader can see it was a choice:

- **No monitoring.** The page contacts nothing and holds no series. The operations
  view stays [the inference operations dashboard](../../telemetry/inference-operations-dashboard.md),
  and the page says so in its own text rather than only here.
- **No second data model.** No status, count, level, or provider is stored in the
  generator. The capability grouping is the only thing it holds that the register
  does not, and it carries no claim state, which is why adding a group cannot
  promote anything.
- **No freshness or assurance signal.** Nothing says when a result was last re-run
  or whether it would reproduce today.
- **No environment fleet view, no continuous verification schedule, and no release
  gate.** No check consumes the page to decide whether anything may ship.
- **No application framework.** One Python module renders Markdown; the repository
  gains no server, no build step, and no front-end dependency.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Generated from, or mechanically checked against, the authoritative claim state | Met. Generated, and the committed page is compared byte for byte with what the register renders |
| Cannot independently overstate status, level, evidence class, or provider scope | Met. No such value exists in the generator; every one is read from the register and asserted against it row by row |
| Distinguishes `certified`, `planned`, `deferred`, and `not claimed` | Met. All four appear in the status table with the register's own meanings and publication rule, and a test fails if a state disappears |
| Each certified capability has a navigable evidence path and a visible limitation | Met. 41 distinct records linked, each resolving from `docs/proof/`; the limitation is a column, not a footnote |
| Does not duplicate Grafana operational monitoring | Met. Stated on the page twice and checked; the page reads files and asks nothing of a cluster |
| No unsupported production, multi-replica, cross-provider, GPU, security, SLO, cost, or portable-capacity claim | Met. Multi-replica, network-policy enforcement, a defended workload, a provider cost, and a portable production platform all appear as `not-claimed` with the register's own reasons |
| Deterministic and reviewable in the repository | Met. One Markdown file, LF-pinned in `.gitattributes`, regenerated by one command |
| Parent story: every planned public claim has evidence and a limitation | Met by `V1-S4-009-PR1` and unchanged here; the page adds an entry point, which the register now governs as a surface that claims nothing |

## Limitations

- The capability grouping is a reading, not a derivation. Which claims belong under
  *model integrity* rather than *real serving* is a judgement in
  `tools/proof_dashboard/core.py`. No test decides it, and a claim placed under a
  heading a reader finds surprising is not a failing build.
- Seven certified claims are in no group. They are counted everywhere and shown
  nowhere as rows, and a reader wanting all 58 in one table wants the register.
- The page inherits the register's first limitation whole: nothing here establishes
  that a statement is true, only that it is the register's statement.
- Every real result behind these rows was produced on one Windows host, by one
  author, by hand, and most of it on the `docker-desktop` reference provider. No
  outside party has reviewed a claim against its evidence.
- The suite compares content rather than bytes on disk: it reads the committed page
  in text mode, so a checkout that translated line endings is not reported as drift.
  `.gitattributes` pins the checkout to LF so that the question does not arise, and
  the generator writes LF on every platform.
- Nothing runs this generator automatically. It is a contributor command and a test,
  in a repository where every lane but one is run by hand.

## Authorisation

Not required. No command in this record contacts a network, selects or mutates a
cluster, downloads or loads a model artifact, provisions anything that costs money,
or runs a destructive operation. The only file written by a command here is
`docs/proof/dashboard.md`, by `python -m tools.proof_dashboard --write`.
