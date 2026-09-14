# Reading the inference operations dashboard in thirty seconds

For an operator opening
[the inference operations dashboard](../../deploy/grafana/inferops-inference-operations.json)
during an incident. What each panel shows and why is in
[the dashboard document](inference-operations-dashboard.md). This page covers how to
read it fast and which conclusions it cannot support.

Every statement about how a panel behaves under failure was observed once, on one
single-replica release on `docker-desktop`, and is recorded with its screenshots in
[the V1-S4-002-PR2 validation record](../proof/telemetry/v1-s4-002-pr2-dashboard-validation.md).
It was not observed on `kind`, with two replicas, or on any other host.

## The thirty seconds

Read the rows top to bottom and stop at the first one that is wrong.

1. **First row, first.** `scrape-targets-answering-by-tier` must show both tiers.
   A tier with no row, or a `discovered no pod` in the panel beside it, means the
   tier has no pod: it cannot serve, and every panel below that reads it is empty or
   stale, so none of them can tell you why.
2. **Look for text before numbers.** A panel with no number shows text naming its
   state: *missing*, *not emitted*, or *not answerable*. None of those is a zero. If
   the text is too small to read, the title still names what the panel counts, and a
   panel without a number is never a zero.
3. **Counts before rates.** The three *since the API processes started* counts
   (`requests-since-start`, `errors-since-start`,
   `readiness-checks-failed-since-start`) are what show that something happened.
   The rate panels beside them can read `0` through a real failure.
4. **Then identity.** `build-identity-per-replica` and `runtime-operating-identity`
   say what is running. Nothing on the dashboard names the cluster provider. That
   comes from the run's evidence record.

## The four states, as they render

| What you see | State | What it means |
|---|---|---|
| A number, including `0` | `zero` or a value | Something was read. A zero on a count means the processes publishing now have counted nothing *since they started* |
| Text starting `Missing:` | `missing` | The expression returned nothing. The text lists what that can mean. Check the first row |
| A title saying *not emitted*, and `not emitted` in the panel | `not-emitted` | No component emits this metric. It will look the same when the model is down |
| A title saying *not answerable*, and a text panel | `not-answerable` | No telemetry source exists for this question. The text says what would have to exist |

## Every panel: what it answers and what it does not

Each row names a conclusion **the panel cannot support**. Each one is either a
misreading the validation run produced on purpose, or a property of how the panel
is built.

