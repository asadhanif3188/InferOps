# The capacity preflight for the two-replica release

Status: **the gate is implemented, and synthetic cases show an acceptance and each kind of refusal at evidence level C0. No reading of a cluster is recorded on this page. An acceptance compares stated requests and limits with what one node allocates. It does not establish that a pod is scheduled or starts.**

The desired-state release declares two platform API replicas and two serving
runtime replicas. This page describes the gate that decides, before anything is
installed, whether one cluster can hold that release: what it reads, what it
requires, each rule, each unit, and what a record does not establish.

The gate has two parts.

1. **`scripts/environment/capacity-preflight.sh` reads the cluster and writes one
   directory, the collection.** It changes nothing in the cluster.
2. **`tools/capacity_preflight` reads the collection and prints one record.** It
   reads files and contacts no cluster. The result of a record is `ACCEPTED` or
   `REFUSED`.

**A refusal is a result.** The gate lowers no request, no limit, no replica count,
and no reserve to obtain an acceptance. A cluster that is refused stays refused
until the cluster or the committed release changes.

## What the gate requires: the declared footprint

The footprint is read from committed files, and not from the cluster.
`python -m tools.capacity_preflight --footprint` prints it. The tool reads
[the Application](argocd-application.md) of the desired-state release, which
names the chart and one values file. The values are the chart's defaults, then
the release's [generated values](git-desired-state.md), then the values that the
Application states itself. A later document replaces a member of an earlier one,
as Helm merges values documents.

The tool restates which pods the chart renders. A test renders the chart with
the same values and compares each pod template of the render with the footprint:
the replicas, the surge, and the name, the requests, and the memory limit of
each container. A pod that the chart renders and the footprint does not state
fails that test.

At chart version `0.5.0` the footprint is:

| Component | Kind | Class | Replicas | Surge pods | Processor request of one pod (millicores) | Memory request of one pod (bytes) | Memory limit of one pod (bytes) |
|---|---|---|---|---|---|---|---|
| `platform-api` | Deployment | steady | 2 | 1 | 100 | 134,217,728 | 536,870,912 |
| `serving-runtime` | Deployment | steady | 2 | 0 | 1,000 | 2,147,483,648 | 3,221,225,472 |
| `telemetry-collector` | Deployment | steady | 1 | 1 | 100 | 134,217,728 | 536,870,912 |
| `model-acquisition` | Job | transient | 1 | 0 | 100 | 33,554,432 | 134,217,728 |
| `connection-test` | Pod | transient | 1 | 0 | 10 | 16,777,216 | 67,108,864 |

The request of one pod is the larger of two figures: the sum over its
containers, and its largest init container. The memory limit of one pod is
computed the same way from the limits. The serving runtime pod has one init
container, `verify-model`, which is smaller than the runtime container.

### Rollout headroom

A rollout creates pods beyond the replica count. The footprint states them as
surge pods.

- **The platform API surges by one pod.** Its strategy is 0 unavailable and 1
  surge, so a rollout holds three API pods for a time.
