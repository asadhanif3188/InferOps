# Repository governance

Status: accepted for the public repository skeleton on 2026-08-23; each decision
below takes effect when the change that records it is merged.

This document governs contributions to this repository. Technical contracts and
architecture decisions become authoritative only when their public, accepted
artifacts are added to the corresponding indexes.

## Decision status

| Area | Decision | Status |
|---|---|---|
| License | MIT License | Accepted |
| Default branch | `main`; changes arrive through short-lived branches and pull requests | Accepted |
| Review | One approving maintainer review, passing applicable checks, resolved feedback | Accepted |
| Commits | Conventional Commit-style subjects; focused history | Accepted |
| Merge | Squash preferred; merge commit allowed for a meaningful maintained series | Accepted |
| Conduct | Interim expectations; formal framework waits for a private reporting path | Accepted deferral |
| Development environment | Container runtime, local Kubernetes distribution, isolation, cleanup, and minimum host tier | [ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md) accepted in part on executed proof from one Windows host |
| Task runner and dependency installation | Not selected | [ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md) D3 and D4 remain proposed; neither has been run |
| Component and resource-ownership boundaries | Component decomposition, dependency direction, and the Terraform/Helm/controller ownership split | [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md) accepted in part; the ownership inventory is machine-checked and no component it describes is built |
| Telemetry collection and ingress ownership | Not selected | [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md) D7 records both as unowned and defers them out of V1 |
| Runtime host for serving | No model runtime, accelerator, or recommended hardware tier selected | Pending; nothing has served a model |
| V1 release | Semantic versioning and the high-level gated process in [docs/releases.md](../releases.md) | Accepted process; unexecuted |
| Security reporting | Public reports prohibited; private intake channel not yet published | Accepted prohibition; channel blocked |
| Maintainers | Review required, but no public roster or `CODEOWNERS` file exists | Accepted requirement; roster pending |

Accepted repository governance does not accept a technical design or prove a
runtime. A proposal must remain labelled `Proposed` until its owner, alternatives,
compatibility impact, security implications, and evidence have been reviewed.

## Public-information boundary

Public changes include only implementation-relevant information that is safe for
users and contributors. Do not publish:

- credentials, secret values, private data, or sensitive prompts/responses;
- unpublished plans, prompt collections, strategy, or internal work queues;
- personal filesystem paths, host identifiers, or generated local state;
- model artifacts or outputs whose source, license, classification, or publication
  permission is unclear;
- capability, reliability, security, performance, or production claims without the
  required public evidence.

Repository content must stand on its own. Public decisions link to public artifacts,
not inaccessible sources.

## Ownership and changes

Maintainers own repository policy and release approval. Contract owners and
architecture decision owners will be named in their public artifacts when those
areas are established. Consequential contract or architecture changes require an
accepted decision record, compatibility analysis, appropriate fixtures/tests, and a
changelog entry.

Issue labels and branch protection are not claimed as configured until their remote
state is verified. This PR documents conventions only and performs no remote
repository mutation.

## Validation evidence

The initial governance validation is recorded in
[docs/proof/governance/v1-s0-001-pr1.md](../proof/governance/v1-s0-001-pr1.md).
It is local static evidence, not runtime or production proof.

The development host measured for ADR 0001 is recorded, redacted, in
[docs/proof/environment/v1-s0-002-pr1-host-inventory.md](../proof/environment/v1-s0-002-pr1-host-inventory.md).
It is a hardware and software inventory of one host. It proves nothing about
whether a cluster, container, or workload runs. The document checks run when that
record and ADR 0001 were added are in
[docs/proof/environment/v1-s0-002-pr1-validation.md](../proof/environment/v1-s0-002-pr1-validation.md).

The first real-runtime evidence this repository holds is
[docs/proof/environment/v1-s0-002-pr2-cluster-smoke.md](../proof/environment/v1-s0-002-pr2-cluster-smoke.md):
a local Kubernetes cluster created, a workload deployed and answering a request,
and both removed with residue verified absent, on one Windows host. It is local
real-runtime proof of the development environment. It is not proof of inference,
serving, capacity, or production behaviour, and it covers no other operating
system. The checks run alongside it are in
[docs/proof/environment/v1-s0-002-pr2-validation.md](../proof/environment/v1-s0-002-pr2-validation.md).
