# Helm values renderer

Status: **implemented in the platform domain** by `V2-S2-001-PR1`. This page says how a
validated render context becomes the values of the existing `inferops-llm` chart: where
each value goes, what is refused, the canonical form the values are written in, what a
hand-written values file may still set, and how the result compares with the V1 real
release. The renderer returns values **in memory**. Nothing in this repository writes them
to the file a release is installed with, binds them to a RenderedWorkloadRelease, commits
them, or installs them. Every check behind this page is static, at evidence level C0.

| Property | Value |
|---|---|
| Module | [`src/inferops/domain/render/helm_values.py`](../../src/inferops/domain/render/helm_values.py), with the YAML form in [`values_yaml.py`](../../src/inferops/domain/render/values_yaml.py) |
| Entry points | `HelmValuesRenderer(revision).render(context)`, or `render_with(renderer, ...)` on documents; `manual_value_findings(values)` for a hand-written file |
| Input | A `RenderContext` from [the renderer input boundary](renderer-input-boundary.md), for a `synchronous-llm` contract |
| Output | `GeneratedHelmValues`: 25 chart values, as a read-only document and as canonical YAML |
| Chart | `inferops-llm` `0.3.0`; a test fails if [`Chart.yaml`](../../charts/inferops-llm/Chart.yaml) names another |
| Refusal | `RenderRefused`, under the boundary's vocabulary; four rules are the renderer's own |
| Golden output | [`support-assistant-local.values.generated.yaml`](../../tests/domain/fixtures/helm-values/support-assistant-local.values.generated.yaml) |
| Tests | [`tests/domain/test_helm_values_renderer.py`](../../tests/domain/test_helm_values_renderer.py) |
| Validation record | [`v2-s2-001-pr1-validation.md`](../proof/domain/v2-s2-001-pr1-validation.md) |

## What it is for

A V1 release is installed with a values file somebody wrote by hand, and that file
restates what the WorkloadContract already says: the runtime image, the model's pins, the
owner, the resources. Two copies of one intent drift, and nothing says which one a release
used. The renderer removes the second copy. It reads the context the boundary built - every
value with its one owner - and writes the chart values those owners decide, so the
contract is the only place the workload's intent is written.

It extends the chart's values contract rather than defining a format beside it. Every value
it writes is one [`values.schema.json`](../../charts/inferops-llm/values.schema.json)
already defines; every value it does not write keeps the chart's own default or comes from
a hand-written file. The chart, its templates, and its schema are unchanged.

## What it produces

For the reference workload - the [`synchronous-llm` contract fixture](../../contracts/workload/examples/valid/synchronous-llm-local.yaml)
on either [local binding](../../contracts/environment/examples/valid/local-kind.yaml), with
the chart's API defaults - the output is the committed golden file, byte for byte:

```yaml
# Generated Helm values for the inferops-llm chart, version 0.3.0.
# Do not edit by hand: change the WorkloadContract, the EnvironmentBinding, or
# the platform defaults they were rendered from, and render them again.
api:
  drainTimeoutMs: 15000
  maxOutputTokens: 128
  replicaCount: 1
  requestTimeoutMs: 120000
model:
  artifact:
    fileName: "Qwen3-1.7B-Q8_0.gguf"
    repository: "Qwen/Qwen3-1.7B-GGUF"
    sha256: "sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a"
    sizeBytes: 1834426016
  cache:
    claimName: "inferops-model-cache"
  identifier: "qwen3-1-7b-q8-0"
  revision: "90862c4b9d2787eaed51d12237eafdfe7c5f6077"
ownership:
  costCenter: "demo-cost-center"
  owner: "team-platform-demo"
  tenant: "demo"
  workloadId: "support-assistant"
  workloadVersion: "0.1.0"
profile: "real"
runtime:
  image:
    digest: "sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"
    repository: "ghcr.io/ggml-org/llama.cpp"
  replicaCount: 1
  resources:
    limits:
      cpu: "6"
      memory: "3Gi"
security:
  secretRefs: []
telemetry:
  deploymentEnvironment: "local"
  enabled: true
```

