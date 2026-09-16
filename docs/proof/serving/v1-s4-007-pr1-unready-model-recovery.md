# V1-S4-007-PR1 — a model that did not become ready, on `docker-desktop`

Date captured: 2026-09-16

Classification: **local real evidence**, redacted. Evidence class `local-real-cpu`,
certification ceiling `C2`. A release was installed on a real Kubernetes cluster with
the serving runtime container given one hundredth of a processor, so `llama-server`
started, bound its port, began loading the model and did not finish; it was held there
for 179 755 ms while four request surfaces were asked and readiness was sampled from
four places; and it was got back by dropping one values overlay and upgrading.
**Nothing here is mock, synthetic, or estimated.**

Produced by:

```text
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/unready-model-recovery.sh run \
  --values charts/inferops-llm/ci/real-values.yaml \
  --values <host model seed overlay> \
  --values <host API image overlay> \
  --confirm-real-kubernetes
```

The machine-readable result is
[`v1-s4-007-pr1-unready-model-record.v1alpha1.json`](v1-s4-007-pr1-unready-model-record.v1alpha1.json).
It regenerates exactly from the six committed inputs beside it —
[environment](v1-s4-007-pr1-environment.v1alpha1.json),
[lifecycle](v1-s4-007-pr1-lifecycle.v1alpha1.json),
[readiness](v1-s4-007-pr1-readiness.v1alpha1.json),
[probes](v1-s4-007-pr1-probes.v1alpha1.jsonl),
[diagnostics](v1-s4-007-pr1-diagnostics.v1alpha1.json), and
[telemetry](v1-s4-007-pr1-telemetry.v1alpha1.json):

```sh
python -m tools.unready_model_recovery verify \
  --dir docs/proof/serving --prefix v1-s4-007-pr1-
```

**What this record may not be read as.** Not an availability figure, not a
service-level objective, not an error budget, not a recovery-time objective, and not a
benchmark of Kubernetes, the model, the runtime, or any provider. It is one release,
misconfigured once, on one host, under
[`ADR 0013`](../../architecture/decisions/ADR-0013-bounded-local-performance-observations.md).
The record carries `productionBenchmark`, `portableCapacityClaim`, and
`availabilityClaim` all `false`.

## The gap this closes

