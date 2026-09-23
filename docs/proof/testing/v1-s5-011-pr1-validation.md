# V1-S5-011-PR1 validation: the InferOps evidence-level model

Change: an authoritative definition of the InferOps Evidence Levels at
[`docs/testing/evidence-levels.md`](../../testing/evidence-levels.md), the decision
that accepts it at [ADR 0016](../../architecture/decisions/ADR-0016-inferops-evidence-level-model.md),
a dated amendment note on [ADR 0005](../../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
D4, a supersession banner on [the certification document](../../testing/certification.md),
and [a suite](../../../tests/testing/test_evidence_levels.py) that refuses a second
current definition. This record says what was run, what it found, and what none of it
supports.

**Evidence class: `local-static`.** Every command this change executed reads committed
files and contacts nothing else. **No cluster was contacted.** No release was
installed, upgraded, rolled back, or uninstalled, no Terraform ran, no forward was
opened, no model was loaded, and no completion was generated. No cluster run was
authorised for this change and none would have established anything about it: the
change decides what five identifiers mean.

**Nothing is reclassified, and nothing product-facing changes.** `contracts/`, `src/`,
`charts/`, `deploy/`, `infra/`, `scripts/`, and `tools/` are byte-for-byte unchanged.
No claim status, certification level, evidence class, or committed record moves. The
claim register, the proof dashboard, and the CI gate matrix are untouched.

**No dated evidence record is edited.** Two files under [`docs/proof/`](../) change
and neither is a record: this one, which is new, and
[the evidence index](../README.md), which gains a row for it and a paragraph saying
that every record it indexes was classified under the superseded meanings and that
none has been re-examined. An earlier draft of this record and of the changelog said
"no file under `docs/proof/` is edited", which was false of the index; the
independent review before this change landed caught it.

## What the change is

**One authoritative definition, and a mapping out of the old one.** `C0` to `C4` now
name Static, Substituted Execution, Runtime, Representative, and Operational Evidence
— one axis, *how was this evidence obtained*. The superseded meanings were Schema,
Mock, Real controlled, Failure, and Composed. The first three map conceptually. The
last two do not map at all, and that is the defect being fixed: failure names what an
experiment was for and composition names what the path was, and neither is a strength.

**The old ladder was safe only because its top two rungs were unreachable.** Under
ADR 0005 D4, `C3` and `C4` were placed out of V1 scope and a test refuses an active
claim requiring either. That is why the repository never actually recorded a mocked
failure experiment as outranking a real completion — not because the ranking was
right, but because nothing was allowed to use it.

**Three things the specification separates that the certification document did not.**
An evidence *level* belongs to one evidence record; an evidence *class* belongs to a
test layer and carries the enforced ceiling; a claim's *status* is a publishing
decision. One claim may be supported by several records at different levels, and the
weaker ones are kept as the history of how confidence was built.

**Synthetic input is separated from substitution.** `C1` is decided by one question —
was a component material to the claim replaced — and the origin of the workload does
not answer it. A generated request through the real API, adapter, runtime, and model
is evidence about all four.

## What is enforced, and what is not

This is the part most easily overstated, so it is stated as a table.

| Statement | Enforced by | Today |
|---|---|---|
| One document binds `C0`–`C4` to the current names | `test_only_the_specification_defines_the_current_levels` | yes |
| A current document states a superseded pairing only if registered | `test_a_current_document_states_a_superseded_meaning_only_if_registered` | yes |
| Any document stating a superseded pairing declares it superseded | `test_every_document_stating_a_superseded_meaning_declares_it_superseded` | yes |
| The surfaces awaiting migration carry the notice where a reader lands | `test_every_surface_awaiting_migration_opens_with_the_supersession_notice` | yes |
| The mapping and the project-defined disclaimer are published | `test_the_mapping_documents_publish_every_superseded_meaning`, `test_the_specification_denies_being_an_external_standard` | yes |
| ADR 0005 D4's accepted text is annotated, not rewritten | `test_the_prior_decision_is_amended_rather_than_rewritten` | yes |
| The new ADR has a valid owner and sign-off authority | `tests/architecture/test_decision_authority.py`, over the register | yes |
| `C1` requires a claim-material substitution | nothing | **no** |
| `C3` requires declared representativeness and acceptance criteria | nothing | **no** |
| `C4` requires production operation and an observation period | nothing | **no** |
| A synthetic workload is not forced to `C1` | nothing; the committed `synthetic → C1` ceiling still enforces the opposite | **no** |

The four unenforced rows are `V1-S5-012-PR1`. They are left unenforced deliberately:
the committed ceilings are the guard that stops a mock certifying real behaviour, and
removing a guard before its replacement exists would be the failure ADR 0005 D4 was
written to prevent. The current rule is stricter than intended, which is the safe
direction to be wrong in while the replacement is built.

**One test is a tripwire and is meant to fire.**
`test_the_enforcing_data_still_carries_the_superseded_names` asserts that
[`test-strategy.v1alpha1.json`](../../testing/test-strategy.v1alpha1.json) still
publishes Schema, Mock, Real controlled, Failure, and Composed, and that the
`synthetic` class still carries a `C1` ceiling. The specification tells a reader both
of those things. When `V1-S5-011-PR2` versions the data model, this test fails, and
the page that described the old state has to be corrected in the same change rather
than a later one.

## What the checks caught

**The first draft of the suite bound the wrong table cell.** The pattern matched an
identifier's first table row anywhere in a document, so it read the specification's
*current* level table when it meant to read the *mapping* table, and then asserted
that `C3 — Representative Evidence` should say "No direct mapping". Five tests failed
on it. The fixed form binds an identifier to a specific name in the second cell, which
is what "this document defines `C3` as *Failure*" actually looks like in Markdown.

**Two documents legitimately state the superseded pairing.** The scan for
`C3 Failure` and `C4 Composed` across every tracked Markdown file flagged
[the architecture index](../../architecture/README.md) and ADR 0005 — both of which
name the old pairing in order to say it is superseded. Rather than exempting them, the
rule was generalised: **any document that states a superseded meaning must contain the
word `superseded` and name ADR 0016 in the same document.** Five documents are
registered as allowed to, and a test refuses a sixth.

**The scan's first form was unusable.** Matching `C3` alone finds a decision-criterion
identifier in ADR 0015, a review-checklist item in the boundary checklist, and a
load-generation concurrency level; matching `Failure` alone finds a test layer and a
pytest marker. Only the pairing means anything, and the suite documents why.

## Commands and results

Run from the repository root on branch `docs/v1-s5-011-evidence-level-model`, in a
POSIX shell, with every file committed so that `git ls-files` sees them.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked ruff format --check .` | `479 files already formatted` |
| `uv run --locked python -m mypy` | `Success: no issues found in 263 source files` |
| `uv run --locked python -m pytest tests/testing/test_evidence_levels.py -q` | `38 passed` |
| `uv run --locked python -m pytest tests/testing tests/architecture -q` | `7350 passed, 6 skipped` |
| `uv run --locked python -m pytest -q` | `12923 passed, 33 skipped, 14 deselected` |
| `git diff --check main...HEAD` | no output |
| `git ls-files -z '*.md' \| xargs -0 grep -n '[[:blank:]]$'` | no match |
| `git ls-files -z '*.md' \| xargs -0 grep -n "$(printf '\t')"` | no match |

Both counts are from runs with every file committed. A run with an untracked file
produces a different count, because the link suite and this change's suite both
collect from `git ls-files`.

**One earlier full-suite run reported a failure and it was an artifact of how it was
run, not of this change.** Two `pytest` processes were running at once, and
`tests/serving/test_performance_scenarios.py::test_the_collector_is_asked_by_get_without_parameters_and_by_post_with_them`
failed in one of them. That test reads nothing this change touches, it passes on its
own, and the run recorded above — executed alone, on the committed tree — passes it
along with everything else. It is recorded here rather than dropped, because a
failure seen once and not explained is the kind of thing a later reader deserves to
find already answered.

**No cluster, model, or runtime command was run.** The `cluster`, `realruntime`,
`failure`, and `load` markers stay deselected by
[`pytest.ini`](../../../pytest.ini), as they are for every change that does not
authorise a cluster.

## What this record does not establish

- **That the definitions are good ones.** Every check here establishes that the
  repository states one definition consistently. Whether that definition carves
  evidence at a useful joint is a judgement, and no suite can hold it.
- **That any existing record is classified correctly.** Nothing was re-examined. Every
  committed record keeps the level it was given under the superseded meanings, and
  `V1-S5-012-PR2` reviews them claim by claim.
- **That the new rules hold of anything.** `C1`, `C3`, and `C4` have requirements and
  no validators. Until `V1-S5-012-PR1` they are enforced by review, which is the state
  this repository elsewhere refuses to describe as enforcement.
- **That the evidence-level model is recognised anywhere.** It is project-defined. No
  outside party has reviewed a decision, a claim, or a record in this repository, and
  naming a level does not change that.
- **Anything about a running system.** No model was loaded, no request was served, no
  cluster was contacted, and this change could not have established otherwise.

## Related records

| Topic | Document |
|---|---|
| The definitions this change publishes | [InferOps Evidence Levels (C0–C4)](../../testing/evidence-levels.md) |
| The decision that accepted them | [ADR 0016](../../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) |
| The decision whose D4 they amend | [ADR 0005](../../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md) |
| Evidence classes and the ceilings still enforced | [Certification levels and evidence classes](../../testing/certification.md) |
| Who signs that a claim matches its evidence | [Decision ownership and sign-off authority](../../governance/decision-authority.md) |