- **The serving runtime surges by no pod.** Its strategy is 1 unavailable and 0
  surge. A rollout removes one runtime pod before it creates the next, so the
  gate requires no third runtime and no third copy of the model in memory.
  [The chart's README](../../charts/inferops-llm/README.md) describes that
  strategy.
- **The telemetry collector surges by one pod.** The chart states no strategy
  for this Deployment. The Kubernetes documentation states the default surge of
  a Deployment as 25 percent of its replicas, rounded up, which is one pod for
  one replica.

### Transient pods

The model acquisition hook is one Job pod. The chart's test hook is one pod. The
gate counts both beside the Deployments and the surge pods.

**This sum is an upper bound, and it was not observed.** The acquisition hook
runs before an install and before an upgrade. Whether a hook pod, a surge pod,
and a test pod exist at one time was not observed, so the gate requires room for
all of them. On the one provider where the Application was applied, no pod of
the test hook was listed ([the Application page](argocd-application.md)).

### The reserve and the requirement

The reserve is the two headroom figures of the V1 multi-replica
certification descriptor: 500 millicores and 536,870,912 bytes (512 MiB). No pod
is attributed to it. It stands for what the gate does not measure. Whether it is
enough was not measured.

| Part | Pods | Processor requests (millicores) | Memory requests (bytes) | Memory limits (bytes) |
|---|---|---|---|---|
| The pods of the three Deployments | 5 | 2,300 | 4,697,620,480 | 8,053,063,680 |
| The surge pods of a rollout | 2 | 200 | 268,435,456 | 1,073,741,824 |
| The hook pod and the test pod | 2 | 110 | 50,331,648 | 201,326,592 |
| The reserve | 0 | 500 | 536,870,912 | 536,870,912 |
| **Required** | **9** | **3,110** | **5,553,258,496** | **9,865,003,008** |

The gate holds two of these figures and the pod count to the node. It holds the
**processor requests**, because the scheduler places a pod by its requests. It
holds the **memory limits**, and not the memory requests, because a serving
runtime loads a model of 1,834,426,016 bytes and can use its whole limit.
The tool gives no footprint for a pod whose memory limit is below its memory
request, so a node that holds the memory limits also holds the memory requests. The record states the memory requests, and no
rule reads them.

## What the gate reads: the collection

The script verifies the selected target first, as every platform workflow does
([the provider contract](local-cluster-provider-contract.md)). It then writes the
footprint, and then it makes the reads. Each read is one `kubectl get` or
`kubectl version`, or one `docker info`.

| File | What it holds |
|---|---|
| `footprint.json` | What `python -m tools.capacity_preflight --footprint` printed before the script collected a read. Schema `inferops.io/capacity-preflight-footprint/v1alpha1` |
| `run.json` | The provider, the context, the release key, the release namespace, the commit of the working tree, and the time. Schema `inferops.io/capacity-preflight-collection/v1alpha1` |
| `nodes.json` | Every node |
| `pods.json` | Every pod of every namespace |
| `namespace-limits.json` | Every ResourceQuota and every LimitRange of the release namespace |
| `claims.json` | Every PersistentVolumeClaim of the release namespace |
| `version.json` | The client and server versions. No rule reads it |
| `engine.json` | The container engine's processor count and memory. No rule reads it |
| `record.v1alpha1.json` | The record that the tool printed for this directory. Schema `inferops.io/capacity-preflight/v1alpha1` |

**A read that does not answer is not an empty result.** The script writes no file
for it. The tool reads an absent file, a file that is not JSON, and a file that
is not a list as a read that was not made, and the record is `REFUSED`.

The script writes into a new directory under
`.artifacts/capacity-preflight/collections/`, and it refuses a name that exists.
Git ignores `.artifacts/`.

## What the gate computes

### Units

| Figure | Unit |
|---|---|
| A processor figure | millicores: one thousandth of one processor |
| A memory figure and a storage figure | bytes |
| A pod figure | pods |

A Kubernetes quantity is read exactly, as a fraction. A request is rounded up to
the unit, and a figure that a node allocates is rounded down. A text that is not
a quantity is not read as zero: a sign, a blank, a suffix in another case, and a
digit that is not ASCII are refused.

### The node

The gate adds figures for exactly one schedulable node. The figures are the
node's `allocatable` processor, memory, and pod count. The record also states
the node's `capacity` and its allocatable ephemeral storage, and no rule reads
them.

**More than one schedulable node is refused as ambiguous.** The gate does not
decide where a pod is placed among nodes. The model cache claim is
`ReadWriteOnce`, and the Kubernetes documentation states that such a claim is
mounted by pods of one node. So a sum over two nodes says nothing about whether
both runtime pods fit on one of them.

### The reservations

A reservation is the request of a pod that the node already holds. The gate
counts each pod that is not `Succeeded` or `Failed`, and that the one
schedulable node holds or that no node holds yet. It does not count a pod on
another node.

The request of one pod follows the arithmetic that the Kubernetes documentation
gives. A request that the pod states for itself is its request. Without one, the
request is the larger of two figures: the sum over the containers and the
restartable init containers, and the largest init container beside the
restartable init containers that start before it. The pod's overhead is added.

**A container that states no request is counted as zero.** The sum is a sum of
stated requests, and such a container adds nothing to it. Its use is not
measured. The record states how many counted pods have such a container, for the
processor and for memory. On 2026-10-08, on
the provider where the Application was applied, the pods of the Argo CD
installation stated no request ([Git desired state](git-desired-state.md)). The
gate counts such an installation as zero.

The record states the sums for each namespace, and the totals.

### The three comparisons

For the pod count, the processor requests, and the memory limits:

```text
available = what the node allocates - what the counted pods request
held when   required <= available
shortfall = required - available, when it is above zero
```

For memory, `what the counted pods request` is their memory requests. The gate
does not read the memory limits of pods outside the footprint.

## The rules

12 rules. 11 are required. Each rule has one of three states.

| State | Meaning |
|---|---|
| `held` | The reads show the statement |
| `not-held` | One read contradicts the statement |
| `not-observed` | A read that the rule needs was not made, or an earlier rule left the rule without one node to compare |

| Result | When |
|---|---|
| `ACCEPTED` | Every required rule is `held`, and no rule is `not-held` |
| `REFUSED` | One rule is `not-held`, or one required rule is `not-observed` |

A refusal names its categories. `insufficient` means that a stated figure does
not fit. `ambiguous` means that the gate cannot decide from what it read. A rule
that is `not-observed` refuses as `ambiguous`, whatever its own category is.
**Every rule is evaluated. One record names each figure that is short, and not
the first one only.**

| Rule | Category | Statement |
|---|---|---|
| `cluster-reads-complete` | ambiguous | The collection holds each of the four cluster reads, and each is a list. |
| `quantities-readable` | ambiguous | Each resource quantity of each node and of each unfinished pod is a Kubernetes quantity that is not negative. |
| `one-schedulable-node` | ambiguous | The cluster has exactly one schedulable node. |
| `node-ready-without-pressure` | ambiguous | The schedulable node reports Ready, and it reports no pressure condition. |
| `node-states-no-blocking-taint` | ambiguous | The schedulable node states no taint with the effect NoSchedule or NoExecute. |
| `release-states-no-placement-constraint` | ambiguous | The footprint states no node selector, no toleration, and no affinity. |
| `namespace-states-no-quota-or-limit-range` | ambiguous | The release namespace holds no ResourceQuota and no LimitRange. |
| `release-is-not-installed` | ambiguous | The release namespace holds no unfinished pod of the release. |
| `pod-count-fits` | insufficient | The pods of the footprint fit in the pod count that the node allocates, less the unfinished pods that the node holds. |
| `cpu-requests-fit` | insufficient | The processor requests of the footprint and the reserve fit in the processor that the node allocates, less the processor that the unfinished pods request. |
| `memory-limits-fit` | insufficient | The memory limits of the footprint and the reserve fit in the memory that the node allocates, less the memory that the unfinished pods request. |
| `model-cache-claim-holds-artifact` (not required) | insufficient | The model cache claim has at least the byte count of the model artifact. |

The last rule is not required, because the gate can run before
[the prerequisite layer](platform-prerequisites.md) creates the claim. An absent
claim is `not-observed` and does not refuse. A claim that exists and is smaller
than the artifact refuses. The rule compares the claim's capacity, or its
request when the claim states no capacity. It does not read the disk behind the
claim.

Why three of the `ambiguous` rules refuse:

- **A quota or a limit range in the namespace.** The Kubernetes documentation
  describes a ResourceQuota as a limit on what a namespace's pods request
  together, and a LimitRange as a source of default requests and limits. So one
  can refuse a pod that the node has room for, and the other can change what a
  pod requests. The gate models neither.
- **A release that is already installed.** Its pods are among the pods that the
  node holds, so the gate would count the release two times. The gate measures a
  cluster before the release.
- **A placement constraint.** A node selector, a toleration, or an affinity in
  the release's values changes which node a pod can use. The gate does not
  evaluate one. The Kubernetes documentation states that a pod without a
  matching toleration is not scheduled onto a node whose taint has the effect
  `NoSchedule` or `NoExecute`. The release states no toleration, so the gate
  refuses a node that states such a taint.

## How to run it

```sh
INFEROPS_PROVIDER=<provider> scripts/environment/capacity-preflight.sh [--into NAME]
```

| Exit status | Meaning |
|---|---|
| 0 | The record is `ACCEPTED` |
| 5 | The record is `REFUSED`. The directory is kept |
| 1 | No record was written: the target was not verified, the name exists, or the tool refused the directory |

The tool alone:

```sh
uv run --locked python -m tools.capacity_preflight --footprint
uv run --locked python -m tools.capacity_preflight DIRECTORY
uv run --locked python -m tools.capacity_preflight DIRECTORY --as-collected
uv run --locked python -m tools.capacity_preflight --check
```

`DIRECTORY` prints the record, with the same exit statuses. Before it builds a
record, it compares the stored footprint with the footprint that the committed
files give now, and it prints no record when they differ. So a collection that
was written for fewer replicas, or for smaller requests, is not a gate for the
declared release. `--as-collected` skips that comparison, for a collection that
an earlier tree wrote.

**A stored footprint is not trusted for its arithmetic.** The tool computes each
derived figure again from the stated quantities, and it requires its own
reserve. A footprint whose figures differ is not a collection.

## The committed cases

`tests/domain/fixtures/capacity-preflight/` holds six collections that no
cluster produced, each with its record. Their header states the provider
`synthetic` and a commit of forty zeros. `--check` builds each record again and
compares it with the committed record.

| Case | Result | What it shows |
|---|---|---|
| `accepted-one-node` | `ACCEPTED` | One node with room, nine pods of a control plane, and a bound claim |
| `refused-insufficient-memory` | `REFUSED`, `insufficient` | The same cluster with 8 GiB of allocatable memory. The memory limits do not fit |
| `refused-insufficient-processor-and-pods` | `REFUSED`, `insufficient` | A node with 4 processors and 16 pods. Two figures are short, and the record names both |
| `refused-ambiguous-two-nodes` | `REFUSED`, `ambiguous` | Two schedulable nodes of 64 processors and 256 GiB each |
| `refused-ambiguous-read-not-made` | `REFUSED`, `ambiguous` | A collection without `pods.json` |
| `refused-ambiguous-release-installed` | `REFUSED`, `ambiguous` | A runtime pod of the release in the release namespace |

Each case stores the footprint of chart version `0.5.0`. A later chart can
declare other figures. The cases then show the gate's arithmetic on the stored
footprint, and the suite builds its other cases from the footprint of the tree.

## What this gate takes from the V1 preflight, and where it differs

The V1 [multi-replica certification](../serving/kubernetes-multi-replica-certification.md#the-capacity-gate-and-why-it-is-a-gate)
has a capacity preflight. That preflight is not changed, and its record of
2026-09-12 is not changed.

| | The V1 preflight | This gate |
|---|---|---|
| What is required | Figures written in a descriptor. A test holds them to the chart | The footprint, derived from the committed values |
| Processor | Requests and 500 millicores | The same reserve. The requests include the surge pods and the hook pods |
| Memory | The sum of the memory limits and 512 MiB | The same reserve. The limits include the surge pods and the hook pods |
| Rollout headroom | Not counted | Counted, as surge pods |
| Nodes | The sum over every schedulable node | Exactly one schedulable node. More is refused |
| A pod on another node | Counted | Not counted |
| A restartable init container, and pod overhead | Not read | Read |
| A quantity that is not readable | The program fails | The record is `REFUSED`, and it names the quantity |
| The container engine | A minimum processor count and a minimum memory | Stated in the record. No rule reads it |
| The pod count | Not read | Held to the node |
| Refusal exit status | 5 | 5 |

Each requirement of this gate is larger than the V1 figure for the same
Deployments: 300 millicores more, and 1,207,959,552 bytes (1,152 MiB) more of
memory limits. A test holds both differences.

**The engine minimum is the one V1 check that this gate does not make.** The V1
preflight refuses an engine with fewer than 4 processors, or with less than
9,126,805,504 bytes of memory. This gate reads the node, because the node's
allocatable figures are what the scheduler places against. A node that this gate
accepts allocates at least 9,865,003,008 bytes, which is more than the V1 memory
minimum. **For the processor, this gate can accept less than the V1 minimum.**
It requires 3,110 millicores that no counted pod requests, and a node that
allocates fewer than 4 processors can have that.

On one document that both read, this tool and the V1 measuring program give the
same four sums. A test runs the program that the V1 script holds.

## What a record does not establish

- A record does not establish that a pod of the release is scheduled, starts, becomes Ready, or answers a request.
- A record does not establish the memory or the processor time that a pod uses. The gate compares stated requests and stated limits with the figures that the node allocates.
- A record does not establish the use of a pod that states no request. The gate counts that request as zero. The record states how many pods state none.
- A record does not establish that the node's disk holds the images, the volume of the model cache claim, or an emptyDir volume.
- A record does not establish capacity at another time. It is one reading, and the cluster can change after it.
- A record does not establish capacity for a pod that the footprint does not state. A load generator and an experiment driver are not in the footprint.
- A record does not establish capacity on more than one node, and it does not establish that the release continues to serve when the node fails.
- A record does not establish throughput, latency, an overload threshold, or availability.
- A record does not establish an evidence level, and it registers no claim.

Four more limits are of the gate, and not of one record.

- **The gate is not a model of inference capacity.** It adds stated requests and
  limits. It states nothing about how many requests a replica serves.
- **The reserve is a fixed figure.** It is not derived from a measurement of
  this host or of this release.
- **The record of a collection is built from the footprint that the collection
  stores.** The command compares that footprint with the committed files. The
  check of the committed collections does not, because a later tree can declare
  other figures.
- **The script is not the first reader of the cluster.** The target verification
  reads the cluster before the footprint is written.

## Where the gate is checked

- `tests/domain/test_capacity_preflight.py` gives the tool each quantity, each
  insufficient cluster, each ambiguous cluster, and each directory that is not a
  collection. It compares the footprint with a render of the chart.
- `tests/architecture/test_capacity_preflight_collector.py` reads the script, and
  it executes the script against stubs of `kubectl`, `kind`, `docker`, and `git`.
  It holds that each `kubectl` call is a read.

Both suites are in the default lane. They contact no cluster.
