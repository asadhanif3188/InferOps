# ADR 0004: Component architecture and resource ownership boundaries

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-08-25 |
| Date accepted | 2026-08-25, for D1 through D6 only |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | None |

> [!IMPORTANT]
> This record decides boundaries for components that **do not exist**. There is no
> platform API, no adapter, no Helm chart, and no Terraform configuration in this
> repository. Nothing here is evidence that the design works; it is a constraint on
> what may be built, adopted before there is an implementation to argue with.
>
> One half of it is machine-checked. The ownership inventory this record accepts is
> committed as data and validated by `tests/architecture/test_resource_ownership.py`,
> so single ownership and the Terraform/Helm disjointness are properties a change
> has to break a test to violate. The component half has no such check, because
> there is no code, and this record does not pretend otherwise.
>
> D7 is **not decided**. Two resources have no owner, are recorded as unowned, and
> are deferred out of V1 rather than assigned to a tool for tidiness.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Component decomposition and dependency direction | **Accepted** as a constraint on unwritten code | Review only. Nothing enforces it; there is no code to enforce it against |
| D2 | The serving runtime is a separate deployment, not a sidecar | **Accepted** | The memory-mapping measurement in ADR 0002, and the probe mapping it proved |
| D3 | Terraform owns prerequisites, Helm owns the release, controllers own derived objects | **Accepted** | A committed inventory, with single ownership and disjointness enforced by a test |
| D4 | The model cache is a prerequisite, not a release resource | **Accepted** | The teardown finding in the feasibility record: a cache inside the release's own scope was destroyed and cost a full re-download |
| D5 | The trust boundary map | **Accepted as a map only** | Every control it names is unimplemented. It records where controls would go and who owns deciding them |
| D6 | Two serving capabilities, and no gateway or deep-serving work | **Accepted** as a scope rule | Review only |
| D7 | Who owns a telemetry collector, and an ingress or load-balancer implementation | **Not decided** | Nothing. Both are recorded as unowned and deferred |

## Context

Three decisions are accepted and one contract is published: an environment, a
runtime and model selected on executed proof, the schema tooling behind the
contract, and the contract itself. What does not exist is any statement of what
components there will be, which may depend on which, and which tool is allowed to
create which resource.

That gap is not neutral. The next work in this project writes a platform API, an
adapter, a chart, and a Terraform configuration at roughly the same time. Ownership
boundaries decided while those are being written are decided by whoever types first,
and the failure mode is specific and well known: two tools reconciling one object,
each undoing the other, with the winner determined by execution order.

The architecture index records this gap explicitly — no infrastructure ownership
boundary and no application architecture has been selected. This record closes it.

Two constraints come from outside. The accepted local cluster ships no ingress
controller and no load-balancer implementation, so external access is a port-forward
and nothing here may assume otherwise. And the accepted cleanup rules already grant
a label-scoped teardown the right to delete project-labelled objects, which
collides with any tool that owns a long-lived project-labelled resource — a
collision this record has to resolve rather than inherit.

## Decision criteria

A boundary is judged against, in order:

1. **Unambiguous lifecycle** — for every resource, can a reader name the one thing
   that creates it and the one thing that destroys it?
2. **Testability without infrastructure** — can the largest part of the system be
   exercised without a cluster, a model, or a network?
3. **Survivability of the runtime choice** — if the selected serving runtime is
   replaced, how much has to change?
4. **Honest claims** — does the boundary make it harder to publish a claim the
   evidence does not support?
5. **Reviewability** — can a reviewer apply the boundary from the repository, without
   knowing what was intended?

Criterion 1 is a gate. A design that leaves one resource with two plausible owners
fails regardless of its merits elsewhere.

## D1 — Component decomposition and dependency direction

**Accepted** as a constraint. Nothing enforces it.

The components and the direction dependencies may point are drawn in
[the system architecture](../system-architecture.md). The rule:

> Nothing in the platform domain may import a Kubernetes client, a Helm library, a
> serving-runtime SDK, or an HTTP framework. The domain owns the serving-adapter
> interface; adapters implement it; the API selects one at composition time.

| Alternative | Assessment |
|---|---|
| **Domain owns the interface; adapters implement it** | **Selected.** The largest part of the system is testable with no cluster, no model, and no network, which is criterion 2. Replacing the runtime is an adapter change, which is criterion 3 |
| Domain calls the runtime directly | Fewer moving parts, and it makes the runtime's vocabulary the platform's vocabulary. Every contract change would then be a runtime change and the reverse. It fails criterion 3 outright |
| A Kubernetes controller with a custom resource | The natural end state if InferOps becomes a controller, and it would make the contract a first-class API object. Premature: it binds the contract to an API server before any component reads a contract at all, and it makes every test need a control plane |
| One process containing API, domain, adapter, and runtime configuration | Simplest to write and impossible to review. The composition point stops being one small place and becomes the whole program |

