# The infrastructure timelines of an experiment run

Status: **the collector and the stream tool are implemented, and collections that the test suites build show each stream, each state of a read, and each state of a field at evidence level C0. No cluster was read. No stream of a real run is committed, and no claim is registered. The collector was executed against stand-ins for `kubectl` only.**

An experiment run compares what a caller observed with what the cluster and the
delivery controller published at the same time. This page describes how the
second part is captured: which objects are read, what each reading states, which
clock each instant is on, and what a stream does not establish.

The capture has two parts.

1. **`scripts/environment/experiment-timeline.sh` samples the cluster a bounded
   number of times and writes one directory, the collection.** It changes nothing
   in the cluster, and it sends no request to the release. It writes the
   collection under `.artifacts/`. Its target verification writes the target's
   kubeconfig under `.kube/`, as it does for every platform workflow.
2. **`tools/experiment_timeline` reads the collection and prints four streams.**
   It reads files and contacts no cluster.

| Stream | What each reading states |
|---|---|
| `endpoints` | For the API Service and for the serving runtime Service: the number of endpoints, the number that are Ready, and the pod name and pod UID of each |
| `pods` | Each pod of the two tiers: its name, its UID, its revision, its phase, its Ready condition, the restart counts of its containers and of its init containers, and its deletion timestamp |
| `deployments` | The Deployment of each tier: its revision, its generation, its replica counts, and two conditions |
| `argo` | What the delivery controller reported about one Application: the revision it follows, the commit it resolved, the sync state, the health state, and the last operation |

**A stream states readings. It does not judge.** It does not say whether a count
is the expected count, whether a state is healthy, or whether a run passed. The
tool computes no metric and gives no verdict.

## What a stream is not

**A stream is not caller truth.** Each value is what the cluster or the delivery
controller published. None is a request that a caller sent and had answered. The
collector holds no `curl`, no port-forward, and no process inside a pod, and a
test holds that. The caller record of a run has a separate source, the
[reliability runner](../serving/reliability-runner.md), and no stream is derived
from it or feeds it. A period in which a stream and the caller record disagree is
an observation, and this tool does not remove it.

**The `argo` stream is read on its own.** Each sample makes two reads: the
workload read and the Application read. Each has its own two instants and its own
state. A workload read that did not answer does not change the `argo` stream, and
an Application read that did not answer does not change the three other streams.
A test holds both.

**A stream is not a Prometheus series, and it is not an operator event.** This
tool reads no metric, and it records no fault injection, no detection, and no
reversal. Since `V2-S5-003-PR2` those two sources have their own tools:
[the telemetry streams](experiment-telemetry.md) and
[the operator event log](experiment-operator-events.md). Neither changes a
stream of this page.

## What is read: the collection

The collector reads the release that the environment scripts name: the release
`inferops` in the namespace `inferops-release`. It reads the one Application that
the [Application procedure](argocd-application.md) delivers the release with, in
the namespace of the delivery controller. Where the cluster has the resource type
of the Application and no object has the name, the read answers with no object,
and the reading states `absent`. Where the cluster does not have the resource
type, the read does not answer, and each reading of the `argo` stream states
`unanswered`. [The reconciliation record](reconciliation-evidence.md) observed
both on one provider. No run of this collector observed either.

Before the first sample, the target verification of the script library makes
reads of its own: `kubectl config` and `kubectl version`, and `kubectl get` of
the nodes, of the pods of the system namespace, and of the storage classes. They
change nothing, and no stream holds what they return.

| File | What it holds |
|---|---|
| `collection.json` | The header, which the collector writes before the first sample |
| `sample-NNNN.workload.json` | `kubectl get services,endpointslices.discovery.k8s.io,pods,replicasets.apps,deployments.apps` in the release namespace, as JSON |
| `sample-NNNN.application.json` | `kubectl get` of the one Application by name, with `--ignore-not-found`, as JSON |
| `sample-NNNN.meta` | For each of the two reads: whether it answered, and its two instants |
| `collection.end` | The number of samples, written after the last one |
| `streams/<stream>.jsonl` | The four streams that the tool gives for the files above |

