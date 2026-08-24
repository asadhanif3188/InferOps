# WorkloadContract v1alpha1

Status: **accepted contract**, at `v1alpha1` maturity. The schema, its identifier,
its compatibility rules, and its valid and invalid fixtures are published here and
validated on every change. It describes a workload; it does not deploy one. Nothing
in this repository reads a WorkloadContract yet, and this document does not claim
otherwise.

| Property | Value |
|---|---|
| Schema | [`contracts/workload/workload-contract.v1alpha1.schema.json`](../../contracts/workload/workload-contract.v1alpha1.schema.json) |
| Dialect | JSON Schema draft 2020-12 |
| Schema `$id` | `https://inferops.io/contracts/workload/workload-contract.v1alpha1.schema.json` |
| `apiVersion` | `inferops.io/v1alpha1` |
| `kind` | `WorkloadContract` |
| Authoring form | YAML, restricted to the JSON-representable subset |
| Wire form | JSON |
| Unknown fields | Rejected |
| Semantic rules | [`tools/contract_validation/`](../../tools/contract_validation/) |
| Compatibility matrix | [`contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json`](../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json) |
| Tooling decision | [ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md) |

## Two layers, and why a consumer needs to know which is which

Validation happens in two layers, and the split is not an implementation detail —
it changes what a consumer gets.

| Layer | What it is | Who has it |
|---|---|---|
| **Structural** | The published JSON Schema | Anyone, in any language, by validating against the schema file |
| **Semantic** | Rules JSON Schema cannot express: comparing two sibling values, consulting a compatibility matrix, judging whether a locator is a pasted credential | Only a consumer that runs the published validator, or reimplements these rules |

[ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md)
accepted that split knowingly, and its cost is exactly this: **a consumer
validating against the raw schema alone accepts documents the platform refuses.**
The rejection matrix below marks every rule with the layer that applies it, so
which documents those are is a published fact rather than something discovered by
having one accepted.

## What it is for

A WorkloadContract is the declaration an application team writes to say what its
inference workload is, who owns it, what model it serves, what it costs, what data
it touches, and where the evidence for its claims lives. It is the input the
platform will act on, so every field in it is a field the platform is entitled to
refuse.

The design bias throughout is **refuse rather than guess**. There are no defaults
for resources, no implicit owner, no inferred environment, and no tolerance for a
field the schema does not know. That bias costs authors a little verbosity and buys
the reviewer the ability to read a contract and know it means what it says.

## Identifiers

The contract carries the platform's common identifiers. Their meaning is fixed
across every contract and telemetry surface, not redefined per document.

| Field | Identifier | Rule |
|---|---|---|
| `metadata.name` | `workload_id` | DNS-safe, lowercase, 1-63 characters, stable across releases |
| `metadata.version` | `workload_version` | Immutable: a semantic version, or an image reference pinned by digest |
| `metadata.owner` | `owner_id` | DNS-safe stable catalogue identifier; required |
| `spec.environment` | `environment` | Controlled vocabulary: `ci`, `local`, `dev`, `staging`, `production` |
| `spec.attribution.tenant` | `tenant_id` | DNS-safe; declared here, but validated or injected by a trusted component rather than trusted from this document |
| `spec.model.servingCapability` | `capability_id` | Stable identifier of the serving capability |
| `apiVersion` | `contract_version` | Explicit on every document; never inferred |

Two rules about `tenant_id` are worth stating plainly, because getting them wrong
is how multi-tenancy leaks. A tenant written into a contract is a **request**, not
an assertion. The platform must validate it against the owning team's entitlement
before it is used for isolation, attribution, or authorisation, and it must never
be trusted simply because a client supplied it.

Enum values are lowercase kebab-case. Timestamps, where later contracts carry them,
are UTC RFC 3339. Resource quantities use documented Kubernetes units.

## Structure

```text
apiVersion, kind
metadata:  name, version, owner, [description], [annotations]
spec:
  profile, environment
  model:         servingCapability, modelRef, runtimeProfile
  resources:     cpu, memory, accelerator{type, count}
  scaling:       minimumReplicas, maximumReplicas
  integrations:  telemetry{capabilityRef, required}
                 [modelAccess], [evaluation]
  security:      dataClassification, secretRefs[]
  attribution:   tenant, costCenter
  evidence:      runbookRef, [proofRefs]
  [synchronousLlm] | [mockLlm]      <- profile-specific, exactly one
```