The cost is stated because the enthusiastic version of this omits it: **an
interface with exactly two implementations, one of which is a mock, is an interface
designed against a sample of one.** The real runtime is the only implementation that
has ever been observed, so the interface will encode assumptions from it and will
discover them when a second real runtime arrives. That is a known and accepted risk,
not an argument that the abstraction is free.

There is a second, sharper cost. An adapter interface is exactly the surface that
makes it easy to run the whole platform against a mock and feel finished. The rule
that a mock may never certify real runtime behaviour is what stands between this
design and that outcome, and it is a published rule rather than an instinct for
precisely this reason.

## D2 — The serving runtime is a separate deployment, not a sidecar

**Accepted**, on measurement rather than preference.

The comparison and the deciding measurement are in
[the system architecture](../system-architecture.md). In short: the selected runtime
memory-maps its weights, and two identical pods were observed reporting 2.167 GiB and
531 MiB for the same work, because the kernel charges mapped pages to whichever
control group faults them in first. Sizing a memory limit against that is hard on
its own; sizing it for a pod that also holds an API process is worse. Model load and
process liveness are also different questions with different probes, and the runtime's
health endpoint answers 503 while loading — correct for readiness, wrong for liveness.

The accepted cost is an additional failure mode: the API can be healthy while the
runtime is unreachable. This is why `model not ready`, timeout, and internal failure
are canonical platform errors rather than incidental HTTP statuses, and why the
inference flow asks about readiness instead of assuming it.

## D3 — Terraform owns prerequisites, Helm owns the release, controllers own derived objects

**Accepted**, and the part of it that can be checked is checked.

The rule and every resource it applies to are in
[the resource ownership document](../resource-ownership.md), and the authoritative
form is [the inventory](../resource-ownership.v1alpha1.json).

| Alternative | Assessment |
|---|---|
| **Terraform prerequisites, Helm release, controllers derived** | **Selected.** Each tool owns what matches its lifetime. The split is expressible as data and therefore checkable |
| Helm owns everything, including the namespace | One tool, one lifecycle, no boundary to police — and no way to have anything outlive a release. The model cache would be destroyed on every uninstall, which D4 shows is the thing that actually hurt |
| Terraform owns everything through a Kubernetes provider | Also one tool. It puts workload rollout into a state file, makes every application change a plan-and-apply cycle, and reconciles objects that controllers are simultaneously rewriting |
| A GitOps controller owns the cluster state | The strongest alternative for a real environment, and genuinely better at drift. It adds a controller to a cluster this project already asks a contributor to run on a memory-constrained host, and it moves the boundary rather than removing it: something still has to say which resources are prerequisites |
| Kustomize instead of Helm | A real option for rendering. It does not change this boundary at all — the same split would apply — so it is a packaging choice for a later decision, not an alternative to this one |

Three prohibitions carry the rule:

1. Helm is never invoked with `--create-namespace`. One flag, recommended almost
   everywhere, and it silently gives both tools the namespace.
2. Terraform never imports or adopts an object a release installed.
3. Neither tool creates, reconfigures, or deletes a cluster.

### The overlap this decision found

The accepted cleanup rules describe partial teardown as deleting *"only objects
matching the project label selector inside `inferops-` namespaces"*, and every object
this project creates carries the project label. A prerequisite would therefore be
inside the blast radius of a routine scoped teardown, giving one resource two
destroyers.

It is not a live defect: the implemented teardown is bound to one smoke-test
namespace and sweeps nothing else, and no prerequisite exists to sweep. It becomes
one the moment either the sweep is generalised to match the accepted wording or
Terraform is written.

A resolution is specified: a lifecycle label that a scoped sweep must exclude, set on
the namespace metadata Terraform owns, plus a platform namespace distinct from the
smoke-test namespace the environment scripts already delete outright. **Neither is
implemented, here or anywhere.** This record does not modify the environment scripts,
and the overlap is closed on paper only — which is why it is carried as an open risk
rather than as a fix.

## D4 — The model cache is a prerequisite, not a release resource

**Accepted**, on the teardown finding in the feasibility record.

