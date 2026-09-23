# ADR 0016: InferOps Evidence Levels describe how evidence was obtained, and attach to an evidence record

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date proposed | 2026-09-23 |
| Date accepted | 2026-09-23 |
| Decision owner | [`repository-maintainer`](../../governance/decision-authority.md) |
| Supersedes | None |
| Amends | [ADR 0005](ADR-0005-test-ci-and-certification-strategy.md) D4, whose level **meanings** are replaced. Its ceiling mechanism, its layers, and its lanes are untouched |
| Superseded by | None |

> [!IMPORTANT]
> This record changes what `C0` through `C4` **mean**. It changes nothing about what
> has been run, and it moves no claim.
>
> The old meanings were `C0` Schema, `C1` Mock, `C2` Real controlled, `C3` Failure,
> and `C4` Composed. The last two are the reason this record exists: *failure* names
> what an experiment was for, and *composed* names what the path was, and neither is
> the dimension the first three describe. The new meanings — Static, Substituted
> Execution, Runtime, Representative, and Operational — all answer one question,
> **how was this evidence obtained**, and everything else becomes metadata on the
> record rather than a rung on a ladder.
>
> **Nothing is reclassified here, and the new rules are not yet enforced.** Every
> existing record keeps the level it was given. The committed
> [`test-strategy.v1alpha1.json`](../../testing/test-strategy.v1alpha1.json) still
> carries the old level names and still applies the `synthetic → C1` ceiling that
> `D3` below argues is too broad, because a `v1alpha1` data contract is not re-pointed
> at new semantics in the change that writes the semantics down. Versioning that
> contract is `V1-S5-011-PR2`; making these rules executable and migrating the
> existing records claim by claim is `V1-S5-012`.
>
> What is machine-checked today is narrow and worth stating exactly:
> [`tests/testing/test_evidence_levels.py`](../../../tests/testing/test_evidence_levels.py)
> refuses a second current definition of the five levels, refuses the superseded
> names appearing as current meanings outside the surfaces registered as awaiting
> migration, and holds the mapping table and the disclaimer in place. It checks that
> the repository says one thing. It cannot check that the thing is true of any run.

## What `V1-S5-011-PR2` settled, on 2026-09-23

A dated note. The accepted text above and below is unchanged: a decision record is
evidence about when a decision was made, and editing it to be currently correct
destroys the only thing it is good for. What follows is what happened afterwards, and
where three rows of the tables in this record now point.

`V1-S5-011-PR2` published
[`claim-evidence-matrix.v1alpha2.schema.json`](../../testing/claim-evidence-matrix.v1alpha2.schema.json)
and [the model document](../../testing/evidence-record-model.md) that explains it. It
**published a shape and migrated no data.**

- **`D2`.** Its status row says the register stores one level per claim *until
  `V1-S5-011-PR2`*. That pointer resolves to the **schema**, not to the register. The
  shape that can hold several records per claim now exists; the committed register is
  still `v1alpha1` and still stores one level per claim, and migrating the rows is
  `V1-S5-012-PR2`. Two tests fail on the day that happens, so the pages describing the
  unmigrated state are corrected in the same change.
- **`D3`.** Unchanged and still not enforced over committed data. The `v1alpha2` schema
  separates `execution.substitutions[].claimMaterial` from `workload.source`, so the
  new shape cannot express the rule `D3` rejects; the committed `synthetic → C1`
  ceiling is untouched and still enforces the old one. `V1-S5-012-PR1` replaces it.
- **`R4`.** Half closed. The data model now supports several records per claim; the
  register still does not. The risk stays open on that half.
- **`Q2`.** Answered, as this record said `V1-S5-011-PR2` might: the
  `production-experience` evidence **class** survives alongside the `C4` **level**, and
  neither absorbs the other. A class says where a result came from; a level says how it
  was obtained. Both are unreachable here, for the same underlying reason, at different
  layers — and collapsing them would lose the difference between a source this project
  has no access to and a strength it has not reached.
  [The model document](../../testing/evidence-record-model.md) carries the reasoning
  and a test holds the answer in place.