The two local bindings render the same bytes. They differ only in the cluster provider and
the GitOps destination, and neither is a chart value. A test asserts both facts.

## Where every value goes

Every one of the context's 44 values has one disposition, and a test fails if the context
gains a value this table does not name:

- **`rendered`** - written to the chart values named. 24 values, written to 25 chart values:
  the runtime image reference is split at its digest.
- **`constrained`** - not written, because the chart has no setting for it, and refused
  unless it asks for what the chart already does. 8 values.
- **`not-rendered`** - not written, and no chart setting depends on it. 12 values.

A test compares this table with the code, row for row.

<!-- The table below is generated from HELM_VALUE_DISPOSITIONS. -->

| Context value | Disposition | Chart values | Why |
|---|---|---|---|
| `workload.id` | `rendered` | `ownership.workloadId` | The chart value of the same meaning |
| `workload.version` | `rendered` | `ownership.workloadVersion` | The chart value of the same meaning |
| `workload.owner` | `rendered` | `ownership.owner` | The chart value of the same meaning |
| `workload.profile` | `rendered` | `profile` | Synchronous-llm is the chart's real profile; the chart derives the serving capability and the adapter from it |
| `workload.environment` | `rendered` | `telemetry.deploymentEnvironment` | The environment every emitted record carries |
| `model.servingCapability` | `not-rendered` | - | The chart derives the capability from its profile, and the boundary already requires the native capability for this profile |
| `model.ref` | `rendered` | `model.identifier` | The platform identifier a caller's model member is checked against |
| `model.runtimeProfile` | `constrained` | - | The chart configures one runtime sizing, so only that sizing is accepted |
| `resources.cpu` | `rendered` | `runtime.resources.limits.cpu` | The ceiling the runtime runs under; the request stays the chart's |
| `resources.memory` | `rendered` | `runtime.resources.limits.memory` | The ceiling the runtime runs under; the request stays the chart's |
| `resources.accelerator.type` | `constrained` | - | The chart requests no accelerator, so only none is accepted |
| `resources.accelerator.count` | `constrained` | - | The chart requests no accelerator, so only a count of zero is accepted |
| `serving.replicas.minimum` | `rendered` | `runtime.replicaCount` | The chart runs a fixed replica count, so the range must be one number |
| `serving.replicas.maximum` | `constrained` | - | The chart has no autoscaler, so the maximum must equal the minimum |
| `integrations.telemetry.capabilityRef` | `rendered` | `telemetry.enabled` | The platform's telemetry is the chart's own, so declaring it enables it; another capability is refused |
| `integrations.telemetry.required` | `not-rendered` | - | Telemetry is enabled for every workload, which satisfies either answer |
| `integrations.modelAccess.capabilityRef` | `constrained` | - | The chart wires no model-access or evaluation capability, so declaring one is refused rather than dropped |
| `integrations.modelAccess.required` | `constrained` | - | The chart wires no model-access or evaluation capability, so declaring one is refused rather than dropped |
| `integrations.evaluation.capabilityRef` | `constrained` | - | The chart wires no model-access or evaluation capability, so declaring one is refused rather than dropped |
| `integrations.evaluation.required` | `constrained` | - | The chart wires no model-access or evaluation capability, so declaring one is refused rather than dropped |
| `security.dataClassification` | `not-rendered` | - | No chart setting acts on a classification, and no policy engine reads one |
| `security.secretRefs` | `rendered` | `security.secretRefs` | Rendered empty; a declared reference is refused, because no accepted rule maps a contract locator to the chart's secret binding |
| `attribution.tenant` | `rendered` | `ownership.tenant` | The chart value of the same meaning |
| `attribution.costCenter` | `rendered` | `ownership.costCenter` | The chart value of the same meaning |
| `evidence.runbookRef` | `not-rendered` | - | A documentation reference; no chart setting reads it |
| `evidence.proofRefs` | `not-rendered` | - | Documentation references; no chart setting reads them |
| `runtime.imageReference` | `rendered` | `runtime.image.repository`, `runtime.image.digest` | Split at its digest, because the chart pins the repository and the digest as two values |
| `model.artifact.repository` | `rendered` | `model.artifact.repository` | The chart value of the same meaning |
| `model.artifact.revision` | `rendered` | `model.revision` | The chart derives the in-claim directory from it |
| `model.artifact.file` | `rendered` | `model.artifact.fileName` | The chart value of the same meaning |
| `model.artifact.sizeBytes` | `rendered` | `model.artifact.sizeBytes` | The chart value of the same meaning |
| `model.artifact.sha256` | `rendered` | `model.artifact.sha256` | The chart value of the same meaning |
| `mock.ciOnly` | `not-rendered` | - | The mock profile's block; the renderer takes the synchronous profile only, so no context it renders holds one |
| `mock.determinism` | `not-rendered` | - | The mock profile's block; the renderer takes the synchronous profile only, so no context it renders holds one |
| `mock.fixtureRef` | `not-rendered` | - | The mock profile's block; the renderer takes the synchronous profile only, so no context it renders holds one |
| `api.requestTimeoutMs` | `rendered` | `api.requestTimeoutMs` | The chart value of the same meaning |
| `api.drainTimeoutMs` | `rendered` | `api.drainTimeoutMs` | The chart value of the same meaning |
| `api.maxOutputTokens` | `rendered` | `api.maxOutputTokens` | The chart value of the same meaning |
| `destination.clusterProvider` | `not-rendered` | - | Selects the cluster a release is installed into; not a chart value |
| `destination.namespace` | `not-rendered` | - | The release namespace is an install argument, not a value, and the chart checks its prefix itself |
| `modelCache.class` | `not-rendered` | - | The chart mounts an existing claim, the one class this binding version has |
| `modelCache.claimName` | `rendered` | `model.cache.claimName` | The existing claim the runtime mounts |
| `api.replicas` | `rendered` | `api.replicaCount` | The chart value of the same meaning |
| `gitops.destinationPath` | `not-rendered` | - | Where a release is written, not something a release reads |

