# The workload domain model

Status: **implemented**, for `WorkloadContract v1alpha1`. This is the first
InferOps-owned code that is part of the distribution rather than repository
tooling. It turns a contract document into typed platform objects. It deploys
nothing, serves nothing, and validates nothing beyond what having a typed object
requires — the rules a document is *accepted* by are the second half of this
story and are not implemented yet.

| Property | Value |
|---|---|
| Package | [`src/inferops/domain/workload/`](../../src/inferops/domain/workload/) |
| Entry point | `inferops.domain.workload.parse_workload_contract` |
| Contract | [WorkloadContract `v1alpha1`](../contracts/workload-contract.md) |
| Supported `apiVersion` | `inferops.io/v1alpha1`, and only that |
| Runtime dependencies | None. The standard library and this distribution |
| Tests | [`tests/domain/`](../../tests/domain/), and the dependency-boundary check in [`tests/architecture/`](../../tests/architecture/) |
| Governing decisions | [ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md), [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md), [ADR 0009](../architecture/decisions/ADR-0009-python-toolchain.md) |

## What it is for

A WorkloadContract document is what an application team writes. A domain object is
what the platform reasons about. Keeping the two apart is what lets every later
component — the serving adapters, the API, the deployment rendering — be written
against one stable vocabulary instead of against a YAML shape, and be tested
without a cluster, a model, or a network.

The layer boundary is not new; it is
[ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)'s
dependency rule:

> Nothing in the platform domain may import a Kubernetes client, a Helm library, a
> serving-runtime SDK, or an HTTP framework.

