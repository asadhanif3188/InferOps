# Repeatable LLM load generation

Status: **implemented, rehearsed, and run against a real release** by
[the performance scenarios](performance-scenarios.md), which install the release,
derive the facts file from the cluster, and run this profile twice. The
versioned profile
[`llm-load-profile.v1.json`](../../deploy/serving/load/llm-load-profile.v1.json) and
the [`tools.llm_load`](../../tools/llm_load/) command send a fixed, bounded inference
load through the InferOps API of an installed release, and turn it into a raw
record set plus a summary regenerated from it. The whole tool has been executed
against an in-process stub over loopback HTTP, and that synthetic rehearsal is
committed as
[an example raw record set](../proof/serving/v1-s4-003-pr1-rehearsal-raw.jsonl) and
[its summary](../proof/serving/v1-s4-003-pr1-rehearsal-summary.json). The
validation record is
[`v1-s4-003-pr1-validation.md`](../proof/serving/v1-s4-003-pr1-validation.md).

> [!WARNING]
> **A load run is a bounded observation, and not a benchmark.** Every latency and
> rate it produces describes that one run, on the provider, host, model, runtime,
> and profile recorded beside it. It is not a portable capacity figure, a
> production SLO, or a benchmark of Kubernetes, the model, the runtime, or any
> provider. The profile, the raw header, and the summary each carry
> `productionBenchmark: false`, `portableCapacityClaim: false`, and the same
> boundary sentence, and the loader refuses a profile or a raw record set that says
> otherwise. The generic `sustained-throughput-and-capacity-under-load` claim stays
> deferred, and the `capacity` lane stays unrun.

This guide covers generating load. It does not analyze saturation, compare levels,
or decide what a result means. That analysis is a separate piece of work, and nothing
here makes it early.

## What the profile fixes

| Setting | Committed value |
|---|---|
| Fixture | `llm-load-single-turn-v1`: one `user` message, `POST /v1/chat/completions`, model `qwen3-1-7b-q8-0`, `stream: false` |
| Generation | `maxOutputTokens` 128, `temperature` 0, `contextSizeTokens` 4096, `parallelSlots` 1 |
| Warm-up | 3 requests at concurrency 1 |
| Levels | `c1` = 1, `c2` = 2, `c4` = 4 |
| Level bound | 180 s or 60 requests, whichever is reached first |
| Request deadline | 150,000 ms |
| Worst case | 1,460 s |
| Success | HTTP 200, adapter `real`, model `qwen3-1-7b-q8-0`, usage counts present. The runtime name `llama.cpp llama-server` is required of the identity probe before any load, not of each answer |
| Percentiles | Nearest rank; P50, P95, P99 over successful requests only |

`python -m tools.llm_load check` prints the same values from the file itself.

### Why the generation settings are not sent

The API accepts only `model`, `messages`, and `stream`. The output token limit and
the temperature are the release's, not the request's. The profile therefore
**records** them instead of sending them, and the loader compares every one with
[the runtime profile](runtime-profile.local.v1.json) and with the chart's values:
[`values.yaml`](../../charts/inferops-llm/values.yaml) with
[`ci/real-values.yaml`](../../charts/inferops-llm/ci/real-values.yaml) layered on
top, in the order a real install passes them to Helm. A drift in any of them stops
the load before a run starts.

The fixture body is also passed through the parser the API itself uses. A fixture
can satisfy every other check and still be refused by the API on every request;
[the serving baseline](local-serving-baseline.md) learned that from a real run.

### Why the deadline is above the API's

The API's own deadline is `api.requestTimeoutMs`, 120,000 ms. The client deadline
must be above it, or the loader refuses the profile. Set below it, a slow completion
would end at the client as a `timeout`, and the platform's own answer at its
deadline would never be seen. The record would then describe the load generator's
patience rather than the platform's behaviour.

**What that answer usually is.** In the API container, two timers share that one
budget: the HTTP carrier's response timer in
[`tools/api_carrier/http_server.py`](../../tools/api_carrier/http_server.py), and the
adapter's own. The carrier's starts first, when the request arrives, so it
normally fires first and answers `504` with an **empty body**. The adapter's
canonical `upstream-timeout` body is rarely what a client receives. A load record
therefore shows a platform deadline as `http-error`, status `504`, with `errorCode`
and `errorCondition` both null, and the summary's `httpStatuses` counts it. This
was read from the code, not observed.

