# V1-S5-006-PR2 change validation

Date: 2026-09-24

Change: every finding [the evidence normalization](v1-s5-006-pr1-evidence-normalization.md)
answered given one final state; every executed record's code identity read and
derived; three claims given a record at a named revision by
[running their suites again](v1-s5-006-pr2-pinned-suite-run.md); four records given the
citation that holds their content pins; five certified claims held as release
blockers; and [the V1 evidence index](../v1-evidence-index.md) extended into the
evidence manifest, with a release gate. [The completeness report](v1-s5-006-pr2-evidence-completeness.md)
is the substance; this record says how the change was checked.

Classification: **local static evidence**, evidence class `local-static`, and `C0`
under [the evidence-level specification](../../testing/evidence-levels.md), except the
pinned suite run, which is its own record with its own levels. Every result below was
produced on one Windows host by running commands over files in this repository and
reading its history. No cluster was selected or contacted, no model was loaded, no
runtime was started, no container was built or run, and no job was executed on the
continuous-integration service.

## What changed

| Area | Files |
|---|---|
| The completeness ledger and its report | [`v1-s5-006-pr2-completeness.v1alpha1.json`](v1-s5-006-pr2-completeness.v1alpha1.json) and [`v1-s5-006-pr2-evidence-completeness.md`](v1-s5-006-pr2-evidence-completeness.md) |
| A new evidence record | [`v1-s5-006-pr2-pinned-suite-run.md`](v1-s5-006-pr2-pinned-suite-run.md), cited by three register records |
| The index tool | [`tools/evidence_index/`](../../../tools/evidence_index/) — reads both ledgers, names every cited file by its git blob, carries each executed record's code identity and each claim's blockers, digests the evidence set, and adds `--gate` |
| The generated index and dashboard | [`v1-evidence-index.v1alpha1.json`](../v1-evidence-index.v1alpha1.json) and [its page](../v1-evidence-index.md); [the proof dashboard](../dashboard.md), regenerated with `--write` |
| The register | [`claim-evidence-matrix.v1alpha2.json`](../../testing/claim-evidence-matrix.v1alpha2.json): 12 changes, every one in the completeness ledger; 60 evidence records, up from 57 |
| The strategy data | [`test-strategy.v1alpha1.json`](../../testing/test-strategy.v1alpha1.json): one layer note that paired `C3` with its superseded meaning |
| Pages that describe the register | [The claim and evidence matrix](../../testing/claim-evidence-matrix.md), [the evidence-record model](../../testing/evidence-record-model.md), [the testing index](../../testing/README.md), [the evidence records index](../README.md), [the README](../../../README.md), and the changelog |
| Tests | New [`tests/testing/test_evidence_completeness.py`](../../../tests/testing/test_evidence_completeness.py); [`test_evidence_index.py`](../../../tests/testing/test_evidence_index.py) and [`test_evidence_migration.py`](../../../tests/testing/test_evidence_migration.py) undo and read both ledgers; `test_test_inventory.py` learned the number forty-two; one stub server in `tests/serving/test_performance_scenarios.py` now reads a request body before answering, for the reason under the commands below |
| The test inventory | One module added to [the data](../../testing/test-inventory.v1alpha1.json) and [the document](../../testing/test-inventory.md), with the no-claim and documentation-layer counts moved to match |

Nothing under `docs/proof/` that existed before this change was edited except the
evidence records index, [`docs/proof/README.md`](../README.md); the index's own
[page](../v1-evidence-index.md); and the two generated files.

## Commands, and what they returned

Run from the repository root, in Git Bash, on the working tree that became the first
commit, with every file staged so that the suites which list tracked files see the new
records.

