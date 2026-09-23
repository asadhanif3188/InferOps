# The claim and evidence data model, `v1alpha2`

Status: **published schema, and the shape of the committed register.** The schema is
[`claim-evidence-matrix.v1alpha2.schema.json`](claim-evidence-matrix.v1alpha2.schema.json).
Since `V1-S5-012-PR2` the register this repository reads is
[`claim-evidence-matrix.v1alpha2.json`](claim-evidence-matrix.v1alpha2.json); the
`v1alpha1` register it was migrated from is kept unchanged, and
[the migration report](../proof/testing/v1-s5-012-pr2-migration-report.md) says how
every record in it was read.

> [!IMPORTANT]
> This document describes **shape**. What the levels mean is in
> [the evidence-level specification](evidence-levels.md), accepted by
> [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md),
> and it is the only document that defines them. Nothing here classifies a record,
> promotes a claim, or reclassifies anything.

## Why a new version exists

[ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) D2
decided that an evidence level is a property of an **evidence record**, and that one
claim may be supported by several records at several levels. Its own risk register
recorded the gap that left: `R4`, *the register cannot represent multiple records per
claim*, open and scheduled.

`v1alpha1` stores one `certificationLevel` and one `evidenceLabel` per claim. There is
no row in it for a claim that has static evidence, substituted-execution evidence, and
runtime evidence; the strongest value wins and the other two records disappear from the
data even though they are cited in the same row. That is not a field that needs
renaming. It is a shape that cannot hold the thing the specification describes.

## The version, and why this one

**`v1alpha2`.** Not `v2alpha1`, and not a redefinition of `v1alpha1`.

The change is **breaking** by the repository's own definition. It removes a required
field from the claim object, moves a field's meaning to a different object, and makes
every currently valid document invalid. [The workload contract](../contracts/workload-contract.md)
sets out what this project does with a breaking change, and the rule it states is
deliberately stricter than the usual alpha convention:

> A breaking change requires a new `apiVersion` — `v1alpha2` — even at alpha
> maturity. […] a contract that can be redefined under a stable identifier is not
> enforced, it is merely written down.

So `v1alpha1` keeps its file, its identifier, and its meaning, and the new shape gets
a new one. `v2alpha1` would say something different and false: that a stable `v1`
existed and is being left behind. There has never been a stable version of this
register, and the maturity suffix is the honest part of the string.

## Old shape and new shape

```text
v1alpha1                                  v1alpha2

claim                                     claim
  claimId, area, statement, status          claimId, area, statement, status
  assertsRealBehaviour                      assertsRealBehaviour
  certificationLevel   <- one level         evidenceRecords[]   <- many records
  evidenceLabel        <- one class           evidenceLevel     <- per record
  provider, environment                       execution         <- what ran,
  evidenceRefs[]                                                   what was replaced
  versionsRecordedIn                          workload          <- origin and shape
  limitation                                  environment       <- where
  doesNotEstablish                            versions[]        <- digests, revisions
  implementationRefs[], automatedTestRefs[]   procedure         <- commands or workflow
  ciGateIds[], readmeRefs[]                   measurement       <- method, period
  strategyClaimIds[], recordedCoverageGaps[]  acceptanceCriteria[]
  notClaimedReason                            results[]
                                              evidenceRefs[]
                                              limitations[]
                                              doesNotEstablish[]
                                          limitation, doesNotEstablish
                                          implementationRefs[], automatedTestRefs[]
                                          ciGateIds[], readmeRefs[]
                                          strategyClaimIds[], recordedCoverageGaps[]
                                          notClaimedReason
```

What moved, and what deliberately did not:

| | `v1alpha1` | `v1alpha2` |
|---|---|---|
| Evidence level | `claim.certificationLevel` | `claim.evidenceRecords[].evidenceLevel` |
| Records per claim | one implied row, several cited paths | `evidenceRecords[]`, each with its own level |
| Claim status | `claim.status` | `claim.status`, unchanged and still separate |
| What ran | not represented | `execution.executedComponents[]` |
| What was replaced | implied by the evidence label | `execution.substitutions[]`, each with `claimMaterial` |
| What the claim depends on | not represented | `claim.claimMaterialComponents[]`, optional, added by `V1-S5-012-PR1`; required by the validator of a claim holding a record at `C1` or above |
| Workload origin | folded into the `synthetic` label | `workload.source`, with `representativeness` beside it |
| Environment, provider, hardware | three claim fields | `environment`, on the record |
| Versions and digests | a path to a record that names them | `versions[]` *and* `versionsRecordedIn` |
| Measurement and observation period | not represented | `measurement`, with `observationPeriod` |
| Acceptance criteria | not represented | `acceptanceCriteria[]`, each saying whether it was declared before the run |
| Results | not represented | `results[]` |
| Limitations | one sentence on the claim | one sentence on the claim, **and** `limitations[]` per record |
| Evidence class | `claim.evidenceLabel` | `evidenceClasses[]` vocabulary, kept as its own dimension |
| Class ceiling | `evidenceLabels[].ceiling`, enforced | `evidenceClasses[].legacyCeiling`, carried, **never** applied to an `evidenceLevel`; since `V1-S5-012-PR1`, applied to carried legacy values only |

### The three separations the shape enforces

**A level belongs to a record.** `claim` has no `evidenceLevel` property and refuses
unknown ones, so the one-level-per-claim shape cannot be reintroduced by adding a
field. The strongest level a claim holds is for a reader to derive; nothing stores
it, and nothing committed derives it yet either — the proof dashboard still reads
`v1alpha1`, which is why it gained a version guard rather than a second code path.

**Substitution decides `C1`; workload origin decides nothing.** `execution.substitutions[]`
carries `claimMaterial`, and `workload.source` carries where the input came from. They
are different objects and neither constrains the other. A record with
`workload.source: "synthetic"` and no claim-material substitution validates at `C2`,
`C3`, or `C4`; a record classified `C1` must name the claim-material substitution that
put it there. Both directions are committed fixtures.

**Claim status is not an evidence level.** `status` stays on the claim and takes its
four values unchanged. A `not-claimed` claim may still hold a record, because an
absence somebody measured is worth more than one nobody mentions.

### What each level requires of a record

The schema encodes the parts of [the specification](evidence-levels.md) that are
structural. It does not encode the parts that are judgements.

