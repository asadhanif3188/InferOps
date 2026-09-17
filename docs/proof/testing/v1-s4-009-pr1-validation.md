# V1-S4-009-PR1 change validation

Date: 2026-09-17

Change: [the V1 claim and evidence matrix](../../testing/claim-evidence-matrix.md)
and [its authoritative data](../../testing/claim-evidence-matrix.v1alpha1.json),
[the suite that holds it to its own rules](../../../tests/testing/test_claim_evidence_matrix.py),
the row that suite adds to
[the test inventory](../../testing/test-inventory.v1alpha1.json) and
[its document](../../testing/test-inventory.md), the entry point the register
gains in [the README](../../../README.md), and the pointers added to
[the testing index](../../testing/README.md),
[the claim and test matrix](../../testing/claim-test-matrix.md), and
[the evidence index](../README.md).

Classification: **local static evidence.** Evidence class `local-static`. Every
result below was produced on one Windows host by running commands over files in
this repository. No cluster was selected or contacted, no model was loaded, no
runtime was started, no request was served, no container was built or run, and no
job was executed on the continuous-integration service.

**No product behaviour changed.** Nothing under `src/`, `tools/`, `charts/`,
`infra/`, `deploy/`, or `scripts/` is touched by this change. The only executable
file it adds is a test.

Claim boundary: 58 claims are registered as data; each names a status, an evidence
label, an environment, a limitation, and a statement of what it does not establish;
each certified row cites at least one committed record under `docs/proof/` that is
not a template and names the record carrying its immutable versions; each of the
24 claims in the accepted test strategy is mapped by at least one row, and no row
carries a stronger status than the strategy claim it maps to; every implementation,
test-module, gate, record, and README path a row cites resolves; and every relative
link in the README's public entry-point table is either cited by a row or listed,
with a reason, as a surface that makes no capability claim.

**What this record does not establish.** It is not evidence that any statement in
the matrix is true. The suite checks references, ranks, ceilings, and vocabulary;
whether a record says what the row citing it says it says is a reading, and no test
performs one. It raises no certification level — every level in the matrix is
restated from a record that already carried it — and it produces no new measurement
of any kind. The figures it quotes are quoted from records made earlier, on other
days, by other changes.

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
| Branch | `docs/v1-s4-009-claim-evidence-matrix` |
| Base | `main` at `8819a725901dcfb505709959b63a3846f26541d0` |

No Docker engine, Helm, Terraform, `kubectl`, or `promtool` was used. `shellcheck`
is not installed on this host and no shell script changed, so it is recorded as not
run rather than as passing.

## What the register holds

| Fact | Value |
|---|---|
| Claims | 58 |
| Certified | 41 |
| Planned | 8 |
| Deferred | 1 |
| Not claimed | 8 |
| Rows citing at least one record | 43 |
| Distinct records cited | 46 |
| Distinct test modules cited | 70 |
| Distinct continuous-integration gates cited | 9 of 11 |
| Test-strategy claims mapped | 24 of 24 |
| README entry points claimed by a row | 43 |
| README entry points declared to claim nothing | 7 |
| Rows asserting real behaviour | 26 |
| Rows at `C2` | 18 |
| Rows whose provider is `docker-desktop` | 14 |
| Rows whose provider is `kind` | 1 |

Evidence labels in use: `local-static` 20, `local-real-cpu` 20,
`documented-unexecuted` 13, `mock` 3, `estimated` 1, `production-experience` 1.
`cloud-real-cpu` and `cloud-real-gpu` are declared and used by nothing, which is
the same statement the certification document already makes about them.

43 plus 7 is 50, and the README's public entry-point table has 50 rows after this
change. That arithmetic is the completeness check, and it is a test rather than a
sentence.

## Commands, and what they returned

Run from the repository root, in Git Bash, through the locked environment.