Until this change that rule described a component that did not exist. It now
describes one, and it is checked from the source rather than at review time — see
[the dependency rule](#the-dependency-rule-and-how-it-is-checked) below.

## The objects

One document becomes one tree of frozen objects. The names below are the domain's;
the field names beside them are the document's.

```text
WorkloadContract           apiVersion (ContractVersion), kind
  WorkloadMetadata         name, version, owner, [description], [annotations]
  WorkloadSpec             profile, environment
    ModelReference         servingCapability, modelRef, runtimeProfile
    ResourceRequest        cpu, memory
      Accelerator          type, count
    ScalingPolicy          minimumReplicas, maximumReplicas
    Integrations           telemetry, [modelAccess], [evaluation]
      CapabilityDependency capabilityRef, required
    SecurityPolicy         dataClassification, secretRefs[]
      SecretReference      name, provider, reference, owner, rotation
    Attribution            tenant, costCenter
    EvidenceReferences     runbookRef, [proofRefs]
    SynchronousLlmProfile  runtime{imageReference}, modelArtifact{...}   <- profile
    MockLlmProfile         ciOnly, determinism, fixtureRef               <- profile
```

Everything in square brackets is optional in the contract, and is `None` on the
object when the author did not write it.

### Values, not strings

Each identifier and formatted value is its own type, and an instance of one is a
value whose format has already been checked.

| Type | Contract field | Rule |
|---|---|---|
| `DnsLabel` | `metadata.name`, `metadata.owner`, `spec.attribution.tenant`, a secret's `owner` | DNS-safe, lowercase, 1–63 characters |
| `KebabCaseName` | `modelRef`, `capabilityRef`, `costCenter`, a secret's `name` | A chosen name, same character rule |
| `WorkloadVersion` | `metadata.version` | A semantic version **or** a digest-pinned image reference, and which one it is stays readable |
| `ImageReference` | `synchronousLlm.runtime.imageReference` | Pinned by digest; a tag alone is a movable label |
| `Sha256Digest`, `UpstreamRevision` | `modelArtifact.sha256`, `.revision` | The two independent pins on the bytes |
| `RepositoryPath` | `runbookRef`, `proofRefs[]`, `fixtureRef` | Repository-relative; absolute paths and `..` traversal are excluded |
| `ResourceQuantity` | `resources.cpu`, `resources.memory` | Kubernetes units, kept as written and never converted |
| `SecretLocator` | a secret's `reference` | A locator character set, and there is no field a value could go in |
| `Description`, `AnnotationKey`, `AnnotationValue` | `metadata.description`, `metadata.annotations` | Bounded; the annotation key is namespaced |

`ResourceQuantity` is deliberately not a number. Two quantities are never compared,
added, or resolved against a node anywhere in this domain: the unit grammar is
Kubernetes', and a domain that reimplemented its arithmetic would be making a claim
about scheduling that nothing here has tested.

The controlled vocabularies — profile, environment, serving capability, runtime
profile, accelerator type, data classification, secret provider, rotation
responsibility, mock determinism — are Python enumerations with exactly the members
the schema publishes.

## Parsing, and the line it does not cross

`parse_workload_contract(document)` takes the **JSON wire form** — a mapping,
already loaded from YAML or JSON by whoever owns that — and returns a
`WorkloadContract`. It reads no files and parses no YAML: the authoring form is the
contract tooling's business, and a domain that loaded documents would be a domain
with a file system.

It enforces exactly the constraints that having a typed object requires, which is
the same line the contract document already draws between its two validation
layers:

| Enforced when parsing | Deferred to the validation pipeline |
|---|---|
| The document is an object | The profile and its block agree (`synchronous-llm` ↔ `spec.synchronousLlm`) |
| Every required field is present | `minimumReplicas` does not exceed `maximumReplicas` |
| Every value has the JSON type its field declares | Two secret entries do not share a logical name |
| No field this contract version does not define | A locator is not a pasted credential |
| Every controlled vocabulary, format, length, and bound the schema publishes | A `mock-llm` workload declares no secret |
| | The runtime and the artifact format are a registered, compatible pair |

"The JSON type its field declares" means the type as JSON Schema defines it, not as
Python spells it. `5.0` **is** an integer there — the type is decided by the value,
not by how it was written — and the validator the contract tooling uses accepts it,
so this parser accepts it too and holds it as the integer it is. Refusing it would
make the domain stricter than the contract it implements, which is the one direction
of divergence a domain object must not have. `true` is **not** an integer, even
though Python says `isinstance(True, int)`.

Everything in the right-hand column is a published **semantic** rule with a
canonical error code and a rule identifier, in
[the rejection matrix](../contracts/workload-contract.md#the-rule-matrix). None of
it is implemented in this change, and the tests say so directly rather than leaving
it to be inferred: a document with an inverted replica range parses into an object,
and a test asserts that it does. The pipeline that refuses it is `V1-S1-001-PR2`.

Two consequences of that split are worth stating plainly:

- **a parsed document is not an accepted document.** A `WorkloadContract` object is
  a document that could be read, not one the platform has agreed to act on;
- **the offline validator in [`tools/contract_validation/`](../../tools/contract_validation/)
  is still the complete published check.** It applies both layers today. The domain
  does not call it and it does not call the domain.

### The schema is copied, and the copy is checked

The domain cannot import a JSON Schema validator. `jsonschema` is a development
dependency, the distribution declares no runtime dependency at all, and a domain
object that needed a validator in order to exist would have made validation a
precondition for having a value. So every pattern, vocabulary, and bound is written
twice — once in the published schema, once in Python.

Two copies of one fact drift.
[`tests/domain/test_workload_schema_agreement.py`](../../tests/domain/test_workload_schema_agreement.py)
is why these cannot: it reads
[the schema](../../contracts/workload/workload-contract.v1alpha1.schema.json) and
fails if a single pattern, enumerated value, numeric bound, field list, or required
field disagrees with the domain — in both directions for the patterns,
vocabularies, bounds, and field lists. It also generates a sweep: every field the
schema declares *unconditionally* required is deleted from a committed fixture in
turn, and the parser has to refuse each one at that field's own address. That sweep
runs one way only, and the profile block the schema requires through a conditional
is deliberately outside it — that is a cross-field rule, and the table above says
where it belongs.

Three definitions carry a length bound in the domain that the schema does not
publish — a semantic version, a `sha256:` digest, and an upstream revision are all
bounded by their patterns instead. Those numbers are local guards rather than
published rules, and the drift test knows the difference.

## Contract-version handling

`apiVersion` is explicit on every document and is never inferred. The versions this
package implements are a constant, `SUPPORTED_CONTRACT_VERSIONS`, and today it has
exactly one entry.

The version is read **first**, and a document that declares an unsupported one — or
declares none — is refused before any field below it is read. That ordering is the
whole point: every field path this package knows is a path in `v1alpha1`, and
applying them to a `v1alpha2` document would produce complaints about a shape this
package has no claim over.

A supported version is kept as a `ContractVersion`, split into the group and the
version, rather than as the string it came from.

## Refusals

A parse answers one question — can this be read as a domain object — so it raises
on the first thing that cannot, rather than collecting findings. Collecting every
reason at once is what the validation pipeline owes an author, and it is `PR2`'s.

| Raised | When |
|---|---|
| `UnsupportedContractVersionError` | The document declares no contract version, or one this package does not implement |
| `MalformedWorkloadContractError` | The document declares a supported version and cannot be read as one |
| `InvalidValueError` | A value object was constructed directly with a value its format refuses |

Both contract errors carry a **field location** (`$.spec.security.secretRefs[1].name`),
a **reason**, and the request-scoped identifiers a caller supplied.

**No message ever repeats a value read out of the document**, and a test asserts it
over every string of eight characters or more in a refused document, excluding the
schema's own published vocabulary. The field most likely to be refused for looking
wrong is the field most likely to hold a secret, and an error is the surface most
likely to be logged, pasted into a ticket, and kept. Two consequences:

- a refused vocabulary **lists what is permitted**, because that set is the
  schema's, not the author's;
- an undefined field is **not named**. The refusal says how many undefined fields an
  object carries and which fields the version defines, and leaves the reader to
  diff two lists that are both safe to print. This parser has no credential
  heuristic — that is the semantic layer's — so it does not judge whether a field
  name is safe to echo; it declines to echo any. A consumer that needs the offending
  name located runs the published validator, whose redaction rule for exactly this
  case is measured in [the contract document](../contracts/workload-contract.md).

### Request context

The canonical error body carries a `requestId` and a `correlationId`. A parse can
carry the same two, through `RequestContext`, so that a refusal is as traceable as
a success:

```python
parse_workload_contract(
    document, context=RequestContext(request_id=..., correlation_id=...)
)
```

**The domain never generates either identifier.** The architecture assigns the
correlation identifier at the edge, before anything can fail, and nothing here runs
at an edge. A parse called with no context produces an error whose context is
empty, and empty is a state the object names rather than one a reader infers from
two `None` values.

## Nothing is dropped, and nothing is added

`WorkloadContract.as_document()` rebuilds the wire form, and a test asserts over
every committed valid fixture that it rebuilds the document it was given exactly.

That property is what makes "the domain loses nothing" checkable rather than
claimed: a field the parser forgot to read is a field missing from the rebuilt
document, and a field it defaulted is one that appears where the author wrote none.
It is fidelity of *content*, not of spelling: a replica count written `2.0` is held
as the integer it is and rebuilt as `2`, which is the same JSON value written the
ordinary way.
Absence is preserved for the same reason — an absent `proofRefs` and a declared
empty one are different documents, both comply, and a component that rendered one
as the other would be making a document say something its author did not write.

## The dependency rule, and how it is checked

[`tests/architecture/test_domain_dependency_boundary.py`](../../tests/architecture/test_domain_dependency_boundary.py)
parses every module under `src/inferops/` with the standard library's own parser
and fails if one imports anything outside the standard library and this
distribution. It is an allowlist, not a list of forbidden packages: a denylist stops
the imports somebody thought of, and the dependency rule is about everything the
domain is not, including whatever ships next year. A second check names the
forbidden families — Kubernetes clients, Helm and Terraform tooling, serving-runtime
and model SDKs, HTTP frameworks and clients — in the words ADR 0004 uses, so that a
reader sees the rule and not only its consequence.

Two further properties are checked there: the domain imports neither of its own
development dependencies (`jsonschema`, `PyYAML`), and no module under the
distribution reads a file — a domain object must be constructible from a wheel with
no repository around it.

## Validation

```sh
uv run --locked python -m pytest tests/domain -q
uv run --locked python -m pytest tests/architecture -q
uv run --locked python -m mypy
uv run --locked ruff check .
```

The domain suite reads only files in this repository: no network, no cluster, no
model, no clock, no randomness. Its evidence class is `local-static` and its
certification ceiling is `C0`, which is
[the `unit` layer](../testing/test-strategy.md) of the test strategy — registered
since `V1-S0-006` and, until this change, empty.

## What this does not do

- **It deploys nothing and serves nothing.** No controller, adapter, API, or chart
  reads a `WorkloadContract` object, because none exists.
- **It does not validate a contract.** The published rules that decide acceptance
  are the semantic layer, and this change implements none of them.
- **It is not a second validator.** Where it overlaps the schema — required fields,
  formats, closed objects — it does so because a typed object cannot be built
  without those, and the overlap is held to the schema by a test rather than
  maintained by hand.
- **It resolves no reference.** A `capabilityRef` names a capability no registry
  can resolve, a `proofRef` names a path this object does not open, and a
  `modelRef` names a catalogue entry that does not exist.
- **It checks no entitlement.** `spec.attribution.tenant` is a request, not an
  assertion. A trusted component must validate it against the owning team's
  entitlement before it is used for isolation, attribution, or authorisation, and
  nothing in this domain does that or should be read as having done it.