**How close a level is to that deadline.** The runtime has one parallel slot, so at
concurrency 4 a request can wait behind three others. With at most 128 output
tokens, a completion's time is set by the decode rate of the host that runs it.
[The runtime feasibility trial](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md)
recorded a worst-case 128-token completion of 14.52 s on one CPU host. Four of those
in a row is about 58 s: inside 120 s, but a slower or busier host shrinks that margin
quickly. Whether the pinned runtime abandons a job when the API
closes the connection after its deadline has not been checked. If it does not, a
timed-out job keeps the slot while the next request waits, and timeouts at the
highest level can compound. Read a level full of `504`s with that in mind.

### Why a warm-up, and why a failed one stops the run

The first requests after a start measure caches and the first prompt-processing
pass. They are recorded in their own `warmup` phase and never reach a level. If any
warm-up request is not a success, **no level runs**. The record ends as
`warmup-failed`, because a level measured behind a failed warm-up describes the
failure.

### Why a closed loop, and what a level's bound means

Each level starts `concurrency` workers. Each worker sends the fixture, waits for
the answer, and sends again. A level stops dispatching when its request ceiling or
its duration is reached, whichever comes first. **A request already dispatched is
always allowed to finish** and is always recorded. The level's window runs from its
start to the last completion, so it can extend past the duration by up to one
deadline. The worst case above counts that for every level, every warm-up request
timing out, and both identity probe requests timing out.

**The worst case is not a hard bound.** The deadline is given to the HTTP client as a
socket timeout, which limits each wait for bytes rather than the whole request. A
server that keeps sending slowly can hold a request past 150 s. Such an answer is
still classified `timeout` when it ends, because its latency is compared with the
deadline, but it lengthens the run. The InferOps API sends a completion's body in
one write, so this is not expected from it; it is possible through anything in
between.

With one parallel slot in the runtime, concurrency above 1 queues inside the runtime.
That queue is what a higher level exposes, and this tool does not interpret it.

### Why the ceilings are in code

The largest values a profile may name are constants in `tools.llm_load.core`, not
values read from the profile: 6 levels, concurrency 8, 20 warm-up requests, 500
requests per level, 900 s per level, a 300,000 ms deadline, 3,600 s for the worst
case of a whole run, and 5 transport errors in a row before a run stops. A heavier run therefore cannot be authorized by editing
the record that is supposed to bound it.

## How every request is classified

Every dispatched request gets exactly one sequence number and exactly one outcome.
`classify` decides the outcome from the status, the parsed body, the transport
failure kind, and the latency, and from nothing else, in this order:

| Order | Outcome | When |
|---:|---|---|
| 1 | `timeout` | No answer arrived before the client's socket timeout |
| 1 | `transport-error` | The connection failed before any answer: refused, reset, or closed |
| 2 | `identity-refused` | An answer named an adapter other than the required one, whatever its status and however late. **The run is aborted** |
| 3 | `timeout` | An answer arrived after the deadline, whatever it says |
| 4 | `http-error` | A status other than 200. The canonical error `code` and the `conditionId` from its details are kept as `errorCode` and `errorCondition`, each only if it is a plain token and `unrecognized` otherwise. A body that is not a canonical error, such as the carrier's empty `504`, leaves both null |
| 5 | `invalid-response` | Status 200 with a body naming no adapter or another model, carrying no choice, or lacking usage counts |
| 6 | `success` | Anything left |

`errorCondition` is what separates two refusals that share a code. A draining API
and an unreachable runtime both answer `503 capability-unavailable`, and only the
condition identifier tells them apart.

Token counts and the finish reason are kept only for a `success`. Latency
percentiles are computed over successes only, and the summary says so in the member
that holds them (`latencyOfSuccesses`). A percentile that mixed fast refusals with
completions would read faster than any completion was.

A mock answer never counts. The target is refused **before any load** if its
readiness answer or its model list names an adapter other than `real`. That
includes the rehearsal stub's `synthetic-stub`. If a later answer names one, the run
stops, that request is recorded as `identity-refused`, and the record ends as
`aborted`.

