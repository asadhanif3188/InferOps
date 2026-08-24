# V1-S0-004-PR2 change validation

Date: 2026-08-24

Classification: **local static evidence for the change itself.** Every result below
comes from reading and validating files in this repository. No cluster was created,
no model was loaded, no runtime was started, and no workload was deployed. Nothing
here is evidence that a WorkloadContract does anything, because nothing in this
repository reads one.

Claim boundary: every valid fixture inherited from the first pull request still
validates under both layers; every invalid fixture is refused with exactly the
canonical error code, rule identifier, and field location published beside it;
each fixture's declared validation layer is the layer that actually refuses it;
neither a refusal's message nor its field location repeats a value read out of the
document; and the published diff carries no private or overclaimed content.

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

### Contract suite

```text
python -m pytest tests/contracts -q
191 passed, 7 skipped
```

Split across the two files:

```text
python -m pytest tests/contracts/test_workload_contract_v1alpha1.py -q
37 passed

python -m pytest tests/contracts/test_workload_contract_validation.py -q
154 passed, 7 skipped
```

The 37 are the first pull request's schema suite, unchanged except for a docstring
that pointed forward to work this change lands. The remaining 161 are new.

The seven skips are deliberate and visible. One test asks what a consumer
validating against the bare schema file sees, which is a question only the nine
structural fixtures have an answer to; the seven semantic fixtures skip it by
name. They are reported as skipped rather than silently returning, so that a
reader of the summary line is not told that seven assertions ran when none did.

### What the new suite actually asserts

| Group | Checks |
|---|---|
| Valid fixtures preserved | The three inherited fixtures are all still present by name, and each validates under **both** layers with zero findings |
| Locator false positives | The secret-reference example's two locators survive the credential heuristic, as do Vault, AWS Secrets Manager, and Google Secret Manager path forms |
| Manifest agreement | Every invalid fixture is in the manifest and the reverse; every expected rule is a registered rule; every expected code is a canonical code and carries that rule's code |
| Exact refusal | Each of the sixteen fixtures produces exactly the `(code, rule, field)` list committed beside it, in that order |
| Determinism | Five validations of each invalid fixture produce identical output, in one order, with array indices ordered as numbers. The command-line entry point's determinism is checked by hand rather than by the suite; see below |
| Layer claim | A fixture declared `structural` must be refused by the bare schema; one declared `semantic` must be **accepted** by it and refused only above it |
| Non-retryable | Every finding on every invalid fixture reports `retryable: false` |
| No leakage | Neither a finding's message nor its field location contains any string of eight characters or more read out of the document, excluding the schema's own published vocabulary. Separately: an annotation key that is over-long or credential-shaped is refused without being repeated back |
| Credential heuristic | Eleven credential shapes are caught; six locator shapes are not; three documented gaps are asserted to still be gaps |
| Compatibility matrix | Shape, unique runtime identifiers, no repository mapped to two runtimes, every reference resolves to a real file, accepted formats are declared formats, the single executed pair matches ADR 0002, and every real valid fixture pins a runtime that pair covers |
| Document agreement | Every rule the validator can cite appears in the contract document; every canonical code it can emit appears there; no code it emits is retryable; every semantic rule has an invalid fixture; the two structural rules that have none are exactly the two the document names |
| Single refusal per fault | An annotation key that breaks two constraints at once produces one finding under one rule, not one per constraint |

### Command-line validation

```text
python -m tools.contract_validation --json \
  contracts/workload/examples/valid/*.yaml \
  contracts/workload/examples/invalid/*.yaml
```

**3 documents valid, 16 refused, 24 findings.** Exit status `1`, as expected when
any document is refused. Run twice and compared with `cmp`: **byte-identical.**

Against the valid fixtures alone the same command exits `0`.

### The sixteen refusals, as published

**Seven** of these are refused by rules the published schema cannot express, and
nine by the schema itself. Those seven are the measured cost of validating against
the raw schema alone, and a test fails if any of them starts being caught
structurally without the manifest saying so.

