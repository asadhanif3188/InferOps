# The RP-1 in-cluster reliability runner

Status: **implemented and checked by `V2-S5-001-PR2` against scripted answers and a
loopback server. No run was started in a cluster, and no request was sent to a
model.** The runner sends the [RP-1 reliability workload](reliability-workload-rp-1.md)
from a pod inside the cluster to the API Service, and it writes one caller record for
each run. This is static evidence at C0, with one rehearsal that is substituted
execution. It registers no claim. The validation record is
[`v2-s5-001-pr2-validation.md`](../proof/serving/v2-s5-001-pr2-validation.md).

> [!WARNING]
> **A caller record is not a benchmark and not a verdict.** Each record carries the
> boundary sentence of the profile:
>
> RP-1 is a reliability workload: one fixed public request, sent by two closed-loop workers. It is not a representative production workload, an overload test, or a benchmark. Concurrency 2 is a fixed choice and not a measured threshold. No figure from a run under it is a portable capacity figure or a production SLO.

## What the runner is for

A reliability experiment asks what a caller sees while something fails and recovers.
A pod can be Ready, a Service can have endpoints, and a delivery controller can
report a healthy release while a caller gets errors. The reverse can also occur. So
the caller needs its own record, made by something that reads none of those signals.

The runner is that caller. It sends requests on this path:

```text
runner pod  ->  API Service  ->  API pod  ->  runtime Service  ->  runtime pod
```

The runner is started for one experiment run, and it is removed after the run. It is
not part of the release. The chart does not render it, and the desired state does
not hold it.

## The parts

| Part | What it is |
|---|---|
| [`tools/reliability_runner/incluster.py`](../../tools/reliability_runner/incluster.py) | The one file that a runner pod executes. It imports the standard library and nothing else |
| [`tools.reliability_runner`](../../tools/reliability_runner/) | The host tool. It writes the plan and the manifest of a run, and it checks a caller record. It contacts no cluster |
| [`scripts/environment/reliability-runner.sh`](../../scripts/environment/reliability-runner.sh) | The real path. It applies the manifest, reads the log of the pod, and deletes the two objects of the run |
| [`tests/serving/test_reliability_runner.py`](../../tests/serving/test_reliability_runner.py) | The suite |

### Why no image is built

A run is one ConfigMap and one Job. The ConfigMap holds the runner file and the
plan. The Job mounts both, read-only, and runs `python -I` on the file. The image of
the Job is an interpreter and no more: an image that holds Python 3.12, named by
digest. The script uses the image that the API Deployment names, because the node
already holds it.

So no image holds the runner, and a change of the runner changes no image digest.
The ConfigMap states the SHA-256 of the runner file and of the plan as annotations.
The pod computes both digests from the files it mounts, and it writes them in the
header of the record. `verify` compares the digest of the plan. It reports whether
the digest of the runner file is the digest of the file in this tree, and it does
not refuse a record of an earlier runner file.

## What a run sends

A plan repeats the committed profile, and no argument of the tool changes these
values:

| Value | In the plan | Origin |
|---|---|---|
| Request | `POST /v1/chat/completions`, the fixture body of RP-1 | The RP-1 profile |
| Headers | `X-InferOps-Request-ID`: the run identifier and the sequence number. `X-InferOps-Correlation-ID`: the run identifier | The RP-1 profile, and the form of the V1 load harness |
| Workers | 2, closed loop: each worker sends, waits for the answer, and sends again | The RP-1 profile |
| Client deadline | 150,000 ms for each request | The RP-1 profile |
| Success rule | HTTP 200, adapter `real`, the model of the fixture, usage counts, at least one choice, within the deadline | The RP-1 profile |
| Connection | A new connection for each request, no redirect followed, no proxy variable read, no retry | The V1 transport, restated |

An operator states the rest:

| Argument | Meaning | Bound |
|---|---|---|
| `--experiment-id` | The experiment that the run belongs to | Letters, digits, `.`, `_`, `-`; at most 63 characters |
| `--run-id` | The run. It is part of the name of the Job | A lower-case DNS label of at most 40 characters |
| `--duration-seconds` | No request is dispatched after this time | From 1 to 3,600 seconds |
| `--request-ceiling` | No more requests than this are dispatched. The default is the maximum | From 1 to 10,000 requests |
| `--release-id` | The release identifier that the operator declares | 64 lower-case hexadecimal characters, or absent |

