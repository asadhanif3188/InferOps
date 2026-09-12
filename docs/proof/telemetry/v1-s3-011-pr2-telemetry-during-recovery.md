# V1-S3-011-PR2 — what telemetry saw while a serving pod was replaced

Date captured: 2026-09-12

Classification: **local real evidence**, redacted. Evidence class `local-real-cpu`.
A real Prometheus — the collector the release installs — was asked the accepted
correlation expressions before, during, and after a real serving pod was deleted
and replaced in the cluster Docker Desktop provides.

`V1-S3-011-PR1` established that the collector discovers and scrapes both InferOps
jobs and that a real Prometheus can evaluate every accepted query. This record
asks a different question: **during a failure and a recovery, which of the things
an operator would want to know can this system actually answer?** The answer is
partly yes, partly no, and the point of this record is to be exact about which.

## Method

One release of the real profile, installed on `docker-desktop`, with the telemetry
collector enabled. Two loopback forwards: one to the collector's API, one to the
release's API Service. Three real inference requests before the disruption and
three after it, so that counters had something to count — **their timings were
deliberately not recorded and are not a measurement of anything.** One serving
runtime pod deleted by name. `up` for the serving-runtime job sampled every 5 s
for 60 s across the replacement.

Every expression below is the committed one from
[the correlation query record](../../telemetry/telemetry-correlation-queries.v1alpha1.json),
asked of the collector's `/api/v1/query`.

## The four-way classification

The query record already carries this vocabulary in its `answerability` field,
and this run is what turns three of the four from a claim into an observation.

| Signal the lifecycle wanted | Expression | Status | What was actually seen |
|---|---|---|---|
| Target availability, per job | `inferops:scrape_targets_up:sum / inferops:scrape_targets:count` | **collected and queryable** | `1` for both jobs before and after |
| Workload identity and version | `inferops_build_info` | **collected and queryable, API tier only** | one series, on the platform-API job; unchanged across the replacement |
| Request counters | `sum by (…) (inferops_inference_requests_total)` | **collected and queryable** | `3` before → `6` after, outcome `success` |
| Readiness failures | `sum by (…) (inferops_readiness_check_failures_total)` | **collected and queryable** | `2` before → `3` after: one failure during the replacement |
| Per-target scrape health | `up` | **collected and queryable** | see the window below |
| Model readiness | `inferops_model_ready` | **not emitted** | 0 series. The catalog assigns this to the serving-runtime adapter and marks it not emitted; nothing puts it on any endpoint |
| Pod restarts / container readiness | `kube_pod_container_status_restarts_total` | **no source** | 0 series. It would need `kube-state-metrics`, which this release does not install and this project has not adopted |

Nothing was derived, computed, or invented to fill a row. The two empty rows are
empty, and they are reported as empty.

## The replacement window, sampled

`up{job="inferops-inferops-llm-serving-runtime"}`, every 5 s from the deletion:

| Since deletion | Targets reported up |
|---:|---|
| 5 s – 15 s | the **deleted** pod only |
| 20 s – 50 s | the deleted pod **and** the replacement, both `1` |
| 55 s – 60 s | the replacement only |

**Read this carefully, because the obvious reading is wrong.** `up` never reached
`0` for the serving-runtime job, and that does **not** mean there was no
interruption. Three separate things are true here and only the first is about
availability:

1. **`up` means "the scrape succeeded", not "the workload is ready".** The
   replacement's target was discovered and answered a scrape while its runtime was
   still loading a 1.71 GiB model, so it reported `1` long before it could serve
   anything. An operator reading only this expression during a replacement would
   conclude the service was fine when it was not.
2. **The deleted pod kept reporting `1` for roughly 50 s.** It was terminating,
   not gone: the runtime has a drain period, and Prometheus keeps a target's last
   value until service discovery drops it and staleness applies. A target still
   answering is a target still answering.
3. **The overlap is not two replicas.** One replica of the serving runtime was
   configured throughout, and the pod-restart record establishes separately that
   the replacement had a different name and a different UID. Two series in this
   window are one workload mid-replacement, not a multi-replica claim.

The readiness-failure counter moving `2 → 3` is the signal that *did* notice: it
is emitted by the API's own readiness check against its serving adapter, and it
incremented once while the runtime was unavailable. That is the closest thing this
system emits to "something restarted", and it is a side effect of a readiness
probe rather than a restart signal.

## What this establishes, and what it does not

Established, on `docker-desktop` only:

- the collector installed by the release answers the accepted correlation
  expressions against a **real scrape**, during a disruption and not only at rest;
- request counters increment across a recovery and can be read before and after;
- workload identity is queryable for the API tier;
- at least one emitted signal moves when a serving pod goes away.

Not established, and stated rather than implied:

- **that telemetry would have detected the failure.** It did not, in the sense that
  matters: no expression here went to zero or to an error state when the serving
  pod was deleted. The failure in the upgrade/rollback experiment was detected by
  reading the workload's init-container exit status through the Kubernetes API,
  not through a metric;
- **any alerting.** No alerting rule, no receiver, no runbook link, and no
  notification path exists. `V1-S4-008` is where that would live;
- **any dashboard.** Nothing renders these series;
- **any latency, throughput, or capacity figure.** Six requests across the whole
  run, sent to move counters off zero;
- **durability.** The collector's series are in an `emptyDir` and go with its pod.
  Everything above was read while that pod was alive and would not survive it.

## Limitations

- One provider (`docker-desktop`), one Windows host, one replacement, one moment.
- One replica of each tier. The multi-replica profile was refused at the capacity
  gate on this host.
- The sampling interval is 5 s, so the window boundaries are 5 s wide. Nothing
  here is a measurement of how long anything took.
- `kind` has not executed this, and
  [ADR 0011](../../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
  forbids reading one provider's telemetry answer as the other's.

## Authorisation

Required: **yes**. The run installs a release into a cluster the operator owns,
loads a real model, sends real inference requests, and deletes a running pod.

Granted by: the host owner, in the session that ran it, for the `docker-desktop`
provider specifically.

Sensitive values removed before committing: host name, user account, absolute
filesystem paths, the operator's kubeconfig and its path, and the API server
address. Cluster-internal pod names are reproduced as emitted. No prompt or
completion text was retained.