**A lost target stops the run too.** Five `transport-error` outcomes in a row within
a phase end the run as `transport-lost`. A connection that fails before any answer is
the forward, or the path to it, gone, not the platform answering. Without this, a
dead port-forward fails each request in about a millisecond, every level spends its
whole ceiling in seconds, and the run ends `completed` with a record of nothing but
the load generator's own loss of its target. Answers the API does give, such as
`503` while a model loads or `504` at its deadline, are the platform's behaviour.
They never stop a run, however many arrive in a row.

## What a run records about its environment

The raw header carries three things. Each field says how it is known:

| Source | Fields | How each is known |
|---|---|---|
| Generator host | operating system, release, architecture, logical CPUs, total memory, Python version | Read from the host running the tool. No hostname, user, network identity, or path |
| Served identity | readiness status, adapter kind, model identifier, model revision, runtime name, runtime version | **Reported by the API** in its `/health/ready` and `/v1/models` answers before any load, and compared with the profile and the model record. These are the API's statements about its own configuration: the model revision and runtime name are values it was built or configured with, and the runtime version is the pinned image digest unless something asked the runtime for its build. None of them is an independent observation of the model file or of the image a pod runs |
| Environment facts | see below | **Stated by the operator** in a file. Four are compared with what this repository records; six are recorded as declared only |

The facts file a real run requires:

```json
{
  "provider": "docker-desktop",
  "kubernetesServerVersion": "<kubectl version: serverVersion.gitVersion>",
  "chart": "inferops-llm-<Chart.yaml version>",
  "releaseRevision": 1,
  "apiImage": "<repository>@sha256:<digest of the API image the release runs>",
  "runtimeImage": "ghcr.io/ggml-org/llama.cpp@sha256:<the pinned digest>",
  "modelRevision": "<the pinned model revision>",
  "apiReplicas": 1,
  "runtimeReplicas": 1,
  "repositoryRevision": "<git rev-parse HEAD>"
}
```

| Fact | Checked against |
|---|---|
| `provider` | The providers [the provider contract](../environment/local-cluster-provider-contract.v1alpha1.json) publishes |
| `chart` | This checkout's `Chart.yaml` |
| `runtimeImage` | The pinned runtime image |
| `modelRevision` | [The model source record](model-source.v1.json) |
| `apiImage` | Must be pinned by digest, and must not be the chart fixture's labelled placeholder digest. The digest itself is declared only |
| `kubernetesServerVersion`, `releaseRevision`, `apiReplicas`, `runtimeReplicas`, `repositoryRevision` | Format only. **Declared, not verified**: this tool contacts no cluster |

The raw header lists the split under `environment.provenance`, as
`checkedAgainstRepository`, `declaredOnly`, and `reportedByApi`. A reader never has
to guess whether a fact was checked. **Checked means the stated value agrees with
this repository, not that the cluster was asked.** A facts file naming
`docker-desktop` is accepted because that is a published provider; nothing in this
tool confirms that the forward reaches a Docker Desktop cluster, or that it reaches
the release the facts name. Collecting these facts from the cluster automatically, and correlating a run with Kubernetes resource data, is left to the
work that executes and analyzes scenarios.

## Commands

From the repository root, inside the locked environment
(`uv run --locked python -m ...`).

### Validate the profile without sending anything

```text
python -m tools.llm_load check
```

This reads committed files only. It contacts no cluster, binds no port, and sends no
request.

### Rehearse the whole tool with no cluster or model

```text
python -m tools.llm_load rehearse
```

This runs the loopback check, the identity probe, the warm-up, all three levels,
the classifier, the raw writer, and the raw reader's accounting checks. It uses real
HTTP against a stub in the same process, on an ephemeral loopback port. The stub
names itself `synthetic-stub`. Its answers are a fixed function of each request's
sequence number: every ninth request is a `503 model-not-ready`, and every
thirteenth is a completion with no usage. The rehearsal shrinks each level to 12
requests, a 20 s bound, and a 5,000 ms deadline. The fixture, the generation
settings, the warm-up, and the levels stay the committed ones. The output is written
under `.cache/inferops/load/rehearsal/`, labelled `synthetic`, ceiling `C1`, with no
provider. **No latency it records describes serving.**

### Run against a real release, only when authorized

Prerequisites, all of which already exist in this repository:

