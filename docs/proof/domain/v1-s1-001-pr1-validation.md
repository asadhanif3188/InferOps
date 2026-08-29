# V1-S1-001-PR1 change validation

Date: 2026-08-29

Classification: **local static evidence for the change itself.** Every result below
comes from running a tool over files in this repository. No cluster was created, no
model was downloaded, no runtime was started, no request was served, and no secret
scanner, image scanner, or dependency scanner was run. Nothing here is evidence that
InferOps serves anything; it is evidence that
[the workload domain model](../../domain/workload-domain-model.md) parses the
committed contract fixtures, refuses what it cannot represent, and imports nothing
the architecture forbids.

Claim boundary: every committed valid fixture parses into typed domain objects; a
parsed document rebuilds into exactly the document it came from; a contract version
this package does not implement is refused before any field below it is read; every
field the published schema declares required is required by the parser at that
field's own address; the domain's copy of every published pattern, vocabulary, and
bound agrees with the schema; no refusal repeats a value read out of the document;
and no module under `src/inferops/` imports anything outside the standard library
and this distribution.

**What this record does not establish.**

- **It does not establish that a contract is valid.** This change implements none of
  the published semantic rules. A document with an inverted replica range, a
  mismatched profile block, a duplicate secret name, or a pasted credential in a
  locator parses into a domain object here, and two tests assert exactly that. The
  complete published check is still
  [`tools/contract_validation/`](../../../tools/contract_validation/), and the
  pipeline that brings those rules into the domain is `V1-S1-001-PR2`.
- **It does not establish that anything consumes a domain object.** No adapter, API,
  controller, or chart exists.