- **`Q1` and `Q3`** are untouched and remain open.

## What `V1-S5-012-PR1` settled, on 2026-09-23

A second dated note, on the same terms as the first: the accepted text is unchanged.

`V1-S5-012-PR1` made the rules executable. [The rule catalogue](../../testing/evidence-level-rules.md)
lists forty-three classification rules and says, for each, whether the `v1alpha2` schema,
the validator in [`tools/evidence_model/rules.py`](../../../tools/evidence_model/rules.py),
or review enforces it; every rule marked for the schema or the validator is watched
refusing a document built to break it. It added one optional field to the `v1alpha2`
claim, `claimMaterialComponents`, so that materiality is declared once per claim
rather than asserted per record by the record's author.

- **`R1`.** Half closed. The four rows this record's validation listed as enforced by
  *nothing* — `C1` requires a claim-material substitution, `C3` requires declared
  representativeness and criteria, `C4` requires production operation and an
  observation period, a synthetic workload is not forced to `C1` — are now enforced
  over any `v1alpha2` document. No committed register is one, so over committed
  evidence they are still applied by review, and the risk stays open on that half until
  `V1-S5-012-PR2` migrates the register.
- **`D3`.** Enforced for classified records: no validator rule below `C4` reads the
  workload's origin, a test asserts it, and a run whose only "substitution" is its
  generated prompt set is refused at `C1`. The committed `synthetic → C1` ceiling in
  `test-strategy.v1alpha1.json` is **still in place**, which is not what `D3` above
  says. `D3` says it stays "until `V1-S5-012-PR1` replaces the mechanism". The
  mechanism is replaced; the ceiling was left where it is, because the only register
  it governs is the committed `v1alpha1` one, whose rows carry no substitution
  metadata for the replacement to read. Lifting it before that register moves would
  remove the guard from the data the replacement cannot see — the failure `D3` itself
  warns about. It moves with the register in `V1-S5-012-PR2`.
- **`Q1`.** Answered: in data, as a flag, and by review. The schema requires every
  `C3` criterion to carry `declaredBefore: true`, the validator requires a measured
  result for every criterion including the ones not met, and whether a criterion
  flagged as declared first really was is the review rule
  `a-criterion-flagged-declared-before-was-registered-before`. A timestamp comparison
  was considered and rejected: the record's author writes both timestamps.

## What `V1-S5-012-PR2` settled, on 2026-09-23

A third dated note, on the same terms: the accepted text is unchanged, and several of
its present-tense sentences — "the new rules are not yet enforced", "two vocabularies
coexist until `V1-S5-012-PR2` finishes" — describe the day it was accepted.

`V1-S5-012-PR2` read every record the `v1alpha1` register cited against `D1`, one claim
at a time, and wrote the result as
[the `v1alpha2` register](../../testing/claim-evidence-matrix.v1alpha2.json), which every
consumer now reads. [The migration report](../../proof/testing/v1-s5-012-pr2-migration-report.md)
says what each record turned out to be.

- **`D2` and `R4`.** Closed. The register stores a level on each of 54 evidence records,
  and nine claims hold more than one — the weaker runs a claim-level `C2` used to hide
  are visible beside the real ones.
- **`D3` and `R1`.** Enforced over committed evidence. Every record passes the schema
  and the validator with every cited file present, and the dashboard runs the same
  rules before it renders. The committed strategy data carries the current level names,
  and its `synthetic` class names a simulated environment only, so the `synthetic → C1`
  rule over generated input is gone from the data. No layer or gate used the class.
- **`D8`.** Held, and checked. No record was upgraded by terminology: 43 kept the level
  their claim carried, 8 moved with a justification from what they executed — three to
  a higher-numbered level, each named in a test so that a fourth has to be added on
  purpose — and no record is `C3` or `C4`. One claim moved from `certified` to
  `not-claimed`, because the audit measured its statement untrue of the committed
  records; its statement was kept.
