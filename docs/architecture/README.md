# Architecture and decision records

Status: entry point established; seven decisions accepted in part, one accepted with a
recorded exception, two accepted, and one accepted and later amended.

Accepted architecture decisions are indexed here with their status, date, decision
owner, alternatives, consequences, compatibility impact, and supporting evidence.
Superseded decisions remain available and link to their replacement.

The local development and Kubernetes environment is partly settled, a model and
serving runtime are now selected on executed proof, the schema language and
validation approach behind the first public contract are settled, and the component
and resource-ownership boundaries, decided before the components existed, have since
been executed against a real cluster for every row the inventory marks implemented.
A proposed decision record is a subject for review, not a supported capability,
and must not be implemented against as though it were settled.

## Architecture documents

These describe the V1 design. The platform domain — with typed workload objects in
[the workload domain model](../domain/workload-domain-model.md) — both serving
adapters, the InferOps API, the Helm chart and the Terraform prerequisite layer are
now built, and the chart and the prerequisite layer have been installed and applied
on the `docker-desktop` reference provider. Deployment rendering is the component
still unbuilt: nothing turns a validated document into release values.

| Document | What it covers |
|---|---|
| [System architecture](system-architecture.md) | Context, components, inference request flow, deployment flow, telemetry and evidence flow, trust boundaries |
| [Resource ownership](resource-ownership.md) | Which tool owns which resource, with lifecycle and handoff rules |
| [`resource-ownership.v1alpha1.json`](resource-ownership.v1alpha1.json) | The authoritative form of that inventory, validated by `tests/architecture/` |
| [Project boundaries](project-boundaries.md) | Where this project stops, and what belongs to gateway or deeper serving work instead |
| [Boundary review checklist](boundary-review-checklist.md) | The questions a reviewer applies to all of the above |
| [Workload domain model](../domain/workload-domain-model.md) | The first component built under these boundaries, and the dependency rule it is held to |
| [Security baseline](../security/README.md) | The threats these boundaries face, the controls that exist, and the risks V1 carries |

## Decision records

| ID | Decision | Status | Date | Evidence |
|---|---|---|---|---|
| [0001](decisions/ADR-0001-local-development-environment.md) | Local development and Kubernetes environment | Accepted in part; D2, D5, and D6 superseded in part by 0011 | 2026-08-23 | [Host inventory](../proof/environment/v1-s0-002-pr1-host-inventory.md), [cluster smoke proof](../proof/environment/v1-s0-002-pr2-cluster-smoke.md) |
| [0002](decisions/ADR-0002-model-and-serving-runtime.md) | Model and serving runtime | Accepted, with one recorded exception | 2026-08-24 | [Runtime feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) |
| [0003](decisions/ADR-0003-workload-contract-schema-tooling.md) | Workload contract schema tooling | Accepted | 2026-08-24 | Schema and fixture validation output recorded in the record itself |
| [0004](decisions/ADR-0004-component-and-ownership-boundaries.md) | Component architecture and resource ownership boundaries | Accepted in part | 2026-08-25 | [Change validation](../proof/architecture/v1-s0-005-pr1-validation.md); the ownership inventory is checked, the component design is not |
| [0005](decisions/ADR-0005-test-ci-and-certification-strategy.md) | Test, CI, and certification strategy | Accepted in part | 2026-08-25 | [Change validation](../proof/testing/v1-s0-006-pr1-validation.md); the strategy is machine-checked, eight of its eleven test layers exist, and three do not — failure-and-resilience and security-scan are planned, capacity-and-load is deferred |
| [0006](decisions/ADR-0006-telemetry-and-evidence-catalog.md) | Telemetry and evidence catalog | Accepted in part | 2026-08-25 | [Original change validation](../proof/telemetry/v1-s0-007-pr1-validation.md) plus [API instrumentation validation](../proof/telemetry/v1-s1-008-pr1-validation.md); the catalog and API emission declarations are machine-checked; a release-scoped collector now exists and has scraped both InferOps jobs, while spans and any durable store remain absent |
| [0007](decisions/ADR-0007-inference-cost-method.md) | Inference cost-calculation method | Accepted in part | 2026-08-26 | [Change validation](../proof/cost/v1-s0-008-pr1-validation.md); the method and its worked example are machine-checked, and nothing in this repository computes a cost record |
| [0008](decisions/ADR-0008-v1-security-baseline.md) | V1 threat model and security baseline | Accepted in part | 2026-08-26 | [Change validation](../proof/security/v1-s0-009-pr1-validation.md); the baseline is machine-checked, and nothing in this repository defends a running system |
| [0009](decisions/ADR-0009-python-toolchain.md) | InferOps Python toolchain | Accepted | 2026-08-27 | [Change validation](../proof/toolchain/v1-s0-011-pr1-validation.md); every tool named was run on this repository, and it supersedes ADR 0001 D3 and D4 |
| [0010](decisions/ADR-0010-inference-api-compatibility-surface.md) | V1 inference API compatibility surface | Accepted; amended 2026-09-01 | 2026-08-27; amended 2026-09-01 | [Change validation](../proof/serving/v1-s0-012-pr1-validation.md); the surface is machine-checked against both the record that measured the runtime and the implemented ASGI application, which has served a real completion through an installed release's Service; no OpenAPI document or JSON Schema is published and `contracts/` is untouched |
| [0011](decisions/ADR-0011-external-local-cluster-provider-contract.md) | Local Kubernetes clusters are external, explicitly selected provider targets | Accepted in part | 2026-09-11 | [Change validation](../proof/architecture/v1-s3-010-pr1-validation.md); the contract is machine-checked and both providers have an identity guard — `kind`'s by container label for any explicitly selected cluster name, Docker Desktop's by node shape plus the API server port the verified kubeconfig dials — and neither can refuse a cluster deliberately named to impersonate the other |

