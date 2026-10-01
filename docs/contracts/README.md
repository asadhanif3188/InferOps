# Contracts

Status: one contract accepted and two schemas published, all at alpha maturity. The
platform domain reads a WorkloadContract and an EnvironmentBinding into typed objects and
selects the binding that serves a contract; nothing deploys, serves, or admits a workload
from either, and nothing renders one. The [renderer input
boundary](../domain/renderer-input-boundary.md) reads a validated contract and the binding
selected for it into a render context, refuses under one canonical vocabulary inputs that
are invalid, unbound, unsupported by a renderer, or in conflict over who owns a value, and
renders nothing. The platform domain
reads a RenderedWorkloadRelease and checks its provenance; nothing produces one.

This directory indexes versioned, machine-readable public contracts and the
compatibility policy each one carries. The schemas themselves live under
[`contracts/`](../../contracts/README.md); the documents here say what each schema
means, how it is versioned, which rules are enforced, and which are not.

| Contract | Version | Status | Document |
|---|---|---|---|
| WorkloadContract | `v1alpha1` | Accepted; parsed by [the workload domain model](../domain/workload-domain-model.md), and no runtime consumer exists | [WorkloadContract v1alpha1](workload-contract.md) |
| EnvironmentBinding | `v1alpha1` | Published schema with valid and invalid fixtures and a structural validator; parsed by the platform domain, which refuses conflicting bindings and selects the one serving a contract; the renderer input boundary reads the selected binding into a render context, and no renderer exists | [EnvironmentBinding v1alpha1](environment-binding.md) |
| RenderedWorkloadRelease | `v1alpha1` | Published schema with valid and invalid fixtures and a structural validator; a repository document, not a cluster resource; parsed by the platform domain, which defines how a release and its sources are hashed, recomputes the release identifier, refuses credential-shaped values, and compares a release with the contract and binding it names; no renderer produces one | [RenderedWorkloadRelease v1alpha1](rendered-workload-release.md) |

A published schema is a commitment about what will be accepted. It is not evidence
that anything accepts it, and it certifies no runtime behaviour.

## What a contract entry must carry

Owner, version, maturity, compatibility rules, valid and invalid fixtures, security
behaviour, telemetry implications, and validation evidence. A proposed document must
be visibly labelled as proposed.

Where a rule is stated but not yet enforced, the entry must say so in the same place
it states the rule. A reader must never have to discover from a failure that a rule
was aspirational.

## Not yet published

No capability descriptor, runtime descriptor, model-access API, evaluation result,
cost record, or policy decision exists. Each will be added when the capability
behind it exists rather than in advance.

The EnvironmentBinding and the RenderedWorkloadRelease are the two schemas published
before their consumer, and the exception is deliberate rather than a lapse in the rule
above. The renderer is the second version's first capability: it reads a binding and
writes a release, and it is built against both, so their shapes, the binding's boundary
with the WorkloadContract, and the release's rule for its own identifier have to be fixed
and tested first. Each document says, in its status line, what reads it and that nothing
renders one. The renderer's input side now exists as [its own
boundary](../domain/renderer-input-boundary.md); the renderer does not.

A **cost record** is the one of those whose shape is now written down. [The cost
method](../cost/cost-method.md) publishes the fields a record would carry, as part
of the method rather than as a schema here, because nothing in a running system
produces or consumes one; a repository tool that computes a record by hand validates
it against the method, not against a schema. That is the rule above applied rather than an exception to it: publishing a
schema would create a versioned commitment to a consumer that does not exist.

A **runtime and model compatibility matrix** does exist, at
[`contracts/workload/compatibility/`](../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json).
It is narrower than the cross-project compatibility matrix the integration
specification calls for: it records which artifact formats each serving runtime
loads and which single runtime-and-model pair this project has executed. It
records no provider, no provider version, and no certification level, because no
provider project and no certification process exist yet.