- **`R3`.** The conceptual mapping for `C0`–`C2` held for 43 records and was not used
  for the other 8. That is the reason it was published as conceptual.
- **Consequence on vocabularies.** The certification document no longer states the
  superseded meanings and left the list of surfaces awaiting migration, which is empty.
  The superseded meanings are stated only where they are mapped — the specification,
  this record, ADR 0005, and the architecture index — and in dated records.
- **`Q3`** is untouched and remains open: field names, file paths, and tool names still
  say `certification`.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | A level describes **how evidence was obtained**: `C0` Static, `C1` Substituted Execution, `C2` Runtime, `C3` Representative, `C4` Operational | **Accepted** | A published specification, and a test that refuses a competing current definition |
| D2 | A level is a property of an **evidence record**, not of a claim, a suite, or the system; one claim may carry several records at different levels | **Accepted** as a definition | Stated in the specification; the register still stores one level per claim until `V1-S5-011-PR2` |
| D3 | `C1` is decided by **substitution of a claim-material component**, and not by the origin of the input workload | **Accepted** as a definition; **not yet enforced** | The specification; the committed `synthetic → C1` ceiling still enforces the old rule and is left in force on purpose |
| D4 | `C3` Failure and `C4` Composed are **superseded as level meanings**; failure mode and composition become evidence-record metadata | **Accepted** | The mapping table, the supersession note on ADR 0005 D4, and a test over both |
| D5 | `C4` requires genuine organizational production operation over a stated observation period; public-cloud execution is not `C4` | **Accepted** | Stated in the specification, and unreachable here: there is no organizational production |
| D6 | The framework is **project-defined** and may not be presented as an ISO, NIST, regulatory, or industry certification | **Accepted** | A required disclaimer, checked by a test |
| D7 | ADR 0005's historical text stands; its `D4` is amended with a dated note rather than rewritten | **Accepted** | The note is in ADR 0005, dated, and names this record |
| D8 | This record reclassifies **no** existing evidence, and no documentation change may upgrade a claim | **Accepted** as a rule | No level, status, class, or record changes in the change carrying this record |

## Context

[ADR 0005](ADR-0005-test-ci-and-certification-strategy.md) D4 decided a certification
ladder and [the certification document](../../testing/certification.md) published it.
It was a good decision for the problem it had: the mock suite was about to become the
cheapest thing in the repository, and the distance from *the mock passes* to *serving
works* is one hurried pull-request description. The ladder made the ceiling a number
in a data file and three tests enforce it. That part has worked, and this record does
not touch it.

What has not held is the ladder itself, in two specific places.

**`C3` Failure and `C4` Composed answer a different question from `C0` to `C2`.**
`C0` Schema, `C1` Mock, and `C2` Real controlled all describe *how a result was
obtained* — by inspection, against a substitute, or for real. `C3` describes *what
was tested*, and `C4` describes *how many systems were in the path*. Ranking them
above `C2` on the same axis produces claims that are wrong in both directions. A
failure experiment against a mocked provider is not stronger than a real completion;
it is weaker, and the old ladder called it `C3`. A composed path with a substituted
backend is not stronger than a single real component; it is weaker, and the old
ladder called it `C4`. The repository has never actually made either mistake, because
both levels were placed out of V1 scope — which is the useful detail. **The ladder
was safe only because its top two rungs were unreachable.**

**A synthetic workload is not a substituted component.** The committed strategy gives
the `synthetic` evidence class a `C1` ceiling, on the reasoning that generated input
is a kind of substitute. A generated request can travel through the real API, the
real adapter, the real runtime, the real model, and a real Kubernetes release, and
the result is evidence about all five. Capping it at `C1` says the opposite. The
distinction that matters is whether a component **material to the claim** was
replaced, and input origin does not answer that question. The rule also blocks the
level the project most needs next: representative evidence is usually reached with
deliberately constructed workloads, and under the current ceiling a deliberately
representative load test can never exceed the level of a mock.

