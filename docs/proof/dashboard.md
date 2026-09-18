# The V1 proof dashboard

Status: **generated page**. It is produced by
`python -m tools.proof_dashboard` from
[the claim and evidence register](../testing/claim-evidence-matrix.v1alpha1.json),
and [`tests/testing/test_proof_dashboard.py`](../../tests/testing/test_proof_dashboard.py)
regenerates it and fails if the committed page and the register disagree.
**Do not edit it by hand.** An edit here would be the only place in this
repository where a capability status was asserted instead of derived, and it
would survive exactly until the next check.

This page answers one question: **what has this project actually proven?**
It is not a monitoring view. What is happening inside a running release is
[the inference operations dashboard](../telemetry/inference-operations-dashboard.md),
which is asked of a Prometheus and shows nothing when nothing is running. This
page reads committed files, says the same thing on every machine, and does not
change when a cluster does.

**Certified: 41 of 58 claims.** The remaining 17 are the rows worth
reading, and they are listed in full under [what V1 does not
claim](#what-v1-does-not-claim) rather than summarised away. Every number on
this page is counted from the register at render time; there is no field
anywhere in this tool that a count could be typed into.

## Where V1 stands

Four states, and the difference between the last three is the difference
between a promise, a decision, and a measured absence.

| Status | Claims | May be published as a capability | What it means |
|---|---|---|---|
| `certified` | 41 | yes | An executed record under docs/proof/ supports the statement at the level named, inside the boundary its limitation states. |
| `planned` | 8 | no | V1 intends it and nothing has proven it. It may be published only as an intention, and it may cite no evidence record. |
| `deferred` | 1 | no | Out of V1 scope by an accepted decision. It may not be published as a capability at all, and it may cite no evidence record. |
| `not-claimed` | 8 | no | A reader would reasonably expect it and V1 states that it does not have it. It may cite the record that measured the absence, because an absence somebody measured is worth more than one nobody mentions. |

### The levels the certified claims reached

A level says how strong a proof is, and it is not the same question as
whether the claim may be published. The meanings are in
[the certification document](../testing/certification.md).

| Certification level | Certified claims |
|---|---|
| `C0` | 21 |
| `C1` | 3 |
| `C2` | 17 |

### What the evidence behind them is

The label decides the ceiling. A claim cannot be certified above what its
evidence class can support, and 5 of the 6 classes in use
below can support no statement about real runtime behaviour at all.

| Evidence label | Claims | Ceiling | May support real runtime behaviour | What it is |
|---|---|---|---|---|
| `documented-unexecuted` | 13 | `none` | no | A statement in a document. Nothing ran. |
| `local-static` | 21 | `C0` | no | A deterministic check over files in this repository. No network, no cluster, no model, no clock, no randomness. |
| `mock` | 3 | `C1` | no | A labelled mock provider that loads no model. |
| `estimated` | 1 | `none` | no | A calculation rather than a measurement. |
| `local-real-cpu` | 19 | `C2` | yes | The real component, on a contributor's own machine, on CPU, with versions and commands recorded. |
| `production-experience` | 1 | `none` | no | Operating the thing in an organization's production. Part of the published evidence vocabulary and unreachable from this repository. |

### Which provider the real results came from

Only the claims that name a provider are counted here. The rest named none
because no provider produced them, and folding those in would make the
reference provider look like a minority of the evidence rather than all of
it.

| Provider | Claims naming it |
|---|---|
| `docker-desktop` | 14 |
| `kind` | 1 |

A result on one provider certifies that provider. It does not certify
another provider, a cloud cluster, a GPU, another host, another model,
another runtime, or production, and no row on this page may be read as
though it did. The providers themselves are published in
[the local cluster provider contract](../environment/local-cluster-provider-contract.md).

## The capabilities

Each group is a question a reviewer asks, and the rows under it are the
register's answer with the four things a summary usually loses kept beside
each one: the level, the evidence class, the provider and environment, and
the limitation that travels with the claim. A group's tally is counted from
its own rows, and a group is never given a single colour, because a group
holding one certified row and one measured absence is not one status.

### Real serving

*Has a real model ever answered a request through this API?*

**Tally:** 4 `certified`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| The pinned runtime loads the hash-verified model and the InferOps API returns a real completion from it, on a contributor's own machine, certified at `C2` by one authorized run. | `certified` | `C2` | `local-real-cpu` | `capable-host`, no provider | [`serving/v1-s2-004-c2-certification-result.md`](serving/v1-s2-004-c2-certification-result.md), [`serving/v1-s1-real-runtime-closure.md`](serving/v1-s1-real-runtime-closure.md) | One host, one run, one day on 2026-09-04, CPU only, loopback composition rather than Kubernetes, one fixed request. Runtime readiness was 285,828 ms against a pinned 300,000 ms budget — under five per cent of headroom — and the record says the budget is not comfortable. The request and correlation identifiers were not echoed back. |
| A Helm release installed into the operator's Kubernetes cluster loads the pinned model from a Terraform-owned claim and serves a real completion through the release's own Service. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md), [`serving/v1-s0-003-pr2-runtime-feasibility.md`](serving/v1-s0-003-pr2-runtime-feasibility.md) | One provider, `docker-desktop`; one Windows host; one Docker Desktop installation; CPU; one replica of each tier; one moment on 2026-09-12. Docker Desktop chooses its own Kubernetes version and node image and InferOps pins neither. Three inference requests were sent and their timings were deliberately not recorded. |
| The InferOps inference API implements five ASGI routes and selects the mock or the real serving adapter explicitly, never by falling back. | `certified` | `C1` | `mock` | `repository-only`, no provider | [`serving/v1-s1-005-pr1-validation.md`](serving/v1-s1-005-pr1-validation.md), [`serving/v1-s1-005-pr2-validation.md`](serving/v1-s1-005-pr2-validation.md) | The published surface is five endpoints served in part. The distribution carries no server dependency; the repository's loopback-only HTTP carrier is tooling rather than a product. |
| A mock, a simulation, or an estimate certifies at most `C1` however faithful it is, and the ceiling is enforced in the strategy data rather than asked for in review. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`testing/v1-s0-006-pr1-validation.md`](testing/v1-s0-006-pr1-validation.md) | The ceiling is enforced over the committed strategy data. It stops a layer certifying above its class; it cannot tell an honestly planned layer from one nobody will write. |

