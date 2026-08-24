# V1-S0-004-PR1 change validation

Date: 2026-08-24

Classification: **local static evidence for the change itself.** Every result below
comes from reading and validating files in this repository. No cluster was created,
no model was loaded, no runtime was started, and no workload was deployed. Nothing
here is evidence that a WorkloadContract does anything, because nothing in this
repository reads one.

Claim boundary: the schema is a valid draft 2020-12 schema; its valid fixtures
validate; the constraints this change documents are the constraints the schema
actually applies; the change's Markdown, links, whitespace, and line endings are
clean; and the published diff carries no private or overclaimed content.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.6` |
| `jsonschema` | `4.26.0` |
| `pytest` | `8.3.4` |
| `PyYAML` | `6.0.2` |
| `ruff` | `0.16.1` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |

## Commands and results

### Contract schema and fixtures

```text
python -m pytest tests/contracts -q
37 passed
```

The suite covers: the schema parses and passes the draft 2020-12 metaschema; it
declares its dialect, `$id`, `apiVersion`, and `kind`; **every** object in it
declares an additional-property policy; each of the three valid fixtures validates
with zero errors; each fixture stays inside the JSON-representable subset of YAML;
no fixture contains a field name that could hold a secret; every
repository-relative reference in a fixture resolves to a real file; the
`synchronous-llm` fixture's runtime digest, model revision, content hash, filename,
and byte count all appear in ADR 0002; the mock fixture is self-labelling and cites
no runtime proof; the mock response fixture identifies itself as a mock from its own
contents; a mock cannot be edited into a production environment, into the native
serving capability, or into citing runtime proof; and repeated validation of the
same document produces byte-identical output.

### Lint and format

```text
python -m ruff check tests/contracts     All checks passed!
python -m ruff format tests/contracts    1 file reformatted
```

`ruff` was run as an additional check and its formatting was applied. It is **not**
a selected repository tool: no linter or formatter is chosen yet, and running one
here does not select it.

### Rejection spot check

The contract document publishes a table of what the platform must reject and where
each rejection happens. That table was checked rather than asserted, by mutating a
valid fixture once per row and confirming both the rejection and the keyword that
produced it. This ran as a one-off script and is not committed; the negative
fixtures that make these permanent are the second pull request's scope.

**Thirty-one mutations, thirty-one rejections:**

| Mutation | Rejected by |
|---|---|
| Unsupported `apiVersion` | `$.apiVersion :: const` |
| Unknown top-level field | `$ :: additionalProperties` |
| Unknown `spec` field | `$.spec :: additionalProperties` |
| Missing owner | `$.metadata :: required` |
| Empty owner | `$.metadata.owner :: minLength` |
| Owner that is not DNS-safe | `$.metadata.owner :: pattern` |
| Mutable workload version (`latest`) | `$.metadata.version :: oneOf` |
| Missing `resources` | `$.spec :: required` |
| Missing `memory` | `$.spec.resources :: required` |
| Quantity in undocumented units | `$.spec.resources.memory :: pattern` |
| Unsupported data classification | `$.spec.security.dataClassification :: enum` |
| Secret reference carrying a `value` field | `$.spec.security.secretRefs[0] :: additionalProperties` |
| Secret reference without owner and rotation | `$.spec.security.secretRefs[0] :: required` |
| Secret locator containing whitespace | `$.spec.security.secretRefs[0].reference :: pattern` |
| Runtime image pinned by tag only | `$.spec.synchronousLlm.runtime.imageReference :: pattern` |
| Model artifact without a content hash | `$.spec.synchronousLlm.modelArtifact :: required` |
| `synchronous-llm` without its profile block | `$.spec :: required` |
| Unsupported profile | `$.spec.profile :: enum` |
| Unsupported environment | `$.spec.environment :: enum` |
| Missing telemetry integration | `$.spec.integrations :: required` |
| Negative `minimumReplicas` | `$.spec.scaling.minimumReplicas :: minimum` |
| Zero `maximumReplicas` | `$.spec.scaling.maximumReplicas :: minimum` |
| Absolute path in `runbookRef` | `$.spec.evidence.runbookRef :: pattern` |
| Parent traversal in `runbookRef` | `$.spec.evidence.runbookRef :: not` |
| Annotation key without a namespace | `$.metadata.annotations :: pattern` |
| Mock in a production environment | `$.spec.environment :: const` |
| Mock claiming the native serving capability | `$.spec.model.servingCapability :: const` |
| Mock citing real-runtime proof | `$.spec.evidence.proofRefs :: maxItems` |
| Mock with `ciOnly: false` | `$.spec.mockLlm.ciOnly :: const` |
| Mock carrying an accelerator | `$.spec.resources.accelerator.count :: const` |
| Mock carrying the real profile block | `$.spec :: not` |

**Three mutations were accepted, exactly as documented.** These are the gaps the
contract document already names, and the same script was used to confirm they are
gaps rather than to discover it:

| Accepted today | Why | Owner |
|---|---|---|
| `minimumReplicas: 5`, `maximumReplicas: 2` | JSON Schema cannot compare two sibling values | Second pull request |
| A base64-shaped string in a secret locator | Indistinguishable from a short opaque locator without heuristics | Second pull request |
| A model and runtime pair that does not go together | Needs a compatibility matrix that does not exist | Second pull request |

Publishing this table is the point of the check: a rule stated in a document and
not applied by the schema is worth less than a rule stated as unenforced.

### Whitespace, blanks, and hard tabs

```text
git diff --cached --check
```

Clean, exit `0`.

The two Markdown checks from [CONTRIBUTING](../../../CONTRIBUTING.md) were run over
every tracked Markdown file in the repository, not only the changed ones. **No
trailing blank and no hard tab in either.**

### Relative link resolution

The POSIX link check from [CONTRIBUTING](../../../CONTRIBUTING.md) was run over
every tracked Markdown file. **No broken target.** This change adds nine relative
links that cross directory boundaries — from `contracts/` into `docs/`, from
`docs/contracts/` into `contracts/` and `tests/`, and from a decision record up to
the repository root — so the check mattered more than usual.

No in-page anchor is introduced by this change, so the anchor check that the
previous record needed does not apply.

### Line endings

```text
git ls-files --eol contracts/ tests/ docs/contracts/ docs/architecture/decisions/ADR-0003-workload-contract-schema-tooling.md
```

Every new file reports `i/lf`. Git normalises on checkout under the existing
`* text=auto` rule.

### Checks not run, and why

| Check | Status | Reason |
|---|---|---|
| `bash -n`, `shellcheck` | **Not run** | No file under `scripts/` is changed |
| `kubeconform` | **Not run** | No file under `deploy/` is changed |
| Cluster smoke test, runtime proof | **Not run** | This change adds no manifest and starts nothing. It would produce no evidence about a schema |
| Consumer or provider certification suite | **Not run** | Neither exists. Certification is a later story |
| Dependency vulnerability scan of `jsonschema`, `pytest`, `PyYAML` | **Not run** | No scanner is selected. Recorded as an open item in ADR 0003's security section rather than silently skipped |
| Validation on a second host or a non-Windows platform | **Not run** | One Windows host, as with every other record here |
| Continuous integration | **Not run** | No lane exists. Every check above was run by hand |

## Diff inspection

The full staged diff — 17 files: 6 Markdown added, 4 Markdown modified, 1 JSON
schema, 1 JSON fixture, 3 YAML fixtures, 1 Python test file, 1 contract changelog —
was read in full and searched.

| Looked for | Found |
|---|---|
| Local filesystem paths, drive letters, home directories | None. The only path-shaped strings are repository-relative and every one resolves |
| Host name, user name, account identifiers, email addresses | None |
| IP addresses, ports, endpoints | None |
| Credentials, keys, tokens, bearer values | **None.** Every occurrence of the word is a field name, a rejection rule, or a locator in the secret-reference shape example. `inferops-serving/model-registry#token` is a Kubernetes secret name and key, not a value |
| Private planning material, prompts, roadmaps, positioning, strategy | None. Work-item identifiers appear only in the form already published here |
| Model weights, binaries, generated state, caches | None. No file in the diff is generated |
| Overclaimed capability | None found; see below |