A third problem is smaller and shows up everywhere. **The level is stored on the
claim.** A claim has one level, so the register keeps only the strongest record and
the history of how confidence was built is not representable. A claim with static,
substituted, and runtime evidence is better documented than one with runtime evidence
alone, and today there is nowhere to say so.

The trigger for fixing all three now rather than later is `V1-S5-006`, which freezes
an immutable V1 evidence pack. Evidence frozen under semantics already known to be
superseded is evidence that has to be unfrozen.

## Decision criteria

Six, registered before the options were compared.

| ID | Criterion | Why |
|---|---|---|
| C1 | One axis per level | The defect being fixed is two dimensions on one ladder; a replacement that mixes them again is not a replacement |
| C2 | A claim's strength may not rise without a run | The one failure this whole area exists to prevent. A renaming that promotes anything has done harm, whatever else it achieved |
| C3 | History stays readable | Records produced under the old names must remain interpretable without a reader knowing this record exists |
| C4 | The level must be claim-relative | *Real* means real **for this claim**; a model absent from the path is not a substitution for a schema claim and is a fatal one for a serving claim |
| C5 | No unearned authority | The word *certification* invites a reader to assume an outside body. Nothing here has one |
| C6 | Definition before enforcement | Semantics must be stable before existing records are re-examined against them, or the migration is re-run |

## D1 — Five levels, one axis

| Level | Name | The question it answers |
|---|---|---|
| `C0` | Static Evidence | What can be established without executing the target behaviour? |
| `C1` | Substituted Execution Evidence | What can be established when a claim-material component is replaced? |
| `C2` | Runtime Evidence | What does the actual claim-relevant implementation do in this recorded environment? |
| `C3` | Representative Evidence | What does the real system do under conditions deliberately chosen to represent intended use? |
| `C4` | Operational Evidence | What has been observed during genuine production operation, over a stated period? |

The full definitions, with each level's classification rule, what it can support, what
it does not establish, and worked illustrations, are in
[the evidence-level specification](../../testing/evidence-levels.md). That document
is the authoritative one; this record decides that it is.

Two alternatives were compared.

| Option | C1 | C3 | C5 | Why not |
|---|:---:|:---:|:---:|---|
| Keep the ladder and add rules for `C3`/`C4` | no | yes | no | It leaves *failure* and *composed* on the strength axis, so every rule added is a rule about when a weaker result outranks a stronger one |
| A new vocabulary with different identifiers | yes | no | yes | Fixes the axis and orphans every committed record, every proof document, and every validation record that says `C2`. The identifiers are load-bearing history |
| **Reuse `C0`–`C4`, redefine the meanings** (**selected**) | yes | yes | yes | The first three keep the dimension they always had, the last two change, and the mapping is published rather than assumed |

Reusing the identifiers has a real cost and it is worth naming: for as long as both
vocabularies exist in the repository, `C3` means two things depending on which
document a reader arrived from. That is why `D4` publishes a mapping, why the
supersession is dated, and why `D7` amends ADR 0005 in place rather than leaving the
old table to be found by a reader who never sees this record.

## D2 — The level belongs to the record

An evidence level is a property of **one evidence record**. It is not a property of a
claim, a test suite, a document, or the repository.

The three ideas that get collapsed, kept apart:

- **evidence level** — how *this record's* evidence was obtained;
- **evidence class** — what a *layer* runs against, and the ceiling that carries;
- **claim status** — whether the project publishes the property as a capability.

A claim may reference several records at different levels, and the weaker ones are
kept rather than replaced. A claim carrying `C0` static evidence, `C1` substituted
evidence, and `C2` runtime evidence has shown how its confidence was built; deleting
the first two would leave the claim no stronger and the reasoning invisible.

**This is a definition today and not yet a representation.** The committed register
stores one certification level per claim. Storing several records per claim is the
schema change `V1-S5-011-PR2` makes, against a new contract version rather than by
redefining `v1alpha1` in place.

## D3 — Substitution decides `C1`, workload origin does not

