# Certification levels and evidence classes

Status: **accepted definition**, in
[ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md),
effective for evidence produced after this document is merged. It certifies nothing
by existing. It fixes what a certification level means, what each evidence class may
support, and why a mock stops at C1 — before there is an argument about a specific
claim to settle.

Two things are described here and they are routinely conflated. **Certification level
describes proof strength.** **Evidence class describes what the proof ran against.**
A result can be real and weak, or exhaustive and worthless. Keeping them separate is
the only way to say so.

## Certification levels

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

`production-experience` is deliberately absent. Public-cloud execution is not
production operation, and there is no organizational production to draw the label
from. Adding it would create exactly the misuse it is named after.

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

- It does not grant a level to anything. Levels are reached by records, and
  [the claim/test matrix](claim-test-matrix.md) says which claims currently hold one.
- It does not define a process for disputing a level. There is no maintainer roster
  to arbitrate one, which is a known governance gap recorded in
  [CONTRIBUTING](../../CONTRIBUTING.md).
- It does not describe integration certification for other projects. V1 has no second
  project and publishes no capability descriptor.
