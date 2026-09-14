# Repeatable LLM load generation

Status: **implemented and rehearsed; never run against a real release.** The
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
| Success | HTTP 200, adapter `real`, model `qwen3-1-7b-q8-0`, runtime `llama.cpp llama-server`, usage counts present |
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

The API's own upstream deadline is `api.requestTimeoutMs`, 120,000 ms. The client
deadline must be above it, or the loader refuses the profile. Set below it, a slow
completion would end at the client as a `timeout`, and the API's canonical
`upstream-timeout` answer would never be seen. The record would then describe the
load generator's patience rather than the platform's behaviour.

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
always allowed to finish**, bounded by its deadline, and is always recorded. The
level's window runs from its start to the last completion, so it can extend past
the duration by up to one deadline. The worst case above counts that for every
level, every warm-up request timing out, and both identity probe requests timing out.

With one parallel slot in the runtime, concurrency above 1 queues inside the runtime.
That queue is what a higher level exposes, and this tool does not interpret it.

### Why the ceilings are in code

The largest values a profile may name are constants in `tools.llm_load.core`, not
values read from the profile: 6 levels, concurrency 8, 20 warm-up requests, 500
requests per level, 900 s per level, a 300,000 ms deadline, and 3,600 s for the
worst case of a whole run. A heavier run therefore cannot be authorized by editing
the record that is supposed to bound it.

## How every request is classified

Every dispatched request gets exactly one sequence number and exactly one outcome.
`classify` decides the outcome from the status, the parsed body, the transport
failure kind, and the latency, and from nothing else, in this order:

| Outcome | When |
|---|---|
| `timeout` | No answer arrived within the deadline, **or** an answer arrived after it |
| `transport-error` | The connection failed before any answer: refused, reset, or closed |
| `identity-refused` | An answer named an adapter other than the required one, whatever its status. **The run is aborted** |
| `http-error` | A status other than 200. The canonical error code is kept only if it is a plain token; anything else is recorded as `unrecognized` |
| `invalid-response` | Status 200 with a body naming another model, carrying no choice, or lacking usage counts |
| `success` | Anything left |

Token counts and the finish reason are kept only for a `success`. Latency
percentiles are computed over successes only, and the summary says so in the member
that holds them (`latencyOfSuccesses`). A percentile that mixed fast refusals with
completions would read faster than any completion was.

A mock answer never counts. The target is refused **before any load** if its
readiness answer or its model list names an adapter other than `real`. That
includes the rehearsal stub's `synthetic-stub`. If a later answer names one, the run
stops, that request is recorded as `identity-refused`, and the record ends as
`aborted`.

## What a run records about its environment

The raw header carries three things. Each field says how it is known:

| Source | Fields | How each is known |
|---|---|---|
| Generator host | operating system, release, architecture, logical CPUs, total memory, Python version | Read from the host running the tool. No hostname, user, network identity, or path |
| Served identity | readiness status, adapter kind, model identifier, model revision, runtime name, runtime version | **Observed** from the target's `/health/ready` and `/v1/models` before any load, and compared with the profile and the model record |
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
`checkedAgainstRepository`, `declaredOnly`, and `observedFromApi`. A reader never has
to guess whether a fact was checked. **Checked means the stated value agrees with
this repository, not that the cluster was asked.** A facts file naming
`docker-desktop` is accepted because that is a published provider; nothing in this
tool confirms that the forward reaches a Docker Desktop cluster. Collecting these facts from the cluster
automatically, and correlating a run with Kubernetes resource data, is left to the
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
2. The real release installed as
   [the paved road](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md)
   installs it: the Terraform prerequisites applied, the API image and model seed
   image loaded, and `helm install` from `ci/real-values.yaml` plus the two
   generated overlays. Every workload must be ready.
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
git rev-parse HEAD

python -m tools.llm_load run \
  --target-url http://127.0.0.1:18091 \
  --environment-facts .artifacts/llm-load-facts.json \
  --confirm-real-load