Every record that declares itself `migrated` — that is, every record carrying a
level at all — must state what executed, where its input came from, where it ran,
how to run it again, at least one immutable identifier or the record that names
them, at least one artifact a reader can open, its limitations, and what it does
not establish. Those are the sentences
[the specification](evidence-levels.md#what-a-level-does-not-carry) says a record
states, and they are required rather than encouraged.

On top of that, per level:

| Level | What the shape requires |
|---|---|
| `C0` | `execution.targetBehaviourExecuted` is `false` |
| `C1` | something executed and is named, and `substitutions[]` contains a `claimMaterial` one |
| `C2` | something executed and is named, and no substitution is `claimMaterial` |
| `C3` | everything `C2` requires, plus declared representativeness with written assumptions, a measurement method, results, and acceptance criteria registered **before** the run |
| `C4` | an `organizational-production` environment, a `productionContext` naming the organization and the workload that depended on the system, a stated observation period, documented known gaps, and results |

**What it cannot check.** Four judgements: whether a component was *really* material to
a claim, whether the components named as having executed are *really* the ones the
claim needs, whether a workload is *really* representative of intended use, and whether
a criterion was *really* registered before the run. A validator reads all four as flags
and names.
The shape makes them impossible to leave out. It cannot make them true.

**The rules the schema cannot express now exist as checks.** `V1-S5-012-PR1` added a
validator, in [`tools/evidence_model/rules.py`](../../tools/evidence_model/rules.py),
for the rules that compare two fields of a record, a record with its claim, or a claim
with its register, and published [the rule catalogue](evidence-level-rules.md) saying
which of the schema, the validator, or review enforces each of forty-three rules. The
first of the four judgements above moved as a result: a claim now declares its
claim-material components once, in the optional `claimMaterialComponents` field, and
every record is held to that declaration rather than to its own `claimMaterial` flags.
Whether the declaration is right is still a judgement; the other three are unchanged.
Since `V1-S5-012-PR2` the committed register declares `v1alpha2`, so all of this
governs committed evidence, and the register's suite holds every record to it.

The first draft of this schema made four of those sentences optional at every level, so
a record could be classified `C2` while naming no component that ran, no workload, no
immutable identifier, and no artifact a reader could open. Two independent reviews of
the change that published it found the gap, and the refused fixtures beside
[the suite](../../tests/testing/test_evidence_record_model.py) now drive each rule over
a record built to break it.

**No evidence in this repository is `C3` or `C4`.** The fixtures at those levels are
shapes, committed so that the model can express a level before anybody needs it rather
than being extended under pressure by whoever needs it first. Nothing in the register
reaches either level under either vocabulary, and a test asserts that rather than
assuming it.

## The compatibility path

There are two versions and one register. Since `V1-S5-012-PR2` the register is
`v1alpha2` and every consumer reads it. The `v1alpha1` file is kept unchanged as the
point the migration started from, and nothing reads it as current.

Before the migration there was a **reader**, [`tools/evidence_model`](../../tools/evidence_model/),
which produces a `v1alpha2` document from the `v1alpha1` register in memory. It writes
nothing. Its job was to make the migration reviewable as a transformation before it
was performed as an edit, and it still does that for anybody comparing the two.

It is deliberately dull, and the three rules it follows are the interesting part:

1. **Every record it produces is `legacy-unmigrated` and carries no
   `evidenceLevel`.** The superseded value is kept verbatim under
   `legacyClassification`, together with the record that publishes what it used to
   mean. Writing `evidenceLevel = certificationLevel` would restate the forty-three
   classifications the register holds in a vocabulary they were not made in. For a
   `C3` or `C4` value it would be worse still, because the old meaning has no
   counterpart at all — there is no such value in the register today, so that half of
   the objection is about the value somebody adds next rather than about anything
   committed.
2. **One record per claim, not one per cited path.** `v1alpha1` gave the claim a
   single level covering every record it named. Splitting the row would hand each
   cited path a level nothing ever assigned to it individually.
3. **A claim that cited no record keeps its label anyway.** Fourteen rows name no
   evidence and still carry `documented-unexecuted`, `estimated`, or
   `production-experience`. A label with no record is a statement about an absence,
   so it is carried on the claim rather than dropped for having nowhere to hang.

Nothing is enriched. A field the `v1alpha1` row does not contain is absent from the
record it produces, and `legacy-unmigrated` is what says so. That is the difference
between a record whose environment is unknown and a record whose environment is
`repository-only` because somebody guessed.

**Is the reader temporary?** Yes. It existed for the migration and for the review of
it. `V1-S5-012-PR2` has read each record against the current definitions and written the
`v1alpha2` register, and the two versions do not run side by side: there is one
register, and the reader's only remaining job is the audit trail — showing what the
migration started from, which [the migration suite](../../tests/testing/test_evidence_migration.py)
compares with where it ended. The migrated register was not produced by the reader:
every record in it was written from a reading of the files it cites. The repository
does not commit to supporting both versions, because nothing outside this repository
consumes either.

**Where the legacy values are auditable.** `legacyClassification` on a record or on a
claim holds the `v1alpha1` `certificationLevel`, `evidenceLabel`, `provider`, and
`environment`, unchanged, with a note saying what they are. In the reader's output the
note says the value has not been re-examined; in the migrated register every claim
carries its classification with a note saying it is history, and its records carry
the level the reading reached.
`tools/evidence_model` also publishes `LEGACY_FIELD_DESTINATIONS`, which names where
every field of a `v1alpha1` claim row lands, and a test walks the committed register's
own keys against it. "Nothing is lost" is checked rather than asserted.

### The class ceiling is carried, not re-enforced

`v1alpha1` gives every evidence label a `ceiling` — the strongest level a result of
that class may certify — and it lives in
[the superseded register](claim-evidence-matrix.v1alpha1.json), as `evidenceLabels[].ceiling`.
Until `V1-S5-012-PR2` it was enforced in two places, and a third rule of the same shape
lives elsewhere:

| Where | What is enforced | What reads it |
|---|---|---|
| `claim-evidence-matrix.v1alpha1.json`, `evidenceLabels[].ceiling` | a claim's level may not exceed its label's ceiling | [`tests/testing/test_claim_evidence_matrix.py`](../../tests/testing/test_claim_evidence_matrix.py), and the dashboard rule `a-level-may-not-exceed-its-labels-ceiling` in [`tools/proof_dashboard`](../../tools/proof_dashboard/) |
| `test-strategy.v1alpha1.json`, `evidenceClasses[].maxCertification` | a test *layer* may not certify above its class | [`tests/testing/test_test_strategy.py`](../../tests/testing/test_test_strategy.py) |

The two bound to the register **stopped applying when the register was migrated**:
they read `claim.certificationLevel` and `evidenceLabels[].ceiling`, and `v1alpha2` has
neither. `V1-S5-012-PR2` retired both, and could, because their replacement already
existed — the validator `V1-S5-012-PR1` published, which the register's suite and the
dashboard now run over every record. The layer rule in the strategy data is untouched
by any of that and keeps working: its `synthetic` class was narrowed to a simulated
environment, and no layer used it.

The ceilings are **not** re-encoded as rules in `v1alpha2`. They come across as
`legacyCeiling`, which the schema stores and applies to nothing. Two reasons:

- A ceiling constrains what a **test layer** may certify. A level describes how one
  **record** was obtained. Carrying a layer rule onto a record would reintroduce, in a
  new file, exactly the conflation ADR 0016 was written to undo.
- The `synthetic` ceiling is the specific rule
  [ADR 0016 D3](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md)
  records as too broad. Copying it into the new version under a new name would carry
  the defect forward and make it look freshly decided.

Replacing the mechanism — a validator that reads a record and applies the rules above
— was `V1-S5-012-PR1`, and it exists: [the rule catalogue](evidence-level-rules.md)
describes it. The old ceilings stayed in force on the old data until the register
moved, which was a stricter rule than intended rather than a missing one.

One qualification to "applies to nothing", added with the validator: `legacyCeiling`
is still never applied to an `evidenceLevel`, but the rule
`a-legacy-classification-stays-under-its-legacy-ceiling` applies it to a carried
`legacyClassification` — the old rule to the old value, so that a record the migration
leaves `legacy-unmigrated` is still held to the rule it was made under.

### `production-experience` and `C4`

[ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) left
open whether the `production-experience` evidence class survives alongside `C4`. It
does, and they are not duplicates.

`production-experience` is a **class**: where a result came from. `C4` is a **level**:
how it was obtained. Both are unreachable from this repository, for the same underlying
reason, and at different layers. Collapsing them would lose the difference between a
source this project has no access to and a strength it has not reached — and a project
that later gained access to a production system would need both statements back.

## What `V1-S5-011-PR2` did not do, and what `V1-S5-012-PR2` then did

The change that published this schema migrated no data, reclassified nothing,
enforced nothing over committed data, and changed no consumer's behaviour beyond
teaching the proof dashboard to refuse a register version it did not understand. That
was deliberate: a shape is published before evidence is read into it, so that the
reading cannot bend the shape.

`V1-S5-012-PR2` did the reading. It wrote
[`claim-evidence-matrix.v1alpha2.json`](claim-evidence-matrix.v1alpha2.json) from the
files every `v1alpha1` row cited, moved every consumer onto it, retired the two
register-bound ceiling guards, and left the `v1alpha1` register and every record under
[`docs/proof/`](../proof/) unchanged. It changed no claim's statement or citations,
moved one claim's status on a measurement, and published
[a report](../proof/testing/v1-s5-012-pr2-migration-report.md) of every level that did
not simply carry across. The suite behind this page still publishes no claim, for the
reason [the test inventory](test-inventory.md) records: it establishes that a shape
exists and is consistent, never that any evidence is classified correctly under it.

## Related documents

| Topic | Document |
|---|---|
| What the levels mean | [InferOps Evidence Levels (C0–C4)](evidence-levels.md) |
| The decision that made a level a record's property | [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) |
| The register this model holds | [Claim and evidence matrix](claim-evidence-matrix.md) |
| How every record was read into it | [The V1 evidence migration, claim by claim](../proof/testing/v1-s5-012-pr2-migration-report.md) |
| The compatibility conventions this version follows | [The workload contract](../contracts/workload-contract.md) |
| Evidence classes, their ceilings, and what a real record must contain | [Certification levels and evidence classes](certification.md) |
| Which classification rules are checked, and by what | [Evidence-level classification rules](evidence-level-rules.md) |
| Where records live and what sections each carries | [Evidence records](../proof/README.md) |
| The suite behind this page | [`tests/testing/test_evidence_record_model.py`](../../tests/testing/test_evidence_record_model.py) |