| Fixture | Layer | Code | Rule | Field |
|---|---|---|---|---|
| `unsupported-api-version.yaml` | Structural | `version-unsupported` | `contract-version-unsupported` | `$.apiVersion` |
| `missing-owner.yaml` | Structural | `contract-invalid` | `field-required` | `$.metadata.owner` |
| `resource-free-workload.yaml` | Structural | `contract-invalid` | `field-required` | `$.spec.resources` |
| `owner-not-dns-safe.yaml` | Structural | `contract-invalid` | `value-malformed` | `$.metadata.owner` |
| `malformed-identifiers.yaml` | Structural | `contract-invalid` | `value-malformed`, `value-malformed`, `value-not-permitted`, `value-malformed` | `$.metadata.annotations.unnamespaced-key`, `$.metadata.name`, `$.metadata.version`, `$.spec.attribution.tenant` |
| `unsupported-profile.yaml` | Structural | `contract-invalid` | `value-not-permitted` | `$.spec.profile` |
| `unknown-field.yaml` | Structural | `contract-invalid` | `field-unknown` | `$.spec.scaling.maxiumumReplicas` |
| `secret-value-in-value-field.yaml` | Structural | `contract-invalid` | `field-unknown` | `$.spec.security.secretRefs[0].value` |
| `mock-presented-as-real.yaml` | Structural | `contract-invalid` | `value-not-permitted`, `value-out-of-range`, then `value-not-permitted` ×3 | `$.spec.environment`, `$.spec.evidence.proofRefs`, `$.spec.model.servingCapability`, `$.spec.resources.accelerator.count`, `$.spec.resources.accelerator.type` |
| `replica-range-inverted.yaml` | **Semantic** | `contract-invalid` | `replica-range-inverted` | `$.spec.scaling` |
| `secret-value-in-locator.yaml` | **Semantic** | `contract-invalid` | `secret-value-in-locator` ×2 | `$.spec.security.secretRefs[0].reference`, `$.spec.security.secretRefs[1].reference` |
| `duplicate-secret-ref-name.yaml` | **Semantic** | `contract-invalid` | `secret-ref-name-duplicated` | `$.spec.security.secretRefs[1].name` |
| `mock-with-secret-refs.yaml` | **Semantic** | `contract-invalid` | `mock-secret-ref-declared` | `$.spec.security.secretRefs` |
| `runtime-model-incompatible.yaml` | **Semantic** | `contract-invalid` | `runtime-model-incompatible` | `$.spec.synchronousLlm.modelArtifact.file` |
| `runtime-unregistered.yaml` | **Semantic** | `contract-invalid` | `runtime-unregistered` | `$.spec.synchronousLlm.runtime.imageReference` |
| `model-artifact-format-unrecognised.yaml` | **Semantic** | `contract-invalid` | `model-artifact-format-unknown` | `$.spec.synchronousLlm.modelArtifact.file` |

### What the previous change accepted, and what happens to it now

The first pull request's evidence record listed three mutations it accepted and
named each as this change's work. **Two are now refused outright; the third is
narrowed rather than closed**, and saying so is the point of running the check
instead of asserting it.

| Mutation PR1 accepted | Now |
|---|---|
| `minimumReplicas: 5`, `maximumReplicas: 2` | **Refused.** `replica-range-inverted.yaml` |
| A model and runtime pair that does not go together | **Refused.** `runtime-model-incompatible.yaml` |
| An unpadded base64 string in a secret locator, and any alphanumeric credential | **Partly.** The exact string PR1 used, `aHVudGVyMg`, still passes: it is ten characters, below the opaque-segment bound. A longer blob of the same kind is refused, and so is any of the thirty-odd published credential prefixes |

The third row disagrees with the first draft of this paragraph, which said all
three were closed. `aHVudGVyMg` was run against the new layer and passed. The gap
that remains is the one
[the contract document](../../contracts/workload-contract.md) states and three
tests pin.

### The credential heuristic, measured rather than asserted

The first pull request measured what the schema's locator **pattern** does. That
measurement stands and is unchanged: over 400 random secrets, padded base64 mostly
fails the pattern and unpadded base64 mostly passes, and any alphanumeric
credential passes untouched. This change adds the check above the pattern, and its
behaviour is asserted in both directions rather than claimed.

