# Repository governance

Status: accepted for the public repository skeleton on 2026-08-23.

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
| Runtime host | No OS, Kubernetes distribution, runtime, or hardware support selected | Pending a tested public ADR |
| V1 release | Semantic versioning and the high-level gated process in `docs/releases.md` | Accepted process; unexecuted |

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
