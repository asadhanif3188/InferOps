# Contributing to InferOps

Status: accepted repository convention; effective for changes merged after this
guide is merged.

Thank you for helping build InferOps. The repository has moved from its governance
and decision phase into implementing against those decisions, and the caution is
unchanged in both: a merged document is not evidence that a runtime capability
exists, and neither is a merged package.

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

Run the smallest complete check set available for the changed files. Every check
below is run **by hand**: no continuous-integration lane, workflow file, or capable
runner is selected, and
[ADR 0005](docs/architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
D6 leaves that open on purpose. No task runner is selected either, and that one is
settled rather than open —
[ADR 0009](docs/architecture/decisions/ADR-0009-python-toolchain.md) D7 rejects one,
so the list below is the list.

### The toolchain, and how to get it

[ADR 0009](docs/architecture/decisions/ADR-0009-python-toolchain.md) selects the
packaging layout, the dependency manager, the lockfile policy, the linter, the
formatter, and the type checker, and every one of them was run on this repository
before it was accepted. Install [uv](https://docs.astral.sh/uv/), then:

```sh
uv sync --locked
```

That creates `.venv/` from the committed [`uv.lock`](uv.lock) — the same versions
every recorded result was produced with — and fails rather than re-resolving if the
lockfile would have to change. Run the checks through it:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m mypy
uv run --locked python -m pytest -q
```

`--locked` is not decoration. Without it a run may quietly re-resolve, and a check
whose inputs were resolved fresh measures the package index as much as it measures
the repository.

Adding or changing a dependency is two steps, and the second cannot be skipped: edit
the relevant group in [`pyproject.toml`](pyproject.toml), then run `uv lock`. Review
the resulting `uv.lock` diff — it is the file that decides what every check ran
against.

`python -m pytest` without `uv` still works and is still accepted for a
documentation-only change. It runs against whatever versions are on your machine,
which is why a recorded result always names the command that produced it.

Two conventions the linter and the type checker carry, stated because they are
easier to keep than to restore. `E501` is switched off and the formatter owns line
length, so run `ruff format` rather than rewrapping by hand. The test composition
helpers contain narrowly coded `# type: ignore[...]` directives where tests
deliberately inject protocol-invalid doubles. Keep every directive scoped to an
error code and make the reason evident from the surrounding test or helper.

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
bash -n scripts/environment/*.sh scripts/security/*.sh
shellcheck -x -S style scripts/environment/*.sh scripts/security/*.sh
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

It requires `jsonschema`, `pytest`, and `PyYAML`. All three are in the `test`
dependency group and are installed by `uv sync --locked`; like `shellcheck` and
`kubeconform` they are not vendored, and installing them another way is fine. The
schema language, authoring form, and validator are settled in
[ADR 0003](docs/architecture/decisions/ADR-0003-workload-contract-schema-tooling.md),
and the repository-wide Python and packaging toolchain is settled separately in
[ADR 0009](docs/architecture/decisions/ADR-0009-python-toolchain.md); this suite
settles neither.

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

The same suite holds the platform domain to the dependency rule. It parses every
module under [`src/inferops/`](src/inferops/) and fails if one imports anything
outside the standard library and this distribution — which is checklist question
**B1**, answered from the source rather than at review time. Adding a runtime
dependency to the domain is an amendment to
[ADR 0004](docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
with an argument attached, not a new import.

A change touching components, ownership, deployment, telemetry, trust boundaries,
or scope also works through
[the boundary review checklist](docs/architecture/boundary-review-checklist.md).

### The platform domain

Changes under [`src/inferops/`](src/inferops/) or [`tests/domain/`](tests/domain/)
must pass the domain suite and the architecture suite:

```sh
uv run --locked python -m pytest tests/domain -q
uv run --locked python -m pytest tests/architecture -q
uv run --locked python -m mypy
```

The domain suite reads only files in this repository and needs `pytest` and
`PyYAML` — the latter to load the committed fixtures, which are authored in YAML.
It checks [the workload domain model](docs/domain/workload-domain-model.md): that
every committed valid fixture parses; that a parsed document rebuilds into exactly
the document it came from, so that a dropped field or an invented default fails
here rather than in whatever renders one later; that an unsupported contract version
is refused before any field below it is read; that every field the schema declares
*unconditionally* required is required by the parser, at that field's own address —
the conditionally required profile block is a cross-field rule and is not enforced
here; and that no refusal repeats a value read out of the document.

It also compares the domain's copy of the contract against the published schema —
every pattern, enumerated value, numeric bound, field list, and required field, in
both directions. That copy exists because the domain declares no runtime dependency
and so cannot import a JSON Schema validator; the comparison is what stops the two
drifting. **A change to
[the schema](contracts/workload/workload-contract.v1alpha1.schema.json) is therefore
a change to `src/inferops/domain/workload/values.py` as well** — and, when a field
is added or removed, to `parsing.py` and `contract.py` with it. The suite fails
until they are made.

Two things belong to the validation pipeline rather than to the domain, and a change
should not quietly move either: the semantic rules the schema cannot express, and
the canonical error codes and rule identifiers a refusal carries. The domain raises
typed exceptions with a field location and no canonical code, and
[the domain document](docs/domain/workload-domain-model.md) says where the line is.

### Serving adapters

Changes under [`src/inferops/adapters/`](src/inferops/adapters/) or
[`tests/adapters/`](tests/adapters/) must pass the adapter suite, the domain
suite, and the architecture suite:

```sh
uv run --locked python -m pytest tests/adapters -q
uv run --locked python -m pytest tests/domain -q
uv run --locked python -m pytest tests/architecture -q
uv run --locked python -m mypy
```

The adapter suite reads only files in this repository and needs `pytest` alone. The
conformance half lives in `tests/support/serving_conformance.py` and is **inherited,
not copied**: it asserts only what the `ServingAdapter` protocol publishes, so the
same assertions run against the in-memory double under `unit` and against the
deterministic mock under `adapter`. A new adapter subclasses it and supplies an
adapter and a configuration; a new obligation is added there once, and every adapter
is held to it immediately.

The rest of the suite is what an adapter owes beyond the protocol, and for
[the mock](docs/serving/mock-serving-adapter.md) that is mostly the mock and real
boundary made mechanical: the response is the committed fixture, the runtime identity
is the row the compatibility matrix publishes, the identity block carries the same
notice the fixture carries, a non-mock model identity is refused at configuration
time, token counting is declared unsupported rather than invented, and the declared
evidence class is checked against the ceiling the committed strategy gives it.

**An adapter suite proves the shape of the call, not the thing on the other end of
it.** Its ceiling is `C1` for the real adapter too. A change that would let a mock
result support a real-serving claim is a change to
[the mock and real boundary](docs/serving/mock-and-real-boundary.md), which is an
accepted rule, and not a change to a test.

### The selected runtime's adapter

[`src/inferops/adapters/llama_cpp/`](src/inferops/adapters/llama_cpp/) is where the
runtime ADR 0002 selected is configured, inspected, and called, and it runs under
the same commands as the rest of the adapter layer.
[The configuration half](docs/serving/real-runtime-configuration.md) holds the
pins, settings, translation, readiness mapping, metadata parsers, and capability
declaration; [the inference half](docs/serving/real-runtime-inference.md) holds the
transport seam, the inference client, the deadlines, the error mapping, and
`LlamaServerAdapter`. The versioned
[local runtime profile](docs/serving/local-runtime-profile.md) selects concrete
deployment values without adding defaults to that generic package; validate it
with `uv run --locked python -m tools.runtime_configuration check`.

The standalone [local runtime package](docs/serving/local-runtime-package.md)
translates that profile into a Docker command. Validate its descriptor and exact
command without Docker or model bytes with
`uv run --locked python -m tools.runtime_packaging check`. Commands that inspect
real model bytes or operate Docker require `--confirm-real-runtime`; they never
pull an image or download a model implicitly. Keep the model mount read-only, the
published port loopback-only, and cleanup restricted to the package's exact
ownership label.

The [local real composition](docs/serving/local-real-composition.md) is the guarded
host-local workflow above that package. Validate it without Docker or model access
with `uv run --locked python -m tools.local_composition check`. Its `start`,
`status`, and `cleanup` commands require `--confirm-real-runtime`; `start` remains
attached so Ctrl+C can drain the API before removing the owned runtime. Keep its
API loopback-only, preserve the runtime-before-API startup and API-before-runtime
shutdown order, and never add a mock fallback.

The [C2 real-runtime certification](docs/serving/real-runtime-certification.md)
is the repeatable smoke workflow above that composition. Validate its descriptor
without contacting anything with
`uv run --locked python -m tools.runtime_certification check`; `certify` requires
`--confirm-real-runtime` and refuses a host below the selected package's needs
before any container exists. Keep its prerequisite refusal ahead of the artifact
hash, keep the mock-identity and mock-capability prohibitions, and keep the
prompt, the completion, and every host identifier out of the records it writes.

The [local serving baseline](docs/serving/local-serving-baseline.md) is the
registered experiment above that composition. Validate it without Docker or model
access with `uv run --locked python -m tools.serving_baseline check`. Only `run`
executes it, and only with `--confirm-real-runtime`; `summarize` recomputes the
summary from committed records and touches nothing else. Keep the fixture and the
generation settings in agreement with the runtime profile, keep concurrency equal
to the runtime's parallel slots, keep warm-up out of every distribution, and never
publish a figure it produces as a benchmark.

Five rules apply to a change here beyond the usual ones.

**A pin is compared to its source, never restated.** The runtime image digest and
the model revision, file, size, and hash are copied from
[ADR 0002](docs/architecture/decisions/ADR-0002-model-and-serving-runtime.md), and
`tests/adapters/test_llama_server_pins.py` reads that record, the compatibility
matrix, and the committed `synchronous-llm` example and fails when a copy drifts.
Changing a pin therefore means changing the accepted decision first, and a pin
that appears only in code is a pin nothing checks.

**A value ADR 0002 left undecided may not acquire a default here.** The context
length, the KV budget, the concurrency limit, and the sampling defaults are
recorded there as undecided. A default added in this package would be read back
later as a project recommendation nobody made, so the required inputs stay
required and a test enforces it. The request the adapter sends therefore carries no
sampling parameter at all, and a test names seven of them and asserts each absent.

**A canonical error code is mapped where it was decided, not where it is raised.**
The condition-to-code mapping is copied from
[the accepted API surface data](docs/serving/inference-api-surface.v1alpha1.json),
carries that record's own condition identifiers, and is compared to it by
`tests/adapters/test_llama_server_inference.py`. A change that maps a new condition
changes that record first. A code the record lists as never emitted — `rate-limited`
among them — may not be produced here, because emitting one would claim a mechanism
V1 does not have.

**A runtime's own words stop at the transport.** The three transport failures take
no argument and carry no message, and a source sweep over `src/` fails if any
construction site passes one. Downstream of that seam an unrecognised error's
message is dropped rather than wrapped, and no canonical error repeats a status
code, a body, a host, a port, a path, or a prompt. That is
[the redaction rule](docs/telemetry/redaction.md) at the one place in this
distribution that receives a prompt.

**Every runtime call goes through both deadlines, and a check on it asserts the
elapsed time.** The transport is handed the configured budget; the adapter's
backstop is that budget plus a grace, and the grace is load-bearing rather than
cosmetic — set equal, the backstop starts first and wins by the dispatch cost, so
every slow runtime is reported `request-timeout` and `upstream-timeout` becomes a
code nothing can produce. A new call that skips the bounded helper is an unbounded
stretch inside a bounded call, and a check that asserts only the error code would
pass just as happily if the call had taken thirty seconds to produce it. Assert the
clock.

### The real-runtime lane

[`tests/realruntime/`](tests/realruntime/) is the only executable suite here that
talks to a running runtime holding the pinned model. It carries the `realruntime`
marker, which the default marker expression deselects, and it reads the six runtime
settings from the process environment — the only place in this repository that
does. It **skips** when they are unset:

```sh
uv run --locked python -m pytest tests/realruntime -m realruntime -q
```

Running it needs a capable host, the pinned image, the hash-verified model
artifact, and explicit authorization, and the procedure is
[the feasibility workflow](docs/serving/feasibility-workflow.md). A passing run is
one input to an evidence record that also names the digest, the revision and
per-file hash, the environment, the commands, and the results — never the record
itself. A change that adds an assertion here states which stage a failure names, in
the vocabulary the lane's `failureDiagnostics` already publishes.

### Test lanes and markers

The pytest configuration lives in [`pytest.ini`](pytest.ini) and stays there.
`pyproject.toml` declares no pytest table, ADR 0009 D8 decided that deliberately,
and a test refuses one — because the marker expression below is the mechanism
behind "the default lane cannot execute a real model", and a mechanism is worth
keeping where a reader will look for it.

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

`cluster`, `failure`, and `load` currently select nothing, because the layers
behind them have no code yet. That is the intended state: the marker exists so
that the first test of its kind is written under it rather than into whichever
suite was already open. `unit` was in that list until `V1-S1-001` wrote the first
domain code and now selects [`tests/domain/`](tests/domain/); `adapter` was in it
until `V1-S1-003` wrote the deterministic mock adapter and now selects
[`tests/adapters/`](tests/adapters/); `realruntime` was in it until `V1-S1-004-PR2`
wrote [`tests/realruntime/`](tests/realruntime/), which is written and has never
been run against a runtime; and `mockintegration` was in it until `V1-S1-005-PR1`
built the API for [`tests/api/`](tests/api/) to drive.

A new test module belongs to exactly one layer and declares that layer's marker at
module level:

```python
pytestmark = pytest.mark.contract
```

A module under a layer's declared paths that omits its marker fails the strategy
suite, because a marker nothing is marked with selects nothing, silently. It must
also be added to
[the test inventory](docs/testing/test-inventory.v1alpha1.json) with the claim it
protects, or with a written reason for protecting none; a module absent from the
inventory fails the inventory suite.

Adding a test that needs a cluster or a model means adding it to a layer outside the
default lane. Adding a public claim means adding a row to
[the claim and test matrix](docs/testing/claim-test-matrix.md) with a test layer, an
environment, a required certification level, and an evidence owner; a claim with none
of those fails the build — and it must then be named by an inventory entry or
recorded there as a coverage gap.

### Test strategy, inventory, and certification

Changes under `docs/testing/`, `tests/testing/`, or `pytest.ini` must pass the
strategy suite — and so must **any change that adds, renames, moves, or removes a
test module anywhere in the tree**, because the inventory beside the strategy
lists every one of them:

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

It also checks
[the test inventory](docs/testing/test-inventory.v1alpha1.json) against the test
tree and the strategy in both directions: that every `test_*.py` under `tests/` is
listed exactly once and every listed module exists; that the layer and marker
recorded for a module are the ones the strategy's own declared paths give it, and
that the module declares that marker; that a module names only claims whose layers
include its own, so a `mock` suite cannot be recorded as defending a claim needing
a real runtime; that a module naming no claim says why; and that every claim is
either named by a module or recorded as a coverage gap with a reason, and never
both.

It checks a strategy, not a test suite. Three of the eleven layers it describes have
no code, nothing here can distinguish a layer that is honestly planned from one that
will never be written, and the inventory records which suite defends which claim
without reading a single assertion inside one.

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

That suite checks a catalog and not a running system. A second one,
[`tests/telemetry/test_api_telemetry_agreement.py`](tests/telemetry/test_api_telemetry_agreement.py),
compares the catalog against what the distribution declares and refuses — that every
emitted metric carries the name, instrument, labels, and bucket count its row
declares, that a label the catalog forbids cannot be declared, and that a field it
does not publish cannot be written — and
[`tests/api/test_api_observability.py`](tests/api/test_api_observability.py) drives
the API and reads what it actually emitted. No span is produced by anything, and no
store has held a single series or record.

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
committed; that every count those documents state in prose is recomputed from the
data; and that a reserved vocabulary of twelve terms appears in **every Markdown
document committed here** only inside a sentence that denies it.

It checks a baseline, not a system. Nothing in this repository authenticates a
caller, authorises a request, enforces a network policy, or applies a security
context to a pod it deployed, because nothing here deploys a pod or serves a request.
No secret scanner has been run and recorded. An image scanner and a dependency
auditor have each been run once, by hand, against the pinned runtime image and the
committed dependency lockfile; neither runs continuously, because no continuous-
integration service is selected, and no assessment by an outside party has ever
been performed.

A change that adds a control names the verification for it or declares that it has
none — there is no third option, and the derivation is what makes that true rather
than a convention. A change that adds a security document is scanned for the reserved
vocabulary automatically, because the scan reads every Markdown file rather than a
list somebody has to remember to extend. A change that adds a threat names a control or the register entry
that carries it. A change that removes a register entry adds the control that replaces
it; that last rule is enforced by review alone and is marked as such. The decision
behind all of it is
[ADR 0008](docs/architecture/decisions/ADR-0008-v1-security-baseline.md), and the
document it exists to protect is
[the deferred-risk register](docs/security/deferred-risks.md): a register that shrinks
because the project wants to look further along is the failure this suite cannot
catch.

### Inference API surface

Changes under `docs/serving/` or `tests/serving/` must pass the serving-surface
suite:

```sh
python -m pytest tests/serving -q
```

It reads only files in this repository and needs `pytest`. It checks the committed
surface
[`docs/serving/inference-api-surface.v1alpha1.json`](docs/serving/inference-api-surface.v1alpha1.json):
that every one of the thirteen canonical error codes is either mapped to a condition
or recorded as never emitted with a reason, and never both, so that a code cannot be
dropped by being forgotten; that a `retryable` value differing from the canonical
default is marked an override rather than left looking like a discrepancy; that a row
claiming the trial observed a field names one the feasibility record carries as a JSON
member key inside a fenced block — not a word that happens to appear in its prose — and
a row that was not observed cites no evidence; that a capability declares what supports it and agrees
with the deferral already recorded in the telemetry catalog; that every serving-contract
role is covered by an in-scope endpoint or by a stated equivalent; that every field
the runtime returned and this surface drops was actually seen and says why; that the
request counter this surface owes exists in the telemetry catalog and its error
counter is labelled by the code the mapping produces; and that the decision, the
document, and the data publish the same endpoints, codes, and capability names.

It checks a decision, not an API. **Nothing in this repository listens on a port,
registers a route, or answers a request.** No OpenAPI document is published, nothing
was added to [`contracts/`](contracts/), and a test refuses a contract artifact for
this surface appearing there without the record changing. A shape stated in these
documents is a decision a reviewer can argue with; it becomes an interface when
`V1-S1-005` serves it.

A change that adds an endpoint states its serving-contract role and says what serves
it, and "none" is the only answer this repository can honestly give today. A change
that removes one records it as out of scope with a reason rather than deleting the
row. The decision behind all of it is
[ADR 0010](docs/architecture/decisions/ADR-0010-inference-api-compatibility-surface.md).

### The workload template

Changes under `src/inferops/scaffolding/`, `tools/workload_scaffold/`,
`tests/scaffolding/`, or [`docs/scaffolding/`](docs/scaffolding/) must pass the
template suite, which runs in the default lane under the `contract` marker:

```sh
uv run --locked python -m pytest tests/scaffolding -q
uv run --locked python -m pytest tests/contracts -q
uv run --locked python -m mypy
```

It reads only files in this repository. It renders the template from representative
parameter sets and puts what came out through the *same* validator every committed
fixture goes through, and then through the contract package's own validation
pipeline, so a generated workload is held to the published contract rather than to
a copy of it. It also imports the generated test skeleton and runs it against the
workload rendered beside it: a skeleton that does not run is a file that looks like
coverage.

Four rules travel with a change here, and each has a check behind it.

**A template may not offer a place to paste a secret.** The check is applied to the
template, not only to the output, because a field introduced in a template is
inherited by every workload generated afterwards.

**A mock must declare itself a mock in its own contents.** Rule 1 of
[the mock and real boundary](docs/serving/mock-and-real-boundary.md) is checked in
the rendered document, in the workload's own name, and in the prose a reader meets
first. The mock and the real quick starts must also stay distinct in both
directions: the mock must not offer the real-runtime lane, and the real one must.

**A generated workload cites only evidence it has produced**, which today is none.
Pre-filling `evidence.proofRefs` with an existing record would hand every generated
workload a result produced by a different one.

**A generated workload carries no platform implementation code.** It declares; the
platform serves. The generated test reads the contract through
`inferops.domain.workload` and imports nothing from the API, the adapters, or the
scaffolder.

Adding a template parameter means adding it to the dataclass, to its published
constraint, to the template that reads it, to `PARAMETER_OPTIONS` in
[`tools/workload_scaffold/arguments.py`](tools/workload_scaffold/arguments.py),
and to the parameter table in
[the template document](docs/scaffolding/workload-template.md). A parameter no
template reads, a placeholder no parameter supplies, and a parameter the command
line cannot gather all fail the suite.

Three more rules travel with the command that writes a workload.

**Nothing is written before a refusal.** The order is refuse, render, validate,
plan, write, read back — and it is checked against a file system rather than
described: an invalid parameter set must leave the destination directory
uncreated, not merely empty.

**Nothing is overwritten.** A generated workload is an ordinary committed
directory the moment it exists. There is no `--force`, adding one is a change to
[the template document](docs/scaffolding/workload-template.md) with an argument
attached, and an occupied destination must be refused with its contents
byte-identical afterwards.

**A failed write leaves what it found.** Every directory and file the command
creates is recorded as it is created and removed in reverse order on any failure,
including a failure of the read-back. A rollback that cannot remove something
reports it rather than claiming a clean undo.

The generated project is proven by running it, not by importing it:

```sh
uv run --locked python -m tools.workload_scaffold --help
```

generates into a directory of your choosing, and the suite runs the generated
skeleton under a real `python -m pytest` subprocess from outside this repository.
An import proves a module is importable; only a subprocess proves the command a
generated quick start prints.

### The toolchain itself

Changes to [`pyproject.toml`](pyproject.toml), [`uv.lock`](uv.lock),
[`.python-version`](.python-version), `src/`, or `tests/testing/test_toolchain.py`
must pass the strategy suite above, which now also reads
[ADR 0009](docs/architecture/decisions/ADR-0009-python-toolchain.md) and compares
its two published tables against the configuration they describe. A dependency
bumped without updating that record fails, and so does a version typed into the
record that the lockfile does not pin.

The same suite refuses a `Taskfile`, a `justfile`, a `Makefile`, a `noxfile.py`, and
a `tasks.py`. Adopting a task runner is an amendment to ADR 0009 D7 with an argument
attached, not a new file.

A change that alters the packaging layout also rebuilds the distribution and
inspects what came out of it:

```sh
uv build
```

The wheel must contain the `inferops` package and its metadata and nothing else; the
source distribution is anchored to the repository root, because an unanchored
include pattern matches at every depth and quietly ships whatever it found.

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
