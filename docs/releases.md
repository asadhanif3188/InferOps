# Release process

Status: accepted high-level process; executed for the first time for `v1.0.0`,
prepared in `V1-S5-008-PR1` and tagged and published on 2026-09-27.

InferOps uses Semantic Versioning for public releases. A release number is
evidence of packaged repository state, not by itself proof of runtime, performance,
security, or production fitness.

## Version policy

- `v1.0.0` is the first versioned release. Under Semantic Versioning, `1.0.0` fixes
  the public interfaces a later breaking change is measured against; it says nothing
  about maturity, which the package's `3 - Alpha` classifier states.
- Pre-release identifiers such as `-alpha.1` or `-rc.1` may identify review builds.
- Breaking changes after `1.0.0` increment the major version.
- Compatible features increment the minor version; compatible fixes increment the
  patch version.
- The version is declared once, in `pyproject.toml`
  ([ADR 0009](architecture/decisions/ADR-0009-python-toolchain.md) D1). `uv.lock`
  records it, and the local composition repeats it as `service.version` under a check
  that refuses a mismatch. The workload contract and the Helm chart keep versions of
  their own.

## Releases

| Version | Notes | Checklist | Data | State |
|---|---|---|---|---|
| `v1.0.0` | [Release notes](releases/v1.0.0.md) | [Checklist](releases/v1.0.0-checklist.md) | [`v1.0.0.v1alpha1.json`](releases/v1.0.0.v1alpha1.json) | Released on 2026-09-27: an annotated tag on `718ad2e`, prepared from `742355b` over the evidence pack frozen by `V1-S5-013-PR2`. [What was read after the release](proof/releases/v1-s5-009-pr1-v1.0.0-publication.md) |

A release is cut over a frozen evidence pack and changes nothing inside it. The claim
and evidence register is part of that pack, so it describes the repository as it was
frozen, before the release; [the `v1.0.0` notes](releases/v1.0.0.md#where-the-frozen-evidence-still-describes-the-repository-before-this-release)
list every surface inside the pack, or bound to it, that still does. A decision record's
accepted text is history too, and carries a dated note where the release changed what it
describes.

A change after the release may move the register, as `V1-S5-009-PR1` did through
[a post-release ledger](proof/testing/v1-s5-009-pr1-post-release.v1alpha1.json) to
record the release itself. That moves the digests of the pack `main` holds, which no
release quotes; the pack a release quotes stays the one it was cut over, and the
evidence index recomputes it from `main` by undoing the ledgers after it.

## High-level release checklist

1. Define the release scope and freeze the candidate commit.
2. Confirm all required changes are merged and the changelog and limitations match
   the implemented state.
3. Run the repository-approved test, contract, documentation, security, and
   capable-runner checks required by the release's actual claims.
4. Record immutable source, dependency, image, contract, runtime, model, and tool
   versions where applicable. Remove secrets and sensitive data from evidence.
5. Verify a clean-clone workflow on every host/runtime configuration claimed as
   supported. Mock or synthetic runs remain separately labelled.
6. Review licenses, compatibility, upgrade/rollback notes, known limitations, and
   security findings.
7. Obtain approval for the exact candidate commit from the `repository-maintainer`
   role, which holds `v1-release-approval` under
   [ADR 0015](architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md).
   That approval is internal and covers architecture and governance only; it is not
   an assessment by an outside party and does not make the release number mean more
   than the first paragraph of this document says it means.
8. Create an annotated `v1.0.0` tag only after all required gates pass, then publish
   release notes and immutable artifacts/checksums that actually exist.
9. Verify published artifacts and links; document any release failure or rollback.

Each release's checklist carries the exact commands for its post-merge checks, its tag,
and its release entry, and records which gates passed before merge. This document
performs none of them. Artifact signing and rollback automation do not exist: a tag is
annotated rather than signed, and a pushed tag is never moved, so a defect found after a
release is fixed forward in a later version.
