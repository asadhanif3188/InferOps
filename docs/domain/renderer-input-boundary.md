# Renderer input boundary

Status: **implemented in the platform domain** by `V2-S1-003-PR1`. This page says what a
renderer may be given, who owns each value it may read, the precedence between those
owners, and how the values are gathered into one deterministic context. **No renderer
exists.** Nothing in this repository generates Helm values, writes a
RenderedWorkloadRelease, writes to Git, or reaches a cluster, and building a render
context is not evidence that anything will. Every check behind this page is static, at
evidence level C0.

| Property | Value |
|---|---|
| Package | [`src/inferops/domain/render/`](../../src/inferops/domain/render/__init__.py) |
| Entry points | `validate_for_render`, then `build_render_context`; a `Renderer` takes the result |
| Inputs | A parsed [WorkloadContract](../contracts/workload-contract.md), one set of platform defaults, and the parsed [EnvironmentBindings](../contracts/environment-binding.md) supplied together |
| Output | A `RenderContext`: 44 named values, each with its one owner and its source, and the identity and digest of every input |
| Renderer | An interface only; no implementation |
| Tests | [`tests/domain/test_renderer_input_boundary.py`](../../tests/domain/test_renderer_input_boundary.py) |
| Validation record | [`v2-s1-003-pr1-validation.md`](../proof/domain/v2-s1-003-pr1-validation.md) |

## Why a boundary before a renderer

[The decision that opens a second version](../governance/v2-authorization.md) makes
contract-to-deployment rendering its first capability. A renderer is only as trustworthy
as what it is allowed to read: one that accepts a raw document, a contract nobody
validated, or a values file somebody edited can produce output that no input explains.
So the input side is fixed first, and tested, before anything is rendered from it. The
output - generated Helm values beside a release - is a later change, and is built
against this boundary rather than beside it.

## The path

Three steps, and each takes only what the one before it produced:

1. **`validate_for_render`** turns a parsed `WorkloadContract` into a
   `ValidatedWorkloadContract`, or refuses it with every finding at once.