In the executed trial the weight cache was placed inside the trial's own namespace,
and scoped teardown destroyed it; re-running cost the full download again. That
download is roughly 1.7 GiB over a transport that does not validate certificates, so
the published file hash carries the entire integrity argument and repeating the
transfer repeats the exposure.

| Alternative | Assessment |
|---|---|
| **A Terraform-owned claim, filled by a release-owned job** | **Selected.** Lifetime matches the layer. Exactly one sanctioned handoff, named in the claim's own row |
| A Helm-owned claim | Simplest, and `helm uninstall` destroys the weights. That is the behaviour the trial already paid for |
| A Helm-owned claim with a retention annotation | Keeps the object and makes ownership conditional on an annotation nobody reads during an incident. Ownership that depends on a flag is not ownership |
| A host path mounted into the cluster | Fastest and it breaks the isolation rules: it reaches outside the project's own resources onto a contributor's filesystem |
| Bake the weights into an image | Reproducible and pinned, at 1.7 GiB per image on a host with about 23 GB free. It also makes every runtime image rebuild a weight redistribution, with the licence question that implies |

The accepted cost: `helm uninstall` now leaves roughly 1.7 GiB occupied until
`terraform destroy` runs. On the measured host that is not negligible, and teardown
was separately shown not to return disk space to the host at all. This must be
documented where an operator will find it rather than discovered as a disk-full
error.

## D5 — The trust boundary map

**Accepted as a map only.** Five boundaries are named, and what each does and does
not defend is stated in [the system architecture](../system-architecture.md).

This record asserts **no security property**. Of the five boundaries, two have any
enforcement today and both were inherited: artifact pinning with hash verification,
and the cluster identity guard in the environment scripts. The namespace, workload,
and caller boundaries have none — there is no authentication, no authorization, no
rate limit, and no tenant isolation anywhere in this project.

Naming a boundary with no control behind it is worth doing only if the absence is
stated as loudly as the boundary. The map does that in the same table as the
boundary itself. Threat modelling, the control set, and their verification belong to
the security baseline decision, which does not exist yet.

## D6 — Two serving capabilities, and no gateway or deep-serving work

**Accepted** as a scope rule. The rule and its three tests are in
[the project boundaries document](../project-boundaries.md).

The short form: this project serves one real open model through one selected runtime,
plus a mock that may never certify anything. It does not stand in front of a choice
of providers, hold their credentials, or meter what a caller may spend against them —
that is gateway work. It does not engineer the runtime's own behaviour, whether that
means several models in one process, more throughput from one, traffic handed between
versions, or hardware allocated to demand — that is deeper serving work. And it
publishes no throughput, latency, capacity, or benchmark figure, because the only such
number it holds came from a single sequential request on one CPU host and is recorded
as explicitly not a benchmark.

This reserves nothing and plans nothing elsewhere. It states where this project
stops.

## D7 — Telemetry collection and ingress ownership

**Not decided.** Two resources are recorded with no owner and deferred out of V1:

- a metrics collector, store, and dashboards — components will expose metrics and
  nothing will collect them;
- an ingress controller and a load-balancer implementation — the accepted local
  cluster ships neither, and installing them was recorded as an open cost.

Both appear in the inventory carrying an explicit `undecided` owner, and a test
requires that any resource with that owner is deferred. That is deliberate: an
unowned resource inside V1 scope is exactly the ambiguity criterion 1 rejects, so the
inventory refuses to represent one. Recording the gap is what stops it being closed
by whoever adds the first scrape target.

## Consequences

- **The domain layer becomes the largest testable surface in the project**, and every
  test of it runs with no cluster, no model, and no network. The price is a
  composition point that knows about everything, which must stay small and must stay
  singular.
- **An adapter interface with one real implementation encodes that implementation's
  assumptions.** This will be discovered when a second real runtime arrives, not
  before.
- **Two deployments where one would do.** An extra Service, an extra probe set, an
  extra network hop, and a service-to-service failure mode that is now a first-class
  canonical error rather than a timeout.
- **`helm uninstall` stops being a full cleanup.** It leaves the namespace, its
  metadata, and roughly 1.7 GiB of weights. The reclamation step is `terraform
  destroy`, and the ordering — release first, prerequisites second — is load-bearing
  rather than stylistic, because destroying the namespace cascades.
- **Two constraints land on work that has not started**: the scoped teardown must
  exclude prerequisites before it is ever generalised, and the platform namespace
  must be distinct from the smoke-test namespace.
- **A new test directory and a new committed data file** enter the repository, with
  the same posture as the contract suite: reads only files here, no network, no
  clock, no randomness.
