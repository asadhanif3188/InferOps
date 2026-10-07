# Renderer input boundary

Status: **implemented in the platform domain** by `V2-S1-003-PR1`, with its refusals by
`V2-S1-003-PR2`. This page says what a renderer may be given, who owns each value it may
read, the precedence between those owners, how the values are gathered into one
deterministic context, and what a render is refused with when any of that fails. **One
renderer exists**: `V2-S2-001-PR1` added the [Helm values renderer](helm-values-renderer.md),
which turns a `synchronous-llm` context into the `inferops-llm` chart's values.
`V2-S1-004-PR1` added `record_release`, the one supported path from a context to a
RenderedWorkloadRelease: it builds the release in memory, from allowlisted fields only,
and writes nothing - see [Recording a release](#recording-a-release). `V2-S2-001-PR2`
added [the generated release](helm-values-renderer.md#the-generated-release), which a
caller can write to a directory it names. Nothing in this repository writes those values
to a file a release is installed with, writes to Git, or reaches a cluster, and building
a render context is not evidence that anything will. Every check behind this page is
static, at evidence level C0.

| Property | Value |
|---|---|
| Package | [`src/inferops/domain/render/`](../../src/inferops/domain/render/__init__.py) |
| Entry points | `prepare_render`, the canonical path, or its two steps `validate_for_render` and `build_render_context`; `render_with` calls a `Renderer` on the result; `record_release` builds the release a renderer records |
| Inputs | A parsed [WorkloadContract](../contracts/workload-contract.md), one set of platform defaults, and the parsed [EnvironmentBindings](../contracts/environment-binding.md) supplied together |
| Output | A `RenderContext`: 46 named values, each with its one owner and its source, and the identity and digest of every input |
| Refusal | A `RenderRefused` carrying every finding at once, each with a category, a canonical code, and a rule identifier, before any output |
| Renderer | The interface, and one implementation: `HelmValuesRenderer`, published in [the Helm values renderer](helm-values-renderer.md) |
| Tests | [`tests/domain/test_renderer_input_boundary.py`](../../tests/domain/test_renderer_input_boundary.py), [`tests/domain/test_renderer_refusals.py`](../../tests/domain/test_renderer_refusals.py), [`tests/domain/test_provenance_input_trust.py`](../../tests/domain/test_provenance_input_trust.py), and, for the renderer's own rules, [`tests/domain/test_helm_values_renderer.py`](../../tests/domain/test_helm_values_renderer.py) |
| Validation records | [`v2-s1-003-pr1-validation.md`](../proof/domain/v2-s1-003-pr1-validation.md), [`v2-s1-003-pr2-validation.md`](../proof/domain/v2-s1-003-pr2-validation.md), [`v2-s1-004-pr1-validation.md`](../proof/domain/v2-s1-004-pr1-validation.md), and [`v2-s2-001-pr1-validation.md`](../proof/domain/v2-s2-001-pr1-validation.md) |

## Why a boundary before a renderer

[The decision that opens a second version](../governance/v2-authorization.md) makes
contract-to-deployment rendering its first capability. A renderer is only as trustworthy
as what it is allowed to read: one that accepts a raw document, a contract nobody
validated, or a values file somebody edited can produce output that no input explains.
So the input side was fixed first, and tested, before anything was rendered from it. The
output - generated Helm values - is [the Helm values renderer](helm-values-renderer.md),
built against this boundary rather than beside it; binding those values to a release is
a later change.

## The path

Three steps, and each takes only what the one before it produced:

1. **`validate_for_render`** turns a parsed `WorkloadContract` into a
   `ValidatedWorkloadContract`, or refuses it with every finding at once.
2. **`build_render_context`** takes the validated contract, one `PlatformDefaults`, and the
   parsed bindings supplied together. It selects the binding that serves the contract
   with [the binding domain's own selection rule](../contracts/environment-binding.md#rejection-and-canonical-errors),
   and returns a `RenderContext`.
3. **A `Renderer`** takes that context, and nothing else. `HelmValuesRenderer` is the one
   that exists.

A raw mapping, a parsed contract that skipped step 1, and a raw defaults or binding
document are each refused at step 2 with a `TypeError`: they are programming errors, not
documents to report on.

**`prepare_render` runs steps 1 and 2 as one, for one renderer.** It takes a parsed
contract, the defaults, the bindings, and the renderer's declared `RendererSupport`, and
gathers every finding of every step - the renderer's support, the contract's rules, the
selection, and the ownership check - into one `RenderRefused`, so a caller fixes
everything in one pass rather than one refusal per run. A step that needs the selected
binding runs once there is one. `render_with` calls `prepare_render` with a renderer's own
support and calls the renderer only when nothing was found; see
[the refusals](#what-a-render-is-refused-with).

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

A `v1alpha1` set carries five settings of the platform API tier. Each was chosen because
the chart exposes it, neither the WorkloadContract nor the EnvironmentBinding has a
field for it, and the chart's default is the value every values file the repository renders
with uses - no file under `charts/inferops-llm/ci/` overrides any of them:

| Setting | Chart value it mirrors | Chart default | Bounds |
|---|---|---|---|
| `api.requestTimeoutMs` | `api.requestTimeoutMs` | 120000 | 1 to 3600000 |
| `api.drainTimeoutMs` | `api.drainTimeoutMs` | 15000 | 1 to 3600000 |
| `api.maxOutputTokens` | `api.maxOutputTokens` | 128 | 1 to 32768 |
| `api.rollout.maxUnavailable` | `api.rollout.maxUnavailable` | 0 | 0 to 16 |
| `api.rollout.maxSurge` | `api.rollout.maxSurge` | 1 | 0 to 16 |

The bounds are the chart's values schema, and a test fails if they differ. A value outside
them, a boolean, a float, or a string is refused at construction, and so is a version other
than `v1alpha1`. No attribute has a default.

The two rollout settings are the bounds of the API Deployment's rolling update, in whole
pods: how many API pods a rollout may take away before their replacements are Ready, and
how many it may add above the replica count. A percentage is a string and is refused. Two
zeros are refused at construction, and by the chart, because Kubernetes refuses a rolling
update that may neither remove a pod nor add one. The defaults allow no existing API pod
to be taken away before its replacement is available. They are a rollout policy: they do not establish what a
caller observes during a rollout, and they do not bound a pod deletion, a node loss, or an
eviction.

**The two rollout settings joined `v1alpha1` in place.** The first sets carried three
settings. No defaults file is committed at any revision, so no stored document changed its
meaning. A caller that constructs a set states the two bounds, or construction fails.

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
than discouraged: the answer to "who owns this value" has exactly one entry, and
[an input that supplies a second answer is refused](#ownership-conflicts), neither value
chosen.

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
| `api.rollout.maxUnavailable` | `platform-defaults` | `api.rollout.maxUnavailable` | yes |
| `api.rollout.maxSurge` | `platform-defaults` | `api.rollout.maxSurge` | yes |
| `destination.clusterProvider` | `environment-binding` | `spec.destination.clusterProvider` | yes |
| `destination.namespace` | `environment-binding` | `spec.destination.namespace` | yes |
| `modelCache.class` | `environment-binding` | `spec.modelCache.class` | yes |
| `modelCache.claimName` | `environment-binding` | `spec.modelCache.claimName` | yes |
| `api.replicas` | `environment-binding` | `spec.platform.apiReplicas` | yes |
| `gitops.destinationPath` | `environment-binding` | `spec.gitops.destinationPath` | yes |

That is 46 values: 35 of workload intent (21 always present, 14 present only when the
contract carries them), 5 platform defaults, and 6 environment facts. The six binding rows
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
  package, so the boundary is not wired to any delivery path. Two tools are exempt by
  name, each a repository check. Since `V2-S2-002-PR1`,
  [the drift check](helm-values-renderer.md#verifying-a-committed-release) in
  `tools/generated_release` derives the committed generated releases again and writes
  only a declared release directory in this repository. Since `V2-S2-003-PR2`, the
  [E01 runner](../proof/experiments/README.md#the-e01-static-run) in `tools/experiment_e01`
  runs the static parts of E01 and writes only a new run directory under
  `docs/proof/experiments/v2-e01/runs/`; it reads the platform defaults with the drift
  check's reader, because the freeze record names that reader. A test holds that each
  exemption is used. Since `V2-S3-002-PR1`, `tools/gitops_desired_state` is listed with
  them: it does not import the package, and it calls the drift check to derive a
  [desired-state release](../environment/git-desired-state.md). Since `V2-S3-003-PR1`,
  `tools/desired_state_provenance` is listed too: it does not import the package, and it
  names the drift check and the desired-state tool to read
  [a declared release at a Git commit](../environment/desired-state-provenance.md). It
  writes nothing. Since `V2-S3-003-PR2`, `tools/reconciliation_evidence` is listed
  too: it does not import the package, and it names the provenance tool, the
  drift check, and the desired-state tool to compare
  [what a controller reported](../environment/reconciliation-evidence.md) with a
  declared release. It writes nothing. Another reads every tracked file under `src`, `tools`, `scripts`,
  `charts`, `deploy`, `infra`, and `.github`, and `pyproject.toml`, whatever its suffix,
  and fails if any file outside the five tools names any of their packages as a whole
  word - so no module, script, chart, deployment or infrastructure file, workflow, or
  project setting reaches any of them in turn. A file inside one of the five is not read, so
  the E01 runner may name the drift check's reader.

## The renderer interface

A `Renderer` has a `revision` - the full commit it runs from, which a release records in
`source.renderer.revision` - a `support` naming the versions and profiles it takes, and a
`render` method whose one input is a `RenderContext`. It is given no contract, binding,
defaults set, raw document, path, or client: everything it may read is in the context, with
its owner. What it returns is a type parameter rather than a decision: the Helm values
renderer returns `GeneratedHelmValues`, and another renderer may return something else.
Writing that output to a GitOps destination and reconciling it into a cluster are other
components' work, and nothing here does either.

**`render_with` is the one way to call a renderer on documents.** It asks `prepare_render`
for the context with the renderer's own support, and calls `render` only when every check
has passed. A refused render never reaches the renderer, so there is no partial output to
discard, and nothing in the package writes anywhere: a test runs every rule's refusal
through it with a renderer that records its calls, and the record stays empty.

### What a renderer declares it takes

A `RendererSupport` lists the contract versions, binding versions, platform-defaults
versions, and profiles a renderer takes. An input outside any of them is refused before
the renderer is given anything: one built for today's contract cannot be assumed to render
a later version correctly, and one built for `synchronous-llm` has nothing to say about a
`mock-llm` workload. The binding's version is checked on the binding selected, not on every
binding supplied.

The declaration is the renderer's, not the domain's. It may name a version the domain does
not implement yet - a renderer built for a later contract version refuses today's
documents, which is the right outcome rather than an error in the declaration - and that
is also how the version refusals are reached in the tests, since the domain implements one
version of each input. What is refused at construction, with `InvalidValueError`, is a
declaration that cannot be meant: an empty set, a set that is not a `frozenset`, an empty
or non-string version, or a profile that is not a `Profile`. **One declaration exists in the
repository**, the Helm values renderer's `HELM_VALUES_SUPPORT`: today's three input
versions and the `synchronous-llm` profile. Every other declaration is a test's.

## What a render is refused with

A render is refused with a `RenderRefused`, carrying every finding at once. Each finding
has three parts, kept apart as [the contract's canonical error
model](../contracts/workload-contract.md#rejection-and-canonical-errors) keeps them apart,
plus where and why:

| Part | What it is for |
|---|---|
| **Category** | Which kind of refusal it is, out of the eight an operator has to tell apart. Stable, and the dimension a test or a dashboard groups by |
| **Canonical code** | The coarse public vocabulary a client switches on. It does not grow when a rule is added |
| **Rule identifier** | Which rule refused it, looked up in [the refusal matrix](#the-refusal-matrix) |
| **Field** | Where: the input by its role - `contract`, `bindings[i]` for the i-th binding supplied, `platformDefaults`, or `selection` for the caller's own request; in a renderer's own findings, `binding` for the one selected, and `manualValues` for a hand-written values file - then the path inside it |
| **Reason** | Why, in the rule's own words. It never repeats a value read out of an input |

The eight categories, in the order findings are sorted and a reader should fix them:

| Category | Code | Means |
|---|---|---|
| `version-unsupported` | `version-unsupported` | The renderer does not take the version of an input |
| `profile-unsupported` | `capability-unavailable` | The renderer was not built for the contract's profile |
| `value-unsupported` | `capability-unavailable` | The contract asks for a value or a capability the renderer's chart cannot carry. Only a renderer refuses under it, after the boundary has passed |
| `shape-invalid` | `contract-invalid` | The contract breaks a condition the published schema applies - at this boundary, only the profile conditions the domain parser does not |
| `semantic-invalid` | `contract-invalid` | The contract breaks a cross-field rule, the bindings supplied together contradict each other, or a value a renderer would write is shaped like a credential |
| `model-runtime-incompatible` | `contract-invalid` | The pinned runtime and model artifact do not go together under the compatibility matrix |
| `binding-missing` | `contract-invalid` | No single binding serving the contract could be selected |
| `ownership-conflict` | `contract-invalid` | An input supplies a value it does not own, or a hand-written values file sets a value a renderer generates |

Findings are sorted by category in that order, then by field - list indices as numbers -
then by rule. The refusal's own `code` and `category` are its first finding's, the one to
resolve first, so a renderer that does not take a contract's version answers
`version-unsupported` however much else is wrong. Every render refusal is non-retryable,
and each finding carries the request and correlation identifiers the caller supplied. The
same inputs are refused with the same findings in the same order.

**The vocabulary reuses before it adds.** A refusal that another domain already publishes
keeps that domain's rule identifier and code: the semantic pipeline's seven rules, the three
structural rules the profile conditions are refused under, and the binding domain's five set
and selection rules. A test holds each reused identifier to its publisher's - the workload
rule matrix and the binding domain's table - code for code, and holds a reused workload rule
to `shape-invalid` exactly when the matrix calls it structural. Ten rules are this package's
own, for what no other domain can see - six the boundary applies and four only the Helm
values renderer applies - and a test holds them apart from every identifier the offline
validator, the binding domain, and the release domain publish.

**Why `capability-unavailable` for a profile.** It is the first domain refusal to carry a
code beyond the two an offline document check reaches. The contract is not invalid and its
version is supported; the renderer was simply never built for that profile. The same holds
for a value or a capability the renderer's chart has no setting for, so the two
`value-unsupported` rules carry it too. The canonical
vocabulary already has the code for that case: [ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md#d8--error-mapping-and-the-counter-inferops-owns)
answers a request for streaming, a capability V1 never built, with `capability-unavailable`
and retryable `false`, and this is the same shape of refusal. A test holds every render code
inside the codes the API serves, and holds the rules that carry this one to
`render-profile-unsupported`, `render-value-unsupported`, and `render-capability-unsupported`.

**What is not a category.** Policy refusal: no policy engine exists, ADR 0010 records
`policy-denied` as a code nothing emits, and a category with no rule would claim a check
that nothing makes. A test asserts no category names one. A document that cannot be
parsed is not a render refusal either: the boundary takes parsed objects only, and each
parser refuses a malformed or unsupported-version document first, in its own vocabulary.

### The refusal matrix

Every rule a render can be refused under, in category order. "Published by" says which
vocabulary owns the identifier. Each row has an input in the tests that is refused under
exactly that rule and no other: through the canonical path for the boundary's rules, and,
for the four only the Helm values renderer applies, through `render_with` with that
renderer or through `manual_value_findings`.

| Rule | Category | Code | Published by | Refuses |
|---|---|---|---|---|
| `render-contract-version-unsupported` | `version-unsupported` | `version-unsupported` | `render` | The renderer does not take the contract's version |
| `render-binding-version-unsupported` | `version-unsupported` | `version-unsupported` | `render` | The renderer does not take the selected binding's version |
| `render-defaults-version-unsupported` | `version-unsupported` | `version-unsupported` | `render` | The renderer does not take the platform defaults' version |
| `render-profile-unsupported` | `profile-unsupported` | `capability-unavailable` | `render` | The renderer was not built for the contract's profile |
| `render-value-unsupported` | `value-unsupported` | `capability-unavailable` | `render` | An accepted value has no form the renderer's chart accepts |
| `render-capability-unsupported` | `value-unsupported` | `capability-unavailable` | `render` | The contract asks for something the renderer's chart does not provide |
| `field-required` | `shape-invalid` | `contract-invalid` | `workload-contract` | A profile's own block is absent |
| `value-not-permitted` | `shape-invalid` | `contract-invalid` | `workload-contract` | A value the schema forbids for the contract's profile |
| `value-out-of-range` | `shape-invalid` | `contract-invalid` | `workload-contract` | A mock citing proof references |
| `replica-range-inverted` | `semantic-invalid` | `contract-invalid` | `workload-contract` | The minimum replica count exceeds the maximum |
| `secret-value-in-locator` | `semantic-invalid` | `contract-invalid` | `workload-contract` | A secret reference shaped like a pasted credential |
| `secret-ref-name-duplicated` | `semantic-invalid` | `contract-invalid` | `workload-contract` | Two secret entries declare the same logical name |
| `mock-secret-ref-declared` | `semantic-invalid` | `contract-invalid` | `workload-contract` | A mock-llm workload declares a secret reference |
| `binding-identity-duplicated` | `semantic-invalid` | `contract-invalid` | `environment-binding` | Two bindings supplied together declare the same environment and name |
| `binding-destination-overlaps` | `semantic-invalid` | `contract-invalid` | `environment-binding` | Two bindings supplied together share a GitOps destination |
| `render-value-credential-shaped` | `semantic-invalid` | `contract-invalid` | `render` | A value the renderer would write has a part shaped like a published credential |
| `runtime-unregistered` | `model-runtime-incompatible` | `contract-invalid` | `workload-contract` | The runtime image has no entry in the compatibility matrix |
| `model-artifact-format-unknown` | `model-runtime-incompatible` | `contract-invalid` | `workload-contract` | The model artifact is in no format the matrix recognises |
| `runtime-model-incompatible` | `model-runtime-incompatible` | `contract-invalid` | `workload-contract` | The pinned runtime does not accept the pinned artifact's format |
| `binding-not-found` | `binding-missing` | `contract-invalid` | `environment-binding` | No binding serves the contract's environment, or none has the name asked for |
| `binding-selection-ambiguous` | `binding-missing` | `contract-invalid` | `environment-binding` | Several bindings serve the contract's environment and none was named |
| `binding-environment-mismatch` | `binding-missing` | `contract-invalid` | `environment-binding` | The binding named serves a different environment |
| `render-ownership-conflict` | `ownership-conflict` | `contract-invalid` | `render` | An input supplies a value another layer owns |
| `render-value-unowned` | `ownership-conflict` | `contract-invalid` | `render` | An input supplies a value no row of the ownership table assigns to it |
| `render-manual-value-generated` | `ownership-conflict` | `contract-invalid` | `render` | A hand-written values file sets a value the renderer generates |

The three structural rules are reached at this boundary only through the profile
conditions, which is why the matrix describes them in those terms; elsewhere they are the
offline validator's general structural rules.

## Ownership conflicts

The ownership table gives every render value one owner, and normalization reads each value
from its owner alone, so no value inside the context can be overridden. On its own that
would let a value somewhere else pass in silence: an input carrying a value it does not own
would simply not be read, and its author would believe it had taken effect. So before a
context is built, every leaf of each input's JSON form - the contract, the platform
defaults, and the selected binding - must be a value the table assigns to that input, or a
field the table leaves out of it with a reason. A leaf that is neither is refused:

- **`render-ownership-conflict`** - the leaf is a value another layer owns: its path is
  that layer's source path for it, or the value's own name. A binding carrying
  `spec.scaling.minimumReplicas` claims the workload's replica range; defaults carrying
  `api.replicas` claim the binding's API replica count. The render is refused, the finding
  names the value and its owner, and **neither value is chosen** - that is the rule against
  silent last-value-wins, applied to the inputs rather than only inside the context.
- **`render-value-unowned`** - the leaf is a value no layer owns, or an input's own value at
  a path the table does not read it from. Rendering without it would drop a value somebody
  wrote, so it is refused rather than ignored.

A leaf is any value that is not an object, an empty object included, or an object the table
names as a whole - the contract's annotations, the one open map, left out as the non-normative
extension point whatever its keys say.

**The path is the input's meaning.** The contract and the binding share three paths, and in
a binding each means the binding's own thing: `metadata.name` is the binding's name,
`metadata.owner` the team that owns its facts, and `spec.environment` the selection key,
which selection has already required to equal the contract's. A binding carrying them is a
binding, not a claim on the workload's values. A test asserts these three are the only
shared paths.

**What the tests reach, and what reaches it today.** For each of the 46 values and each of
the two layers that do not own it, an input of that layer supplying the value by its name is
refused as an ownership conflict naming the owner: 92 cases. Each of the 41 values the
contract or the binding owns is also supplied at its owner's source path from the other of
the two: 38 are refused and the three shared paths are not. **No parsed input reaches the
check today.** Each parser refuses a field its schema does not define, so a binding writing
a contract field is refused as `field-unknown` before it is a binding - [the committed
fixture](../../contracts/environment/examples/invalid/workload-intent-in-binding.yaml) shows
it - and a test walks every pairing of a committed valid contract and a binding serving it
and finds nothing. The tests reach it with inputs of the boundary's own types whose JSON
form carries one more value, which is what an input type that gained a field nobody gave an
owner - a later version, a new defaults setting - would look like. The check is what keeps
the rule on that day.

## Field-ownership matrix for the reference workload

The reference workload is `support-assistant`, the [`synchronous-llm` contract
fixture](../../contracts/workload/examples/valid/synchronous-llm-local.yaml), on the
[V1 reference environment's binding](../../contracts/environment/examples/valid/local-docker-desktop.yaml),
`local-docker-desktop`, with the chart's API defaults read at a placeholder revision. Each
row is a render value; a layer's cell is **owns** with the path the value is read from, or
`refused`: an input of that layer supplying it is refused as an ownership conflict. The last
column is the value the reference inputs give it, in the JSON form the context holds, or
`absent` where the contract leaves an optional value out and nothing fills it in.

| Value | Workload intent | Platform defaults | Environment binding | Reference value |
|---|---|---|---|---|
| `workload.id` | **owns** `metadata.name` | refused | refused | `"support-assistant"` |
| `workload.version` | **owns** `metadata.version` | refused | refused | `"0.1.0"` |
| `workload.owner` | **owns** `metadata.owner` | refused | refused | `"team-platform-demo"` |
| `workload.profile` | **owns** `spec.profile` | refused | refused | `"synchronous-llm"` |
| `workload.environment` | **owns** `spec.environment` | refused | refused | `"local"` |
| `model.servingCapability` | **owns** `spec.model.servingCapability` | refused | refused | `"inferops-native-serving"` |
| `model.ref` | **owns** `spec.model.modelRef` | refused | refused | `"qwen3-1-7b-q8-0"` |
| `model.runtimeProfile` | **owns** `spec.model.runtimeProfile` | refused | refused | `"resource-conscious"` |
| `resources.cpu` | **owns** `spec.resources.cpu` | refused | refused | `"6"` |
| `resources.memory` | **owns** `spec.resources.memory` | refused | refused | `"3Gi"` |
| `resources.accelerator.type` | **owns** `spec.resources.accelerator.type` | refused | refused | `"none"` |
| `resources.accelerator.count` | **owns** `spec.resources.accelerator.count` | refused | refused | `0` |
| `serving.replicas.minimum` | **owns** `spec.scaling.minimumReplicas` | refused | refused | `1` |
| `serving.replicas.maximum` | **owns** `spec.scaling.maximumReplicas` | refused | refused | `1` |
| `integrations.telemetry.capabilityRef` | **owns** `spec.integrations.telemetry.capabilityRef` | refused | refused | `"platform-telemetry"` |
| `integrations.telemetry.required` | **owns** `spec.integrations.telemetry.required` | refused | refused | `true` |
| `integrations.modelAccess.capabilityRef` | **owns** `spec.integrations.modelAccess.capabilityRef` | refused | refused | absent |
| `integrations.modelAccess.required` | **owns** `spec.integrations.modelAccess.required` | refused | refused | absent |
| `integrations.evaluation.capabilityRef` | **owns** `spec.integrations.evaluation.capabilityRef` | refused | refused | absent |
| `integrations.evaluation.required` | **owns** `spec.integrations.evaluation.required` | refused | refused | absent |
| `security.dataClassification` | **owns** `spec.security.dataClassification` | refused | refused | `"internal"` |
| `security.secretRefs` | **owns** `spec.security.secretRefs` | refused | refused | `[]` |
| `attribution.tenant` | **owns** `spec.attribution.tenant` | refused | refused | `"demo"` |
| `attribution.costCenter` | **owns** `spec.attribution.costCenter` | refused | refused | `"demo-cost-center"` |
| `evidence.runbookRef` | **owns** `spec.evidence.runbookRef` | refused | refused | `"docs/serving/feasibility-workflow.md"` |
| `evidence.proofRefs` | **owns** `spec.evidence.proofRefs` | refused | refused | `["docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md"]` |
| `runtime.imageReference` | **owns** `spec.synchronousLlm.runtime.imageReference` | refused | refused | `"ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"` |
| `model.artifact.repository` | **owns** `spec.synchronousLlm.modelArtifact.repository` | refused | refused | `"Qwen/Qwen3-1.7B-GGUF"` |
| `model.artifact.revision` | **owns** `spec.synchronousLlm.modelArtifact.revision` | refused | refused | `"90862c4b9d2787eaed51d12237eafdfe7c5f6077"` |
| `model.artifact.file` | **owns** `spec.synchronousLlm.modelArtifact.file` | refused | refused | `"Qwen3-1.7B-Q8_0.gguf"` |
| `model.artifact.sizeBytes` | **owns** `spec.synchronousLlm.modelArtifact.sizeBytes` | refused | refused | `1834426016` |
| `model.artifact.sha256` | **owns** `spec.synchronousLlm.modelArtifact.sha256` | refused | refused | `"sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a"` |
| `mock.ciOnly` | **owns** `spec.mockLlm.ciOnly` | refused | refused | absent |
| `mock.determinism` | **owns** `spec.mockLlm.determinism` | refused | refused | absent |
| `mock.fixtureRef` | **owns** `spec.mockLlm.fixtureRef` | refused | refused | absent |
| `api.requestTimeoutMs` | refused | **owns** `api.requestTimeoutMs` | refused | `120000` |
| `api.drainTimeoutMs` | refused | **owns** `api.drainTimeoutMs` | refused | `15000` |
| `api.maxOutputTokens` | refused | **owns** `api.maxOutputTokens` | refused | `128` |
| `api.rollout.maxUnavailable` | refused | **owns** `api.rollout.maxUnavailable` | refused | `0` |
| `api.rollout.maxSurge` | refused | **owns** `api.rollout.maxSurge` | refused | `1` |
| `destination.clusterProvider` | refused | refused | **owns** `spec.destination.clusterProvider` | `"docker-desktop"` |
| `destination.namespace` | refused | refused | **owns** `spec.destination.namespace` | `"inferops-release"` |
| `modelCache.class` | refused | refused | **owns** `spec.modelCache.class` | `"existing-claim"` |
| `modelCache.claimName` | refused | refused | **owns** `spec.modelCache.claimName` | `"inferops-model-cache"` |
| `api.replicas` | refused | refused | **owns** `spec.platform.apiReplicas` | `2` |
| `gitops.destinationPath` | refused | refused | **owns** `spec.gitops.destinationPath` | `"gitops/environments/local-docker-desktop"` |

39 values are present and 7 absent: the two optional integrations the contract does not
declare, and the mock profile's three. A test builds the context from those inputs through
the canonical path and fails if one cell of this table differs. The values are a committed
fixture's, not a deployment's: nothing was rendered from them.

## Recording a release

`record_release(render_context, *, renderer, helm_values)` is the one supported path from a
`RenderContext` to a RenderedWorkloadRelease. It takes the context, a `RendererReference`,
and a `HelmValuesReference`, and nothing else: a raw document, a dictionary, or a bare
string at any of the three, or a reference built around bare strings instead of its
constrained types, is a `TypeError`. It reads each field of the release from the
source the provenance policy names for it, reads a context value only if that value is
classified a public-safe identity - the workload's name and version, and no other - and
derives the release identifier. It reads the release back from its plain JSON form with
the published parser, so a value of the right type that skipped its check - a subclass,
or one changed with `object.__setattr__` - is refused, and then applies the release
domain's single-release rules, so a value with a part shaped like a published credential
is refused with `ReleaseNotRecordedError` before anything is returned, without quoting
it. A caller that imports the private sentinel can still build a context of well-formed
values the boundary never saw; that limit is the context's own, recorded above.

The policy - every release field and every one of the 46 context values classified as a
public-safe identity, a derived digest or revision, or excluded, each with its reason - is
published with the release, under
[Provenance input trust](../contracts/rendered-workload-release.md#provenance-input-trust),
and lives in `inferops.domain.render.recording`. It establishes what the supported path
can carry. It cannot establish that a value an author chose as a name is not a secret
written to look like one; the release document states that limit.

## What is refused, and with what

| Input | Refused with |
|---|---|
| A raw document where a contract, defaults set, binding, or support declaration belongs | `TypeError` |
| A parsed contract that did not pass `validate_for_render`, given to `build_render_context` | `TypeError` |
| An object without a revision, a support, and a render method, given to `render_with` | `TypeError` |
| A contract failing a semantic rule or a profile condition, at `validate_for_render` | `WorkloadNotAcceptedError`, every finding with its published rule identifier, non-retryable |
| The same, through `prepare_render` or `render_with` | `RenderRefused`, under the same rule identifiers, categorised |
| No binding, several and none named, a name that does not exist, a name serving another environment, or bindings that contradict each other | `RenderRefused`, under the binding domain's own rule identifiers |
| An input that supplies a value it does not own | `RenderRefused`: `render-ownership-conflict` or `render-value-unowned` |
| An input version or a profile the renderer does not declare | `RenderRefused`: a `render-*-version-unsupported` rule or `render-profile-unsupported` |
| Defaults of an unsupported version, outside the chart's bounds, or of the wrong type | `InvalidValueError` at construction |
| A support declaration that cannot be meant | `InvalidValueError` at construction |
| A raw document, a dictionary, or a string where `record_release` takes a context, a renderer reference, or a values reference | `TypeError` |
| A release the single-release rules refuse - a credential-shaped workload name, version, binding name, or values file name - or a workload version no release can hold, at `record_release` | `ReleaseNotRecordedError`, every refusal at once, non-retryable |
| A context the Helm values renderer's chart cannot carry - a value outside the chart's schema, a capability the chart does not provide, or a value it would write shaped like a credential | `RenderRefused` from the renderer, after the boundary passed: `render-value-unsupported`, `render-capability-unsupported`, or `render-value-credential-shaped` |
| A hand-written values file that sets, replaces, or removes a value the Helm values renderer generates, at `manual_value_findings` | A `render-manual-value-generated` finding per value |

### Rules that are not applied yet

Each is stated so that nobody reads the boundary as more than it is.

| Not applied | Why | What it needs |
|---|---|---|
| A policy refusal | No policy engine exists, and `policy-denied` is a code nothing emits | A policy engine, and a category with a rule |
| A contract whose version a release cannot record is refused by the render boundary | A release's workload version is narrower than a contract's. `record_release` refuses such a version when a release is recorded, since `V2-S1-004-PR1`; `prepare_render` still builds a context for it | A support rule tying a renderer to the release versions it records |
| The defaults revision names the values supplied | No defaults file exists | The change that reads the defaults from the repository |
| A binding value shaped like a lowercase credential is refused by the render boundary | The binding has no semantic credential rule, as [its document](../contracts/environment-binding.md#secrets) states. Since `V2-S1-004-PR1` the binding's name, the one binding value a release records, is refused when a release is recorded. Since `V2-S2-001-PR1` the Helm values renderer refuses any string it would write that has a credential-shaped part, whichever input supplied it - for a binding, the claim name. A binding value no renderer writes still reaches the context unchecked | A credential rule in the binding domain |

## What this does not establish

- **It writes nothing a release is installed from.** The Helm values renderer derives
  values from a context, and the package's one writer puts them and their release in a
  directory a caller names; no values file a release is installed with, no Git write,
  and no cluster change comes out of this package, and no published claim moves:
  `deployment-values-derive-only-from-a-validated-document` stays planned, because nothing
  installs generated values and no record cites them.
- **It proves nothing about an environment.** A binding selected into a context is not a
  binding whose cluster, namespace, or claim exists.
- **It does not show a conflict arriving from a real input.** No parsed input can carry
  one today; the ownership check is exercised with inputs built to carry one.
- **It declares support for one renderer.** `HELM_VALUES_SUPPORT` is the only declaration
  outside the tests.
- **Its evidence is static.** Every check runs in the default unit lane on committed files,
  at evidence level C0.

## Validation

```sh
uv run --locked python -m pytest tests/domain/test_renderer_input_boundary.py tests/domain/test_renderer_refusals.py tests/domain/test_provenance_input_trust.py tests/domain/test_helm_values_renderer.py -q
uv run --locked python -m pytest tests/domain tests/architecture -q
uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy
```