The target is `http://inferops-inferops-llm.inferops-release.svc:8090`: the API
Service of the release, by its cluster DNS name. The tool builds the URL from a
Service name, a namespace, and a port, and the runner file refuses a plan whose URL
is not built that way. A pod address, a loopback address, and a port-forward cannot
be written in that form. The suite holds the Service name and the port against the
committed render of the chart.

### The bounds of a run

- **The duration and the ceiling.** A worker dispatches no request after the
  duration, and none after the ceiling. A request that was dispatched is given its
  deadline, and it is recorded.
- **The Job.** `activeDeadlineSeconds` is the duration, one client deadline, and 60
  seconds. `backoffLimit` is 0, so a failed pod is not replaced: a second pod would
  be a second run under one run identifier.
- **The finished Job.** `ttlSecondsAfterFinished` is 3,600 seconds. Kubernetes
  documents that it then deletes the Job and its pod. The log is deleted with the
  pod, so a record that was not collected in that time is lost.
- **The stop signal.** On `SIGTERM` the runner dispatches no further request, waits
  for a request in flight, and writes its end line with the state `interrupted`.
  The pod is given one client deadline and 30 seconds to do so.

### The wait after a request that is not a success

A worker waits 1,000 ms after a request whose outcome is not `success`. **The RP-1
profile states no such wait. It is a bound of this runner.** A refused connection
and an error answer return in milliseconds. A closed loop with no wait would then
send without a bound on its rate, exactly while a fault is in progress, and it would
reach its request ceiling in seconds. With the wait, two workers send at most about
two failed requests in one second.

The wait is not a retry. The next request is a new request with its own sequence
number and its own line. The wait changes how many requests a run sends during a
failure. So a count of failed requests under this runner is a count of this runner's
attempts, and it is not a count of the requests that a caller without the wait would
have lost.

### What the runner does not carry from the V1 harness

- **No identity probe.** The V1 harness reads the readiness answer and the model
  list before it sends load, and it refuses a target that is not ready. The runner
  sends its first request when it starts.
- **No warm-up.** Each request is a caller result.
- **No stop on an outcome.** The V1 harness ends a run on an answer of another
  adapter, and after five transport errors in a row. A reliability experiment can
  delete a pod on purpose. The runner ends at its bounds and at a stop signal only.
- **No summary of latency.** The tool counts outcomes. It computes no rate and no
  percentile.

## What the runner does not read

**The runner reads the plan file, its own file, and the answers of the target.** It
reads nothing else:

- The pod holds no service account token (`automountServiceAccountToken: false`),
  and the runner file calls no Kubernetes API.
- The runner sends no request to `/health/ready`, to `/health/live`, or to
  `/v1/models`. Each request that it sends is the `POST` of the plan.
- The Job has no init container and no probe, and the script does not wait for a
  rollout or for a Ready pod before it applies the Job.
- The runner reads no state of Argo CD, and no metric.

The script reads one thing from the release when no `--image` is given: the image
that the API Deployment names in its specification. It does not read the status of
the Deployment.

## The caller record

A run writes its record to standard output, one JSON object on each line: one
header, one line for each request in the order in which the requests finished, and
one end line. The script reads it as the log of the pod.

### The header

| Member | Holds |
|---|---|
| `record` | `header` |
| `schemaVersion` | `inferops.io/reliability-caller-record/v1alpha1` |
| `mode` | `in-cluster` for a run of the runner file in a pod. `rehearsal` for a run against scripted answers |
| `experimentId`, `runId` | The two identifiers of the plan |
| `boundary` | The boundary sentence of the profile |
| `profile` | The profile identifier, its revision, and its content digest |
| `release` | The release identifier and its source: `declared` or `not-declared` |
| `target` | The Service name, the namespace, the port, and the base URL |
| `concurrency`, `requestTimeoutMs`, `success`, `bounds` | The values of the plan |
| `planSha256`, `runnerSha256` | The digests that the pod computed of the two files it mounted |
| `promptText`, `completionText` | Both `false` |
| `startedAt` | The UTC instant at which the run started |

### A request line