### Kubernetes deployment

*Does a release install, serve, and leave without residue?*

**Tally:** 4 `certified`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| InferOps requires an explicitly selected, already existing local cluster, positively verifies the target before it mutates anything, and creates, resets, reconfigures, or deletes no cluster. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md), [`architecture/v1-s3-010-pr1-validation.md`](architecture/v1-s3-010-pr1-validation.md) | `docker-desktop` is the executed V1 reference provider, verified by binding the node container's published API-server port to the port the verified kubeconfig dials. `kind` is supported by a guard and is certified by none of this evidence. Two things the Docker Desktop identity check cannot refuse are accepted as `EX-06`. |
| `helm uninstall` removes every object the release owns and leaves the operator's cluster, its node, its storage class, and the Terraform-owned prerequisites intact. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`environment/v1-s3-011-pr2-scoped-cleanup.md`](environment/v1-s3-011-pr2-scoped-cleanup.md) | One provider, one host, one teardown on 2026-09-12. Survival was checked immediately afterwards and nothing is known about days later. `terraform destroy` reclaims the model weights, so the next real run re-acquires them. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed record. |
| The optional `kind` helper creates a local development cluster, runs a workload inside it, and removes it leaving no residue the verifier can find. | `certified` | `C2` | `local-real-cpu` | `kind`, `local-kubernetes` | [`environment/v1-s0-002-pr2-cluster-smoke.md`](environment/v1-s0-002-pr2-cluster-smoke.md) | One Windows host on WSL 2, one architecture, one point in time on 2026-08-23, on cgroup v1, with a static-text HTTP server as the workload. Since ADR 0011 this helper is optional and InferOps no longer creates a cluster for its own workflows. About 0.1 GB of host free space was not returned, and the node image is retained by design. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed record. |
| A symptom-oriented Kubernetes troubleshooting guide covering cluster, scheduling, memory, storage, model load, probe, Service, telemetry, Helm, and Terraform faults, with four separated cleanup radii, is published and machine-checked against the repository. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`environment/v1-s3-009-pr1-validation.md`](environment/v1-s3-009-pr1-validation.md), [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md), [`environment/v1-s3-011-pr2-scoped-cleanup.md`](environment/v1-s3-011-pr2-scoped-cleanup.md) | Every command is checked against the repository, which is a property of strings rather than of a cluster. The record that machine-checks the guide contacted no cluster, and states that when it was written the release half had never been run by anybody; `V1-S3-011` ran that half afterwards, on one Windows host, on `docker-desktop`, and those two records are cited beside it. |

### Model integrity

*Is the artifact that gets loaded the artifact that was published?*

