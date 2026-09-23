# V1-S5-011-PR2 validation: the versioned evidence-record data model

Change: a published schema for the next version of the claim and evidence register at
[`docs/testing/claim-evidence-matrix.v1alpha2.schema.json`](../../testing/claim-evidence-matrix.v1alpha2.schema.json),
the document explaining it at
[the claim and evidence data model](../../testing/evidence-record-model.md), a
compatibility reader at [`tools/evidence_model`](../../../tools/evidence_model/),
thirty committed fixtures with a refusal matrix, and
[a suite](../../../tests/testing/test_evidence_record_model.py) that holds the schema
to what `V1-S5-011-PR1` decided a level is. This record says what was run, what it
found, and what none of it supports.

**Evidence class: `local-static`.** Every command this change executed reads committed
files and contacts nothing else. **No cluster was contacted.** No release was
installed, upgraded, rolled back, or uninstalled, no Terraform ran, no forward was
opened, no model was loaded, and no completion was generated. No cluster run was
authorised for this change and none would have established anything about it: the
change publishes a shape.

**Nothing is reclassified, and no register is migrated.**
[`claim-evidence-matrix.v1alpha1.json`](../../testing/claim-evidence-matrix.v1alpha1.json)
is byte-for-byte unchanged. No claim status, certification level, evidence class, or
evidence reference moves. `contracts/`, `src/`, `charts/`, `deploy/`, `infra/`, and
`scripts/` are unchanged. Four files under `tools/` are touched and none is the
register's writer: two are the new [`tools/evidence_model`](../../../tools/evidence_model/)
package, and two are [`tools/proof_dashboard`](../../../tools/proof_dashboard/), whose
`core.py` gains a version guard and whose `__init__.py` re-exports the constant it
added. The guard is described below. (This paragraph said "one file" until the
independent review counted them.)

**One dated evidence record is annotated, and none is rewritten.** Three files under
[`docs/proof/`](../) change. Two are not records: this one, which is new, and
[the evidence index](../README.md), which gains a row for it. The third is
[the `V1-S5-011-PR1` record](v1-s5-011-pr1-validation.md), which predicted that this
change would fire a tripwire it did not fire. Its text is left exactly as written and a
dated note is added beside it, which is the same treatment ADR 0005 D4 received from
`V1-S5-011-PR1`: a record is evidence about what was believed when it was made, and
editing it to be currently correct destroys the only thing it is good for.

## What the change is

**A version, chosen and justified.** `v1alpha2`. The change removes a required field
from the claim object, moves a field's meaning to a different object, and makes every
currently valid document invalid, which is *breaking* by
[the compatibility rules this repository publishes](../../contracts/workload-contract.md).
Those rules deliberately decline the usual alpha convention: a breaking change gets a
new version string even at alpha maturity, because a contract that can be redefined
under a stable identifier is not enforced. `v2alpha1` was rejected for saying something
false — that a stable `v1` existed and is being left behind. None ever did.

**The structural change, not a rename.** `claim.certificationLevel` does not become
`claim.evidenceLevel`. The claim object has no level property at all and refuses
unknown ones; a level sits on each entry of `claim.evidenceRecords[]`, and a claim may
hold several at several levels. The cheap migration — rename the field, keep it on the
claim, declare the model versioned — would have preserved every defect
[ADR 0016](../../architecture/decisions/ADR-0016-inferops-evidence-level-model.md)
identified and added a version number to it. A test asserts the schema contains no
property named `certificationLevel` anywhere outside the block whose only purpose is
to carry a legacy value.

**What a record can now answer.** What claim it supports; its level; which components
executed; which were substituted and whether each substitution was material to the
claim; where the workload came from and whether it was declared representative; the
environment, provider, and hardware class; versions and digests; the commands or the
workflow; the measurement method and the observation period; the acceptance criteria
and whether each was registered before the run; the actual results; the evidence
references; the limitations; and what the result does not establish.

**Substitution and workload origin are different objects.** `execution.substitutions[]`
carries `claimMaterial`; `workload.source` carries where the input came from. Neither
constrains the other, which is [ADR 0016 D3](../../architecture/decisions/ADR-0016-inferops-evidence-level-model.md)
expressed as a shape rather than as a sentence. Both directions are committed: a
record with `workload.source: "synthetic"` and no claim-material substitution validates
at `C2`, and the same run classified `C1` on the strength of its generated input is
refused for naming no claim-material substitution.

## What the schema enforces, and what it cannot

