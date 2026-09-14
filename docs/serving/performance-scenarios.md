# Performance scenarios

Status: **implemented and executed once, on `docker-desktop`.** The committed scenario
matrix
[`performance-scenarios.v1.json`](../../deploy/serving/experiments/performance-scenarios.v1.json),
the workflow
[`scripts/environment/performance-scenarios.sh`](../../scripts/environment/performance-scenarios.sh),
and the [`tools.performance_scenarios`](../../tools/performance_scenarios/) command run
the [repeatable load profile](llm-load-generation.md) against one real release and keep,
on one wall clock, what is needed to read the result later: the raw load records, the
node's resource counters, the release collector's readings, and the environment the
cluster reported. The first run and its record are in
[the V1-S4-004-PR1 validation record](../proof/serving/v1-s4-004-pr1-validation.md).

> [!WARNING]
> **Every figure this produces is a bounded observation of one executed matrix** on
> the provider, host, model, runtime, release, and load profile recorded beside it
> ([ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)).
> It is not a portable capacity figure, a production SLO, or a benchmark of
> Kubernetes, the model, the runtime, or any provider. The descriptor and the record
> carry `productionBenchmark: false` and `portableCapacityClaim: false`, and the
> record carries `saturationJudged: false`: nothing here decides where the setup
> degraded. That analysis is separate work and cites the record.

## What the matrix fixes

| Setting | Committed value | Why |
|---|---|---|
| Load | The load profile, pinned by its LF-normalized SHA-256 | A matrix whose profile changed underneath it would describe a different run |
| Scenarios | `warmup` (concurrency 1), `c1` baseline, `c2` and `c4` higher-load | Exactly the profile's warm-up and levels, in order; the loader refuses any other set |
| Provider | `docker-desktop` only | The V1 reference provider. `kind` is supported by the platform and not described here, so a run on it is refused |
| Release | One API replica, one runtime replica, and the collector | The forward reaches one pod; a record of more replicas would say nothing about them |
| Schedule | 2 repetitions; 60 s idle baseline; 90 s settle between runs and after the last | Settles are at least two collector scrapes, so every counter a run moved is scraped before the next reading |
| Stability | Every Deployment available, no container restart, the same pods throughout, every run completed | Checked by the record, not assumed. **No idle CPU threshold** is applied: background use is measured and recorded, because any bar chosen here would be arbitrary |
| Resources | The node's cgroup v1 counters every 2,000 ms; a gap above 8,000 ms, or a phase with fewer than 3 samples, makes the record unusable | See below |
| Telemetry | Nine sum-aggregated series over the whole schedule at a 15 s step; three counter reconciliations; the dashboard's panel expressions at each phase end | Aggregated so that no per-target label, such as a pod address, reaches a record |
| Forwards | API on `127.0.0.1:18093`, collector on `127.0.0.1:19093` | The API behind the forward is unauthenticated; both bind loopback only |

`python -m tools.performance_scenarios check` validates all of them and prints a
summary: the scenarios, the schedule, the sample interval, and the series and
reconciliation counts.
The ceilings that bound them — three repetitions, a 7,200 s worst-case schedule, 20
series, a sample interval between 1,000 and 10,000 ms — are constants in
`tools.performance_scenarios.core`, not values read from the descriptor.

## What is read, and how

### The environment, from the cluster's own answers

After every tier's rollout and before any load, the workflow saves what the API
server, Helm, the node, and the container engine report: versions, the node's capacity
and allocatable resources, the release, its Deployments with their container resources
and arguments, its configuration, its pods, and a count of running pods in other
namespaces. The record keeps a fixed subset. Other workloads are **counted, never
named**, and nine configuration keys are kept out of the ConfigMap, among them the
request deadline, the output-token limit, the model revision, and the runtime threads.

The load facts file that `tools.llm_load run` requires is **derived** from those
answers by `python -m tools.performance_scenarios facts`, not typed by an operator, and
then checked by the load tool as before. The environment also keeps each image's
config ID and every digest it carries. The digests of the files a run executes are
recorded beside the repository revision, so a record can say which code produced it
even when the tree was not clean.