**A read that does not answer is not an empty result.** The collector writes no
file for it, and the sample states the read as `unanswered`. Each request that
`kubectl` makes for a read has a timeout of 10 seconds, and a request that passes
it makes the read `unanswered`. The timeout does not bound a read: the workload
read makes one request for each kind, so it can take longer than 10 seconds and
still answer. No run observed that the timeout ends a request that hangs.

**The collection holds the whole answer of each read.** An answer holds addresses,
node names, and the environment of each pod. Do not commit a collection. The four
stream files hold an allowlist, and they are the evidence files of a run.

The header states the collection schema, the experiment identifier and the run
identifier that the operator gave, the provider, the server version, the
namespace, the release, the Application and its namespace, the commit of the
working tree, the SHA-256 of the collector script and of its library, the number
of samples, the pause, and the request timeout. It names the provider and not the
kubeconfig context, because a context name can hold an account identifier. The
tool refuses a header with any member that it does not expect, and a header with
a member of another form. One member is an exception: a server version of
another form is kept as `malformed`, and one that the collector could not read
is `missing`.

### Bounds

| Bound | Value |
|---|---|
| Samples of one collection | 1 to 1800 |
| Pause between two samples | 1 to 30 seconds |
| Timeout of one request of a read | 10 seconds in the collector. The tool accepts a header that states 1 to 60 |
| Pods of the two tiers that one reading states | 64 |
| Containers that one reading states for one pod | 8 |

The pause is the time between the end of one sample and the start of the next. It
is not a period: a sample takes the time of its two reads. The instants of each
read state when it was made.

A collection that was interrupted has no `collection.end`. The header of each
stream then states `complete` as false, and each sample that was not written is a
reading with the read state `not-taken`.

## The clocks

A timeline needs one time basis. A stream has one, and it says where a second
clock enters.

**The time basis is the clock of the collecting host.** The collector takes one
instant before each read and one after it. A reading states them as
`read.startedAt` and `read.finishedAt`, in UTC, to one millisecond, in the form
`2026-10-12T08:00:00.000Z`. A reading of a sample that was not taken, and a
reading whose sample states no usable instants, states neither. The caller record of the reliability runner uses the
same form. The two are still two clocks: the runner's instants are the clock of
its pod.

**An instant that a cluster component wrote is on the clock of that component.**
The creation time and the deletion timestamp of a pod, the last transition time
of the Ready condition of a pod, the two times of a condition of a Deployment,
and the five instants of the Application are such values. The tool normalises
each to UTC. A value with an offset is converted. A value with no fraction of a
second keeps a resolution of one second. A value with a fraction is cut to one
millisecond and is not rounded, so a finer fraction is lost. Each such field
states its `resolution`: `second` or `millisecond`.

**The difference between the two clocks is not measured.** The header of each
stream states `skew` as `not-measured`. The end line of each stream states two
observations that the collection supports:

- `clusterInstantsAfterRead` counts the cluster instants that are later than the
  finish of the read that returned them, and states the largest difference. A
  component wrote such an instant before the read returned it, so a count above
  zero shows that its clock was ahead of the host clock by at least that
  difference. A count of zero shows nothing. A deletion timestamp is not counted,
  because Kubernetes sets it to the end of the grace period.
- `instantsOutOfOrder` names each reading whose start is before the finish of the
  reading before it. Such a reading shows that the host clock was set back.

**What ordering a stream supports.** A change is between two reads, so it is not
before the start of the earlier read and not after the finish of the later one.
With a pause of 1 second and two reads for each sample, that interval is longer
than 1 second. No order of two events inside one interval is established, and no
order under one second is established for a cluster instant.

## Absence of a signal is not a value

Each read has one of five states.

