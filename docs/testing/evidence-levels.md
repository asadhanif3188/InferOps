# InferOps Evidence Levels (C0–C4)

Status: **accepted definition**, in
[ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md),
effective for evidence classified after this document is merged. This is the single
authoritative current definition of what `C0` through `C4` mean in this repository.

> [!IMPORTANT]
> **InferOps Evidence Levels are project-defined. They are not an ISO standard, a
> NIST standard, a regulatory scheme, or an industry certification.** Nobody outside
> this repository has reviewed, accredited, or endorsed them. A level is a shorthand
> this project uses to say how a result was obtained, and it carries exactly the
> weight of the record behind it.

> [!NOTE]
> This document **defines**. It does not yet **enforce**, and it reclassifies nothing.
> The committed `v1alpha1` strategy data still carries the superseded level names and
> the ceiling rules built on them, every existing record keeps the level it was given,
> and no claim moves in the change that publishes this page. What is enforced today,
> and what is not, is set out in [what this document does not do](#what-this-document-does-not-do).

## Why levels exist

A repository accumulates passing checks, and a passing check has no opinion about
what it may be used to say. Left unlabelled, the cheapest result in the repository
becomes the one that gets cited, because it is the one that is always green.

These levels exist so that every published claim can answer four questions:

1. **What is claimed?**
2. **What evidence supports it?**
3. **Under what conditions was that evidence obtained?**
4. **What does that evidence not establish?**

The rule the whole model serves:

> **The strength of a claim must not exceed the evidence supporting it.**

The model is deliberately **claim-relative**. A level says how evidence was obtained.
It is not a score for the system, the repository, or the project.

## Three things that are routinely conflated

| Thing | What it describes | Where it lives |
|---|---|---|
| **Evidence level** | How the evidence was obtained: statically, with substitutes, for real, representatively, or in production | A property of **one evidence record** |
| **Evidence class** | What the result ran against, and the ceiling that carries under the currently enforced strategy | A property of a **test layer**, in [the certification document](certification.md) |
| **Claim status** | Whether this project publishes the property as a capability: certified, planned, deferred, or not claimed | A property of a **claim**, in [the claim and evidence register](claim-evidence-matrix.md) |

Keeping them apart is the point. A result can be real and narrow, or exhaustive and
worthless. An approval is not evidence. And a claim may sit at `not-claimed` while
strong evidence exists, because the evidence establishes something adjacent to the
statement somebody wanted to publish.

**One claim may be supported by several evidence records, each at its own level.** A
claim with static evidence, substituted-execution evidence, and runtime evidence is
better documented than a claim with runtime evidence alone, and none of the three
records is redundant. The weaker records are the history of how confidence was built,
and they are kept rather than replaced.

## The five levels

| Level | Name | The question it answers |
|---|---|---|
| `C0` | Static Evidence | What can be established without executing the target behaviour? |
| `C1` | Substituted Execution Evidence | What behaviour can be established when a claim-material component is replaced? |
| `C2` | Runtime Evidence | What does the actual claim-relevant implementation do in this recorded environment? |
| `C3` | Representative Evidence | What does the real system do under conditions deliberately chosen to represent intended use? |
| `C4` | Operational Evidence | What has been observed during genuine production operation, over a stated period? |

### C0 — Static Evidence

**Definition.** Relevant artifacts are inspected, analysed, or validated **without
executing the target behaviour**.

Typical forms: schema validation, manifest validation, configuration validation,
repository consistency checks, static policy inspection, document-to-data consistency
checks, and architecture inventory checks.

**C0 can support** statements such as: a schema exists and validates; a manifest
conforms to a required structure; a configuration contains the required fields;
committed artifacts are internally consistent with each other.

**C0 does not establish** that the runtime starts, that a workload executes, that a
model loads, that an API request succeeds, that a policy is enforced at run time,
that an alert is delivered, or that any reliability or performance requirement is
met.

### C1 — Substituted Execution Evidence

**Definition.** Behaviour is executed, but one or more components **material to the
claim** are replaced by a mock, stub, fake, simulator, or other substitute.

**The classification rule** is one question: *was a component material to evaluating
this claim substituted?* If it was, the record is `C1` for that claim, however
faithful the substitute is and however much of the rest of the path is real.

Typical forms: a real API with a mocked inference provider; a contract suite against
a stubbed backend; a control-flow test against a fake scheduler; an orchestration
test against a simulated external dependency.

**C1 can support** claims about a contract, about control flow, about error mapping,
about orchestration logic, and about the behaviour of the implementation *relative to
the substitute*.

**C1 does not establish** the behaviour of the component that was replaced. Making
the substitute more faithful does not change this, because a substitute built from
the contract cannot test the contract against reality — pointing one at the other
tests the author's understanding against itself, and it passes either way.

### C2 — Runtime Evidence

**Definition.** The **actual components required to evaluate the stated claim**
execute, in a recorded environment. Any substitution outside the claim-material path
is documented.

**The classification rule:** *real* is relative to the claim. For a claim that the
selected model serves a completion through the InferOps API, `C2` requires the
request to traverse the claim-relevant real path:

```text
request
   ↓
the InferOps API
   ↓
the real adapter
   ↓
the real inference runtime
   ↓
the pinned real model
```

If the inference backend is substituted, that claim has no `C2` evidence — it has
`C1` evidence, whatever else in the path was real.

Typical forms: a real model loaded by the real runtime; a real inference request
through the actual API and adapter; a real Kubernetes deployment lifecycle; an
executed upgrade or rollback; a real container and runtime integration.

**C2 can support** statements such as: the actual implementation can execute the
claimed behaviour; this real runtime and model pair works in the recorded
environment; a real lifecycle operation completed.

**C2 does not establish** representative capacity, a sustained latency target,
production reliability, portability to another environment, or behaviour under a
production workload distribution.

### C3 — Representative Evidence

**Definition.** The claim-relevant real system is exercised under workloads,
infrastructure, and operating conditions **deliberately chosen to represent intended
use**, against acceptance criteria declared before the run.

`C3` extends `C2`. It requires everything `C2` requires, and then all of:

- the claim-relevant real components execute;
- the target or production-like infrastructure is declared;
- the workload characteristics are declared;
- the representativeness assumptions are written down, as assumptions;
- acceptance criteria are defined **before** the run;
- results are measured against those criteria, including the ones that failed;
- limitations are recorded.

Typical forms: a representative concurrency test; a realistic prompt-size
distribution; a realistic request arrival pattern; a representative node or
accelerator shape; declared latency and error-rate targets; a controlled failure
experiment on representative infrastructure.

**A synthetic workload may contribute to C3.** Generated input is not a defect in a
representative experiment; it is usually how representativeness is achieved
deliberately rather than by accident. What matters is that the workload is
constructed to represent intended use, that the assumption is stated, and that the
claim-relevant real system executes.

**C3 does not establish** behaviour outside the tested workload distribution,
infrastructure, duration, or operating conditions, and it is not production
observation.

### C4 — Operational Evidence

**Definition.** Evidence obtained from **actual organizational production
operation**, under genuine production traffic and conditions, over a stated
observation period.

`C4` requires all of: an actual production system; genuine organizational production
usage or traffic; a recorded observation period; an identified production
environment; recorded metrics or observations; documented conditions and known gaps;
and stated limitations.

**Running in public cloud is not C4.** A cloud experiment is `C2`, or `C3` where it
meets the representativeness requirements above. Paying a provider does not produce
production operation, and neither does a long-running deployment nobody depends on.
What `C4` requires is that real users or real organizational workload depended on the
system over the period being reported.

**C4 does not establish** future performance, behaviour under failure modes that did
not occur during the observation window, or behaviour outside the observed workload
and environment.

**No evidence in this repository is C4, and none can be.** There is no organizational
production to draw it from. The level is defined so that the ceiling is visible rather
than implied, and so that no later record can reach for the word without meeting the
requirement.

## C0–C4 is not a maturity score

The numbering tracks increasing closeness to the intended operating context. It does
**not** mean that a higher number is better evidence.

A deliberately induced recovery experiment under controlled representative conditions
can be far stronger evidence for a failure-recovery claim than months of ordinary
production operation in which that failure never happened. The production record has
a higher number and says nothing about the claim.

> **The level describes the conditions under which the evidence was obtained. The
> claim decides whether that evidence is relevant and whether it is sufficient.**

Two consequences worth stating plainly:

- **C0–C4 is not a whole-system score.** There is no such thing as "InferOps is at
  C2". Levels attach to records, records support claims, and the claims are listed
  individually with their own limitations.
- **Governance approval does not raise a level.** A level is reached by a record.
  Merging a change, signing off a claim, or approving a release adds no evidence;
  [ADR 0015](../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md)
  D6 already says so, and it holds under this model unchanged.

## What a level does not carry

A level is a shorthand. It compresses one dimension and drops every other one, and
the dropped dimensions are where most misreading happens. These are **evidence-record
metadata, not levels**:

| Dimension | Example values | Why it is not a level |
|---|---|---|
| Failure mode / scenario purpose | timeout, denial, pod loss, unready model, rollback | *What was tested*, not how strongly. A failure experiment can be `C1`, `C2`, `C3`, or `C4` |
| Composition / topology | single process, two containers, a Kubernetes release, two projects integrated | *What the path was*, not how strongly. A composed path can be `C1`, `C2`, `C3`, or `C4` |
| Workload origin and shape | synthetic or captured; concurrency, prompt size, arrival pattern | Origin alone decides nothing; representativeness does, and only for `C3` |
| Provider and environment | `kind`, `docker-desktop`, a cloud region | Two `C2` records in different environments are not interchangeable |
| Hardware class | CPU, a named accelerator | A `C2` result on CPU says nothing about an accelerator |
| Versions and digests | image digest, model revision and hash, chart version | A record without them cannot be repeated, whatever its level |

**A level without a record is not evidence.** Every record that supports a published
claim states the components that executed, the components that were substituted, the
workload source and shape, the environment, the provider, the hardware class, the
runtime and model versions, the commands, the measurement method, the observation
period where one applies, the acceptance criteria, the actual results, the
limitations, and what the result does not establish.

```text
Evidence level  = the shorthand
Evidence record = the inspectable engineering artifact
```

## Claim status is separate

A claim's status is a publishing decision, not a level. The statuses this project
uses, and the register that holds them, are in
[the claim and evidence matrix](claim-evidence-matrix.md): `certified`, `planned`,
`deferred`, and `not-claimed`.

`not-claimed` means the available evidence does not justify publishing the property
as a capability — because verification has not run, because the available evidence is
too narrow, because verification was deliberately deferred, because the property is
out of scope, or because relevant evidence is absent.

> **`not-claimed` may never hide evidence that a requirement was tested and failed.**
> A failed check is recorded as a failed check, with the record that shows it. Moving
> a claim to `not-claimed` and deleting the failure is the one use of this status the
> model forbids outright.

## Illustrations

These illustrate the definitions. They classify **no** committed record, and no
record's level changes in the change that publishes this page.

```text
Claim:      The workload schema rejects an invalid field.
Evidence:   Schema validation and deterministic repository checks.
Level:      C0 — Static Evidence
Not:        That a running platform refuses the workload at admission.
```

```text
Claim:      The API maps a provider timeout to the canonical timeout response.
Evidence:   The API executed against a fake provider configured to time out.
Level:      C1 — Substituted Execution Evidence
Not:        That the real provider behaves this way under real failure conditions.
```

```text
Claim:      The selected model serves a real completion through the InferOps API.
Evidence:   A request through the actual API, real adapter, real runtime, and
            pinned model, in a recorded environment.
Level:      C2 — Runtime Evidence
Not:        Representative capacity, a sustained latency target, accelerator
            behaviour, or production reliability.
```

```text
Claim:      The system sustains a declared request rate within a declared p95
            latency and error-rate budget.
Evidence:   The real system on declared infrastructure, under a documented
            workload representing expected request size and concurrency, against
            criteria registered before the run.
Level:      C3 — Representative Evidence
Not:        Behaviour outside the tested distribution, infrastructure, or duration.
```

```text
Claim:      The service meets its latency and error-rate targets under production
            traffic.
Evidence:   Production telemetry over a stated observation window.
Level:      C4 — Operational Evidence
Not:        Future performance, unobserved failure modes, or behaviour outside the
            observed workload and environment. Unreachable in this repository.
```

## What this supersedes, and what it does not

Until [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md)
these five identifiers named a different set of things, decided by
[ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
D4 and published in [the certification document](certification.md):

| Identifier | Meaning before 2026-09-23 | How it is treated now |
|---|---|---|
| `C0` | Schema | Maps conceptually to **C0 — Static Evidence** |
| `C1` | Mock | Maps conceptually to **C1 — Substituted Execution Evidence** |
| `C2` | Real controlled | Maps conceptually to **C2 — Runtime Evidence** |
| `C3` | Failure | **No direct mapping.** Superseded as a level meaning |
| `C4` | Composed | **No direct mapping.** Superseded as a level meaning |

The first three map conceptually because they were already describing how a result
was obtained. *Conceptually* is doing work in that sentence: it means the old and new
definitions are about the same dimension, not that any particular record has been
re-examined against the new wording. That examination is a separate, claim-by-claim
piece of work.

**Why `C3` Failure has no direct mapping.** Failure is an experiment *purpose*. A
failure experiment produces `C1` evidence when the failure is induced through a
substitute, `C2` when the claim-relevant real components execute, `C3` when the
behaviour is exercised under representative conditions, and `C4` when it is observed
during real production operation. Putting failure at a fixed rank meant the same
experiment had a level before anybody asked what actually ran.

**Why `C4` Composed has no direct mapping.** Composition is a property of the *path*
being exercised. A composed path is `C1` if a material component is substituted, `C2`
if the real composed path executes, `C3` under representative conditions, and `C4`
only in production. Integrating a second system does not by itself make evidence
stronger; it changes what the evidence is about.

**What is not superseded, and is not changed here:**

- **The evidence classes and their ceilings.** `documented-unexecuted`,
  `local-static`, `mock`, `synthetic`, `estimated`, `local-real-cpu`,
  `cloud-real-cpu`, and `cloud-real-gpu` keep their meanings and their committed
  ceilings in [the certification document](certification.md), which stays the
  document a test layer is assigned from.
- **What a real-runtime record must contain.** The digest-not-tag rule, the model
  revision and per-file hash, the environment, the exact commands, the actual
  results, the limitations, and the failure diagnostics are unchanged and remain in
  [the certification document](certification.md).
- **The rule that a mock cannot certify real behaviour.** It is restated here as the
  `C1` classification rule and is argued at length in
  [the mock and real serving boundary](../serving/mock-and-real-boundary.md).
- **Any record's level.** Nothing is reclassified by this document.

## What this document does not do

- **It grants no level to anything.** Levels are reached by records.
  [The claim and evidence register](claim-evidence-matrix.md) and
  [the proof dashboard](../proof/dashboard.md) say which claims currently hold one.
- **It reclassifies nothing.** Every existing record keeps the level it was given
  under the previous definitions. Reviewing each one against the definitions above is
  deliberately separate work, so that a terminology change cannot promote a claim.
  **No claim may be upgraded by a documentation change.**
- **It is not yet machine-enforced.** What is enforced today is the previous model:
  the committed [`test-strategy.v1alpha1.json`](test-strategy.v1alpha1.json) still
  carries the legacy level names, still ranks `C3` and `C4` above `C2`, and still
  applies a `C1` ceiling to the `synthetic` evidence class — the specific rule the
  `C3` section above says is too broad. Those rules are left in force on purpose: a
  data contract published as `v1alpha1` is not re-pointed at new semantics in the
  change that writes the semantics down.

  **A versioned evidence-record model now exists, and it holds no committed data.**
  [`claim-evidence-matrix.v1alpha2.schema.json`](claim-evidence-matrix.v1alpha2.schema.json)
  is the shape the definitions above describe — a level on each record, several
  records per claim, substitution separated from workload origin — and
  [the model document](evidence-record-model.md) explains the version and the path
  out of `v1alpha1`. `V1-S5-011-PR2` published the schema and changed no register:
  [the claim and evidence matrix](claim-evidence-matrix.md) is still `v1alpha1`,
  still stores one level per claim, and is still what every consumer reads. Reading
  each record against the definitions above is `V1-S5-012-PR2`, and validators for
  the requirements the schema cannot check are `V1-S5-012-PR1`.
- **It defines no dispute procedure.** Since
  [ADR 0015](../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md)
  an authority exists that would arbitrate a classification — the
  `repository-maintainer` role, which holds `claim-evidence-sign-off` — but there is
  no procedure for raising a disagreement, no second holder to escalate to, and no
  outside party involved at any point.
- **It claims no external recognition.** Repeating the banner at the top of this page,
  because it is the sentence most likely to be dropped in a summary: these levels are
  project-defined, and they are not an ISO, NIST, regulatory, or industry
  certification standard.

## Related documents

| Topic | Document |
|---|---|
| The decision that established this model | [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) |
| The data model that can hold a record at one of these levels | [The claim and evidence data model, `v1alpha2`](evidence-record-model.md) |
| The decision that established the previous one | [ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md) |
| Evidence classes, their ceilings, and what a real record must contain | [Certification levels and evidence classes](certification.md) |
| Every claim, its status, its evidence, and its limitation | [Claim and evidence matrix](claim-evidence-matrix.md) |
| The same, as one generated page | [The V1 proof dashboard](../proof/dashboard.md) |
| Test layers, lanes, and evidence retention | [Test and CI strategy](test-strategy.md) |
| Why a mock cannot stand in for a real provider | [The mock and real serving boundary](../serving/mock-and-real-boundary.md) |
| Who signs that a claim matches its evidence | [Decision ownership and sign-off authority](../governance/decision-authority.md) |
| Where records live and what sections each carries | [Evidence records](../proof/README.md) |
