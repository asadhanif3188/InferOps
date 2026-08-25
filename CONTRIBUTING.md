# Contributing to InferOps

Status: accepted repository convention; effective for changes merged after this
guide is merged.

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

Opening a pull request populates the checklist in
[.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md). Fill in every
section rather than deleting it.

At least one approving maintainer review is required before merge. The author must
resolve requested changes and rerun affected checks. A reviewer verifies scope,
public-information safety, test evidence, security implications, and compatibility.
Exceptions for urgent security fixes must be documented in the pull request and
reviewed after the fact.

No public maintainer roster or `CODEOWNERS` file is published yet, so a review is
requested by opening the pull request itself rather than by addressing a named
reviewer. Publishing that roster is a known governance gap and must be resolved
before external maintainers are added.

Squash merge is preferred for a single cohesive change. A maintained commit series
may use a merge commit when preserving independently meaningful commits helps review.
The pull-request title becomes part of the public history and must describe the
implemented outcome without overstating it.

## Validation

Run the smallest complete check set available for the changed files. No repository
task runner, linter, or continuous-integration lane is selected yet, so the checks
below are run manually until those tooling decisions are accepted and published.

Documentation changes require, at minimum, a clean whitespace check:

```text
git diff --check main...HEAD
```

Trailing whitespace and hard tabs in Markdown should also return no matches:

```sh
git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
```

Every relative Markdown link must resolve from the directory of the file that
contains it. Both checks below skip fenced code blocks so that command samples are
not mistaken for links. On a POSIX shell:

```sh
git ls-files -z '*.md' | while IFS= read -r -d '' f; do
  d=$(dirname "$f")
  awk '/^[ \t]*```/ { fence = !fence; next } !fence' "$f" |
    grep -oE '\]\([^)]+\)' | sed 's/^](//; s/)$//' |
    while read -r t; do
      case "$t" in http*|mailto:*|\#*) continue ;; esac
      p="${t%%#*}"
      [ -n "$p" ] && [ ! -e "$d/$p" ] && echo "BROKEN: $f -> $t"
    done