**Tally:** 4 `certified`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| The model artifact this project uses is acquired revision-pinned and resumable, and its bytes are compared against the published SHA-256 before anything loads it. | `certified` | `C2` | `local-real-cpu` | `capable-host`, no provider | [`serving/v1-s0-003-pr2-runtime-feasibility.md`](serving/v1-s0-003-pr2-runtime-feasibility.md), [`serving/v1-s1-real-runtime-closure.md`](serving/v1-s1-real-runtime-closure.md) | The downloader does not validate TLS certificates, so the published hash is the whole integrity argument for the transfer rather than a redundant check on it. Resumption after interruption is proved synthetically; the executed acquisition took 866 seconds over three bounded resume attempts on one host. Both records cited also ran in a cluster, and this row carries no provider because the comparison it is about happens in the download procedure on the host rather than inside one. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed record. |
| A deleted serving pod is replaced against the surviving Terraform-owned claim, with the artifact's byte count, SHA-256, inode, and mtime unchanged and no re-acquisition Job created. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`serving/v1-s3-003-pr2-kubernetes-pod-restart.md`](serving/v1-s3-003-pr2-kubernetes-pod-restart.md) | One provider, one host, one pod deleted once on 2026-09-12, with one replica. Four defects were found: two by running it, and two more by an independent review of the change afterwards, both of the second pair defects in a published figure rather than in a run that failed, which is why running it did not find them. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed record. |
| One serving runtime and one model revision were selected by a published feasibility procedure executed once against twelve pre-registered thresholds, eleven met and one recorded as failed. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`serving/v1-s0-003-pr2-runtime-feasibility.md`](serving/v1-s0-003-pr2-runtime-feasibility.md) | One host, one architecture, one point in time on 2026-08-24, single-request throughout. `T7` — a cumulative request counter — is a blocking threshold recorded as not met as written, and ADR 0002 accepted the pair with that exception. The runtime was started in the container desktop distribution's own single-node cluster and answered through cluster DNS and a Service, so this is a Kubernetes result; the record predates ADR 0011 and names that cluster descriptively rather than by provider identifier, and the provider here is read from its description rather than from a field the record carries. |
| The published model lifecycle ordering — liveness holding while the model loads, readiness false until it is ready, the artifact surviving a restart, and a cache hit in both arms — held in all three cold and warm comparisons measured. | `certified` | `C2` | `local-real-cpu` | `capable-host`, no provider | [`serving/v1-s2-007-pr1-cold-warm-start.md`](serving/v1-s2-007-pr1-cold-warm-start.md), [`serving/v1-s2-007-cache-miss-observation.md`](serving/v1-s2-007-cache-miss-observation.md) | Six starts on one host on 2026-09-03, CPU only. The cold arm was not cold — Windows offers no supported page-cache drop — and the host was memory-constrained throughout, with 904 to 1,725 MiB free of 16,057 MiB. The cache-miss observation cited beside it is from 2026-09-04 and establishes the miss classification and the refusal it triggers; it says nothing about the six starts or either arm. |

### Pod recovery

*What does a caller see when the serving pod goes away?*

**Tally:** 2 `certified`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| One serving pod deleted by name mid-load produced a 31,960 ms caller-visible outage in which 40 of 41 dispatched requests were refused with `capability-unavailable`, the replacement reported itself Ready 33,665 ms after the delete, and no person intervened. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`serving/v1-s4-006-pr1-inference-pod-recovery.md`](serving/v1-s4-006-pr1-inference-pod-recovery.md) | One provider, one host, one single-replica release, one load profile, one pod lost once on 2026-09-16, as a bounded observation under ADR 0013. One replica is the cause of the outage. The forward is in every latency, and the readiness sampler takes 1.7 to 5.4 seconds to answer. |
| A release starved of processor time started, bound its port, began loading the model and did not finish for 179,755 ms; four request surfaces were asked and readiness sampled from four places throughout; and dropping the overlay and upgrading returned it to a served completion. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`serving/v1-s4-007-pr1-unready-model-recovery.md`](serving/v1-s4-007-pr1-unready-model-recovery.md) | One provider, one host, one single-replica release, one misconfiguration applied once on 2026-09-16, as a bounded observation under ADR 0013. The model did not become ready inside the registered observation window, which is not the same as proving it never would: the load was starved rather than failed. The recovery is an operator changing a value and issuing an upgrade. |

### Rollback and release recovery

*Can a bad release be taken back, with real inference restored?*

**Tally:** 1 `certified`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| A deliberately broken release revision was detected by an init container's non-zero exit 6,425 ms after the fault, rolled back in 1,512 ms, and served a real completion 7,983 ms after detection. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`environment/v1-s3-011-pr2-upgrade-rollback.md`](environment/v1-s3-011-pr2-upgrade-rollback.md) | One provider, one host, one moment, one replica of each tier, and one injected fault — an artifact byte-count mismatch. Five attempts were made and four failed for reasons the record lists. Detection and rollback were both performed by an operating script a person started. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed record. |

### Telemetry, dashboard, and alerts

*What can be seen while it runs, and what reaches a person?*