1. An existing `docker-desktop` cluster, selected explicitly and verified by an
   environment script. `INFEROPS_PROVIDER=docker-desktop` must be set on every
   command, and any script that calls `inferops::resolve_target` writes the verified
   single-context `.kube/inferops-target.config`. InferOps never creates, resets, or
   deletes the cluster.
2. The real release installed and left running, the way
   [the dashboard validation run](../proof/telemetry/v1-s4-002-pr2-dashboard-validation.md#method)
   installed one: the API image built, loaded and its values overlay written with
   `scripts/environment/api-image.sh`, the model seed image prepared with
   `scripts/environment/model-seed-image.sh` and its overlay written with
   `model-seed-image.sh values > .artifacts/model-seed-values.yaml`, the Terraform prerequisites applied
   with `scripts/environment/terraform-prerequisites.sh apply`, and then
   `helm install inferops charts/inferops-llm --namespace inferops-release -f charts/inferops-llm/ci/real-values.yaml -f .artifacts/api-image-values.yaml -f .artifacts/model-seed-values.yaml`.
   The Kubernetes certification workflow is not a way to get here: it uninstalls
   the release it installs.
3. The pinned model already in the release's claim. This tool downloads nothing.

Then, from Git Bash:

```text
K="kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop -n inferops-release"
H="helm --kubeconfig .kube/inferops-target.config --kube-context docker-desktop -n inferops-release"

$K rollout status deployment/inferops-inferops-llm-runtime --timeout=10m
$K rollout status deployment/inferops-inferops-llm --timeout=5m
$K port-forward svc/inferops-inferops-llm 18091:8090      # leave running in its own shell

# Read the facts for the file above:
$K version -o json                                          # serverVersion.gitVersion
$H list -o json                                             # chart and revision
$K get deployment inferops-inferops-llm \
  -o jsonpath='{.spec.replicas} {.spec.template.spec.containers[?(@.name=="api")].image}'
$K get deployment inferops-inferops-llm-runtime \
  -o jsonpath='{.spec.replicas} {.spec.template.spec.containers[?(@.name=="runtime")].image}'
$K get pods -o jsonpath='{range .items[*]}{.metadata.name} {.status.containerStatuses[*].imageID}{"\n"}{end}'
git rev-parse HEAD

python -m tools.llm_load run \
  --target-url http://127.0.0.1:18091 \
  --environment-facts .artifacts/llm-load-facts.json \
  --confirm-real-load
```

Three of those readings need care when they are written into the facts file.
`helm list -o json` prints the revision as a string, and `releaseRevision` must be an
integer. `.spec.replicas` is the count the Deployment asks for, not the count that is
ready. The `image` in a pod template is the reference the chart rendered; the pods'
`imageID` values are what the node actually resolved, and they are worth checking
against it before the run.

Keep the facts file under `.artifacts/`, which version control ignores. The Service
port-forward goes to one selected pod rather than through the Service's virtual IP,
so a run through it says nothing about how load is spread across replicas. It also
adds the forward's own cost to every latency. Both belong in any later reading of
the numbers.

Without `--confirm-real-load`, `--target-url`, and `--environment-facts`, `run`
refuses and sends nothing. The target must be `http://127.0.0.1:<port>`, with no
path, query, or credentials. The transport ignores proxy environment variables and
never follows a redirect.

These hand-run commands are **documented and unexecuted** as written. The tool's
first real runs were made through
[`scripts/environment/performance-scenarios.sh`](../../scripts/environment/performance-scenarios.sh),
which installs and removes its own release, uses its own forward ports, derives the
facts file from the cluster's own answers instead of the readings above, and records
the evidence in
[the V1-S4-004-PR1 validation record](../proof/serving/v1-s4-004-pr1-validation.md).

### Regenerate a summary from a raw record set

```text
python -m tools.llm_load summarize --raw <path to raw.jsonl>
```

Summarizing is a pure function of the raw record set. It reads no clock, contacts
nothing, and uses integer arithmetic throughout. The summary is always written to
`.cache/inferops/load/<real or rehearsal>/summary.json`, chosen by the mode the raw
set records, and never beside the file named by `--raw`.

### Exit codes

`0` the run completed. `3` a refusal: before any load was sent; the run ended
`aborted` or `transport-lost`; or a later refusal such as a record that could not be
written. `4` an unexpected local failure. `6` the run ended without being usable, for
example after a failed warm-up. `130` interrupted. An interrupt that arrives while a
phase is running stops dispatch, lets the dispatched requests finish, and writes the
partial record, ending `interrupted`. One that arrives at any other moment ends the
command where it is. The raw record set may then have been written without its
summary, and the message says so.

## Outputs

| File | Format | Contents |
|---|---|---|
| `.cache/inferops/load/<real or rehearsal>/raw.jsonl` | JSON Lines | One `run` header, then each phase's `phase` record followed by its `request` records, then one `end` record |
| `.cache/inferops/load/<real or rehearsal>/summary.json` | JSON | The deterministic reduction of `raw.jsonl` |

Neither file is committed until a reviewed change promotes it into
[`docs/proof/serving/`](../proof/serving/).

A `request` record carries `sequence`, `phase`, `levelId`, `concurrency`,
`worker`, `dispatchOffsetMs`, `latencyMs`, `outcome`, `status`, `errorCode`,
`errorCondition`, `finishReason`, `inputTokens`, `outputTokens`, `adapterKind`, and `modelRef`.
**It never carries the prompt, the completion, or a response header.** The raw
header records the fixture's identifier and message count, not its text.

The `run` header also carries `startedAtEpochMs`: the wall-clock millisecond read
beside the performance counter that every phase's `startedOffsetMs` is measured from.
A request's `dispatchOffsetMs` is measured from its own phase's start, so its wall-clock
moment is `startedAtEpochMs` plus its phase's `startedOffsetMs` plus its
`dispatchOffsetMs`. `startedAt` is truncated to the second, which is too coarse to place a
phase against samples taken outside this process, such as a node's resource counters.
The reader accepts a raw set without it, because record sets written before it existed
are committed evidence. It was added for
[the performance scenarios](performance-scenarios.md).

A `phase` record carries its bounds (`requestCeiling`, `durationSeconds`), its
`startedOffsetMs` and `windowMs`, how many requests it `dispatched`, and its
`stopReason`: `request-ceiling`, `duration`, `aborted`, `interrupted`, or
`transport-lost`. The `end` record carries the run's state (`completed`,
`warmup-failed`, `aborted`, `interrupted`, or `transport-lost`), the reason, the elapsed time, and the total dispatched.