| Read state | Meaning | Values |
|---|---|---|
| `answered` | The read returned an answer that the tool can read | Yes, unless a fault of the reading says why not |
| `absent` | The read answered, and no object has the name. Only the Application read has this state | None |
| `unanswered` | The read failed, or a request of it timed out | None |
| `unreadable` | The answer is not usable: it is not one JSON object, it is not a list of the five kinds, it is another object than the named Application, its file is not in the collection, or the sample does not state whether the read answered or states no usable instants for it | None |
| `not-taken` | The collection was asked for the sample and did not write it | None |

An empty answer of the workload read is `unreadable`. It is not an empty
namespace. An answered list with no item is a reading: it states no pod and two
tiers with no Deployment.

Each field of an answered reading has one of three states.

| Field state | Meaning |
|---|---|
| `reported` | The object held the field, and the value has the form that the field needs. Only this state carries a value |
| `missing` | The object was read and did not hold the field |
| `malformed` | The field held a value of another type or of another form. The value is not copied |

No function replaces a state with zero, with false, or with a healthy value.
These cases are each a test:

- A status count of a Deployment that the API omitted is `missing`. Kubernetes
  omits a count that is zero, and it omits a count that the Deployment controller
  did not write yet. The field cannot tell the two apart, so the reading states neither.
  The `generation` and the `observedGeneration` of the same reading state whether
  the controller wrote the status for the present generation.
- A pod with no Ready condition has a `ready` that is `missing`. It is not read as
  not Ready. A Ready condition of `Unknown` keeps that value.
- A pod with no container status has a `restartCount` that is `missing`. A pod
  with one container that states no count has a sum that is `malformed`. A pod
  with no init container status has an `initRestartCount` that is `missing`.
- A field of the Application that the controller did not write is `missing`. An
  Application with no health state is not healthy and not unhealthy.
- A pod whose ReplicaSet is not in the read has a `revision` that is `missing`.

A reading that answered and cannot be reduced without a guess states no value
and lists the reason in `faults`. A pod with no usable UID, two pods with one
UID, and more than 64 pods of the two tiers each leave the `pods` reading with no
pod. A tier with no Deployment or with two has the state `refused` and no count.

## The four streams

A stream is a text file of JSON lines. The first line is the header, each
following line is one reading, and the last line is the end line. Each line has
sorted members, so one collection gives one text. The schema name is
`inferops.io/experiment-timeline/v1alpha1`.

**`endpoints`.** The tiers are those of the
[endpoint-state record](service-endpoint-state.md), and the same rules decide
them: this tool calls that tool for each sample. A tier states what a tier of
that record states: `tier`, `state`, `service`, `slices`, `addressTypes`, the
five counts of `endpoints`, the pods in `ready`, and the pods in `notReady` with
`serving` and `terminating` for each. A tier that a rule refuses states no count.
The reading lists the rule and the tier in `faults`. It does not copy the detail
of that tool, because a detail can quote a name of the answer.

**`pods`.** A pod is listed when it carries the instance label of the release and
the component label of one of the two tiers. Every other pod of the namespace is
counted in `otherPods` and is not listed. For each listed pod the reading states
`name`, `uid`, `tier`, `templateHash`, `owner`, `revision`, `phase`, `ready`,
`readyTransitionAt`, `containers`, `restartCount`, `initContainers`,
`initRestartCount`, `createdAt`, `deletionTimestamp`, and
`deletionGracePeriodSeconds`. The `revision` is the revision annotation of the
ReplicaSet that owns the pod. The `restartCount` is the sum over the containers
of the pod. The `initRestartCount` is the sum over its init containers, and it is
a field of its own: a pod whose init container restarts reports no restart of a
container. A restart of an ephemeral container is not read. The
`deletionTimestamp` of a pod is the instant at which its grace period ends.
Kubernetes documents that the request to delete the pod is earlier by
`deletionGracePeriodSeconds`. Both values are to one second, and a second request
with a shorter grace period replaces both.

**`deployments`.** For each tier the reading states `tier`, `state`, the `name`
and the `uid` of the one Deployment, its `revision`, and eight counts: `generation`,
`observedGeneration`, `specReplicas`, `replicas`, `updatedReplicas`,
`readyReplicas`, `availableReplicas`, and `unavailableReplicas`. It states the
`Available` and the `Progressing` condition: the status, the reason, and the two
instants. It does not state a message.

