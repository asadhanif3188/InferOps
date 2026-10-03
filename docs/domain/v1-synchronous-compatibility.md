# V1 synchronous compatibility

Status: **recorded by `V2-S2-003-PR1`, amended by `V2-S2-004-PR1`**, at evidence level
C0. This page says whether the
V2 render path produces the release input of the released V1 synchronous workload, who
owns each value of that input now, and what is still written by hand. Every check behind
it reads committed files, runs the render path in memory, or runs `helm`. Nothing was
installed, and nothing here establishes that a generated release serves a request.

| Property | Value |
|---|---|
| Record | [`v1-synchronous-compatibility.v1alpha1.json`](v1-synchronous-compatibility.v1alpha1.json) |
| Target | The V1 real release: the [`inferops-llm`](../../charts/inferops-llm/Chart.yaml) chart `0.3.0`, released in `v1.0.0`, with the V1 [real values file](../../charts/inferops-llm/ci/real-values.yaml) over the chart's [defaults](../../charts/inferops-llm/values.yaml) |
| V2 inputs | The [reference contract](../../contracts/workload/examples/valid/synchronous-llm-local.yaml), the [`local-kind` binding](../../contracts/environment/examples/valid/local-kind.yaml), and the chart's `api` defaults: the [declared reference release](helm-values-renderer.md#verifying-a-committed-release) |
| V2 release input | The generated [`values.generated.yaml`](../../tests/domain/fixtures/helm-values/support-assistant-local-kind/values.generated.yaml), and the hand-written [`support-assistant-local.manual-values.yaml`](../../tests/domain/fixtures/helm-values/support-assistant-local.manual-values.yaml) installed after it |
| Tests | [`tests/domain/test_v1_sync_compatibility.py`](../../tests/domain/test_v1_sync_compatibility.py) for the record; the Helm lint and render in [`tests/architecture/test_helm_chart.py`](../../tests/architecture/test_helm_chart.py) |
| Validation records | [`v2-s2-003-pr1-validation.md`](../proof/domain/v2-s2-003-pr1-validation.md); the amendment, [`v2-s2-004-pr1-validation.md`](../proof/domain/v2-s2-004-pr1-validation.md) |

> **Amendment, 2026-10-03 (`V2-S2-004-PR1`).** As first recorded, two hand-written values
> repeated contract pins: the download URL (`model.artifact.sourceUrl`) and the licence
> reference (`model.license.reference`). A contract that pinned another model revision
> needed both strings edited by hand, and admission accepted a copy that disagreed with
> the contract. The renderer now derives both from the contract's pins, the hand-written
> file no longer carries them, and admission refuses a hand-written copy. The rows, counts,
> and prose below are the amended state. The first state is in the
> [V2-S2-003-PR1 validation record](../proof/domain/v2-s2-003-pr1-validation.md) and in
> Git history; it is not rewritten there.

## The question

A V1 release is installed from a values file somebody wrote by hand. That file states the
model's pins, the runtime image, the owner, and the attribution, which is the same intent
the WorkloadContract states. V2 renders that intent from the contract and keeps a
hand-written file only for what no input owns. Compatibility means three things here:

1. The V2 render path produces release input for the V1 workload from committed inputs,
   with no edit to the chart, the renderer, or the generated file.
2. That input describes the V1 workload: the same values and the same manifests, except
   for the differences this page states.
3. No value a WorkloadContract owns is written by hand after rendering.

## The target is the released workload

The chart directory, the reference contract, the compatibility matrix, the model-source
record, and the runtime-profile record are byte for byte what `v1.0.0` released. The
validation record shows the `git diff` that measured this; no test reads the tag. The
target is the committed V1 values file, not a deployment of it. A V1 deployment also took
a contributor's API image from an overlay that version control ignores, and that overlay
is outside this comparison.

## The result

| Check | Result | Where |
|---|---|---|
| The generated values over the chart's defaults satisfy the chart's values schema | Holds | `tests/domain/test_helm_values_renderer.py` |
| The hand-written file is admitted beside the generated values | Holds: no finding | `tests/domain/test_v1_sync_compatibility.py` |
| Both files merged over the chart's defaults equal the V1 values file merged the same way | Holds, except one recorded difference | `tests/domain/test_v1_sync_compatibility.py` |
| `helm template` of both files equals `helm template` of the V1 values file with the contract's environment label | Holds: byte-identical | `tests/architecture/test_helm_chart.py` |
| `helm lint --strict` of both files | Passes, and no chart guard fails | `tests/architecture/test_helm_chart.py` |
| What the chart's guards require beyond the generated values | Four values, each hand-written, none owned by a contract | `tests/architecture/test_helm_chart.py` |

The two Helm checks are in the chart suite because the CI job that installs a pinned Helm
runs that suite and fails on a skip. On a host without Helm they skip.

**Lint is not the check.** `helm lint --strict` exits 0 even when one of the chart's own
`fail` guards fires: Helm 3.19 reports the failure as `[INFO]`. Given the generated values
alone, lint exits 0 and reports four guard failures. So the tests read lint's report as
well as its exit status, and `helm template`, which stops on a guard, is the render check.