Everything not in square brackets is required.

`resources` is required in every environment, not only production-like ones. The
specification only demands that resource-free production-like workloads be
rejected; requiring it everywhere is stricter and is deliberate, because a workload
first sized at promotion time is sized by whoever is on call that day.

`integrations.telemetry` is required for the same kind of reason: a workload the
platform cannot observe is a workload it cannot operate, and making the dependency
optional would let that fact be discovered after deployment rather than before.

### Profiles

| Profile | Status | Purpose |
|---|---|---|
| `synchronous-llm` | V1 | Real-time LLM inference against a real model |
| `mock-llm` | V1, continuous integration only | Deterministic contract tests. Never runtime proof |

Profile-specific fields live in their own block — `spec.synchronousLlm` or
`spec.mockLlm` — and never in the common section. Exactly one such block is
present, and the schema enforces which one from the value of `spec.profile`.

Later profiles named in the integration specification (`asynchronous-llm`,
`agent-runtime`) are **not** in this schema. Adding one is a compatible change, and
it will be made when the capability behind it exists rather than in advance.

### The mock profile cannot pass itself off as real serving

The rule is in [the mock and real serving boundary](../serving/mock-and-real-boundary.md).
This schema is the half of it a reviewer does not have to remember. Under
`profile: mock-llm`:

- `spec.environment` must be `ci`;
- `spec.model.servingCapability` must be `inferops-mock-serving`;
- `spec.mockLlm.ciOnly` must be `true` and `spec.mockLlm.determinism` must be
  `fixed-fixture`;
- the accelerator must be `none` with a count of `0`;
- `spec.evidence.proofRefs` is capped at **zero entries**, so a mock workload
  cannot cite real-runtime proof at all;
- `spec.synchronousLlm` must be absent.

Each of those is a structural constraint, so editing a mock fixture into something
that reads as real serving does not produce a valid contract. It produces a
validation failure.
[`mock-presented-as-real.yaml`](../../contracts/workload/examples/invalid/mock-presented-as-real.yaml)
is that edit, committed: it changes the environment, the serving capability, the
accelerator, and the proof references all at once, and every one of the four is
refused.

One further rule is semantic rather than structural. A `mock-llm` workload may not
declare a secret reference at all
([`mock-with-secret-refs.yaml`](../../contracts/workload/examples/invalid/mock-with-secret-refs.yaml)).
A fixture replayer reaches nothing that needs a credential, so a mock asking for
one is either misdescribing itself or is a continuous-integration workload pointed
at a real secret. The schema cannot see that, because the secret entry is
structurally perfect.

### The real profile is pinned to the accepted decision

`spec.synchronousLlm` requires the runtime image **by digest** and the model by
upstream revision **and** per-file content hash. A revision names what a publisher
said it published; a hash names what actually arrived. Both are required because
neither alone survives a compromised or re-pointed mirror.

[The synchronous-llm fixture](../../contracts/workload/examples/valid/synchronous-llm-local.yaml)
carries exactly the runtime digest and model revision that
[ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md) selected,
and a test fails if the two ever disagree.

## Secret references

**A contract carries references to secrets. It never carries a secret.**

Every entry in `spec.security.secretRefs` declares five things:

| Field | Why it is required |
|---|---|
| `name` | The logical name the workload consumes |
| `provider` | `kubernetes-secret`, `external-secret`, or `file-mount` |
| `reference` | Where the secret lives, as a locator |
| `owner` | Who is responsible for its contents |
| `rotation` | `platform-managed`, `owner-managed`, or `external-managed` |

`owner` and `rotation` are required because an unrotated credential is almost never
a decision anyone made. It is what happens when nobody was named.

The structural defence against a pasted value is that **every object in this schema
is closed**. There is no `value`, `data`, `password`, or `token` field to write one
into, and adding one is a schema change that goes through review. The `reference`
field is additionally constrained to a locator character set with no whitespace,
quotes, or assignment characters.

**What that does not do** is worth measuring rather than hand-waving, because the
answer is not the obvious one in either direction.

The locator character set excludes `+` and `=`, which are exactly the two
characters standard base64 uses for its 63rd symbol and its padding. Over 400
random secrets of 16-32 bytes, base64-encoded with padding, **71 passed the pattern
and 329 were rejected** — so most of a pasted base64 blob already fails today. Drop
the padding by choosing an input length that is a multiple of three and it inverts:
**279 of 400 pass**.

