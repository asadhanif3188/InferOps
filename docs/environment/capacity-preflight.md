# The capacity preflight for the two-replica release

Status: **the gate is implemented, and synthetic cases show an acceptance and each kind of refusal at evidence level C0. Three readings of one cluster are committed, each of 2026-10-09 on the `docker-desktop` provider and each with the result `ACCEPTED`. Two are whole collections, and one is a record with part of its collection. None is a qualification of that host. An acceptance compares stated requests and limits with what one node allocates. It does not establish that a pod is scheduled or starts.**

The desired-state release declares two platform API replicas and two serving
runtime replicas. This page describes the gate that decides, before anything is
installed, whether the stated requests and limits of that release fit in what
one node of a cluster allocates: what it reads, what it requires, each rule,
each unit, and what a record does not establish.

The gate has two parts.

1. **`scripts/environment/capacity-preflight.sh` reads the cluster and writes one
   directory, the collection.** It changes nothing in the cluster or in the
   container engine. It writes the collection under `.artifacts/`. Its target
   verification writes the target's kubeconfig under `.kube/`, as it does for
   every platform workflow.
2. **`tools/capacity_preflight` reads the collection and prints one record.** It
   reads files and contacts no cluster. The result of a record is `ACCEPTED` or
   `REFUSED`.

**A refusal is a result.** The gate lowers no request, no limit, no replica count,
and no reserve to obtain an acceptance. A cluster that is refused stays refused
until the cluster or the committed release changes.

The gate derives the footprint of the desired-state release only. Since
`V2-S4-003-PR2` a [single-runtime baseline profile](single-runtime-baseline-profile.md)
exists, with one runtime replica. No Application names it, so the gate gives no
footprint for it.

## What the gate requires: the declared footprint