| Requirement | Enforced by the schema | Left to review |
|---|---|---|
| A level belongs to a record | yes — the claim object has no level property and refuses unknown ones | — |
| Several records per claim | yes — `evidenceRecords[]` | — |
| `C0` executed nothing of the target behaviour | yes — `targetBehaviourExecuted` is `false` | whether the behaviour identified is the one the claim is about |
| `C1` requires a claim-material substitution | yes — `substitutions[]` must contain one | whether a substitution really was material |
| `C2` and above allow none | yes | the same judgement, in the other direction |
| `C3` requires declared representativeness and written assumptions | yes | whether the workload really represents intended use |
| `C3` criteria were registered before the run | the flag is required | whether the flag is true |
| `C4` requires production, a depending workload, and a period | yes | everything about whether the claim is honest |
| A record states limitations and what it does not establish | yes — both non-empty for a migrated record | whether they are the right ones |
| A record names what executed | yes — non-empty `executedComponents` whenever the target behaviour ran | whether the components named are the ones the claim needs |
| A record says where its input came from | yes — `workload` is required of every migrated record | whether the description is accurate |
| A record can be repeated | yes — `versions[]` or `versionsRecordedIn`, and a non-empty `procedure` | whether the commands still work |
| A record cites something a reader can open | yes — non-empty `evidenceRefs` for a migrated record | whether the artifact says what the record says it says |
| `C4` documents what the window did not cover | yes — non-empty `knownGaps` | whether the gaps listed are the real ones |
| No evidence is reclassified by the transformation | yes — an unmigrated record may carry no level | — |

**This is enforced over documents that declare `v1alpha2`, and none is committed.**
The rules above apply to fixtures. Applying them to committed evidence is
`V1-S5-012-PR1`; reading each existing record against the current definitions is
`V1-S5-012-PR2`.

**The class ceilings are carried, not re-enforced.** `v1alpha1` gives every evidence
label a ceiling, in `evidenceLabels[].ceiling` of
[the register itself](../../testing/claim-evidence-matrix.v1alpha1.json), enforced by
[`tests/testing/test_claim_evidence_matrix.py`](../../../tests/testing/test_claim_evidence_matrix.py)
and by the proof dashboard's `a-level-may-not-exceed-its-labels-ceiling` rule. A third
rule of the same shape — `evidenceClasses[].maxCertification` in
[`test-strategy.v1alpha1.json`](../../testing/test-strategy.v1alpha1.json) — constrains
a test *layer* instead. None of the three moves here.

They come into `v1alpha2` as `legacyCeiling`, which the schema stores and applies to
nothing, for two reasons: a ceiling constrains what a test layer or a whole claim may
certify rather than how one *record* was obtained, and the `synthetic` ceiling in
particular is the rule ADR 0016 D3 records as too broad. Copying it forward under a new
name would have carried the defect and made it look freshly decided.

**Which matters for the ordering of `V1-S5-012`.** The two register-bound guards read
`claim.certificationLevel` and `evidenceLabels[].ceiling`, and `v1alpha2` has neither,
so they stop applying the moment the register is migrated. `V1-S5-012-PR2` therefore
cannot migrate and leave the guard running: its replacement, `V1-S5-012-PR1`, has to
land first. Earlier drafts of this record and of
[the model document](../../testing/evidence-record-model.md) named only the strategy
file and said the ceilings were enforced "where they always were", which was both the
wrong file and an implication that the guard survives the migration. The independent
review found it.

## The compatibility path

[`tools/evidence_model`](../../../tools/evidence_model/) reads the committed
`v1alpha1` register and produces a `v1alpha2` document **in memory**. It writes
nothing, and no generated register is committed.

It follows three rules, and all three are tested:

1. **Every record it produces is `legacy-unmigrated` and carries no `evidenceLevel`.**
   The superseded `certificationLevel` is kept verbatim under `legacyClassification`
   together with a note saying it has not been re-examined and the record that
   publishes what it used to mean.
2. **One record per claim, not one per cited path.** `v1alpha1` gave the claim a single
   level covering every record it named; splitting the row would hand each path a level
   nothing ever assigned to it individually.
3. **A claim that cited no record keeps its label.** Fourteen rows name no evidence and
   still carry `documented-unexecuted`, `estimated`, or `production-experience`. A
   label with no record is a statement about an absence, and it is carried on the claim
   rather than dropped for having nowhere to hang.

**The read, over the committed register:** 59 claims in, 59 claims out, 45 evidence
records produced, all 45 `legacy-unmigrated` with a null level, 14 claims carrying a
claim-level `legacyClassification`, and 0 refusals from the schema.

**Nothing is lost, and it is checked rather than asserted.** `LEGACY_FIELD_DESTINATIONS`
names where each of the twenty fields of a `v1alpha1` claim row lands. One test walks
the committed register's own keys against it in both directions, and a second checks
that every named destination is a property the schema actually has.

## The one consumer change

[The proof dashboard](../dashboard.md) gains a rule and nothing else:
`a-register-declares-a-version-the-page-can-read`. It refuses to render from a register
whose `contractVersion` it does not implement.

This is the smallest change that makes the migration safe to perform later. Every value
the page prints is read out of the `v1alpha1` shape. A renderer pointed at a `v1alpha2`
register would find no `certificationLevel` and no `evidenceLabel` on a claim, print
empty cells, and produce a page that looked merely incomplete rather than wrong. The
rule turns that into a refusal. The committed page is unchanged — regenerating it
produces the same bytes, which the existing suite checks — because the register it
renders from has not moved.