The classification question for `C1` is exactly one: **was a component material to
evaluating this claim substituted?** If it was, the record is `C1` for that claim,
however faithful the substitute and however real the rest of the path.

The origin of the input is a separate property of the record. A synthetic workload
through a real path produces evidence about the real path. A captured production
workload through a mocked provider produces evidence about the mock.

**This is not enforced, and the old rule is deliberately left running.** The
`synthetic` evidence class keeps its `C1` ceiling in the committed strategy data
until `V1-S5-012-PR1` replaces the mechanism. Turning that ceiling off in this change
would remove a guard before its replacement exists, and the guard's failure mode —
a generated load test cited as runtime evidence — is the exact failure ADR 0005 D4
was written to prevent. The two rules are not symmetrical: the current one is too
strict, and the risk of removing it early is that something becomes too loose.

## D4 — `C3` Failure and `C4` Composed are superseded as level meanings

| Identifier | Meaning before this record | Treatment |
|---|---|---|
| `C0` | Schema | Maps conceptually to `C0` Static Evidence |
| `C1` | Mock | Maps conceptually to `C1` Substituted Execution Evidence |
| `C2` | Real controlled | Maps conceptually to `C2` Runtime Evidence |
| `C3` | Failure | **No direct mapping.** Superseded |
| `C4` | Composed | **No direct mapping.** Superseded |

*Conceptually* is load-bearing in the first three rows. It means the old and new
definitions describe the same dimension. It does **not** mean any record has been
re-examined, and `D8` says so again because this is the row a reader most easily
over-reads.

**Failure becomes a scenario, not a rank.** A failure experiment is `C1` when the
failure is induced through a substitute, `C2` when the claim-relevant real components
execute, `C3` under representative conditions, and `C4` when observed in production.
The old ladder assigned it a level before anybody asked what ran.

**Composition becomes a topology, not a rank.** A composed path is `C1` if a material
component is substituted, `C2` if the real composed path executes, `C3` under
representative conditions, and `C4` only in production. Integrating a second system
changes what the evidence is about, not how strong it is.

Both survive as evidence-record metadata, along with workload shape, provider,
environment, and hardware class. Nothing is deleted; two things stop being levels.

## D5 — What `C4` requires, and why nothing here can reach it

`C4` requires an actual production system, genuine organizational production usage,
a recorded observation period, an identified production environment, recorded
observations, documented conditions and known gaps, and stated limitations.

**Public-cloud execution is not `C4`.** A cloud experiment is `C2`, or `C3` where it
meets the representativeness requirements. This is the same rule the certification
document already applies to the `production-experience` evidence label, which it
records as defined and unreachable; `D5` restates it at the level rather than only at
the label, because the label is the easier one to notice missing.

No evidence in this repository is `C4` and none can be, for the reason the old `C4`
was also unreachable — although not the same reason. The old one needed a second
project. This one needs users.

`C3` is reachable in principle and nothing is classified there today. Reaching it
requires declared infrastructure, declared workload characteristics, written
representativeness assumptions, and acceptance criteria registered **before** the
run — the ordering that separates a measurement from a search for a supporting
number, which [the proof templates](../../proof/templates/) already enforce for
experiments.

## D6 — Project-defined, and said so where it cannot be missed

[The specification](../../testing/evidence-levels.md) opens with:

> **InferOps Evidence Levels are project-defined. They are not an ISO standard, a
> NIST standard, a regulatory scheme, or an industry certification.**

A test requires that sentence's substance to be present. The word *certification*
carries an implication this project has not earned and cannot earn from inside
itself: no outside party has reviewed a decision, a claim, or a record here, which
[ADR 0015](ADR-0015-v1-decision-ownership-and-sign-off-authority.md) R3 already
records as open. The target term is **evidence level**. The word `certification`
survives in identifiers, committed field names, and historical records during
migration, and each of those is a name rather than a claim.

## D7 — ADR 0005 is amended, not rewritten