**How an image is bound to its pod.** A pod's `imageID` names one of an image's
repository digests, and one image can carry several. The first real attempt of this
workflow showed it: the API build had been imported into the node twice, under two
OCI index digests, which the node's containerd holds as one image with two names. The
pod reported the older name while its template named the newer, and a digest
comparison refused a pod that was running the right bytes. The binding is now made
through the node's own answer, `crictl inspecti`, for the template reference: the image
it resolves to, and every digest that image carries. A pod whose `imageID` is not among
them is refused, and the record keeps the image's config ID.

### The resource counters, from inside the node

The sampler reads CPU usage and memory. It does **not** read the cgroup's `cpu.stat`
throttling counters, so a record cannot tell a CPU limit that bound from threads that
were simply busy.

The workflow locates each release pod's cgroup directory once, by the pod UID the API
server reported, and refuses a tier with other than one match. It then runs one
read-only `sh -c` in the verified node container per sample, which prints:

| Tier | Source | What the record derives |
|---|---|---|
| Virtual machine | `/proc/stat`, aggregate jiffies | Busy CPU across the VM's logical processors |
| Node | The node container's root `cpuacct.usage` and `memory` cgroup | CPU, and working set (usage less inactive file) |
| Each release pod | The pod's `cpuacct.usage` and `memory` cgroup | The same, per tier |

Each sample is stamped with bash's `EPOCHREALTIME` immediately before and after the
read, on the same host clock `tools.llm_load` reads for its millisecond origin, and
with the node's own nanosecond clock. The record places a sample by the host midpoint
and keeps how long the read took.

### The collector, after the runs

Once the last settle has passed, `python -m tools.performance_scenarios telemetry`
asks the release's own Prometheus, through its loopback forward, for:

- each descriptor series over the whole schedule;
- the three reconciled counters at the moments the schedule defines — each run's launch
  and the next run's launch or the final settle;
- every dashboard panel expression, evaluated at the end of each phase.

Proxies are ignored and redirects refused.

## How a phase is placed

`tools.llm_load` now writes `startedAtEpochMs` into the raw header: the wall-clock
millisecond read beside the performance counter that every phase and request offset
is measured from. A phase's window is that origin plus its `startedOffsetMs`, to its
last completion.

A tier's CPU over a phase is **the increase of its cgroup counter between the first and
last samples inside the window, over the node clock between them**. No sample taken
before a window opens or after it closes is used, so a figure never borrows load from
a neighbouring phase. Memory is the largest working set any sample inside the window
read. `nodeOutsideRelease` is the node's CPU less the three release pods', which is
what everything else on the node used.

## What makes a record usable

| Check | Fails when |
|---|---|
| `every-deployment-available` | A tier did not have its desired replicas available before load |
| `same-pods-throughout` | A tier's pod UID differs between the readings before and after the runs |
| `zero-container-restarts` | Any container restart was counted in either reading |
| `telemetry-series-answered` | The collector refused a range query |
| `run-N-completed` | A load run did not end `completed`, or exited non-zero |
| `counters-reconcile-with-raw-records` | The API's request counter did not rise by exactly the requests the raw set dispatched, or the API's or runtime's output tokens by exactly the tokens it recorded |
| `resource-samples-cover-every-phase` | The first sample is more than the maximum gap after the idle window opens, the last is before the last phase closes, two samples are further apart than the maximum gap, a read between the idle window's start and the last phase's end is missing the node's or any release pod's CPU counter, or a measured phase or the idle window has fewer than the minimum samples |

Once the workflow reaches the record, a record whose checks fail is still written, with
`usable: false`, and the workflow exits non-zero. A load run that does not complete
stops the workflow before any record is built; its raw set is kept in the run
directory. Its `observations` list facts a later analysis must account for: a
phase with non-successful requests, a level stopped by its duration rather than its
request ceiling, a counter that disagreed.