```

Keep the facts file under `.artifacts/`, which version control ignores. The Service
port-forward goes to one selected pod rather than through the Service's virtual IP,
so a run through it says nothing about how load is spread across replicas. It also
adds the forward's own cost to every latency. Both belong in any later reading of
the numbers.

Without `--confirm-real-load`, `--target-url`, and `--environment-facts`, `run`
refuses and sends nothing. The target must be `http://127.0.0.1:<port>`, with no
path, query, or credentials. The transport ignores proxy environment variables and
never follows a redirect.

These real-run commands are **documented and unexecuted**. They name only objects
that the committed chart renders and that the paved road installed. No real load
run has been performed with this tool.

### Regenerate a summary from a raw record set

```text
python -m tools.llm_load summarize --raw <path to raw.jsonl>
```

Summarizing is a pure function of the raw record set. It reads no clock, contacts
nothing, and uses integer arithmetic throughout. The summary is written beside the
raw set for that run's mode.

### Exit codes

`0` the run completed. `3` refused before sending load, or the run was aborted by an
identity refusal. `4` an unexpected local failure. `6` the run ended without being
usable, for example after a failed warm-up. `130` interrupted. An interrupt that
arrives while a phase is running stops dispatch, lets the dispatched requests finish,
and writes the partial record, ending `interrupted`. One that arrives at any other
moment ends the command before any record is written, and it says so.

## Outputs

| File | Format | Contents |
|---|---|---|
| `.cache/inferops/load/<real or rehearsal>/raw.jsonl` | JSON Lines | One `run` header, then each phase's `phase` record followed by its `request` records, then one `end` record |
| `.cache/inferops/load/<real or rehearsal>/summary.json` | JSON | The deterministic reduction of `raw.jsonl` |

Neither file is committed until a reviewed change promotes it into
[`docs/proof/serving/`](../proof/serving/).

A `request` record carries `sequence`, `phase`, `levelId`, `concurrency`,
`worker`, `dispatchOffsetMs`, `latencyMs`, `outcome`, `status`, `errorCode`,
`finishReason`, `inputTokens`, `outputTokens`, `adapterKind`, and `modelRef`.
**It never carries the prompt, the completion, or a response header.** The raw
header records the fixture's identifier and message count, not its text.

A `phase` record carries its bounds (`requestCeiling`, `durationSeconds`), its
`startedOffsetMs` and `windowMs`, how many requests it `dispatched`, and its
`stopReason`: `request-ceiling`, `duration`, `aborted`, or `interrupted`. The `end`
record carries the run's state (`completed`, `warmup-failed`, `aborted`, or
`interrupted`), the reason, the elapsed time, and the total dispatched.

The reader refuses a raw record set that:

- has a gap or a repeat in its sequence numbers;
- has a phase whose `dispatched` disagrees with its request records, or exceeds its
  ceiling;
- has a request under the wrong phase, or a worker its phase did not have;
- counts tokens for a failure, or keeps free text where a token belongs;
- claims a benchmark or a portable capacity figure, or drops the boundary sentence;
- is real without a supported provider, or synthetic with one.

The summary reports, for the warm-up and each level: its outcome counts (every
outcome, zeros included), successful and unsuccessful counts, window, the latency
of successes, successful requests and output tokens per second in thousandths, and
token totals. Its `accounting.balanced` member says whether the outcome counts add
up to the requests dispatched. Its `usable` member is true only for a `completed`
run. It contains no judgement about saturation.

## What this cannot establish

- Nothing about capacity, saturation, or where a level degrades. No level is
  compared with another here.
- Nothing about `kind`, another provider, a second host, or a GPU.
- Nothing about how a Service spreads load, because the documented forward goes to
  one pod.
- Nothing about the cluster facts it records as declared. They are what the operator
  wrote.
- Nothing about connection reuse. Every request opens a new loopback connection.
- On Windows, a connection to a closed loopback port is retried for about two
  seconds before it is refused. A deadline shorter than that would report a refused
  connection as a `timeout`. The committed deadline is 150 s, so this does not affect
  a real run, but it is why the transport test uses a generous deadline.