**Tally:** 6 `certified`, 1 `not-claimed`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| The InferOps API emits eight catalog metrics and structured request records when its ASGI interface is exercised, each inside a declared series budget. | `certified` | `C1` | `mock` | `repository-only`, no provider | [`telemetry/v1-s1-008-pr1-validation.md`](telemetry/v1-s1-008-pr1-validation.md) | Repository-local, mock-backed evidence, and at the date of the record nothing collected any of it — no exporter, collector, store, dashboard, or alert was selected. A release-scoped collector has since scraped these metrics, which is a separate row with its own record. No component emits a span. |
| The collector the release installs discovered and scraped both InferOps scrape jobs on `docker-desktop`, and a real Prometheus evaluated every accepted correlation query against what it collected. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`telemetry/v1-s3-011-pr2-telemetry-during-recovery.md`](telemetry/v1-s3-011-pr2-telemetry-during-recovery.md), [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md) | One provider, one Windows host, one moment, one replica of each tier, sampled every five seconds. The collector's series are ephemeral and no durable store exists. |
| A real Prometheus parsed and evaluated all 30 panel expressions in nine states and refused none, and a real Grafana imported the generated JSON and rendered all 29 panels. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`telemetry/v1-s4-002-pr2-dashboard-validation.md`](telemetry/v1-s4-002-pr2-dashboard-validation.md), [`telemetry/v1-s4-002-pr1-validation.md`](telemetry/v1-s4-002-pr1-validation.md) | One provider, one host, one single-replica release, one Grafana version, one run of about twelve minutes on 2026-09-14. Grafana ran as a local container outside the cluster and no server runs it. Of 270 readings, 152 were a value, 81 empty and 37 zero. |
| Six alerts are published, each with an owner, a severity, the condition, what a caller is experiencing, an evidence query repeated verbatim from an accepted correlation query, an operator action, a runbook link, a declared threshold basis, and what it will be quiet for; five conditions are deferred — three because nothing emits the signal, one because no chart here installs the exporter that would, and one because no error budget is decided anywhere in this project — and eight more are refused by a named rule. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`telemetry/v1-s4-008-pr1-alert-validation.md`](telemetry/v1-s4-008-pr1-alert-validation.md), [`telemetry/v1-s4-008-pr1-validation.md`](telemetry/v1-s4-008-pr1-validation.md) | The scenario fixtures are synthetic — every number in them was written by hand — and the evaluator is not Prometheus. The pinned collector's own `promtool` loads both rendered rule files, which is a smaller thing than evaluating them. No threshold is a figure this project measured. |
| Five of the six alerts were replayed over the telemetry captured by three real `docker-desktop` experiments; one fired, over one capture, and every silence carries the reason it was silent. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`telemetry/v1-s4-008-pr1-alert-validation.md`](telemetry/v1-s4-008-pr1-alert-validation.md), [`serving/v1-s4-007-pr1-unready-model-recovery.md`](serving/v1-s4-007-pr1-unready-model-recovery.md) | The captures are real, from `docker-desktop`, and they step at 15 seconds; the replay over them is this repository's own evaluator, which its record classifies `local-static` — so this row is a `C0` claim about a replay, not a `C2` claim about a runtime. The 60-second step belongs to the synthetic fixtures rather than to these captures. One alert missed the same run by one evaluation, and that is recorded rather than tuned away. |
| A prompt, a response, a provider error body, and a secret have no permitted placement in the committed telemetry catalog at all, and a tenant identifier, a correlation identifier, and any unbounded or measured value are excluded from metric labels. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`telemetry/v1-s0-007-pr1-validation.md`](telemetry/v1-s0-007-pr1-validation.md), [`telemetry/v1-s1-008-pr1-validation.md`](telemetry/v1-s1-008-pr1-validation.md) | Content capture is disabled at the API's metric-declaration and structured-record sinks and has no policy that could enable it. The first record cited predates every one of those sinks — when it was written nothing in this repository emitted a metric, a log record, or a span, and it checks the committed catalog alone; the second is where the sinks arrive. The check is over committed data and the sinks that read it. |
| An operator is notified when an InferOps alert fires. | `not-claimed` | — | `documented-unexecuted` | `local-kubernetes`, no provider | none recorded | The gap is published in the alerts document rather than left to be discovered. |

### Performance evidence

*What was measured under load, and what does it not mean?*