## The canonical form

The values are YAML because Helm reads YAML. The distribution has no runtime dependency, so
[`values_yaml`](../../src/inferops/domain/render/values_yaml.py) writes it, with one
spelling for each value:

- mappings in block style, **keys sorted** by code point, two spaces per level; lists in
  block style, in order; `{}` and `[]` for empty ones;
- **every string double-quoted**, with only `\` and `"` escaped. A plain scalar is read by
  its shape - `yes` and `on` as booleans, `1e3` as a number, `2026-09-30` as a date - and
  quoting every string removes that question rather than answering it value by value;
- integers in decimal within +/-(2^53 - 1), booleans as `true` and `false`;
- LF line endings, one final newline, and the fixed three-line header above. The header
  holds no revision, date, or identifier.

What has no single spelling is refused, with its location and never its value: a string
holding anything but printable ASCII, a key that is not a plain identifier or is a word YAML
1.1 reads as a boolean or a null, `None`, a float, a nested list, or any other type. Nothing
the renderer writes needs one: every chart string it writes is ASCII by the chart's own
pattern. A test round-trips 29 strings that a plain scalar would misread.

The same context gives the same bytes: whatever order the bindings arrive in, under two hash
seeds in two interpreters, and with every clock, random source, and environment read patched
to fail. The renderer's revision names the commit it runs from and takes no part in the
values. **How the values file is hashed is not decided here**; binding the values to a
release, with its digest, is a later change's.

## What it refuses

A context reaches the renderer only after the boundary accepted it, so every refusal here is
about the chart rather than the input. Each finding names the input by its role -
`contract`, `binding` for the selected binding, `platformDefaults` - and the path inside it,
and never quotes a value. Every finding is reported at once, in the boundary's order.

| Rule | Category | Code | Refuses |
|---|---|---|---|
| `render-capability-unsupported` | `value-unsupported` | `capability-unavailable` | A replica range, since the chart has no autoscaler; an accelerator; a runtime sizing other than `resource-conscious`; a telemetry capability other than `platform-telemetry`; a `modelAccess` or `evaluation` integration; a secret reference |
| `render-value-unsupported` | `value-unsupported` | `capability-unavailable` | A value outside the chart schema's constraint on the value it would be written to; a CPU or memory limit below the chart's runtime request |
| `render-value-credential-shaped` | `semantic-invalid` | `contract-invalid` | A string the renderer would write with a part beginning with a published credential prefix |
| `render-profile-unsupported`, `render-contract-version-unsupported`, `render-binding-version-unsupported` | as published | as published | A context outside the renderer's support. `render_with` refuses it before calling the renderer; `render` refuses it again for a context built without that check |

