# EnvironmentBinding v1alpha1

Status: **published schema**, at `v1alpha1` maturity, added by `V2-S1-001-PR1`, and
**read by the platform domain** since `V2-S1-001-PR2`. The schema, its identifier, its
compatibility rules, its ownership boundary with the WorkloadContract, and its valid and
invalid fixtures are published here and validated on every change. The domain parses a
binding into typed objects, refuses bindings that conflict with each other, and selects
the one binding that serves a WorkloadContract. **Nothing uses what it selects**: no
renderer, controller, or script in this repository turns a binding into release values,
and a selection is not evidence that anything will.

| Property | Value |
|---|---|
| Schema | [`contracts/environment/environment-binding.v1alpha1.schema.json`](../../contracts/environment/environment-binding.v1alpha1.schema.json) |
| Dialect | JSON Schema draft 2020-12 |
| Schema `$id` | `https://inferops.io/contracts/environment/environment-binding.v1alpha1.schema.json` |
| `apiVersion` | `inferops.io/v1alpha1` |
| `kind` | `EnvironmentBinding` |
| Authoring form | YAML, restricted to the JSON-representable subset |
| Wire form | JSON |
| Unknown fields | Rejected |
| Validator | [`tools/contract_validation/environment_binding.py`](../../tools/contract_validation/environment_binding.py), structural only |
| Domain | [`src/inferops/domain/environment/`](../../src/inferops/domain/environment/__init__.py): typed objects, parsing, the set rules, and selection |
| Fixtures | [`contracts/environment/examples/`](../../contracts/environment/examples/README.md) |
| Tooling decision | [ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md), applied unchanged |

## What it is for

[The decision that opens a second version](../governance/v2-authorization.md) makes
contract-to-deployment rendering its first capability, and expects rendering to need
input the `v1alpha1` WorkloadContract does not carry, "such as what differs between the
hosts a workload is deployed to". A binding is that input, written down as its own
artifact.

Today those facts live in three places that nothing ties together: the namespace in
the environment scripts and the prerequisite layer, the model cache claim name in the
prerequisite layer and in a values file, and the API replica count in a values file. A
binding states them once per environment, so that a later renderer can take workload
intent from a WorkloadContract and environment facts from a binding, and never either
from a values file somebody edited by hand.

The WorkloadContract is **unchanged** by this. Its schema, fixtures, validator rules,
and domain model are exactly as they were, and a binding adds no field to it.

## Ownership: what a binding owns and what it may not touch

The boundary is the reason the artifact exists, so it is stated first.

**A binding owns environment facts.** Every field under `spec`:

| Field | What it states | Who owns the thing it names |
|---|---|---|
| `spec.environment` | Which environment the facts are for | Shared key — see below |
| `spec.destination.clusterProvider` | The local cluster provider a release goes to | The operator provides the cluster; the [provider contract](../environment/local-cluster-provider-contract.md) supports the value |
| `spec.destination.namespace` | The namespace a release installs into | The prerequisite layer creates the namespace; the binding references it |
| `spec.modelCache.class` | How the model cache is provided | The binding |
| `spec.modelCache.claimName` | The claim a release mounts | The prerequisite layer creates the claim; the binding references it |
| `spec.platform.apiReplicas` | Replicas of the platform API tier | The binding |
| `spec.gitops.destinationPath` | Where generated desired state for the environment is to be written | The binding |

Referencing is not owning, in exactly the sense of
[the resource ownership inventory](../architecture/resource-ownership.md): a binding
naming the namespace and the claim creates neither, and adds no row to that inventory.
A binding is a repository document, not a cluster resource.

**A binding may not carry workload intent.** The WorkloadContract owns every one of
these, and the binding schema has no field for any of them — not an optional field,
not an override block, not a free-form map:

| WorkloadContract field | Why it stays with the contract |
|---|---|
| `spec.profile` | What kind of workload it is |
| `spec.model` | Which model, runtime profile, and serving capability the workload asks for |
| `spec.resources` | What the workload asks the scheduler for |
| `spec.scaling` | The serving replica range, including the serving runtime's replica count |
| `spec.integrations` | Which capabilities the workload depends on |
| `spec.security` | The workload's data classification and secret references |
| `spec.attribution` | Tenant and cost center |
| `spec.evidence` | The workload's runbook and proof |
| `spec.synchronousLlm` | The runtime image and model artifact pins |
| `spec.mockLlm` | The mock's fixture |