## Where every value went

The record has one row for every chart value either release sets: 40 values.
Twenty-seven are generated. The WorkloadContract owns twenty-two of those, the
EnvironmentBinding two, and the platform defaults three. Two of the contract's are
derived: the renderer writes them from three model pins by one rule, described below.
Nineteen of the 27 came from the V1 values file, and eight from the chart's defaults.
Thirteen values stay hand-written, under four classes. A test derives every owner from the
renderer's disposition table, its derived-value table, and the boundary's ownership table,
and fails if the record says otherwise.

What moved:

- **Eighteen contract-owned values that V1 wrote by hand are generated**: the model's
  identifier, revision, and four artifact pins, the runtime image's repository and digest,
  the five ownership and attribution values, the profile, telemetry, and the environment
  label, and the two values derived from the model pins, the download URL and the licence
  reference.
- **Four contract-owned values that V1 left to the chart's defaults are generated**:
  `runtime.replicaCount`, the runtime's CPU and memory limits, and `security.secretRefs`.
  A change to those chart defaults no longer changes a rendered release. The contract does.
- **Two values belong to the binding**: `model.cache.claimName`, which V1's file set, and
  `api.replicaCount`, which V1 left to the chart.
- **Three API settings belong to the platform defaults**: the request and drain timeouts
  and the output-token ceiling. The platform defaults are read from the chart's `api`
  block today, so these values come from the same place as in V1. The record names their
  owner.

<!-- The classes below are generated from the record. -->

| Class | Values | What it is |
|---|---:|---|
| `platform-component` | 3 | The platform's own API image. It is a contributor's local build that no registry publishes, so no input owns it yet. It is not workload intent: every workload on the platform runs the same API. |
| `model-acquisition` | 2 | How the model cache is filled: whether the acquisition job runs, and how it fetches. The download location is not in this class: the renderer derives it from the contract's pins. The generated model.artifact.sha256 decides which bytes the acquisition accepts. |
| `model-metadata` | 2 | Facts about the artifact that no contract field determines: its licence identifier, and the name the runtime serves it under. The licence reference is derived from the contract's pins and is generated. Callers name the model by the generated model.identifier. |
| `host-operation` | 6 | How the release runs and checks itself on the host: pull policies, the cache mount, start-time verification, and whether its own collector runs. |

<!-- The table below is generated from the record. -->

| Chart value | V1 took it from | V2 | Owner or class | Note |
|---|---|---|---|---|
| `api.drainTimeoutMs` | `chart-default` | `generated` | `platform-defaults` (`api.drainTimeoutMs`) |  |
| `api.image.digest` | `values-file` | `hand-written` | `platform-component` |  |
| `api.image.pullPolicy` | `values-file` | `hand-written` | `platform-component` |  |
| `api.image.repository` | `values-file` | `hand-written` | `platform-component` |  |
| `api.maxOutputTokens` | `chart-default` | `generated` | `platform-defaults` (`api.maxOutputTokens`) |  |
| `api.replicaCount` | `chart-default` | `generated` | `environment-binding` (`api.replicas`) |  |
| `api.requestTimeoutMs` | `chart-default` | `generated` | `platform-defaults` (`api.requestTimeoutMs`) |  |
| `model.acquisition.enabled` | `values-file` | `hand-written` | `model-acquisition` |  |
| `model.acquisition.source` | `values-file` | `hand-written` | `model-acquisition` |  |
| `model.alias` | `values-file` | `hand-written` | `model-metadata` |  |
| `model.artifact.fileName` | `values-file` | `generated` | `workload-intent` (`model.artifact.file`) |  |
| `model.artifact.repository` | `values-file` | `generated` | `workload-intent` (`model.artifact.repository`) |  |
| `model.artifact.sha256` | `values-file` | `generated` | `workload-intent` (`model.artifact.sha256`) |  |
| `model.artifact.sizeBytes` | `values-file` | `generated` | `workload-intent` (`model.artifact.sizeBytes`) |  |
| `model.artifact.sourceUrl` | `values-file` | `generated` | `workload-intent` (derived) | Derived from `model.artifact.repository`, `model.artifact.revision`, `model.artifact.file` |
| `model.cache.claimName` | `values-file` | `generated` | `environment-binding` (`modelCache.claimName`) |  |
| `model.cache.mountPath` | `values-file` | `hand-written` | `host-operation` |  |
| `model.cache.readOnly` | `values-file` | `hand-written` | `host-operation` |  |
| `model.identifier` | `values-file` | `generated` | `workload-intent` (`model.ref`) |  |
| `model.integrity.verifyOnStart` | `values-file` | `hand-written` | `host-operation` |  |
| `model.license.reference` | `values-file` | `generated` | `workload-intent` (derived) | Derived from `model.artifact.repository`, `model.artifact.revision` |
| `model.license.spdx` | `values-file` | `hand-written` | `model-metadata` |  |
| `model.revision` | `values-file` | `generated` | `workload-intent` (`model.artifact.revision`) |  |
| `ownership.costCenter` | `values-file` | `generated` | `workload-intent` (`attribution.costCenter`) |  |
| `ownership.owner` | `values-file` | `generated` | `workload-intent` (`workload.owner`) |  |
| `ownership.tenant` | `values-file` | `generated` | `workload-intent` (`attribution.tenant`) |  |
| `ownership.workloadId` | `values-file` | `generated` | `workload-intent` (`workload.id`) |  |
| `ownership.workloadVersion` | `values-file` | `generated` | `workload-intent` (`workload.version`) |  |
| `profile` | `values-file` | `generated` | `workload-intent` (`workload.profile`) |  |
| `runtime.image.digest` | `values-file` | `generated` | `workload-intent` (`runtime.imageReference`) |  |
| `runtime.image.pullPolicy` | `values-file` | `hand-written` | `host-operation` |  |
| `runtime.image.repository` | `values-file` | `generated` | `workload-intent` (`runtime.imageReference`) |  |
| `runtime.replicaCount` | `chart-default` | `generated` | `workload-intent` (`serving.replicas.minimum`) |  |
| `runtime.resources.limits.cpu` | `chart-default` | `generated` | `workload-intent` (`resources.cpu`) |  |
| `runtime.resources.limits.memory` | `chart-default` | `generated` | `workload-intent` (`resources.memory`) |  |
| `security.secretRefs` | `chart-default` | `generated` | `workload-intent` (`security.secretRefs`) |  |
| `telemetry.collection.collector.deploy` | `values-file` | `hand-written` | `host-operation` |  |
| `telemetry.deploymentEnvironment` | `values-file` | `generated` | `workload-intent` (`workload.environment`) | V1 `dev`, V2 `local`: intended |
| `telemetry.enabled` | `values-file` | `generated` | `workload-intent` (`integrations.telemetry.capabilityRef`) |  |
| `telemetry.scrapeAnnotations` | `values-file` | `hand-written` | `host-operation` |  |