| Member | Holds |
|---|---|
| `record` | `request` |
| `sequence` | The number of the request in the run, from 1 |
| `worker` | The worker that sent it: 0 or 1 |
| `requestId` | The run identifier and the sequence number. The request carried it in `X-InferOps-Request-ID` |
| `experimentId`, `runId`, `releaseId` | The identifiers of the header |
| `startedAt`, `finishedAt` | UTC instants of the pod's clock, to one millisecond |
| `latencyMs` | The time from the send to the answer, from a monotonic clock |
| `httpStatus` | The status of the answer. `null` when no answer arrived |
| `success` | `true` when the outcome is `success`, and `false` for each other outcome |
| `outcome` | One of the six outcomes below |
| `errorCode`, `errorCondition` | The canonical error code and the condition identifier of an `http-error` answer. `null` for each other outcome |
| `finishReason`, `inputTokens`, `outputTokens` | Of a `success`. `null` for each other outcome |
| `adapterKind`, `modelRef` | What the answer named, or `null` |

The six outcomes are the outcomes of the V1 load harness, decided in the same order:

| Outcome | When |
|---|---|
| `timeout` | No answer arrived within the client deadline, or an answer of the required adapter arrived after it |
| `transport-error` | The connection failed before an answer arrived |
| `identity-refused` | The answer names an adapter other than the required one, at each status and at each latency |
| `http-error` | The status is not 200 |
| `invalid-response` | The status is 200, and the answer names another model, has no choice, or has no usage counts |
| `success` | Each other answer |

**A request with no answer has the status `null`.** The V1 record writes 0 there. A
missing status is not a status.

**The release identifier is a declared value.** No answer of the API states a
release identifier, so the runner cannot observe one. The operator declares it, the
record repeats it on each line, and the header states the source.

### The end line

| Member | Holds |
|---|---|
| `record` | `end` |
| `experimentId`, `runId` | The identifiers of the header |
| `endState` | `duration`, `request-ceiling`, or `interrupted` |
| `dispatched`, `recorded` | The number of requests sent, and the number of request lines written |
| `outcomes` | The count of each of the six outcomes |
| `elapsedMs`, `finishedAt` | The length of the run, and the UTC instant at which it ended |

**A record with no end line is refused.** It is the log of a run that has not ended,
or of a pod that was stopped before it wrote the line.

### What a record never holds

The prompt text, the completion text, a response header, an address of a pod, and
the message of an error. A value that is read from an answer is kept only when it is
a short plain token, and a value that is not one is written as `unrecognized`. The
checker gives each line an exact set of members, and each text member a pattern or
a registered value. So a line has no member that can hold a prompt or a completion.

## The rules

The tool has 16 rules. Four are of a plan and a manifest, and twelve are of a caller
record. Each command stops at the first refusal, and the message starts with the
rule.

| Rule | Refuses |
|---|---|
| `runner-profile-refused` | A plan when the loader of the RP-1 profile refuses the committed profile |
| `runner-identifier-unsupported` | A run identifier or an experiment identifier that is not in the supported form |
| `runner-plan-refused` | A duration, a ceiling, a release identifier, a Service name, a namespace, or a port that is not usable, a plan file that is unreadable, and a manifest of a rehearsal plan |
| `runner-image-not-pinned` | An image that is named by a tag, and a pull policy other than `Never` and `IfNotPresent` |
| `caller-record-unreadable` | A line that is empty, is not one JSON object, states one member twice, or has no record kind |
| `caller-record-header-missing` | A record whose first line is not a header, and a record with two headers |
| `caller-record-members-unsupported` | A line with a missing or unknown member, a member of another type, a text that is not a short plain token, and a header that does not target the API Service |
| `caller-record-profile-unregistered` | A header whose profile, revision, content digest, or boundary sentence is not one that the profile tool registers |
| `caller-record-plan-differs` | With `--plan`: a header that does not name the digest of the plan, or does not repeat its values |
| `caller-record-identity-differs` | A line that names another experiment, run, or release than the header, a request identifier of another sequence number, and a worker that the run does not have |
| `caller-record-time-invalid` | An instant that is not UTC to one millisecond, a request that finishes before it starts or starts before the run, and a request that finishes after the run ends |
| `caller-record-outcome-inconsistent` | A line whose `success`, status, and kept members do not agree with its outcome |
| `caller-record-sequence-gap` | Sequence numbers that are not each number from 1 to the number of request lines, once |
| `caller-record-end-missing` | A record with no end line, and a line after the end line |
| `caller-record-counts-differ` | An end line whose counts are not the counts of the request lines, and a run with more requests than its ceiling |
| `caller-record-holds-content` | A header that does not state `promptText: false` and `completionText: false` |