Read a partial status from the record's own per-decision table, never from this
row. In 0001, the container runtime, Kubernetes distribution, isolation, cleanup,
and minimum host tier are accepted; the task runner, dependency installation
approach, and recommended host tier are not; since 0011, the distribution,
isolation, and cleanup decisions are superseded in part, because the cluster is no
longer InferOps's to create or delete. In 0011, eleven decisions are accepted, and
positive identity now covers both providers: a Docker Desktop cluster is bound to the
local engine through its node container and the API server port the verified
kubeconfig dials, with the two residual impersonation gaps recorded as `EX-06`. In
0004, six decisions are accepted and the seventh is decided in part — the telemetry
collector is Helm-owned and release-scoped since the 2026-09-09 amendment, while an
ingress or load-balancer implementation, a durable store, dashboards and an alert
routing path are explicitly not assigned. In 0005, five decisions are accepted and
one — which continuous-integration service runs the lanes, and what labels a capable
runner — is explicitly not made. In 0006, six decisions are accepted, one — what would
allow prompt and response capture — is explicitly not made, and one — the telemetry
toolchain, exporter and store — is deliberately left to 0004 rather than answered in
passing; 0004 has since assigned the collector and left the store, dashboards and
alerting open. In 0007, eleven decisions are accepted and two —
which provider rate cards a comparison would use, and which component computes a cost
record — are not. In 0008, twelve decisions are accepted and two — who signs off a
control, and whether a renderer or an admission policy enforces a pod-security
property — are not. In 0010, all nine decisions are accepted: `D3` was narrowed and
`D9` accepted on 2026-09-01, designating `inference-api-surface.v1alpha1.json` as the
canonical tested snapshot — explicitly not OpenAPI, not JSON Schema, and not an
artifact in `contracts/`.

0002 selects one runtime image digest and one immutable model revision, on evidence
from a trial that was executed on 2026-08-24: a model was downloaded and
hash-verified, the runtime served real inference requests inside a Kubernetes
cluster, and the pod was torn down without residue. Eleven of its twelve
pre-registered thresholds are met. **One blocking threshold, `T7`, is not**, and the
record is accepted with that exception argued in the open rather than absorbed. Read
the exception before relying on the acceptance.