**`argo`.** The reading states ten fields of the Application and three of the last
entry of its history. The names are those of the
[reconciliation record](reconciliation-evidence.md).

| Field | Path in the Application |
|---|---|
| `followedRevision` | `spec.source.targetRevision`: the revision that the Application follows |
| `resolvedRevision` | `status.sync.revision`: the commit that the controller resolved and compared with |
| `syncStatus` | `status.sync.status` |
| `healthStatus` | `status.health.status` |
| `operationPhase` | `status.operationState.phase` |
| `operationRevision` | `status.operationState.syncResult.revision`: the commit of the last sync operation |
| `operationStartedAt`, `operationFinishedAt` | The two instants of the last operation |
| `reconciledAt` | `status.reconciledAt` |
| `deletionTimestamp` | `metadata.deletionTimestamp` |
| `historyId`, `historyRevision`, `historyDeployedAt` | The last entry of `status.history` |

A resolved revision is a full commit identifier, and any other value is
`malformed`. The tool does not compute whether the Application is settled, and it
compares no commit with a provenance. The reconciliation record does both.

### What a stored stream is held to

`python -m tools.experiment_timeline check` reads stored streams. It holds each
one to nine rules.

| Rule | Statement |
|---|---|
| `timeline-stream-unreadable` | A stream is UTF-8 text. Each line is one JSON object with no member stated twice. |
| `timeline-header-unsupported` | The first line is the header. It states the stream schema, one of the four stream names, an experiment identifier, and a run identifier, each in its form. |
| `timeline-members-unsupported` | Each line has exactly the members of its record and of its stream. |
| `timeline-reading-out-of-sequence` | Each line between the header and the end line is a reading, and the readings are numbered from 1 with no gap. |
| `timeline-read-state-unsupported` | Each reading states one of the registered read states. |
| `timeline-instant-invalid` | Each instant of a read is absent or is UTC to one millisecond in the one registered form, and a read does not finish before it starts. |
| `timeline-reading-unsupported` | Each reading states its faults as a list of text, and states a value only when its read answered. Each value that the changes command reads has its type. Only a reading of the argo stream has the read state absent. |
| `timeline-end-missing` | The last line is the end line, and no line follows it. |
| `timeline-counts-differ` | The end line states the number of readings and the number of readings in each read state, as the stream holds them. |

**The check reads the form of a stream.** It holds each value that the `changes`
command reads to its type, so that command does not fail on a stream that the
check accepts. It does not hold a reported value to the form that the builder
holds it to: a stored stream with a pod name of another form is accepted. It
does not read a field that `changes` does not track. It does not show that a
stream is what a collection gives: the collection is not committed, so no check
can build the stream again.

## Changes

`python -m tools.experiment_timeline changes FILE` compares each reading of one
stored stream with the next one and prints each tracked value that differs. A
change states the two readings and two bounds: `notBefore` is the start of the
earlier read, and `notAfter` is the finish of the later read.

| Stream | Tracked values |
|---|---|
| `endpoints` | For each tier: the state, the five counts, and the UIDs of the Ready pods |
| `pods` | For each pod UID: whether it is `present`, and `ready`, `phase`, `restartCount`, `initRestartCount`, `revision`, and `deletionTimestamp` |
| `deployments` | For each tier: the state, the `revision`, and the eight counts |
| `argo` | Whether the Application is `present`, and each of its thirteen fields |

- A value that was reported and is then not reported is a change to that state.
  A count that stops being reported is a change to `missing`. It is not a change
  to zero.
- No value is carried across a reading that gave none. A reading that is not
  answered gives a change to `not-collected` and, at the next answered reading, a
  change from it.
- A reading that answered and states no value for the stream gives a change to
  `refused`: a `pods` reading with a pod that has no usable identity, and a tier
  that a rule refuses. Two consecutive readings that give no value have no
  tracked value to compare. When one is `not-collected` and the other is
  `refused`, one change names the subject `reading`.
