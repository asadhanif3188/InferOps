# The Ready endpoint state of the API Service and the runtime Service

Status: **the collector and the record tool are implemented, and synthetic cases show a reading and each kind of refusal at evidence level C0. No Service and no EndpointSlice of a cluster was read: on 2026-10-09 the one local cluster held no release. So no record on this page states what a cluster published.**

A release renders two Services: one for the platform API and one for the serving
runtime. Kubernetes publishes, for each Service, the pods behind it and whether
each is Ready. This page describes how that state is captured as one record:
what is read, what a record states, each rule, the identities, the bounds, and
what a record does not establish.

The capture has two parts.

1. **`scripts/environment/service-endpoint-state.sh` reads the cluster and writes
   one directory, the collection.** It changes nothing in the cluster, and it
   sends no request to the release. It writes the collection under `.artifacts/`.
   Its target verification writes the target's kubeconfig under `.kube/`, as it
   does for every platform workflow.
2. **`tools/service_endpoint_state` reads the collection and prints one record.**
   It reads files and contacts no cluster. The result of a record is `OBSERVED`
   or `REFUSED`.

**A record counts. It does not judge.** It does not say whether a count is the
expected count. A record with zero Ready endpoints is `OBSERVED`, because zero is
a reading. A record is `REFUSED` only when the collection does not give one
unambiguous reading.

## What a record is not

**A record is not caller truth.** A Ready endpoint is a pod whose readiness the
cluster published. It is not a request that a caller sent and had answered. The
collector holds no `curl`, no port-forward, and no process inside a pod, and a
test holds that. A caller's result is a separate signal with a separate source,
and it is not derived from this record. A period in which the two signals
disagree is an observation, and this record does not remove it.

**A Prometheus `up` series is not this signal.** The chart's scrape jobs
discover pods by label, with the Prometheus role `pod`. They read no Service and
no EndpointSlice, and they do not select on the pod's Ready condition. So `up`
states that one scrape of one pod's metrics port succeeded. It does not state
that the pod is Ready, and it does not state how many endpoints a Service has.
This tool reads no metric.

**A record is one reading. It is not a timeline.** It states what two calls
returned between two instants. It holds no transition, and it does not state the
moment at which an endpoint stopped being Ready. A caller that needs a timeline
must take one reading for each sample, and must treat a read that did not answer
as no reading for that sample.

## What is read: the collection

The collector reads the release that the environment scripts name: the release
`inferops` in the namespace `inferops-release`.

| File | The read |
|---|---|
| `services.json` | `kubectl get services` in the release namespace, selected by the release's instance label, as JSON |
| `endpointslices.json` | `kubectl get endpointslices.discovery.k8s.io` in the release namespace, as JSON |
| `run.json` | The header, which the collector writes: the schema, the provider, the namespace, the release, the commit of the working tree, and the two instants |
| `record.v1alpha1.json` | The record that the tool gives for the three files above |

**A read that does not answer is not an empty result.** The collector writes no
file for it. The record then states that read as not made, and it states no
endpoint count.

The two instants are `readStartedAt` and `readFinishedAt`. Each is the
collecting host's clock in UTC, to one second. The collector takes the first
before the Service read and the second after the EndpointSlice read.

The header names the provider. It does not name the kubeconfig context, because a
context name can hold an account identifier. The tool refuses a header with any
member that it does not expect.

The commit in the header is the commit of the working tree that ran the
collector. The collector does not refuse a working tree with changes, and the
record does not state that the tree was clean. The record reads no file of the
tree.

**A collection holds what the cluster returned.** It holds pod addresses and
node names. A record holds neither. The directory `.artifacts/` is not tracked.

## What a record states

The schema name is `inferops.io/service-endpoint-state/v1alpha1`. A record
states two tiers, in one order: `platform-api` and `serving-runtime`. Each name
is the component label that the chart gives the Service of that tier.

For each tier, a record states:

| Member | Meaning |
|---|---|
| `state` | `observed`, `refused`, or `not-observed` |
| `service` | The name of the one Service that carries the tier |
| `slices` | The number of EndpointSlices of that Service |
| `addressTypes` | The address types of those slices |
| `endpoints.total` | The number of pods that the slices name |
| `endpoints.ready` | The number whose `ready` condition is true |
| `endpoints.notReady` | The number whose `ready` condition is false |
| `endpoints.serving` | The number whose `serving` condition is true |
| `endpoints.terminating` | The number whose `terminating` condition is true |
| `ready` | The pod name and the pod UID of each Ready endpoint |
| `notReady` | The pod name, the pod UID, `serving`, and `terminating` of each other endpoint |

A tier whose state is `refused` or `not-observed` states no figure and no pod:
each of those members is null. A tier is `refused` when a rule is not held for
it. A tier is `not-observed` when the collection gives no usable reads. When one
tier is refused, the other tier can still be `observed`, and the result of the
record is `REFUSED`. **Read `result` first.**

**A pod is counted once.** A cluster with two address families writes one slice
for each family, and each names the same pods. The tool counts a pod by its UID.

Kubernetes documents the three conditions. `ready` is true for an endpoint that
is serving and is not terminating. `serving` is the readiness of the pod without
regard to termination. `terminating` is true for a pod that is being deleted.
The record copies each condition as the slice states it, and derives none.

### The identities

An identity is a pod name and a pod UID, as the slice's `targetRef` states them.
It is valid for the life of that pod on that cluster. A replacement pod has
another name and another UID, so an identity is not a stable name for a replica.

A record omits, on purpose:

- the addresses of an endpoint;
- the node name, the zone, and the hostname of an endpoint;
- the ports and the hints of a slice;
- the name of the kubeconfig context.

### The bounds

The values that a consumer may use as a label are closed sets: two tiers, three
tier states, two results, and three rule states. A pod name and a pod UID are
not bounded, and they change at every replacement. **They are record values. They
are not label values**, and nothing in this repository writes one to a metric.

A record states at most 32 pods for one Service. That is the 16 replicas and the
16 pods of surge that the chart's values schema admits for a tier. A Service with
more is refused, and the record lists none of its pods. A test compares the
number with the schema.

## The rules

Nine rules decide the result. The first two are about the collection, and the
others are evaluated for each tier. A rule has one of three states: `held`,
`not-held`, or `not-observed`. A rule is `not-observed` when an earlier rule left
it unread. The result is `OBSERVED` when every rule is held. In every other case
it is `REFUSED`, and `refusedBy` names each rule that is not held or not
observed.

| Rule | It holds when |
|---|---|
| `each-read-was-made` | The collection holds `services.json` and `endpointslices.json` |
| `each-read-has-the-shape-of-its-kind` | Each read is a list of objects of its kind, in the namespace that the header names, and each member that a rule reads has its type |
| `one-service-carries-each-tier` | For each tier, exactly one Service of the release carries the component label of that tier |
| `the-service-publishes-ready-addresses-only` | The Service does not set `publishNotReadyAddresses` |
| `the-slice-controller-wrote-each-slice` | Each slice of the Service carries the managed-by label of the Kubernetes EndpointSlice controller |
| `each-endpoint-states-its-conditions` | Each endpoint states `ready`, `serving`, and `terminating`, each as true or false |
| `each-endpoint-names-one-pod` | Each endpoint names one Pod of the namespace, by name and by UID |
| `one-pod-has-one-state` | A pod that more than one endpoint names has the same three conditions in each, and one pod name has one UID |
| `the-endpoint-count-is-within-the-bound` | The Service has at most 32 pods behind it |

Four of these need a reason.

- **`the-service-publishes-ready-addresses-only`.** Kubernetes documents that a
  Service with `publishNotReadyAddresses` publishes each endpoint as ready,
  whatever its pod reports. For such a Service, `ready` says nothing about a pod.
  The chart's two Services do not set it, and a test holds that.
- **`each-endpoint-states-its-conditions`.** Kubernetes documents that a consumer
  reads an unstated `ready` as true. This tool does not apply that reading. An
  endpoint that states no `ready` is not counted as Ready: its tier is refused.
- **`the-slice-controller-wrote-each-slice`.** A slice with another writer does
  not state what the EndpointSlice controller derived from a pod's readiness.
- **`one-service-carries-each-tier`.** The `mock` profile renders no runtime
  Service. A reading of such a release is refused for the runtime tier. The tool
  reads the two-tier release.

