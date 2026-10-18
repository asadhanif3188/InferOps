# The telemetry of an experiment run

Status: **the collector script and the stream tool are implemented, and collections that the test suites build show each stream, each state of a read, and each result at evidence level C0. Since `V2-S5-006-PR1` the script read one cluster and its telemetry collector in the two attempts of [a non-result integration validation](../proof/experiments/README.md#the-sprint-5-integration-validation), on the docker-desktop provider with one node, and the streams of both attempts are committed. Each of the 288 query reads of each attempt answered through the Service proxy of the API server. No claim is registered.** (Until `V2-S5-006-PR1` this status said that no cluster and no telemetry collector was read, that no stream of a real run is committed, and that the script was executed against stand-ins for `kubectl` only.)

An experiment run compares what a caller observed with what the platform
published at the same time. [The timelines page](experiment-timelines.md)
describes what is read from the Kubernetes API and from the delivery controller.
This page describes what is read from the telemetry collector of the release:
which queries are asked, what each reading states, which clock each instant is
on, and what a stream does not establish.

The capture has two parts.

1. **`scripts/environment/experiment-telemetry.sh` asks the telemetry collector
   a registered set of instant queries, a bounded number of times, and writes
   one directory, the collection.** It changes nothing in the cluster, and it
   sends no request to the API of the release or to the serving runtime. It
   writes the collection under `.artifacts/`. Its target verification writes
   the target's kubeconfig under `.kube/`, as it does for every platform
   workflow.
2. **`tools/experiment_telemetry` reads the collection and prints two streams.**
   It reads files and contacts no cluster and no collector.

| Stream | What each reading states |
|---|---|
| `telemetry` | For each tier: the number of scrape targets, the number whose last scrape succeeded, and the instant of the oldest last scrape. For the API: the request counter for each outcome and the error counter for each canonical error code |
| `resources` | What the API process publishes about itself: the number of processes whose processor time the collector holds, their processor time, and their resident memory |

**A stream states readings. It does not judge.** It does not say whether a
target count is the expected count, whether an error count is high, or whether a
run passed. The tool computes no rate and no ratio, and it gives no verdict.

## What a stream is not

**A stream is not caller truth.** Each value is what the telemetry collector
stored after it scraped a process. None is a request that a caller sent and had
answered. The caller record of a run has a separate source, the
[reliability runner](../serving/reliability-runner.md). No stream is derived
from it or feeds it, the tool imports no caller tool, and a test holds that. A
period in which a stream and the caller record disagree is an observation, and
this tool does not remove it.

**A stream holds no request identifier.** The
[telemetry catalog](../telemetry/telemetry-catalog.md) bars a request
identifier, a correlation identifier, a trace identifier, and a tenant
identifier from a metric label. No registered query groups by one, and a test
compares the registered labels with the catalog. A stored stream whose series
states any label that its query does not register is refused.

**A stream is not a timeline of the cluster, and it is not an operator event.**
The Ready endpoints, the pods, the Deployments, and the Application have
[their own streams](experiment-timelines.md). A fault injection, a reviewed
detection, and a reversal have [their own log](experiment-operator-events.md).

**This is not a telemetry platform.** The tool asks 11 registered
instant queries. It takes no query from an argument, it reads no log and no
trace, it stores no series, and it draws no dashboard.

## The registered queries

The set has the name `experiment-run-queries-r1`. The tool states its SHA-256 over the name,
the stream, the expression, the labels, and the kind of each query. The
collector script writes the name and the digest into the header of a
collection, and the tool builds a stream only from a collection that states the
digest that the tool gives. So a stream names the queries that were asked. A
change to a query changes the digest, and it takes another set name: a test
pins the digest of this name.

**Since `V2-S6-003-PR1` the freeze records of the reliability experiments name
this set.** The evidence layout describes the role `telemetry` as readings of the
metrics that the frozen record registers. Each of the
[five records](../proof/experiments/README.md#the-reliability-experiment-freezes)
names `experiment-run-queries-r1` and pins this tool, so a change to the set moves a
pin of each. (Until `V2-S6-003-PR1` this paragraph said that no frozen record of an
experiment names this set.)

The `telemetry` stream:

| Query | Expression | Labels | Kind | What it states |
|---|---|---|---|---|
| `api-scrape-targets` | `count(up{k8s_component="platform-api"})` | none | `count` | The number of scrape targets of the API tier that the collector holds. |
| `api-scrape-targets-up` | `sum(up{k8s_component="platform-api"})` | none | `count` | The number of those targets whose last scrape succeeded. |
| `api-oldest-scrape` | `min(timestamp(up{k8s_component="platform-api"}))` | none | `instant` | The instant of the oldest last scrape among the targets of the API tier. |
| `runtime-scrape-targets` | `count(up{k8s_component="serving-runtime"})` | none | `count` | The number of scrape targets of the serving runtime tier that the collector holds. |
| `runtime-scrape-targets-up` | `sum(up{k8s_component="serving-runtime"})` | none | `count` | The number of those targets whose last scrape succeeded. |
| `runtime-oldest-scrape` | `min(timestamp(up{k8s_component="serving-runtime"}))` | none | `instant` | The instant of the oldest last scrape among the targets of the serving runtime tier. |
| `api-requests-by-outcome` | `sum by (inferops_outcome) (inferops_inference_requests_total)` | `inferops_outcome` | `number` | The request counter of the API, summed over its processes, for each outcome. |
| `api-errors-by-code` | `sum by (inferops_error_code) (inferops_inference_errors_total)` | `inferops_error_code` | `number` | The error counter of the API, summed over its processes, for each canonical error code. |

The `resources` stream:

| Query | Expression | Labels | Kind | What it states |
|---|---|---|---|---|
| `api-processes-reporting-cpu` | `count(inferops_process_cpu_seconds_total)` | none | `count` | The number of API processes whose processor time the collector holds. |
| `api-cpu-seconds` | `sum(inferops_process_cpu_seconds_total)` | none | `number` | The processor time of the API processes, in seconds, summed. |
| `api-resident-memory-bytes` | `sum(inferops_process_resident_memory_bytes)` | none | `number` | The resident memory of the API processes, in bytes, summed. |

- **Each query aggregates.** `sum`, `count`, and `min` drop each label that a
  `by` clause does not name. So an answer states no pod name, no target, no
  scrape job, and no address, and the registered labels are the only ones that
  a series can state.
- **The kinds.** A value of the kind `count` is a whole number that is not
  negative. A value of the kind `number` is a finite number. A value of the kind
  `instant` is an instant that the collector states in seconds, and a reading
  states it in UTC to one millisecond.
- **A counter is stated as the collector holds it.** The request counter and the
  error counter are sums over the API processes. An analysis computes a rate
  from two readings. This tool computes none.
- **The resident memory has no series today.** The telemetry catalog records
  `inferops_process_resident_memory_bytes` as not emitted: no process of the
  release publishes it. A collector that scrapes the release therefore answers
  the query `api-resident-memory-bytes` with no series, and the reading states
  `no-series`. It does not state zero bytes. A test compares this sentence with
  the catalog.
- **No query reads the resource use of the serving runtime, of a container, or
  of a node.** The release has no source for it. The `resources` stream
  therefore states the processor time of the API processes and nothing about
  the serving runtime. Three queries of the `telemetry` stream read the scrape
  state of the serving runtime tier.
- **The serving runtime has a scrape job only under one profile.** The chart
  renders that job only under the profile `real`. Under another profile the
  three queries of the serving runtime tier have no series.

## A release with no collector

The chart installs the telemetry collector only when
`telemetry.collection.collector.deploy` is set, and the value is off by default.
The [Application](argocd-application.md) sets it in its hand-written values, so
the release that the delivery controller delivers installs a collector. A
release that was installed with the default of the chart has none, and it has
no Service of one.

A collection against a release with no collector is still a collection. The
Service read answers with no object, no query answers, and each reading states
the read state `absent`. It states no result and no value. **A release with no
collector does not give a stream of zeros.** No run observed either case.

## What is read: the collection

The script reads the release that the environment scripts name: the release
`inferops` in the namespace `inferops-release`. The Service of the collector has
the name `inferops-inferops-llm-collector`, as
[the collection verification](../telemetry/kubernetes-telemetry-collection.md)
names it, and its port has the name `http`.

A query read is one HTTP GET of the query API of the collector. It goes through
the Service proxy of the API server:
`kubectl get --raw /api/v1/namespaces/<namespace>/services/<service>:http/proxy/api/v1/query?query=<expression>`.
The script opens no port and starts no process that outlives a read. The chart
starts the collector with no admin API and no lifecycle endpoint, and the script
asks for no path other than `api/v1/query`.

**The script holds no query.** Before it verifies the target, it asks the tool
for the requests with `python -m tools.experiment_telemetry requests`. It holds
each line to a fixed form: a query name, and a path that is `api/v1/query?query=`
and an expression in which each character other than a letter, a digit, `-`,
`.`, `_`, and `~` is percent-encoded. A line of another form stops the script
before any call to a cluster.

Before the first sample, the target verification of the script library makes
reads of its own: `kubectl config` and `kubectl version`, and `kubectl get` of
the nodes, of the pods of the system namespace, and of the storage classes. They
change nothing, and no stream holds what they return.

| File | What it holds |
|---|---|
| `collection.json` | The header, which the script writes before the first sample |
| `sample-NNNN.collector.json` | `kubectl get service` of the collector's Service by name, with `--ignore-not-found`, as JSON |
| `sample-NNNN.query.<name>.json` | The answer of the collector to one registered query |
| `sample-NNNN.meta` | For the Service read and for each query read: whether it answered, and its two instants. The script writes it after the last read of the sample |
| `collection.end` | The number of samples, written after the last one |
| `streams/<stream>.jsonl` | The two streams that the tool gives for the files above |

**A read that does not answer is not an empty result.** The script writes no
file for it, and the sample states the read as `unanswered`. Each kubectl call
of a read states `--request-timeout 10s`, and kubectl applies it to each
request that the call makes. The call of the Service read can make more than
one request. No run observed how long a read takes. (Since `V2-S5-006-PR1` the
streams of two attempts on one provider state the two instants of each of their
reads. No page states a duration from them.) A query that the collector
refused and a query that the API server could not pass to the collector both
fail the read, and the script does not tell them apart.

**The collection holds the whole answer of each read.** The answer of the
Service read holds an address. Do not commit a collection. The two stream files
hold an allowlist, and they are the evidence files of a run.

The header states the collection schema, the experiment identifier and the run
identifier that the operator gave, the provider, the server version, the
namespace, the release, the name and the port name of the collector's Service,
the name and the digest of the query set, the commit of the working tree, the
SHA-256 of the script and of its library, the number of samples, the pause, and
the request timeout. It names the provider and not the kubeconfig context,
because a context name can hold an account identifier. The tool refuses a header
with any member that it does not expect, and a header with a member of another
form. One member is an exception: a server version of another form is kept as
`malformed`, and one that the script could not read is `missing`.

### Bounds

| Bound | Value |
|---|---|
| Samples of one collection | 1 to 720 |
| Pause between two samples | 5 to 120 seconds |
| Request timeout of one kubectl call | 10 seconds in the script. The tool accepts a header that states 1 to 60 |
| Queries of one sample | 11, as the tool registers them. The script refuses more than 32 |
| Series that one reading states | 32 |

The pause is the time between the end of one sample and the start of the next.
It is not a period: a sample takes the time of its reads. The chart's scrape
interval is 30 seconds by default, so two samples that are closer than that can
state one scrape twice. The instant of the oldest scrape of each tier shows it.

A collection that was interrupted has no `collection.end`. The header of each
stream then states `complete` as false, and each query of a sample that was not
written is a reading with the read state `not-taken`.

## The clocks

A stream has one time basis, and it says where a second clock enters.

**The time basis is the clock of the collecting host.** The script takes one
instant before each read and one after it. A reading states them as
`read.startedAt` and `read.finishedAt`, in UTC, to one millisecond, in the form
`2026-10-12T08:00:00.000Z`. It is the form that the timeline streams and the
operator event log use, so the three have one time basis when one host writes
them.

**An evaluation instant is on the clock of the telemetry collector.** The
collector states with each sample the instant at which it evaluated the query.
A reading states it as `evaluatedAt`, in UTC, cut to one millisecond. The value
of a query of the kind `instant` is on the same clock: it is the instant at
which the collector made a scrape.

**A value can be older than its read.** The collector answers from the last
sample that it stored. `api-oldest-scrape` and `runtime-oldest-scrape` state how
old that sample is for the scrape state. The stream states no age for a counter.

**The difference between the two clocks is not measured by a stream.** Since
`V2-S6-007-PR1`, revision 2 of the freeze records of V2-E02A, V2-E02B, V2-E02C, and
V2-E05 bounds that difference at two readings of each run, and states when a verdict may
use the bound: see [the clock policy of rule set
2](../proof/experiments/README.md#the-clock-policy-of-rule-set-2). No stream reads that
bound.
The header of each
stream states `skew` as `not-measured`. The end line states two bounds in
`evaluationOffset`. The query API documents that a query with no `time`
parameter is evaluated at the present time of the collector. When that holds,
the collector took each evaluation instant while its read was open. Then its
clock minus the host clock is not below `evaluatedAt` minus
`read.finishedAt`, and it is not above `evaluatedAt` minus `read.startedAt`. No
run observed it, and each instant is cut to one millisecond, so each bound is
to about one millisecond. The
end line states the largest lower bound as `notBelowMilliseconds` and the
smallest upper bound as `notAboveMilliseconds`, over the readings that state an
evaluation instant. When the first is above the second, the difference changed
during the collection, or a clock was set. The bounds are as wide as a read is
long. A stream with no evaluation instant states neither.

**What ordering a stream supports.** A change of a value is between two scrapes
of the collector, and a stream shows it between two readings. No order of two
events inside one of those intervals is established.

## No series is not zero

Each read has one of five states. They are the states of the timeline streams.

| Read state | Meaning | Result |
|---|---|---|
| `answered` | The collector returned an instant vector that the tool can read | `series` or `no-series`, unless a fault of the reading says why not |
| `absent` | The query did not answer, and the Service read of the same sample answered with no object: the release has no collector | None |
| `unanswered` | The query failed or timed out, and the Service read did not show that the collector is absent | None |
| `unreadable` | The answer is not usable: it is not one JSON object, it states a member twice or a number that cannot be read, it does not state success, it is not an instant vector, its file is not in the collection, or the sample does not state whether the read answered or states no usable instants for it | None |
| `not-taken` | The collection was asked for the sample and did not write it | None |

An answered read has one of two results.

| Result | Meaning |
|---|---|
| `series` | The answer holds at least one series. Each has its registered labels and one value |
| `no-series` | The answer holds no series. The collector held no sample for the query at the evaluation instant. The reading states no value, and `evaluatedAt` is `missing`, because the collector states an instant only with a sample |

Each reading also states what the Service read of its sample showed.

| Collector | Meaning |
|---|---|
| `present` | The Service read returned the Service of the collector |
| `absent` | The Service read answered with no object |
| `not-read` | The Service read did not answer, or it returned another object |

A value and an evaluation instant are fields. A field has one of three states:
`reported`, `missing`, or `malformed`. Only `reported` carries a value.

No function replaces a state with zero. These cases are each a test:

- An answer with no series is `no-series`. A sum that the collector answers as
  `0` is a value of zero. The two readings differ.
- A read that did not answer states no result. It is not a result with no
  series.
- A release with no collector states each read as `absent`.
- A value that is `NaN`, an infinity, a JSON number in place of text, or text of
  another form is `malformed`, and it is not copied. A count with a fraction and
  a negative count are `malformed`. A number that is not zero and is too small
  for its storage is `malformed`, and it is not read as zero.
- Series that state two evaluation instants, or one that is not a number, leave
  `evaluatedAt` as `malformed`.

A reading that answered and cannot be reduced without a guess states no result
and no series, and it lists the reason in `faults`. A series with a label that
the query does not register, a label value of another form, two series with the
same labels, and more than 32 series each leave the reading with no
series. The other series of the answer are not kept: a part of an answer is not
the answer. A fault is a text of this tool. It quotes no label name, no label
value, and no error text of the answer.

## The two streams

A stream is a text file of JSON lines. The first line is the header, each
following line is one reading, and the last line is the end line. Each line has
sorted members, so one collection gives one text. The schema name is
`inferops.io/experiment-telemetry/v1alpha1`.

**The header** states the stream, the two identifiers, the header of the
collection with `completedSamples` and `complete`, the registered queries of the
stream, the two clocks, the bounds, what is left out, the limitations, and what
the stream does not establish.

**A reading** is one query of one sample. It states `index`, `sample`, `query`,
`read` with its state and its two instants, `collector`, `result`,
`evaluatedAt`, `series`, and `faults`. The readings of one sample are in the
registered order of the queries. A series states `labels` and `value`. The
labels of a query that registers none are an empty object. The value of a label
is 1 to 63 letters, digits, dots, underscores, and hyphens, with a letter or a
digit first. That form holds each registered outcome and each canonical error
code. It is not a check for a secret.

**The end line** states the number of readings, the number in each read state
as `byReadState`, the number with each result as `byResult`, the two bounds of
`evaluationOffset`, and `instantsOutOfOrder`: each reading whose start is before
the finish of the reading before it. Such a reading shows that the host clock
was set back.

### What a stored stream is held to

`python -m tools.experiment_telemetry check` reads stored streams. It holds each
one to 11 rules.

| Rule | Statement |
|---|---|
| `telemetry-stream-unreadable` | A stream is UTF-8 text, and each line ends with a line feed. Each line is one JSON object with no member stated twice. |
| `telemetry-header-unsupported` | The first line is the header. It states the stream schema, one of the two stream names, an experiment identifier, and a run identifier, each in its form. Its collection has exactly the members of a collection, each in its form. Its clocks, its bounds, what it leaves out, its limitations, and what it does not establish are the texts of this tool. |
| `telemetry-members-unsupported` | Each line has exactly the members of its record, and each read has exactly its three members. |
| `telemetry-query-unregistered` | The header states the registered queries of its stream, as this tool registers them, and it names the registered set. |
| `telemetry-reading-out-of-sequence` | Each line between the header and the end line is a reading. The readings are numbered from 1 with no gap, and each sample holds the queries of the stream in the registered order. |
| `telemetry-read-state-unsupported` | Each reading states one of the registered read states and one of the registered states of the collector. |
| `telemetry-instant-invalid` | Each instant of a read is absent or is UTC to one millisecond in the one registered form. A read states both instants or neither, and it does not finish before it starts. |
| `telemetry-reading-unsupported` | Each fault of a reading is a text of this tool. A reading states a result, a series, and an evaluation instant only when its read answered. A reading with the result series states at least one series and at most 32, and a reading with the result no-series states none. Each series has its labels and one value. Each value and each evaluation instant is a field with the form of its kind. A read that was not taken states no instant, each other read except an unreadable one states its instants, and an absent read states an absent collector. |
| `telemetry-label-unregistered` | Each series states only labels that its query registers, each value of a label has the form of a label value, and no two series of one reading state the same labels. |
| `telemetry-end-missing` | The last line is the end line, and no line follows it. |
| `telemetry-counts-differ` | The end line states the number of readings, the number in each read state, the number with each result, the two bounds of the clock difference, and each reading that starts before the one before it finished, as this tool computes them from the readings. |

**The check reads the form of a stream.** It holds the collection of the header
to its members and their forms, and the clocks, the bounds, and the three lists
of statements to the texts of this tool. It holds each fault to a text that the
tool writes, each value and each evaluation instant to the form of its kind,
and the end line to what the tool computes from the readings. It reads the
queries of the header against the registered set, so a stream of an earlier set
is refused when a later change registers another one.

It does not show that a stream is what a collection gives: the collection is not
committed, so no check can build the stream again. It does not show that a
value is what a collector answered. It holds a name, an identifier, and the
value of a registered label to a form, and a form is not a check for a secret.

## What a stream leaves out

A stream leaves these out, on purpose:

- Each label of a series that the query does not register. Each registered query
  aggregates over every other label.
- The name of a pod, of a scrape target, and of a scrape job, and the address of
  a target.
- Each request identifier, correlation identifier, trace identifier, and tenant
  identifier. The telemetry catalog bars each from a metric label, and no
  registered query groups by one.
- The text of an error that the collector or the API server returned.
- The name of the kubeconfig context. A context name can hold an account
  identifier.
- The Service object of the collector. The tool reads whether it is present and
  nothing else.

The test suite gives the tool answers that hold an address, a node name, a pod
name, a request identifier in a label, and an error text, and it holds that none
reaches a stream. That test covers the members it names. It is not a scan for
every secret.

**The value of a registered label is held to a form and not to a vocabulary.**
The two registered labels state an outcome and a canonical error code. A text
of the form of a label value under one of those two labels reaches a stream,
whatever it is: a test shows it for an address and for a pod name. This tool
holds the value to no set of values.

## Limitations

- The instants read.startedAt and read.finishedAt are the wall clock of the host
  that ran the collector script, in UTC, to one millisecond. A wall clock can be
  set while a collection runs. The end line names each reading whose start is
  before the finish of the reading before it.
- A value is the answer of the telemetry collector to one instant query. It is
  not a reading of the process that published the metric. The collector answers
  from the last sample that it stored. That sample can be older than the read by
  the scrape interval. When the collector stored no newer sample and no mark
  that the series ended, the sample can be older by up to the lookback of the
  collector, which the chart leaves at the default of the collector. No run
  observed either.
- The instant evaluatedAt and the value of a query of the kind instant are on
  the clock of the telemetry collector, to one millisecond. They are not on the
  clock of the collecting host.
- The difference between the two clocks is not measured. The end line states two
  bounds that the evaluation instants give. The bounds hold when the collector
  took each evaluation instant while its read was open, and when the difference
  did not change during the collection. Each instant is cut to one millisecond,
  so each bound is to about one millisecond. No run observed when a collector
  takes the instant.
- A reading with the result no-series states that the collector held no sample
  for the query at the evaluation instant. It does not state why. A metric that
  no process publishes, a target that the collector did not discover, and a
  sample that went stale each give no series.
- A value of a counter is the sum over the processes that the collector scraped.
  The sum falls when a process starts again and when a target leaves. A stream
  computes no rate and corrects no reset.
- The queries of one sample are separate reads at separate instants. They are
  not one atomic reading.
- A state that began and ended between two scrapes is in no sample of the
  collector. A state that began and ended between two readings is in no reading.
- Each kubectl call of a read states a request timeout, and kubectl applies it
  to each request that the call makes. The call of the Service read can make
  more than one request. No run observed how long a read takes. A query that the
  collector refused and a query that the API server could not pass to the
  collector are both unanswered. (Since `V2-S5-006-PR1` the streams of two
  attempts state the two instants of each of their reads. No page states a
  duration from them.)
- A read reaches the collector through the Service proxy of the API server. The
  network policy of the chart selects the pod of the collector and admits no
  connection to its port. Whether a cluster applies that policy to a connection
  from the API server is a property of its network plugin. No run observed it.
  (Since `V2-S5-006-PR1` two attempts on the docker-desktop provider read
  through it, and each of the 288 query reads of each attempt answered. The
  requests of the runner of the first attempt all timed out, and its result page
  infers that the network policy of the API dropped them. Why no policy stopped
  the reads of the collector was not established.)
- The series of the collector are in a volume that goes when its pod goes. A
  stream holds only what was read while the collection ran.
- The resources stream reads what the API process publishes about itself. No
  query reads the resource use of the serving runtime, of a container, or of a
  node, because the release has no source for them.
- The chart renders the scrape job of the serving runtime only under the profile
  real. Under another profile the three queries of the serving runtime tier have
  no series.
- A value of a registered label is free within the form of a label value. The
  form is not a check for a secret, and it does not show that the value is a
  registered outcome or a canonical error code.
- A value of the kind number is stored as a binary number of 64 bits. A counter
  above 9007199254740992 loses its last digits.
- A reading whose answer holds more than 32 series states no series.
- The collection names the commit of the working tree that ran the collector
  script, and the SHA-256 of the script and of its library. It does not state
  whether the tree had a change that was not committed.

## What a stream does not establish

- That a caller obtained a completion at any instant. A scrape that succeeded, a
  request counter, and an error counter are what the telemetry collector stored.
  None of them is a request that a caller sent and had answered.
- That a reading with the result no-series is a value of zero. No series is not
  zero, not healthy, and not failed.
- That the telemetry collector existed or answered at a sample whose read state
  is not answered. A read that did not answer is not a result with no series.
- That a metric means what its name says. A scrape that succeeded does not show
  that a counter agrees with what callers observed.
- The instant of a change. A change is bounded by two scrapes of the collector
  and by two readings.
- The resource use of the serving runtime, of a container, or of a node.
- A rate, a ratio, a detection lag, or any other metric of an experiment. A
  stream is evidence that an analysis reads. This module computes no metric and
  gives no verdict.

## A stream in a run directory

The [evidence layout](../testing/experiment-evidence-layout.md) registers a raw
role for each stream, with the same name: `telemetry` and `resources`. A stream
file has the suffix `.jsonl`, which the evidence index hashes as text. So a run
manifest can name each of the two files under its role, and the layout check
then holds each file to its digest.

The layout check does not call this tool. It reads the form of a caller record
and of no other evidence file. Until a later change joins the two, run
`python -m tools.experiment_telemetry check` on the two files of a run.

## Commands

```sh
INFEROPS_PROVIDER=<provider> scripts/environment/experiment-telemetry.sh \
  --experiment ID --run ID --samples COUNT --interval SECONDS [--into NAME]
uv run --locked python -m tools.experiment_telemetry requests
uv run --locked python -m tools.experiment_telemetry stream DIRECTORY NAME
uv run --locked python -m tools.experiment_telemetry check FILE [FILE ...]
```

The script writes `.artifacts/experiment-telemetry/collections/<NAME>`. Without
`--into`, the name is the UTC time of the start. It refuses a name that exists,
and it refuses arguments that are not usable before it makes any call.

| Exit status | The script | The tool |
|---|---|---|
| 0 | Every sample was taken, and the two streams were written | The command printed what it was asked for |
| 1 | The script stopped before it wrote the two streams: it refused its arguments or its target, the tool gave no usable request, or the tool gave no stream for a collection that is kept | |
| 2 | | The arguments are not usable |
| 3 | | A directory is not a collection of the registered query set, or a file is not a stream |

**Exit status 0 does not say that a read answered.** A collection whose every
read is `absent` or `unanswered` is a collection, and its streams state no
value. The script prints a warning for each sample with a read that did not
answer.

## What is not done

- No result-bearing run read a cluster or a telemetry collector. The script read
  one only in the two attempts of the integration validation, on one provider
  with one node. In the suites it ran against stand-ins for `kubectl`, and the
  tool read collections that the suites built. The form of an answer is the one
  that the query API documents. (Until `V2-S5-006-PR1` this item said that no
  cluster and no telemetry collector was read, and that no answer of a running
  collector was read by this tool.)
- The Service proxy path reached the collector in both attempts, on the
  docker-desktop provider. No other provider was read. (Until `V2-S5-006-PR1`
  this item said that no run observed that the path reaches the collector, on
  any provider.)
- Two run directories hold the streams, those of the two attempts, and neither
  is of a result-bearing run. (Until `V2-S5-006-PR1` this item said that no run
  directory holds a stream.)
- No criterion of a frozen record reads a telemetry figure. The freeze records of
  `V2-S6-003-PR1` name the query set as a measurement. (Until then this item said that
  no frozen record of an experiment names the query set.)
- No query reads the resource use of the serving runtime, of a container, or of
  a node.
- The tool does not merge a stream with a caller record, and it computes no
  rate, no ratio, and no detection lag. An analysis does that.
  [The reliability analysis](../testing/reliability-analysis.md) of
  `V2-S5-004-PR1` is not that analysis: it reads no telemetry stream.
- The layout check does not hold a stream file to its form.
- The script does not stop on a signal with a complete collection. A collection
  that was interrupted has no end file.
- The script and the timeline collector are two processes. No tool starts them
  together, and nothing aligns their samples. Since `V2-S5-006-PR1`
  [the driver of the integration validation](../proof/experiments/v2-s5-integration/procedure/run-driver.txt)
  starts both, one after the other, in the background. (Until `V2-S5-006-PR1`
  this item said that nothing starts them together.)

## Tests

[`tests/domain/test_experiment_telemetry.py`](../../tests/domain/test_experiment_telemetry.py)
builds each collection in a temporary directory and holds the tool to the
registered queries, the states, the results, the forms, the allowlist, and the
stored form that this page states. It compares the queries, the rules, the
limitations, and the boundaries on this page with the tool's.
[`tests/architecture/test_experiment_telemetry_collector.py`](../../tests/architecture/test_experiment_telemetry_collector.py)
reads the script as text and executes it against stand-ins. The executed tests
need `bash` and skip without it.
