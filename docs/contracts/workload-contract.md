# WorkloadContract v1alpha1

Status: **accepted contract**, at `v1alpha1` maturity. The schema, its identifier,
its compatibility rules, and its valid fixtures are published here and validated on
every change. It describes a workload; it does not deploy one. Nothing in this
repository reads a WorkloadContract yet, and this document does not claim otherwise.

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
| Tooling decision | [ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md) |

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
validation failure. The corresponding negative fixtures are the second pull
request's to add; the constraints themselves are already in the schema, and
[the tests](../../tests/contracts/test_workload_contract_v1alpha1.py) already assert
that each rejection happens.

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

**What that does not do**, stated so that nobody relies on more than exists: a
base64 blob is a valid string in that character set. The schema cannot tell a
locator from a short opaque secret that happens to look like one. Detecting that is
a semantic check with heuristics behind it, it belongs to the validator rather than
the schema, and it is the second pull request's work. Until it lands, the defence
against a pasted secret is the closed-object rule plus review — and this paragraph
exists so that the gap is visible rather than assumed away.

Secrets must not appear in logs, traces, metrics, evidence, or screenshots. Local
development should use synthetic credentials.

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

### What counts as breaking

A change is breaking when it removes or renames a required field, changes a field's
meaning or unit, narrows allowed behaviour without negotiation, changes
authentication requirements, changes default security or retention behaviour,
removes a failure mode consumers depend on, changes event type or ordering
guarantees, or makes previously valid input invalid.

### What is compatible within `v1alpha1`

- adding an optional field;
- adding a value to an enum, where the new value does not change how existing
  values behave;
- adding a new profile with its own profile block;
- relaxing a pattern or raising a bound;
- editorial changes to descriptions.

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

The platform must reject a contract that has any of the following. The right-hand
column records where the rejection happens today, so that no rule is assumed to be
enforced when it is not.

| Rejected | Canonical error | Enforced by |
|---|---|---|
| Unsupported `apiVersion` | `version-unsupported` | Schema |
| Missing owner or workload identity | `contract-invalid` | Schema |
| Unsupported profile | `contract-invalid` | Schema |
| A field the schema does not define | `contract-invalid` | Schema |
| Unsupported data classification | `contract-invalid` | Schema |
| A secret value in a value-shaped field | `contract-invalid` | Schema (no such field exists) |
| Resource-free workload | `contract-invalid` | Schema |
| Mock profile presented as real serving | `contract-invalid` | Schema |
| Replica range where minimum exceeds maximum | `contract-invalid` | **Not yet.** Validator; second pull request |
| Model and runtime combination known to be incompatible | `contract-invalid` | **Not yet.** Validator; second pull request |
| Undeclared required capability | `contract-invalid` | **Not yet.** Requires a capability registry that does not exist |
| A secret value pasted into `reference` | `contract-invalid` | **Not yet.** Validator; second pull request |
| Policy exception without owner, reason, and expiry | `contract-invalid` | **Not yet.** No policy contract exists |

Canonical error bodies carry `code`, a safe `message`, `requestId`,
`correlationId`, `retryable`, and optional `retryAfterMs` and `details`. Both codes
above are non-retryable: an invalid document does not become valid on retry.

A message must never expose a secret, an internal stack trace, a prompt, or
sensitive policy detail.

## Validation

```sh
python -m pytest tests/contracts -q
```

The suite reads only files in this repository: no network, no cluster, no model, no
clock, no randomness. It checks that the schema is a valid draft 2020-12 schema,
that every object declares its additional-property policy, that each valid fixture
validates, that fixture references resolve to real files, that the real fixture
still matches ADR 0002, that the mock cannot be edited into a real-looking contract,
and that repeated validation of the same document produces identical output.

Required packages are `jsonschema` and `pytest`, plus `PyYAML` for the authoring
form. They are not vendored; install them however your platform prefers. The
repository-wide Python and packaging toolchain is a separate decision and is not
made here.

## What this contract does not do

- **It deploys nothing.** No controller, adapter, or serving path in this
  repository reads a WorkloadContract.
- **It certifies nothing.** A valid contract is a well-formed declaration, not
  evidence that the workload it describes runs.
- **It has no consumers.** No capability descriptor, registry, or admission path
  exists to validate a `capabilityRef` against.
- **Its semantic rules are not all enforced yet.** The table above says which.
- **Its `$id` is an identifier, not a URL.** Nothing is served at
  `inferops.io`, and a validator must resolve the schema from this repository
  rather than by fetching it. That is normal for JSON Schema and is recorded here
  so that nobody plans on retrieval.
