# Release process

Status: accepted high-level process; not yet executed.

InferOps intends to use Semantic Versioning for public releases. A release number is
evidence of packaged repository state, not by itself proof of runtime, performance,
security, or production fitness.

## Version policy

- `v1.0.0` is the first planned stable project release.
- Pre-release identifiers such as `-alpha.1` or `-rc.1` may identify review builds.
- Breaking changes after a stable release increment the major version.
- Compatible features increment the minor version; compatible fixes increment the
  patch version.

No versioned release currently exists.

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
7. Obtain maintainer approval for the exact candidate commit.
8. Create an annotated `v1.0.0` tag only after all required gates pass, then publish
   release notes and immutable artifacts/checksums that actually exist.
9. Verify published artifacts and links; document any release failure or rollback.

Tag creation, remote publication, artifact signing, and rollback automation are not
performed or proven by this document. Their exact commands belong to later release
implementation after the build and CI toolchains exist.