The footprint is read from files of the working tree, and not from the cluster.
`python -m tools.capacity_preflight --footprint` prints it. The tool reads
[the Application](argocd-application.md) of the desired-state release, which
names the chart and one values file. The values are the chart's defaults, then
the release's [generated values](git-desired-state.md), then the values that the
Application states itself. A later document replaces a member of an earlier one,
as Helm merges values documents, and a null removes a member.
[ADR 0019](../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
states that order for the Application.

**The tool reads the files as the tree holds them. It reads no commit.** The
script records the commit that `HEAD` names, and it refuses a working tree that
differs from that commit. Neither compares that commit with the revision that
the Application names, which is a branch of a remote repository. The footprint
states that revision and the repository address as the Application writes them.

**The Application is read against a list of members.** The tool reads the
project, the source, the destination, and the sync policy of `spec`; the
repository address, the revision, the path, and the Helm block of the source;
and the release name, the values file, and the values object of the Helm block.
It gives no footprint for an Application that states another member, such as a
second source, a parameter, or inline values. The procedure that applies the
Application adds the API image digest as one Helm parameter. That parameter is
not in the committed file, and the tool does not read the applied object.

**The footprint states processor and memory only.** The tool gives no footprint
for a container that requests or limits another resource. No rule compares one.

The tool restates which pods the chart renders. A test renders the chart with
the same values and compares each pod template of the render with the footprint:
the replicas, the surge, and the name, the requests, and the memory limit of
each container. A pod that the chart renders and the footprint does not state
fails that test.

At chart version `0.6.0` the footprint is:

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

The footprint states the pods that each Deployment's rollout bounds permit
beyond its replica count, as surge pods. No rollout of this release was run
under these bounds, so none of this was observed.

- **The platform API surges by one pod.** Its strategy states 0 unavailable and
  1 surge.
- **The serving runtime surges by no pod.** Its strategy states 1 unavailable
  and 0 surge, so the footprint holds no third runtime pod.
  [The chart's README](../../charts/inferops-llm/README.md) describes that
  strategy.
- **The telemetry collector surges by one pod.** The chart states no strategy
  for this Deployment. The Kubernetes documentation states the default surge of
  a Deployment as 25 percent of its replicas, rounded up, which is one pod for
  one replica.

**The footprint does not count a pod that is terminating.** The Kubernetes
documentation of the Deployment states that a terminating pod is not counted
against the rollout bounds. The chart gives each pod a termination grace period
of 30 seconds. So during a rollout a runtime pod that is terminating can hold
its request beside the pod that replaces it, and the gate requires no room for
that. A replacement that does not fit then waits until the old pod is gone.
This was not observed.

### Transient pods

The model acquisition hook is one Job pod. The chart's test hook is one pod. The
gate counts both beside the Deployments and the surge pods.

**The gate requires room for all of them at one time. That was not observed.**
The chart annotates the acquisition Job as a hook that runs before an install
and before an upgrade. Whether a hook pod, a surge pod, and a test pod exist at
one time was not observed. On the one provider where the Application was
applied, Argo CD ran the hook before the sync, and no pod of the test hook was
listed ([the Application page](argocd-application.md)). With the terminating
pods above, the sum is not an upper bound on what a rollout can hold.

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

The gate holds two of these figures and the pod count to the node. The reserve
applies to the processor and to memory, and not to the pod count. The gate
holds the **processor requests**, which is the V1 preflight's rule. It
holds the **memory limits**, and not the memory requests, because a serving
runtime loads a model of 1,834,426,016 bytes and can use its whole limit.
The tool gives no footprint for a pod whose memory limit is below its memory
request, so a node that holds the memory limits also holds the memory requests. The record states the memory requests, and no
rule reads them.

## What the gate reads: the collection

The script verifies the selected target first, as every platform workflow does
([the provider contract](local-cluster-provider-contract.md)). That verification
reads the cluster and the engine. The script then refuses a working tree that
differs from the commit `HEAD` names, writes the footprint, and makes its own
reads. Each of those is one `kubectl get` or `kubectl version`, or one
`docker info`.

| File | What it holds |
|---|---|
| `footprint.json` | What `python -m tools.capacity_preflight --footprint` printed before the script collected a read. Schema `inferops.io/capacity-preflight-footprint/v1alpha1` |
| `run.json` | The provider, the context, the release key, the release namespace, the commit that `HEAD` named, and the time. Schema `inferops.io/capacity-preflight-collection/v1alpha1` |
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

**A document of another form is not read as absent.** A node or an unfinished pod
whose kind, name, or member has another type than the tool reads refuses the
cluster: a container list that is not a list, a taint that states no known
effect, a pod that names a node the read does not hold. A pod list without a
pod refuses too. A cluster with a Ready node holds the pods of its own system,
so an empty list is not read as a cluster that holds nothing.

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
the node's `capacity` and its allocatable ephemeral storage. No sufficiency rule
compares them. One that is not a readable quantity fails `quantities-readable`.

**More than one schedulable node is refused as ambiguous.** The gate does not
decide where a pod is placed among nodes. The model cache claim is
`ReadWriteOnce`, and the Kubernetes documentation states that such a claim is
mounted by pods of one node. So a sum over two nodes says nothing about whether
both runtime pods fit on one of them.

### The reservations

A reservation is the request of a pod that the node already holds. The gate
counts each pod that is not `Succeeded` or `Failed`, and that the one
schedulable node holds or that no node holds yet. It does not count a pod on
another node. A pod that is terminating is counted until its phase is
`Succeeded` or `Failed`. Without exactly one schedulable node there is no node
to count against, and the record states no count.

The request of one pod follows the arithmetic that the Kubernetes documentation
gives. A request that the pod states for itself is its request. Without one, the
request is the larger of two figures: the sum over the containers and the
restartable init containers, and the largest init container beside the
restartable init containers that start before it. The pod's overhead is added.
A request that a pod states for itself is a feature that a cluster can have
disabled. The tool reads the member when a pod states it.

**A container that states no request is counted as zero.** The sum is a sum of
stated requests, and such a container adds nothing to it. Its use is not
measured. The record states how many counted pods have such a container or
init container, for the processor and for memory. On 2026-10-08, on
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

13 rules. 12 are required. Each rule has one of three states.

| State | Meaning |
|---|---|
| `held` | The reads show the statement |
| `not-held` | One read contradicts the statement |
| `not-observed` | The rule could not be decided. A read that it needs was not made; or, for a sufficiency rule, a document has another form, a quantity is not readable, an allocatable figure is absent, or there is not exactly one schedulable node; or, for the claim rule, the claim is absent or states no size |

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
| `reads-well-formed` | ambiguous | Each node and each unfinished pod has the kind, the name, and the member types that this tool reads, each placed pod names a node of the read, and the pod list is not empty. |
| `quantities-readable` | ambiguous | Each processor, memory, pod, and ephemeral-storage figure of each node, each request of each counted pod, and each size of the model cache claim is a Kubernetes quantity that is not negative. |
| `one-schedulable-node` | ambiguous | The cluster has exactly one schedulable node. |
| `node-ready-without-pressure` | ambiguous | The schedulable node reports Ready as True, it reports each of the memory, disk, and process pressure conditions as False, and it does not report the network as unavailable. |
| `node-states-no-blocking-taint` | ambiguous | The schedulable node states no taint with the effect NoSchedule or NoExecute. |
| `release-states-no-placement-constraint` | ambiguous | The footprint states no node selector, no toleration, and no affinity. |
| `namespace-states-no-quota-or-limit-range` | ambiguous | The release namespace holds no ResourceQuota and no LimitRange. |
| `release-is-not-installed` | ambiguous | The release namespace holds no unfinished pod of the release. |
| `pod-count-fits` | insufficient | The pods of the footprint fit in the pod count that the node allocates, less the unfinished pods that the node holds. |
| `cpu-requests-fit` | insufficient | The processor requests of the footprint and the reserve fit in the processor that the node allocates, less the processor that the unfinished pods request. |
| `memory-limits-fit` | insufficient | The memory limits of the footprint and the reserve fit in the memory that the node allocates, less the memory that the unfinished pods request. |
| `model-cache-claim-holds-artifact` (not required) | insufficient | The model cache claim is not Lost, and the smaller of its capacity and its request is at least the byte count of the model artifact. |

The last rule is not required, because the gate can run before
[the prerequisite layer](platform-prerequisites.md) creates the claim. An absent
claim is `not-observed` and does not refuse. **An accepted record with an absent
claim does not say that the release can start**: each serving runtime pod mounts
that claim, and the release does not create it. A claim that exists refuses when
its phase is `Lost`, or when the smaller of its capacity and its request is
below the artifact's byte count. A claim that is not bound states a request and
no capacity. The rule does not read the disk behind the claim.

The node rule reads four conditions. The node must report `Ready` as `True` and
each of `MemoryPressure`, `DiskPressure`, and `PIDPressure` as `False`. A
pressure condition that the node does not report is not read as `False`.
`NetworkUnavailable` is not a pressure condition, and a node need not report it.
When a node reports it, it must be `False`.

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
| 1 | No record was written. The script refuses an argument it does not know, a name that is not usable or that exists, a target that is not verified, a working tree whose commit or state it cannot read, a working tree that differs from its commit, and files that give no footprint. The tool refuses a directory that is not a collection |

The tool alone:

```sh
uv run --locked python -m tools.capacity_preflight --footprint
uv run --locked python -m tools.capacity_preflight DIRECTORY
uv run --locked python -m tools.capacity_preflight DIRECTORY --as-collected
uv run --locked python -m tools.capacity_preflight --check
```

`DIRECTORY` prints the record, with the same exit statuses. Before it builds a
record, it compares the stored footprint with the footprint that the files of
the tree give now, and it prints no record when they differ. So a collection that
was written for fewer replicas, or for smaller requests, is not a gate for the
declared release. `--as-collected` skips that comparison, for a collection that
an earlier tree wrote. **With `--as-collected`, exit status 0 says only that a
record was printed.** It does not say that the result is `ACCEPTED`.

**A stored footprint is not trusted for its arithmetic.** The tool computes each
derived figure again from the stated quantities, and it requires its own
reserve. A footprint whose figures differ is not a collection.

## The committed cases

`tests/domain/fixtures/capacity-preflight/` holds six collections that no
cluster produced, each with its record. The suite's own builders wrote each
document. Their header states the provider `synthetic` and a commit of forty
zeros. `--check` builds each record again and compares it with the committed
record. The figures of `accepted-one-node` are also those of
the first committed reading below: the node's allocatable figures, and nine pods that request
950 millicores and 304,087,040 bytes.

| Case | Result | What it shows |
|---|---|---|
| `accepted-one-node` | `ACCEPTED` | One node with room, nine system pods, and a bound claim |
| `refused-insufficient-memory` | `REFUSED`, `insufficient` | The same cluster with 8 GiB of allocatable memory. The memory limits do not fit |
| `refused-insufficient-processor-and-pods` | `REFUSED`, `insufficient` | A node with 4 processors and 16 pods. Two figures are short, and the record names both |
| `refused-ambiguous-two-nodes` | `REFUSED`, `ambiguous` | Two schedulable nodes of 64 processors and 256 GiB each |
| `refused-ambiguous-read-not-made` | `REFUSED`, `ambiguous` | A collection without `pods.json` |
| `refused-ambiguous-release-installed` | `REFUSED`, `ambiguous` | A runtime pod of the release in the release namespace |

Each case stores the footprint of chart version `0.5.0`. A later chart can
declare other figures. The cases then show the gate's arithmetic on the stored
footprint, and the suite builds its other cases from the footprint of the tree.

## Two later readings

> **Note, 2026-10-09 (`V2-S4-005-PR2`).** Two more readings are committed. Both were
> taken on the `docker-desktop` provider at commit
> `25f2cfbfe587e0e0c76ceb519cb90f6ef0e09810`, which is a commit of `main`, in the run
> that read the [Service endpoints](service-endpoint-state.md#one-reading-of-a-cluster)
> once. [The first](../proof/environment/v2-s4-005-pr2-capacity-preflight-run-1-before-install/record.v1alpha1.json)
> was taken before anything was installed: `ACCEPTED`, with the claim rule
> `not-observed`. [The second](../proof/environment/v2-s4-005-pr2-capacity-gate-before-apply/record.v1alpha1.json)
> was taken after the model cache claim was filled and the controller was installed,
> and before the Application was applied: `ACCEPTED`, with each of the 13 rules `held`.
> Both state 9,865,003,008 bytes required and 10,126,585,856 available. The release
> was then installed, and both rollouts reported success. That is one install on one
> host. It is not a qualification of that host. The second reading is committed without
> its read of every pod of the cluster, so `--check` does not build its record again:
> [the validation record](../proof/environment/v2-s4-005-pr2-validation.md#what-is-committed)
> states why. The section below describes the first committed reading, of the change
> that added the gate.

## The one committed reading

[`docs/proof/environment/v2-s4-003-pr1-capacity-preflight-run-1/`](../proof/environment/v2-s4-003-pr1-capacity-preflight-run-1/record.v1alpha1.json)
holds one collection that the script wrote on 2026-10-09 on the `docker-desktop`
provider, with its record.
[The transcript](../proof/environment/v2-s4-003-pr1-capacity-preflight-run-1-transcript.txt)
is what the script printed. `--check` builds the record again from the
collection.

| Property | Value |
|---|---|
| Result | `ACCEPTED`. 12 rules `held`, and the claim rule `not-observed` |
| Commit of the working tree | `479ffda591b484edcd9ee19e1e040b6aee542124`, a commit of the branch of this change. It is not a commit of `main`, which is the revision that the Application names. At that commit the files of the footprint are the same on both |
| Cluster | One node, server `v1.36.1`. Nine unfinished pods, all of the cluster's own system. No pod of this project, and no Argo CD installation |
| The node allocates | 12,000 millicores, 10,430,672,896 bytes, 110 pods |
| The nine pods request | 950 millicores and 304,087,040 bytes. Two state no processor request, and five state no memory request |
| Pod count | 9 required, 101 available |
| Processor requests | 3,110 millicores required, 11,050 available |
| Memory limits | 9,865,003,008 bytes required, 10,126,585,856 available: 261,582,848 bytes (about 249 MiB) more than required |
| Model cache claim | The read of the release namespace returned no claim, so the claim was not observed |

**What this reading does not establish.**

- It does not establish that the release fits on that host when it is
  reconciled. A reconciled release needs an Argo CD installation. On 2026-10-08
  its pods stated no request, so the gate would count them as zero, and their
  use is not measured. The memory margin of this reading is smaller than the
  512 MiB reserve.
- It does not establish that two runtime pods start there. In the one run that
  started them, on 2026-10-08, both API pods were restarted once by their
  startup probe ([the record](../proof/environment/v2-s4-002-pr2-validation.md)).
  This gate reads no such thing.
- It is one reading. The V1 preflight refused the same provider on 2026-09-12,
  when other workloads held memory there.
- It is not the qualification of an environment for an experiment. No
  experiment was run, and no claim is registered.

## What this gate takes from the V1 preflight, and where it differs

The V1 [multi-replica certification](../serving/kubernetes-multi-replica-certification.md#the-capacity-gate-and-why-it-is-a-gate)
has a capacity preflight. That preflight is not changed, and the record of its
refusal on 2026-09-12
([the paved road on Docker Desktop](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md))
is not changed.

| | The V1 preflight | This gate |
|---|---|---|
| What is required | Figures written in a descriptor. A test holds them to the chart | The footprint, derived from the committed values |
| Processor | Requests and 500 millicores | The same reserve. The requests include the surge pods and the hook pods |
| Memory | The sum of the memory limits and 512 MiB | The same reserve. The limits include the surge pods and the hook pods |
| Rollout headroom | Not counted | Counted, as surge pods |
| Nodes | The sum over every schedulable node | Exactly one schedulable node. More is refused |
| A pod on another node | Counted | Not counted |
| A restartable init container, and pod overhead | Not read | Read |
| A quantity that is not readable | A blank is read as zero. For another text the program fails | The record is `REFUSED`, and it names the quantity |
| A document of another form | Not checked | The record is `REFUSED` |
| The container engine | A minimum processor count and a minimum memory | Stated in the record. No rule reads it |
| The pod count | Not read | Held to the node |
| Refusal exit status | 5 | 5 |

Each requirement of this gate is larger than the V1 figure: 300 millicores
more, and 1,207,959,552 bytes (1,152 MiB) more of memory limits. The V1 figure
is the same three Deployments and one pod with the resources of the chart's
test pod. A test holds both differences.

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
- A record does not establish the use of a pod that states no request. The gate counts that request as zero. The record states how many counted pods have a container or an init container that states none.
- A record does not establish that the footprint is the release that a controller applies. The footprint is read from the files of one working tree. The record does not compare that tree with a commit, or with the revision that the Application names.
- A record does not establish capacity for a pod that is terminating. The footprint counts the replicas and the surge pods. During a rollout, a pod that is terminating can hold its request beside the pod that replaces it.
- A record does not establish that the node's disk holds the images, the volume of the model cache claim, or an emptyDir volume.
- A record does not establish capacity at another time. It is one reading, and the cluster can change after it.
- A record does not establish capacity for a pod that the footprint does not state. A load generator and an experiment driver are not in the footprint.
- A record does not establish capacity on more than one node, and it does not establish that the release continues to serve when the node fails.
- A record does not establish throughput, latency, an overload threshold, or availability.
- A record does not establish an evidence level, and it registers no claim.

Seven more limits are of the gate, and not of one record.

- **The gate is not a model of inference capacity.** It adds stated requests and
  limits. It states nothing about how many requests a replica serves.
- **The reserve is a fixed figure.** It is not derived from a measurement of
  this host or of this release.
- **The record of a collection is built from the footprint that the collection
  stores.** The command compares that footprint with the files of the tree. The
  check of the committed collections does not, because a later tree can declare
  other figures.
- **The script is not the first reader of the cluster.** The target verification
  reads the cluster before the footprint is written.
- **No procedure of this repository calls the gate.** An operator runs it. An
  install or an apply that follows a refusal is not prevented by a tool.
- **The check of a committed collection does not verify where it came from.** It
  builds the record again from the committed files. It does not compare the
  digests that the footprint states with the files of the commit that the
  header names.
- **A request below one millicore is rounded up for the pod, and not for each
  container.**

## Where the gate is checked

- `tests/domain/test_capacity_preflight.py` gives the tool each quantity, each
  insufficient cluster, each ambiguous cluster, and each directory that is not a
  collection. It compares the footprint with a render of the chart.
- `tests/architecture/test_capacity_preflight_collector.py` reads the script, and
  it executes the script against stubs of `kubectl`, `kind`, `docker`, and `git`.
  It holds that each `kubectl` call is a read.

Both suites are in the default lane. They contact no cluster.