| Command | Result |
|---|---|
| `python -m pytest tests/testing/test_claim_evidence_matrix.py -q` | `1599 passed` |
| `python -m pytest tests/testing/test_test_inventory.py -q` | `836 passed` |
| `uv run --locked ruff format --check .` | `445 files already formatted` |
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked python -m mypy` | `Success: no issues found in 249 source files` |
| `uv run --locked python -m pytest -q` | `11336 passed, 30 skipped, 14 deselected in 758.43s` |
| `git diff --check main...HEAD` | no output, exit 0 |
| `git ls-files -z '*.md' \| xargs -0 grep -n '[[:blank:]]$'` | no match |
| `git ls-files -z '*.md' \| xargs -0 grep -n "$(printf '\t')"` | no match |
| the POSIX link check CONTRIBUTING publishes | two pre-existing reports, below |

The first two commands were also run before the document existed, and the second of
those runs is the reason this record can say the suite works: with the data file
committed and the document absent, seven checks failed — a limitation shorter than
the floor, a level above its label's ceiling, the reserved vocabulary, a surface
listed in both directions, a reason shorter than the floor, and the two document
checks. Six were defects in the data and were fixed; the seventh was the document
not yet being written.

### The link check's two reports

The shell snippet in [CONTRIBUTING](../../../CONTRIBUTING.md) reports two broken
links that are not broken and are not introduced here:

```text
BROKEN: docs/proof/README.md -> ...
BROKEN: docs/proof/security/v1-s3-004-pr1-validation.md -> ...
```

Both are the literal string `Produced from [the raw-result template](...)` quoted
inside an inline code span, as an illustration of the declaration a record carries.
Both are present on `main` at the base revision. The snippet strips fenced blocks
and not inline code;
[`tests/testing/test_document_links.py`](../../../tests/testing/test_document_links.py)
strips both and passes, and it is the check the certified claim rests on. This is
recorded rather than silenced because a contributor running the published command
will see the same two lines.

## What the suite refuses

Eight rules, each driven over a row corrupted to break it, and one positive control.
A rule nobody has watched fail may already be unreachable, and one of these refused
a sentence it should have accepted until the control was added.

| Rule | The row it was driven over |
|---|---|
| A level may not exceed its label's ceiling | a certified row relabelled `mock` at `C2` |
| A real-behaviour claim needs real evidence | a certified serving row relabelled `mock` |
| A row may not outrank the strategy claim it maps to | a planned row promoted to certified |
| A planned or deferred row cites no record | a planned row given an evidence reference |
| A template is not evidence | a certified row citing `TEMPLATE-claim-evidence.md` |
| No estimate is described in an invoice's vocabulary | a limitation naming an invoice without denying it |
| A real Kubernetes row names its provider | a `docker-desktop` row with its provider removed |
| Every row states a limitation | a row with its limitation emptied |
| The vocabulary rule admits a denial | a limitation that names the word in order to refuse it |

The last is a positive control rather than a negative one, and it exists because
the first version of that rule banned the words outright. That version refused the
register's own statement of the cost rule, which is a rule that cannot be published.
The corrected rule permits a reserved word inside a sentence that denies it and
nowhere else, and both directions are now driven.

## Defects this change found in its own data

Six, all found by running the suite rather than by reading the file.

1. **A cost claim certified on an evidence label that certifies nothing.** The row
   binding the cost method to the `V1-S4-004` samples was labelled `estimated` and
   claimed `C0`. `estimated` carries a ceiling of `certifies nothing`, so the row
   was asserting a level its own label forbids. What is actually certified is the
   derivation and the arithmetic — a `local-static` fact — and the row now says so,
   with the amounts' confidence of `none` moved into its limitation. The
   `estimated` label moved to the row it fits: the one saying what running this
   workload costs on a provider, which is not claimed.
2. **The cost rule stated in the vocabulary it refuses.** "Only an invoice-backed
   basis may carry an invoice's vocabulary" names the reserved words without
   denying them. Rewritten to deny them.
3. **A limitation that was one clause.** The link-check row said "It establishes
   that a path resolves." — true, and shorter than the floor the suite sets for a
   limitation, because it did not say what the check does not read.
4. **Three surfaces listed as claiming nothing while a row claimed them.** The
   certification document, the claim and test matrix, and the project boundaries
   were in both lists. Removed from the exclusion list, since a row cites each.
5. **A reason that was four words.** `LICENSE` was excused with "The MIT licence
   text." The exclusion list is the place an uncomfortable path could be parked, so
   its reasons carry the same floor the limitations do.
6. **Counts in prose with nothing checking them.** The document's and the README's
   claim counts are now derived and compared, after the test inventory's per-layer
   counts drifted three times for exactly this reason.

One further defect was found outside this change's own data, while adding a row to
the evidence index: the `Testing` row of [that index](../README.md) did not list
[`v1-s4-001-pr1-validation.md`](v1-s4-001-pr1-validation.md), which has been
committed since 2026-09-12. Nothing checks that index against the directory it
describes. The missing link is added here rather than left for a later change,
because the register this PR publishes cites the index it is missing from; the
absent check is not fixed here and stays a gap.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Every planned README claim has evidence and limitation | **Met.** Every one of the README's 50 public entry points is cited by a row or listed with a reason, checked in both directions. Every row carries a limitation and a statement of what it does not establish, both with a length floor |
| Mock, synthetic, local real, and estimated labels are explicit | **Met.** Every row declares one of nine labels, each with the ceiling it carries; a level above that ceiling is refused, and a real-behaviour claim resting on `mock`, `synthetic`, or `estimated` is refused |
| Unsupported claims are removed or marked future | **Met.** 8 planned, 1 deferred, and 8 `not claimed`. None of the planned or deferred rows cites a record, which is enforced |
| The final matrix preserves provider boundaries | **Met.** Every real Kubernetes row names a provider the cluster provider contract publishes; 14 rows are `docker-desktop` and 1 is `kind`; the multi-replica row is `not claimed` and cites the capacity refusal |
| Bounded load figures are not portable capacity claims | **Met.** The performance rows are bounded observations under ADR 0013 and say so; `sustained-throughput-and-capacity-under-load` stays `deferred` |
| Synthetic cost output is not an actual cost | **Met.** No row describes an amount in the vocabulary reserved for an invoice except in a sentence denying it, and what running the workload costs on a provider is `not claimed` |
| A lightweight completeness check where practical | **Met.** 1599 checks; the README direction is the completeness half |
| Deferred to PR2 | The light V1 proof dashboard. This PR publishes the authoritative data it will be generated from or validated against, and builds no dashboard |

## Limitations

- **One host, one day, one author.** Every command above ran on one Windows
  machine. None of them ran on the continuous-integration service, because the
  workflow runs on a pull request and this change has not opened one.
- **The suite cannot read.** It establishes that a row's references resolve and
  that its status, level, label, and provider are mutually consistent. It cannot
  establish that the record a row cites supports the sentence the row makes. That
  is the gap this whole document exists inside, and the matrix states it in its own
  limitations rather than only here.
- **Every quoted figure is second-hand.** The measurements in the rows — 31,960 ms,
  0.554 to 0.575 requests per second, 285,828 ms, 179,755 ms, 8,484,278,272 bytes —
  were made by earlier changes on other days and are reproduced here. Nothing in
  this change measured anything.
- **The classification of a cited record is the record's own.** A row repeats the
  evidence class the record declares. Nothing re-derives it, so a record that
  classified itself generously is repeated generously.
- **`readmeRefs` is one surface.** The case study this register is meant to govern
  has not been written, so a future case-study claim with no row here would be
  caught by nothing. The matrix records that as a limitation.
- **The `claim-evidence` template has still produced no record.** A table is a
  weaker form than the one-claim-per-record document, and this change does not
  change that count.
- **`shellcheck` was not run**, because it is not installed on this host and no
  shell script changed. Not run is the honest answer; passing would not be.

## Authorisation

Required: **no**. Nothing here downloads a large artifact, costs money, or touches
anything outside this repository's working tree.

Review: the change was reviewed against this record by an independent reviewer
before the second commit on this branch. No maintainer roster exists to name a
person, which is the governance gap
[CONTRIBUTING](../../../CONTRIBUTING.md) records.