| Panel | Answers | Unsafe conclusion |
|---|---|---|
| `scrape-targets-answering-by-tier` | Did the collector reach each tier's pods at the last scrape? | "100% means the tier can serve." Reachability is not readiness: a pod still loading its model, or already deleted, can answer a scrape |
| `scrape-jobs-that-discovered-no-pod` | Does a tier have no pod at all? | "No absence recorded means pods are ready." It only means at least one pod exists |
| `api-identity-not-published` | Is no API process publishing its identity? | "It reads 1, so an API target answered without an identity." It also reads 1 when there is no API pod at all |
| `readiness-checks-failed-since-start` | How many readiness refusals have the running API processes counted? | "0 means no readiness trouble recently." The count starts again when an API process restarts: 20 went to 0 after a pod replacement |
| `readiness-refusals-by-component` | Which component the API names when it refuses? | "A flat 0 means no refusals." It read 0 beside 3 counted startup refusals, and a rate never sees events before a series' first scrape |
| `model-readiness` | Nothing. It is not emitted | "Not emitted, so the model is fine." It read the same while the serving runtime had zero replicas |
| `pod-container-and-runtime-readiness` | Nothing. It is not answerable | Any conclusion about pod or container readiness |
| `requests-since-start` | How many requests have the running API processes finished? | "The number is the release's total." It sums only processes publishing now, and until a deleted pod's series go stale it also includes that pod |
| `request-rate-by-outcome` | How the recent request rate splits by outcome | "server-error 0 means no server errors." Ten `capability-unavailable` failures read 0 here. And "a success rate means the API is up": it still showed one with no API pod running |
| `api-in-flight-by-replica` | How many requests each API replica has in flight, at scrape moments | "Empty means idle." The series appears only after a replica's first request |
| `runtime-processing-and-deferred` | How many requests the runtime is processing and deferring | "0 while the API shows traffic means the runtime is idle." It trails the API by a scrape and a rule evaluation, so a short burst can finish before it moves |
| `request-latency-quantiles` | Roughly where P50, P95 and P99 request duration fall | "Latency dropped, so things improved." Refused requests are included and fast: with only refusals in the window, P50 read 0.25 s against 1.62 s under traffic. Also "P95 is 2.41 s": it is an interpolation inside a bucket, and clients observed 1.54 s |
| `successful-requests-per-second` | The recent successful request rate | "Zero means nothing is being served *right now*." It is a five-minute rate and misses events before a series' first scrape |
| `queue-wait-p95` | Nothing. It is not emitted | Any conclusion about queueing. Use `runtime-processing-and-deferred` for whether queueing happened, never for how long |
| `errors-since-start` | How many errors the running API processes have counted | "0 means no errors recently." It went from 33 to 0 when the API pod was replaced |
| `unsuccessful-request-ratio` | What share of requests since start did not succeed | "Missing means no failures." It is missing while no request has been counted, and it does not depend on a published identity |
| `errors-by-code` | Which canonical error codes are occurring, as a rate | "No `capability-unavailable` rate means the serving capability was available." That rate read 0 through the outage |
| `model-load-duration-p95` | Nothing. It is not emitted | Any conclusion about model load time |
| `api-processes-publishing-identity` | How many API processes the collector has read | "2 means two replicas." It read 2 with one replica configured, while a deleted pod's series were still returned |
| `restarts-and-pod-phase` | Nothing. It is not answerable | "No restarts." Restarts are visible only indirectly, as a new instance in the identity table |
| `api-process-cpu-by-replica` | Each API process's CPU use | "Two lines means two replicas." A replaced pod keeps its line for the rate window |
| `api-process-memory` | Nothing. It is not emitted | Any conclusion about memory |
| `container-and-pod-resource-use` | Nothing. It is not answerable | Any conclusion about the serving runtime's CPU or memory |
| `scrape-targets-discovered-by-tier` | How many pods the collector discovered per tier | "This is the replica count." It is discovered pods with a metrics port, not desired or ready replicas |
| `build-identity-per-replica` | Which build, model revision, runtime and image each API process runs | "The table is every replica." Columns are truncated at narrow widths. Scroll the table |
| `runtime-operating-identity` | Which environment, workload, model and runtime the runtime tier reports | "Missing means the model is wrong." It is missing whenever the runtime job discovered no pod |
| `cluster-provider` | Nothing. It is not answerable | Which provider this release runs on. Read the run's evidence record |
| `tokens-per-second-at-the-api` | Input and output token rates as the API counts them | "Tokens are flowing, so the API is up." The rate outlived the API pod |
| `tokens-per-second-at-the-runtime` | Token rates as llama-server counts them | "Runtime input is far below API input, so tokens are lost." Runtime input excludes prompt-cached tokens: counter totals of 247 against the API's 4140, with 3893 on llama-server's cached-prompt counter, while output matched at 690. The gap depends on prompt reuse, and that run reused one prompt |

## What this dashboard cannot tell you at all

- **Whether the model is ready.** No panel reads a number about it.
- **That anything restarted.** Only indirectly, as a new instance and since-start
  counts dropping to 0.
- **Which provider it is on**, and whether a second release shares the data source.
  Totals would add the two together.
- **Anything about capacity.** Every figure in the validation run is one
  observation of one release.

## What each screenshot shows

Each was taken shortly after its state's capture, so a figure on it can differ from
the committed reading.

| State | Screenshot |
|---|---|
| Idle, every workload ready | [01-idle.png](../proof/telemetry/v1-s4-002-pr2-screenshots/01-idle.png) |
| Traffic finished and recorded | [02-traffic.png](../proof/telemetry/v1-s4-002-pr2-screenshots/02-traffic.png) |
| Twenty requests naming the wrong model | [03-error.png](../proof/telemetry/v1-s4-002-pr2-screenshots/03-error.png) |
| Serving runtime scaled to zero | [04-serving-runtime-scaled-to-zero.png](../proof/telemetry/v1-s4-002-pr2-screenshots/04-serving-runtime-scaled-to-zero.png) |
| API pod replaced, settled | [05-api-pod-replaced.png](../proof/telemetry/v1-s4-002-pr2-screenshots/05-api-pod-replaced.png) |
| API scaled to zero | [06-api-scaled-to-zero.png](../proof/telemetry/v1-s4-002-pr2-screenshots/06-api-scaled-to-zero.png) |
