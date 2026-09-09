# Certifying real inference through Kubernetes

Status: **published procedure, not yet executed.** The workflow described here is
committed and its descriptor validates. Nothing in this repository has installed
the chart into a cluster, and no `C2` Kubernetes record exists. Every figure in a
future record comes from a run; none is quoted here.

This procedure answers one question: **does a real model, loaded by the pinned
runtime, answer a real request through the release's Kubernetes Service?** The
[composed C2 certification](real-runtime-certification.md) already answers the
same question for two containers on a host. Neither answer implies the other, and
this document exists because the Kubernetes path adds a namespace, a chart, a
scheduler, two Deployments, two Services, a claim, and a probe mapping between the
request and the model.

## What runs, and what owns each piece

| Piece | Owns | Where |
|---|---|---|
| [`scripts/environment/kubernetes-certification.sh`](../../scripts/environment/kubernetes-certification.sh) | Every cluster operation: prerequisites, install, readiness waits, the forward, diagnostics, teardown | Shell, beside the other environment scripts |
| [`tools/kubernetes_certification`](../../tools/kubernetes_certification) | The descriptor, the assertions, and the machine-readable record | Python, driven by the script |
| [`deploy/serving/certification/k8s-real-inference.v1.json`](../../deploy/serving/certification/k8s-real-inference.v1.json) | Every budget, target, and assertion the run applies | Committed data |
| [`tests/architecture/test_kubernetes_certification.py`](../../tests/architecture/test_kubernetes_certification.py) | That the descriptor agrees with the chart and the accepted records, and that the script is written the way the safety decisions require | Default check lane |

The split between the first two is deliberate and is the one thing to understand
before editing either. The guard that establishes **which cluster is being acted
on** lives in [`lib.sh`](../../scripts/environment/lib.sh): the reachable API
server's nodes must be containers `kind` labelled for this project's cluster.
Every script here acts through it. A second implementation of that guard in
Python would be a second guard, and two guards for one rule is how a rule stops
being one. So Python operates no cluster: it reads a committed descriptor, reads
the facts the script collected, asserts over what the release answered, and
writes the record.

## The stages

A run passes through these in order, and a diagnostics record names the one it
stopped in. The vocabulary is fixed in `tools/kubernetes_certification/core.py`
and is what turns a failure into a place to look.

| Stage | What it establishes | What a failure there means |
|---|---|---|
| `load` | The committed descriptor is internally consistent and agrees with the runtime package's startup budget, the composition's real-path selection, and the runtime profile's request budget. The chart's budgets and names are compared with it by [the architecture suite](../../tests/architecture/test_kubernetes_certification.py) rather than at load time, and the model source record is compared at `release` and `identity`, where there is something observed to compare it to | An edit to one record and not the others. Nothing was contacted |
| `prerequisites` | The run is authorized, the tools are present, the cluster is this project's and is running the pinned node image, and the forward is loopback | The host or the authorization, not the platform |
| `release` | The Terraform prerequisites applied and Helm installed one release of the real profile, with digest-pinned images, the expected replica count, and the model cache mounted read-only from the claim Terraform owns and verified against its pinned hash | The chart, the values file, or the prerequisite layer |
| `readiness` | Both Deployments reported every replica ready inside their own budgets, the release's own in-cluster test passed, and the forwarded API reported itself ready | Most often the model load, and the runtime's log is the first thing to read |
| `identity` | The API published the real adapter kind, the selected runtime, the configured model, and the pinned revision, with token counting declared | The wrong profile is installed, or the release is answering with mock metadata |
| `inference` | One real request returned one non-empty completion with consistent runtime-derived token counts | The model answered, and the answer did not hold |
| `evidence` | The record was written to the ignored evidence directory | The workspace, not the cluster. Everything the run established still happened; only storing it did not |

## What this proves, and what it does not

Two requests are made, because neither one establishes what the other does.

**The release's own connection test** (`helm test`) runs a pod **inside** the
cluster that asks both Services for their health endpoints by name. That is the
half a host-side forward cannot establish: that cluster DNS resolves the Service
names, that the Services select something, and that what is behind them answers.

**The certified completion** is sent through a `kubectl port-forward` to the API
Service. What that establishes is bounded, and the bound is stated here rather
than discovered later:

- it **does** resolve the Service and reach a ready endpoint behind it, and it
  **does** exercise the whole request path from the API through the runtime to
  the loaded model and back;
- it **does not** traverse the Service's virtual IP, because a forward is served
  by the API server against a selected endpoint rather than by `kube-proxy`;
- it is **not** covered by the release's `workload-network-policy`, whose API
  ingress rule names this release's own pods. Traffic from a forward arrives from
  the node, and whether a plugin permits it is the plugin's answer. On the
  accepted local cluster the question does not arise: `kindnetd` enforces no
  policy at all, which [an executed
  experiment](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md)
  established.