- A pod that is in one reading and not in the next gives one change of `present`
  to `absent`. A pod that enters gives one change from `absent`. **No change says
  that one pod replaced another.** An analysis that pairs the two states that
  itself.
- The word `absent` has two uses. As the state of a change it says that an
  answered reading held no such pod. As a read state it says that the Application
  read answered with no object, and the change then states `present` as false.

The changes document is computed from a stream. It is a derived file, and it
holds no value that the stream does not hold.

## Identities, and what a stream leaves out

Each text value of a reading is held to a fixed form before it is stored: a
Kubernetes name, a label value for a container name, a UID, a commit identifier,
a word, a template hash of at most 16 characters, an instant, and, for the
revision that the Application follows, a reference name of at most 128 letters,
digits, dots, underscores, slashes, and hyphens. A value of another form is
`malformed` and is not copied. A fault is one line of at most 240 characters from
a fixed set of characters. It is written by this tool and quotes no text of an
answer. A reading lists at most 10 faults and one more line that counts the
others. A name, a reference name, and a label value are free within their form:
the form is not a check for a secret.

A stream leaves these out, on purpose:

- The addresses of an endpoint and of a pod.
- The node name, the zone, and the hostname of an endpoint and of a pod.
- The images, the commands, the environment variables, and the volumes of a pod.
- Each message of a condition, of a container state, and of an operation.
- The repository address of the Application.
- The name of the kubeconfig context. A context name can hold an account identifier.
- Every pod of the namespace that is not a pod of one of the two tiers. A
  reading states their number and nothing else.

A pod name and a UID are identities of one cluster. The test suite gives the tool
answers that hold an address, a node name, an image, an environment value, a
message, and a repository address with a credential, and it holds that none
reaches a stream. That test covers the members it names. It is not a scan for
every secret.

## Limitations

- The instants read.startedAt and read.finishedAt are the wall clock of the host
  that ran the collector, in UTC, to one millisecond. A wall clock can be set
  while a collection runs. The end line names each reading whose start is before
  the finish of the reading before it.
- A reading is the state at an instant that is not known. The instant is not
  before read.startedAt and not after read.finishedAt, when the API server
  answered from its present state. The workload read is one command that makes
  one request for each kind, so its kinds are not one atomic reading.
- The timeout of a read is the timeout of each request that kubectl makes. A read
  makes more than one request, so it can take longer than the timeout and still
  answer.
- An instant that a cluster component wrote is on the clock of that component.
  It is normalised to UTC and keeps its resolution, which is one second for each
  instant that Kubernetes writes into the fields read here. It is not on the
  clock of the collecting host.
- The difference between the clock of the collecting host and a clock of the
  cluster was not measured. The end line counts the cluster instants, other than
  a deletion timestamp, that are later than the finish of the read that returned
  them. A count above zero shows that the two clocks differ. A count of zero does
  not bound the difference.
- The deletion timestamp of a pod is the instant at which its grace period ends.
  It is not the instant of the request to delete the pod, and it can be later
  than the read that returned it.
- No order between two events is established when the events are less than one
  second apart and one of them is a cluster instant, or when both are in the
  interval of one read.
- A state that began and ended between two readings is in no reading.
- The Kubernetes API omits a status count of a Deployment that is zero, and it
  omits a count that the controller did not write yet. A reading states each
  omitted count as missing. It does not state zero.
- An identity is a name and a UID. It is valid for the life of that object on
  that cluster. It is not a stable identity of a replica.
- A pod that left the read and a pod that entered it are two facts. No reading
  states that one pod replaced another.
- The revision of a pod is the revision annotation of the ReplicaSet that owns
  it, in the same read. It is missing when that ReplicaSet is not in the read.
- A reading with more than 64 pods of the two tiers states no pod.
- The restart counts of a pod are two sums: one over its containers and one over
  its init containers. A restart of an ephemeral container is not read.
- The collection names the commit of the working tree that ran the collector,
  and the SHA-256 of the collector script and of its library. It does not state
  whether the tree had a change that was not committed.

