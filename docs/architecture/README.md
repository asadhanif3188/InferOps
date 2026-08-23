# Architecture and decision records

Status: entry point established; one decision proposed, none accepted.

Accepted architecture decisions are indexed here with their status, date, decision
owner, alternatives, consequences, compatibility impact, and supporting evidence.
Superseded decisions remain available and link to their replacement.

No runtime, model, Kubernetes environment, infrastructure ownership boundary, or
application architecture is selected yet. A proposed decision record is a subject
for review, not a supported capability, and must not be implemented against as
though it were settled.

## Decision records

| ID | Decision | Status | Date | Evidence |
|---|---|---|---|---|
| [0001](decisions/0001-local-development-environment.md) | Local development and Kubernetes environment | Proposed | 2026-08-23 | [Host inventory](../proof/environment/v1-s0-002-pr1-host-inventory.md) |

## Conventions

Records live in [decisions/](decisions/) as `NNNN-short-slug.md`, numbered in the
order they are proposed. A number is never reused, and a withdrawn record is kept
and marked rather than deleted.

Each record states its status, the date it was proposed, the date it was accepted if
it was, its decision owner, the alternatives that were compared, the consequences of
the choice, its compatibility impact, its security considerations, and the evidence
supporting it.

A record is `Proposed` until reproducible evidence exists for the claims it makes.
A record whose selection depends on runtime behaviour cannot be marked `Accepted`
from documentation alone; it must link to executed proof. Estimated and measured
values must be labelled as such within the record.