**Caught (11 shapes, each asserted by a test):** AWS access key identifiers
(`AKIA`, `ASIA`), GitHub tokens (`ghp_`, `github_pat_`), GitLab (`glpat-`), Hugging
Face (`hf_`), Slack (`xoxb-`), OpenAI-style (`sk-`), Google API keys (`AIza`), a
JSON Web Token (`eyJ`), and an opaque 31-character mixed-case segment with digits
embedded in an otherwise ordinary path.

**Not caught, deliberately (6 locator shapes, each asserted by a test):**
`inferops-serving/model-registry#token`, `inferops/telemetry/ingest#key`, a Vault
path, a Google Secret Manager resource name, a locator containing
`TelemetryIngestPathForServing`, and an AWS Secrets Manager ARN. A check that
refuses well-formed references is switched off within a week, and then nothing is
checked at all.

**Still missed, asserted as still missed:** `Winter2026`,
`inferops/telemetry/hunter2`, and `correcthorsebatterystaple` all pass, and so
does the ten-character `aHVudGVyMg` from the previous change's record. A short or
low-entropy secret has the shape of a name, and no shape heuristic separates the
two. There is a test asserting each of the three committed strings passes, so a
future change that closes the gap has to come to
[the contract document](../../contracts/workload-contract.md) and rewrite the
paragraph rather than leave it overstating the check.

### Lint and format

```text
python -m ruff check tests/contracts tools conftest.py     All checks passed!
python -m ruff format tests/contracts tools conftest.py    1 file reformatted
```

`ruff` was run as an additional check and its formatting was applied. It is **not**
a selected repository tool: no linter or formatter is chosen yet, and running one
here does not select it. The reformatted file is the new test module.

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
every tracked Markdown file. **No broken target.** This change adds links that
cross directory boundaries in both directions — from `docs/contracts/` into
`contracts/` and `tools/`, and from `contracts/` into `docs/` and `tests/` — so
the check mattered.

No in-page anchor is introduced by this change.

### Line endings

```text
git ls-files --eol conftest.py tools/ contracts/ tests/
```

Every new file reports `i/lf`. Git normalises on checkout under the existing
`* text=auto` rule.

### Checks not run, and why

| Check | Status | Reason |
|---|---|---|
| `bash -n`, `shellcheck` | **Not run** | No file under `scripts/` is changed |
| `kubeconform` | **Not run** | No file under `deploy/` is changed |
| Cluster smoke test, runtime proof | **Not run** | This change adds no manifest and starts nothing. It would produce no evidence about a validator |
| Serving a workload described by any fixture | **Not run** | No serving path reads a WorkloadContract. Format compatibility in the matrix is a necessary condition, not a demonstration |
| Consumer or provider certification suite | **Not run** | Neither exists. Certification is a later story |
| Dependency vulnerability scan of `jsonschema`, `pytest`, `PyYAML` | **Not run** | No scanner is selected. It remains the open item ADR 0003's security section already records |
| Type checking of the new module | **Not run** | No type checker is selected repository-wide. Annotations are present; nothing verifies them |
| Coverage measurement | **Not run** | No coverage tool or threshold is selected. Rule coverage is enforced structurally instead: a test fails if any semantic rule has no invalid fixture |
| Validation on a second host or a non-Windows platform | **Not run** | One Windows host, as with every other record here |
| Continuous integration | **Not run** | No lane exists. Every check above was run by hand |

## Diff inspection

The full staged diff — **35 files, 26 added and 9 modified**: 8 Markdown modified,
1 Markdown added, 16 YAML fixtures added, 2 JSON files added, 6 Python modules
added, 1 Python test module added, 1 Python test module modified — was read in
full and searched.

| Looked for | Found |
|---|---|
| Local filesystem paths, drive letters, home directories | None. The only path-shaped strings are repository-relative and every one resolves |
| Host name, user name, account identifiers, email addresses | None |
| IP addresses, ports, endpoints | None |
| Credentials, keys, tokens, bearer values | **None that authenticate against anything.** See the section below, which is the one part of this change that needed its own examination |
| Private planning material, prompts, roadmaps, positioning, strategy | None. Work-item identifiers appear only in the form already published here |
| Model weights, binaries, generated state, caches | None. No file in the diff is generated. `__pycache__` is already ignored and none is staged |
| Overclaimed capability | None found; see below |

### On the credential-shaped strings specifically