- **The published serving claim stays narrow by construction.** D6 makes "InferOps
  served this" a statement about one runtime and one model, which is the only form
  of it the evidence supports.

## Compatibility impact

None. This record introduces no schema, no API surface, and no change to the
published contract. There is no released version, no consumer, and no supported
environment for it to break.

It does add a committed data file under `docs/architecture/`. Nothing external
consumes it, it is not a contract, and it carries a `v1alpha1` marker only so that
it can be versioned in the same way as everything else here if it ever needs to be.

## Security considerations

This record asserts no security property. Four points are recorded because the
decisions make them relevant later:

- **A separate serving deployment adds cluster-internal traffic** between two pods
  that previously would have shared a loopback interface. That traffic is unencrypted
  and unauthenticated, and the network policy planned for it is a declaration until
  a test proves the local cluster's network plugin enforces one.
- **A long-lived model cache is a long-lived copy of an artifact whose transport was
  not authenticated.** D4 makes the hash check load-bearing on every acquisition, not
  only the first, and the acquisition job is a no-op only when it has verified what
  is already there.
- **Nothing in this project creates, rotates, or reads secret material.** A chart may
  mount a secret by name and may never template one carrying a value. The contract
  already has no field a secret value could be written into.
- **A tenant identifier in a contract is a request, not an assertion**, and the
  boundary where it would have to be validated is the one with no controls at all.

Threat modelling, the control set, scanner selection, and supply-chain attestation
belong to the security baseline decision. None of them is made here.

## Evidence

Documented and executed, on 2026-08-25, on the same Windows host as every earlier
record in this repository. The full record is
[the V1-S0-005-PR1 change validation](../../proof/architecture/v1-s0-005-pr1-validation.md).

| Component | Version |
|---|---|
| Python | 3.12.6 |
| `pytest` | 8.3.4 |

```text
python -m pytest tests/architecture -q
357 passed
```

What that result establishes: the ownership inventory is internally consistent, no
resource has two owners, Terraform's set and Helm's set do not intersect, every
survival claim is drawn from the declared operations, forms a prefix of the
blast-radius ordering, and never contradicts the operation that destroys the
resource, prerequisites outlive releases, release objects do not outlive
prerequisites, derived resources have no tool owner, an unowned resource is
deferred, evidence is cited only by implemented rows, and the ownership document and
the inventory publish the same identifiers in both directions.

What it establishes about any Terraform configuration or Helm chart: **nothing.**
Neither exists. This is a check on a design commitment, not on an implementation,
and the day an implementation exists this suite will not be sufficient.

## Risks, assumptions, and open questions

| ID | Item | Status | Impact |
|---|---|---|---|
| R1 | The ownership inventory describes tools that do not exist | Open, by construction | Nothing compares the inventory to a real Terraform configuration or chart. It can be wrong in ways no test here can find |
| R2 | The scoped teardown could delete a Terraform-owned prerequisite if it is generalised to match the accepted cleanup wording | Open | Two destroyers for one resource. Mitigated only by a lifecycle label that is specified here and implemented nowhere |
| R3 | The adapter interface has one real implementation | Open | It will encode that runtime's assumptions, and the cost surfaces when a second runtime is attempted rather than now |
| R4 | `helm uninstall` leaves roughly 1.7 GiB occupied | Open | On a host with about 23 GB free, and where teardown was measured not to return disk space, this accumulates. The reclamation path must be documented before anyone runs a second workload |
| R5 | No collector exists for the metrics these components will expose | Open, and deliberately unowned | Telemetry is emitted into nothing. Any claim that the platform is observable is unsupported until an owner is chosen |
| R6 | Every service is ClusterIP, because the accepted cluster ships no ingress or load balancer | Open | External access is a port-forward. The contracts InferOps most needs to exercise remain unexercised |
| R7 | The network policy planned for the release may not be enforced by the local cluster's network plugin | Open | A policy that is not enforced is a comment. It must be tested before it is described as a control |
| R8 | No public maintainer roster exists | Open | This record has no named decision owner and cannot be formally approved by one |
| R9 | The trust boundary map names five boundaries and three of them have no control at all | Open, and stated | The map could be read as coverage. It is labelled as a map in the record, the diagram, and the table |

Open questions carried forward: whether a GitOps controller should replace the
Terraform layer once the environment is less memory-constrained; what the lifecycle
label must be named so that it does not collide with the existing project label
selector; whether the acquisition job belongs in the release at all, or whether
model acquisition is a prerequisite operation with the claim it fills; and who owns
a telemetry collector, which D7 leaves open on purpose.