The serving runtime's replica count is the case most likely to be misplaced, because it
reads like a platform setting. It is not one: it is the workload's scaling intent, and
[`invalid/workload-intent-in-binding.yaml`](../../contracts/environment/examples/invalid/workload-intent-in-binding.yaml)
is refused for writing it under `spec.platform`. The platform API tier is a different
component with a different owner, and its replica count is the binding's.

**One value is shared, and it is a key, not a copy.** `spec.environment` has the same
controlled vocabulary in both schemas — `ci`, `local`, `dev`, `staging`, `production` —
and a test holds the two vocabularies equal. A contract's environment is what a binding
is matched on. Permitting a value is not a statement that such an environment exists:
the only environment either fixture binds is `local`.

**Because nothing overlaps, there is nothing to override.** A document that tries is not
merged, and no value wins: it is refused as a whole, with `field-unknown` at the field
it tried to write. Silent precedence between a contract and a binding is impossible at
this layer rather than prohibited by a rule someone must remember. A test reads both
schemas and fails if any property name defined under a binding's `spec` is also defined
under a contract's `spec`, other than `environment`.

## Identity

| Identifier | Rule |
|---|---|
| `apiVersion` + `kind` | Name the schema. `apiVersion` alone does not: the WorkloadContract and the EnvironmentBinding share `inferops.io/v1alpha1`, and each is versioned independently of the other |
| `metadata.name` | `binding_id`. A lowercase DNS label, stable, and unique among the bindings of one environment. Renaming a binding makes a different binding |
| `metadata.owner` | `owner_id` of the team that owns the environment's facts — the platform side of the boundary, not the workload's owner |
| `spec.environment` + `metadata.name` | Identify one binding. Two bindings may serve one environment, as the two fixtures do; two with the same pair are refused together, under [`binding-identity-duplicated`](#rules-across-bindings-and-selection) |

A binding carries **no revision field**. A number maintained by hand beside the content
can disagree with the content, and nothing could tell which is right. A binding's
content is identified by a digest of the document instead; how that digest is computed
and where it is recorded belongs to the release provenance artifact, which does not
exist yet, and is not decided here.

## Structure

```yaml
apiVersion: inferops.io/v1alpha1
kind: EnvironmentBinding

metadata:
  name: local-docker-desktop        # binding_id
  owner: platform-operations-demo   # owner_id

spec:
  environment: local                # the key a WorkloadContract is matched on

  destination:
    clusterProvider: docker-desktop # kind | docker-desktop
    namespace: inferops-release     # must start inferops-; must already exist

  modelCache:
    class: existing-claim           # the only class
    claimName: inferops-model-cache # an existing claim; referenced, not created

  platform:
    apiReplicas: 1                  # 1..16, the chart's own bounds

  gitops:
    destinationPath: gitops/environments/local-docker-desktop
```

Every member is required, and every object is closed. A binding that leaves a fact out
would leave a renderer to supply it from somewhere else, which is the silent default the
artifact exists to replace.

- **`destination`** records a selection. It holds no cluster address, context, or
  credential — the provider contract never records those — and it verifies nothing:
  that the selected cluster is live and is the one the operator meant is established by
  the provider contract's verification before anything is mutated, not by a binding.
- **`modelCache.class`** has one value, `existing-claim`: a claim that exists before the
  release is installed, mounted read only, and never created by the release. The storage
  class behind the claim is the prerequisite layer's input and is deliberately not a
  binding field — two owners of one value is what this boundary is for preventing.
- **`platform.apiReplicas`** uses the bounds the chart's values schema accepts for the
  API tier, one to sixteen. A test holds the two schemas to the same bounds.
- **`gitops.destinationPath`** is repository-relative and written as lowercase segments.
  It is a declared location: no GitOps directory exists in this repository, and nothing
  reconciles one.

## Secrets

**A binding references nothing secret and carries nothing secret.** It has no secret
reference block, because an environment fact that needs a credential is a credential
problem the binding should not be solving, and it has no field a value could be written
into. Two things make that structural rather than a promise:

1. **Every object is closed.** A `token`, `password`, or `credentials` field is an unknown
   field and the document is refused, as
   [`invalid/secret-value-in-a-field.yaml`](../../contracts/environment/examples/invalid/secret-value-in-a-field.yaml)
   demonstrates.
2. **Every string is a lowercase identifier or a lowercase path**, or a member of a
   closed vocabulary. There is no free-text field — not even a description — so uppercase
   letters, underscores, dots, whitespace, and assignment characters are refused wherever
   a string can be written. That excludes most of the shapes a pasted credential takes:
   an AWS key identifier, a GitHub or Hugging Face token, a JSON Web Token, and an opaque
   mixed-case string, as
   [`invalid/secret-value-in-an-identifier.yaml`](../../contracts/environment/examples/invalid/secret-value-in-an-identifier.yaml)
   demonstrates.

**What that does not catch, measured rather than hedged.** A credential written only in
lowercase letters, digits, and hyphens has the shape of a name. Tokens in formats that
begin `sk-`, `glpat-`, `gldt-`, or `xoxb-` and continue in lowercase and digits are
accepted by the schema in `metadata.name`, `metadata.owner`, `modelCache.claimName`, and
any segment of `gitops.destinationPath`, and the namespace accepts one after its
`inferops-` prefix. The WorkloadContract's credential heuristic tests for a published
prefix at the start of a value, so it would catch one that begins a name, an owner, or a
claim name, and would miss one inside a path or behind the namespace's prefix; **the
binding applies neither half**, because it has no semantic layer. A test asserts every
one of those outcomes, so the day a change closes the gap it has to say so there. Until
then, a binding is reviewed like any other file for what the schema cannot see.

A refusal never repeats a value from the document, in its message or its field location.
That is the canonical error model's rule and the binding inherits it unchanged.

## Versioning and compatibility

`apiVersion` and `kind` together are the compatibility axis, and the classes are the
WorkloadContract's, applied to this schema:

- **Compatible** — adding an optional field; adding a value to an enum where existing
  values behave as before, such as a second cluster provider once the provider contract
  supports one, or a second model cache class once something provides one; relaxing a
  pattern or raising a bound; adding an invalid fixture for an existing rule; editorial
  changes to descriptions.
- **Conditionally compatible** — adding a semantic rule that refuses a document the
  schema accepts, including applying a credential heuristic; changing a canonical code,
  rule identifier, or field location for an existing rejection. A previously valid
  binding stays valid unless a committed valid fixture says otherwise, but what a
  consumer is told moves.
- **Breaking** — adding a required field; removing or renaming a field; removing an enum
  value; narrowing a pattern or a bound so that a committed valid fixture fails; and any
  field that lets a binding carry a value a WorkloadContract owns. The last one is
  breaking even though it would accept more documents, because it breaks the one
  guarantee the artifact exists to give.

A breaking change requires a new `apiVersion`, even at alpha maturity — the same rule
[the WorkloadContract takes](workload-contract.md#the-alpha-rule-this-project-does-not-take),
for the same reason. Only one binding version exists, so the support window has nothing
to apply to yet.

## Rejection and canonical errors

A single binding document is refused through the canonical error model the
WorkloadContract uses: the same two codes, the same structural rule identifiers, the same
field locations, and the same messages. No code and no rule identifier was added for a
single document. The five rules that compare several documents,
[further down](#rules-across-bindings-and-selection), have identifiers of their own and the
same `contract-invalid` code; the table below is the single-document one.

| Rule | Code | Layer | Refuses, for a binding |
|---|---|---|---|
| `contract-version-unsupported` | `version-unsupported` | Structural | `apiVersion` names a binding version this validator does not implement |
| `field-required` | `contract-invalid` | Structural | A required field is absent — owner, namespace, a whole block |
| `field-unknown` | `contract-invalid` | Structural | A field the binding does not define — a misspelling, a workload field, a credential field |
| `value-not-permitted` | `contract-invalid` | Structural | A value outside a controlled vocabulary — environment, provider, cache class — or a `kind` naming another contract |
| `value-malformed` | `contract-invalid` | Structural | A value that does not match its field's format — a non-DNS-safe identifier, a namespace without its prefix, a traversing or credential-shaped path |
| `value-out-of-range` | `contract-invalid` | Structural | A value outside a permitted length or bound — an API replica count outside one to sixteen |
| `value-wrong-type` | `contract-invalid` | Structural | A value of the wrong JSON type — a replica count written as a string |
| `contract-structure-invalid` | `contract-invalid` | Structural | A structural constraint with no more specific rule. Reaching it means the translation table needs a row |

Every rule for a single document is structural, so **a consumer validating one binding
against the bare schema file reaches the same verdict as the published validator** on
every committed fixture, and so does the domain parser. That is true of this schema and
not of the WorkloadContract, and it is true only because a single binding has no semantic
layer. The rules in the next section need more than one document, and no schema can
apply them.

Seven of the eight rules have an invalid fixture demonstrating them. The eighth,
`contract-structure-invalid`, is the fallback for a keyword the translation table does
not map, and a fixture pinning it would pin a defect. A test asserts that it is the only
rule without one.

### Rules across bindings, and selection

Added by `V2-S1-001-PR2`. [The platform domain](../../src/inferops/domain/environment/selection.py)
applies these to the set of bindings supplied together, and a selection among them for one
WorkloadContract. No canonical code was added: each maps to `contract-invalid`, the code
an offline check concludes when the documents it was given cannot be used as given, and
none is retryable. No identifier is one the offline validator already uses.

| Rule | Code | Refuses |
|---|---|---|
| `binding-identity-duplicated` | `contract-invalid` | Two bindings declare the same `spec.environment` and `metadata.name`. Which one a selection by name returned would be decided by list order |
| `binding-destination-overlaps` | `contract-invalid` | Two bindings declare the same `gitops.destinationPath`, or one inside the other, compared directory by directory and across environments. Desired state generated for one would be written over or inside the other's |
| `binding-not-found` | `contract-invalid` | No binding serves the contract's environment, or no binding has the name asked for |
| `binding-selection-ambiguous` | `contract-invalid` | More than one binding serves the contract's environment and none was named |
| `binding-environment-mismatch` | `contract-invalid` | The binding named for a contract serves a different environment from the contract's |

**The selection rule.** A WorkloadContract's `spec.environment` selects a binding. When
exactly one binding supplied serves that environment, it is the one. When more than one
does, the caller names one, because the contract has no field to name it with and the
domain will not choose: first, last, or any other order is a precedence rule nobody wrote
down. A named binding must serve the contract's environment; a name found only under
another environment is refused, not followed. So adding a second binding to an
environment turns a selection that used to need no name into a refusal until one is given
— the choice is surfaced rather than made. A set with any conflict is not selected from at
all, even for a binding outside the conflict, and the refusal carries every conflict at
once.

**Selection merges nothing.** It returns one of the bindings supplied, as the same object,
and reads one member of the contract, `spec.environment`. The contract's scaling,
resources, model, and every other field are neither read nor copied, and nothing in a
binding could hold them. Combining the two into release input is a renderer's, and no
renderer exists.

**Where a refusal points.** A single document's refusal is located inside it, `$.spec…`.
A refusal about several documents names the document by its role first: `contract` for the
WorkloadContract, `bindings[i]` for the i-th binding supplied (the later of a conflicting
pair, with the earlier one's position in the message), and `selection` for the caller's own
request. No refusal repeats a binding's name, path, or any other value from a document.

Not applied, because nothing in this repository has decided it: a rule relating
`clusterProvider` to `environment`. Both providers are local ones and the vocabulary
admits `production`; no record says which environments a local provider may serve, so the
domain does not guess.

### Rules that are not applied yet

Each of these needs something no document here contains, and nothing applies any of them
today. They are stated so that nobody reads the schema or the domain as more than they
are.

| Rule | Why it is not applied | What it needs |
|---|---|---|
| A binding value shaped like a lowercase credential is refused | A single binding has no semantic layer; see [Secrets](#secrets) | A semantic rule, which is a conditionally compatible change |
| The selected cluster, namespace, and claim exist | A document check cannot see a cluster | The provider contract's verification, at run time, as today |
| Release values are derived from a contract and the binding selected for it | No renderer exists | The renderer, which will consume a selected binding rather than choose one |

## Fixtures

Two valid and eleven invalid fixtures, described in
[their own README](../../contracts/environment/examples/README.md). The valid fixtures are
held to the records whose values they copy — the release lifecycle's namespace, the
prerequisite layer's defaults, the chart's real render values, the provider contract's
providers, and the chart's replica bounds — so a drift between a fixture and the
environment it describes fails the build. They are contract examples: neither is
evidence that the environment it describes was ever run with it.

## Validation

```sh
python -m pytest tests/contracts/test_environment_binding_v1alpha1.py tests/domain/test_environment_binding_domain.py -q
```

A document that is not a committed fixture can be checked from Python, for every
structural reason at once:

```python
import yaml
from tools.contract_validation.environment_binding import validate

findings = validate(yaml.safe_load(open("binding.yaml", encoding="utf-8")))
```

or read into the platform's objects, which stops at the first reason, and then checked
against other bindings and a contract:

```python
from inferops.domain.environment import (
    parse_environment_binding,
    select_environment_binding,
    validate_environment_bindings,
)

binding = parse_environment_binding(document)
refusals = validate_environment_bindings([binding, *others])
chosen = select_environment_binding(contract, [binding, *others], binding_name=name)
```

`python -m tools.contract_validation` validates WorkloadContract documents only and will
refuse a binding as a malformed contract; it was not extended.

The suite reads only files in this repository: no network, no cluster, no clock, no
randomness. It checks that the schema is a valid draft 2020-12 schema whose every
object declares its additional-property policy; that no string field accepts a
credential shape the pattern is meant to exclude, and that the lowercase shapes it
cannot exclude are still accepted; that no property under a binding's `spec` is one a
WorkloadContract's `spec` defines, other than `environment`, and that the two
vocabularies for it agree; that both tables in [the ownership section](#ownership-what-a-binding-owns-and-what-it-may-not-touch)
agree with the schemas; that each valid fixture validates, is JSON-representable, holds
no secret-shaped field name, and copies its values from the records that own them; that
every invalid fixture is refused with exactly the published code, rule, and field, by the
bare schema as well as the validator, and without quoting a value from the document;
that the rule matrix above names every rule the binding can cite; and that the
WorkloadContract's own fixtures are refused as bindings and binding fixtures as
contracts, so neither schema can accept the other's documents.

The domain suite checks that every vocabulary, pattern, length, bound, and field list the
parser applies is the schema's; that every valid fixture parses and rebuilds to itself,
and every invalid one is refused with the manifest's code at a field the manifest names or
at the object holding it; that no attribute or wire name in a binding's tree is one a
contract's `spec` tree uses, other than `environment`, which is the contract's own type,
and that a binding carrying workload intent is refused whole; that selection returns a
supplied binding unchanged, leaves the contract unchanged, and reads only its
environment; that each rule in [the table above](#rules-across-bindings-and-selection)
refuses the case it names and not its near neighbours, with every reason at once, sorted,
final, and without a document value; that raw documents cannot take the supported path;
that the table is the code's and adds no canonical code; and that the package imports
nothing outside the standard library.

Every check is static. A pass is `C0` under
[the evidence levels](../testing/evidence-levels.md): it establishes what the committed
files say about each other and nothing about a running system.

## What this contract does not do

- **It deploys nothing, and what reads it renders nothing.** The platform domain parses a
  binding and selects one for a contract; no renderer exists, and nothing turns a binding
  and a contract into release values. The values file a release is installed with is
  still written by hand.
- **It moves no claim.** `deployment-values-derive-only-from-a-validated-document` and
  `the-platform-serves-a-workload-the-contract-describes` stay planned.
- **It certifies nothing about an environment.** A valid binding is a well-formed
  statement of facts. It is not evidence that the provider is running, that the
  namespace or the claim exists, or that the API ever ran with the replica count it
  names.
- **It is not a cluster resource.** No custom resource definition, controller, or
  reconciliation is involved, and a binding is never applied to a cluster.
- **Its `$id` is an identifier, not a URL.** Nothing is served at `inferops.io`.
