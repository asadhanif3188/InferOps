# Certification levels and evidence classes

Status: **accepted definition** for the evidence classes, their ceilings, and what a
real-runtime record must contain, in
[ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md).
It certifies nothing by existing.

> [!IMPORTANT]
> **This document does not define what a level means.**
> [InferOps Evidence Levels (C0–C4)](evidence-levels.md) does, under
> [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md), and
> it is the single authoritative definition. The levels are project-defined; they are
> not an ISO, NIST, regulatory, or industry certification standard, and the word
> *certification* in this document's name and in the strategy's field names is an
> identifier rather than a claim that anybody outside this repository certified
> anything.
>
> Until `V1-S5-012-PR2` this page also published the level meanings ADR 0005 D4
> accepted. Those meanings are superseded, and the mapping from each of them to the
> current one is published in [the specification](evidence-levels.md#what-this-supersedes-and-what-it-does-not)
> and in ADR 0016 rather than restated here. A record written before 2026-09-23 is
> read through that mapping.

Three things are described across this document and its neighbours, and they are
routinely conflated. **An evidence level says how one evidence record was obtained**,
and belongs to the record. **An evidence class says what a test layer runs
against**, and carries a ceiling on the level that layer may reach. **A claim's
status** says whether the project publishes the property at all. A result can be real
and narrow, or exhaustive and worthless; keeping the three apart is the only way to
say so.

## The levels a layer may reach

A layer names the highest level it may reach, and its evidence class caps that. The
identifiers are the ones [the specification](evidence-levels.md) defines; this table
says only which of them V1 layers may reach and where each is used as a ceiling.

| Level | In V1 scope | Used here as the ceiling of | Defined in |
|---|---|---|---|
| `C0` | yes | `local-static` | [Static Evidence](evidence-levels.md#c0--static-evidence) |
| `C1` | yes | `mock`, `synthetic` | [Substituted Execution Evidence](evidence-levels.md#c1--substituted-execution-evidence) |
| `C2` | yes | `local-real-cpu`, `cloud-real-cpu`, `cloud-real-gpu` | [Runtime Evidence](evidence-levels.md#c2--runtime-evidence) |
| `C3` | no | no class | [Representative Evidence](evidence-levels.md#c3--representative-evidence) |
| `C4` | no | no class | [Operational Evidence](evidence-levels.md#c4--operational-evidence) |

**No V1 layer reaches above `C2`, and no V1 claim requires more.** A test refuses an
active claim requiring a level outside V1 scope: such a claim must be deferred or
lowered. `C3` is reachable in principle — it needs declared representativeness and
acceptance criteria registered before the run — and no record reaches it. `C4` is
unreachable from this repository, because there is no organizational production to
observe.

## Evidence classes

An evidence class describes what produced a result, and it carries a hard ceiling on
the level a layer of that class may reach.

| Class | What produced it | Ceiling |
|---|---|---|
| `documented-unexecuted` | A statement in a document. Nothing ran. | certifies nothing |
| `local-static` | A deterministic check over files in this repository. No network, no cluster, no model, no clock, no randomness. | `C0` |
| `mock` | A labelled mock provider that loads no model. | `C1` |
| `synthetic` | A simulated environment rather than the real one: a simulator or emulator standing in for a component the result is about. Generated input is not this class. | `C1` |
| `estimated` | A calculation rather than a measurement. | certifies nothing |
| `local-real-cpu` | The real component, on a contributor's own machine, on CPU, with versions and commands recorded. | `C2` |
| `cloud-real-cpu` | The real component on authorized cloud CPU capacity, with provider, region, node shape, budget, and verified cleanup recorded. | `C2` |
| `cloud-real-gpu` | The real component on authorized cloud GPU capacity, with the accelerator stack, allocation mode, budget window, and verified cleanup recorded. | `C2` |

**`synthetic` no longer covers generated input.** Until `V1-S5-012-PR2` the class read
*generated inputs or a simulated environment*, and its `C1` ceiling therefore capped
any layer whose prompts were generated, however real the path they travelled. That
is the rule [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md)
D3 records as too broad: a simulated environment is a substitution and belongs at
`C1`, and a workload's origin is not. The class now names only the first, and a layer
whose only generated part is its input is classed by what it ran against. No layer
and no gate in the committed strategy uses `synthetic`, so the change moves no
layer's ceiling; what it removes is the rule, before somebody relied on it.

`local-static` extends the vocabulary [CONTRIBUTING](../../CONTRIBUTING.md) publishes.
The existing proof records already describe themselves in prose as "local static
evidence"; naming the class makes the phrase checkable instead of conventional.

No V1 record uses `cloud-real-cpu` or `cloud-real-gpu`. They are defined because the
rule about them has to exist before the capacity does: **normal CI may never allocate
paid GPUs**, a cloud suite is manual or runs on an explicitly authorized labelled
runner, and an absence of paid capacity fails or skips the cloud-specific
certification honestly. It never falls back to a mock.

`production-experience` is a published label and it is deliberately absent from the
table above, because the table lists the classes this strategy may assign to a layer
and no layer here can produce production experience. There is no organizational
production to draw it from, and public-cloud execution is not production operation.
It stays part of the evidence vocabulary [CONTRIBUTING](../../CONTRIBUTING.md)
publishes — unreachable rather than unmentioned — so that a future record cannot
reintroduce it as though the question had never been asked.

## A layer ceiling is not a record's level

The ceilings above constrain what a **test layer** may reach. Since `V1-S5-012-PR2`
every evidence record in [the claim and evidence register](claim-evidence-matrix.md)
carries its own level, decided by what that record executed and what it substituted,
and checked by the rules in [the rule catalogue](evidence-level-rules.md) rather than
by the class of the layer that produced it. The two agree in the direction that
matters — a record that substituted a claim-material component cannot be `C2`, and a
layer of a mock class cannot reach `C2` — and they are held by different code so
that neither can quietly stand in for the other.

## Why a mock stops at C1

[The mock and real serving boundary](../serving/mock-and-real-boundary.md) argues
this at length and is the accepted rule; this section says how the strategy makes it
mechanical.

The argument in one line: **the question is whether the contract matches reality,
and a mock is built from the contract.** Pointing one at the other tests the author's
understanding against itself. It passes. It would also pass if the contract were
wrong, which is the only case where the test was worth running.

The mechanism is a ceiling in the data rather than a warning in a document. Each
layer declares an evidence class; each class declares the highest level it can
support; a test refuses a layer that reaches above its class. A second test refuses
a claim requiring `C2` or above whose qualifying layers are `mock`, `synthetic`, or
`estimated`. A third refuses a layer labelled with an unreal class that also claims to
need a real model, which is the shape a misfiled layer takes. For a record, the same
rule is the substitution rule: a record that replaced a component material to its
claim is `C1` for that claim, and the validator refuses it at `C2`.

The consequence a contributor actually feels: making the mock more faithful does not
raise what it can support, and no amount of coverage in the default lane produces a
serving claim. The only thing that produces one is running the real thing and
recording it.

## What a C2 record must contain

A `C2` claim requires an executed record. No record, no claim — not a weaker claim,
no claim. The record names:

- the runtime image **digest**, not a tag; a tag is a label that can be moved;
- the model revision and its per-file hash, computed and compared against the
  published value;
- the environment: operating system, hardware class, cluster version, and the tool
  versions that matter;
- the exact commands, in an order somebody else can repeat;
- the actual results, including the ones that disagree with the expectation;
- the limitations, and any pre-registered threshold the run failed;
- the failure diagnostics, where anything failed.

For a cloud record, add the provider and region without account identifiers, the node
shape and accelerator stack, the allocation mode, the authorization and maximum
budget with its price source, the infrastructure owner, the shutdown deadline, and
verified cleanup. And an explicit statement that it is not production.

The register's `v1alpha2` shape asks the same of every record at any level, in
fields a validator reads: what executed, what was substituted, where the workload came
from, where it ran, the immutable identifiers or the record that names them, how to
run it again, its limitations, and what it does not establish.

## Where certifying records live

Under [`docs/proof/`](../proof/), committed, retained for as long as the claim stands.
A lane's raw artifacts expire; a certifying record does not. The promotion rule,
the retention periods, and what happens to a superseded record are in
[the test strategy](test-strategy.md).

## What this document does not do

- **It does not define what a level means.**
  [InferOps Evidence Levels (C0–C4)](evidence-levels.md) does, under
  [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md).
  What stays here is what a class may support, the ceiling each one carries, and what
  a record certifying real behaviour must contain.
- It does not grant a level to anything. Levels are reached by records, and
  [the claim and evidence register](claim-evidence-matrix.md) says which records hold
  which level.
- It does not define a process for disputing a level. Since
  [ADR 0015](../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md)
  there is an authority that would arbitrate one — the `repository-maintainer` role,
  which holds `claim-evidence-sign-off` — but no procedure for raising a dispute, no
  second holder of the role to escalate to, and no outside party involved at any
  point. Naming who decides is not the same as defining how a disagreement is heard.
- It does not describe integration certification for other projects. V1 has no second
  project and publishes no capability descriptor.