The reader refuses a raw record set that:

- has a gap or a repeat in its sequence numbers;
- has a phase whose `dispatched` disagrees with its request records, or exceeds its
  ceiling;
- has a request under the wrong phase, or a worker its phase did not have;
- counts tokens for a failure, or keeps free text where a token belongs;
- claims a benchmark or a portable capacity figure, or drops the boundary sentence;
- is real without a supported provider, or synthetic with one.

The summary reports, for the warm-up and each level: its outcome counts (every
outcome, zeros included), a count of each HTTP status received, successful and
unsuccessful counts, window, the latency of successes, successful requests and
output tokens per second in thousandths, and token totals. Its `accounting` member
gives the run's total dispatched and outcome counts; the reader has already refused
any set in which they could disagree. Its `usable` member is true only for a
`completed` run. It contains no judgement about saturation.

Latencies are measured with the platform's high-resolution performance counter.
The coarser monotonic clock ticks every 15.6 ms on Windows, and the first version of
this tool used it.

## What this cannot establish

- Nothing about capacity, saturation, or where a level degrades. No level is
  compared with another here.
- Nothing about `kind`, another provider, a second host, or a GPU.
- Nothing about how a Service spreads load, because the documented forward goes to
  one pod.
- Nothing about the cluster facts it records as declared. They are what the operator
  wrote.
- Nothing about connection reuse. Every request opens a new loopback connection.
- Nothing about varied prompts. Every request sends the same fixture, so after the
  first one the runtime's prompt cache can make prompt processing nearly free. Every
  latency is the cached case.
- Nothing about what the pods run on. The Docker Desktop VM's CPUs and memory, node
  capacity, container limits, the `kubectl` client version, and the deployed
  `requestTimeoutMs` and `maxOutputTokens` are not recorded. The last two are checked
  only against the committed chart values, and an overlay could change them.
- On Windows, a connection to a closed loopback port is retried for about two
  seconds before it is refused. A deadline shorter than that would report a refused
  connection as a `timeout`. The committed deadline is 150 s, so this does not affect
  a real run, but it is why the transport test uses a generous deadline.
