# Contributing to InferOps

Thank you for helping build InferOps. The repository is currently in its governance
and decision phase; a merged document is not evidence that a runtime capability
exists.

## Before opening a change

1. Read the [repository governance](docs/governance/repository.md).
2. Confirm the relevant public contract or architecture decision exists. If it does
   not, label the change as proposed and do not implement against an assumed design.
3. Keep the change within one stated issue, story, or pull-request boundary.
4. Remove credentials, prompts/responses, model files, local paths, generated host
   state, and unpublished planning material from the diff.

## Branches

Create a short-lived branch from `main` using `<type>/<work-item>-<slug>`, where
`type` is one of `docs`, `feat`, `fix`, `test`, `ci`, `build`, `refactor`, or `chore`.
For example: `docs/v1-s0-001-repository-governance`.

Do not commit directly to `main`. Keep branches focused and rebase or merge `main`
before final review when needed to resolve conflicts.

## Commits

Use Conventional Commit-style subjects:

```text
<type>(optional-scope): concise imperative summary
```

Examples include `docs(governance): clarify release review` and
`fix(parser): reject unsupported contract versions`. Keep commits reviewable; do
not mix formatting or unrelated cleanup with the requested change. Commit signing
is encouraged but is not currently required.

## Pull requests and review

A pull request must:

- explain its scope, exclusions, dependencies, and compatibility impact;
- distinguish accepted decisions from proposals and executed proof from documented
  expectations;
- list exact validation commands and results, including skipped checks and blockers;
- update documentation and the changelog when public behavior or governance changes;
- contain no secret, sensitive data, large model artifact, or unsupported claim;
- leave the branch usable for the capability it owns.

At least one approving maintainer review is required before merge. The author must
resolve requested changes and rerun affected checks. A reviewer verifies scope,
public-information safety, test evidence, security implications, and compatibility.
Exceptions for urgent security fixes must be documented in the pull request and
reviewed after the fact.

Squash merge is preferred for a single cohesive change. A maintained commit series
may use a merge commit when preserving independently meaningful commits helps review.
The pull-request title becomes part of the public history and must describe the
implemented outcome without overstating it.

## Validation

Run the smallest complete check set available for the changed files. Documentation
changes require, at minimum:

```text
git diff --check
```

Also verify every changed relative link, inspect the full diff, and search it for
credentials, private planning content, personal paths, generated files, and
unsupported capability claims. Tool-specific checks will be added only after their
tooling decisions are accepted.

## Evidence and claims

Record the environment, immutable tool/component versions, commands, results,
limitations, and failure diagnostics for executed proof. Label evidence accurately:
documented/unexecuted, mock, synthetic, estimated, local real runtime, cloud real
runtime, or production experience. A mock or document review cannot certify real
runtime behavior.

## Conduct and security

Follow the [interim conduct expectations](CODE_OF_CONDUCT.md). Do not open a public
issue containing a vulnerability, credential, private data, or sensitive prompt or
response. A dedicated private reporting channel is not yet published; this is a
known governance limitation that must be resolved before accepting sensitive reports.