## Commands

From Git Bash at the repository root, inside the locked environment
(`uv run --locked ...`).

### Validate the matrix without contacting anything

```text
scripts/environment/performance-scenarios.sh check
python -m tools.performance_scenarios check
```

### Run it, only when authorized

Prerequisites are those of [a real load run](llm-load-generation.md#run-against-a-real-release-only-when-authorized),
except that this workflow installs and uninstalls the release itself: the API image
built, loaded, and its overlay written with `scripts/environment/api-image.sh`, the
model seed image prepared and its overlay written with
`scripts/environment/model-seed-image.sh values > .artifacts/model-seed-values.yaml`,
no existing release named `inferops`, and a `kubectl` within one minor of the server.

```text
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/performance-scenarios.sh run \
  --values charts/inferops-llm/ci/real-values.yaml \
  --values .artifacts/api-image-values.yaml \
  --values .artifacts/model-seed-values.yaml \
  --confirm-real-kubernetes
```

It verifies the target, applies the Terraform prerequisites, installs the release,
waits for the runtime, the API, and the collector, records the environment, starts the
sampler, opens both forwards, waits out the idle baseline, runs each repetition, asks
the collector, uninstalls the release, checks for residue and an unchanged claim count,
and builds the record. The run in the validation record took 16 min 56 s, by the operator shell's timestamps.

A run directory that already exists is refused rather than overwritten. On failure the
sampler and the forwards are stopped, diagnostics go to
`.artifacts/performance-scenarios/`, and an installed release is left for inspection.

### Rebuild or verify a record

```text
python -m tools.performance_scenarios record --run-dir .cache/inferops/experiments/performance-scenarios
python -m tools.performance_scenarios verify --dir docs/proof/serving --prefix v1-s4-004-pr1-
```

`record` reads the files in the run directory, and from the repository the descriptor,
the load profile, and the chart values the descriptor is checked against. `verify`
regenerates a committed record from its committed inputs and fails if it differs in any
byte after line endings are normalized to LF.

### Exit codes

`0` usable, or validated. `1` a committed record does not regenerate. `3` a refusal,
including a malformed input. `6` a record was written and is not usable. The shell
workflow exits non-zero whenever any step did not complete.

## Outputs

| File | Contents |
|---|---|
| `.cache/inferops/experiments/performance-scenarios/cluster/` | The cluster's answers. **Not committed**: they hold node addresses and other workloads' names |
| `.../facts.json` | The derived load facts |
| `.../resource-samples.txt` | One line per node read |
| `.../windows.json` | The schedule as kept: idle window, each run's launch, exit, and code, and the final settle |
| `.../load/run-N-raw.jsonl` | Each repetition's raw load record set |
| `.../telemetry.json` | The collector's answers |
| `.../record/` | The committed-form inputs and `performance-record.v1alpha1.json` |

A record is promoted by copying `record/` into `docs/proof/serving/` under a prefix.
Every input the record is built from is refused if it carries a value shaped like a
Windows drive path, a user or home directory, or an IPv4 address other than loopback.
Host names and IPv6 addresses are not recognized and are left to review. No prompt or
completion text reaches any input.

## What this cannot establish

- Nothing about capacity, saturation, or where a level degrades. The record places
  figures side by side and judges none.
- Nothing about `kind`, another host, a second replica, a GPU, or a Service spreading
  load: the forward reaches one API pod.
- Nothing about varied prompts. Every request sends the same fixture, so the runtime's
  prompt cache serves nearly all of every prompt after the first.
- Nothing finer than a collector scrape about telemetry. The collector scrapes every 30
  seconds; a series locates an event to within a scrape and a rule evaluation.
- Nothing free of the observer. The sampler's `docker exec` runs inside the node and is
  counted in the node and virtual-machine tiers, and every latency includes the
  port-forward.
- Nothing about other workloads beyond how much CPU and memory they left. The node and
  the virtual machine are shared, and their use is recorded, not controlled.
