# Architecture and decision records

Status: entry point established; six decisions accepted in part, one accepted with a
recorded exception, two accepted.

Accepted architecture decisions are indexed here with their status, date, decision
owner, alternatives, consequences, compatibility impact, and supporting evidence.
Superseded decisions remain available and link to their replacement.

The local development and Kubernetes environment is partly settled, a model and
serving runtime are now selected on executed proof, the schema language and
validation approach behind the first public contract are settled, and the component
and resource-ownership boundaries are now decided for components that do not exist
yet. A proposed decision record is a subject for review, not a supported capability,
and must not be implemented against as though it were settled.

## Architecture documents

These describe the V1 design. Every component below the contract layer is unbuilt.

| Document | What it covers |
|---|---|
| [System architecture](system-architecture.md) | Context, components, inference request flow, deployment flow, telemetry and evidence flow, trust boundaries |
| [Resource ownership](resource-ownership.md) | Which tool owns which resource, with lifecycle and handoff rules |
| [`resource-ownership.v1alpha1.json`](resource-ownership.v1alpha1.json) | The authoritative form of that inventory, validated by `tests/architecture/` |
| [Project boundaries](project-boundaries.md) | Where this project stops, and what belongs to gateway or deeper serving work instead |
| [Boundary review checklist](boundary-review-checklist.md) | The questions a reviewer applies to all of the above |
| [Security baseline](../security/README.md) | The threats these boundaries face, the controls that exist, and the risks V1 carries |

## Decision records

| ID | Decision | Status | Date | Evidence |
|---|---|---|---|---|
| [0001](decisions/ADR-0001-local-development-environment.md) | Local development and Kubernetes environment | Accepted in part | 2026-08-23 | [Host inventory](../proof/environment/v1-s0-002-pr1-host-inventory.md), [cluster smoke proof](../proof/environment/v1-s0-002-pr2-cluster-smoke.md) |
| [0002](decisions/ADR-0002-model-and-serving-runtime.md) | Model and serving runtime | Accepted, with one recorded exception | 2026-08-24 | [Runtime feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) |
| [0003](decisions/ADR-0003-workload-contract-schema-tooling.md) | Workload contract schema tooling | Accepted | 2026-08-24 | Schema and fixture validation output recorded in the record itself |
| [0004](decisions/ADR-0004-component-and-ownership-boundaries.md) | Component architecture and resource ownership boundaries | Accepted in part | 2026-08-25 | [Change validation](../proof/architecture/v1-s0-005-pr1-validation.md); the ownership inventory is checked, the component design is not |
| [0005](decisions/ADR-0005-test-ci-and-certification-strategy.md) | Test, CI, and certification strategy | Accepted in part | 2026-08-25 | [Change validation](../proof/testing/v1-s0-006-pr1-validation.md); the strategy is machine-checked, and six of its eleven test layers have no code |
| [0006](decisions/ADR-0006-telemetry-and-evidence-catalog.md) | Telemetry and evidence catalog | Accepted in part | 2026-08-25 | [Change validation](../proof/telemetry/v1-s0-007-pr1-validation.md); the catalog is machine-checked, and nothing in this repository emits a single signal |
| [0007](decisions/ADR-0007-inference-cost-method.md) | Inference cost-calculation method | Accepted in part | 2026-08-26 | [Change validation](../proof/cost/v1-s0-008-pr1-validation.md); the method and its worked example are machine-checked, and nothing in this repository computes a cost record |
| [0008](decisions/ADR-0008-v1-security-baseline.md) | V1 threat model and security baseline | Accepted in part | 2026-08-26 | [Change validation](../proof/security/v1-s0-009-pr1-validation.md); the baseline is machine-checked, and nothing in this repository defends a running system |
| [0009](decisions/ADR-0009-python-toolchain.md) | InferOps Python toolchain | Accepted | 2026-08-27 | [Change validation](../proof/toolchain/v1-s0-011-pr1-validation.md); every tool named was run on this repository, and it supersedes ADR 0001 D3 and D4 |

Read a partial status from the record's own per-decision table, never from this
row. In 0001, the container runtime, Kubernetes distribution, isolation, cleanup,
and minimum host tier are accepted; the task runner, dependency installation
approach, and recommended host tier are not. In 0004, six decisions are accepted
and one — who owns telemetry collection and an ingress or load-balancer
implementation — is explicitly not made. In 0005, five decisions are accepted and
one — which continuous-integration service runs the lanes, and what labels a capable
runner — is explicitly not made. In 0006, six decisions are accepted, one — what would
allow prompt and response capture — is explicitly not made, and one — the telemetry
toolchain and who owns a collector — is deliberately left to 0004's open question
rather than answered in passing. In 0007, eleven decisions are accepted and two —
which provider rate cards a comparison would use, and which component computes a cost
record — are not. In 0008, twelve decisions are accepted and two — who signs off a
control, and whether a renderer or an admission policy enforces a pod-security
property — are not.

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

0004 decides boundaries for components that do not exist. It fixes the component
decomposition and which direction dependencies may point, puts the serving runtime
in its own deployment rather than a sidecar, splits resource ownership so that
Terraform owns what outlives a release and Helm owns the release, makes the model
cache a prerequisite, maps five trust boundaries without implementing a single
control, and states where this project stops. The ownership half is committed as
data and checked by a test; the component half has no code to check it against.
**One decision inside it is deliberately not made**: nobody owns a telemetry
collector or an ingress implementation, and both are deferred rather than assigned
for tidiness.

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

It emits **nothing**. No component here writes a metric, a log record, or a span, no
collector or store is selected, and the only signals ever observed are the serving
runtime's own, in one trial, on one host. Two of its fifteen rules are marked
enforced by review alone rather than promoted to tested.

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

It defends **nothing that is running**. Twenty-two of its thirty-two controls are
enforced by something and ten are not; twelve risks are carried rather than reduced,
ten of them blocking production use; four exceptions are recorded with a compensating
control each; and the pod-security properties hold over five YAML files that are
smoke and trial apparatus rather than over any pod this platform deployed. No
scanner has been run and recorded, and no assessment by an outside party has ever been
performed. Four of its fifteen rules are enforced by review alone.

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
