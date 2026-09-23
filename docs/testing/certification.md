# Certification levels and evidence classes

Status: **accepted definition** for the evidence classes, their ceilings, and what a
real-runtime record must contain, in
[ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md).
It certifies nothing by existing.

> [!IMPORTANT]
> **The level meanings below are superseded.** Since 2026-09-23,
> [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md)
> redefines `C0` to `C4`, and
> [InferOps Evidence Levels (C0–C4)](evidence-levels.md) is the single authoritative
> current definition. `C3` Failure and `C4` Composed are superseded outright: failure
> is a scenario and composition is a topology, and neither is a strength. The other
> three map conceptually — Schema to Static, Mock to Substituted Execution, Real
> controlled to Runtime — and *conceptually* means the definitions describe the same
> dimension, not that any record has been re-examined.
>
> **Nothing here is reclassified, and this document is still the one a layer is
> assigned from.** The evidence classes, their ceilings, and the contents a real
> record must carry are unchanged and stay in force. The table immediately below is
> retained as the meaning every record written before 2026-09-23 was classified
> under, so that a historical record stays readable. Re-examining those records
> against the new definitions is `V1-S5-012-PR2`, and until it runs, no level in this
> repository has moved.

Two things are described here and they are routinely conflated. **Certification level
describes proof strength.** **Evidence class describes what the proof ran against.**
A result can be real and weak, or exhaustive and worthless. Keeping them separate is
the only way to say so. [The evidence-level specification](evidence-levels.md) adds
a third that this document never separated out: a level belongs to an **evidence
record**, and a claim's **status** is a different question again.

## Certification levels

**Superseded as current meanings.** This table is the historical definition, kept for
reading records written under it. The current one is in
[InferOps Evidence Levels (C0–C4)](evidence-levels.md).

| Level | Name | Meaning | In V1 scope |
|---|---|---|---|
| `C0` | Schema | Documents, schemas, and inventories in this repository are internally consistent and validate. Nothing is executed against a runtime. | yes |
| `C1` | Mock | A consumer passes a deterministic contract suite against a labelled mock provider. | yes |
| `C2` | Real controlled | A real provider works in a controlled, reproducible environment carrying an explicit environment label. | yes |
| `C3` | Failure | Timeout, denial, unavailability, retry, and recovery are proven against a real provider. | no |
| `C4` | Composed | End-to-end integration across at least two real projects is proven. | no |

**V1 claims nothing above C2.** `C3` and `C4` are defined here so that the ceiling is
visible rather than implied, and a test refuses to let an active claim require a level
outside V1 scope: such a claim must either be deferred or lowered.

`C4` is not merely unreached. There is no second project, so it is not reachable at
all from inside this repository.

Both sentences describe the superseded meanings and both stay true of them. Under
[the current definitions](evidence-levels.md) the ceiling is unchanged in practice
and the reasons differ: `C3` Representative Evidence is reachable in principle and
nothing is classified there, and `C4` Operational Evidence is unreachable because
there is no organizational production to observe rather than because there is no
second project. The committed strategy data still ranks the superseded levels and
still refuses an active claim requiring `C3` or `C4`, which is what the enforcement
below acts on.

## Evidence classes

An evidence class describes what produced a result, and it carries a hard ceiling on
what that result may certify.

| Class | What produced it | Ceiling |
|---|---|---|
| `documented-unexecuted` | A statement in a document. Nothing ran. | certifies nothing |
| `local-static` | A deterministic check over files in this repository. No network, no cluster, no model, no clock, no randomness. | `C0` |
| `mock` | A labelled mock provider that loads no model. | `C1` |
| `synthetic` | Generated inputs or a simulated environment rather than the real one. | `C1` |
| `estimated` | A calculation rather than a measurement. | certifies nothing |
| `local-real-cpu` | The real component, on a contributor's own machine, on CPU, with versions and commands recorded. | `C2` |
| `cloud-real-cpu` | The real component on authorized cloud CPU capacity, with provider, region, node shape, budget, and verified cleanup recorded. | `C2` |
| `cloud-real-gpu` | The real component on authorized cloud GPU capacity, with the accelerator stack, allocation mode, budget window, and verified cleanup recorded. | `C2` |

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

## Why a mock stops at C1

[The mock and real serving boundary](../serving/mock-and-real-boundary.md) argues
this at length and is the accepted rule; this section says how the strategy makes it
mechanical.

The argument in one line: **certification asks whether the contract matches reality,
and a mock is built from the contract.** Pointing one at the other tests the author's
understanding against itself. It passes. It would also pass if the contract were
wrong, which is the only case where the test was worth running.

The mechanism is a ceiling in the data rather than a warning in a document. Each
layer declares an evidence class; each class declares the highest level it can
support; a test refuses a layer that certifies above its class. A second test refuses
a claim requiring `C2` or above whose qualifying layers are `mock`, `synthetic`, or
`estimated`. A third refuses a layer labelled with an unreal class that also claims to
need a real model, which is the shape a misfiled layer takes.

The consequence a contributor actually feels: making the mock more faithful does not
raise what it can certify, and no amount of coverage in the default lane produces a
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

## Where certifying records live

Under [`docs/proof/`](../proof/), committed, retained for as long as the claim stands.
A lane's raw artifacts expire; a certifying record does not. The promotion rule,
the retention periods, and what happens to a superseded record are in
[the test strategy](test-strategy.md).

## What this document does not do

- **It no longer defines what a level means.**
  [InferOps Evidence Levels (C0–C4)](evidence-levels.md) does, under
  [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md).
  What stays here is what a class may support, the ceiling each one carries, and what
  a record certifying real behaviour must contain.
- It does not grant a level to anything. Levels are reached by records, and
  [the claim/test matrix](claim-test-matrix.md) says which claims currently hold one.
- It does not define a process for disputing a level. Since
  [ADR 0015](../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md)
  there is an authority that would arbitrate one — the `repository-maintainer` role,
  which holds `claim-evidence-sign-off` — but no procedure for raising a dispute, no
  second holder of the role to escalate to, and no outside party involved at any
  point. Naming who decides is not the same as defining how a disagreement is heard.
- It does not describe integration certification for other projects. V1 has no second
  project and publishes no capability descriptor.
