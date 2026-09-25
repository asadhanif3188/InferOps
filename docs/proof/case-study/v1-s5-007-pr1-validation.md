# V1-S5-007-PR1 — validation of the draft V1 engineering case study

Date: 2026-09-25

Change: a **draft** of [the V1 engineering case study](../../case-study/v1-engineering-case-study.md),
[its data file](../../case-study/v1-engineering-case-study.v1alpha1.json), and
[`tests/testing/test_case_study.py`](../../../tests/testing/test_case_study.py), which
holds the draft to the register and to the records whose figures it quotes.

This record describes a documentation change. Nothing it describes was executed for it:
no cluster was contacted, no model was loaded, no runtime was started, and no record
under `docs/proof/` other than this one was written or changed. Every figure the draft
quotes was already committed. The draft certifies nothing, and no claim's status and no
record's level moved.

## Why it is a draft, and what it may be used for

[The completeness check](../testing/v1-s5-006-pr2-evidence-completeness.md) holds the
V1 evidence pack **not frozen** on five release blockers, and its ledger names
`V1-S5-007` among the stories that may not consume the pack as frozen. This change does
not consume it as frozen. It drafts the narrative against the evidence as it stands,
names the five blocked claims wherever the draft leans on them and in its appendix, and
leaves verification against a frozen pack and publication to the next change. The test
holds the page to that: while the gate is incomplete, or while the ledger still lists
this story as blocked, the page's status must read **draft**.

What the draft may be used for today: reviewing the narrative, the structure, and the
choice of evidence. What it may not be used for: citing as a published account of V1,
or as evidence for any claim.

## What changed