done
```

On Windows PowerShell:

```powershell
foreach ($f in (git ls-files '*.md')) {
  $dir = Split-Path -Parent $f
  if (-not $dir) { $dir = '.' }
  $fence = $false
  $body = (Get-Content -LiteralPath $f | Where-Object {
    if ($_ -match '^\s*```') { $fence = -not $fence; $false } else { -not $fence }
  }) -join "`n"
  foreach ($m in [regex]::Matches($body, '\]\(([^)]+)\)')) {
    $t = $m.Groups[1].Value
    if ($t -match '^(https?:|mailto:|#)') { continue }
    $p = ($t -split '#')[0]
    if ($p -and -not (Test-Path -LiteralPath (Join-Path $dir $p))) {
      "BROKEN: $f -> $t"
    }
  }
}
```

Both variants share one known limitation: a link target is read up to its first
closing parenthesis, so a relative path that itself contains a parenthesis is
truncated and may be reported incorrectly. Keep repository paths free of
parentheses rather than working around the check.

Check any changed external link separately and record the date it was checked.

### Shell scripts

Changes under `scripts/` must parse and must pass a static analyser at style level:

```sh
bash -n scripts/environment/*.sh
shellcheck -x -S style scripts/environment/*.sh
```

`shellcheck` is not vendored. Install it however your platform prefers; a Python
distribution of it exists if no system package is convenient.

### Contract schemas and fixtures

Changes under `contracts/`, `tools/contract_validation/`, or `tests/contracts/`
must pass the contract suite:

```sh
python -m pytest tests/contracts -q
```

Run it from the repository root, which is where the root `conftest.py` makes
`tools.contract_validation` importable. To validate a document that is not a
committed fixture:

```sh
python -m tools.contract_validation path/to/workload.yaml
```

The suite reads only files in this repository — no network, no cluster, no model,
no clock, no randomness — so a run that passes on one machine passes on every
machine with the same files. It checks that each schema is a valid draft 2020-12
schema, that every object in it declares an additional-property policy, that each
valid fixture validates, that repository-relative references in a fixture resolve,
that a fixture pinned to an accepted decision still matches it, that every invalid
fixture is refused with exactly the canonical error code, rule identifier, and
field location committed beside it, that neither a refusal's message nor its
field location repeats a value read out of the document, and that repeated
validation of the same document produces identical output.

It requires `jsonschema`, `pytest`, and `PyYAML`. Like `shellcheck` and
`kubeconform`, they are not vendored; install them however your platform prefers.
The schema language, authoring form, and validator are settled in
[ADR 0003](docs/architecture/decisions/ADR-0003-workload-contract-schema-tooling.md).
The repository-wide Python and packaging toolchain is not, and this suite does not
settle it.

A change that adds a field to a published schema also updates
[the contract package changelog](contracts/CHANGELOG.md) and the contract's own
document, and states its compatibility classification in the pull request. The
three classes — compatible, conditionally compatible, and breaking — are defined in
[the WorkloadContract document](docs/contracts/workload-contract.md); a change that
alters a canonical error code, a rule identifier, or a field location is at least
conditionally compatible even though the accept-or-refuse verdict is unchanged.

A change that adds a validation rule adds an invalid fixture demonstrating it,
with its expected refusal recorded in
[`contracts/workload/examples/invalid/expected-rejections.json`](contracts/workload/examples/invalid/expected-rejections.json).
For a **semantic** rule the suite enforces this: an unexercised one fails the
build. Two structural rules deliberately have no fixture, and
[the contract document](docs/contracts/workload-contract.md) names both and says
why. A valid fixture is never edited to make a change pass: a change that would
invalidate one is breaking by definition.

### Architecture ownership inventory

Changes under `docs/architecture/` or `tests/architecture/` must pass the
architecture suite:

```sh
python -m pytest tests/architecture -q
```

It reads only files in this repository and needs `pytest` alone. It checks the
committed ownership inventory
[`docs/architecture/resource-ownership.v1alpha1.json`](docs/architecture/resource-ownership.v1alpha1.json):
that every resource has exactly one owner, that the Terraform and Helm sets do not
intersect, that each resource's lifecycle is one its owner actually has, that no
resource claims to survive the operation that destroys it, that prerequisites
outlive releases and release resources do not outlive prerequisites, that a derived
resource has no tool owner, that a resource with no owner is deferred out of V1,
that evidence is cited only by rows marked implemented, and that
[the ownership document](docs/architecture/resource-ownership.md) publishes every
row in the data.

It checks a design commitment, not an implementation. No Terraform configuration
and no Helm chart exists, so nothing here can establish that the inventory
describes them. A change that adds a resource adds a row; a change that moves one
between owners is an architecture change and needs
[ADR 0004](docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
updated with it.

A change touching components, ownership, deployment, telemetry, trust boundaries,
or scope also works through
[the boundary review checklist](docs/architecture/boundary-review-checklist.md).

### Kubernetes manifests

Changes under `deploy/` must parse and must validate against the Kubernetes version
this project pins:

```sh
kubeconform -strict -summary -kubernetes-version 1.34.0 deploy/smoke/*.yaml
```

The kind cluster definition is excluded from that command because its schema is
kind's rather than Kubernetes'. Validate it by using it.

Container images in manifests must be pinned by digest, not by tag alone. A tag is
a label that can be moved; a digest is what the engine actually resolves.

Then inspect the full diff and search it for credentials, private planning content,
personal paths, generated files, and unsupported capability claims. Report the exact
commands you ran, their results, and any check you skipped.

## Evidence and claims

Record the environment, immutable tool/component versions, commands, results,
limitations, and failure diagnostics for executed proof. Label evidence accurately:
documented/unexecuted, mock, synthetic, estimated, local real runtime, cloud real
runtime, or production experience. A mock or document review cannot certify real
runtime behavior.

## Conduct and security

Follow the [interim conduct expectations](CODE_OF_CONDUCT.md). Do not open a public
issue containing a vulnerability, credential, private data, or sensitive prompt or
response. The [security policy](SECURITY.md) records why a dedicated private
reporting channel is not yet published and treats that gap as a known governance
limitation that must be resolved before accepting sensitive reports.