The larger hole is not base64 at all. **Any alphanumeric credential passes**, and
many real ones are alphanumeric by construction — an AWS access key ID and a
GitHub-style token both validate against this pattern without a character out of
place.

So the honest summary of the *pattern* is: it is a partial filter that happens to
catch padded base64, and it is no defence at all against the credential formats
most likely to be pasted.

### The semantic check that sits above it

Because the pattern cannot close that gap, a second check does, in the semantic
layer. It refuses a locator on two grounds, and neither is a proof.

| Ground | What it recognises | Rule |
|---|---|---|
| **Published prefix** | The value begins with a prefix that its issuer documents as the start of a credential — `AKIA`, `ghp_`, `xoxb-`, `glpat-`, `hf_`, `eyJ`, and around thirty more | `secret-value-in-locator` |
| **Opaque segment** | A path segment of at least 20 characters carrying mixed case, digits, and high character entropy: the shape of a string a system issued rather than a name a person chose | `secret-value-in-locator` |

The three conditions in the second row are each there to stop a specific false
positive rather than because they sounded strict. The length bound clears
`inferops-serving` and `model-registry`. The digit bound clears
`TelemetryIngestPathForServing`, which varies its case because somebody typed it
that way. The entropy bound clears names built from English-like letter
frequencies. Vault, AWS Secrets Manager, and Google Secret Manager path forms are
all in the test suite as locators that must *not* be flagged, because a check that
refuses well-formed references gets switched off within a week and then nothing is
checked at all.

**What it still does not catch, stated as a measured fact and tested as one:** a
short or low-entropy secret has the shape of a name. `Winter2026` passes.
`hunter2` passes. `correcthorsebatterystaple` passes. There is a test asserting
each of those passes, so that a future change which closes the gap has to come
here and rewrite this paragraph rather than leave it overstating the check in
either direction.

Two smaller rules complete the block. A duplicate logical name across two secret
entries is refused (`secret-ref-name-duplicated`), because the workload consumes
by name and a duplicate makes which provider it reaches undefined. And a
`mock-llm` workload may declare no secret reference at all
(`mock-secret-ref-declared`).

Secrets must not appear in logs, traces, metrics, evidence, or screenshots. Local
development should use synthetic credentials. **A validation message never
contains a value read out of the document** — it names the field and the rule and
stops there — because the field most likely to be refused for looking wrong is the
field most likely to hold a secret, and an error body is the surface most likely to
be logged, pasted into a ticket, and kept.

## Data classification

`spec.security.dataClassification` is one of `public`, `internal`, `confidential`,
or `restricted`. The vocabulary is closed. A capability that will accept a workload
must declare which of these classes it accepts and how it retains and redacts each;
no capability in this repository declares that yet, so no classification here is
currently enforced against anything downstream.

## Extension rules

There is exactly one extension point, and it is deliberately weak.

**`metadata.annotations`** takes namespaced keys — `<dns-domain>/<name>` — with
string values up to 1024 characters. Annotations are **non-normative**: the
platform must not change its behaviour because of one. They exist for provenance,
tooling hints, and human notes.

Everything else is a schema change:

- a **new normative field** goes through the contract governance process — problem
  statement, affected consumers, compatibility classification, security and
  telemetry review, valid and invalid fixtures, provider and consumer test updates,
  migration plan where applicable, an ADR for a consequential boundary change, and
  a changelog entry;
- **profile-specific fields** go in that profile's own block, never in the common
  section;
- **unknown fields are rejected.** `additionalProperties` is `false` on every
  object. The alternative — accepting unknown fields for forward compatibility —
  makes `maximumReplicas` misspelled as `maxiumumReplicas` a silent single-replica
  deployment instead of a validation error, and that trade is not worth making at
  alpha.

## Versioning and compatibility

`apiVersion` is the compatibility axis. It moves along the maturity ladder
`v1alpha1` → `v1beta1` → `v1`.

Every change to this contract falls into one of three classes. The class is stated
in the pull request, and the changelog entry records it.

### Compatible

A previously valid document stays valid, and a previously refused document is
still refused for the same reason.

- adding an optional field;
- adding a value to an enum, where the new value does not change how existing
  values behave;
