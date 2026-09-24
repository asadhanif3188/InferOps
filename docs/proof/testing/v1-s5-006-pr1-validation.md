# V1-S5-006-PR1 change validation

Date: 2026-09-24

Change: every finding [the evidence migration](v1-s5-012-pr2-migration-report.md) left
open answered with one disposition, the register corrected where those answers
required it, corrections recorded beside nine historical records, and
[the V1 evidence index](../v1-evidence-index.md) generated over the result.
[The normalization report](v1-s5-006-pr1-evidence-normalization.md) is the substance;
this record says how the change was checked.

Classification: **local static evidence.** Evidence class `local-static`, and `C0`
under [the evidence-level specification](../../testing/evidence-levels.md). Every result
below was produced on one Windows host by running commands over files in this
repository and reading its history. No cluster was selected or contacted, no model was
loaded, no runtime was started, no request was served, no container was built or run,
and no job was executed on the continuous-integration service.

## What changed

| Area | Files |
|---|---|
| The index tool | [`tools/evidence_index/`](../../../tools/evidence_index/) — builds the index from the register and the ledger, hashes every cited file, and restores or re-applies the ledger's register changes |
| The generated index | [`v1-evidence-index.v1alpha1.json`](../v1-evidence-index.v1alpha1.json) and [its page](../v1-evidence-index.md); its checkout is pinned to LF in `.gitattributes`, as the dashboard's is |
| The ledger and its report | [`v1-s5-006-pr1-normalization.v1alpha1.json`](v1-s5-006-pr1-normalization.v1alpha1.json) and [`v1-s5-006-pr1-evidence-normalization.md`](v1-s5-006-pr1-evidence-normalization.md) |
| The register | [`claim-evidence-matrix.v1alpha2.json`](../../testing/claim-evidence-matrix.v1alpha2.json): 25 changes, every one in the ledger; 57 evidence records, up from 54 |
| Pages generated from the register | [The proof dashboard](../dashboard.md), regenerated with `--write` |
| Pages that describe the register | [The claim and evidence matrix](../../testing/claim-evidence-matrix.md), [the evidence-record model](../../testing/evidence-record-model.md), [the architecture index](../../architecture/README.md), [the testing index](../../testing/README.md), [the evidence records index](../README.md), [the README](../../../README.md), [the pod recovery page](../../serving/inference-pod-recovery.md), and the changelog |
| Tests | New [`tests/testing/test_evidence_index.py`](../../../tests/testing/test_evidence_index.py); [`test_evidence_migration.py`](../../../tests/testing/test_evidence_migration.py) now undoes the ledger's changes before comparing the migration; `test_test_inventory.py` learned the number forty-one |
| The test inventory | One module added to [the data](../../testing/test-inventory.v1alpha1.json) and [the document](../../testing/test-inventory.md), with the no-claim and documentation-layer counts moved to match |

Nothing under `docs/proof/` that existed before this change was edited except the
evidence records index, [`docs/proof/README.md`](../README.md), and the generated
dashboard. Every correction to a historical record is in the ledger, beside it.

## Commands, and what they returned

Run from the repository root, in Git Bash, on the working tree that became the first
commit.

| Command | Result |
|---|---|
| `python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.proof_dashboard` | `OK       59 claims satisfy 8 dashboard rules` |
| `uv run --locked python -m pytest tests/testing/test_evidence_index.py -q` | `364 passed` |
| `uv run --locked python -m pytest tests/testing/test_evidence_migration.py -q` | `639 passed` |
| `uv run --locked python -m pytest tests/testing tests/security tests/telemetry -q` | `8259 passed`, on the working tree before it was committed |
| `uv run --locked ruff format --check .` | `498 files already formatted` |
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked python -m mypy` | `Success: no issues found in 273 source files` |
| `git diff --check` | no output |

The full default lane was not run for the first commit; it is run on the committed tree
and recorded with the review below, because a suite that lists tracked files counts a
new record only once it is committed.

## Private-information review of the diff

The diff was read for anything that belongs to the host or to private planning rather
than to this repository. It names no host path, user account, drive letter, private
repository, prompt, response, credential, or model artifact. The ledger and the index are
scanned by a test for drive-letter paths, user directories, scratch directories, and
paths into a planning directory. Every quote in them is from a committed file, and every commit
identifier is one this repository's history or its committed records already carry.

## What was not run, and why

- **No experiment was re-run.** Several findings could be closed more strongly by a new
  run — the telemetry sample that nobody has explained, and the 18 executed records
  that do not name the revision that ran. Running a real model or a cluster was outside
  this change's authority, and the ledger carries those to `V1-S5-006-PR2` rather than
  closing them by inference.
- **No continuous-integration run was promoted.** The eleven-gates claim no longer
  states a hosted result, so none was needed.

## Authorisation

Not required. This change read committed files and the repository's history, wrote
documents, data, code, and tests, and contacted nothing outside the repository.