| Command | Result |
|---|---|
| `python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `python -m tools.evidence_index --gate` | `INCOMPLETE V1-S5-006: 5 release blockers`, exit 1 |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.proof_dashboard` | `OK       59 claims satisfy 8 dashboard rules` |
| `uv run --locked python -m pytest tests/testing/test_evidence_completeness.py -q` | `81 passed` |
| `uv run --locked python -m pytest tests/testing/test_evidence_index.py -q` | `399 passed` |
| `uv run --locked python -m pytest tests/testing/test_evidence_migration.py -q` | `639 passed` |
| `uv run --locked python -m pytest tests/testing tests/security tests/telemetry -q` | `8413 passed` |
| `uv run --locked python -m pytest -q` | `1 failed, 14803 passed, 33 skipped, 14 deselected in 821.82s`, on the tree before its last edits; the failure is explained under this table |
| `uv run --locked ruff format --check .` | `502 files already formatted` |
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked python -m mypy` | `Success: no issues found in 274 source files` |
| `git diff --cached --check` | no output |

**The one failure, and what was done about it.** It was
`tests/serving/test_performance_scenarios.py::test_the_collector_is_asked_by_get_without_parameters_and_by_post_with_them`,
which serves a stub collector on a loopback socket and failed with a
`ConnectionAbortedError` from the host's socket layer, while the client read an answer.
The first commit's validation said it was not this change's; that was asserted before
it was checked, and what the checking found is less tidy:

| Run | Result |
|---|---|
| The test alone, and its module alone, on this branch | passed; `123 passed` for the module |
| The full lane on the first commit, `d1232a4` | `1 failed, 14808 passed, 33 skipped, 14 deselected in 811.47s` — the same test |
| Every module that runs before `tests/testing/`, on this branch | `7267 passed, 33 skipped, 14 deselected` |
| The same modules on the unchanged `e145a6e` | `7264 passed, 33 skipped, 14 deselected` |
| The full lane on the unchanged `e145a6e`, in a clean detached worktree | `14662 passed, 33 skipped, 14 deselected in 1098.83s` |

So it failed in both full-lane runs of this branch and in none of the other runs, and
nothing this change touches runs before it. No cause in this change was found; one
cause in the test was. Its stub answers the form POST the collector client sends
without reading the request body, and a server that closes a connection with the body
unread can reset it on Windows before the client reads the answer — a race whose
outcome depends on timing, which is what the pattern above looks like. The stub now
reads the body before it answers, which is what a server is meant to do, and the test
asserts what it asserted before. Whether that race is the whole cause is not proven:
it was the only mechanism found, and after the fix the full lane passed.

After the review's corrections and the stub fix, on the working tree that became the
second commit:

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | `14810 passed, 33 skipped, 14 deselected in 1322.33s` |
| `uv run --locked python -m pytest tests/testing/test_evidence_completeness.py tests/testing/test_document_links.py tests/security -q` | `1182 passed` |
| `uv run --locked python -m pytest tests/serving/test_performance_scenarios.py -q` | `123 passed` |
| `uv run --locked ruff format --check .`, `ruff check .`, `python -m mypy` | clean, `All checks passed!`, `Success: no issues found in 274 source files` |

The pinned suite run's own commands and results are in
[its record](v1-s5-006-pr2-pinned-suite-run.md); it ran in a separate detached worktree
at `e145a6e6fe2417a18e6d77a7f14751ec71786888`, which was removed afterwards.

## What the independent review found, and what the first commit got wrong

An independent reviewer read the first commit before it was pushed: every changed file,
the records the changed register entries cite, and every count the documents publish,
recomputed from the register, the ledgers, and the repository's history. It matched
every headline count, confirmed the ten chart trees, the twelve records naming the chart
version, the four content pins' parents and changed paths, the telemetry mechanism
against the verification tool and the chart's rules, and both recovery records' own
words, and disputed no classification and no blocker. It found one defect:

| Severity | Finding | Fix |
|---|---|---|
| Low | The report's privacy section gave the largest tracked file's size as 913 227 bytes, its size in this Windows checkout with CRLF line endings; the committed object is 882 177 bytes. No test read the sentence | Corrected, and a test now reads the largest committed object's size, and that no model artifact is tracked, from the repository |

It also noted that the content-pin test asserted a subset of the code paths the ledger
records; it now requires all six. The first commit's claim that the full-lane failure
was not this change's is corrected above, under the commands: it was asserted before it
was checked. Neither was caught by a test before, because the
report's tests read its summary table and identifiers, not its prose.

## Private-information review of the diff

The diff was read for anything that belongs to the host or to private planning rather
than to this repository, and the whole cited evidence set was scanned as
[the completeness report](v1-s5-006-pr2-evidence-completeness.md#privacy-and-publicability)
describes. The diff names no host path, user account, drive letter, private repository,
prompt, response, credential, or model artifact. The worktree the pinned run used is
described by what it was, not where it was. The ledger, the index, the pinned run
record, and the report are scanned by a test for drive-letter paths, user and
temporary directories, scratch directories, and paths into a planning directory. Every
commit identifier the change writes is one this repository's history or its committed
records already carry.

## What was not run, and why

- **None of the five reruns that would close a blocker.** Each needs a real model, a
  Kubernetes cluster, or both — the local baseline, the kind helper, a Helm install and
  uninstall with Terraform teardown, an upgrade rollback, and a pod replacement — and
  none was authorised for this change. [The report](v1-s5-006-pr2-evidence-completeness.md#the-release-blockers)
  gives the exact procedure for each.
- **No run to confirm the telemetry mechanism.** Confirming it needs a collector run
  that records each query's samples and timestamps; the report records the mechanism as
  a candidate.
- **No continuous-integration run was promoted.** No claim's support changed on the
  strength of a hosted result.

## Authorisation

Not required. This change read committed files and the repository's history, ran
committed test suites in process, wrote documents, data, code, and tests, and contacted
nothing outside the repository.