| File | Change |
|---|---|
| `docs/case-study/v1-engineering-case-study.md` | New. The draft, in thirteen sections and a claims appendix |
| `docs/case-study/v1-engineering-case-study.v1alpha1.json` | New. The claims each section cites, and the source of each of the 22 quoted figures |
| `tests/testing/test_case_study.py` | New. 131 tests over the draft, its data file, the register, the evidence index, the completeness ledger, and the quoted records |
| `docs/testing/test-inventory.v1alpha1.json`, `docs/testing/test-inventory.md`, `tests/testing/test_test_inventory.py` | The new module registered in the `documentation` layer, which now holds forty-one modules, and in the list of modules that defend no claim, which now holds forty-three |
| `tests/testing/test_evidence_completeness.py` | One test repaired, because it failed on `main` before this change; see [a failure on `main` this change repairs](#a-failure-on-main-this-change-repairs) |
| `docs/proof/README.md` | A `Case study` row indexing this record |
| `CHANGELOG.md` | One entry under `Unreleased` |
| `docs/proof/case-study/v1-s5-007-pr1-validation.md` | This record |

Nothing under `src/`, `tools/`, `charts/`, `infra/`, `deploy/`, or `scripts/` changed, and
neither did the register, the ledgers, the index, the proof dashboard, or any dated
record.

## The outline

1. **Why LLM serving needs a paved road** — six things this project had to learn on its
   own host before a completion could be called evidence, each tied to a record.
2. **Who it is for, and what bound it** — the workload owner, the operator, and the
   reviewer; the host, the no-paid-API rule, the operator-owned cluster, and the rule
   that nothing is published without its evidence.
3. **The architecture and the self-service contract** — the contract, the domain, the
   adapters, the API, the chart and prerequisites, and the one unbuilt component,
   deployment rendering.
4. **Choosing a runtime and a model** — the pre-registered thresholds, the alternatives,
   and the one blocking threshold that failed and was argued past.
5. **Local and Kubernetes implementation** — the local certification, the paved road,
   the clean-clone journey, and the four lifecycle claims that are release blockers.
6. **How a claim becomes publishable** — the register's chain from statement to
   limitation, status apart from level, the counts, and the gate.
7. **Experiments and what they found** — declared load, pod loss, the unready model, and
   the clean-clone run.
8. **Telemetry** — what the signals showed, and the list of what they cannot.
9. **Cost** — the method, the synthetic rate card, and the three findings about
   measured use that survive invented prices.
10. **The security boundary** — what is not defended, and the narrower things that are
    enforced.
11. **Trade-offs and the alternatives not taken** — nine decisions, each with what the
    selection costs.
12. **What V1 does not prove** — every uncertified claim and every release blocker.
13. **What evidence would justify a second version** — evidence, not scope.

## Evidence used

Every figure is read from one of ten committed files, and the data file names which:
eleven by JSON pointer from the local certification result, the performance findings,
the pod-recovery record, and the unready-model record; eleven verbatim from the
clean-clone run, the performance findings, the pod-recovery record, the cost baseline,
the feasibility record, and ADR 0002.

The draft cites 55 of the register's 59 claims: 38 certified, 7 planned, 1 deferred, and
9 not claimed, including all five release blockers. Four certified claims are not cited,
because the narrative does not rest on them: the developer quick start on a clean
checkout, the model lifecycle comparison, and the two troubleshooting guides. Beyond the
records, it reads ADRs 0002, 0004, 0007, 0011, 0012, 0013, 0014, and 0016, the system
architecture, the project boundaries, the evidence-level specification, the evidence
index, and the security baseline.

## Missing narrative inputs

These are what the final version needs and this draft could not supply:

- **The decision on the five release blockers.** Each is a re-run at a named commit or a
  status decision, and either changes what sections 5, 6, and 12 may say.
- **A frozen evidence pack and its digest.** The final version should cite the pack it
  was verified against by its `evidenceSetSha256`, which is only meaningful once frozen.
- **A reader who is not the author.** No second engineer has followed the clean-clone
  journey, and nobody but the author has read the draft. Section 13 names the first as
  evidence; the second is an editorial input.
- **The final diagrams.** The draft carries one ASCII diagram, in the repository's
  convention. Whether the published version also uses the committed architecture image,
  and a diagram of the failure shapes, is undecided.
- **Where it is published.** Publication, and any external announcement, need their own
  authorisation, which this change did not have.

## Claims and statements needing final verification

- **The five blocked claims**, cited in sections 5 and 12: the local serving baseline,
  the `kind` helper, the Helm uninstall's survival clause, the upgrade and rollback, and
  the pod replacement. The draft quotes no figure from any of them.
- **Paraphrases of records.** Every figure reads back, but the sentences around them are
  readings. The ones most worth a second reading: the attribution of the degradation
  point in section 7, which the record says is correlated and not established; the
  explanation of why no caller met `model-not-ready`, in section 7; and the cost
  findings in section 9, whose third point restates a record's refusal rather than a
  figure.
- **Two figures anchored to a decision record rather than a proof record**: the
  1.71 GiB model size and the 7.60 GiB container memory, both read from ADR 0002. The
  final version should re-anchor them to the records ADR 0002 quotes.
- **Section 4's alternatives.** Every rejection there was read from documentation, and
  the draft says so; the final version should keep that qualifier beside each.
- **Section 13.** Every item is phrased as evidence rather than scope, and the final
  version should keep it that way: whether a second version proceeds is a separate
  decision.

## A sentence this change leaves stale, deliberately

[The claim and evidence register](../../testing/claim-evidence-matrix.md) says, in its
limitations and in what it does not cover, that the case study "has not been written",
and that "a future case-study claim with no row here would be caught by nothing". A
draft now exists and a test now catches an unregistered claim in it. The register is
not edited here: an edit to it needs an operation in a ledger, the evidence pack is
under a freeze decision, and whether the sentence becomes "a draft exists, unpublished"
or is removed depends on publication. It is carried to the change that publishes the
case study, together with the README entry point, which must be governed by a register
row or listed as a surface that claims nothing.

## A failure on `main` this change repairs

The first run of the documentation suites on this branch, before any commit, failed one
test that is not this change's:
`test_the_report_states_the_largest_committed_object_and_no_model_artifact`, in
`tests/testing/test_evidence_completeness.py`. The branch had no commit of its own, so
the tree it read was `main`'s, and it fails there too.

The cause is `4fd96a4`, committed to `main` after `V1-S5-006-PR2` merged, which added
the 1 327 803-byte architecture image. The test read "the largest committed object"
from `HEAD` and required [the completeness report](../testing/v1-s5-006-pr2-evidence-completeness.md)
to state its size. The report is a dated record: its sentence, that the largest tracked
file was the runtime image's bill of materials at 882 177 bytes, was true of the tree it
was published in and is no less true now. The test, not the record, was wrong.

The repair keeps both halves of what the test was for. The absence of any model
artifact is still checked on `HEAD`. The stated size is checked against the committed
object of the file the report names, on `HEAD`, which needs no history, since the
default lane's checkout is shallow; and where history exists, the test finds the commit
that last changed the report and checks that the named file was the largest object in
that tree. The report is not edited.

## How the checks were shown to bite

Six mutations were made to working copies of the draft and its data file, the suite run
against each, and the files restored. Each failed exactly the test it was aimed at:

| Mutation | Test that failed |
|---|---|
| A duration with no declared source added to the prose | `test_no_measurement_is_quoted_without_a_declared_figure` |
| A release blocker's appendix row changed to `no` | `test_each_appendix_row_is_what_the_register_and_the_ledger_say` |
| An amount from a cost result quoted | `test_the_case_study_quotes_no_amount_from_a_cost_result` |
| A figure changed in both the page and the data file | `test_every_figure_reads_back_from_the_file_it_names` |
| The status line changed from draft to published | `test_the_case_study_stays_a_draft_while_the_release_gate_is_incomplete` |
| A not-claimed claim removed from section 12 | `test_each_section_cites_exactly_the_claims_it_declares` |

## Validation

From Git Bash at the repository root, with every file of this change staged so that
the suites that read `git ls-files` see it:

```text
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked python -m mypy
uv run --locked python -m pytest tests/testing/test_case_study.py -q
uv run --locked python -m pytest tests/testing tests/security -q
uv run --locked python -m pytest -q
uv run --locked python -m tools.evidence_index --gate
git diff --cached --check
```

Results are recorded in [the results section](#results).

### Results

On 2026-09-25, on one Windows host, before the first commit:

| Command | Result |
|---|---|
| `ruff format --check .` | 505 files already formatted |
| `ruff check .` | All checks passed |
| `python -m mypy` | No issues in 275 source files |
| `pytest tests/testing/test_case_study.py -q` | 131 passed |
| `pytest tests/testing tests/security -q` | 7340 passed |
| `pytest -q`, the default lane | 14954 passed, 33 skipped, 14 deselected, in 23 min 2 s |
| `python -m tools.evidence_index --gate` | `INCOMPLETE V1-S5-006: 5 release blockers`, exit 1, as intended |
| `git diff --cached --check` | Clean |

The Helm and Terraform gates were not run: nothing under `charts/` or `infra/` changed.

## Privacy and publicability

The staged diff was searched for a drive-letter or home-directory path, a scratch
directory, an e-mail address, a credential-shaped string, and the name of any private
planning document. None is present. No model artifact, generated render, or machine
state is added.

## Acceptance criteria

For this change:

| Criterion | State |
|---|---|
| Explains why LLM serving needs a paved road | Drafted, in section 1, from this project's own records |
| Connects architecture to measured reliability and bounded, provider-labelled performance evidence | Drafted, in sections 3, 5, and 7, every performance and recovery figure read from a record under `docs/proof/` and published under ADR 0013 |
| Cost limited to the synthetic method; no real-provider cost figure | Met, and held by a test that refuses any amount from a cost result |
| States constraints and alternative decisions | Drafted, in sections 2, 4, and 11 |
| Contains no fabricated or generalized result | Every figure reads back from a committed file; whether the prose generalizes is a reading, carried to final verification |
| Uses the current `C0`–`C4` meanings, with environment, workload, and failure kept apart | Drafted, in section 6; the repository's existing checks refuse a superseded pairing anywhere |
| Explains what evidence would justify a second version | Drafted, in section 13 |

For the parent story, the sign-off against a frozen evidence pack is **not met**: the
pack is not frozen, and this change does not ask for sign-off.

## Not run

No real model, runtime, Kubernetes cluster, or destructive experiment was run, and none
was authorised. No paid service was used. Nothing was tagged, released, or published.