2. **`build_render_context`** takes the validated contract, one `PlatformDefaults`, and the
   parsed bindings supplied together. It selects the binding that serves the contract
   with [the binding domain's own selection rule](../contracts/environment-binding.md#rejection-and-canonical-errors),
   and returns a `RenderContext`.
3. **A `Renderer`** takes that context, and nothing else. None exists.

A raw mapping, a parsed contract that skipped step 1, and a raw defaults or binding
document are each refused at step 2 with a `TypeError`: they are programming errors, not
documents to report on.

## What validated means

`validate_for_render` applies two sets of rules and refuses the contract if either finds
anything, with every finding sorted by field and rule:

1. **The domain's semantic pipeline**, `validate_workload_contract`, unchanged: the replica
   range, the three secret rules, and the three compatibility-matrix rules. The matrix is
   whatever the caller supplied to the workload package's loader; the render package reads
   no file. A `synchronous-llm` contract with no matrix supplied raises the loader's own
   error rather than passing.
2. **The profile conditions** the published schema applies through the `allOf` under
   `spec`. The domain's parser reads whichever profile block is present, and the pipeline
   above has no rule for the pairing, so both pass all ten of the conditions below. The
   published validator refuses every one.

That second set is a gap this change measured rather than one it was told about. The
[workload domain model's](workload-domain-model.md) table lists "the profile and its block
agree" as deferred to the validation pipeline; the pipeline it names has seven rules and
this is not one of them. Nine mutations of the committed valid fixtures break the ten
conditions, the domain pipeline accepts all nine, and the published validator refuses all
nine. `validate_for_render` refuses each under the published validator's rule and at its
field, with the `$.` prefix dropped to match the pipeline's field addresses, and a test
compares the two on every mutation. Another test reads the conditions out of the schema
and fails if this list and the schema's disagree. The workload pipeline itself is
unchanged: a test asserts it still accepts all nine, so the duplicate here is removed
deliberately on the day the pipeline gains them, not left beside them.

| Profile | Field | Rule | Condition |
|---|---|---|---|
| `synchronous-llm` | `spec.synchronousLlm` | `field-required` | the synchronous-llm profile requires its own profile block |
| `synchronous-llm` | `spec` | `value-not-permitted` | the synchronous-llm profile does not permit the mock-llm profile block |
| `synchronous-llm` | `spec.model.servingCapability` | `value-not-permitted` | the synchronous-llm profile requires 'inferops-native-serving' |
| `mock-llm` | `spec.mockLlm` | `field-required` | the mock-llm profile requires its own profile block |
| `mock-llm` | `spec` | `value-not-permitted` | the mock-llm profile does not permit the synchronous-llm profile block |
| `mock-llm` | `spec.environment` | `value-not-permitted` | the mock-llm profile requires the 'ci' environment |
| `mock-llm` | `spec.model.servingCapability` | `value-not-permitted` | the mock-llm profile requires 'inferops-mock-serving' |
| `mock-llm` | `spec.resources.accelerator.type` | `value-not-permitted` | the mock-llm profile requires accelerator type 'none' |
| `mock-llm` | `spec.resources.accelerator.count` | `value-not-permitted` | the mock-llm profile requires an accelerator count of 0 |
| `mock-llm` | `spec.evidence.proofRefs` | `value-out-of-range` | the mock-llm profile permits no proof references |

**What validated does not mean.** It does not mean the offline validator ran: the domain
cannot import a JSON Schema validator, and the single-field structural constraints are the
parser's, which [the schema agreement suite](../../tests/domain/test_workload_schema_agreement.py)
holds to the schema. It does not mean a binding serves the contract, that a renderer
supports its profile, or that a release can record its version.

**The guard is against accidents, not intent.** A `ValidatedWorkloadContract` and a
`RenderContext` each refuse construction without a sentinel private to the module that
issues them, and `dataclasses.replace` cannot carry one, so no ordinary code path produces
either without passing through its function. Python has no private names: a caller who
imports the sentinel can forge one, and a test does exactly that so the limit is recorded
rather than discovered. Nothing relies on the guard as a security boundary.

## Platform defaults

A release takes workload intent from a WorkloadContract and environment facts from an
EnvironmentBinding. A third kind of input belongs to neither: a setting InferOps fixes for
every workload in every environment. `PlatformDefaults` holds one versioned set of them.

A `v1alpha1` set carries three settings of the platform API tier. Each was chosen because
the chart already exposes it, neither the WorkloadContract nor the EnvironmentBinding has a
field for it, and the chart's default is the value every values file the repository renders
with uses - no file under `charts/inferops-llm/ci/` overrides any of them:

| Setting | Chart value it mirrors | Chart default | Bounds |
|---|---|---|---|
| `api.requestTimeoutMs` | `api.requestTimeoutMs` | 120000 | 1 to 3600000 |
| `api.drainTimeoutMs` | `api.drainTimeoutMs` | 15000 | 1 to 3600000 |
| `api.maxOutputTokens` | `api.maxOutputTokens` | 128 | 1 to 32768 |

The bounds are the chart's values schema, and a test fails if they differ. A value outside
them, a boolean, a float, or a string is refused at construction, and so is a version other
than `v1alpha1`. No attribute has a default.

A set is identified by the full Git revision its values were read at, which a release
records in `source.platformDefaults.revision`. **No platform-defaults file exists yet, and
nothing reads one**: the caller constructs the object and states the revision. The API
replica count is deliberately absent: it varies by environment, and the binding's
`spec.platform.apiReplicas` owns it. A setting enters the defaults when a change needs it
rendered, not in advance.

## Who owns each value

Three layers supply render input, and they own disjoint values: **workload intent** (the
WorkloadContract, authored by the workload's owner), **platform defaults** (owned by
InferOps and versioned), and the **environment binding** selected for the contract (owned
by the platform side of the environment).

**The precedence rule is that there is none.** No layer overrides another, in either
direction: the set of pairs in which one layer may replace a value another owns,
`OVERRIDES`, is empty, and a test holds it empty. A value has one owner, the other layers
have no field to supply it from, and so there is no order in which a later value could win.
That is the rule the binding's schema already states in its shape - it has no field for a
contract value - extended to the defaults. It makes "last value wins" impossible rather
than discouraged. Detecting an attempt to supply one value from two layers, and refusing
it, is a later change; what this table fixes is that the answer to "who owns this value"
has exactly one entry.

Each name is semantic - `api.replicas`, `serving.replicas.minimum` - rather than a copied
path, so two layers claiming one meaning would claim one name. No name is another's
prefix, segment by segment. "Always present" is `yes` exactly when the owner's schema
requires the source field unconditionally; a `no` value is absent from the context when its
owner left it out, and nothing fills it in.

| Context value | Owner | Read from | Always present |
|---|---|---|---|
| `workload.id` | `workload-intent` | `metadata.name` | yes |
| `workload.version` | `workload-intent` | `metadata.version` | yes |
| `workload.owner` | `workload-intent` | `metadata.owner` | yes |
| `workload.profile` | `workload-intent` | `spec.profile` | yes |
| `workload.environment` | `workload-intent` | `spec.environment` | yes |
| `model.servingCapability` | `workload-intent` | `spec.model.servingCapability` | yes |
| `model.ref` | `workload-intent` | `spec.model.modelRef` | yes |
| `model.runtimeProfile` | `workload-intent` | `spec.model.runtimeProfile` | yes |
| `resources.cpu` | `workload-intent` | `spec.resources.cpu` | yes |
| `resources.memory` | `workload-intent` | `spec.resources.memory` | yes |
| `resources.accelerator.type` | `workload-intent` | `spec.resources.accelerator.type` | yes |
| `resources.accelerator.count` | `workload-intent` | `spec.resources.accelerator.count` | yes |
| `serving.replicas.minimum` | `workload-intent` | `spec.scaling.minimumReplicas` | yes |
| `serving.replicas.maximum` | `workload-intent` | `spec.scaling.maximumReplicas` | yes |
| `integrations.telemetry.capabilityRef` | `workload-intent` | `spec.integrations.telemetry.capabilityRef` | yes |
| `integrations.telemetry.required` | `workload-intent` | `spec.integrations.telemetry.required` | yes |
| `integrations.modelAccess.capabilityRef` | `workload-intent` | `spec.integrations.modelAccess.capabilityRef` | no |
| `integrations.modelAccess.required` | `workload-intent` | `spec.integrations.modelAccess.required` | no |
| `integrations.evaluation.capabilityRef` | `workload-intent` | `spec.integrations.evaluation.capabilityRef` | no |
| `integrations.evaluation.required` | `workload-intent` | `spec.integrations.evaluation.required` | no |
| `security.dataClassification` | `workload-intent` | `spec.security.dataClassification` | yes |
| `security.secretRefs` | `workload-intent` | `spec.security.secretRefs` | yes |
| `attribution.tenant` | `workload-intent` | `spec.attribution.tenant` | yes |
| `attribution.costCenter` | `workload-intent` | `spec.attribution.costCenter` | yes |
| `evidence.runbookRef` | `workload-intent` | `spec.evidence.runbookRef` | yes |
| `evidence.proofRefs` | `workload-intent` | `spec.evidence.proofRefs` | no |
| `runtime.imageReference` | `workload-intent` | `spec.synchronousLlm.runtime.imageReference` | no |
| `model.artifact.repository` | `workload-intent` | `spec.synchronousLlm.modelArtifact.repository` | no |
| `model.artifact.revision` | `workload-intent` | `spec.synchronousLlm.modelArtifact.revision` | no |
| `model.artifact.file` | `workload-intent` | `spec.synchronousLlm.modelArtifact.file` | no |
| `model.artifact.sizeBytes` | `workload-intent` | `spec.synchronousLlm.modelArtifact.sizeBytes` | no |
| `model.artifact.sha256` | `workload-intent` | `spec.synchronousLlm.modelArtifact.sha256` | no |
| `mock.ciOnly` | `workload-intent` | `spec.mockLlm.ciOnly` | no |
| `mock.determinism` | `workload-intent` | `spec.mockLlm.determinism` | no |
| `mock.fixtureRef` | `workload-intent` | `spec.mockLlm.fixtureRef` | no |
| `api.requestTimeoutMs` | `platform-defaults` | `api.requestTimeoutMs` | yes |
| `api.drainTimeoutMs` | `platform-defaults` | `api.drainTimeoutMs` | yes |
| `api.maxOutputTokens` | `platform-defaults` | `api.maxOutputTokens` | yes |
| `destination.clusterProvider` | `environment-binding` | `spec.destination.clusterProvider` | yes |
| `destination.namespace` | `environment-binding` | `spec.destination.namespace` | yes |
| `modelCache.class` | `environment-binding` | `spec.modelCache.class` | yes |
| `modelCache.claimName` | `environment-binding` | `spec.modelCache.claimName` | yes |
| `api.replicas` | `environment-binding` | `spec.platform.apiReplicas` | yes |
| `gitops.destinationPath` | `environment-binding` | `spec.gitops.destinationPath` | yes |

That is 44 values: 35 of workload intent (21 always present, 14 present only when the
contract carries them), 3 platform defaults, and 6 environment facts. The six binding rows
are [the binding's published ownership table](../contracts/environment-binding.md#ownership-what-a-binding-owns-and-what-it-may-not-touch)
less `spec.environment`, and each of the ten contract blocks that table says a binding may
not carry is read here as workload intent and never as a binding value. A test compares
this table with the code, and both binding tables with the binding rows.

**Fields deliberately read into no value.** Eleven, each with its reason in the code:
nine of the fields the two schemas define, and two attributes of the defaults object,
which has no schema. A test walks every field each schema defines - 39 in the
WorkloadContract's, 35 read and 4 left out, and 11 in the binding's, 6 read and 5 left
out - and fails if one is in neither list, so a field added to either schema fails the
build until somebody decides who owns it. Another does the same over the defaults
object's own fields.

| Owner | Field | Why no value is read from it |
|---|---|---|
| Workload intent | `apiVersion` | Identity of the document; the context's sources record it with the contract's digest |
| Workload intent | `kind` | Fixed for every contract |
| Workload intent | `metadata.description` | Free text for a reader, which no render setting may depend on |
| Workload intent | `metadata.annotations` | The contract's non-normative extension point; the platform must not change behaviour because of one |
| Platform defaults | `version` | The shape of the defaults, refused at construction when unsupported |
| Platform defaults | `revision` | Identity of the defaults; the context's sources record it |
| Environment binding | `apiVersion` | Identity of the document; the context's sources record it with the binding's digest |
| Environment binding | `kind` | Fixed for every binding |
| Environment binding | `metadata.name` | Identity of the binding; the context's sources record it |
| Environment binding | `metadata.owner` | The team that owns the binding's facts, which no render setting depends on |
| Environment binding | `spec.environment` | The key a binding is selected by, not a value: selection guarantees it equals the contract's, and the context takes the environment from the contract |

## The normalized render context

A `RenderContext` holds:

- **`fields`** - every value present, sorted by name, each with its owner, its source path,
  and its value in the JSON form its owner holds it, read-only: lists become tuples and
  objects become read-only mappings. Each value is read from its owner at the path the
  table names, and no other layer is consulted for it, so nothing is merged, overridden,
  or defaulted.
- **`sources`** - the contract's version and digest, the binding's version, environment,
  name, and digest, and the defaults' revision, as the
  [RenderedWorkloadRelease](../contracts/rendered-workload-release.md) records them. The
  digests are the release domain's own `contract_digest` and `binding_digest`.
  `release_source` adds a renderer revision and returns the `source` block a release from
  that renderer would carry; a test builds a release from it and the release domain's
  provenance rules find nothing to refuse.

`as_document` returns the JSON form and `digest` its SHA-256 in the release domain's
canonical JSON, so the context refuses a value with no single JSON spelling instead of
writing one.

**One limit of the sources, recorded.** A release names platform defaults by revision
alone, so two defaults sets with one revision and different values give contexts whose
sources agree, while the contexts' values and digests differ. The revision is the caller's
statement of what it read; the boundary has no file to check it against. A test asserts
the limit.

## Deterministic and pure

Building a context reads no clock, no random source, no environment variable, no file,
and no network; it runs no process and writes nothing - no Git, no `kubectl`, no Helm.
The tests assert each property directly:

- equal inputs give an equal context with the same canonical form and digest, whatever
  order the bindings were supplied in;
- two Python interpreters under two hash seeds compute the same four digests;
- with every clock, random source, and `os.getenv` patched to fail, a context is built
  and its digest is unchanged;
- a change to one input moves exactly its own value and its own source identity: a
  contract change moves its value and the contract digest, a binding change its value and
  the binding digest, a defaults change its value and nothing in the sources, and a
  defaults revision change only the sources;
- the package's absolute imports are seven standard-library modules - `__future__`,
  `collections`, `dataclasses`, `enum`, `re`, `types`, `typing` - and its relative
  imports reach only the workload, environment, and release domains and the request
  context; no module names `open`, `eval`, `exec`, `__import__`, or `importlib`;
- nothing under `src`, `tools`, `scripts`, `charts`, `deploy`, or `infra` imports the
  package, so the boundary is not wired to any delivery path.

## The renderer interface

A `Renderer` has a `revision` - the full commit it runs from, which a release records in
`source.renderer.revision` - and a `render` method whose one input is a `RenderContext`.
It is given no contract, binding, defaults set, raw document, path, or client: everything
it may read is in the context, with its owner. What it returns is a type parameter rather
than a decision, because the output is a later change. Writing that output to a GitOps
destination and reconciling it into a cluster are other components' work, and nothing
here does either.

## What is refused today, and with what

| Input | Refused with |
|---|---|
| A raw document where a contract, defaults set, or binding belongs | `TypeError` |
| A parsed contract that did not pass `validate_for_render` | `TypeError` |
| A contract failing a semantic rule or a profile condition | `WorkloadNotAcceptedError`, every finding with its published rule identifier, non-retryable |
| No binding, several and none named, a name that does not exist, or a name serving another environment | The binding domain's `BindingSelectionError`, unchanged, with its own rule identifiers |
| Defaults of an unsupported version, outside the chart's bounds, or of the wrong type | `InvalidValueError` at construction |

### Rules that are not applied yet

Each is stated so that nobody reads the boundary as more than it is.

| Not applied | Why | What it needs |
|---|---|---|
| A canonical render refusal code for each refusal above | No render refusal vocabulary exists; the refusals above use the contract, binding, and value vocabularies they already have | A later change that maps each to a stable code |
| An attempt to supply one value from two layers is refused | No layer has a field for another's value today, so no input can attempt it | Conflict detection over the ownership table, a later change |
| A profile a renderer does not support is refused | No renderer exists to support or not support one; both validated profiles reach the context | The renderer's own refusal |
| A contract whose version a release cannot record is refused | A release's workload version is narrower than a contract's, and nothing here derives a release identifier | The change that writes a release |
| The defaults revision names the values supplied | No defaults file exists | The change that reads the defaults from the repository |
| A binding value shaped like a lowercase credential is refused | The binding has no semantic credential rule, as [its document](../contracts/environment-binding.md#secrets) states | A semantic rule on bindings |
| Helm values are generated from the context | Out of this change's scope | A renderer |

## What this does not establish

- **It renders nothing.** No values file, release, Git write, or cluster change comes out
  of it, and no published claim moves:
  `deployment-values-derive-only-from-a-validated-document` stays planned, because no
  values are derived.
- **It proves nothing about an environment.** A binding selected into a context is not a
  binding whose cluster, namespace, or claim exists.
- **Its evidence is static.** Every check runs in the default unit lane on committed files,
  at evidence level C0.

## Validation

```sh
uv run --locked python -m pytest tests/domain/test_renderer_input_boundary.py -q
uv run --locked python -m pytest tests/domain tests/architecture -q
uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy
```