**The chart is narrower than the contract.** `CHART_VALUE_CONSTRAINTS` copies the chart
schema's constraint for each of the 25 values written, and a test reads the schema and fails
if one keyword differs. The contract accepts more than the chart in these places, and each
is refused here rather than by Helm, each through `render_with` in a test, but for the
last row:

| Contract accepts | Chart accepts | Example refused |
|---|---|---|
| `spec.environment` of `staging` or `production` | `dev`, `ci`, `local`, `test` | `staging` |
| A semantic version with pre-release or build identifiers, or a digest-pinned image reference | `MAJOR.MINOR.PATCH` only | `1.0.0-rc.1` |
| Quantities in `P`, `E`, `Pi`, `Ei`, and CPU in any suffix | CPU in cores or `m`; memory up to `T` and `Ti` | CPU `2k`, memory `1Pi` |
| A model repository of any depth | `owner/name` | `Qwen/Qwen3/GGUF` |
| A file name up to 255 characters | Up to 253 | A 254-character file name |
| A revision of 40 to 64 hexadecimal characters | Exactly 40 | A 64-character revision |
| Up to 100 replicas | Up to 16 | 17 |
| An image reference up to 512 characters | A repository up to 255 | None today: the compatibility matrix registers one runtime repository, and the boundary refuses any other as `runtime-unregistered` before the renderer sees it. A test measures that, and the check stays for the day the matrix registers a longer one |

### Decisions this change made

Each is a decision rather than a fact, recorded so a later change can revisit it on purpose.

- **Resources mean limits.** The contract's `cpu` and `memory` render to
  `runtime.resources.limits`. The runtime's requests stay the chart's - one CPU and `2Gi` -
  because they reserve what a local cluster can schedule: a request of the contract's six
  CPUs would not schedule on a host the environment scripts accept, which need four logical
  CPUs. That is the V1 release's own split. A limit below the chart's request is refused,
  because Kubernetes refuses a container whose request exceeds its limit.
- **Telemetry is enabled for every workload.** Declaring `platform-telemetry` renders
  `telemetry.enabled: true`. `required` is not rendered: `true` and `false` are both
  satisfied by telemetry that is on, and the platform does not operate a workload it cannot
  observe.
- **A secret reference is refused, not rendered.** The chart binds a named Kubernetes
  Secret key to an environment variable of the API; a contract names a provider, a locator,
  an owner, and a rotation duty. No accepted rule maps one to the other - which provider
  becomes which Secret, which variable a logical name becomes - and inventing one here would
  render a binding nobody decided. `security.secretRefs` is rendered empty, and a contract
  declaring any reference is refused. The committed
  [secret-reference example](../../contracts/workload/examples/valid/synchronous-llm-secret-refs.yaml)
  is refused for that reason, and a test says so.
- **One runtime sizing.** The chart configures one runtime - one CPU process, one slot,
  the settings the [runtime profile record](../serving/runtime-profile.local.v1.json)
  publishes - and the renderer reads that as `resource-conscious`. `balanced` and
  `throughput-oriented` ask for sizing no chart setting changes, so they are refused.
- **The environment label is the contract's.** `spec.environment` renders to
  `telemetry.deploymentEnvironment`. The V1 real fixture labels the laptop run `dev`; the
  reference contract declares `local`, so the generated release is labelled `local`. That
  is the one difference from V1 below.
- **Generated values carry no credential shape.** Generated values are meant for Git, so a
  string the renderer would write is refused if any part of it begins with a published
  credential prefix, whichever input supplied it. A binding's claim name is checked here
  for the first time; a binding value no renderer writes still is not.

## Hand-written values