Both Services are `ClusterIP` and no Ingress exists, so a forward is the only way
anything outside the cluster reaches this API. That is a property of the accepted
local environment (ADR 0001 D2), not a shortcut taken here.

**Proving that requests reach more than one replica is out of scope.** This
procedure certifies a single-replica release and refuses a release running any
other replica count rather than reporting a stronger result than it measured.
Multi-replica certification is a separate piece of work.

## The budgets, and which record decides each one

Getting this wrong is the defect most likely to make a correct run look like a
failure, so the sources are named rather than implied.

| Budget | Value | Decided by |
|---|---|---|
| Serving runtime startup | 600,000 ms | `runtime.probes.startup.budgetMs` in the chart |
| Serving runtime rollout | 900,000 ms | `runtime.lifecycle.progressDeadlineSeconds` in the chart |
| Platform API startup | 60,000 ms | `api.probes.startup.budgetMs` in the chart |
| Platform API rollout | 300,000 ms | `api.lifecycle.progressDeadlineSeconds` in the chart |
| One request | 120,000 ms | `requestBudgetMs` in the runtime profile |

**The runtime budget is the chart's, not the adapter's, and the difference
matters.** `startupBudgetMs` in the runtime package is 300,000 ms and is how long
the *adapter* waits for a runtime it started itself. The chart deliberately
budgets the kubelet's startup probe at twice that, because the loads this project
has measured do not fit inside the smaller figure: V1-S2-007 recorded 133,515 ms
to 215,906 ms across six starts and the V1-S2-005 first attempt recorded
358,735 ms cold. A workflow that timed a rollout at 300,000 ms would report that
cold load as a failure. The rollout budgets are larger again, because a rollout
also covers scheduling, the image pull, and the init container's SHA-256 read of a
1.83 GB artifact.

The descriptor refuses a runtime startup budget below the adapter's — the chart's
own rule, since a kubelet that gives up first makes the adapter's budget
unreachable — and refuses a rollout budget below the startup budget it contains.

`helm install` runs **without** `--wait`, so its own budget bounds only the
acceptance of the objects. `--wait` would fold the install, the model load, and
the API start into one number, and the model load is the measurement this workflow
exists to take.

## Prerequisites

Before an authorized run:

1. the local cluster is up — [`cluster-up.sh`](../../scripts/environment/cluster-up.sh),
   verified with [`cluster-verify.sh`](../../scripts/environment/cluster-verify.sh);
2. the host meets the minimum tier — [`preflight.sh`](../../scripts/environment/preflight.sh);
3. the pinned model artifact is downloaded and hash-verified, and the runtime
   image is present — see [model acquisition](model-acquisition.md);
4. the model cache claim holds the artifact, at the subdirectory the declared
   revision derives — see [model cache storage](../environment/model-cache-storage.md);
5. a values file selecting the real profile exists, with an API image reference
   that can actually be pulled or is loaded into the cluster.

Each of these is a declaration in the descriptor, and each one says here whether
it is really enforced:

| Declaration | Enforced by |
|---|---|
| `requiresTerraformPrerequisites` | The script applies the layer before installing, and a test reads the script for the ordering |
| `requiresTargetClusterAssertion` | `inferops::assert_target_cluster` before any mutating call, and the collected cluster name, context, and node image digest are compared with the descriptor |
| `requiresPinnedRuntimeImage` / `requiresPinnedApiImage` | Every image on every workload is read from the cluster and refused unless it carries a digest |
| `requiresVerifiedModelCache` | The claim name, the read-only volume and mount, the presence of the `verify-model` init container, and the pinned SHA-256 appearing in the command it will run are all read from the cluster and compared |

The fourth row is the one worth reading twice. The chart permits
`verifyOnStart: sha256 | size | none` under the real profile and the operator
supplies the values file, so a release installed with `none` would load whatever
bytes the claim held — and the record's provenance names a SHA-256. The
certification therefore reads the rendered init container's own command and
refuses a run in which nothing compared the hash.

Point 5 is the blocker today, and it is stated plainly rather than left to be
discovered at the first image pull. **No InferOps API image is published.**
`platform-api-container-image` is `planned` in
[the ownership inventory](../architecture/resource-ownership.md), no Dockerfile is
committed, and the digest in
[`ci/real-values.yaml`](../../charts/inferops-llm/ci/real-values.yaml) is a
documented placeholder that exists only so the chart's refusal of an unpinned
image has something to accept in a render fixture. Until an API image exists and
is loaded into the cluster, an authorized run stops at the `release` stage with a
pull failure and a diagnostics record saying so. That is the workflow behaving
correctly; it is not a workflow that has been run.

## Running it

Validation, which contacts nothing and installs nothing:

```bash
bash scripts/environment/kubernetes-certification.sh check
```

The authorized run, which applies the Terraform prerequisites, installs a
release, loads a real model, sends a real request, and uninstalls the release:

```bash
bash scripts/environment/kubernetes-certification.sh certify \
  --values path/to/real-values.yaml \
  --confirm-real-kubernetes
```

`--port N` moves the loopback forward, which matters when the local composition
is already running and holding the API's own port.

Without `--confirm-real-kubernetes` the script refuses before it touches
anything. That is the same shape the
[composed certification](real-runtime-certification.md) uses, and for the same
reason: a workflow that provisions and installs on the strength of a default is a
workflow somebody runs by accident.

## The evidence it produces

| File | What it is |
|---|---|
| `.cache/inferops/certification/k8s-real-inference.json` | The record of a certified run. Ignored by version control until it is promoted |
| `.cache/inferops/certification/k8s-real-inference-diagnostics.json` | Why a run did not certify, naming the stage |
| `.artifacts/kubernetes-certification/cluster-facts.json` | What the script measured. **Host state, not evidence.** Its location is fixed by the descriptor and the tool accepts no argument naming it: the whole cluster half of the record is copied out of this file, so a path flag would let a run reach a real Service and describe an environment read from somewhere else |
| `.artifacts/kubernetes-certification/` | Diagnostics collected on failure: release history, object listing, pod descriptions, events, and tail-bounded container logs |

The record names the cluster version and node image digest, the tool versions,
the release revision and chart version, every workload's digest-pinned images and
replica readiness, how the model cache was mounted and whether its hash was
compared in the cluster, the configured model identifier and revision, the
measured prerequisite, install, and readiness times, and the observed identity and
token counts. Its provenance names the pinned model SHA-256 **beside the flag
saying the run compared it**, because
[the certification levels](../testing/certification.md) require a C2 record to
name a hash "computed and compared" and a hash copied out of a committed record is
neither.

It does **not** contain the prompt or the completion. `retainGeneratedText` is
`false` in the descriptor and a run that set it true is refused, which is the
same rule [the telemetry catalog](../telemetry/telemetry-catalog.md) applies to
every other surface: content this project has no business retaining is not
retained because a record would have been convenient.

Promoting a record into `docs/proof/` is what makes a `C2` claim. The rules for
that are in [the certification levels](../testing/certification.md) and
[the test strategy](../testing/test-strategy.md), and nothing here raises a
ceiling.

## Cleanup, and what it deliberately leaves

On success the script uninstalls the release and then asks the cluster four
questions rather than trusting Helm's bookkeeping: that no object carrying the
release's instance label survived — persistent volume claims included in the
selector, because a chart that created one would show up there; that Helm itself
reports no such release; that the namespace survived; and that the claim count is
the one counted before the install. The last is why the count is taken on both
sides: the claim is the single object in this namespace that must outlive a
release, and comparing counts asserts it without this workflow needing to know
which claim a values file named.

It removes **nothing else**, and the boundary is
[the ownership inventory](../architecture/resource-ownership.md)'s rather than a
preference:

- the **namespace** and the **model cache claim** are Terraform's. Reclaiming
  them is `scripts/environment/terraform-prerequisites.sh destroy --confirm`, and
  that is the only operation in this repository that frees the model weights
  while leaving the cluster standing — which the next run re-downloads over a
  transport whose certificate this project does not validate. Deleting the cluster
  frees them as well: the claim is backed by storage inside the node container.
- the **cluster** is the contributor's host.
  [`cluster-down.sh`](../../scripts/environment/cluster-down.sh) removes it and
  neither Helm nor Terraform nor this workflow may.

On failure it removes nothing at all. The release stays installed, the
diagnostics are collected, and the message says how to remove it by hand. A
teardown that ran on failure would delete the evidence of the failure.

## Troubleshooting

| Symptom | Where to look |
|---|---|
| The install fails pulling an image | The API image blocker above. `.artifacts/kubernetes-certification/events.txt` names the pull |
| The runtime rollout times out | `.artifacts/kubernetes-certification/release.log`. A load slower than the budget is a host that is short of memory more often than a broken image |
| The connection test fails | The Services select nothing, or a probe never passed. `describe-pods.txt` and `events.txt` |
| The identity stage refuses with mock metadata | A values file selecting the mock profile, or a release installed from one |
| The forward never accepts a connection | `.artifacts/kubernetes-certification-forward.log` |
| The run refuses before anything happens | The descriptor disagrees with a record that decides one of its values. Run `check`, which names the field |
| The run stops at `release` saying the artifact hash was not compared | The values file set `verifyOnStart` to `size` or `none`. The certified path requires `sha256` |
| The run stops at `prerequisites` naming the node image | The cluster is running a node image that is not the pinned one. Recreate it with [`cluster-up.sh`](../../scripts/environment/cluster-up.sh) |

Cluster-level symptoms — scheduling, storage, the claim, the node — are in
[the local cluster guide](../environment/local-cluster.md) and
[local runtime troubleshooting](local-runtime-troubleshooting.md).
