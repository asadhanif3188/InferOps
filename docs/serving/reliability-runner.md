# The RP-1 in-cluster reliability runner

Status: **implemented by `V2-S5-001-PR2`. No run was started in a cluster, and no
request was sent to a model.** The runner sends the
[RP-1 reliability workload](reliability-workload-rp-1.md) from a pod inside the
cluster to the API Service, and it writes one caller record for each run. The loop,
the classification, and the transport of the runner were executed against scripted
answers and against a loopback server. That is substituted execution, C1: the API
and the model were replaced, and it says nothing about either. The manifest, the
script, and the pages were read and not executed: C0. The change registers no claim.
The validation record is
[`v2-s5-001-pr2-validation.md`](../proof/serving/v2-s5-001-pr2-validation.md).

> **Since `V2-S5-006-PR1`:** the real path ran on the docker-desktop provider, in the
> attempts of the [Sprint 5 integration validation](../proof/experiments/README.md#the-sprint-5-integration-validation).
> The first attempt showed that the network plugin of that cluster enforces the
> release's network policy: no request of the runner reached the API. A run is now
> three objects: [the network policy of the run](#the-network-policy-of-a-run) admits
> the pod of that run to the API pods. The statements below that say that no run
> started are the state of `V2-S5-001-PR2`, and the paragraphs that this change
> edits say so.

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
| [`scripts/environment/reliability-runner.sh`](../../scripts/environment/reliability-runner.sh) | The real path. It creates the three objects of a run, reads the log of the pod, and deletes the three objects |
| [`tests/serving/test_reliability_runner.py`](../../tests/serving/test_reliability_runner.py) | The suite |

### Why no image is built

A run is one ConfigMap and one Job, and one network policy that
[admits the pod of the run](#the-network-policy-of-a-run). The ConfigMap holds the runner file and the
plan. The Job mounts both, read-only, and runs `python -I -u -B` on the file. The
image of the Job is an interpreter and no more: an image that holds Python 3.12,
named by digest. The script uses the image that the API Deployment names, because a
node that runs an API pod holds it. Nothing schedules the runner onto such a node,
and the script sets the pull policy `Never`. On a cluster with more than one node,
the pod of a run can be placed on a node that does not hold the image.

So no image holds the runner, and a change of the runner changes no image digest.
The ConfigMap states the SHA-256 of the runner file and of the plan as annotations.
The runner file computes both digests from the files it is started with, and it
writes them in the header of the record. With `--plan`, `verify` compares the digest
of the plan. It reports whether the digest of the runner file is the digest of the
file in this tree, and it does not refuse a record of an earlier runner file.

## What a run sends

A plan repeats the committed profile, and no option of the command changes these
values:

| Value | In the plan | Origin |
|---|---|---|
| Request | `POST /v1/chat/completions`, the fixture body of RP-1 | The RP-1 profile |
| Headers | `X-InferOps-Request-ID`: the run identifier and the sequence number. `X-InferOps-Correlation-ID`: the run identifier | The RP-1 profile, and the form of the V1 load harness |
| Workers | 2, closed loop: each worker sends, waits for the answer, and sends again | The RP-1 profile |
| Client deadline | 150,000 ms for each request | The RP-1 profile |
| Success rule | HTTP 200, adapter `real`, the model of the fixture, usage counts, at least one choice, within the deadline | The RP-1 profile |
| Connection | A new connection for each request, no redirect followed, no proxy variable read, no retry | The V1 transport, restated |
| Target | `http://inferops-inferops-llm.inferops-release.svc:8090` | The API Service of the release, by its cluster DNS name |

An operator states the rest:

| Option | Meaning | Bound |
|---|---|---|
| `--experiment-id` | The experiment that the run belongs to | Letters, digits, `.`, `_`, `-`; at most 63 characters; a letter or a digit first and last |
| `--run-id` | The run. It is part of the name of the Job | A lower-case DNS label of at most 40 characters |
| `--duration-seconds` | No request is dispatched after this time | From 1 to 3,600 seconds |
| `--request-ceiling` | No more requests than this are dispatched. The default is the maximum | From 1 to 10,000 requests |
| `--release-id` | The release identifier that the operator declares | 64 lower-case hexadecimal characters, or absent |

**The command has no option for the target.** The tool writes the Service name, the
namespace, and the port of the API Service into the plan. Three checks hold the
target:

- The runner file refuses a plan whose URL is not
  `http://<service>.<namespace>.svc:<port>`, built from the three members of the
  plan. A pod address, a loopback address, and a port-forward are not of that form.
  The runner file does not know the name of the API Service.
- The manifest builder refuses a plan whose target is not the registered one.
- The record checker refuses a header whose target is not the registered one.

The suite holds the registered Service name and port against the committed render
of the chart, and the namespace against the script library.

### The bounds of a run

- **The duration and the ceiling.** A worker dispatches no request after the
  duration, and none after the ceiling. A request that was dispatched is waited
  for, and it is recorded.
- **The Job.** `activeDeadlineSeconds` is the duration, one client deadline, and 120
  seconds. `backoffLimit` is 0. Kubernetes documents that a failed pod is then not
  replaced: a second pod would be a second run under one run identifier.
- **The finished Job.** `ttlSecondsAfterFinished` is 3,600 seconds. Kubernetes
  documents that it then deletes the Job and its pod, and that a log does not
  outlive its pod. So a record that was not collected in that time is lost. The
  time to live does not delete the ConfigMap. `cleanup` deletes it.
- **The stop request.** The runner file registers a handler for `SIGTERM` and for
  `SIGINT`. The handler makes the run dispatch no further request. The run waits
  for a request in flight, and it writes its end line with the state `interrupted`.
  `terminationGracePeriodSeconds` is one client deadline and 30 seconds. The suite
  calls the stop function directly. No signal was delivered to a runner process.

### The network policy of a run

The chart's policy admits traffic to the API pods from the pods of the release and
from a named collector, and from nothing else. The runner is neither, by design: its
labels match no selector of the release. So on a cluster whose network plugin
enforces the policy, the requests of the runner do not reach the API. The first
attempt of the Sprint 5 integration validation, on 2026-10-14, observed that on the
docker-desktop provider: each of its six requests ended at the client deadline, and
the API counted none. (Until `V2-S5-006-PR1` this page said that whether the local
cluster enforces the policy was not checked.)

Since `V2-S5-006-PR1` the manifest of a run holds a third object, first in the List:
a NetworkPolicy with the name and the labels of the run.

| Member | Value |
|---|---|
| Selects | The API pods: `app.kubernetes.io/name: inferops-llm`, `app.kubernetes.io/instance: inferops`, `app.kubernetes.io/component: platform-api`. The selector of the API Deployment and of the release's API policy in the committed render |
| Admits | A pod with `app.kubernetes.io/name: inferops-reliability-runner` and the `inferops.io/run-id` of the run, on TCP port 8090, the API container port of the committed render |
| Types | `Ingress` only. It states no egress rule, and it selects no runtime pod |

- **It edits no object of the release, and it widens what reaches the API.**
  Network policies add up: a pod is admitted when one policy that selects it admits
  the traffic. The default deny and the API policy of the release are unchanged, and
  the runner does not carry a label of the release. While the policy exists, the API
  pods admit one more set of pods on the API port than the release's policy alone
  admits.
- **It admits the pods labelled for the run, in the release namespace.** The rule
  matches by label and not by identity: any pod in that namespace that carries
  `app.kubernetes.io/name: inferops-reliability-runner` and the run's
  `inferops.io/run-id` is admitted, and the labels are written in the manifest. So
  whoever can create a pod in that namespace can be admitted while the policy
  exists. The pod of another run has another run identifier and is not admitted. The
  suite holds the selector and the port against the committed render.
- **It lives until the cleanup, and not until the end of the pod.** `start` refuses
  when a policy of the run's name exists. `kubectl create` makes the objects of the
  List in their order and does not stop at a refused one, so a policy that is not
  created leaves a Job whose requests are dropped, and a Job that is not created can
  leave a policy: `start` then fails, and `cleanup` removes what was made. The time to
  live of the finished Job removes the Job and its pod and not the policy, which has
  no owner reference. `cleanup` deletes it after the Job and the ConfigMap, and it
  fails when an object of the run, the policy included, is still present. When the
  deletion of the Job or the ConfigMap fails, `cleanup` stops before the policy, and
  a later `cleanup` removes it.
- **The runner's own traffic out is not restricted.** No policy of the release selects
  the runner pod, so its egress, DNS included, is open. That was so before this
  change.

**The client deadline is the timeout of each socket operation**, as it is in the V1
transport. An answer that arrives in many slow parts can take longer than the
deadline, and the outcome is then `timeout`. The active deadline of the Job and the
grace period assume that one request takes at most one client deadline. Kubernetes
documents that a Job which reaches its active deadline ends its pod. The log of
that pod, and the record in it, can then be lost. This was not observed.

### The wait after a request that is not a success

A worker waits 1,000 ms after a request whose outcome is not `success`. **The RP-1
profile states no such wait. It is a bound of this runner.** A refused connection
and an error answer can return at once. A closed loop with no wait would then send
without a bound on its rate while a fault is in progress, and it could reach its
request ceiling long before its duration. With the wait, a worker whose requests
fail at once sends about one request in one second. No run measured the rate.

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
  delete a pod on purpose. The runner ends at its bounds, at a stop request, and
  when a worker fails.
- **No summary of latency.** The tool counts outcomes. It computes no rate and no
  percentile.

## What the runner does not read

**The runner file reads the plan file, its own file, and the answers of the
target.** The suite holds these four statements:

- The pod of the manifest holds no service account token
  (`automountServiceAccountToken: false`), and the code of the runner file names no
  Kubernetes API.
- The code of the runner file names no readiness path and no model list, and each
  call that the loop makes is the `POST` of the plan.
- The Job of the manifest has no init container and no probe.
- The script has no command that waits for a rollout or for a Ready pod.

The runner file has no code that reads a state of Argo CD or a metric.

The script reads one thing from the release when no `--image` is given: the image
that the API Deployment names in its specification. It also reads whether an object
of the run's name exists. It does not read the status of a Deployment or of a pod of
the release.

## The caller record

A run writes its record to standard output, one JSON object on each line: one
header, one line for each request in the order in which the lines were written, and
one end line. The script reads the log of the pod.

Kubernetes documents that the log of a container holds standard output and standard
error. The runner file writes a refusal of a plan to standard error, and the
interpreter writes there when it fails. Such a line is not JSON, and the checker
then refuses the log as unreadable.

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
| `target` | The kind `api-service`, the Service name, the namespace, the port, and the base URL |
| `concurrency`, `requestTimeoutMs`, `success`, `bounds` | The values of the plan |
| `planSha256`, `runnerSha256` | The digests that the runner file computed of the two files it was started with |
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
| `timeout` | No answer arrived within the client deadline, or an answer that does not name another adapter arrived after it |
| `transport-error` | The connection failed before an answer arrived |
| `identity-refused` | The answer names an adapter other than the required one, at each status and at each latency |
| `http-error` | The status is not 200 |
| `invalid-response` | The status is 200, and the answer names no adapter, names another model, has no choice, or has no usage counts |
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
| `endState` | `duration`, `request-ceiling`, `interrupted`, or `failed` |
| `dispatched`, `recorded` | The number of requests sent, and the number of request lines written |
| `outcomes` | The count of each of the six outcomes |
| `elapsedMs`, `finishedAt` | The length of the run, and the UTC instant at which it ended |

The end state `failed` says that a worker failed in a way that no outcome names.
The run then wrote fewer request lines than it sent requests, and the checker
refuses the record. The runner file exits with status 0 at `duration` and at
`request-ceiling`, with 1 at `interrupted`, with 4 at `failed`, and with 3 when it
refuses the plan. **The exit status does not grade the answers**: a run in which
each request failed exits 0.

**A record with no end line is refused.** It is the log of a run that has not ended,
or of a pod that was stopped before it wrote the line.

### What a record never holds

The prompt text, the completion text, a response header, the address of a pod, and
the message of an error. A text that is read from an answer is kept only when it is
a short plain token, and a text that is not one is written as `unrecognized`.

The checker gives each line an exact set of members. A text member holds a
registered value, a pattern, or at most 64 characters of `[a-z0-9._-]`. So a line
cannot hold a text with a space, with an upper-case letter, or of more than 64
characters. No rule searches a record for a prompt or a completion.

## The rules

The tool has 16 rules. Four are of a plan and a manifest, and twelve are of a caller
record. Each command stops at the first refusal. Its message is the word `REFUSED`,
the rule, and the reason.

| Rule | Refuses |
|---|---|
| `runner-profile-refused` | A plan when the loader of the RP-1 profile refuses the committed profile |
| `runner-identifier-unsupported` | A run identifier or an experiment identifier that is not in the supported form |
| `runner-plan-refused` | A duration, a ceiling, or a release identifier that is not usable, a plan file that is unreadable or that the runner file refuses, and a manifest of a rehearsal plan or of a plan with another target |
| `runner-image-not-pinned` | An image that is not named by a `sha256` digest. The function also refuses a pull policy other than `Never` and `IfNotPresent` under this rule. The command refuses one as an unusable argument |
| `caller-record-unreadable` | A record file or a plan file that cannot be read, and a line that is empty, is not one JSON object, states one member twice, or has no record kind |
| `caller-record-header-missing` | A record whose first line is not a header, and a record with two headers |
| `caller-record-members-unsupported` | A line with a missing or unknown member, a member of another type, a text that is not a short plain token, a latency or a run length above 10,000,000 ms, and a header whose target is not the registered API Service |
| `caller-record-profile-unregistered` | A header whose profile, revision, content digest, or boundary sentence is not one that the profile tool registers |
| `caller-record-plan-differs` | With `--plan`: a plan that is not readable, and a header that does not name the digest of the plan or does not repeat its values |
| `caller-record-identity-differs` | A line that names another experiment, run, or release than the header, a request identifier of another sequence number, and a worker that the run does not have |
| `caller-record-time-invalid` | An instant that is not UTC to one millisecond, a request that finishes before it starts or starts before the run, a request that finishes after the run ends, and a run that ends before it starts |
| `caller-record-outcome-inconsistent` | A line whose `success`, status, latency, adapter, and kept members do not agree with its outcome |
| `caller-record-sequence-gap` | Sequence numbers that are not each number from 1 to the number of request lines, once |
| `caller-record-end-missing` | A record with no end line, and a line after the end line |
| `caller-record-counts-differ` | An end line whose counts are not the counts of the request lines, a run with more requests than its ceiling, and an end state that names a bound which the counts did not reach |
| `caller-record-holds-content` | A header that does not state `promptText: false` and `completionText: false` |

The table is in the order of the registered list. It is not the order in which a
command reaches the rules.

**A record that each rule accepts is a well-formed record.** Acceptance says nothing
about how many requests succeeded. The checker does not hold each relation between
the members of a line. For example, it does not compare `latencyMs` with the two
instants of a line, which come from another clock. The summary that `verify` prints holds counts and identities. It
holds no rate, no percentile, and no result.

## Commands

From the repository root, inside the locked environment
(`uv run --locked python -m ...`).

```text
python -m tools.reliability_runner plan --experiment-id ID --run-id ID --duration-seconds N
python -m tools.reliability_runner manifest --plan FILE --image REPOSITORY@DIGEST
python -m tools.reliability_runner verify RECORD [--plan FILE]
python -m tools.reliability_runner rehearse
```

No command has code that contacts a cluster or sends a request. Exit status `0` says
that the command printed its result. For `verify` it says that each rule accepted
the record. Exit status `3` says that one rule refused. Exit status `2` says that
the arguments are not usable. Exit status `4` says that the command failed in
another way.

### The rehearsal

`rehearse` runs the loop of the runner file against six scripted answers, one for
each outcome, and prints the caller record. It sends no request. The header states
`mode: rehearsal`. The transport, the wall clock, and the wait are replaced: the
wall clock is one real reading and one millisecond more for each later reading, and
the wait is not slept. The latency clock is real, and the two workers are real
threads. The first two answers wait for each other, so each worker sends at least
one request. Two rehearsals give the same outcomes and not the same bytes.

[`v2-s5-001-pr2-rehearsal-caller.jsonl`](../proof/serving/v2-s5-001-pr2-rehearsal-caller.jsonl)
is one committed rehearsal: 12 request lines, two of each outcome. It shows the
format. Its instants are not measurements, and its latencies describe nothing.

### The real path

The real path runs only when an operator starts it. It needs a cluster that holds
the release, and it sends real requests to the model. (Until `V2-S5-006-PR1` this
page said that the script was not executed against a cluster. The attempts of the
Sprint 5 integration validation ran its four actions on the docker-desktop
provider; their transcripts are in the run directories of that validation.)

```text
INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh start \
  --experiment-id ID --run-id ID --duration-seconds N [--release-id SHA256]
INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh status --run-id ID
INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh collect --run-id ID
INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh cleanup --run-id ID
```

- `start` verifies the selected target, and refuses when a Job, a ConfigMap, or a
  network policy of the run's name exists. It writes `plan.json` and `manifest.json`
  under `.artifacts/reliability-runner/runs/<run-id>/`, and creates the three objects. It
  does not wait for the run. A run identifier is used once: a second `start` under
  it is refused.
- `status` prints the counts and the two times of the Job. It changes nothing.
- `collect` reads the log of the pod and checks it against the plan. When each rule
  accepts it, the log is kept as `caller.jsonl`. When a rule refuses it, the log is
  kept as `caller.refused.jsonl`, the exit status is `5`, and a later `collect` can
  run. A `collect` before the run ends gives a log with no end line.
- `cleanup` deletes the Job, the ConfigMap, and the network policy by name, in that
  order, and fails when an object of the run is still present. It warns when no
  accepted record is kept.

The directory under `.artifacts/` is host state. Version control ignores it.

## What this does not establish

- **Nothing about a caller of a release beyond the attempts of the integration
  validation.** Those attempts ran on one provider, one node, and one release. (Until
  `V2-S5-006-PR1` this bullet said that no run was started in a cluster.)
- **Nothing about another network plugin.** The policy of a run was observed on one
  plugin, kindnetd with its policy controller, on docker-desktop. Another plugin can
  apply policies with other rules for traffic from a node or between policies.
  (Until `V2-S5-006-PR1` this bullet said that the chart has no allowance for a
  caller, and that whether the local cluster enforces the policy was not checked.
  The first attempt of the integration validation observed that it does.)
- **Nothing about the log of a long run.** The record is the log of one container.
  A container runtime can rotate a log by size, and a rotated log loses its first
  lines. The checker then refuses the record, because its header is missing. No run
  measured the size of a record.
- **Nothing about a signal.** No signal was delivered to a runner process.
- **Nothing about the release identifier.** It is declared, and nothing compares it
  with the release that the cluster holds.
- **Nothing about the clock of the pod.** `startedAt` and `finishedAt` are the
  pod's wall clock. Nothing compares it with the clock of another collector.
- **Nothing about capacity.** The pod requests 100 m of CPU and 64 Mi of memory.
  The capacity preflight does not count it.
- **Nothing about ownership records.** The Job, the ConfigMap, and the network
  policy of a run are not rows of the resource ownership inventory, and they do not
  carry the label `app.kubernetes.io/part-of`.
- **Nothing about how the Service spreads requests.** A record names no pod.
- **Nothing about a representative workload, an overload point, or a production
  SLO.** A run under RP-1 cannot support C3.