This change is a rejection suite for a contract whose subject matter includes
secrets, so it necessarily commits strings that *look* like credentials. Every one
was examined individually.

| String | What it is |
|---|---|
| `AKIAIOSFODNN7EXAMPLE` | The placeholder access key identifier published in AWS's own documentation. It is not an account's key and grants nothing. Widely present in public documentation for exactly this purpose |
| `ASIAIOSFODNN7EXAMPLE` | The same placeholder with the session-credential prefix, used in the heuristic's test table |
| `Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa` | A fixed synthetic string written for this change. It authenticates against nothing and exists to hold the shape the entropy branch recognises |
| `ghp_0000…`, `hf_0000…`, `glpat-0000…`, `xoxb-000…`, `sk-000…`, `AIza000…` | Prefixes followed by runs of zeroes. Each is a shape, deliberately not a plausible value |
| `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9` | The unsigned, universally published JWT header `{"alg":"HS256","typ":"JWT"}`. It carries no claim, no signature, and no subject |
| `Winter2026`, `hunter2`, `correcthorsebatterystaple` | The three documented misses. All are public examples; none is anybody's password |
| `inferops-serving/model-registry#token`, `inferops/telemetry/ingest#key` | Locators, inherited from the first pull request. The secrets they name do not exist |

The two synthetic image digests are sixty-four zeroes and sixty-four ones, written
that way so that no reader can mistake one for a pin on a published image, and
`example.invalid` is a reserved name that can never resolve.

### On what the validator's own messages can carry

The validator generates its own message text rather than passing the underlying
library's through, because the library embeds the offending value. This is the
change's one genuine security-relevant behaviour, so it is tested rather than
argued: for every invalid fixture, no finding message contains any string of eight
characters or more that appears in the document, excluding strings the schema
itself publishes as vocabulary. A second test confirms that the rendered JSON for
the credential fixture contains neither locator nor any distinctive part of one.

### On the capability claim specifically

This change makes the contract stricter, which is exactly the kind of change that
reads as more finished than it is. The wording was checked in both directions:

- The contract document opens with a section stating that a consumer validating
  against the raw schema alone **accepts documents the platform refuses**, and the
  rule matrix marks every row with its layer.
- Three rules the integration specification names remain unenforced, and they are
  listed in their own table with what each is blocked on, rather than omitted now
  that most of the table has moved to "enforced".
- The compatibility matrix's own description says format compatibility is a
  necessary condition, not a sufficient one: it cannot establish that a model fits
  in memory, that a quantisation is supported, or that an architecture is
  implemented.
- vLLM's row is marked as a recorded fallback **never executed by this project**,
  and its experimental GGUF path is deliberately absent because no trial supports
  listing it.
- `executedPairs` carries exactly one entry, tied by test to ADR 0002 and to the
  executed feasibility record.
- The credential heuristic's limits are asserted by test in both directions, and
  the document calls it a heuristic over shape rather than a proof.
- Nothing in this change claims a component reads a WorkloadContract, because
  nothing does.

### On the boundary of this pull request

The validator is contract tooling and not a platform component. It implements no
Sprint 1 domain object, no serving adapter, no API, and no Kubernetes rendering. It
reads a document, the published schema, and a published data file, and returns
findings. It is invoked by the test suite and by a person at a terminal, and by
nothing else in this repository.

## Files changed