[`ADR 0010` D8](../../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
publishes nine rows of error mapping and marks exactly one **observed**:
*the runtime reports not-ready while the model loads* → `model-not-ready`. It was
observed once, incidentally, in a control-plane line during the Sprint 0 feasibility
trial. The mock adapter reproduces the shape as `MockScenario.MODEL_NOT_READY`, and
[the mock and real boundary](../../serving/mock-and-real-boundary.md) states as its rule
that a mock serving path may never be used to certify real local runtime behaviour. So
the only observed row of the accepted mapping rested on an accident and a fixture. This
arranges it deliberately, on a real cluster, and finds that **the row is right about the
runtime and wrong about what a caller meets**.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `0c784d8b3fd939fec1ce0e47f846368e28b08f02`, with this change's own tracked and untracked files present |
| Experiment descriptor, as this record was derived | `sha256:8586ce0861ff1639e0f97283c8e7ae277d82a06710c2c2075fa1153e572c71d2` |
| Experiment descriptor, as the run executed it | `sha256:7220395254fe7da172d438df1252a59b66a376685937c94d5b7834276c4fdb59` |
| Record tool, as the run executed it | `sha256:2ffe2418f99a1e2c0ea53efd50d659717cc04aeaa01fc227814daceeb17f2493` |
| Values overlay | `sha256:4ed92f844f2158dae6b4fbef5e0c7a084c8932009730280b1434534d8ffcbfb5` |
| Provider | `docker-desktop`, verified at `2026-09-16T16:12:19Z` |
| Kubernetes | server `v1.34.3`, client `v1.34.3` |
| Helm | `v3.19.0+g3d8990f` |
| Node | `desktop-control-plane`, `sha256:08497ee19eace7b4b5…`, Debian GNU/Linux 12 (bookworm), kernel `5.15.146.1-microsoft-standard-WSL2` |
| Container engine | `29.7.2`, 12 processors, 10 432 536 576 bytes |
| Chart | `inferops-llm-0.3.0`, release `inferops` in `inferops-release`, revision 1 then 2 |
| Platform API image | `localhost/inferops-api@sha256:9687e1bb11bd2b728bd61fd1338718a6816efa65958b9366cdf536fe8fdfc087` |
| Serving runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model | `qwen3-1-7b-q8-0` at revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, context 4 096, 6 threads |
| Collector | Prometheus `3.5.0` |
| Serving runtime processor, misconfigured | request `10m`, limit `10m` |
| Serving runtime processor, corrected | request `1`, limit `6` |
| Other workloads | 12 running pods outside the release, across 3 other namespaces, uncontrolled |

**This record was rebuilt after the run, and the two descriptor digests above are how a
reader can tell.** Independent review found defects in what the tool derived and in what
this document said; the fixes changed the derivation, so the record was regenerated from
**the same six committed inputs**, which are untouched. No measurement was re-taken and
none could be — the release is gone. The record carries the comparison itself under
`derivation`, and `environment.repository.executedFiles` carries it for every other file
that decided what the run did.

## Environment

One single-replica release of each of the three tiers on one Docker Desktop node, on
CPU, on a Windows host, with twelve other pods running in three other namespaces that
this run neither controlled nor named. The model artifact was already in the cache
claim, and the host's file cache was in whatever state the preceding runs left it —
which matters here more than usual, because the thing being starved is a load whose
cost depends on it.

## Method

**Question.** What does a caller see, what does an operator see, does the platform
destroy itself while it waits, and does correcting one value get the release back —
when the runtime process is healthy and the model behind it is not ready?

**Procedure.** One committed values overlay,
[`unready-model-values.v1.yaml`](../../../deploy/serving/experiments/unready-model-values.v1.yaml),
sets the serving runtime container's processor request and limit to `10m` and nothing
else. It is appended by the operating script rather than passed by the operator, so the
file whose digest this record pins is the file that was installed. The release is
installed with it, held for the registered window, probed, captured, upgraded without
it, and probed again.

**Pre-registered expectations.** Every one was written into the descriptor before the
run.

| Surface | Expected while unready | Expected after the fix | Observed |
|---|---|---|---|
| `runtime-health` — `GET /health` on the runtime pod | `503` | `200` | as registered |
| `api-liveness` — `GET /health/live` on the API pod | `200` | `200` | as registered |
| `api-readiness` — `GET /health/ready` on the API pod | `503` | `200` | as registered |
| `api-completion` — `POST /v1/chat/completions` on the API pod | `503` | `200` | as registered, and see below for *which* `503` |

**Which canonical code was not pre-decided.** The descriptor registers a vocabulary of
eight canonical codes and requires both of the two `ADR 0010` D8 maps this situation to
— `model-not-ready` and `capability-unavailable` — to be in it, because which one
arrives is the result and not the arrangement.

**Where each interval begins and ends.** The unready window begins once the runtime has
answered on its own port and the idle baseline is over. The recovery is stamped from the
moment the corrected upgrade was issued to the completion of the first request that came
back **served with output tokens** — not from a rollout returning, not from a forward
accepting a connection, and not from a `200` with nothing in it.

## Results

> Every figure below is **measured** — read from the probe record set, the cluster's
> answers, and the operating script's own stamps — except the intervals, which are
> **derived** by subtraction on the host's own clock.

### The release installed, and the artifact was never in question

| | value |
|---|---|
| Chart validation | accepted the overlay; revision 1 installed |
| `verify-model` exit code, misconfigured pod | `0` |
| `verify-model` exit code, corrected pod | `0` |
| Release revision | `1` before the fix, `2` after |

The byte count and SHA-256 check passed in both pods. That is what separates this from
[`V1-S3-008`](../environment/v1-s3-011-pr2-upgrade-rollback.md), whose artifact mismatch
is refused by this same init container **before** the runtime container is ever started.

### Readiness, from four places that all agreed

Twenty-one samples across the unready window, every 5 000 ms, widest gap 18 702 ms.

| Place | While unready | After the fix |
|---|---|---|
| Serving runtime pod `Ready` | `0` ready, in all 21 samples | `1` ready, in all 8 |
| Serving runtime Service ready endpoints | `0`, in all 21 samples | `1`, in all 8 |
| Platform API pod `Ready` | `0` ready, in all 21 samples | `1` ready |
| Platform API Service ready endpoints | `0`, in all 21 samples | `1` |
| Serving runtime container `restartCount` | `0`, in all 21 samples | `0` |
| Platform API container `restartCount` | `0`, in all 21 samples | `0` |

**Both Services dropped their only address.** The runtime's readiness probe is an HTTP
GET against the endpoint that answers `503` for the whole of a load, and the API's
readiness path is the conjunction of the API accepting work and its adapter reporting
itself able — so a release whose model is not ready has no ready endpoint anywhere. That
is why both forwards in this experiment address pods.

**Liveness did not restart a healthy process.** The runtime was answering on its own
port no later than 20 272 ms after its container was reported running — a ceiling, for
the reason given under the timings below — and went on answering for the whole window;
the restart count was `0` at every sample. That is what a TCP-connect liveness probe
asks, and it is the asymmetry the chart exists to get right. What the argument needs is
that the socket *was* answering throughout, which every probe round establishes
directly; when it opened is not measured here.

**It is bounded, and the bound is the kubelet's.** The window was held for 179 755 ms,
which is **30.0%** of the runtime's own `runtime.probes.startup.budgetMs` of 600 000 ms.
Past that budget the kubelet kills the container and restarts it into the same load, so
this figure says the process was not killed inside that budget and says nothing about
what happens after it.

### What a caller was told

Eight probe rounds while unready, three after the fix.

| Surface | While unready | After the fix |
|---|---|---|
| `runtime-health` | `503` × 8, detail `Loading model`, type `unavailable_error`, 75 body bytes | `200` × 3, detail `ok`, 15 body bytes |
| `api-liveness` | `200` × 8 | `200` × 3 |
| `api-readiness` | `503` × 8, body `not-ready, adapterKind=real, state=serving` | `200` × 3 |
| `api-completion` | `503` × 8, **`capability-unavailable`**, condition **`runtime-unreachable`**, `retryable: true` | `200` × 3, 3 output tokens each |

The record keeps a classification of each body and never the body itself, so the
figures above are what was stored: the status, the canonical code where there was one,
the condition, the retryable flag, the byte count, and a digest. `llama-server`'s 503
body is
`{"error":{"message":"Loading model","type":"unavailable_error","code":503}}`, which is
75 bytes and matches the byte count every one of these eight probes recorded; it is
quoted here from the runtime's published envelope rather than reconstructed from the
record, and the byte count is what ties the two together.

**The headline finding, and it is not the one `ADR 0010` D8 would have been read as
predicting.** The runtime's own answer *is* the row D8 marks observed: `503`, `Loading
model`, which is exactly the status
[`readiness.py`](../../../src/inferops/adapters/llama_cpp/readiness.py) maps to
`ReadinessState.LOADING`. But **no caller ever received `model-not-ready`.** All eight
completions came back `capability-unavailable` with condition `runtime-unreachable`,
because the runtime pod's readiness probe had already removed its only address from the
runtime Service before the adapter could observe that `503` at all. The readiness gate
answers the question before the adapter does.

So `model-not-ready` is reachable from a runtime the adapter can still talk to — a
sidecar, a direct endpoint, a runtime whose readiness has not yet gone false — and not
from this chart's topology. Both rows of D8 are correct; which one a Service-fronted
release reaches is decided by the probe, and that was written down nowhere before this
run. ADR 0010 gains a dated note recording it.

`V1-S4-006` recorded forty requests answered `503 capability-unavailable` when the pod
was **deleted**. This run produces the same code for a pod that is present, healthy, and
loading — which is the honest cost of the vocabulary having no member meaning
*unavailable*, as the accepted record itself says.

### Timing — one release, misconfigured once, on one host

| | ms | |
|---|---:|---|
| Install to the runtime container running | 21 631 | measured |
| Container running to the socket answering | ≤ 20 272 | **ceiling** — see below |
| Unready window held | 179 755 | measured |
| Upgrade to the runtime reporting Ready | 20 880 | measured |
| Upgrade to the API reporting Ready | 27 797 | measured |
| Upgrade to the recovered window opening | 32 023 | measured, and contains the forward re-open |
| Recovered window opening to a served completion | 4 664 | measured |
| Upgrade to a served completion | 36 687 | **ceiling** — the sum of the two above |

**Two of these bound rather than measure, and both now say so in their names.**

*Container running to the socket answering* is stamped at one end when the container is
reported running and at the other when the **first forward this workflow opens** gets an
answer. Between the two the script waits for the API container, waits for the
collector's rollout, runs five pod queries and seven cluster dumps, reads the Helm and
engine versions, runs the repository subprocess, waits for the local port to be free,
opens the API forward, and then polls at three-second granularity. `llama-server` may
have been listening for most of that. What 20 272 ms establishes is that **by** then the
socket was answering — which is all the liveness argument needs — and not that the
socket took that long to open. Nothing here measures when it opened. The descriptor now
pre-registers this as `observation.socketAnswerMeasuredFrom`, because nothing did before
and that is why the earlier version of this table read it as a runtime property.

*Upgrade to a served completion* contains the rollout, the replaced pod being looked up,
the old forward being killed, its port being waited for, a new forward being opened,
three pod queries, and the probe round's own schedule. 32 023 ms of the 36 687 ms is
everything up to the first probe round being possible; 4 664 ms is the round itself.

**They are not a benchmark, and they are not comparable to anything.** The corrected
model reported Ready 20 880 ms after the upgrade, which is fast for this model, and the
likely reason is that this run had just spent three minutes reading the same file — the
host's page cache was warm, and it is not controlled. That is a stated limitation and
not a measurement: nothing here establishes a cold/warm difference, and this record
deliberately does **not** compare the figure to `V1-S2-007`'s model-load timings, which
[that record forbids being cited](v1-s2-007-pr1-cold-warm-start.md#limitations) by any
claim about model-load cost, were taken on a different host, and were concluded there to
establish no cold/warm difference at all. An earlier version of this section made
exactly that comparison and quoted a warm-arm figure inside a range labelled cold;
independent review caught it.

### What the diagnostics said

The **published** column is what a reader of this record sees. The **captured** column
is the whole capture, which is written into the run directory and is not published. An
earlier version of this table printed the second under the heading of the first and
overstated `runtime-describe`'s published content about thirteenfold; independent review
caught it, and the record now carries both numbers so the table cannot be written that
way again.

| Capture | Registered as naming the cause | Captured lines | Published lines | Withheld | What it showed |
|---|---|---:|---:|---:|---|
| `runtime-resources` | **yes** | 1 | 1 | 0 | `runtime requests={"cpu":"10m","memory":"2Gi"} limits={"cpu":"10m","memory":"3Gi"}` — the misconfiguration itself, read from the Deployment rather than from the values file |
| `runtime-log` | **yes** | 10 | **1** | **9** | the one line that survived is a `LLAMA_ARG_HOST` warning; see below |
| `runtime-describe` | probable | 147 | 11 | 1 | the last twelve lines are the events, including the init container succeeding |
| `api-readiness-body` | partial | 1 | 1 | 0 | `{"status":"not-ready","adapterKind":"real","state":"serving"}` — a not-ready adapter, not a draining API |
| `api-log` | partial | 56 | 12 | 0 | `readiness.failed` at `warn`, naming the component and not the cause |

The excerpt ceiling is twelve lines, registered in the descriptor, so a capture longer
than that contributes its last twelve and no more. `Captured + published` do not add up
to each other for that reason; `published + withheld` equals the number of lines
considered, and the record carries a check that says so.

**An operator holding these could name the cause**, from `runtime-resources` alone: a
serving runtime given `10m` of processor, and a log that stops at *loading model*.

**Two things had to be withheld to publish them, and both are recorded rather than
worked around.** A committed record in this repository may not carry a host path, a
user directory, or an address, and the excerpt of each capture therefore keeps only the
lines that carry none of the three and **counts the rest**:

- `kubectl describe pod` prints the pod's address. One line withheld.
- **`llama-server`'s own log timestamps are indistinguishable from addresses.** It
  prefixes every line with `0.00.077.768`, which is four dotted numbers of at most three
  digits each — exactly the shape the privacy check refuses. Nine of its ten lines went,
  including the `load_model: loading model` line that is the diagnostic. The capture is
  written whole into the run directory, which version control ignores; only the excerpt
  is reduced. This is a real limitation of publishing this runtime's log and it is
  [left as follow-up work](#follow-up-this-run-earned).

### What telemetry did and did not expose

| Signal | Registered as | Answered | While unready → after the fix | Exposed it? |
|---|---|---|---|---|
| `up{job="…-serving-runtime"}` | expected to expose | yes, 2 series | the misconfigured pod's series reads `0` in both phases; the replacement's is absent while unready and reads `1` after | **yes, through the pair** |
| `inferops:scrape_targets_up:sum / inferops:scrape_targets:count` | expected to expose | yes, 2 series | serving-runtime `0` → `1`; platform-api `1` → `1` | **yes** |
| `sum by (workload, code) (inferops_inference_errors_total)` | expected to expose | yes, 1 series | `capability-unavailable` `7` → `8` | **yes** |
| `sum by (workload, component) (inferops_readiness_check_failures_total)` | expected to expose | yes, 1 series | `serving-adapter` `34` → `41` | **yes** |
| `sum by (outcome) (inferops_inference_requests_total)` | expected to expose | yes, 2 series | `server-error` `7` → `8`; `success` absent → `3` | **yes** |
| `inferops:inference_requests_in_flight:runtime` | expected **not** to expose | yes, 1 series | absent → `0` | no — an absence that says the scrape failed, not that nothing was in flight |
| `count by (component) (inferops_build_info)` | expected **not** to expose | yes, 1 series | `1` → `1` | no — the API publishes its identity whether or not its adapter can serve |
| `inferops:model_ready_absent:platform_api` | expected **not** to expose | yes, 1 series | `1` → `1` | **no — it reads `1` in both phases and cannot tell a loading model from a loaded one** |
| `inferops_model_ready` | nothing emits | yes, **0 series** | nothing, as registered | **no — nothing emits it** |
| `kube_pod_container_status_restarts_total` | no source | yes, **0 series** | nothing, as registered | **no — no source** |

No single `up` series transitions from `0` to `1` — there is one series per pod, and
the upgrade replaces the pod. What transitions is the per-job ratio in the row below it,
which is the aggregate a reader would actually look at. An earlier version of this
record and its changelog entry said "`0` then `1`" of `up` itself, which is
substantively right and literally wrong.

**Scrape health exposed this one, and that is a reversal worth stating.**
[`V1-S3-011-PR2`](../telemetry/v1-s3-011-pr2-telemetry-during-recovery.md) and
[`V1-S4-006`](v1-s4-006-pr1-inference-pod-recovery.md) both recorded `up` as
uninformative about readiness, because a terminating pod goes on answering scrapes. This
failure mode is the opposite: the process is up and refusing, `/metrics` answers with
the same `503` as everything else, and the scrape fails. The difference is not that one
record was wrong — it is that `up` reports whether a target answered, which coincides
with readiness here and did not there.

**The one metric declared for this exact question is the one that could not answer it.**
The telemetry catalog declares `inferops_model_ready` with the question *is the model
behind this workload servable right now?*, assigns it to the serving-runtime adapter, and
marks it not emitted because that adapter is not instrumented. It returned no series in
either phase. The recorded rule that publishes its absence returned `1` in both phases,
which is correct and useless. **Nothing in this platform's telemetry says the model was
not ready**; what said so was an error code on a request counter and a readiness-check
counter, both emitted by the API.

Every reading above is published with the instant the point it came from carries, in
`readingWhileUnreadyAsOf` and `readingAfterRecoveryAsOf`, and any label set whose
unready reading predates the unready window is listed in
`labelSetsWhoseUnreadyReadingPredatesTheWindow`. The captured range starts at the idle
baseline and is widened by a scrape interval, so without those a stale point would have
been published under a window's name with nothing to say it was stale. For this run that
list is empty in every row.

The record states each expression's registered expectation and its readings either side;
it does not decide whether a signal exposed the state. This section does, and it is a
reviewed statement rather than a computed one.

### Required human action

One, registered in advance, and the opposite of `V1-S4-006`'s. A deleted pod is replaced
by the Deployment controller and nobody has to act; a model that cannot load is not a
state any controller reverses. The recorded intervention is
`corrected-the-values-and-upgraded`, and the operating script issues exactly two
mutating commands after the install — that upgrade and the uninstall that ends the run —
which a test establishes by reading the script.

### Commands that failed, and their output

```text
The workflow was executed nine times. Eight were discarded and none of their evidence
was promoted; the ninth is this record. The distinct causes are listed below because a
failure that is omitted is the one the next person repeats. Two of the nine were
self-inflicted -- the script was edited while bash was executing it, and bash reads a
script by file offset -- and the rest were defects the workflow only had because it had
never been run.

1. curl: (23) Failure writing output to destination, passed 335 returned 4294967295
   Sixteen probes with an empty body and no canonical code. curl on this host is a
   native binary and the POSIX path it was given was not one it could open. Every
   other file this script hands to a native program already went through
   inferops::native_path; this one did not.

2. HTTP 400 on every completion, with no canonical code.
   The request carried "max_tokens" and "temperature", both of which are outside the
   frozen request subset src/inferops/api/validation.py accepts, so it was refused
   contract-invalid before readiness was ever consulted. That is a fact about the
   request and not about the model.

3. scripts/environment/unready-model-recovery.sh: line 885: phase: unbound variable
   Self-inflicted: the script was edited while bash was executing it, and bash reads a
   script by file offset. A later run showed the same cause as seven probe rounds
   recorded twice.

4. FAILED: expected exactly one 'serving-runtime' pod and found 2.
   A rolling update keeps the predecessor until the replacement is ready. The workflow
   now waits for exactly one pod that is not terminating.

5. FAILED: 'install.issuedEpochMs' must be an integer of at least 1789570695542
   The lifecycle reader had the idle baseline before the install, and the run takes
   the baseline after it.

6. the-runtime-reported-ready-to-a-caller-after-the-fix, on a complete run.
   Two findings in one. The first: waiting for *any* ready serving runtime pod stamped
   the recovery from the misconfigured one, whose starved load had finished, and let it
   serve the completions that were supposed to establish the fix. The second:
   `Unable to listen on port 18097: ... bind: Only one usage of each socket address`.
   Closing a forward kills a subshell and leaves kubectl holding the socket, so the new
   forward refused to bind and the probes were answered by the old one, still pointed at
   the replaced pod.

7. REFUSED unready model recovery: the diagnostics record carries a value shaped like a
   host path, a user directory, or a network address ('<the pod's address, withheld>')
   The record's own privacy check, refusing `kubectl describe pod` output. Correct, and
   the reason the excerpts are now filtered and counted. The address the refusal named
   is withheld here for the same reason it was refused there.
```

## What an earlier execution established that this one does not

An earlier execution held the release unready for 307 673 ms and then watched the
starved load **finish**. The window is registered at 180 s against that measurement. So
this record does **not** claim the model would never have loaded: it claims the model
had not loaded, that the process was healthy while it had not, and that correcting one
value got it back. The window is registered at 180 s against that measurement, which is
roughly 1.7 times it. `10m` is the smallest quota a container runtime will enforce — one
millisecond in a hundred — so a smaller number in a values file would have bought
nothing.

## Follow-up this run earned

1. **`llama-server`'s log cannot be excerpted into a committed record.** Its timestamps
   match this repository's address shape. Either the privacy check learns that a dotted
   quad whose first component is a lone `0` and whose parts are zero-padded is a
   duration, or the runtime capture is reduced to a structured query. Nine of ten lines
   were withheld here; nobody has decided which fix is right.
2. **A large integer in a values file renders in scientific notation.** Found while
   choosing the disruption: `runtime.contextSizeTokens: 1048576` — the schema's own
   maximum — renders as `"1.048576e+06"`, which the API refuses at start-up
   (`INFEROPS_LLAMA_SERVER_CONTEXT_SIZE: must be a whole number written in decimal`) and
   which `llama-server` reads as a context of `1` and aborts on. The same value through
   `--set` renders correctly. Every integer the schema permits above roughly a million
   is affected, and no test covers it. Not fixed here: it is a chart defect and this is a
   test PR.
3. **Nothing emits `inferops_model_ready`.** This run is the strongest case yet for
   instrumenting the adapter, and it is still the adapter's to emit.

## Limitations

- One provider, one host, one single-replica release, one model, one runtime build, one chart, and one misconfiguration applied once. Nothing here is portable to another provider, host, replica count, model, or runtime configuration, and nothing here is an availability figure, a service-level objective, an error budget, or a recovery-time objective.
- The model did not become ready within the registered observation window, and that is not the same as proving it never would. The load was starved rather than failed.
- The disruption is a processor limit and not a corrupt artifact, a wrong revision, or an unloadable file. Those are refused earlier, by chart validation or by the `verify-model` init container.
- Both request surfaces are reached through a loopback forward to a pod rather than to a Service, because a release whose model is not ready has no ready endpoint on either Service. A caller arriving through the API Service in this state would have met no endpoint at all, which is stated rather than measured here.
- The recovery is an operator changing a value and issuing an upgrade. Nothing here says a controller would have reversed it, and nothing here measures how long a person takes to notice.
- The collector scrapes every 30 seconds, so a telemetry series locates a transition to within a scrape and a rule evaluation, never to the request. No figure published here is derived from a telemetry series.
- One round of probes is sent every registered interval, not a load profile. `V1-S4-006` owns the under-load question and this one deliberately does not repeat it.
- Other workloads on the same node and virtual machine are not controlled, and the host's file cache is in whatever state the preceding run left it.

## Authorisation

Required: **yes** — the run installs a release, loads a real model, sends real requests,
upgrades the release, and removes it. It was authorised by the `--confirm-real-kubernetes`
flag and the two host values files, all supplied before the run.

Granted by: the operator of this host.

Cleanup verified: **yes** — the release was uninstalled, no object carrying the release's
instance label survived, and the claim count was 1 before and 1 after. The namespace and
the model cache claim were left in place, as they are Terraform's.

Sensitive values removed before committing: **yes** — every one of the six inputs is
refused by the record tool if it carries a host path, a user directory, or an address
that is not loopback, and ten excerpt lines were withheld from the diagnostics on those
grounds and counted in the record.