Two more limits are of the collector and not of a stream. The Application that
it reads is the one of the `docker-desktop` provider, by name. And a sample is
two `kubectl` processes, so the shortest interval between two samples depends on
the host.

## What a stream does not establish

- That a caller obtained a completion at any instant. A Ready endpoint, a Ready
  pod, a replica count, a sync state, and a health state are what the cluster and
  the delivery controller published. None of them is a request that a caller sent
  and had answered.
- That a field with a state other than reported had any value. A field that was
  not reported is not zero, not Ready, not synced, and not healthy.
- The state of the cluster at a sample whose read is not answered. A read that
  did not answer is not an empty namespace.
- The instant of a change. A change is bounded by two reads, and the interval
  between them is the smallest interval that a stream supports.
- That a request reached a Ready endpoint, or that a pod behind a Ready endpoint
  could serve inference.
- That the delivery controller applied the commit it reported, or that an object
  of the release was rendered at that commit.
- The cause of a change. A stream holds no event, no log, and no message.
- A result of an experiment. A stream is evidence that an analysis reads. This
  module computes no metric and gives no verdict.

## A stream in a run directory

The [evidence layout](../testing/experiment-evidence-layout.md) registers a raw
role for each stream, with the same name: `endpoints`, `pods`, `deployments`, and
`argo`. A stream file has the suffix `.jsonl`, which the evidence index hashes as
text. So a run manifest can name each of the four files under its role, and the
layout check then holds each file to its digest.

The layout check does not call this tool. It reads the form of a caller record
and of no other evidence file. Until a later change joins the two, run
`python -m tools.experiment_timeline check` on the four files of a run.

## Commands

```sh
INFEROPS_PROVIDER=<provider> scripts/environment/experiment-timeline.sh \
  --experiment ID --run ID --samples COUNT --interval SECONDS [--into NAME]
uv run --locked python -m tools.experiment_timeline stream DIRECTORY NAME
uv run --locked python -m tools.experiment_timeline check FILE [FILE ...]
uv run --locked python -m tools.experiment_timeline changes FILE
```

The script writes `.artifacts/experiment-timeline/collections/<NAME>`. Without
`--into`, the name is the UTC time of the start. It refuses a name that exists,
and it refuses arguments that are not usable before it makes any call.

| Exit status | The script | The tool |
|---|---|---|
| 0 | Every sample was taken, and the four streams were written | The command printed what it was asked for |
| 1 | The script stopped before it wrote the four streams: it refused its arguments or its target, or the tool gave no stream for a collection that is kept | |
| 2 | | The arguments are not usable |
| 3 | | A directory is not a collection, or a file is not a stream |

**Exit status 0 does not say that a read answered.** A collection whose every read
is `unanswered` is a collection, and its streams state no value. The script
prints a warning for each sample with a read that did not answer.

## What is not done

- No cluster was read. The collector ran against stand-ins for `kubectl`, and the
  tool read collections that the suites built.
- No run directory holds a stream.
- No stream of this tool holds a metric or an operator event. Each has its own
  tool since `V2-S5-003-PR2`, and nothing starts the three together.
- The tool does not merge a stream with a caller record. An analysis does that.
- The layout check does not hold a stream file to its form.
- The collector does not stop on a signal with a complete collection. A
  collection that was interrupted has no end file.
- Nothing bounds the time of one read. The timeout is of each request.
- A pod of the two tiers that failed or was evicted stays in the read until it is
  removed, and it counts toward the bound of 64.

## Tests

[`tests/domain/test_experiment_timeline.py`](../../tests/domain/test_experiment_timeline.py)
builds each collection in a temporary directory and holds the tool to the states,
the forms, the allowlist, the stored form, and the changes that this page states.
It compares the rules, the limitations, and the boundaries on this page with the
tool's.
[`tests/architecture/test_experiment_timeline_collector.py`](../../tests/architecture/test_experiment_timeline_collector.py)
reads the script as text and executes it against stand-ins. The executed tests
need `bash` and skip without it.