### On the secret-reference shape example specifically

[`synchronous-llm-secret-refs.yaml`](../../../contracts/workload/examples/valid/synchronous-llm-secret-refs.yaml)
is the one file in this change that talks about secrets in concrete terms, so it
was checked separately. It names two secrets that **do not exist**: there is no
`inferops-serving` namespace in any cluster this project runs, no
`model-registry` secret, and no telemetry ingest path. Both entries are locators,
both carry an owner and a rotation responsibility, and neither carries a value —
because the schema provides no field one could go in. The file's own header says
it is a shape example rather than a deployed workload.

### On the capability claim specifically

This change publishes a contract, which is exactly the kind of artifact that reads
as more finished than it is. The wording was checked in both directions:

- The README banner now says one workload contract schema is published, and in the
  same sentence that nothing here reads one.
- The contracts index status is "one contract accepted at alpha maturity. No
  component in this repository consumes it."
- The contract document carries a section titled *What this contract does not do*,
  which states that it deploys nothing, certifies nothing, has no consumers, does
  not enforce all of its own semantic rules, and has an `$id` that is not
  retrievable.
- The rejection table marks four rules as not yet enforced, in the same table that
  states them.
- Every fixture header says it is a contract example and not a deployable workload.
- ADR 0003's evidence section states that its result establishes that the tooling
  validates a schema on one host and "nothing about any workload, any runtime, or
  any other host".

