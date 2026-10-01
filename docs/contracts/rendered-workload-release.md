# RenderedWorkloadRelease v1alpha1

Status: **published schema**, at `v1alpha1` maturity, added by `V2-S1-002-PR1`. The
schema, its identifier, its compatibility rules, the rule that derives a release's
identifier, and its valid and invalid fixtures are published here and validated on every
change. `V2-S1-002-PR2` added the platform domain that reads a release, the canonical form
a release and its source documents are hashed in, and [seven provenance
rules](#provenance-rules-the-platform-domain-applies) the domain applies and the schema
does not. `V2-S1-004-PR1` added the [provenance input-trust
policy](#provenance-input-trust) and the one supported path that builds a release from
validated, typed inputs. **Nothing writes a release**: no renderer exists in this
repository - [the renderer input boundary](../domain/renderer-input-boundary.md) computes
the `source` block a release records, and `record_release` builds the release in memory
and writes nothing - no values file has been generated, and neither fixture describes a
release that was rendered, installed, or run.

| Property | Value |
|---|---|
| Schema | [`contracts/release/rendered-workload-release.v1alpha1.schema.json`](../../contracts/release/rendered-workload-release.v1alpha1.schema.json) |
| Dialect | JSON Schema draft 2020-12 |
| Schema `$id` | `https://inferops.io/contracts/release/rendered-workload-release.v1alpha1.schema.json` |
| `apiVersion` | `inferops.io/v1alpha1` |
| `kind` | `RenderedWorkloadRelease` |
| Authoring form | YAML, restricted to the JSON-representable subset |
| Wire form | JSON |
| Unknown fields | Rejected |
| Validator | [`tools/contract_validation/rendered_workload_release.py`](../../tools/contract_validation/rendered_workload_release.py), structural only |
| Platform domain | [`src/inferops/domain/release/`](../../src/inferops/domain/release/__init__.py): typed parsing, the canonical form and digests, and the provenance rules |
| Fixtures | [`contracts/release/examples/`](../../contracts/release/examples/README.md) |
| Tooling decision | [ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md), applied unchanged |

## What it is for

[The decision that opens a second version](../governance/v2-authorization.md#contract-to-deployment-rendering-moves-into-v2)
makes its first capability "a validated contract rendered deterministically to the
release input a deployment consumes". Values a renderer generates are only as
trustworthy as a reader's ability to say what generated them. Generated values alone do
not say which contract, which environment facts, which renderer, or which platform
defaults they came from, and a reviewer comparing two releases cannot tell whether they
differ because an input changed or because the renderer is not deterministic.

A release is that statement, written as its own document beside the values it
describes. It names every input by an immutable identity and the output by a digest, so
a reviewer can answer, for any generated values file, which contract produced it, which
binding supplied the environment facts, which renderer revision and platform-defaults
revision were applied, and whether two releases were rendered from the same inputs.

The WorkloadContract and the EnvironmentBinding are **unchanged** by this. Their schemas,
fixtures, validators, and domain models are exactly as they were.

## A repository document, not a cluster resource

A release lives in a repository, beside the values it describes. It is **not** a
Kubernetes custom resource, and nothing about it needs one:

- **No custom resource definition** declares it, **no controller** reconciles it, and
  **no cluster** ever receives one. A test fails if any chart, manifest, or
  infrastructure file in this repository mentions the kind.
- It has **no `spec` and no `status`.** Its top-level members are `apiVersion`, `kind`,
  `metadata`, `source`, and `output`, and a test holds them to exactly that. There is no
  desired state in it to converge on and no observed state for anything to write back.
- `apiVersion` and `kind` name the schema, as they do for every contract in this
  repository. They are not a Kubernetes API group, and `inferops.io` serves nothing.

A custom resource would bring an API lifecycle, a controller, access control, upgrade
semantics, and another running component. None of them is needed to say where a release
came from, and a document in the same repository as its inputs can be reviewed in the
same change as them.

## What a release records

**What a release records.** Every field under `metadata`, `source`, and `output`:

| Field | What it records | Where the value comes from |
|---|---|---|
| `metadata.workloadId` | Which workload this is a release of | The WorkloadContract's `metadata.name` |
| `metadata.workloadVersion` | Which version of it | The WorkloadContract's `metadata.version` |
| `metadata.releaseId` | Which release this is | Derived from the fields above it and `source` — see [Release identity](#release-identity) |
| `source.contract.apiVersion` | The contract's version | The WorkloadContract's `apiVersion` |
| `source.contract.sha256` | The contract's content | A digest of the WorkloadContract document |
| `source.environmentBinding.apiVersion` | The binding's version | The EnvironmentBinding's `apiVersion` |
| `source.environmentBinding.environment` | The environment the binding serves | The EnvironmentBinding's `spec.environment` |
| `source.environmentBinding.name` | Which binding | The EnvironmentBinding's `metadata.name` |
| `source.environmentBinding.sha256` | The binding's content | A digest of the EnvironmentBinding document |
| `source.renderer.revision` | The renderer that rendered it | The full commit the renderer ran from |
| `source.platformDefaults.revision` | The platform defaults it applied | The full commit the defaults were read at |
| `output.helmValues.path` | The generated values file | Its name, in the release's own directory |
| `output.helmValues.sha256` | The generated values' content | A digest of the values file |

A binding's identity is its environment and its name together, as [its document
states](environment-binding.md#identity), so a release records both. A binding carries no
revision field — its content is identified by a digest instead — and a release is where
that digest is recorded.

**What a release does not carry.** No input's content and no output's content: not the
contract's intent, not the binding's facts, and not the generated values. Each is
referenced by a digest and nothing else, and every object is closed, so there is no field
a copy could be written into. A copy beside a digest could disagree with it, and nothing
could tell a reader which to believe;
[`invalid/document-content-in-release.yaml`](../../contracts/release/examples/invalid/document-content-in-release.yaml)
is refused for trying. A release has no owner field either: its owner is the workload's,
read from the contract it names.

## Release identity

A release's identifier is **derived, never minted.** The rule:

> `metadata.releaseId` is the SHA-256, as 64 lowercase hexadecimal characters, of the
> JSON object `{"metadata": {"workloadId": …, "workloadVersion": …}, "source": …}` built
> from the release's own values, serialised with keys sorted, no insignificant
> whitespace, non-ASCII characters written as themselves, and encoded as UTF-8.

That serialisation is the canonical JSON form the [evidence index](../../tools/evidence_index/core.py)
already hashes register entries in, reused rather than invented. Every value it covers is a
string, and every string the platform domain accepts in a release is ASCII, so the non-ASCII
clause cannot be reached through it; it is stated so that a later version with a wider
pattern inherits one serialisation rather than choosing one. (The schema's version pattern
uses `\d`, which JSON Schema reads as `[0-9]` and Python's `re` reads as any Unicode digit, so
the offline validator accepts a version with a non-ASCII digit that the domain refuses; a
test measures that difference.) What the rule gives:

- **The same inputs give the same identifier**, on any host and on every render, so two
  renders can be compared by identifier before their values are compared by digest.
- **Any change to an input gives a different identifier**: a new contract digest, another
  binding or a new digest of the same one, another renderer or platform-defaults
  revision, or another workload version.
- **The output is not an input to it.** Two releases with the same identifier and
  different `output.helmValues.sha256` were rendered from the same inputs and produced
  different values, which is the signature of a renderer that is not deterministic. Were
  the output part of the identifier, that case would look like two unrelated releases.
- **The identifier is not part of its own input**, so the rule has no fixed point to
  solve.

**The schema checks the identifier's form; the platform domain checks its derivation.**
The pattern accepts 64 lowercase hexadecimal characters and nothing else, so a UUID — the
identifier a renderer minting a fresh one per run would write — is refused, as
[`invalid/random-release-id.yaml`](../../contracts/release/examples/invalid/random-release-id.yaml)
demonstrates. A random value of the right length is not: it has the shape of a digest,
and only recomputing the rule can tell it apart. The platform domain recomputes it and
refuses a release whose identifier differs, under `release-id-not-derived`; the schema and
the offline validator do not, and a test asserts both halves, so a bare-schema consumer is
told exactly what it is not checking. Both valid fixtures carry the identifier the rule
gives, and the domain's derivation and a copy of the rule written out from this section's
words agree on each.

## Digests and revisions

| Form | Pattern | Used by |
|---|---|---|
| SHA-256 digest | 64 lowercase hexadecimal characters, no prefix | Every `sha256` field, and `metadata.releaseId` |
| Git revision | 40 lowercase hexadecimal characters | `source.renderer.revision`, `source.platformDefaults.revision` |

**One digest has one spelling.** The field name states the algorithm, so the value
carries no `sha256:` prefix; uppercase hexadecimal and any other length are refused, as
[`invalid/malformed-digests.yaml`](../../contracts/release/examples/invalid/malformed-digests.yaml)
demonstrates. Two releases are therefore comparable as text, and a digest copied from
`sha256sum` output fits without editing.

**A revision names one commit for as long as the release exists.** A branch or a tag can
be moved to another commit, and an abbreviated identifier can become ambiguous as history
grows, so all three are refused, as
[`invalid/mutable-revisions.yaml`](../../contracts/release/examples/invalid/mutable-revisions.yaml)
demonstrates. The renderer and the platform defaults each have a revision of their own,
because they can change independently: the same renderer can read an edited defaults
file, and the same defaults can be read by a changed renderer.

## Canonical form and source digests

`V2-S1-002-PR1` left open how a document is hashed. `V2-S1-002-PR2` decided it for the
two source documents, and wrote the code that applies it in
[`inferops.domain.release.canonical`](../../src/inferops/domain/release/canonical.py).

**The canonical form of a value** is its JSON text with keys sorted, no insignificant
whitespace, non-ASCII characters written as themselves, encoded as UTF-8 — the release
identifier's serialisation above, and the evidence index's, which a test holds byte for
byte. It is only canonical if another serialiser can reproduce it, so it **refuses**,
rather than writes some way of its own:

- a **float**: its text differs between serialisers, and `2.0` and `2` are one value to
  JSON Schema and two to a byte comparison. No document hashed here holds one — the
  contract and binding schemas declare integers only, and their parsers read an integral
  `2.0` as `2` before anything is hashed;
- an **integer beyond ±(2⁵³ − 1)**, which a reader holding numbers as doubles cannot
  represent exactly;
- a **date, a time, or any other value JSON has no type for**. An unquoted `2026-09-30` in
  YAML loads as a date; it is refused, not written as text, so a timestamp cannot enter a
  canonical form by an accident of quoting;
- a member name that is not a string, and a string UTF-8 cannot encode.

Nothing is normalised: two strings differing only in Unicode normalisation are two values.
A refusal names where the value is and never what it is. A pinned value's canonical bytes
and digest are held by a test, so a change to the serialisation — which would change every
identifier and digest ever recorded — fails there rather than going unnoticed.

**A source document's digest is the digest of its value, not its bytes.**
`source.contract.sha256` is the SHA-256 of the canonical form of the WorkloadContract *as
the platform domain reads it*, and `source.environmentBinding.sha256` likewise for the
binding. The digest is taken of the parsed object, so a document that does not parse has
no digest, and:

- YAML comments, key order, indentation, blank lines, flow or block style, and an integral
  `2.0` written for `2` **do not move it**, and a test holds that for every committed
  contract and binding fixture;
- **any change to any value does**, and a test changes thirteen contract values and six
  binding values, one at a time, and asserts each moves the digest, the release
  identifier, and the verdict — see [Provenance rules](#provenance-rules-the-platform-domain-applies).

The domain parses without loss, so for every committed fixture the digest equals the
canonical digest of the loaded file, and a test holds that too.

**Not decided here: how the values file is hashed.** `output.helmValues.sha256` has its
form and no rule yet. The file does not exist until a renderer writes one, and whether its
digest names its bytes or its value belongs to the story that writes it. Until then a
values digest in a release is a well-formed claim that nothing checks.

## Structure

```yaml
apiVersion: inferops.io/v1alpha1
kind: RenderedWorkloadRelease

metadata:
  workloadId: support-assistant           # the contract's metadata.name
  workloadVersion: 0.1.0                  # the contract's metadata.version
  releaseId: c10f8012e8cf…                # derived from the values below

source:
  contract:
    apiVersion: inferops.io/v1alpha1
    sha256: "1111…"                       # 64 lowercase hex
  environmentBinding:
    apiVersion: inferops.io/v1alpha1
    environment: local                    # the binding's identity is
    name: local-docker-desktop            #   environment + name
    sha256: "2222…"
  renderer:
    revision: aaaa…                       # a full 40-character commit
  platformDefaults:
    revision: bbbb…

output:
  helmValues:
    path: values.generated.yaml           # beside this document
    sha256: "3333…"
```

Every member is required, and every object is closed. A release that leaves an input out
cannot be traced back to it, and one that leaves the output unpinned cannot be compared
with another.

- **`metadata.workloadVersion`** takes the two forms a WorkloadContract's version takes,
  a semantic version or an image reference pinned by digest, with one narrowing: a
  semantic version's pre-release and build identifiers must be lowercase, and it is at
  most 128 characters. So a contract whose version is `1.0.0-RC.1` is valid and cannot be
  recorded by this version of the release; a test measures exactly that. Every committed
  contract fixture's version fits, and a test holds that too. The narrowing keeps
  uppercase credential shapes out of provenance, and relaxing it later is compatible.
- **`source.*.apiVersion`** lists the versions of the other contract this version of the
  release can record: `inferops.io/v1alpha1` for each today, and a test holds each list to
  that contract's own schema. A release naming a source version it cannot record is
  refused as `value-not-permitted`; the release's own version is supported, so it is not
  `version-unsupported`.
- **`output.helmValues.path`** is the name of a file in the directory that holds the
  release, lowercase, ending in `.yaml`. It has no directory part, so it cannot point
  outside that directory, at another release's values, or at a file on somebody's
  machine, as [`invalid/values-outside-the-release.yaml`](../../contracts/release/examples/invalid/values-outside-the-release.yaml)
  demonstrates. Where the release directory itself lives is not decided here.

## Time and randomness

**A release has no field for a timestamp.** Two renders of the same inputs at different
times must produce the same document, so there is no `generatedAt`, no render time, and
no block for either; Git history records when a release was accepted. A timestamp written
anyway is an unknown field, and the document is refused, as
[`invalid/uncontrolled-timestamp.yaml`](../../contracts/release/examples/invalid/uncontrolled-timestamp.yaml)
demonstrates. A test asserts that no property name in the schema is named for a time, and
that no string field accepts an RFC 3339 timestamp or an HTTP date.

Two places can still hold a date written as digits, and both are measured rather than
hidden: a workload identifier is a DNS label, which an all-digit string satisfies, and a
semantic version's build metadata can carry one, as in `0.1.0+20260929`. Each is a value
copied from the WorkloadContract, not one a renderer adds, so it is the same on every
render of that contract.

**A release identifier is never random**, by the [rule above](#release-identity). The
schema refuses the shape of a UUID and does not recompute the rule; the platform domain
does.

**Computing provenance reads no clock and no random source.** The domain package imports
none of `time`, `datetime`, `random`, `secrets`, `uuid`, or `os`, and names none of
`__import__`, `importlib`, `builtins`, `eval`, or `exec`, so it cannot reach one at run time
either; two tests hold that. A third replaces fourteen named clock and random functions —
among them `time.time`, `uuid.uuid4`, `os.urandom`, and `random.random` — with one that
fails, then records a release, checks it, and verifies it against its sources. That test
alone would not notice a function it does not name, such as `datetime.now`; the import
tests are what rule those out. A fourth
computes every digest and identifier for the committed fixtures in two fresh interpreters
under two different hash seeds and requires one answer. The canonical form of each valid
fixture, and of its identity, is searched for a date, a time of day, and a UUID, and holds
none.

## Provenance input trust

Added by `V2-S1-004-PR1`, on 2026-10-01. An independent review of the first V2 sprint
found that the guarantee this document gave in [Secrets](#secrets) - it opened "A release
references nothing secret and carries nothing secret" - and the guarantee the release's
story asked for were stronger than any check here proves: a lowercase value with no
published credential prefix, written as a workload name, passes every rule, and a test
already asserted that it does. This section replaces the absolute statement with the
property the code enforces, and states the rest as an assumption rather than hiding it.

**The policy.** A release may be built only from values classified as **public-safe
identities or references**, and from **derived immutable digests and revisions**, read from
validated, typed inputs. Everything else is **excluded**: it has no path into a release.
The three classes are closed - `public-identity`, `derived-digest`, and `excluded` - and
the policy is code, in
[`inferops.domain.render.recording`](../../src/inferops/domain/render/recording.py), which
tests hold to the two tables below.

The table below classifies every field a release has. No field is `excluded`: a release
has no field for excluded content to be written into, which the closed schema already
guaranteed and this table now names field by field.

| Field | Trust | Origin | Source |
|---|---|---|---|
| `apiVersion` | `public-identity` | `release` | `apiVersion` |
| `kind` | `public-identity` | `release` | `kind` |
| `metadata.workloadId` | `public-identity` | `context-value` | `workload.id` |
| `metadata.workloadVersion` | `public-identity` | `context-value` | `workload.version` |
| `metadata.releaseId` | `derived-digest` | `derivation` | `releaseId` |
| `source.contract.apiVersion` | `public-identity` | `context-source` | `contract.apiVersion` |
| `source.contract.sha256` | `derived-digest` | `context-source` | `contract.sha256` |
| `source.environmentBinding.apiVersion` | `public-identity` | `context-source` | `environmentBinding.apiVersion` |
| `source.environmentBinding.environment` | `public-identity` | `context-source` | `environmentBinding.environment` |
| `source.environmentBinding.name` | `public-identity` | `context-source` | `environmentBinding.name` |
| `source.environmentBinding.sha256` | `derived-digest` | `context-source` | `environmentBinding.sha256` |
| `source.renderer.revision` | `derived-digest` | `renderer` | `revision` |
| `source.platformDefaults.revision` | `derived-digest` | `context-source` | `platformDefaults.revision` |
| `output.helmValues.path` | `public-identity` | `helm-values` | `path` |
| `output.helmValues.sha256` | `derived-digest` | `helm-values` | `sha256` |

Origins: `release` is the release version and kind this code records; `context-value` is
a value of the render context, by its context name; `context-source` is the render
context's typed identity of an input, by its path in the release's `source`; `renderer` and
`helm-values` are the two typed references the caller supplies; `derivation` is the
[release identity rule](#release-identity).

The table below classifies every value of the render context.

| Trust | Why | Render context values |
|---|---|---|
| `public-identity` | the workload's identity, which a release records: public by policy | `workload.id`, `workload.version` |
| `excluded` | who owns or pays for the workload; it identifies an organisation, not a release, and the contract digest covers it | `workload.owner`, `attribution.tenant`, `attribution.costCenter` |
| `excluded` | a render setting the contract declares, not an identity; the contract digest covers it | `workload.profile`, `workload.environment`, `model.servingCapability`, `model.runtimeProfile`, `resources.cpu`, `resources.memory`, `resources.accelerator.type`, `resources.accelerator.count`, `serving.replicas.minimum`, `serving.replicas.maximum`, `integrations.telemetry.required`, `integrations.modelAccess.required`, `integrations.evaluation.required`, `security.dataClassification`, `model.artifact.sizeBytes`, `mock.ciOnly`, `mock.determinism` |
| `excluded` | a reference to another artifact the contract cites, not an identity of this release; the contract digest covers it | `model.ref`, `integrations.telemetry.capabilityRef`, `integrations.modelAccess.capabilityRef`, `integrations.evaluation.capabilityRef`, `evidence.runbookRef`, `evidence.proofRefs`, `runtime.imageReference`, `model.artifact.repository`, `model.artifact.revision`, `model.artifact.file`, `model.artifact.sha256`, `mock.fixtureRef` |
| `excluded` | sensitive: names the secrets the workload reads; a reference is not a value, and provenance carries neither | `security.secretRefs` |
| `excluded` | a platform default, not an identity; the platform-defaults revision covers it | `api.requestTimeoutMs`, `api.drainTimeoutMs`, `api.maxOutputTokens` |
| `excluded` | a fact of one environment, not an identity; the binding digest covers it, and the binding is recorded by name | `destination.clusterProvider`, `destination.namespace`, `modelCache.class`, `modelCache.claimName`, `api.replicas`, `gitops.destinationPath` |

Members of the contract and the binding that the render context does not hold at all - a
contract's `description` and `annotations`, a binding's `owner`, and the rest of
[the fields the boundary leaves out](../domain/renderer-input-boundary.md#who-owns-each-value) -
cannot be read by the supported path, because its only document-derived input is the
context.

**The supported path, and what it enforces.** `record_release(render_context, *,
renderer, helm_values)` in [the render package](../domain/renderer-input-boundary.md#recording-a-release)
is the one function that builds a release from inputs; the parser reads a release
someone else wrote and builds none. On that path:

- **Only typed inputs cross.** It takes a `RenderContext` - which only `build_render_context`
  and `prepare_render` issue, from a validated contract, typed platform defaults, and a
  selected binding - a `RendererReference`, and a `HelmValuesReference` whose members are
  their constrained types. A raw document, a dictionary, or a bare string at any of the
  three, or a reference built around bare strings, is refused with a `TypeError`.
- **Each field is read from the source its row names, and from nothing else.** A context
  value is read only if it is classified `public-identity`, and both tables are consulted
  when a release is recorded, so a row pointed at an excluded value, or a value
  reclassified, is refused rather than recorded. The function's body reaches the context
  only through that reader and the context's typed sources, and a test reads the body to
  hold it there.
- **Excluded content cannot enter.** No secret reference, free text, annotation, owner,
  render setting, environment fact, environment variable, prompt, response, or other
  document member has a path into a release. The suite gives every excluded context value
  a distinct marker and finds none in the recorded release, and finds none of eight
  markers planted in real inputs' free text, secret references, owners, and environment
  facts; the same check, run with a path opened on purpose, does find its marker.
  Recording reads no environment variable: the module imports nothing that could, and a
  release is recorded with the process environment made unreadable.
- **Known credential shapes stay refused.** The release is judged by the single-release
  rules before it is returned. A workload name, workload version, binding name, or values
  file name with a part that begins with a published credential prefix is refused with
  `ReleaseNotRecordedError`, carrying every refusal and quoting none. That includes a
  binding named so, which the render boundary still accepts. A workload version no release
  can hold - an uppercase pre-release - is refused the same way.

**What it cannot establish - the input-trust limitation.** The four `public-identity`
fields an author chooses - the workload's name and version, the binding's name, and the
values file name - are public **by policy**: whoever names a workload or a binding is
publishing a name. A secret deliberately written as an otherwise valid name has exactly
a name's shape, and an arbitrary value of that shape cannot be proven non-secret by
syntax alone; the credential rule recognises published formats and nothing more. A test
records a release whose workload name is a lowercase token with no published prefix, and
asserts it passes. The same holds for the three hexadecimal values a caller supplies - the
renderer and platform-defaults revisions and the values digest - which have their shape
checked and nothing else, so a secret that is itself a hexadecimal string of that length
would pass. The two source digests are computed, not supplied: each is a one-way digest of
a whole parsed document, excluded members included, and is not a copy of any of them.

**This is not repository secret scanning.** Secret scanning runs a scanner over committed
files and history, against known secret formats, and is configured in `.gitleaks.toml`
with [its allowlist](../../.github/secret-scanning-allowlist.md). This policy decides what a
release can be built from, before any file exists. Neither stands in for the other: a
scan passing does not show that a name is not a disguised secret, and this policy says
nothing about a file that bypasses the supported path.

**Still open, and whose it is.** The render boundary hands a binding whose values are
shaped like a credential to a renderer: provenance refuses its name when a release is
recorded, and every other binding value is excluded from provenance, but whether
generated output may carry such a value belongs to the change that generates values. The
renderer revision, platform-defaults revision, and values digest are still checked for
nothing beyond their form, as [the rules not applied yet](#rules-that-are-not-applied-yet)
state.

## Secrets

**A release has no field for a secret, and its supported path records only what the
[provenance input-trust policy](#provenance-input-trust) classifies public or derived.**
Provenance names its inputs and its output, and needs no secret reference. This section
opened with "A release references nothing secret and carries nothing secret" until
`V2-S1-004-PR1`, which replaced it: no check here can prove the second half for a value an
author chose, and the policy section says exactly where the guarantee stops. Two things
make the absence of a secret *field* structural rather than a promise:

1. **Every object is closed.** A `token`, `password`, or `credentials` field is an unknown
   field and the document is refused, as
   [`invalid/secret-value-in-a-field.yaml`](../../contracts/release/examples/invalid/secret-value-in-a-field.yaml)
   demonstrates.
2. **Every string is a lowercase identifier, a lowercase version, a lowercase file name,
   lowercase hexadecimal of a fixed length, or a member of a closed vocabulary.** There is
   no free-text field, not even a description, so uppercase letters, whitespace, and
   assignment characters are refused wherever a string can be written, and underscores
   everywhere except inside a digest-pinned image reference's path. That excludes most of
   the shapes a pasted credential takes — an AWS key identifier, a JSON Web Token, an
   opaque mixed-case string, a GitHub or Hugging Face token as a whole value, and any of
   those behind a version's pre-release separator — as
   [`invalid/secret-value-in-an-identifier.yaml`](../../contracts/release/examples/invalid/secret-value-in-an-identifier.yaml)
   demonstrates.

**What the schema does not catch, measured rather than hedged.** A credential written only
in lowercase letters, digits, and hyphens has the shape of a name. Tokens in formats that
begin `sk-`, `glpat-`, `gldt-`, or `xoxb-` and continue in lowercase and digits are
accepted by the schema in `metadata.workloadId`, `source.environmentBinding.name`, and
`output.helmValues.path` (before its `.yaml`), and as the pre-release part of
`metadata.workloadVersion`. The WorkloadContract's credential heuristic tests for a
published prefix at the start of a value, so it would catch one that begins an identifier
or a file name and would miss one behind a version's `-`. **The schema and the offline
validator apply neither half**, and a test asserts every one of those outcomes. The same
holds for a workload version in its other form, a digest-pinned image reference: its path
admits lowercase letters, digits, `.`, `_`, and `-`, so a lowercase token in a format that
begins `ghp_`, `hf_`, `npm_`, `sk_live_`, or any other lowercase published prefix can be
written as a segment of it. `V2-S1-002-PR1`'s version of this section said underscores were
refused wherever a string can be written; that was true of every field except that one, and
was corrected when this change found it.

**The platform domain refuses them**, under `release-value-credential-shaped`. It applies
the WorkloadContract heuristic's published prefixes, unchanged, at the start of each of
those four values *and after every separator in it* — `-`, `_`, `.`, `+`, `/`, `@`, and `:`,
which are every punctuation character any accepted form admits, and a test finds that set
by asking each form's own type — so a token behind a version's pre-release or build
separator, inside an image reference's path, or after an identifier's hyphen, is seen as
well as one that begins a value. Every lowercase published prefix — twenty-five of the
heuristic's forty — can be written in some release field: the nine built from letters,
digits, a hyphen, or a dot (`gldt-`, `glpat-`, `sk-`, the five `xox?-` forms, and `ya29.`) in
several, and the sixteen with an underscore only inside an image reference's path. A test
places each in every position and asserts the rule refuses it, and that no committed
contract, binding, or values name is mistaken for one. Every prefix contains a character
outside `0-9a-f`, so no hexadecimal field can hold one.

**What the rule costs, and what it still misses.** A value with a part that begins `sk-` is
refused even when nobody meant a credential: a WorkloadContract named `sk-demo` or
`task-sk-demo` is valid, and no release of it can be recorded; a test measures both. A
lowercase token with no published prefix still has the shape of a name, and the
heuristic's other branch needs mixed case, which no release string can hold — so a token
like that passes, and a test asserts it does. The six hexadecimal fields cannot refuse a
credential that is itself lowercase hexadecimal of the same length: such a value has
exactly a digest's or a revision's shape. The two source digests are now checked when a
caller supplies the documents they name, which catches such a value there; the values
digest and the two revisions are not, and a release is reviewed like any other file for
what they could hide.

A refusal never repeats a value from the document, in its message or its field location.
That is the canonical error model's rule and the release inherits it unchanged.

## Versioning and compatibility

`apiVersion` and `kind` together are the compatibility axis — three contracts now share
`inferops.io/v1alpha1`, and each is versioned independently — and the classes are the
WorkloadContract's, applied to this schema:

- **Compatible** — adding an optional field; adding a value to an enum where existing
  values behave as before, such as a second contract or binding version a release can
  record once that version exists; relaxing a pattern or raising a bound, such as
  admitting uppercase in a version; adding an invalid fixture for an existing rule;
  editorial changes to descriptions.
- **Conditionally compatible** — adding a semantic rule that refuses a document the
  schema accepts, including recomputing the release identifier or applying a credential
  heuristic; changing a canonical code, rule identifier, or field location for an
  existing rejection. A previously valid release stays valid unless a committed valid
  fixture says otherwise, but what a consumer is told moves. `V2-S1-002-PR2` made changes
  of this class, and only in the platform domain: it recomputes the release identifier
  and applies a credential rule, and neither committed valid fixture is refused by either.
  The schema and the offline validator's verdicts did not move.
- **Breaking** — adding a required field; removing or renaming a field; removing an enum
  value; narrowing a pattern or a bound so that a committed valid fixture fails; changing
  the derivation rule, because every existing identifier would then name a different
  release; and any field that lets a release carry a timestamp, a random value, or the
  content of a document it references. The last is breaking even though it would accept
  more documents, because it breaks the guarantee the artifact exists to give.

A breaking change requires a new `apiVersion`, even at alpha maturity — the same rule
[the WorkloadContract takes](workload-contract.md#the-alpha-rule-this-project-does-not-take),
for the same reason. Only one release version exists, so the support window has nothing
to apply to yet.

## Rejection and canonical errors

A release is refused through the canonical error model the WorkloadContract uses: the
same two codes, the same structural rule identifiers, the same field locations, and the
same messages. The offline validator added no code and no rule identifier. The table below is every rule the offline validator can refuse a release under.

| Rule | Code | Layer | Refuses, for a release |
|---|---|---|---|
| `contract-version-unsupported` | `version-unsupported` | Structural | `apiVersion` names a release version this validator does not implement |
| `field-required` | `contract-invalid` | Structural | A required field is absent — a release identifier, a whole input, a digest |
| `field-unknown` | `contract-invalid` | Structural | A field the release does not define — a timestamp, a copy of a document, a credential field |
| `value-not-permitted` | `contract-invalid` | Structural | A value outside a controlled vocabulary — a source version, an environment — a `kind` naming another contract, or a workload version matching neither accepted form |
| `value-malformed` | `contract-invalid` | Structural | A value that does not match its field's format — a digest in another spelling, a movable revision, a UUID as a release identifier, a non-DNS-safe identifier, a values path with a directory |
| `value-out-of-range` | `contract-invalid` | Structural | A value outside a permitted length — an identifier longer than a DNS label |
| `value-wrong-type` | `contract-invalid` | Structural | A value of the wrong JSON type — an unquoted digest YAML read as a number, a revision written as a list |
| `contract-structure-invalid` | `contract-invalid` | Structural | A structural constraint with no more specific rule. Reaching it means the translation table needs a row |

Every rule in that table is structural, so **a consumer validating a release against the
bare schema file reaches the same verdict as the published validator** on every committed
fixture. Neither applies the rules in the next section, which the platform domain applies
and a test holds apart from the validator's.

Seven of the eight rules have an invalid fixture demonstrating them. The eighth,
`contract-structure-invalid`, is the fallback for a keyword the translation table does
not map, and a fixture pinning it would pin a defect. A test asserts that it is the only
rule without one.

### Provenance rules the platform domain applies

A release the schema accepts can still say something false. [The platform
domain](../../src/inferops/domain/release/provenance.py) decides that with two functions:
`check_rendered_workload_release`, which judges one parsed release, and
`verify_release_sources`, which compares a parsed release with the parsed WorkloadContract
and EnvironmentBinding it names. Each returns every refusal at once, sorted, and raises
none; each refuses a raw document with a `TypeError`, because a rule applied to a document
nobody parsed is applied to an unknown shape. The table below is every rule the platform domain applies to a release.

| Rule | Code | Applied by | Refuses |
|---|---|---|---|
| `release-id-not-derived` | `contract-invalid` | One release | `metadata.releaseId` is not the identifier [the derivation rule](#release-identity) gives for the release's own workload identity and `source` |
| `release-value-credential-shaped` | `contract-invalid` | One release | The workload identifier, workload version, binding name, or values file name has a part that begins with a published credential prefix; see [Secrets](#secrets) |
| `release-contract-mismatch` | `contract-invalid` | Release and sources | The workload identifier, workload version, or contract version is not the contract's `metadata.name`, `metadata.version`, or `apiVersion` |
| `release-contract-digest-mismatch` | `contract-invalid` | Release and sources | `source.contract.sha256` is not [the contract's digest](#canonical-form-and-source-digests): the contract changed after the release was recorded, or it is another contract |
| `release-binding-mismatch` | `contract-invalid` | Release and sources | The binding version, environment, or name is not the binding's `apiVersion`, `spec.environment`, or `metadata.name` |
| `release-binding-digest-mismatch` | `contract-invalid` | Release and sources | `source.environmentBinding.sha256` is not the binding's digest |
| `release-environment-mismatch` | `contract-invalid` | Release and sources | The contract and the binding serve different environments, so no release can have been rendered from the two together |

No canonical code was added, and no identifier is one the offline validator or the binding
domain already uses; a test holds both, holds this table to the code, and provokes every
rule. A refusal's field names the document by its role — `release` or `contract` — and the
path inside it, and never repeats a value. These rules are not in the offline validator's
rule table: that table is what a bare-schema consumer can reproduce, and these need either
a recomputation or a second document.

Two of the comparisons cannot fire today, and the rules are stated for when they can: a
release can record exactly one contract version and one binding version, and the domain
reads exactly those, so the two `apiVersion` halves of `release-contract-mismatch` and
`release-binding-mismatch` have nothing to disagree about until a second version exists
on either side. A test asserts that each list has one member.

**What a source change moves.** A test changes each member of a release's workload
identity and `source` that can change, one at a time, and asserts each moves the release
identifier and that the recorded one is then refused as `release-id-not-derived`; it
changes each member of `output` and asserts the release's canonical form moves and its
identifier does not. It then changes thirteen claim-relevant contract values — owner,
description, model reference, runtime profile, CPU, memory, maximum replicas, whether
telemetry is required, data classification, cost centre, runtime image, model revision,
and model artifact digest — and six binding values —
owner, provider, namespace, model cache claim, API replicas, and GitOps destination — one
at a time. Each moves the document's digest and the release identifier, a release recorded
before the change is refused against the changed document with exactly one
`release-contract-digest-mismatch` or `release-binding-digest-mismatch`, and a release
recorded after it verifies.

**Neither committed valid fixture is a record of the documents it names.** Their digests
are placeholders, so each passes `check_rendered_workload_release` and is refused by
`verify_release_sources` with exactly the two digest rules — which a test asserts, so the
fixtures cannot be read as the record of a render.

### Rules that are not applied yet

Each of these needs a file, a repository, or code that does not exist, and nothing
applies any of them today. They are stated so that nobody reads the domain as more than it
is.

| Rule | Why it is not applied | What it needs |
|---|---|---|
| `output.helmValues.sha256` is the digest of the values file it names | How a values file is hashed is not decided, and no values file exists | The code that writes values, and the rule for hashing them |
| The values file exists beside the release | A document check cannot see a directory | The renderer's output check |
| The renderer and platform-defaults revisions name commits that exist | A document check has no repository | A check against the repository the release is committed in |
| A lowercase credential with no published prefix is refused | It has the shape of a name, and the heuristic's other branch needs mixed case; see [Secrets](#secrets). Since `V2-S1-004-PR1` this is stated as the policy's [input-trust limitation](#provenance-input-trust), not a pending rule: no rule over syntax can close it | Nothing syntactic: identities are public by policy, and a test asserts the gap on the supported path too |
| A release committed to the repository matches what its sources derive today | Nothing commits a release | The generated-artifact drift check |

## Fixtures

Two valid and fifteen invalid fixtures, described in
[their own README](../../contracts/release/examples/README.md). The valid fixtures name
the committed synchronous WorkloadContract fixture and each committed EnvironmentBinding
fixture, which a test holds, and carry the release identifier the rule derives, which a
test recomputes. Their digests and revisions are single repeated characters that name
nothing, and a test holds that too, so neither can be mistaken for a record of a render.
They are contract examples: neither is evidence that a release was rendered, installed,
or run.

## Validation

```sh
python -m pytest tests/contracts/test_rendered_workload_release_v1alpha1.py tests/domain/test_rendered_workload_release_domain.py tests/domain/test_provenance_input_trust.py -q
```

A document that is not a committed fixture can be checked from Python, for every
structural reason at once:

```python
import yaml
from tools.contract_validation.rendered_workload_release import validate

findings = validate(yaml.safe_load(open("release.yaml", encoding="utf-8")))
```

and, once it parses, judged and compared with the documents it names:

```python
from inferops.domain.environment import parse_environment_binding
from inferops.domain.release import (
    check_rendered_workload_release,
    parse_rendered_workload_release,
    verify_release_sources,
)
from inferops.domain.workload import parse_workload_contract

release = parse_rendered_workload_release(release_document)
refusals = check_rendered_workload_release(release) + verify_release_sources(
    release,
    parse_workload_contract(contract_document),
    parse_environment_binding(binding_document),
)
```

`python -m tools.contract_validation` validates WorkloadContract documents only and will
refuse a release as a malformed contract; it was not extended, and the
continuous-integration gate that runs it over the WorkloadContract's fixtures was not
given the release's. The release fixtures run in the default pytest lane.

The suite reads only files in this repository: no network, no cluster, no clock, no
randomness. It checks that the schema is a valid draft 2020-12 schema whose every object
is closed and whose every member is required, whose every string in every accepted form
is a pattern or a vocabulary, whose top level has no `spec` or `status`, and in which no
property is named for a time; that no chart, manifest, or infrastructure file mentions
the kind; that the workload identifier, binding name, digest-pinned version, recordable
source versions, and environment vocabulary are the WorkloadContract's and the
EnvironmentBinding's own, and the semantic version is the contract's without uppercase,
with the cost of that narrowing measured; that the [field table](#what-a-release-records)
is the schema; that no other contract's fixture is a release and no release is another
contract; that each valid fixture validates, is JSON-representable, is named after its
workload and binding, holds no secret-shaped field name, names a committed contract and
binding fixture serving one environment, carries the derived release identifier, and has
placeholder digests; that every invalid fixture is refused with exactly the published
code, rule, and field, by the bare schema as well as the validator, repeatably, and
without quoting a document value; that the rule matrix above is every structural rule and
only the fallback lacks a fixture; and that timestamps, UUIDs, and the excluded credential
shapes are refused in every field while an underived identifier and the lowercase
credential shapes still pass the schema where this document says they do.

The domain suite, `tests/domain/test_rendered_workload_release_domain.py`, reads only files
in this repository too. It checks that every field list, pattern, bound, vocabulary, and
recordable version the domain applies is the schema's; that the parser and the validator
agree on every committed fixture, no member of a release can be omitted, and no refusal
quotes a value or an undefined field's name; that no attribute of the typed release has a
default or could hold content, a time, or free text; that the canonical form is the
evidence index's byte for byte, a pinned value keeps its pinned digest, key order and YAML
formatting do not move a source digest, the same answers come out of two interpreters under
two hash seeds, and every value with no single JSON spelling is refused; that computing
provenance reads no clock and no random source; that every identity change moves the
identifier, every output change moves only the release, and every contract and binding
change is caught by the digest rule for that document; that the credential rule refuses
every reachable prefix in every position, mistakes no committed name for one, and has the
cost and the gap this document states; and that the rule table above is the code's and
every rule refuses something.

The input-trust suite, `tests/domain/test_provenance_input_trust.py`, checks that every
field of the schema and of a recorded release has one row in the policy and none is
excluded content, that every render-context value is classified once and only the
workload's name and version are public, and that a schema or ownership table with one
field added is caught as unclassified; that every field of a release recorded from each
committed contract is the value its row names, passes both release checks, and reads back
as itself; that a raw argument is refused, and the function's body reaches the context
only through the allowlisted reader; that no excluded value, marked, reaches a release,
that a row or a classification edited to open a path is refused, and that a path opened
on purpose is seen; that recording reads no environment variable and its signature
admits no payload; that the known credential shapes are refused in every field that can
hold one, without being quoted; that the limitation above holds; and that both tables
here are the code's.

Every check is static. A pass is `C0` under
[the evidence levels](../testing/evidence-levels.md): it establishes what the committed
files say about each other and nothing about a running system.

## What this contract does not do

- **It renders nothing, and nothing writes it.** No renderer exists; the render
  boundary assembles a release's `source` block, and `record_release` builds a release in
  memory and writes no file. The values file a release is installed with is still
  written by hand, and no release document exists for it.
- **It checks a source digest only when it is given the source.** The platform domain
  confirms the contract and binding digests against documents a caller supplies. Nothing
  finds those documents for a release, nothing confirms the values digest, and nothing
  checks that the two revisions exist.
- **It derives provenance from a render context, never from a render.** The domain
  computes the digests and the identifier a release records, and `record_release` builds
  one from a context; no renderer has produced values for any of them.
- **It moves no claim.** `deployment-values-derive-only-from-a-validated-document` and
  `the-platform-serves-a-workload-the-contract-describes` stay planned.
- **It certifies nothing about a deployment.** A valid release is a well-formed statement
  of provenance. It is not evidence that the values it names were generated, that they
  were installed, or that anything ran with them.
- **It is not a cluster resource.** No custom resource definition, controller, or
  reconciliation is involved, and a release is never applied to a cluster.
- **Its `$id` is an identifier, not a URL.** Nothing is served at `inferops.io`.
