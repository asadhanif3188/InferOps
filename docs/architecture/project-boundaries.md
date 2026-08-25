# Project boundaries

Status: **accepted scope rule**, in
[ADR 0004](decisions/ADR-0004-component-and-ownership-boundaries.md). It describes
where this project stops. It does not describe, plan, or commit to any other
project, and nothing named here is a dependency of V1.

Two earlier records already gesture at this boundary — serving *platforms* were
excluded from V1 because adopting one would put a second orchestration layer inside
a cluster this project already orchestrates, and hosted APIs were excluded because
the mandatory path must not need a paid API. This document turns those two asides
into one rule a reviewer can apply.

## The native serving path

**InferOps V1 owns exactly one serving path: a real open model, served by one
selected runtime, in a Kubernetes cluster on a contributor's own machine, with no
paid API and no account.**

That path is what the workload contract's `inferops-native-serving` capability
names. Its runtime and model are pinned in
[ADR 0002](decisions/ADR-0002-model-and-serving-runtime.md), and it is the only
capability for which this project may claim serving evidence.

Beside it sits exactly one other capability, `inferops-mock-serving`, which loads no
model, runs only in continuous integration, and
[may never certify real runtime behaviour](../serving/mock-and-real-boundary.md).

Two capabilities. Nothing else is served here.

## Three boundary rules

### 1. A capability a contract can name is not a capability this project provides

The workload contract lets a workload declare a dependency on model access,
evaluation, or a telemetry capability. None of those exists. The declaration is an
attachment point for a provider that may never be written, and V1's mandatory path
must work with none of them present.

The reviewable consequence: **no V1 code path may require a capability this project
does not implement.** A contract that declares one is describing an intent; a
component that depends on one is describing a dependency, and V1 has none.

### 2. Standing between a caller and a choice of providers is not this project's job

Anything that sits in front of more than one model provider — deciding which one
answers, holding the credential each one needs, or metering what a caller is allowed
to spend against them — is a gateway. V1 has no such component and must not grow one
incrementally.

The distinction is not about ambition; it is about what a serving claim means. This
project's serving evidence names one runtime digest and one model revision, on one
host, on one day. That claim is only meaningful because there is exactly one thing
it can be about. A component that chooses between providers at request time makes
"InferOps served this" a statement about a routing decision rather than about a
model, and no amount of documentation recovers the difference afterwards.

If such a component is ever built, it attaches through the contract's model-access
capability and appears in this architecture as an external provider — the same shape
as any other capability this project does not own.

### 3. Making one runtime work is not the same as engineering the runtime

Work whose subject is the runtime's own behaviour — getting one process to hold
several models, to answer more requests per second than it does, to hand traffic
from one version to the next, or to be given hardware in proportion to demand — is
deeper serving work. V1 does not do it and cannot claim it.

The selected runtime is a single-model, single-process server. Serving a second model
means a second deployment. That is the correct scope for V1, and it is also exactly
the ceiling deeper serving work would have to break through. What must survive that
replacement is the contract and the adapter interface, not the runtime.

This rule has teeth in one specific place: **no benchmark, throughput figure, or
capacity claim may be published from V1.** The one decode-rate figure this project
holds was derived from a single sequential request on one CPU host and is recorded
as explicitly not a benchmark. Publishing it as one would be the first step across
this boundary, and it would be a claim about a runtime this project did not write.

## What crosses the boundary, and how

Only two things, and both are already published or already refused:

| Crosses | Mechanism | Status |
|---|---|---|
| A workload's declared dependency on a capability | `spec.integrations` in the workload contract | Published; no provider exists |
| The identity of the serving capability a workload wants | `spec.model.servingCapability` | Published; two values, both owned here |

Everything else — telemetry export formats, evaluation results, cost records, policy
decisions, capability descriptors — would need a contract that does not exist. The
contracts index records each of them as unpublished, and each will be added when the
capability behind it exists rather than in advance.

## What this document does not do

- It does not name, schedule, or commit to any other project. "A gateway" and
  "deeper serving work" are shapes of work, not plans.
- It does not reserve scope. Another project taking on gateway or deep-serving work
  is neither promised nor prevented by anything here.
- It does not create a compatibility obligation. There is no consumer to be
  compatible with, and the contracts index says so.

## How this is reviewed

The rules above are judgement, not tests. A change that would cross one of them is
caught by a reviewer or not at all, which is why they are written as three
questions in [the boundary review checklist](boundary-review-checklist.md) rather
than left as principles.