- adding a new profile with its own profile block;
- relaxing a pattern or raising a bound;
- adding a runtime, an image repository, or an artifact format to the
  compatibility matrix;
- adding an invalid fixture for a rule that already exists;
- editorial changes to descriptions.

Compatible changes need a changelog entry. They do not need a new `apiVersion`.

### Conditionally compatible

A previously valid document stays valid, but something a consumer could reasonably
have depended on moves. These are the changes that get merged as harmless and are
discovered later, so they are named rather than folded into the class above.

| Change | Why it is not simply compatible |
|---|---|
| **Adding a semantic rule** that refuses a document the schema accepts | A document that validated last week is refused this week, without a schema diff to point at. Conditionally compatible only if no committed valid fixture becomes invalid |
| **Adding an entry to the compatibility matrix that narrows an existing row** — removing an accepted artifact format, or moving a repository between runtimes | A workload can become unservable without any change to its own document |
| **Changing a canonical error code, a rule identifier, or a field location** for an existing rejection | The document is refused either way, but a consumer switching on the code or quoting the rule sees different output. The published matrix is the interface here, not just the accept/refuse verdict |
| **Tightening the credential heuristic** | A locator that passed may start being refused. The gap it closes is real; the change still has to be announced rather than shipped as a fix |
| **Adding a required field with a defaulting rule** applied by the platform | Valid documents stay valid only for as long as the default holds, and the default is now load-bearing |

A conditionally compatible change requires a changelog entry that says what moved,
an updated fixture set, and — where a consumer could be relying on the old output
— a deprecation note. It does not require a new `apiVersion`.

### Breaking

A change is breaking when it removes or renames a required field, changes a field's
meaning or unit, narrows allowed behaviour without negotiation, changes
authentication requirements, changes default security or retention behaviour,
removes a failure mode consumers depend on, changes event type or ordering
guarantees, or makes previously valid input invalid.

Concretely, for this contract: removing an enum value, removing a profile, making
an optional field required without a default, and any change that invalidates a
committed valid fixture are all breaking.

### The alpha rule this project does not take

A common convention lets an alpha schema break compatibility freely, on the
argument that nobody should depend on alpha. **This contract does not adopt it.** A
breaking change requires a new `apiVersion` — `v1alpha2` — even at alpha maturity.

The reason is narrow and worth stating: the project's claim is that contracts are
enforced, and a contract that can be redefined under a stable identifier is not
enforced, it is merely written down. The cost is an extra version string on the
occasions a mistake has to be corrected. That is the cheaper of the two errors.

What `v1alpha1` *does* signal is expected churn: new versions may arrive often, and
a consumer should expect to migrate. It does not signal that a published version
will change underneath them.

### Support window

The provider supports the current and previous compatible contract versions for at
least 90 days or two provider minor releases, whichever is longer, unless a
security issue requires faster removal. A breaking change requires a migration
guide, compatibility fixtures, a deprecation notice, and consumer certification
before the old version is withdrawn.

Only one version exists today, so the window has nothing to apply to yet.

## Rejection and canonical errors

A refusal carries three things, and they are separate on purpose.

| Part | What it is for |
|---|---|
| **Canonical code** | The small public vocabulary an HTTP client switches on. It is deliberately coarse and does not grow when a rule is added |
| **Rule identifier** | Which specific rule refused the document. Stable, quotable in a review, and looked up in the matrix below |
| **Field location** | Where. A JSON-path address such as `$.spec.scaling` or `$.spec.security.secretRefs[1].name` |

Only two canonical codes are reachable from an offline document check.
`version-unsupported` means the document is well-formed for a version this
validator does not implement; `contract-invalid` means everything else. Both are
**non-retryable**: an invalid document does not become valid on retry. The wider
code vocabulary belongs to runtime surfaces that can produce it, and none exists
in this repository.

Canonical error bodies carry `code`, a safe `message`, `requestId`,
`correlationId`, `retryable`, and optional `retryAfterMs` and `details`. **A
message never contains a value read out of the document**, and a test asserts it
for every invalid fixture. A message must also never expose an internal stack
trace, a prompt, or sensitive policy detail.

### The rule matrix

Every rule this validator can cite. "Layer" is the load-bearing column: a
`structural` rule is applied by the published schema and therefore by any
consumer in any language, while a `semantic` rule is applied only by a consumer
that runs the published validator.