ADR 0005 D4's text stands as written. It gains a dated note recording that its level
meanings are superseded by this record from 2026-09-23, that its ceiling mechanism is
untouched, and that nothing it certified is reclassified.

The alternative — editing D4's table to the new meanings — was rejected under `C3`.
It would make the record claim that the project decided in August 2026 something it
decided in September 2026, and every validation record written between those dates
would silently acquire a meaning nobody intended. A decision record is evidence about
when a decision was made. Editing it to be currently correct destroys the only thing
it is good for.

The same rule governs proof records: **no committed record under
[`docs/proof/`](../../proof/) is edited by this change.** A record that says `C2` in
August says `C2` now, and the mapping table is how a reader converts it.

## D8 — Nothing is reclassified, and no document may promote a claim

No claim status, certification level, evidence class, or record changes in the change
carrying this record. The register, the dashboard, the strategy data, `contracts/`,
and `src/` are untouched.

The rule this generalises, which outlives the migration: **a documentation change may
never raise what a claim may say.** A level is reached by a record. Renaming the
level, publishing a better definition of it, or approving the change that does either
adds no evidence. `V1-S5-012-PR2` re-examines each existing record against the
definitions in `D1`, one claim at a time, and every change it makes has to be
justified by what actually executed rather than by the terminology moving under it.

## Consequences

- **`C3` and `C4` become reachable in principle**, and the ceiling stops being
  structural. Under ADR 0005 they were out of V1 scope, and a test refuses an active
  claim that requires either. That test still passes, because nothing claims either.
- **Two vocabularies coexist until `V1-S5-012-PR2` finishes.** The specification, this
  record, and the certification document's banner are the current definition; the
  committed strategy data, the register's field names, and every historical proof
  record still carry the old one.
- **A current document may not introduce the superseded meanings.** Five documents are
  registered as allowed to state `C3` Failure or `C4` Composed — the two that publish
  the mapping, the two that annotate this change, and the one awaiting migration — and
  a test refuses a sixth. The list can shrink as the migration lands; it cannot grow
  unnoticed.
- **A record under `docs/proof/` is exempt from that list and not from the rule.** A
  dated record is history and may state the vocabulary it was written under, so
  requiring each future one to be registered would make the guard paperwork. It must
  still say `superseded` and name this record, which is what stops a reader taking an
  old classification for a current one.
- **The register cannot yet express what `D2` decides.** One level per claim is stored
  today; multiple records per claim is a schema change, and until it lands the
  specification describes a shape the data does not have. This is recorded as a
  limitation rather than described as complete.
- **`V1-S5-006` is blocked on `V1-S5-012`**, which is the point: the immutable evidence
  pack must be assembled under the final semantics rather than frozen under superseded
  ones.
- **Sixteen records name an owner**, and this one is the second assigned at acceptance
  rather than retrospectively.

## Compatibility impact

**None on any published contract.** `contracts/` is untouched. No schema, error code,
rule identifier, field name, or field location changes. No runtime behaviour changes,
and no lane, marker, layer, gate, or ceiling moves.

The `v1alpha1` data contracts keep their current semantics **on purpose**. Neither
[`test-strategy.v1alpha1.json`](../../testing/test-strategy.v1alpha1.json) nor
[`claim-evidence-matrix.v1alpha1.json`](../../testing/claim-evidence-matrix.v1alpha1.json)
changes here; re-pointing a published contract's meaning without a version bump is
the failure `V1-S5-011-PR2` exists to avoid.

One documentation convention changes: the authoritative definition of the five levels
now lives in [`docs/testing/evidence-levels.md`](../../testing/evidence-levels.md),
and [the certification document](../../testing/certification.md) keeps the evidence
classes, their ceilings, and the contents required of a real-runtime record while
carrying a banner that its level names are superseded.

## Security considerations

Two, and both are limits.

**Defining a level defends nothing.** This record adds no control, runs no scan, and
changes no trust boundary. The map in
[ADR 0004](ADR-0004-component-and-ownership-boundaries.md) is unchanged.