A release needs values no input owns: the API image a contributor built and loaded, the
model's alias, licence, and download URL, and how the release runs on a host - how the claim
is filled and verified, whether its collector runs. Those stay in a hand-written file,
installed after the generated one. The reference workload's is
[`support-assistant-local.manual-values.yaml`](../../tests/domain/fixtures/helm-values/support-assistant-local.manual-values.yaml),
copied from the V1 real fixture with every generated value removed.

**A hand-written file may not repeat contract intent.** Helm merges values files in order,
and the last one wins, so a hand-written file could replace a generated value - or remove it
with a `null` - and nothing would say so. `manual_value_findings` refuses, with
`render-manual-value-generated` and the value's path, a hand-written value that:

- sets a generated value;
- sits beneath one, which replaces it with a mapping; or
- sits above one as anything but a non-empty mapping - a scalar, a list, a `null`, or an
  empty mapping at a generated value itself.

An empty mapping above a generated value merges nothing and is accepted, and so is a
sibling: `model.artifact.sourceUrl` beside the generated `model.artifact.repository`. A test
sets each of the 25 generated values in the committed file and gets exactly one finding for
each; the committed file gets none.

**What the check cannot see.** The download URL repeats the repository, revision, and file
the contract pins, and nothing compares them: the acquisition job's content hash, which the
generated values supply, is what refuses a different file. And a hand-written
`runtime.resources.requests` above the generated limit is not refused here; Kubernetes
refuses it at install.

## Compared with the V1 real release

The generated file and the reference hand-written file together describe the V1 real
release, but for its environment label. Three tests check it, at two layers:

- **Values.** Merged over the chart's defaults the way Helm merges them, the two files equal
  the V1 [real fixture](../../charts/inferops-llm/ci/real-values.yaml) merged the same way,
  except `telemetry.deploymentEnvironment`: `dev` there, `local` here. Both merges validate
  against the chart's values schema, and so do the generated values alone over the defaults.
- **Render.** With `helm` on `PATH`, `helm template` of the two files is byte-identical to
  `helm template` of the V1 fixture with `telemetry.deploymentEnvironment=local`. Against the
  committed V1 render, exactly two lines move - the environment variable and the scrape
  relabel that carry the label - plus the three `inferops.io/configuration-checksum`
  annotations derived from the configuration that holds it.

That is compatibility of rendered manifests, at C0. **Nothing was installed.** Whether the
generated release serves the V1 workload on a cluster is for a later change to show,
on a cluster.

## Not applied yet

| Not applied | Why | What it needs |
|---|---|---|
| The values are written to a file and bound to a RenderedWorkloadRelease, with a digest | Out of this change's scope; how a values file is hashed is undecided | A later change |
| Committed generated values are verified against their sources | Nothing commits generated values yet | A later change |
| A secret reference is rendered | No accepted mapping from a contract locator to the chart's secret binding | A decision on that mapping |
| The `mock-llm` profile is rendered | The renderer declares the synchronous profile only, as the story scopes it | A renderer, or a support change, for the mock profile |
| The platform defaults are read from a committed file | No defaults file exists; the caller states the revision, as at the boundary | The change that reads the defaults from the repository |
| The API image is generated | It is a contributor's local build, published to no registry | A published API image |
| The download URL agrees with the contract's pins | The contract has no field for it; the content hash is the check | A contract field for the source, or a derivation rule |
| A data classification changes a render | No chart setting or policy engine acts on one | A policy engine |

## What this does not establish

- **That anything was installed.** The renders were compared as files. No cluster read
  them, and no generated release has served a request.
- **That a release used generated values.** The values a release is installed with are
  still written by hand: nothing writes generated values where an install reads them.
  `deployment-values-derive-only-from-a-validated-document` stays planned.
- **That the hand-written half is safe.** The check refuses a hand-written value that
  repeats a generated one; it does not judge the others.
- **Anything beyond the reference inputs' shape.** The golden file and the V1 comparison
  are one contract on two bindings of one environment.

## Validation

```sh
uv run --locked python -m pytest tests/domain/test_helm_values_renderer.py -q
uv run --locked python -m pytest tests/domain tests/architecture -q
uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy
```