| Rule | Code | Layer | Refuses |
|---|---|---|---|
| `contract-version-unsupported` | `version-unsupported` | Structural | `apiVersion` names a contract version this validator does not implement |
| `field-required` | `contract-invalid` | Structural | A required field is absent — owner, workload identity, resources, telemetry, a profile block |
| `field-unknown` | `contract-invalid` | Structural | A field the contract version does not define, including a misspelled one |
| `value-not-permitted` | `contract-invalid` | Structural | A value outside a controlled vocabulary, or forbidden in this position — an unsupported profile, environment, or data classification; a mock claiming native serving |
| `value-malformed` | `contract-invalid` | Structural | A value that does not match its field's format — a non-DNS-safe identifier, an image pinned by tag, an absolute or traversing path, an unnamespaced annotation key |
| `value-out-of-range` | `contract-invalid` | Structural | A value outside a permitted length, bound, or item count — including a mock citing real-runtime proof |
| `value-wrong-type` | `contract-invalid` | Structural | A value of the wrong JSON type |
| `contract-structure-invalid` | `contract-invalid` | Structural | A structural constraint with no more specific rule. Reaching this is a signal the matrix needs a row, not a catch-all to rely on |
| `replica-range-inverted` | `contract-invalid` | Semantic | `minimumReplicas` exceeds `maximumReplicas`, so the declared range is empty |
| `secret-value-in-locator` | `contract-invalid` | Semantic | A secret reference shaped like a pasted credential rather than a locator |
| `secret-ref-name-duplicated` | `contract-invalid` | Semantic | Two secret entries declare the same logical name |
| `mock-secret-ref-declared` | `contract-invalid` | Semantic | A `mock-llm` workload declares a secret reference |
| `runtime-unregistered` | `contract-invalid` | Semantic | The runtime image repository has no entry in the compatibility matrix |
| `model-artifact-format-unknown` | `contract-invalid` | Semantic | The artifact filename ends in no format extension the matrix recognises |
| `runtime-model-incompatible` | `contract-invalid` | Semantic | The pinned runtime does not accept the pinned artifact's format |

### Rules that are still not enforced

Three rules the integration specification names remain unenforced, for the same
reason each was unenforced before: the thing they would check against does not
exist. They are listed here rather than omitted, so that no reader has to discover
from a passing validation that a rule was aspirational.

| Not enforced | Canonical error it would carry | Blocked on |
|---|---|---|
| Undeclared required capability | `contract-invalid` | No capability registry or descriptor exists to validate a `capabilityRef` against |
| Policy exception without owner, reason, and expiry | `contract-invalid` | No policy contract exists |
| A tenant claimed without entitlement | `authorization-denied` | Entitlement is not a property of the document. It must be checked by a trusted component against a source this validator does not have |

One further limit is a property of an offline check rather than a missing
capability: **a digest proves what bytes are, not that they are the right bytes.**
The validator confirms that a pinned artifact's format is one the pinned runtime
loads. It cannot confirm that the model fits in memory, that the quantisation is
supported, or that the architecture is implemented. Format compatibility is a
necessary condition, never a sufficient one, and the compatibility matrix says so
in its own description.

### Runtime and model compatibility

`runtime-unregistered` and `runtime-model-incompatible` are decided against
[the published matrix](../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json),
which is data rather than code so that adding a runtime is a reviewable diff.

| Runtime | Image repositories | Accepts | Status |
|---|---|---|---|
| `llama-cpp-server` | `ghcr.io/ggml-org/llama.cpp` | `gguf` | Selected in [ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md), and the one pair this project has executed |
| `vllm-cpu` | `docker.io/vllm/vllm-openai`, `vllm/vllm-openai-cpu` | `safetensors`, `pytorch-bin` | Recorded fallback in ADR 0002. **Never executed by this project** |
| `inferops-mock-serving` | none | none | Loads no artifact. No matrix row applies to a `mock-llm` workload |

Two things the matrix deliberately does not say. vLLM's experimental GGUF path is
**not** listed among its accepted formats, because this project has run no trial
that would let it claim that path works. And a repository absent from the table is
refused rather than assumed workable: the integration specification's rule is that
an unknown combination is unsupported until certified, and a digest that pins
uncharacterised bytes is exactly such a combination.

