# Evidence-level classification rules

Status: **enforced over the committed register.** The rules below run in
[`tools/evidence_model/rules.py`](../../tools/evidence_model/rules.py) and in
[the `v1alpha2` schema](claim-evidence-matrix.v1alpha2.schema.json), and
[their suite](../../tests/testing/test_evidence_level_rules.py) watches each enforced
rule refuse a document built to break it. Since `V1-S5-012-PR2` the register every
consumer reads is [`claim-evidence-matrix.v1alpha2.json`](claim-evidence-matrix.v1alpha2.json),
and every one of its records passes every rule, with every cited file required to
exist, in [the register's own suite](../../tests/testing/test_claim_evidence_matrix.py)
and again in [the proof dashboard](../proof/dashboard.md) before it renders.

> [!IMPORTANT]
> This page says what is **checked**. What the levels **mean** is in
> [the evidence-level specification](evidence-levels.md), and nothing here restates or
> changes a definition. InferOps Evidence Levels are project-defined; they are not an
> ISO, NIST, regulatory, or industry certification standard, and a rule that checks
> them is a rule this project applies to itself.

## Three places a rule can live

| Where | What it can check | What it cannot |
|---|---|---|
| **The schema** | The shape of one record or one claim: which fields a level requires, and which values they may take | Anything that compares two objects, or a field with a fact outside the document |
| **The validator** | A record against itself, a record against the claim that holds it, and a claim against the register around it | Whether a statement in a field is *true* |
| **Review** | Whether a declaration is right, a workload is representative, a production context is genuine, a limitation is the one that matters | Nothing mechanical; that is why these rules are listed rather than left out |

Every rule has exactly one of the three in the `Enforced by` column below, and a test
reads that column against the code: a rule published here as enforced that no code
enforces fails the suite. Every rule marked `schema` or `validator` has at least one
committed mutation — the illustrative register, corrupted to break that rule — and the
suite asserts it is refused by that rule at that place. Forty-three rules: eleven
enforced by the schema, twenty-six by the validator, and six left to review.

## The decision that makes `C1` and `C2` checkable

The one question that decides `C1` is *was a component material to evaluating this
claim substituted?* The `v1alpha2` schema records the answer on each substitution, as
`claimMaterial`, which puts it in the hands of whoever writes the record. A record that
replaces the inference runtime with the committed mock, and flags the mock
`claimMaterial: false`, passes the schema at `C2`.

So a claim now declares its claim-material components **once**, in
`claimMaterialComponents`, and every record supporting it is checked against that one
declaration:

- a record that substitutes a declared component must flag it material, so a record
  cannot call a mock of a declared component immaterial;
- a record at `C2` or above must name every declared component as having executed,
  because *real* is relative to the claim;
- a substitution flagged material must replace a declared component, so a record cannot
  reach `C1` by "substituting" something the claim never depended on — which is how a
  run whose only difference from the real path is a generated prompt set is refused.

A claim holding any classified record at `C1` or above must carry the declaration.
Whether the declaration names the right components remains a judgement, and it is the
first review rule below.

**The declaration is the limit of all three rules.** A claim that declares only the API
lets a record mock the runtime, flag the mock immaterial, and pass at `C2`; a test
asserts that it still does. The gap has one edge the rules do reach: if another record
under the same claim substitutes the runtime and flags it material, that substitution
names a component the claim does not declare, and it is refused — so an
under-declaration survives only in a claim none of whose records ever admits the
component mattered. This paragraph was added after an independent review of the change
found that the first draft described the mock-at-`C2` case as closed. What changed is where the judgement is made: once per claim,
in the open, where one reviewer reads it — rather than once per record, by the person
who wants that record to pass.

The field is **optional in the schema and additive**. The compatibility reader does
not produce it, and a `legacy-unmigrated` record carries no level for it to govern.
`V1-S5-012-PR2` wrote it for every claim holding a record at `C1` or above, in the same
reading of each claim that decided its records' levels, and
[the migration report](../proof/testing/v1-s5-012-pr2-migration-report.md) lists the
declarations a second reader could reasonably have made differently.

## The rules

Levels are the levels a rule binds; `any` means it binds every record it applies to,
or is not level-specific. The subject is the smallest object the rule needs to see.

### Enforced by the schema

| Rule | Subject | Levels | Enforced by | What it requires |
|---|---|---|---|---|
| `an-evidence-level-belongs-to-an-evidence-record` | claim | any | schema | A claim carries no evidence level. Its records do, one each. |
| `a-classified-record-states-what-ran-where-and-how` | record | any | schema | A record carrying a level states what executed, its workload source, its environment, how to repeat it, an immutable identifier, and an artifact. |
| `a-classified-record-states-its-limitations-and-what-it-does-not-establish` | record | any | schema | A record carrying a level lists at least one limitation and at least one thing it does not establish. |
| `an-unmigrated-record-carries-no-level` | record | any | schema | A legacy-unmigrated record has a null level and keeps its superseded classification verbatim. |
| `a-c0-record-did-not-execute-the-target-behaviour` | record | `C0` | schema | A C0 record states that the behaviour the claim is about did not run. |
| `an-executing-record-names-what-executed` | record | `C1`, `C2`, `C3`, `C4` | schema | A record at C1 or above states that the target behaviour ran and names at least one component that executed. |
| `a-c1-record-names-a-claim-material-substitution` | record | `C1` | schema | A C1 record names at least one substitution flagged claim-material. |
| `a-real-record-substitutes-nothing-claim-material` | record | `C2`, `C3`, `C4` | schema | A record at C2 or above flags no substitution as claim-material. |
| `a-c3-record-declares-representativeness-and-criteria-before-the-run` | record | `C3` | schema | A C3 record declares representativeness with written assumptions, a measurement method, results, and criteria each flagged declared before. |
| `a-c4-record-names-a-production-context-and-an-observation-period` | record | `C4` | schema | A C4 record ran in organizational production and names the organization, the workload that depended on it, the period, known gaps, and results. |
| `a-planned-or-deferred-claim-cites-no-record` | claim | any | schema | A planned or deferred claim holds no evidence record. |

### Enforced by the validator

| Rule | Subject | Levels | Enforced by | What it requires |
|---|---|---|---|---|
| `a-component-either-executed-or-was-substituted` | record | any | validator | No component is named both as having executed and as having been substituted in the same record. |
| `a-c0-record-ran-only-inspection` | record | `C0` | validator | A C0 record ran only validators or tools, substituted nothing, issued no workload, and names no production context. |
| `an-executing-record-ran-outside-the-repository` | record | `C1`, `C2`, `C3`, `C4` | validator | A record at C1 or above names an environment other than repository-only. |
| `a-result-answers-a-criterion-the-record-declares` | record | any | validator | Criterion identifiers are unique, and a result that names a criterion names one the record declares. |
| `an-observation-period-ends-after-it-starts` | record | any | validator | Every observation period ends after it starts, and a stated duration agrees with the timestamps. |
| `a-limitation-says-something` | record | any | validator | No limitation or does-not-establish entry is a placeholder or shorter than twenty characters. |
| `a-c3-record-declares-its-workload-shape` | record | `C3` | validator | A C3 record states at least one workload characteristic: concurrency, request count, prompt-size distribution, arrival pattern, or duration. |
| `a-c3-record-declares-the-conditions-it-represents` | record | `C3` | validator | A C3 record describes, in its environment note, the infrastructure and conditions it was run on as representative ones. |
| `a-c3-record-measures-every-criterion-it-declares` | record | `C3` | validator | Every C3 criterion has an outcome other than not-evaluated and at least one result that cites it, including the criteria that were not met. |
| `a-c4-record-observed-production-traffic` | record | `C4` | validator | A C4 record's workload source is production traffic. |
| `a-c4-record-states-how-production-was-observed` | record | `C4` | validator | A C4 record carries a measurement method: the production telemetry or observation its results were read from. |
| `a-record-names-the-claim-that-holds-it` | claim | any | validator | A record's claimId is the identifier of the claim that holds it. |
| `a-record-identifier-is-unique` | register | any | validator | No two records in a claim, or in a register, share a recordId. |
| `an-executed-claim-declares-its-claim-material-components` | claim | `C1`, `C2`, `C3`, `C4` | validator | A claim holding a classified record at C1 or above declares the components material to evaluating it, in claimMaterialComponents. |
| `a-substituted-claim-material-component-is-flagged-material` | claim | any | validator | A record that substitutes a component its claim declares material flags the substitution claim-material. A record cannot call a mock of a declared component immaterial; a component the claim never declared is not caught. |
| `a-claim-material-substitution-replaces-a-declared-component` | claim | `C1` | validator | A substitution flagged claim-material replaces a component the claim declares material. Input is not a component, so a synthetic workload cannot be the substitution that puts a record at C1. |
| `a-real-record-executed-every-claim-material-component` | claim | `C2`, `C3`, `C4` | validator | A record at C2 or above names every component its claim declares material among the components that executed. |
| `a-certified-claim-rests-on-classified-evidence` | claim | any | validator | A certified claim holds at least one record with a level, or a carried legacy classification with one. A claim with no classified evidence is not published as a capability. |
| `a-real-behaviour-claim-rests-on-real-evidence` | claim | `C2`, `C3`, `C4` | validator | A certified claim that asserts real behaviour holds a record at C2 or above, or a carried legacy classification whose evidence class may support real behaviour. A mock cannot establish what it replaced. |
| `a-statement-about-real-behaviour-declares-it` | claim | any | validator | A claim whose statement says it serves a real completion or real inference sets assertsRealBehaviour, so the real-evidence rule cannot be switched off by leaving one flag false. A phrase list, carried from the v1alpha1 register. |
| `a-claim-identifier-is-unique` | register | any | validator | No two claims in a register share a claimId. |
| `a-citation-is-a-plain-repository-path` | register | any | validator | No evidence reference, versions reference, or procedure workflow contains a '.' or '..' segment or an empty one, so no citation can detour into the template root or out of the evidence root while its prefix says otherwise. |
| `a-template-is-not-evidence` | register | any | validator | No evidence reference, versions reference, or procedure workflow names a file under the register's templateRoot. |
| `evidence-is-cited-from-the-evidence-root` | register | any | validator | Every evidence reference names a file under the register's evidenceRoot. |
| `a-cited-record-exists` | register | any | validator | Every evidence reference names a file that exists, when the check is given a repository to look in. |
| `a-legacy-classification-stays-under-its-legacy-ceiling` | register | any | validator | A carried v1alpha1 classification names an evidence class the register defines, and its level does not exceed that class's legacy ceiling. The old rule, applied to old data only. |

### Left to review

| Rule | Subject | Levels | Enforced by | Why a machine does not decide it |
|---|---|---|---|---|
| `the-declared-claim-material-components-are-the-right-ones` | claim | any | review | Whether claimMaterialComponents names what evaluating the claim actually requires. The validator holds records to the declaration; only a reader of the claim can hold the declaration to the claim. |
| `a-declared-representative-workload-represents-intended-use` | record | `C3` | review | Whether the declared intended use, assumptions, and shape actually represent how the system is meant to be used. |
| `a-criterion-flagged-declared-before-was-registered-before` | record | `C3` | review | Whether a criterion flagged declaredBefore was in fact registered before the run. The flag is required; its truth is in the history of the record. |
| `a-production-context-is-genuine` | record | `C4` | review | Whether the organization and depending workload are real and depended on the system. A cloud experiment can be written in this shape; it cannot be made genuine by one. |
| `a-limitation-is-the-right-limitation` | record | any | review | Whether the limitations and does-not-establish entries name what a reader would otherwise over-read. The validator refuses placeholders, not omissions of substance. |
| `evidence-is-relevant-and-sufficient-for-its-claim` | claim | any | review | Whether the records a claim holds support its statement. A level says how evidence was obtained; it does not say the evidence is about the claim, and a higher level is not better evidence for every claim. |

These six are not gaps waiting for a cleverer check. Each would have to be decided by
matching the words in a field, and a rule that matched words would fail the first honest
record phrased differently while passing a dishonest one phrased correctly. The schema
makes each of them impossible to leave out — there is a flag, a declaration, or a list
to read. It cannot make them true, and nothing on this page claims it does.

## Per level, what a machine now checks

| Level | Checked by the schema | Added by the validator |
|---|---|---|
| `C0` | the target behaviour did not execute | only validators or tools ran, nothing was substituted, no workload was issued, no production context is named |
| `C1` | something executed and is named; a substitution is flagged claim-material | the claim declares its material components, and the material substitution replaces one of them — not the input |
| `C2` | something executed; no substitution is flagged claim-material; environment, procedure, identifier, artifact, limitations, and boundary are present | every declared material component executed, none was substituted under an immaterial flag, and it ran somewhere other than the repository |
| `C3` | everything for `C2`, plus declared representativeness with assumptions, a measurement method, results, and criteria flagged declared before | a stated workload shape, a described environment, and a measured result for every criterion — including the ones not met |
| `C4` | an `organizational-production` environment, a production context with period and known gaps, and results | production traffic as the workload, and a stated way production was observed |

Across all five: no component is both executed and substituted, every observation
period is ordered and agrees with any stated duration, every result names a criterion
the record declares, limitations are not placeholders, a record says which claim holds
it, and every citation is a plain repository path with no `.` or `..` segment — the
first draft compared prefixes of unnormalised strings, and an independent review cited
the template through `docs/proof/x/../templates/` and passed.

## Synthetic input imposes no ceiling

No validator rule below `C4` reads `workload.source`, and a test reads the module's
source to hold that. Two rules read it and are meant to: `C0` requires that no workload
was issued, and `C4` requires production traffic, because both levels are *defined*
partly by their input. A second test swaps the origin of every executed record below
`C4` in the illustrative register between `synthetic`, `captured`, and
`operator-issued`, and asserts the verdict does not change.

The negative half is the case [ADR 0016 D3](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md)
names: the real API, adapter, runtime, and model execute, the prompts are generated, and
the record is classified `C1` with the prompt set listed as the claim-material
substitution. The schema accepts it. The claim's declaration refuses it, because a
prompt set is input and not a component the claim depends on.

## The ceilings, and what moved

**The layer ceiling in the strategy data no longer covers generated input.**
[`test-strategy.v1alpha1.json`](test-strategy.v1alpha1.json) carries the current level
names since `V1-S5-012-PR2`, and its `synthetic` evidence class names a simulated
environment only — a substitution, which keeps its `C1` ceiling — and says in so many
words that generated input is not the class. The rule [ADR 0016 D3](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md)
records as too broad is gone from the data. No layer and no gate used the class, so no
layer's ceiling moved: what moved is the rule, before anything relied on it. It moved
with the register, as this page said it would, because the register is the data the
replacement below could not read until it had substitution metadata.

**The register ceiling is replaced.** The two `v1alpha1` guards that read
`claim.certificationLevel` — the register suite's ceiling test and the proof
dashboard's `a-level-may-not-exceed-its-labels-ceiling` — stopped applying when the
register moved, because `v1alpha2` has no such field, and both are gone. What replaces
them:

- for a **classified** record, the substitution rules above, which do not look at an
  evidence class at all — and every record in the committed register is classified;
- for a **carried** classification, `a-legacy-classification-stays-under-its-legacy-ceiling`,
  which applies the old ceiling to the old value and to nothing else. The migration
  left no record `legacy-unmigrated`, so today it governs each claim's carried history
  only.

The suite runs every rule over the committed register with every cited file required
to exist, and over the superseded register read into the new shape in memory, and
requires zero refusals from both. It also repeats two of the `v1alpha1` suite's
negative controls — a mock certified at `C2`, and a real-behaviour claim resting on a
static label — against the replacement.

## Where the heuristics stop

- **`a-limitation-says-something`** refuses the placeholders people type (`None`,
  `N/A`, `TBD`, and a short list of others) and any entry under twenty characters. A
  sentence such as *"Limitations are recorded here."* passes, and a test asserts that it
  does, so the gap is visible rather than assumed away. Whether a limitation is the
  right one is a review rule.
- **`a-c3-record-declares-the-conditions-it-represents`** requires a description, not
  a particular infrastructure. A single-node local cluster may be representative of one
  claim and not of another, and the rule does not pretend to know which.
- **`a-c0-record-ran-only-inspection`** reads component roles. A record that names the
  inference runtime under the role `tool` passes it; the role vocabulary is what the
  record's author chose, and review reads it.
- **`a-statement-about-real-behaviour-declares-it`** matches two phrases, the same two
  the `v1alpha1` register suite matches. A statement about real serving phrased any
  other way, with `assertsRealBehaviour` left false, passes it and is exempt from the
  real-evidence rule. It is the replacement of the rule that already runs, not a
  better one.
- **`a-cited-record-exists`** only runs when given a repository to look in. The
  illustrative fixtures cite paths nobody has written, so the suite checks them against
  a temporary directory it populates, and checks the committed register against this
  repository.

## What this does not do

- **It classifies nothing.** The rules check a level; they do not choose one. Every
  level in the committed register was chosen by reading the record it belongs to, in
  `V1-S5-012-PR2`, and [the migration report](../proof/testing/v1-s5-012-pr2-migration-report.md)
  says how each was read and which readings could have gone the other way.
- **It changes no public claim.** A rule refusing a record would fail the build; it
  would not move a claim's status. The one status the migration moved, it moved by
  measurement, and the report says so.
- **It does not make the review rules true.** See above; that is the reason there are
  six.

## Related documents

| Topic | Document |
|---|---|
| What the levels mean | [InferOps Evidence Levels (C0–C4)](evidence-levels.md) |
| The shape a record takes, and the path out of `v1alpha1` | [The claim and evidence data model, `v1alpha2`](evidence-record-model.md) |
| The decision that made a level a record's property | [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) |
| The register these rules govern | [Claim and evidence matrix](claim-evidence-matrix.md) |
| How every committed record was read against the levels | [The V1 evidence migration, claim by claim](../proof/testing/v1-s5-012-pr2-migration-report.md) |
| The suite that watches each rule fail | [`tests/testing/test_evidence_level_rules.py`](../../tests/testing/test_evidence_level_rules.py) |
| The validation record for this change | [`v1-s5-012-pr1-validation.md`](../proof/testing/v1-s5-012-pr1-validation.md) |