- **It does not establish that these checks pass anywhere else.** One Windows host
  ran them, by hand, once. No Linux or macOS host has run them and no
  continuous-integration service exists to run them, which is
  [ADR 0005](../../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
  D6 and is still open.
- **It establishes nothing about dependency vulnerabilities or secrets in history.**
  No scanner is configured and none was run. `gitleaks` is committed as a
  configuration only, and the security-scan layer stays `planned` for that reason.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| `uv` | `0.9.16 (a63e5b62e 2025-12-06)` |
| Python, provisioned by `uv` into `.venv` | `3.12.12 (main, Dec  5 2025, 21:31:16) [MSC v.1944 64 bit (AMD64)]` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1 (compiled: yes)` |
| `pytest` | `8.4.2` |
| `jsonschema` | `4.26.0` |
| `PyYAML` | `6.0.3` |
| Branch base | `main` at `b2f1bee` |

Every command below was run through `uv run --locked`, so each ran against the
versions the committed [`uv.lock`](../../../uv.lock) pins rather than against
whatever happened to be installed. No dependency was added or changed by this
change: the domain declares none, and the lockfile is untouched.

## Commands and results

Run from the repository root. Output is reproduced as it was printed, trimmed only
where a progress line repeats.

### Lint, format, and types

```text
$ uv run --locked ruff check .
All checks passed!

$ uv run --locked ruff format --check .
100 files already formatted

$ uv run --locked python -m mypy
Success: no issues found in 27 source files
```

`mypy` runs in strict mode over `src`, `tools`, `tests`, and `conftest.py`. The new
package carries no `# type: ignore`; there is still not one anywhere in this
repository.

### The default test lane

```text
$ uv run --locked python -m pytest -q
2799 passed, 7 skipped in 10.88s
```

The default marker expression is unchanged, so this lane still deselects every
layer that needs a cluster or a model. The seven skips are the pre-existing ones.

### The domain suite, and the layer it fills

```text
$ uv run --locked python -m pytest tests/domain -q
263 passed in 0.91s

$ uv run --locked python -m pytest tests/domain/test_workload_domain.py -q
100 passed in 0.38s

$ uv run --locked python -m pytest tests/domain/test_workload_schema_agreement.py -q
163 passed in 0.63s

$ uv run --locked python -m pytest -m unit -q
263 passed, 2542 deselected in 1.35s
```

The last command is the one worth reading twice. The `unit` marker was registered by
`V1-S0-006` and selected nothing until this change; it now selects exactly the 263
checks in `tests/domain/`, which is why the `unit` layer moves from `planned` to
`implemented` in
[the test strategy](../../testing/test-strategy.v1alpha1.json) and cites this
record.

### The architecture suite, including the dependency boundary

```text
$ uv run --locked python -m pytest tests/architecture -q
378 passed in 0.30s

$ uv run --locked python -m pytest tests/architecture/test_domain_dependency_boundary.py -q
21 passed in 0.45s
```

### The distribution

```text
$ uv build
Building source distribution...
Building wheel from source distribution...
Successfully built dist\inferops-0.0.0.tar.gz
Successfully built dist\inferops-0.0.0-py3-none-any.whl
```

The wheel's contents, in full:

```text
inferops-0.0.0.dist-info/METADATA
inferops-0.0.0.dist-info/RECORD
inferops-0.0.0.dist-info/WHEEL
inferops-0.0.0.dist-info/licenses/LICENSE
inferops/__init__.py
inferops/domain/__init__.py
inferops/domain/context.py
inferops/domain/workload/__init__.py
inferops/domain/workload/contract.py
inferops/domain/workload/errors.py
inferops/domain/workload/parsing.py
inferops/domain/workload/values.py
inferops/domain/workload/versions.py
```

Eight modules and the metadata; `tools/`, `tests/`, `contracts/`, and `docs/` stay
outside it. The metadata carries **no `Requires-Dist` line at all**, which is the
machine-readable form of the claim that installing `inferops` acquires nothing: the
domain's only dependencies are the standard library's.

### Documentation and diff hygiene

```text
$ git diff --check
(no output)

$ git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
(no matches)

$ git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
(no matches)
```

Every relative Markdown link in the changed and added documents was resolved with
the check published in [CONTRIBUTING](../../../CONTRIBUTING.md), and every one
resolves. No external link was added.

## What the tests actually assert

The counts above are not the evidence; what the checks look at is. The four groups
below are what 284 of them cover.

| Group | Checks | What a failure would mean |
|---|---|---|
| Fixtures parse, and rebuild | Every file under `contracts/workload/examples/valid/` parses, and `as_document()` reproduces it exactly | A field was dropped, defaulted, or invented |
| The schema and the domain agree | Every pattern, enumerated value, numeric bound, field list, and required field, in both directions | The published contract and the domain's copy of it have drifted |
| Refusals are located and safe | A field path on every refusal; no message repeats any string of eight characters or more from the document, excluding the schema's own vocabulary | A refusal disclosed a value, or could not say where the problem was |
| The dependency rule holds | Every module under `src/inferops/` imports only the standard library and this distribution; none reads a file | The domain acquired an infrastructure dependency or a file system |

The redaction check deserves one note, because it is the one whose strength is easy
to overstate. It asserts that a refusal repeats nothing from the document it
refused. It does **not** assert that a value in the document was safe to hold: a
credential pasted into an annotation value is accepted by the published schema and
therefore by this parser, because annotations are non-normative free text and the
credential heuristic applies to secret locators in the semantic layer. That gap is
the contract's, it is measured in
[the contract document](../../contracts/workload-contract.md), and this change does
not narrow or widen it.

## Public-information review

The published diff was read in full for the categories
[CONTRIBUTING](../../../CONTRIBUTING.md) names.

| Category | Result |
|---|---|
| Credentials or tokens | None. Two strings are shaped like one: `AKIAIOSFODNN7EXAMPLE`, the placeholder published in AWS's own documentation, and `ghp_` followed by a run of zeroes. Both are the forms [the secret-scanning allowlist](../../../.github/secret-scanning-allowlist.md) already names, and both appear only so that a test can assert a refusal does **not** repeat them |
| Model artifacts or large binaries | None |
| Personal filesystem paths, host names, user names | None. The only absolute path in the change is the one `RepositoryPath` refuses in a test, `/etc/passwd` |
| Generated or host state | None. `dist/`, `.venv/`, and the tool caches are ignored |
| Private planning material | None. No planning document, backlog, prompt, or roadmap content is quoted or paraphrased. Story and PR identifiers (`V1-S1-001-PR1`) appear as identifiers only, which is the existing convention in this repository |
| Unsupported capability claims | None found. Every document changed by this PR says what is not built in the same place it says what is |

## Acceptance criteria

The parent story's criteria, and where this PR stands against each.

| Criterion | Status | Evidence |
|---|---|---|
| Valid `synchronous-llm` and `mock-llm` fixtures parse | **Met** | `tests/domain/test_workload_domain.py`, over every file in `examples/valid/` |
| Unsupported version fails canonically | **Met for the version half** | Refused as `UnsupportedContractVersionError` with the field `$.apiVersion`, before any field below it is read. The refusal carries a field, a reason, and request context; it does **not** carry the canonical code `version-unsupported`, which the validation pipeline assigns in PR2 |
| Missing owner, invalid profile, invalid replicas fail canonically | **Partly met, by PR boundary** | Each is refused with a field location, because none can be represented. The canonical code and rule identifier are PR2's |
| Plaintext secret fails canonically | **Deferred to PR2** | `secret-value-in-locator` is a semantic rule. This change does not implement it, and does not claim to |
| Domain package imports no Kubernetes, Helm, Terraform, or runtime SDK | **Met** | `tests/architecture/test_domain_dependency_boundary.py`, from the source rather than by review |
| Validation errors contain request/correlation context where available and no sensitive value | **Met** | `RequestContext` is carried through to every error and is empty when a caller supplied none; the redaction check above |

The parent story `V1-S1-001` is **not** complete. Its validation pipeline, its
canonical error mapping, and its invalid-fixture matrix are `PR2`.