| File | Change |
|---|---|
| `contracts/workload/examples/invalid/` (16 YAML files) | Added — one fixture per published rejection |
| `contracts/workload/examples/invalid/expected-rejections.json` | Added — the refusal each fixture must produce, and its validation layer |
| `contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json` | Added — runtime and model matrix, as data |
| `tools/contract_validation/errors.py` | Added — canonical codes, the rule registry, the finding type |
| `tools/contract_validation/workload.py` | Added — structural translation and the semantic rules |
| `tools/contract_validation/__main__.py` | Added — command-line entry point |
| `tools/contract_validation/__init__.py`, `tools/__init__.py` | Added — package surface |
| `conftest.py` | Added — makes the repository root importable, since no packaging exists |
| `tests/contracts/test_workload_contract_validation.py` | Added — the rejection suite, including the layer, leak, ordering, and single-refusal checks a second review asked for |
| `docs/proof/contracts/v1-s0-004-pr2-validation.md` | Added — this record |
| `docs/contracts/workload-contract.md` | Two-layer split, the rule matrix, conditionally compatible changes, fixture ownership, the semantic secret check, corrected rejection table |
| `contracts/workload/examples/README.md` | Invalid fixture table, layer explanation, fixture ownership |
| `contracts/README.md` | Layout, matrix entry, rules, validation commands |
| `contracts/CHANGELOG.md` | This change, with compatibility classification |
| `docs/contracts/README.md` | A compatibility matrix now exists, and how it is narrower than the specification's |
| `CONTRIBUTING.md` | Validation commands, compatibility classes, the fixture rule for new validation rules |
| `CHANGELOG.md` | Recorded the above |
| `README.md` | Entry-point description for the contract document |
| `tests/contracts/test_workload_contract_v1alpha1.py` | Docstring only — it pointed forward at work this change lands |

## What a second review changed

Three independent reviews were run over the first commit of this change: one on the
Python, one on its security posture, and one that checked every claim in this
document against the files. The security review found nothing. The other two found
seven defects between them, and all seven are fixed in the second commit.

**Two were real bugs in the validator.**

| Defect | Effect | Fix |
|---|---|---|
| The rule identifier for a property-name failure was taken from the inner JSON Schema keyword | An annotation key that was both too long and badly shaped was refused **twice**, under two different rule identifiers, with the same message under each. A published rule identifier that can arrive in pairs means less than it says | Every constraint inside a `propertyNames` subschema now maps to one rule, `value-malformed`, and identical findings are collapsed |
| An offending property name was copied verbatim into the field location | `metadata.annotations` is the contract's one open map, so its keys are as author-controlled as any value. A pasted token in a key was echoed back in full — into the one part of a finding the leak test did not check | A key is echoed only when it is short and does not itself look like a credential; otherwise the finding names the parent object. The leak test now checks the field location as well as the message |

**Three were defects in how the work reported itself.**

- A test skipped seven of its sixteen parametrized cases with a bare `return`, so
  they were counted as passed. They now call `pytest.skip`, which is why this
  record reports `191 passed, 7 skipped` rather than a single larger number.
- Findings sorted by string, so `secretRefs[10]` came before `secretRefs[2]`.
  Deterministic, and unreadable. Indices now sort as numbers.
- The two loaders returned a shared mutable dictionary from an `lru_cache`. Nothing
  mutated it, and nothing guarded against it either, in a module whose entire claim
  is determinism. Each caller now gets its own copy.

**Four were false or unsupported claims in this document and its siblings**, each
corrected in place rather than softened:

| Claim | Reality |
|---|---|
| "Six fixtures are refused only by the semantic layer" | **Seven.** Nine are structural |
| "All three mutations the previous change accepted are now refused" | **Two of three.** The third is narrowed, not closed; see the table above |
| "34 files: 5 Markdown modified, 5 Python modules added" | **35 files**, 8 Markdown modified, 6 Python modules added. The stated breakdown did not sum to its own total |
| "A rule with no fixture is refused by a test" | True for **semantic** rules only. Two structural rules have no fixture, and the contract document now names both and says why |

One further claim was credited to the test suite that only a by-hand check
supports: the command-line entry point's determinism. Nothing under `tests/`
invokes it. The table above now says so, and the by-hand result stands where it was
already recorded.

The reason this section exists is the same reason the previous change carried one.
A record that reports only what a first draft got right is not evidence; it is
advertising.

## What this change leaves undone

- **Three rules remain unenforced** — undeclared required capability, policy
  exception without owner and reason and expiry, and entitlement of a claimed
  tenant. Each is blocked on a capability or registry that does not exist, and each
  is named in the contract document's own table.
- **No consumer runs this validator.** Nothing in this repository reads a
  WorkloadContract, so the semantic layer refuses documents in tests and nowhere
  else.
- **No continuous-integration lane runs any of it.** Every check in this record was
  run by hand on one host, which is the same limitation every earlier record here
  carries.
- **The compatibility matrix is not the specification's compatibility matrix.** It
  records artifact formats and one executed pair. It records no provider project,
  provider version, or certification level, because none exists.