### On the mock boundary specifically

[The mock and real serving boundary](../../serving/mock-and-real-boundary.md) is an
accepted rule, and this change is the first artifact that has to obey it in a
machine-readable form. Rule 1 — label at the source — is met by
`spec.mockLlm.ciOnly` in the contract and by the `_inferopsMock` block in the
response fixture, so both stay identifiable after being copied out of their
directory. Rule 5 — a mock may never be the default in the mandatory path — is met
structurally: the mock profile cannot leave the `ci` environment, and it cannot
reference the native serving capability. The five mock rejections in the table above
are the evidence, and three of them are permanent tests rather than a one-off script.

## Files changed

| File | Change |
|---|---|
| `contracts/workload/workload-contract.v1alpha1.schema.json` | Added — the schema |
| `contracts/workload/examples/valid/synchronous-llm-local.yaml` | Added — real profile, pinned to ADR 0002 |
| `contracts/workload/examples/valid/mock-llm-ci.yaml` | Added — CI-only mock profile |
| `contracts/workload/examples/valid/synchronous-llm-secret-refs.yaml` | Added — secret-reference shape example |
| `contracts/workload/fixtures/mock-llm-chat-completion.response.json` | Added — deterministic, self-labelling mock response |
| `contracts/workload/examples/README.md` | Added — what the fixtures are and are not |
| `contracts/README.md` | Added — contract package index and rules |
| `contracts/CHANGELOG.md` | Added — contract-package history |
| `docs/contracts/workload-contract.md` | Added — identifiers, structure, secrets, extension, versioning, rejection and error policy |
| `docs/architecture/decisions/ADR-0003-workload-contract-schema-tooling.md` | Added — schema language, authoring form, validator, no codegen |
| `docs/proof/contracts/v1-s0-004-pr1-validation.md` | Added — this record |
| `tests/contracts/test_workload_contract_v1alpha1.py` | Added — the deterministic suite |
| `docs/contracts/README.md` | Contracts index moves from "none accepted" to one accepted |
| `docs/architecture/README.md` | ADR 0003 indexed; filename convention corrected to the `ADR-` form already in use |
| `README.md` | Status banner and entry points |
| `CONTRIBUTING.md` | Contract validation commands and required packages |
| `CHANGELOG.md` | Recorded the above |

## What this change leaves for the second pull request

- Invalid fixtures under `contracts/workload/examples/invalid/`.
- A semantic validation layer above the schema: replica range ordering, the model
  and runtime compatibility matrix, and detection of a secret value pasted into a
  locator field.
- Validator tests and a published compatibility and negative-test matrix.

Until those land, three documented rules are stated but not applied, and the table
above says which.