**Tally:** 3 `certified`, 1 `deferred`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| A versioned load profile with a warm-up, rising concurrency levels, duration and request bounds, a client deadline above the API's, and a fixed response classification generates repeatable load and a raw record set whose accounting is checked on read. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`serving/v1-s4-004-pr1-validation.md`](serving/v1-s4-004-pr1-validation.md), [`serving/v1-s4-003-pr1-validation.md`](serving/v1-s4-003-pr1-validation.md) | The tool's own rehearsal is synthetic — an in-process stub whose latencies are a 20 ms sleep plus loopback and thread scheduling — and it says so. Its first real load was sent by the performance scenarios, on `docker-desktop`, on one host, twice, in one window. |
| The load profile ran twice against a release the workflow installs, all 366 requests answered HTTP 200, and for that one single-slot release and fixed prompt the observed degradation point is concurrency 2: completed requests stayed between 0.554 and 0.575 per second from concurrency 1 to 4 while median latency rose about twofold and fourfold. | `certified` | `C2` | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`serving/v1-s4-004-pr1-validation.md`](serving/v1-s4-004-pr1-validation.md), [`serving/v1-s4-004-pr2-performance-findings.md`](serving/v1-s4-004-pr2-performance-findings.md) | One provider, one host, one release, one prompt, two repetitions in one window on 2026-09-14, published as a bounded local observation under ADR 0013. The node was shared with twelve other running pods, every latency includes a loopback port-forward, the prompt cache serves nearly all of every prompt after the first, and the repository was not committed when the run was made. |
| A local serving baseline was executed against a fixture, a warm-up, and five thresholds registered before the run, and all thirty measured requests succeeded with every threshold met. | `certified` | `C2` | `local-real-cpu` | `capable-host`, no provider | [`serving/v1-s2-005-local-baseline-experiment.md`](serving/v1-s2-005-local-baseline-experiment.md), [`serving/v1-s2-005-baseline-raw-results.md`](serving/v1-s2-005-baseline-raw-results.md) | One host, one day on 2026-09-03, CPU only, concurrency one, one request shape. The five thresholds were registered before the run; the fixture was not the one registered — the original two-message fixture was refused by the API on all thirty requests of the prior attempt and was rewritten to be answerable before this run, which the experiment record states in its own correction section. The record's own warning is that V1 publishes no throughput, latency, capacity, or benchmark figure from these results, and its periodic processor sampler read 0.83 per cent while a live poll during generation read 801.97 per cent, so its processor figures materially understate the load. |
| InferOps sustains a stated throughput and capacity under load. | `deferred` | — | `documented-unexecuted` | `capable-host`, no provider | none, and a `deferred` claim may cite none | Deferred out of V1 by the project boundaries and left deferred by ADR 0013, which narrowed the rule only far enough to allow a bounded observation of one declared, authorized local experiment. This is the portable claim, and it stays deferred. It is also a recorded coverage gap in the test inventory: the capacity layer declares no test paths and its marker is deselected by default, so no pytest module would notice if it were promoted. |

### Cost method

*What does this project say a run costs?*

**Tally:** 2 `certified`, 1 `not-claimed`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| Two committed cost records derive their processor and memory use by tool from the committed samples of the `V1-S4-004` performance run rather than from a typed-in figure, and each regenerates from its own input and the committed method. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`cost/v1-s4-005-pr2-cost-baseline.md`](cost/v1-s4-005-pr2-cost-baseline.md), [`cost/v1-s4-005-pr2-validation.md`](cost/v1-s4-005-pr2-validation.md) | What is certified here is a file-reading operation: that the use is taken from committed samples by tool rather than typed in, and that each record regenerates from its own input and the committed method. The samples themselves are local real CPU evidence measured on `docker-desktop` during `V1-S4-004` — one host, one release, one prompt, two runs — and that measurement is a different row with its own record; every price is from the synthetic rate card, so both cost records carry confidence `none` and certify nothing themselves. The window is a load span rather than an accounting hour, the collector is left on the unallocated line by a choice rather than a measurement, and the owner is declared rather than observed. |
| Every amount declares its basis, no amount whose basis is not `actual` may carry the vocabulary or the reference of an invoice, every unit cost carries the count it was divided by and vanishes below a declared minimum, and a record's confidence is recomputed from its own inputs rather than read from a field its producer filled in. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`cost/v1-s0-008-pr1-validation.md`](cost/v1-s0-008-pr1-validation.md), [`cost/v1-s4-005-pr1-validation.md`](cost/v1-s4-005-pr1-validation.md) | The only rate card committed is synthetic and says so in its own contents, so every record it prices has confidence `none`. ADR 0014 narrows V1 to the estimated basis; the allocated basis stays specified and unreachable. |
| Running this inference workload costs a stated amount on a real provider. | `not-claimed` | — | `estimated` | `repository-only`, no provider | none recorded | The arithmetic that would consume a real rate card is specified and tested against synthetic fixtures. Nothing else about the figure would be different; the price would. |

### Security boundary

*What is enforced, and what is only rendered?*