The procedure it followed is
[the runtime feasibility workflow](../serving/feasibility-workflow.md), which the
same trial amended in four places where running it showed the procedure was wrong.

0003 settles how contract schemas are written and validated: JSON Schema draft
2020-12, YAML authoring restricted to the JSON-representable subset, an
off-the-shelf conformant validator, and no code generation in V1. It deliberately
does **not** select the repository-wide Python, packaging, or continuous-integration
toolchain, which remain open.

0004 decided boundaries for components that did not exist when it was written; most
of them now do. It fixes the component
decomposition and which direction dependencies may point, puts the serving runtime
in its own deployment rather than a sidecar, splits resource ownership so that
Terraform owns what outlives a release and Helm owns the release, makes the model
cache a prerequisite, maps five trust boundaries without implementing a single
control, and states where this project stops. The ownership half is committed as
data and checked by a test; the decomposition it draws still has no check of its own.
**One decision inside it is deliberately not made**: nobody owns an ingress
implementation. The telemetry collector was the other half of that deferral, and
`D7` was amended on 2026-09-09 to make it Helm-owned and release-scoped; a durable
store, dashboards and alert routing stay deferred as `telemetry-backend`.

0006 decides what a running V1 would say about itself: correlation over W3C Trace
Context assigned at the edge, a field registry in which every attribute declares a
sensitivity class and a cardinality class, thirteen active metrics covering seven
required signal families plus an identity metric, a per-metric and total cardinality
budget the suite recomputes rather than trusts, structured logs with no free-form
message field, and four evidence templates with seven mandatory sections. Its central
mechanism is that **placement is derived rather than chosen**: a field's permitted
placements are the intersection of what its two classes allow, and the two content
classes have an empty list — which is what makes "no prompt in telemetry" arithmetic
instead of a convention somebody has to remember.

The InferOps API now emits eight catalog metrics and structured request records when
the ASGI application is exercised. No component emits a span. A release-scoped
Prometheus collector is now Helm-owned and has scraped both InferOps jobs on
`docker-desktop`; it writes to an `emptyDir` that goes with its pod, so no durable
store, dashboard, or alerting path exists. The selected serving runtime's own signals
were observed in one trial, on one host; the API's committed evidence is local and
mock-backed rather than evidence of a deployed network service. Two of ADR 0006's
eighteen rules remain marked as enforced by review alone rather than promoted to
tested.

0005 decides how V1 is tested and what a passing result may be used to claim: eleven
test layers, four lanes, a ceiling on each layer's evidence class, certification at
C0 to C2, and evidence retention that separates an expiring lane artifact from a
committed certifying record. Its central rule — a mock may never certify real runtime
behaviour — was already accepted in words; what this record adds is a mechanism, in
committed data and a marker expression that a test compares against it in both
directions. It configures **no** continuous integration: there is no workflow file in
this repository, and a lane may claim automation only by naming one that exists.

0008 decides what V1 protects and from whom: the architecture's five trust boundaries
adopted verbatim plus a sixth for publication, six pod-security properties and a
digest pin enforced over every manifest here, least exposure at the caller boundary,
secrets referenced rather than carried, content and secrets with no telemetry
placement, and a reserved vocabulary that may appear only inside a denial.

Its central mechanism is that **a control's status is derived rather than asserted**:
the enforcement kind and runtime scope a control declares determine its status through
a committed table, the test function or shell guard it names has to exist, and a
control claiming an implemented status has to name a committed evidence record. That
is the same shape as 0007's derived confidence, applied to the failure that a written
control is counted as an enforced one.

It establishes **nothing about whether anything running is defended**. Twenty-nine of
its thirty-eight controls are enforced by something and nine are not; twelve risks are
carried rather than reduced, ten of them blocking production use; six exceptions are
recorded with a compensating control each; and the pod-security properties hold over
five YAML files and two committed renders, read as files — a release has since been
installed from those renders and no check here reads a pod that resulted. No secret
scanner has been run and recorded. An image scanner and a dependency auditor have each
been run once by hand and neither runs continuously, because no continuous-integration
service is selected. No assessment by an outside party has ever been performed. Four
of its fifteen rules are enforced by review alone.

