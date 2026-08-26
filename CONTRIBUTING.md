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

Which check proves which public claim, where each one is allowed to run, and what a
passing result may be used to certify are settled in
[the test and CI strategy](docs/testing/test-strategy.md) and
[ADR 0005](docs/architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md).
Read them before adding a test, and read
[the certification levels](docs/testing/certification.md) before citing one as
evidence.

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
resource claims to survive the operation that destroys it, that a survival list is a
prefix of the teardown blast-radius ordering, that prerequisites outlive releases and
release resources do not outlive prerequisites, that a derived resource has no tool
owner, that a resource with no owner is deferred out of V1, that evidence is cited
only by rows marked implemented, and that
[the ownership document](docs/architecture/resource-ownership.md) and the data
publish the same identifiers in both directions.

It checks a design commitment, not an implementation. No Terraform configuration
and no Helm chart exists, so nothing here can establish that the inventory
describes them. A change that adds a resource adds a row; a change that moves one
between owners is an architecture change and needs
[ADR 0004](docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
updated with it.

A change touching components, ownership, deployment, telemetry, trust boundaries,
or scope also works through
[the boundary review checklist](docs/architecture/boundary-review-checklist.md).

### Test lanes and markers

[`pytest.ini`](pytest.ini) registers a marker for every test layer the strategy
defines, refuses an unregistered one, and deselects by default every marker belonging
to a layer that needs a cluster or a model. Running pytest with no marker expression
is therefore the default lane, and it downloads no model and touches no cluster:

```sh
python -m pytest -q
```

Selecting one layer, or opting into one that the default lane excludes, is a marker
expression:

```sh
python -m pytest -m contract -q
python -m pytest -m realruntime -q
```

`unit`, `adapter`, `mockintegration`, `cluster`, `realruntime`, `failure`, and `load`
currently select nothing, because the layers behind them have no code yet. That is
the intended state: the marker exists so that the first test of its kind is written
under it rather than into whichever suite was already open.

A new test module belongs to exactly one layer and declares that layer's marker at
module level:

```python
pytestmark = pytest.mark.contract
```

A module under a layer's declared paths that omits its marker fails the strategy
suite, because a marker nothing is marked with selects nothing, silently.

Adding a test that needs a cluster or a model means adding it to a layer outside the
default lane. Adding a public claim means adding a row to
[the claim and test matrix](docs/testing/claim-test-matrix.md) with a test layer, an
environment, a required certification level, and an evidence owner; a claim with none
of those fails the build.

### Test strategy and certification

Changes under `docs/testing/`, `tests/testing/`, or `pytest.ini` must pass the
strategy suite:

```sh
python -m pytest tests/testing -q
```

It reads only files in this repository and needs `pytest` alone. It checks the
committed strategy
[`docs/testing/test-strategy.v1alpha1.json`](docs/testing/test-strategy.v1alpha1.json):
that every claim names a test layer, an environment, and an evidence owner; that no
layer certifies above the ceiling its evidence class allows, so a mock cannot support
a C2 claim; that no C2-or-above claim is satisfied by a mock, a simulation, or an
estimate; that no layer needing a cluster or a model sits in the default lane; that
every marker belonging to such a layer is deselected by the committed default
expression and no default-lane marker is; that every module under a layer's paths
carries its marker; that a claim cites evidence only when it is certified and only
from layers that are implemented; that a lane claims automation only by naming a
workflow file that exists; and that the three published documents and the data agree
in both directions.

It checks a strategy, not a test suite. Six of the eleven layers it describes have
no code, and nothing here can distinguish a layer that is honestly planned from one
that will never be written.

### Telemetry catalog and evidence templates

Changes under `docs/telemetry/`, `docs/proof/templates/`, `docs/proof/README.md`, or
`tests/telemetry/` must pass the telemetry suite:

```sh
python -m pytest tests/telemetry -q
```

It reads only files in this repository and needs `pytest` alone. It checks the
committed catalog
[`docs/telemetry/telemetry-catalog.v1alpha1.json`](docs/telemetry/telemetry-catalog.v1alpha1.json):
that every attribute and metric states the operational or proof question it answers;
that every field's declared placements are a subset of what its sensitivity class and
its cardinality class both allow, so a prompt, a secret, a correlation identifier, a
tenant identifier, and a measured duration are each excluded from a metric label by
derivation rather than by review; that identity attributes reach metrics only through
the identity metric; that every metric's maximum series count recomputes from its
labels and bucket count and stays inside the per-metric and total budgets; that every
required signal family has an active metric behind it; that a deferred signal says
why and an active one does not; that every native runtime series the catalog names
appears in
[the record that measured it](docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md);
that every rule claiming a test names one that exists; that content capture is
disabled and has no policy that could enable it; that each evidence template carries
every required section exactly once; and that the two published documents and the
data agree in both directions.

It checks a catalog, not a running system. Nothing in this repository emits a metric,
a log record, or a span, and no log line has ever been inspected because none has
been written.

A change that adds a signal adds a row with a stated question, a sensitivity class,
and a cardinality class; a change that adds a metric label adds series to a budget
the suite counts. A change that would place a field somewhere neither of its classes
permits is a change that has to reclassify the field in public first. The decision
behind all of it is
[ADR 0006](docs/architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md).

### Cost method and worked example

Changes under `docs/cost/` or `tests/cost/` must pass the cost suite:

```sh
python -m pytest tests/cost -q
```

It reads only files in this repository and needs `pytest` alone. It checks the
committed method
[`docs/cost/cost-method.v1alpha1.json`](docs/cost/cost-method.v1alpha1.json): that
every amount declares a basis and that only an invoice-backed basis may carry the
vocabulary or the reference of an invoice; that exactly one allocation method and one
residual treatment are selected and the unselected ones say why; that every price
source is committed rather than fetched and the synthetic one says so in its own
contents; that each record's confidence is the lowest ceiling its own inputs allow,
recomputed rather than read; that an unavailable input is null with a declared reason
and never a zero; that every unit cost carries the count it was divided by and is null
below the declared minimum; that every input names a signal the telemetry catalog
declares or records that none exists; that whether a record field may be committed is
derived from the sensitivity class the telemetry catalog gave it, which is what keeps
a tenant identifier out of every record here; that no binary float appears anywhere in
the method; and that the worked example's amounts, shares, and unit costs recompute in
exact decimal and close against the capacity they allocate.

It checks a method, not a cost. Nothing in this repository computes, emits, or reads a
cost record, no invoice has ever been seen, and the only rate card committed here is
synthetic, so every amount the suite verifies is arithmetically correct and
economically meaningless.

A change that adds an input adds the signal it would come from or records that none
exists. A change that adds an amount to the worked example adds a number the suite
recomputes; a figure typed into a document that the arithmetic does not produce is a
failing test. The decision behind all of it is
[ADR 0007](docs/architecture/decisions/ADR-0007-inference-cost-method.md), and the
rule it cannot enforce is the one that matters most: V1 publishes this method and a
synthetic example, and no figure for what running an inference workload costs.

### Threat model and security baseline

Changes under `docs/security/`, `tests/security/`, or `deploy/` must pass the
security suite:

```sh
python -m pytest tests/security -q
```

It reads only files in this repository and needs `pytest` and `PyYAML`. It checks the
committed baseline
[`docs/security/security-baseline.v1alpha1.json`](docs/security/security-baseline.v1alpha1.json):
that every control's status is **derived** from the enforcement kind and runtime
scope it declares rather than asserted, through a table committed beside the
controls; that a control naming an automated test or a shell guard names one that is
actually defined, and one claiming an implemented status names an evidence record
that is actually committed; that no control claims to act inside a running system;
that every threat names a control or the deferred risk that carries it, and every
recorded exception names a compensating control that exists and states its residual
risk; that the five boundaries the architecture maps are reproduced here verbatim and
the sixth says why it extends them; that every YAML document under `deploy/` is
pinned by digest, carries eight pod-security assertions, and declares no Ingress,
NodePort, or LoadBalancer; that nothing generated, personal, or model-shaped is
committed; and that a reserved vocabulary of twelve terms appears in the security
documents only inside a sentence that denies it.

It checks a baseline, not a system. Nothing in this repository authenticates a
caller, authorises a request, enforces a network policy, or applies a security
context to a pod it deployed, because nothing here deploys a pod or serves a request.
No secret scanner, image scanner, or dependency auditor has been run and recorded,
and no assessment by an outside party has ever been performed.

A change that adds a control names the verification for it or declares that it has
none — there is no third option, and the derivation is what makes that true rather
than a convention. A change that adds a threat names a control or the register entry
that carries it. A change that removes a register entry adds the control that replaces
it; that last rule is enforced by review alone and is marked as such. The decision
behind all of it is
[ADR 0008](docs/architecture/decisions/ADR-0008-v1-security-baseline.md), and the
document it exists to protect is
[the deferred-risk register](docs/security/deferred-risks.md): a register that shrinks
because the project wants to look further along is the failure this suite cannot
catch.

### Kubernetes manifests

Changes under `deploy/` must parse and must validate against the Kubernetes version
this project pins:

```sh
kubeconform -strict -summary -kubernetes-version 1.34.0 deploy/smoke/*.yaml
```

The kind cluster definition is excluded from that command because its schema is
kind's rather than Kubernetes'. Validate it by using it.

Container images in manifests must be pinned by digest, not by tag alone. A tag is
a label that can be moved; a digest is what the engine actually resolves. The
security suite above checks this over every YAML document under `deploy/`, alongside
the eight pod-security assertions every manifest here carries.

Then inspect the full diff and search it for credentials, private planning content,
personal paths, generated files, and unsupported capability claims. Report the exact
commands you ran, their results, and any check you skipped.

## Evidence and claims

Record the environment, immutable tool/component versions, commands, results,
limitations, and failure diagnostics for executed proof. Label evidence accurately:
documented/unexecuted, mock, synthetic, estimated, local real runtime, cloud real
runtime, or production experience. A mock or document review cannot certify real
runtime behavior.

Records are written from the templates in
[`docs/proof/templates/`](docs/proof/templates/) — an experiment record, an
environment record, a raw-result record, and a claim-and-evidence record — each of
which carries classification, provenance, environment, method, results, limitations,
and authorisation. Copy a template; never edit one to hold a result. The experiment
template registers the method and the failure condition **before** the run, which is
the ordering that separates a measurement from a search for a supporting number.
What is excluded from a record, and why, is in
[the redaction rules](docs/telemetry/redaction.md): a tenant identifier is a log
field and does not belong in a committed record, and raw output is promoted into one
redacted rather than copied.

[The certification document](docs/testing/certification.md) states the ceiling each
label carries, the explicit CPU and GPU forms of the real-runtime labels, and what a
record certifying real behaviour has to contain. It adds one label to the list above,
`local-static`, for a deterministic check over files in this repository, and it
records that `production experience` is a label V1 cannot reach: there is no
organizational production to draw it from, and public-cloud execution is not
production operation. Where the two lists differ, the certification document is the
one a layer is assigned from. Evidence that certifies a published
claim is committed under `docs/proof/` and kept for as long as the claim stands; a
lane's raw output expires and may never be cited as the evidence for a published
claim.

## Conduct and security

Follow the [interim conduct expectations](CODE_OF_CONDUCT.md). Do not open a public
issue containing a vulnerability, credential, private data, or sensitive prompt or
response. The [security policy](SECURITY.md) records why a dedicated private
reporting channel is not yet published and treats that gap as a known governance
limitation that must be resolved before accepting sensitive reports.