**Tally:** 3 `certified`, 2 `not-claimed`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| Every control in the committed security baseline derives its status from the verification it names, a control naming an automated test or a shell guard names one that exists, and no control claims to act inside a running system. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`security/v1-s0-009-pr1-validation.md`](security/v1-s0-009-pr1-validation.md) | The cited record measured ten of thirty-two controls with no verification at all. The committed baseline has since grown to thirty-eight, of which six have no verification and nine are enforced by nothing automated; those three figures are properties of the data committed today rather than of the record, and the suite that reads it is what holds them. Twelve risks are carried rather than reduced, and ten of the twelve block production use. |
| A committed manifest dropping a required workload security control is refused citing the rules it drops and no others, checked in both directions against nine fixtures that each drop one control. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`security/v1-s3-004-pr1-validation.md`](security/v1-s3-004-pr1-validation.md), [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md) | The validator reads YAML. It holds no credential, contacts no cluster, and stops nothing being applied; no admission control applies any of its rules to a pod. When the first record cited was written no release had been installed and none could be, because no API image was published; `V1-S3-011` installed one from those renders afterwards, which is the second record cited, and no check in either reads a pod that resulted. |
| An image scanner and a dependency auditor were each run once by hand against the pinned runtime image and the committed lockfile at the committed severity threshold, and two CycloneDX bills of materials were published. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`security/v1-s2-006-pr1-validation.md`](security/v1-s2-006-pr1-validation.md) | One host, one day on 2026-09-03, against one vulnerability database version. A rerun tomorrow can find something today's run did not, so a green result dates rather than proves. The dependency scan covers Python distributions only. No provenance is verified and `DR-08` still carries that gap. The record describes itself as local real evidence in the older vocabulary; the strategy assigns the `security-scan` layer the `local-static` class with a `C0` ceiling, and this row follows the strategy, because reading a pinned image is not running one. |
| The NetworkPolicy objects the chart renders restrict traffic in the clusters this project runs on. | `not-claimed` | — | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`security/v1-s3-004-pr1-network-policy-enforcement.md`](security/v1-s3-004-pr1-network-policy-enforcement.md) | One host, one day, on Docker Desktop's Kubernetes rather than the cluster ADR 0001 accepted, and the record says substituting a cluster is a substitution rather than an equivalence. |
| A deployed InferOps workload is authenticated, authorized, isolated, and defended. | `not-claimed` | — | `documented-unexecuted` | `local-kubernetes`, no provider | none recorded | The rendered pod-security settings are carried by workloads a release deployed. That is a property of the manifests, and no check reads a pod that resulted. |

### Multi-replica serving

*Has more than one serving replica ever been certified?*

**Tally:** 1 `not-claimed`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| Two real serving replicas are certified to serve real inference in a cluster. | `not-claimed` | — | `local-real-cpu` | `docker-desktop`, `local-kubernetes` | [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md) | The refusal is the evidence. It is recorded in the paved-road record and it is not a weaker form of a certification. |

### Tests, continuous integration, and evidence

*Who checks the rows above, and where does the proof live?*

**Tally:** 5 `certified`, 1 `not-claimed`.

| Claim | Status | Level | Evidence class | Provider and environment | Record | Limitation |
|---|---|---|---|---|---|---|
| Eleven gates are committed as one workflow and as a matrix that maps each to the claims it defends or to a recorded reason it defends none, compared with the workflow in both directions; nine of them have passed on the selected service. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`testing/v1-s4-001-pr1-validation.md`](testing/v1-s4-001-pr1-validation.md), [`testing/v1-s4-001-pr2-validation.md`](testing/v1-s4-001-pr2-validation.md) | The first record cited committed nine gates and no job had then executed on the service; its one hosted run failed three jobs. The second is where the count reaches eleven and where the nine are read back from the service's public API on 2026-09-13. No log or artifact from those runs is promoted into a record and the logs expire, the two infrastructure gates have never run there, and two gates are not deterministic because a vulnerability database moves daily. |
| The default test lane downloads no model and reaches no cluster, because every marker belonging to a layer that needs one is deselected by the committed default marker expression and a test compares that expression with the strategy in both directions. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`testing/v1-s0-006-pr1-validation.md`](testing/v1-s0-006-pr1-validation.md), [`testing/v1-s4-001-pr2-validation.md`](testing/v1-s4-001-pr2-validation.md) | The marker expression is what the first record cited establishes, and when it was written no continuous-integration lane existed at all. Helm and Terraform arrived with the second: they run in the lane only as subcommands that read files, and a check refuses anything else it can recognise. The lane is cheap and reproducible rather than hermetic — five gates consume the network — and three lanes still run entirely by hand. |
| Evidence that certifies a claim is committed under `docs/proof/`, carries classification, provenance, environment, method, results, limitations, and authorisation, and is produced by a reviewed change rather than by a job. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`telemetry/v1-s0-007-pr1-validation.md`](telemetry/v1-s0-007-pr1-validation.md) | The cited record is from the day the four templates were published, when they had produced nothing. Two have produced records since — one experiment record and five raw-result records, counted by a suite from the declarations those records carry — and `environment` and `claim-evidence` still have none. This matrix does not change that: binding claims in a table is not the one-claim-per-record form the fourth template exists to enforce. |
| Every relative link in every committed Markdown document resolves from the directory of the file that contains it. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`testing/v1-s0-006-pr1-validation.md`](testing/v1-s0-006-pr1-validation.md) | It establishes that a path resolves, and nothing more. It runs over committed Markdown only, reads a target up to its first closing parenthesis, and skips fenced blocks, so a command sample is never mistaken for a link and a link inside one is never checked. |
| The test strategy, the claim and test matrix, the test inventory, the gate matrix, this claim and evidence matrix, and the pytest configuration are compared with their committed data in both directions, so none can gain or lose an identifier without a failing build. | `certified` | `C0` | `local-static` | `repository-only`, no provider | [`testing/v1-s0-006-pr1-validation.md`](testing/v1-s0-006-pr1-validation.md), [`testing/v1-s1-007-pr1-validation.md`](testing/v1-s1-007-pr1-validation.md), [`testing/v1-s4-001-pr1-validation.md`](testing/v1-s4-001-pr1-validation.md), [`testing/v1-s4-009-pr1-validation.md`](testing/v1-s4-009-pr1-validation.md) | It stops each document drifting from its data. The four records cited arrive in that order — the strategy, the inventory, the gate matrix, this register — because the first covers the strategy and its three documents alone and nothing else existed to compare when it was written. Most layers have no code behind them, and the suite cannot tell an honestly planned layer from one that will never be written. |
| A continuous-integration lane installs a release into a cluster or executes a real model. | `not-claimed` | — | `documented-unexecuted` | `repository-only`, no provider | none recorded | Normal continuous integration must not discover an ambient cluster and mutate it, and the lane is checked to be unable to reach one. |

