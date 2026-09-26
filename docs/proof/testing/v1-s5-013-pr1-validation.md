# V1-S5-013-PR1 validation

Date: 2026-09-26

What this change checked before it was committed, and how. The evidence it produced,
the reruns, is recorded in [the blocker closure](v1-s5-013-pr1-blocker-closure.md) and
the four records it links; this page is about the checks run over the repository after
those records were written.

## What changed

- **A third ledger and a stricter gate.** `tools/evidence_index` reads
  [the closure ledger](v1-s5-013-pr1-closure.v1alpha1.json) beside the normalization and
  completeness ledgers. `--gate` reads the current decision from it, and
  `open_blockers` refuses a closure in which any blocker the completeness ledger raised
  is missing, disposed of twice, or disposed of by a mechanism outside the three.
- **Four records added, one status moved, thirteen register changes**, each named in
  the ledger with its value before and after, and applied through the repository's own
  `apply_register_changes`, which checks every value it replaces.
- **The test strategy defers the `kind` helper's claim**, so no current surface counts
  it as certified.
- **Generated surfaces regenerated**: the evidence index and the proof dashboard.
- **Current pages reconciled**: the index page, the README, both claim matrices, the
  test inventory, the proof and testing indexes, the evidence-record model, and the case
  study, which stays a draft and was re-verified for what this change moved.
- **One new test module**, `tests/testing/test_evidence_closure.py`, and changes to five
  existing ones: `test_evidence_completeness.py` reads its own ledger's decisions against
  the register as `V1-S5-006-PR2` left it and the current state through all three
  ledgers; `test_evidence_index.py` allows exactly the status moves a claim decision
  names; `test_case_study.py` reads the gate from the closure ledger;
  `test_test_strategy.py` makes a count sentence's verb agree with its count, which it
  could not while the deferred count was one; and `test_test_inventory.py` spells
  forty-four.

## Checks run before the first commit

| Check | Result |
|---|---|
| `python -m tools.evidence_index --gate` | exit 0, `COMPLETE V1-S5-013`, five closures printed |
| `python -m tools.evidence_index --check` | `OK`, the committed index is what the register and ledgers produce |
| `python -m tools.proof_dashboard --check` | `OK`, the committed dashboard is what the register produces |
| `uv run --locked ruff check .` | all checks passed |
| `uv run --locked ruff format --check .` | 512 files already formatted |
| `uv run --locked mypy` | no issues in 276 source files |
| The ten evidence suites: closure, completeness, index, migration, claim matrix, dashboard, strategy, level rules, record model, and levels | all passed |
| `tests/testing`, `tests/security`, and the decision-authority suite | all passed once this record existed; before it, only the two checks that require it failed |

Every count this change publishes is recomputed by a test from the register, the
ledgers, or the index: the claim and record counts, the code-identity counts, the
blocker dispositions, the digest, and the strategy's split.

## How the reruns were kept apart from the checks

No test suite ran while a rerun was measuring. The suites above were run only after the
last rerun had finished and the cluster had been returned to its starting state, so no
measured figure shares the host with a suite.

## Private-information review

Every file this change adds or edits was searched for drive-letter and home-directory
paths, the scratch directory used during the session, the private planning repository,
the host account, and the unrelated namespace on the operator's cluster. The
transcripts were redacted mechanically before they were copied in, by rules their own
header lists, and a test refuses a drive-letter, home-directory, temporary, scratch, or
planning path in any file the closure cites.

## What was not checked here

- **The full default lane** is run on the committed tree, because the document-link
  suite collects only tracked files; its result is added below after the first commit.
- **Hosted continuous integration** has not run on this branch.