**The window in which two vocabularies coexist is the risk this record creates.** A
reader who finds a `C3` in a historical record and the new definition in the
specification can conclude that a failure experiment was representative evidence.
The mitigations are the dated banner, the published mapping, the pinned list of
surfaces still carrying the old meanings, and the fact that no record in this
repository is classified `C3` or `C4` under either vocabulary — so there is no
document where the misreading would change what a claim says.

## Evidence

| Claim | Evidence | Class | Ceiling |
|---|---|---|---|
| One current definition of the five levels exists, and a second cannot be added unnoticed | [`tests/testing/test_evidence_levels.py`](../../../tests/testing/test_evidence_levels.py) over the committed documents | `local-static` | `C0` |
| The superseded meanings appear as current only on surfaces registered as awaiting migration | The same suite, scanning the committed Markdown | `local-static` | `C0` |
| The mapping table and the project-defined disclaimer are present | The same suite | `local-static` | `C0` |
| This record has a declared owner under the governance model | [`tests/architecture/test_decision_authority.py`](../../../tests/architecture/test_decision_authority.py) over the committed register | `local-static` | `C0` |
| The change itself was validated | [Change validation record](../../proof/testing/v1-s5-011-pr1-validation.md) | `local-static` | `C0` |

**No other evidence exists, and none is possible from this change.** This record
decides what five identifiers mean. Nothing was executed against a runtime to
establish it, no model was loaded, no cluster was contacted, and no suite can
establish that the definitions are good ones — only that the repository states them
once and consistently.

## Risks, assumptions, and open questions

| ID | Risk or question | Status | Consequence |
|---|---|---|---|
| R1 | The definition is published and not enforced | Open, and scheduled | Between this record and `V1-S5-012-PR1`, the specification describes rules that only review applies. The committed ceilings still enforce the old rules, so the gap is a stricter rule than intended rather than a missing one |
| R2 | `C3` meant *failure* and now means *representative* | Mitigated | The supersession is dated, the mapping is published, ADR 0005 D4 carries a note, and nothing in this repository is classified `C3` under either meaning |
| R3 | A reclassification could be read into the conceptual mapping for `C0`–`C2` | Mitigated | `D4` and `D8` both state that no record was re-examined; `V1-S5-012-PR2` does that claim by claim |
| R4 | The register cannot represent multiple records per claim | Open, and scheduled | `D2` is a definition the data model does not yet support; `V1-S5-011-PR2` versions it |
| R5 | `C4` is defined and permanently unreachable here | Accepted | Recorded so that no later change can reach for the word without an organizational production system and an observation period |
| Q1 | Should `C3` require a pre-registered acceptance criterion in data, or by review? | Open | The experiment template already registers a method and a failure condition before a run; whether a validator reads them is `V1-S5-012-PR1`'s question |
| Q2 | Does the `production-experience` evidence label survive alongside `C4`? | Open | Both say the same thing at different layers. Collapsing them is a data-model question `V1-S5-011-PR2` may answer |
| Q3 | When do the `certification` identifiers themselves get renamed? | Open | Field names, file paths, and tool names still say `certification`. A rename touches committed data and tooling and is not in `V1-S5-011` or `V1-S5-012` |

## Related records

| Topic | Document |
|---|---|
| The definitions this record establishes | [InferOps Evidence Levels (C0–C4)](../../testing/evidence-levels.md) |
| The record whose D4 this amends | [ADR 0005](ADR-0005-test-ci-and-certification-strategy.md) |
| Evidence classes, ceilings, and what a real record must contain | [Certification levels and evidence classes](../../testing/certification.md) |
| Who may accept or amend a decision, and who signs off a claim | [ADR 0015](ADR-0015-v1-decision-ownership-and-sign-off-authority.md) |
| The claims this model classifies evidence for | [Claim and evidence matrix](../../testing/claim-evidence-matrix.md) |
| Where records live and what sections each carries | [Evidence records](../../proof/README.md) |
| The decision index and record conventions | [Architecture and decision records](../README.md) |