## What V1 does not claim

17 claims, derived from the register rather than listed here: a
claim that stops being certified joins this table without anybody adding it.
That is deliberate. A page that can only be complete about its successes is
an advertisement.

| Claim | Status | Why it is not certified | Record, where one exists |
|---|---|---|---|
| A workload described by a `WorkloadContract` document is served by the platform that document configures. | `planned` | Every real run so far deployed the runtime from a feasibility manifest or from the Helm chart, not from a generated `WorkloadContract`. The mock layers show the API maps the call; they cannot show a document drove the deployment. | none, and a `planned` claim may cite none |
| Deployment values are derived only from a document that has passed validation. | `planned` | Deployment rendering does not exist. The chart's values are written by an operator, not derived from a document. | none, and a `planned` claim may cite none |
| A reviewer starting from a clean clone reaches mock tests, model acquisition, local real inference, a Kubernetes deployment, telemetry, load, a failure experiment, and a scoped cleanup, with every manual step and the elapsed time recorded. | `planned` | No clean-clone run of the whole journey has been executed or recorded. The pieces have each been run, at different times, on the same host, by the author. The workflow that would run them in one sitting exists, and its two test modules drive it only against stubs: they establish its order, consent, ledger, and cleanup boundary, and nothing about whether the journey completes. | none, and a `planned` claim may cite none |
| The mock serving path declares its own kind and refuses a model identity that is not mock-labelled, so a mock result cannot be mistaken for a real one. | `planned` | The behaviour is implemented and exercised by the adapter and mock-integration layers. The claim and test matrix has not promoted it, and no evidence record binds it. | none, and a `planned` claim may cite none |
| A model that is not ready produces a canonical error rather than an unhandled failure or a fabricated answer. | `planned` | The unready-model experiment measured the real condition and found that no caller ever received `model-not-ready`: all eight completions came back `capability-unavailable` with condition `runtime-unreachable`. That is a measured fact about the deployed shape, and it is a reason this claim stays planned rather than a reason to promote it. | none, and a `planned` claim may cite none |
| A runtime that cannot be reached produces a canonical error rather than an unhandled failure. | `planned` | The mock layers show the API maps the condition to the right error. They cannot show the condition occurs, or that the runtime produces it in the way the mock's author imagined. | none, and a `planned` claim may cite none |
| Two real serving replicas are certified to serve real inference in a cluster. | `not-claimed` | The workflow was run on the reference host and refused at the capacity gate before it installed anything: 8,484,278,272 bytes of uncommitted cluster memory available against 8,657,043,456 required, a shortfall of about 165 MiB held by unrelated workloads that were not this project's to remove. The gate was not weakened and the replica count was not reduced to fit. | [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md) |
| InferOps sustains a stated throughput and capacity under load. | `deferred` | Deferred out of V1 by the project boundaries and left deferred by ADR 0013, which narrowed the rule only far enough to allow a bounded observation of one declared, authorized local experiment. This is the portable claim, and it stays deferred. It is also a recorded coverage gap in the test inventory: the capacity layer declares no test paths and its marker is deselected by default, so no pytest module would notice if it were promoted. | none, and a `deferred` claim may cite none |
| In a real run, no prompt, response, or secret reaches a log or a metric. | `planned` | The mock-integration suite checks that forbidden content reaches neither sink. The claim requires `C2` and a real layer, and no record binds it. | none, and a `planned` claim may cite none |
| An operator is notified when an InferOps alert fires. | `not-claimed` | No alert manager, receiver, routing tree, or notification path is committed or installed. The rules render into the chart and nothing evaluates or routes them. | none recorded |
| Running this inference workload costs a stated amount on a real provider. | `not-claimed` | Nothing here has ever been paid for. It runs on a local single-node cluster on a contributor's own machine, no provider account exists, and the `actual` basis is therefore unreachable in V1. | none recorded |
| The NetworkPolicy objects the chart renders restrict traffic in the clusters this project runs on. | `not-claimed` | An executed experiment on 2026-09-06 applied a total-denial policy and nothing was refused: pod-to-pod by address, a DNS lookup, and a direct query to CoreDNS all succeeded, because the observed network plugin runs with no policy controller enabled. The four policy objects the chart renders are inert on that plugin. | [`security/v1-s3-004-pr1-network-policy-enforcement.md`](security/v1-s3-004-pr1-network-policy-enforcement.md) |
| No credential and no model artifact enters this repository's public history. | `planned` | A secret scanner has run once by hand from its published container image, over 134 commits, and found no leaks; the gate that installs the pinned release archive has since passed on the service, but that run is observed rather than recorded. The claim stays planned on the strength of one run. It is a recorded coverage gap in the test inventory: no pytest module scans history for a credential, and the suite that reads the scanner configuration checks only that it is committed, parses, and exempts things that exist. | none, and a `planned` claim may cite none |
| A deployed InferOps workload is authenticated, authorized, isolated, and defended. | `not-claimed` | Nothing in this repository authenticates a caller, authorises a request, or admits a pod. There is no admission control, no gateway, and no multi-tenancy. Twelve risks are carried rather than reduced and ten of them block production use. | none recorded |
| A continuous-integration lane installs a release into a cluster or executes a real model. | `not-claimed` | No workflow for a cluster lane is committed, only the rules one must satisfy. No runner is labelled capable and no hosted runner is authorized to hold the pinned model artifact; ADR 0005 D6 leaves that half open on purpose. | none recorded |
| InferOps has published a versioned V1 release. | `not-claimed` | The release process is documented and no release has been executed. The changelog holds unreleased changes only. | none recorded |
| InferOps is a production-ready, portable inference platform someone can deploy for someone else. | `not-claimed` | `production-experience` is unreachable from this repository: there is no organizational production to draw it from, and public-cloud execution is not production operation. Every executed result is one Windows host, one provider, CPU, one replica of each tier, started by hand under explicit authorization against a cluster the operator already owns. | none recorded |