**A member of another type is not read as absent.** A `ready` that is the text
`"true"`, an `endpoints` member that is an object, or a slice in another
namespace each break `each-read-has-the-shape-of-its-kind`. No tier is then read.

## How to run it

```sh
INFEROPS_PROVIDER=<provider> scripts/environment/service-endpoint-state.sh [--into NAME]
```

The script verifies the target first, as every platform workflow does. It then
writes `.artifacts/service-endpoint-state/collections/<NAME>`. Without `--into`,
the name is the UTC time of the run. The script does not write into a directory
that exists.

| Exit status | Meaning |
|---|---|
| 0 | The record is `OBSERVED`. This does not say that a Service has a Ready endpoint |
| 5 | The record is `REFUSED`. The directory is kept |
| 1 | No record was written |

The tool reads a collection that exists:

```sh
python -m tools.service_endpoint_state DIRECTORY
python -m tools.service_endpoint_state --check
```

The first command prints the record, with the same exit statuses 0 and 5, and 1
for a directory that is not a collection. `--check` builds the record of each
committed collection again and compares it with the committed record.

A caller that samples a cluster repeatedly can use the function `observe` of the
package for each sample. That function takes the items of the two reads, and it
does not hold them to their shape: `build_record` does that first.

## The committed cases

Six collections are committed under
[`tests/domain/fixtures/service-endpoint-state/`](../../tests/domain/fixtures/service-endpoint-state/).
**Each is written by the suite. The pod names, the UIDs, and the addresses are
invented, and no case states what a cluster did.** A test holds that each
committed file is what the suite's builders give.

| Case | Result | What it shows |
|---|---|---|
| `observed-two-ready-for-each-tier` | `OBSERVED` | Two Ready endpoints for each Service |
| `observed-no-ready-runtime-endpoint` | `OBSERVED` | One runtime pod that is terminating and one that is not yet Ready: zero Ready endpoints, as a reading |
| `observed-two-address-families` | `OBSERVED` | Two slices that name the same two pods: two pods, counted once each |
| `refused-slice-read-not-made` | `REFUSED` | The EndpointSlice read did not answer: no count is stated |
| `refused-no-runtime-service` | `REFUSED` | No Service carries the runtime tier |
| `refused-service-publishes-not-ready-addresses` | `REFUSED` | The runtime Service sets `publishNotReadyAddresses` |

## What a record does not establish

- **That a caller obtains a completion.** See [What a record is not](#what-a-record-is-not).
- **That a request reaches a Ready endpoint.** The node's proxy applies a slice
  after the slice changes. The record does not read the proxy.
- **That a pod behind a Ready endpoint can serve inference.** Ready states the
  result of the pod's readiness probe, as the kubelet reported it. For the
  runtime, that probe asks the runtime's health endpoint. For the API, it asks
  the API's own readiness, which does not follow the runtime
  ([ADR 0020](../architecture/decisions/ADR-0020-api-readiness-is-the-apis-own-answer.md)).
- **The state before the read started or after it finished.**
- **That the release is the declared release.** The record reads no image, no
  revision, and no Argo CD state.
- **What a caller observes when a pod is deleted, evicted, or replaced, and that
  the release survives the loss of a node.** Those need an executed experiment
  with a caller. [The disruption budgets](disruption-budgets.md) states what a
  budget bounds and what it does not.

The limits of one reading:

- The two reads are two calls. They are not one atomic reading, and a pod can
  change between them.
- The two instants are the collecting host's clock. They are not compared with a
  clock of the cluster.
- The record reads one namespace and the Services of one release in it.
- No Service and no EndpointSlice of a cluster was read for this page. The collector was executed against stand-ins
  for `kubectl` only, so its behaviour against an API server was not observed.

## Where the capture is checked

- [`tests/domain/test_service_endpoint_state.py`](../../tests/domain/test_service_endpoint_state.py)
  holds the tool: the counts, each rule, the bound, the header, the omitted
  members, the command, and this page's rule table.
- [`tests/architecture/test_service_endpoint_state_collector.py`](../../tests/architecture/test_service_endpoint_state_collector.py)
  holds the collector: that each kubectl call is a read, that the script sends
  nothing to the release, that it agrees with the tool, and, executed against
  stand-ins, that a read that does not answer leaves no file and refuses.