## What the checks caught

**The register's own `limitations` block is a list of sentences, not of objects.** The
first draft of the schema typed it as an array of objects by symmetry with
`prohibitions`, and the reader refused the committed register on its own data. Caught
by running the transformation against the real file rather than against a fixture,
which is the argument for doing it in that order.

**A fixture that proves nothing.** An early version of
`test_no_fixture_asserts_that_v1_holds_c3_or_c4_evidence` ended in a disjunction whose
second branch was true by construction, so the assertion could not fail. It was
replaced with two checks that can: the model document states in words that no evidence
here is `C3` or `C4`, and the committed register is read for the values rather than
trusted not to have acquired them.

**A schema that let `C2` mean nothing in particular.** The first draft required no
component to be named as having executed, no workload object outside `C3`, no immutable
identifier at any level, no non-empty `evidenceRefs`, and no documented known gaps at
`C4`. A record could therefore be classified `C2` — *the actual components required to
evaluate the claim executed* — while naming no component, no input, no version, and no
artifact a reader could open, and `C4` while saying nothing about what the observation
window failed to cover. The specification's own sentence about what every record states
was the thing the schema was supposed to encode, and it did not. Two independent reviews
of this change found it before it was pushed: one by construction, probing the schema
for documents that should be refused and are not, and one by reading the schema against
the specification. Five rules were added, five refused fixtures now drive them, and two
tests assert the requirements against the schema directly rather than only through the
fixtures.

## Commands and results

Run from the repository root on Windows, in Git Bash, against the staged tree.

| Command | Result |
|---|---|
| `python -m pytest tests/testing/test_evidence_record_model.py -q` | 119 passed |
| `python -m pytest tests/testing/test_evidence_levels.py -q` | 40 passed |
| `python -m pytest tests/testing/test_proof_dashboard.py -q` | 173 passed |
| `python -m pytest tests/testing/test_test_inventory.py -q` | 909 passed |
| `python -m pytest tests/testing/test_claim_evidence_matrix.py -q` | 1824 passed |
| `python -m pytest tests/testing/test_document_links.py -q` | 219 passed |
| `python -m pytest tests/testing tests/architecture -q` | 7482 passed, 6 skipped |
| `python -m pytest tests/telemetry -q` | 1218 passed, as `CONTRIBUTING.md` requires of a change touching `docs/proof/README.md` |
| `python -m pytest -q` | 13057 passed, 33 skipped, 14 deselected |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 484 files already formatted |
| `uv run mypy` | Success: no issues found in 266 source files |
| `git diff --cached --check` | clean |
| Trailing-whitespace and hard-tab scan over 218 tracked Markdown files | none found |

The fourteen deselected tests are the `cluster`, `realruntime`, `failure`, and
`load` markers, which `pytest.ini` deselects by default. None of them was run, and
none would have established anything about this change.

**The compatibility read, executed against the committed register:** 59 claims in,
59 claims out, 45 evidence records produced, all 45 `legacy-unmigrated` with a null
`evidenceLevel`, 14 claims carrying a claim-level `legacyClassification`, and 0
refusals from the schema. Every one of the twenty fields of a `v1alpha1` claim row
resolved to a declared destination that the schema has.

## What this record does not establish

- **That any evidence is classified correctly.** No record was read against the
  definitions. The suite establishes that a shape exists, that it is internally
  consistent, and that the committed register survives a transformation into it.
- **That the `C3` and `C4` fixtures describe anything this project has.** They are
  shapes. Nothing in the register reaches either level under either vocabulary, and a
  test asserts that rather than assuming it.
- **That the schema's booleans and strings are true.** Whether a substitution was
  material, whether the components named as executed are the ones the claim needs,
  whether a workload represents intended use, and whether a criterion was registered
  before a run are four judgements a validator reads as flags and names. The shape
  makes them impossible to omit; it cannot make them honest.
- **That the register will migrate cleanly.** The reader demonstrates that the *fields*
  transfer. Which level each record actually holds under the current definitions is a
  separate reading, claim by claim, and it is `V1-S5-012-PR2`.
- **That two versions are supported.** They are not. There is one register, it is
  `v1alpha1`, and the reader exists for the migration and its review.

## Related records

| Topic | Document |
|---|---|
| The definitions this model represents | [InferOps Evidence Levels (C0–C4)](../../testing/evidence-levels.md) |
| The decision that made a level a record's property | [ADR 0016](../../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) |
| The validation of the change that defined them | [`v1-s5-011-pr1-validation.md`](v1-s5-011-pr1-validation.md) |
| The model this record validates | [The claim and evidence data model, `v1alpha2`](../../testing/evidence-record-model.md) |
| The register that has not moved | [Claim and evidence matrix](../../testing/claim-evidence-matrix.md) |
| The page whose renderer gained the version guard | [The V1 proof dashboard](../dashboard.md) |