0007 decides how a V1 cost figure is produced and what it may be called: three bases
of which only an allocation is reachable, allocation by reserved capacity rather than
observed use, unreserved capacity reported as its own line so that the parts close
against the machine, half-open UTC windows split at a change of reservation, prices
committed rather than fetched, decimal money rounded once, a missing input recorded as
null with a reason instead of a zero, and confidence derived from a record's own
inputs rather than typed by its producer.

The consequence it refuses to soften: **every cost figure this project can produce
today has confidence `none`.** The only rate card committed here is synthetic, no
invoice has ever been read, and no component computes a cost record. It also records
one boundary consequence that is easy to miss — a cost per thousand requests is an
hourly reservation divided by an hour of traffic, so the rule against publishing a
throughput figure is also a rule against publishing a cost-per-request figure. Two of
its fourteen rules are enforced by review alone.

0010 decides what the platform's own inference API looks like from outside, one story
before the adapter interface is frozen and two before the API is written: a **frozen
subset** of the OpenAI HTTP API shape at the `/v1` prefix, five endpoints, the request
and response fields of each, an `x_inferops` extension member beside the
`X-InferOps-` header prefix, streaming declared `false` and token usage declared
`true`, and a mapping from runtime behaviour to canonical error codes in which six of
the thirteen codes are recorded as **never emitted in V1**, with a reason each.

Two properties of it are worth reading before relying on it. The compatibility is a
**shape read on a date** — 2026-08-24, from the response bodies in the feasibility
record, with no vendor documentation consulted for any of it — and not a commitment to
track what the upstream surface does next; that freeze is the answer to the strongest objection
against the choice, which is that the shape is not this project's to version. And
**one error row was observed and eight are specifications**, because the lane that
would provoke a real failure does not exist. The record marks every row either way, and
a test refuses a row claiming an observation the trial did not record.

It **publishes nothing as a contract**. No OpenAPI document or JSON Schema is
published and `contracts/` is untouched; the API is implemented, the distribution
carries no server dependency of its own, and one real completion has been served
through an installed release's Service. It also carries ADR 0002's `T7` exception
forward as a stated obligation rather than a discharged one: the runtime has no
cumulative request counter, so the API owes one, and the metric it owes exists in the
telemetry catalog and is now emitted by the API.

## Conventions

Records live in [decisions/](decisions/) as `ADR-NNNN-short-slug.md`, where `NNNN`
is a zero-padded four-digit sequence number, numbered in the order they are
proposed. A number is never reused, and a withdrawn record is kept and marked
rather than deleted.

Each record states its status, the date it was proposed, the date it was accepted if
it was, its decision owner, the alternatives that were compared, the consequences of
the choice, its compatibility impact, its security considerations, and the evidence
supporting it.

A record is `Proposed` until reproducible evidence exists for the claims it makes.
A record whose selection depends on runtime behaviour cannot be marked `Accepted`
from documentation alone; it must link to executed proof. Estimated and measured
values must be labelled as such within the record.

A record may also reach `Accepted, with one recorded exception`. That status means
the evidence supports the decision while a stated criterion the record itself set
was **not** met. It requires the exception to be named in the record's own status
banner, argued where a reader will find it, and listed among the consequences, so
that acceptance can never be read as though every criterion had passed. It exists
because the alternatives are both dishonest: marking such a record `Accepted`
hides a failure, and holding it at `Proposed` denies evidence that was produced.

A record that decides several things at once may reach `Accepted in part`. That
status requires a per-decision table naming which decisions the evidence covers and
which remain proposed, so that a reader cannot mistake one for the other. It exists
because the alternative is worse in both directions: marking the whole record
`Accepted` would overclaim, and holding it at `Proposed` would deny that evidence
was produced.
