# V1-S5-013-PR2 validation

Date: 2026-09-26

What this change checked before it was committed, and how. What it changed and why is
in [the publication and freeze](v1-s5-013-pr2-publication-and-freeze.md); this page is
about the checks run over the repository after those changes were made.

This change executed nothing against a host: no cluster, runtime, or model was
contacted, and every figure it quotes was already committed.

## What changed

- **A fourth ledger and a freeze.** `tools/evidence_index` reads
  [the publication ledger](v1-s5-013-pr2-publication.v1alpha1.json) after the other
  three. The index's summary now carries `evidenceFreeze`, derived by
  `evidence_freeze`, which refuses a declared freeze beside an open blocker or with an
  unknown decision; `evidencePackSha256`, over the cited files together with the
  register and every ledger, which the index lists as `packSources`; and the
  publication ledger's counts. `--gate` prints the freeze and both digests after the
  closure lines, and exits 1 if the committed index is stale.
- **Four register changes**, each named in the ledger with its value before and after
  and applied through the repository's own `apply_register_changes`, which checks every
  value it replaces. **Four corrections** beside three dated records, none of which was
  edited.
- **Generated surfaces regenerated**: the evidence index. The proof dashboard's check
  passed unchanged.
- **The case study published**, its data file bound to both digests and the freeze.
- **Current pages reconciled**: the README, the claim and evidence matrix page, the
  evidence index page, the proof and testing indexes, the evidence-record model, and the
  test inventory.
- **One new test module**, `tests/testing/test_evidence_publication.py`, and changes to
  four existing ones: `test_case_study.py` requires the page to be published exactly
  when the pack is frozen, the README to link it exactly then, and both digests to
  match; `test_evidence_index.py` reads the closure ledger by its path rather than as
  the last ledger, checks every ledger's corrections, and counts eleven corrected
  files; `test_evidence_closure.py` restores the register as `V1-S5-006-PR2` left it
  through both later ledgers, and compares its dated report with the gate's closure
  lines only; `test_test_inventory.py` knows the word forty-five.

## Commands

From Git Bash at the repository root, with every file of this change staged so that the
suites that read `git ls-files` see it:

```text
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked python -m mypy
uv run --locked python -m pytest tests/testing/test_evidence_publication.py tests/testing/test_case_study.py tests/testing/test_evidence_closure.py tests/testing/test_evidence_index.py tests/testing/test_evidence_completeness.py tests/testing/test_evidence_migration.py -q
uv run --locked python -m pytest tests/testing tests/security tests/architecture -q
uv run --locked python -m tools.proof_dashboard --check
uv run --locked python -m tools.evidence_index --check
uv run --locked python -m tools.evidence_index --gate
uv run --locked python -m pytest -q
git diff --cached --check
```

## Results

On 2026-09-26, on one Windows host, before the first commit:

| Command | Result |
|---|---|
| `ruff format --check .` | 516 files already formatted, after one reformat of three changed files |
| `ruff check .` | All checks passed |
| `python -m mypy` | No issues in 277 source files |
| The six evidence and case-study suites | 1448 passed |
| `pytest tests/testing/test_evidence_publication.py -q` | 42 passed |
| `pytest tests/testing tests/security tests/architecture -q` | 10507 passed, 3 skipped |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `python -m tools.evidence_index --gate` | `COMPLETE V1-S5-013` and `FROZEN   V1-S5-013-PR2`, exit 0, quoted in full in [the publication report](v1-s5-013-pr2-publication-and-freeze.md#the-gate) |
| `pytest -q`, the default lane | 15221 passed, 30 skipped, 14 deselected, in 22 min 4 s |
| `git diff --cached --check` | Clean |

The Helm and Terraform gates were not run: nothing under `charts/` or `infra/`
changed. The default lane ran before this results table was written, which changed
prose only.

## Privacy and publicability

The staged diff was searched for a drive-letter or home-directory path, a scratch
directory, an e-mail address, a credential-shaped string, and the name of any private
planning document. None is present. No model artifact, generated render, or machine
state is added.