The `executedPairs` list in that file carries one entry — the runtime image digest
and model revision [ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md)
selected, with a link to the executed feasibility record. A test fails if that
entry ever stops matching the ADR, and a second test fails if a valid
`synchronous-llm` fixture ever pins a runtime nobody has run.

## Fixtures, and who owns which

| Set | Location | Rule |
|---|---|---|
| **Valid** | [`contracts/workload/examples/valid/`](../../contracts/workload/examples/valid/) | Every file must validate under **both** layers. Picked up automatically from `valid/*.yaml` |
| **Invalid** | [`contracts/workload/examples/invalid/`](../../contracts/workload/examples/invalid/) | Every file must be refused, for exactly the reasons recorded in the manifest beside them |
| **Expected rejections** | [`invalid/expected-rejections.json`](../../contracts/workload/examples/invalid/expected-rejections.json) | The published refusal for each invalid fixture: canonical code, rule, field, and which layer refuses |
| **Response fixtures** | [`contracts/workload/fixtures/`](../../contracts/workload/fixtures/) | Deterministic payloads a contract references. A mock payload identifies itself as a mock from its own contents |

**Ownership.** A fixture belongs to the rule it demonstrates, not to the change
that happened to add it. Three consequences follow:

- **Adding a rule adds a fixture.** A semantic rule with no invalid fixture is a
  claim, and a test refuses to let one exist.
- **Removing or weakening a rule removes its fixture in the same change**, with
  the compatibility class stated. A fixture left behind for a rule that no longer
  applies is worse than no fixture, because it still reads as coverage.
- **A valid fixture is never edited to make a change pass.** If a change would
  invalidate a committed valid fixture, the change is breaking; that is the
  definition, and the fixture is the instrument that detects it.

The manifest records each fixture's **layer**, and a test checks the claim rather
than trusting it: a fixture marked `semantic` must be *accepted* by the bare
schema. If the schema ever grows strict enough to refuse one, that is a
strengthening, a conditionally compatible change, and a manifest edit — not a
silent improvement.

Invalid fixtures contain no credential. Where one has to look like a credential to
demonstrate the check, the file uses a vendor's own published placeholder or a
fixed synthetic string, and says so in its header. Synthetic digests are written
as an obvious run of repeated digits so that no reader mistakes one for a pin on a
published image.

## Validation

```sh
python -m pytest tests/contracts -q
```

Or against an arbitrary document, including one that is not a committed fixture:

```sh
python -m tools.contract_validation path/to/workload.yaml
python -m tools.contract_validation --json path/to/workload.yaml
```

The command exits `0` when every document validates and `1` when any is refused,
and its output is sorted, so two runs over the same document are byte-identical.

The suite reads only files in this repository: no network, no cluster, no model, no
clock, no randomness. It checks that the schema is a valid draft 2020-12 schema,
that every object declares its additional-property policy, that each valid fixture
validates under both layers, that fixture references resolve to real files, that
the real fixture still matches ADR 0002, that the mock cannot be edited into a
real-looking contract, that every invalid fixture is refused with exactly the
published code, rule, and field, that no refusal message quotes a value from the
document, that every rule the validator can cite appears in this document, and
that repeated validation of the same document produces identical output.

Required packages are `jsonschema` and `pytest`, plus `PyYAML` for the authoring
form. They are not vendored; install them however your platform prefers. The
repository-wide Python and packaging toolchain is a separate decision and is not
made here.

## What this contract does not do

- **It deploys nothing.** No controller, adapter, or serving path in this
  repository reads a WorkloadContract.
- **It certifies nothing.** A valid contract is a well-formed declaration, not
  evidence that the workload it describes runs. A pair that the compatibility
  matrix accepts is a pair whose formats match, not a pair anybody has served.
- **It has no consumers.** No capability descriptor, registry, or admission path
  exists to validate a `capabilityRef` against.
- **Its rules are not all enforced.** Three remain blocked on capabilities that do
  not exist, and the table above says which.
- **Its two layers are not equally portable.** A consumer validating against the
  bare schema gets the structural half only. That is a published fact rather than
  a defect, and the rule matrix marks every row.
- **Its `$id` is an identifier, not a URL.** Nothing is served at
  `inferops.io`, and a validator must resolve the schema from this repository
  rather than by fetching it. That is normal for JSON Schema and is recorded here
  so that nobody plans on retrieval.