**A record that each rule accepts is a well-formed record.** Acceptance says nothing
about how many requests succeeded. The summary that `verify` prints holds counts and
identities. It holds no rate, no percentile, and no result.

## Commands

From the repository root, inside the locked environment
(`uv run --locked python -m ...`).

```text
python -m tools.reliability_runner plan --experiment-id ID --run-id ID --duration-seconds N
python -m tools.reliability_runner manifest --plan FILE --image REPOSITORY@DIGEST
python -m tools.reliability_runner verify RECORD [--plan FILE]
python -m tools.reliability_runner rehearse
```

No command contacts a cluster, and no command sends a request. Exit status `0` says
that the command printed its result. For `verify` it says that each rule accepted
the record. Exit status `3` says that one rule refused. Exit status `2` says that
the arguments are not usable. Exit status `4` says that the command failed in
another way.

### The rehearsal

`rehearse` runs the loop of the runner file against six scripted answers, one for
each outcome, and prints the caller record. It sends no request. The header states
`mode: rehearsal`. The clocks are real and the two workers are real threads, so two
rehearsals give the same outcomes and not the same bytes.

[`v2-s5-001-pr2-rehearsal-caller.jsonl`](../proof/serving/v2-s5-001-pr2-rehearsal-caller.jsonl)
is one committed rehearsal: 12 request lines, two of each outcome. It shows the
format. Its instants are not measurements, and its latencies describe nothing.

### The real path

The real path runs only when an operator starts it. It needs a cluster that holds
the release, and it sends real requests to the model.

```text
INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh start \
  --experiment-id ID --run-id ID --duration-seconds N [--release-id SHA256]
INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh status --run-id ID
INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh collect --run-id ID
INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh cleanup --run-id ID
```

- `start` verifies the selected target, writes `plan.json` and `manifest.json` under
  `.artifacts/reliability-runner/runs/<run-id>/`, and applies the manifest. It
  returns when the Job is created.
- `status` prints the counts of the Job. It changes nothing.
- `collect` writes the log of the pod to `caller.jsonl` in the same directory, and
  checks it against the plan. Exit status `5` says that a rule refused the record.
- `cleanup` deletes the Job and the ConfigMap by name, waits for the pod, and fails
  when an object of the run is still present.

The script does not wait for the run, and `collect` before the run ends gives a
record with no end line. The directory under `.artifacts/` is host state. Version
control ignores it.

## What this does not establish

- **Nothing about a caller of a release.** No run was started in a cluster. The
  script was read as text by the suite. It was not executed, so its four actions are
  not observed.
- **Nothing about a cluster whose network plugin enforces NetworkPolicy.** The chart
  admits traffic to the API pods only from pods of the release, and from a named
  collector. The runner is not a pod of the release, and its labels match no
  selector of the release. On a cluster that enforces the policy, the committed
  policy refuses the runner, and each request is a `transport-error` or a `timeout`.
  The chart has no allowance for a caller, and this change adds none. Whether the
  selected local cluster enforces the policy was not checked in this change.
- **Nothing about the log of a long run.** The record is the log of one container.
  A container runtime can rotate a log by size, and a rotated log loses its first
  lines. The checker then refuses the record, because its header is missing. The
  bounds of a run keep a record small. No run measured the size.
- **Nothing about the release identifier.** It is declared, and nothing compares it
  with the release that the cluster holds.
- **Nothing about the clock of the pod.** `startedAt` and `finishedAt` are the
  pod's wall clock. Nothing compares it with the clock of another collector.
- **Nothing about capacity.** The pod requests 100 m of CPU and 64 Mi of memory.
  The capacity preflight does not count it.
- **Nothing about ownership records.** The Job and the ConfigMap of a run are not
  rows of the resource ownership inventory.
- **Nothing about how the Service spreads requests.** A record names no pod.
- **Nothing about a representative workload, an overload point, or a production
  SLO.** A run under RP-1 cannot support C3.