## What this page is not

- **It is not a monitoring dashboard.** It reads committed files and asks
  nothing of a cluster. The operations view is
  [the inference operations dashboard](../telemetry/inference-operations-dashboard.md);
  the two answer different questions and neither substitutes for the other.
- **It is not a second source of truth.** Every status, level, label,
  provider, environment, record, and limitation above is read from
  [the register](../testing/claim-evidence-matrix.md) when the page is
  generated. This tool holds one thing the register does not: which claims a
  reviewer is shown under which heading.
- **It is not a freshness or assurance signal.** Nothing here says when a
  result was last re-run, whether the environment that produced it still
  exists, or whether it would reproduce today. A record's own date and
  provenance sections are the only answer to that, and they are in the record.
- **It is not a release gate.** No check consumes this page to decide whether
  anything may ship. The gates are in
  [the continuous-integration gate matrix](../testing/ci-gate-matrix.md).

## Limitations

- The page inherits every limitation the register carries, including the
  largest: the checks establish that references resolve, that ranks and
  ceilings hold, and that the page and the register agree. None of them
  establishes that a statement is true, or that a record says what the row
  citing it says it says.
- Every real result behind these rows was produced on one Windows host, by
  one author, by hand. No outside party has reviewed a claim against its
  evidence.
- The capability grouping is a reading. Which claims belong under *model
  integrity* rather than *real serving* is a judgement made in
  `tools/proof_dashboard/core.py`, and no check decides it.
- **7 certified claims appear on this page as a number only.** They
  belong to no capability group, and a certified claim is not repeated in the
  table of what V1 does not claim, so they are counted in every total above
  and shown in no row. Every claim V1 does **not** certify is shown as a row
  whether a group names it or not. A reader who wants all of them in one
  table wants [the register](../testing/claim-evidence-matrix.md), which this
  page is a view of rather than a replacement for.
- The bounded performance, recovery, and cost figures quoted in these rows
  are observations of declared local experiments under
  [ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
  and
  [ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md).
  They are not capacity, service-level objectives, availability figures,
  error budgets, recovery-time objectives, benchmarks, or costs.