## What is still written by hand

No contract owns any of the 13 hand-written values. The tests hold this in four ways:

- The hand-written file is admitted beside the generated values. Admission refuses a
  hand-written value that sets, replaces, or removes a generated one.
- Every chart value that a contract-owned context value renders to is in the generated
  file, and no hand-written value sits at, above, or below one of them.
- Given the generated values alone, the chart's guards require exactly four more values,
  and each is a hand-written row: the API image's repository and digest, the model's alias,
  and its licence identifier.
- No hand-written string contains a contract-owned generated value of eight characters or
  more. The record check measures this for every hand-written row.

**Derived, not copied: the download URL and the licence reference.** The renderer writes
both from the contract's model repository, revision, and file, under one rule for the one
model source the platform supports, the Hugging Face Hub:

| Chart value | Rule |
|---|---|
| `model.artifact.sourceUrl` | `https://huggingface.co/<repository>/resolve/<revision>/<file>?download=true` |
| `model.license.reference` | `https://huggingface.co/<repository>/blob/<revision>/LICENSE` |

The rule is the one the V1 [model source record](../serving/model-source.v1.json)
already follows, and the V1 acquisition preflight already refuses a record that does not.
A contract that pins another revision, file, or repository moves both strings, and the
hand-written file needs no edit. A hand-written copy is refused at admission whether it
agrees with the contract or not, because a second copy is the defect. The licence's SPDX
identifier is not derived: no pin determines it, and a repository name does not say which
licence applies. A model published on another host has no supported location: the rule
names one host, and nothing guesses another. The acquisition job still compares what it
fetched with the generated `model.artifact.sha256`; that check, not the URL, decides which
bytes are accepted.

## The one difference

`telemetry.deploymentEnvironment` is `dev` in V1 and `local` in V2. The V1 values file
sets `dev`, which is also the chart's own default. In V2 the contract's `spec.environment`
owns the label, and the reference contract declares `local`, the environment both committed
bindings serve. The difference is intended: the label follows the contract, and nothing is
written by hand to restore `dev`. Against the committed V1 render, it moves two lines, the
environment variable and the scrape relabel that carry the label, and the three
configuration-checksum annotations derived from them.

## What this does not establish

- **That anything was installed or served.** The comparison is of values and rendered
  manifests. No cluster read them. A real deployment of a generated release is later work.
- **That every workload is compatible.** One contract on one binding is compared with one
  V1 values file. Another workload shape, binding, or chart setting is not covered.
- **That the hand-written values are right.** Admission and the record check ownership.
  They do not judge a hand-written value's content, except that the chart's guards require
  four of them.
- **That the derived licence reference resolves.** The rule names the repository's
  `LICENSE` file at the pinned revision. Nothing fetches it. A repository that keeps its
  licence elsewhere would get a reference that does not resolve, and the renderer would not
  notice.
- **That a V1 deployment's overlays are compatible.** The API image overlay a contributor
  generates is outside version control and outside this comparison.

## Validation

```sh
uv run --locked python -m pytest tests/domain/test_v1_sync_compatibility.py -q
uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q
uv run --locked python -m tools.generated_release --check
```
