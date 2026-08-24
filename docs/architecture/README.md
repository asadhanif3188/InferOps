# Architecture and decision records

Status: entry point established; one decision accepted in part, one accepted with a
recorded exception, one accepted.

Accepted architecture decisions are indexed here with their status, date, decision
owner, alternatives, consequences, compatibility impact, and supporting evidence.
Superseded decisions remain available and link to their replacement.

The local development and Kubernetes environment is partly settled, a model and
serving runtime are now selected on executed proof, and the schema language and
validation approach behind the first public contract are settled. No infrastructure
ownership boundary or application architecture is selected yet. A proposed decision
record is a subject for review, not a supported capability, and must not be
implemented against as though it were settled.

## Decision records

| ID | Decision | Status | Date | Evidence |
|---|---|---|---|---|
| [0001](decisions/ADR-0001-local-development-environment.md) | Local development and Kubernetes environment | Accepted in part | 2026-08-23 | [Host inventory](../proof/environment/v1-s0-002-pr1-host-inventory.md), [cluster smoke proof](../proof/environment/v1-s0-002-pr2-cluster-smoke.md) |
| [0002](decisions/ADR-0002-model-and-serving-runtime.md) | Model and serving runtime | Accepted, with one recorded exception | 2026-08-24 | [Runtime feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) |
| [0003](decisions/ADR-0003-workload-contract-schema-tooling.md) | Workload contract schema tooling | Accepted | 2026-08-24 | Schema and fixture validation output recorded in the record itself |

Read a partial status from the record's own per-decision table, never from this
row. In 0001, the container runtime, Kubernetes distribution, isolation, cleanup,
and minimum host tier are accepted; the task runner, dependency installation
approach, and recommended host tier are not.

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

## Conventions

Records live in [decisions/](decisions/) as `ADR-NNNN-short-slug.md`, where `NNNN`
is a zero-padded four-digit sequence number, numbered in the order they are
proposed. A number is never reused, and a withdrawn record is kept
and marked rather than deleted.

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
