# V1-S4-004-PR1 — the performance scenario matrix, executed on `docker-desktop`

Date captured: 2026-09-14

Classification: **local real evidence**, redacted. Evidence class `local-real-cpu`.
One InferOps release of the real profile was installed on `docker-desktop` by
[`scripts/environment/performance-scenarios.sh`](../../../scripts/environment/performance-scenarios.sh).
After a 60-second idle baseline, the committed
[load profile](../../../deploy/serving/load/llm-load-profile.v1.json) ran twice
through the release's API: a warm-up, then concurrency 1, 2, and 4. The node's cgroup
counters were sampled throughout, the release's own collector was read afterwards, and
the release was uninstalled. The machine-readable result is
[`v1-s4-004-pr1-performance-record.v1alpha1.json`](v1-s4-004-pr1-performance-record.v1alpha1.json).
It regenerates exactly from the six committed inputs beside it:
[environment](v1-s4-004-pr1-environment.v1alpha1.json),
[windows](v1-s4-004-pr1-windows.v1alpha1.json),
[resource samples](v1-s4-004-pr1-resource-samples.v1alpha1.jsonl),
[telemetry](v1-s4-004-pr1-telemetry.v1alpha1.json), and the raw load sets
[run 1](v1-s4-004-pr1-run-1-raw.jsonl) and [run 2](v1-s4-004-pr1-run-2-raw.jsonl).

This change also adds
[ADR 0013](../../architecture/decisions/ADR-0013-bounded-local-performance-observations.md),
which makes the figures below publishable as bounded observations. Before it, ADR 0004
D6 and the project boundaries forbade publishing any latency or throughput figure.

## Claim boundary

Established, on `docker-desktop`, for one single-replica release, on one host, between
16:16:27 and 16:31:21 UTC on 2026-09-14:

- the scenario matrix ran end to end, unattended, and its record passed all eight of
  its checks;
- both repetitions completed. Each dispatched 183 requests — 3 warm-up and 60 per
  level — and all 366 were successes;
- the collector's counters reconcile **exactly** with the raw load sets, per run: the
  API's request counter, the API's output tokens, and the runtime's predicted tokens;
- the same three pods served throughout, with no container restart;
- for each phase, the latency distribution of its requests, its request and token
  rates, and the CPU and memory of every tier during the same window.

**Not established:** any saturation point, degradation statement, or comparison
between levels. The record carries `saturationJudged: false`, and that analysis is
V1-S4-004-PR2's. Nothing about `kind`, another host, a second replica, a different
prompt, or a GPU. None of the figures is a portable capacity figure, a production SLO,
or a benchmark of Kubernetes, the model, the runtime, or Docker Desktop.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository | `53492c5ddf20f982690dc3e8c4b0c982e7585c48` (the merge of V1-S4-003-PR1), **with this change uncommitted**. The run recorded the LF-normalized SHA-256 of the twelve files that decide what it did (`environment.repository.executedFiles`), and every one equals the file in this change's first commit |
| Scenario descriptor | `performance-scenarios.v1.json` 1.0.0, `sha256:cae87607cd65fe3152f68fb487e723e0b085148abbabe99252ec0d9c153e4fc1` |
| Load profile | `inferops-llm-load` 1.0.0, `sha256:4dc0fe4a4217f035875fcddbdb99b75246f3a74188d5eca8b4dbbec8f57081c5` |
| Chart | `inferops-llm-0.3.0`, release revision 1 |
| API image | Template `localhost/inferops-api@sha256:9687e1bb11bd2b728bd61fd1338718a6816efa65958b9366cdf536fe8fdfc087`; the pod reported `@sha256:783685ad…`; both are names of image config `sha256:fa912a7e56848652086afcf6807efcc039d1363a0b5e938246eb24015f7b5a21` in the node (see *Attempts*). Built on this host, published to no registry |
| Serving runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384`, `--threads 6 --parallel 1 --ctx-size 4096 --n-predict 128 --temp 0` |
| Model | `qwen3-1-7b-q8-0`, `Qwen/Qwen3-1.7B-GGUF` revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, delivered by the committed seed-image path |
| Collector | Prometheus `3.5.0`, scraping every 30 s |
| Container resources | Runtime: requests 1 CPU / 2Gi, limits 6 CPU / 3Gi. API and collector: requests 100m / 128Mi, limits 1 CPU / 512Mi |
| Deployed configuration | `INFEROPS_REQUEST_TIMEOUT_MS` 120000, `INFEROPS_MAX_OUTPUT_TOKENS` 128, `INFEROPS_LLAMA_SERVER_THREADS` 6, read from the release's ConfigMap |
| Kubernetes | Docker Desktop's cluster: one node, server `v1.34.3`, containerd `2.2.0`, kernel `5.15.146.1-microsoft-standard-WSL2`, cgroup v1; allocatable 12 CPU and 10188024Ki; node image `sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48`; `kubectl` `v1.34.3` |
| Helm | `v3.19.0+g3d8990f` |
| Container engine | Docker Desktop `29.7.2`, 12 processors, 10 432 536 576 bytes; its virtual machine reports 12 logical processors |
| Load generator host | Windows 11, AMD64, 20 logical processors, 16 836 890 624 bytes, Python `3.12.12` |
| Other workloads | 12 running pods in 3 other namespaces shared the node. They are counted in the record and not named |

## Method

From Git Bash at the repository root, inside the locked environment, with
`INFEROPS_PROVIDER=docker-desktop` and a `kubectl` `v1.34.3` first on the path:

```text
scripts/environment/api-image.sh build
scripts/environment/api-image.sh load
scripts/environment/api-image.sh values > .artifacts/api-image-values.yaml
scripts/environment/performance-scenarios.sh run \
  --values charts/inferops-llm/ci/real-values.yaml \
  --values .artifacts/api-image-values.yaml \
  --values .artifacts/model-seed-values.yaml \
  --confirm-real-kubernetes                                       exit 0
python -m tools.performance_scenarios verify --dir docs/proof/serving --prefix v1-s4-004-pr1-
```

The run's `record/` directory was copied into this directory under the
`v1-s4-004-pr1-` prefix. Nothing in it was edited. The model seed image and runtime
image already resolved inside the node and were not re-imported.

### The schedule, as kept

| Step | UTC |
|---|---|
| Idle baseline | 16:16:26.980 – 16:17:27.134 |
| Run 1 (`load-20260914T161728Z`) launched → exited | 16:17:27.384 → 16:22:54.750 |
| Run 1 phases | warm-up 16:17:28.346; `c1` 16:17:34.516; `c2` 16:19:22.763; `c4` 16:21:10.360 – 16:22:54.547 |
| Settle | 90 s |
| Run 2 (`load-20260914T162426Z`) launched → exited | 16:24:25.098 → 16:29:50.313 |
| Run 2 phases | warm-up 16:24:26.532; `c1` 16:24:31.780; `c2` 16:26:16.384; `c4` 16:28:04.515 – 16:29:50.181 |
| Final settle ends | 16:31:20.545 |

The whole workflow, from launch to exit, took 16 min 56 s by the operator shell's
timestamps, which are not committed. Every level stopped at its 60-request ceiling,
well inside its 180-second duration.

## What the run recorded

### Load, per phase

Latency is nearest-rank over successful requests, in milliseconds, measured by the
load generator and including the loopback port-forward. Rates are over each phase's
own window.

| Run | Phase | Requests | Successes | P50 | P95 | P99 | Min | Max | Requests/s | Output tokens/s |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | warm-up | 3 | 3 | 1827 | 2663 | 2663 | 1672 | 2663 | 0.486 | 8.265 |
| 1 | `c1` | 60 | 60 | 1744 | 2258 | 2689 | 1583 | 2689 | 0.554 | 9.422 |
| 1 | `c2` | 60 | 60 | 3504 | 4100 | 4433 | 1797 | 4433 | 0.557 | 9.479 |
| 1 | `c4` | 60 | 60 | 6908 | 7244 | 7311 | 1903 | 7311 | 0.575 | 9.790 |
| 2 | warm-up | 3 | 3 | 1714 | 1838 | 1838 | 1688 | 1838 | 0.571 | 9.719 |
| 2 | `c1` | 60 | 60 | 1700 | 2074 | 2365 | 1581 | 2365 | 0.573 | 9.751 |
| 2 | `c2` | 60 | 60 | 3411 | 4437 | 4765 | 2320 | 4765 | 0.554 | 9.433 |
| 2 | `c4` | 60 | 60 | 6775 | 8614 | 9311 | 1647 | 9311 | 0.567 | 9.653 |

Every one of the 366 requests answered HTTP 200 with finish reason `stop`, 35 input
tokens, and 17 output tokens. No request reached the 128-token limit.

### Resources, per phase

CPU is in millicores, from the counter increase between the first and last samples
inside the phase. Memory is the peak working set. "Node outside release" is the node
less the three release pods.

| Run | Phase | Samples | VM CPU | Node CPU | Node outside release | Runtime CPU | API CPU | Collector CPU | Runtime memory | Node memory |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| — | idle | 24 | 353 | 285 | 282 | 1 | 1 | 1 | 538 787 840 | 5 732 769 792 |
| 1 | warm-up | 2 | 6906 | 6582 | 597 | 5979 | 5 | 1 | 544 473 088 | 5 729 030 144 |
| 1 | `c1` | 32 | 6744 | 6470 | 518 | 5944 | 7 | 1 | 546 287 616 | 5 744 668 672 |
| 1 | `c2` | 32 | 6827 | 6545 | 541 | 5993 | 9 | 2 | 546 414 592 | 5 716 054 016 |
| 1 | `c4` | 31 | 6801 | 6523 | 520 | 5992 | 9 | 2 | 546 312 192 | 5 717 692 416 |
| 2 | warm-up | 2 | 6573 | 6363 | 400 | 5955 | 7 | 1 | 546 213 888 | 5 706 395 648 |
| 2 | `c1` | 30 | 6716 | 6437 | 477 | 5952 | 7 | 1 | 546 349 056 | 5 709 979 648 |
| 2 | `c2` | 31 | 6831 | 6536 | 536 | 5989 | 9 | 2 | 555 487 232 | 5 721 190 400 |
| 2 | `c4` | 31 | 6779 | 6518 | 513 | 5994 | 9 | 2 | 557 223 936 | 5 724 286 976 |

The warm-up phases lasted about five to six seconds and hold two samples each, under
the three the record requires of a measured phase. Their CPU figures span about three
seconds and are the least reliable in the table. The record does not require them.

### Counters, reconciled

| Run | Check | Before | After | Increase | Raw set |
|---:|---|---:|---:|---:|---:|
| 1 | API requests | absent, read as 0 | 183 | 183 | 183 dispatched |
| 1 | API output tokens | absent, read as 0 | 3111 | 3111 | 3111 |
| 1 | Runtime predicted tokens | 0 | 3111 | 3111 | 3111 |
| 2 | API requests | 183 | 366 | 183 | 183 dispatched |
| 2 | API output tokens | 3111 | 6222 | 3111 | 3111 |
| 2 | Runtime predicted tokens | 3111 | 6222 | 3111 | 3111 |

"Absent, read as 0" is marked `absentBeforeReadAsZero` in the record. Before the first
request, the API's labelled counters have no series at all. The record reads that as
zero only for the first run, only when the same pods served throughout with no restart,
and only because the workflow sends no inference request before that run. An absent
series in any other position leaves the check unreconciled.

The collector's own gauges, at its 15-second range step, never read more than one
request processing in the runtime and read at most three deferred, which is what one
parallel slot and four callers allow.

## For V1-S4-004-PR2 to account for

These are facts the record holds. None is a judgement about saturation, and this
record makes none.

1. **The runtime tier's CPU is between 5 944 and 5 994 millicores in every phase,
   including the warm-up and `c1`,** against a 6-CPU limit and `--threads 6`. It does
   not rise with concurrency.
2. **The successful request rate is between 0.554 and 0.575 per second at every level,**
   while the P50 latency is about 1.7 s at `c1`, 3.4–3.5 s at `c2`, and 6.8–6.9 s at
   `c4`.
3. **Every request returned 17 output tokens.** The fixture's answer ends well before
   the 128-token limit, so latency here is not bounded by that limit, and a different
   prompt would change every figure.
4. **Run-to-run spread is visible at `c4`:** P95 7 244 ms and 8 614 ms, P99 7 311 ms and
   9 311 ms.
5. **The node and virtual machine were not idle.** At idle, the VM used 353 millicores
   and the node outside the release 282. Under load, the node outside the release used
   400–597 millicores, which includes the sampler's own `docker exec` and whatever the
   12 other pods did.
6. **The minimum latency at `c2` and `c4` is close to `c1`'s** (1 647–2 320 ms), which
   is what the first request of a phase, or one that found the slot free, would show.
   Whether that is so is not established here.
7. **The sampler's reads slowed under load.** A read took 316 ms at best, 1 171 ms at
   the median, and 1 874 ms at worst. A sample's placement is its midpoint, so its
   uncertainty is up to about 0.9 s.
8. **The collector's panels cover windows wider than a phase.** The dashboard captures
   at each phase end evaluate five-minute rates, which include earlier phases.

## Attempts, and what each found

The workflow was run three times. Only the third produced this record.

**Attempt 1 refused before any load.** The load facts are derived from the cluster,
and the first derivation compared each pod's `imageID` with the digest its Deployment
template named. The API image had been rebuilt and imported that session, and the
rebuild produced a new OCI index digest, `9687e1bb…`, over the same image as the
Sprint 4 dashboard run's `783685ad…`. The node's containerd holds both as names of one
image, and the pod reported the older name. The comparison refused a pod that was
running the right bytes. The binding now goes through the node's own `crictl inspecti`
of the template reference: the pod's `imageID` must be one of the digests the resolved
image carries, and the record keeps that image's config ID. The release was left
installed for inspection and then uninstalled by hand.

**Attempt 2 completed both load runs and failed while reading the collector.** The
capture asked Prometheus's build-information endpoint with a form `POST`, which
Prometheus serves to `GET` only and answers with an empty `405`. The capture now sends
`GET` when it has no parameters. While that release was still installed, the capture
and the record were run by hand against its collector to exercise them on real data.
That found the first-run counter behaviour described above: the API's labelled counters
were absent before any request, and the first version of the record counted that as
"not reconciled". None of attempt 2's data is committed. Its release was then
uninstalled by hand.

**Before attempt 3, a test found one more defect** that would have refused this record
at the last step. The check that keeps network addresses out of committed files read
the node's kernel release, `5.15.146.1-microsoft-standard-WSL2`, as an address. It now
ignores a dotted quad followed by a hyphen and a letter.

**Attempt 3** ran unattended from install to uninstall and exited 0.

## What changed in the repository

- [ADR 0013](../../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
  narrows ADR 0004 D6 and the third project-boundary rule to allow bounded local
  observations, and keeps portable capacity, SLOs, benchmarks, and cross-provider
  readings refused. ADR 0004, ADR 0005, the project boundaries, the architecture index,
  and the test strategy's document and data point to it. The `capacity` lane, the
  `capacity-and-load` layer, and `sustained-throughput-and-capacity-under-load` keep
  their status.
- [`performance-scenarios.v1.json`](../../../deploy/serving/experiments/performance-scenarios.v1.json),
  the scenario matrix.
- [`scripts/environment/performance-scenarios.sh`](../../../scripts/environment/performance-scenarios.sh),
  the workflow, registered with both environment-script safety suites.
- [`tools/performance_scenarios`](../../../tools/performance_scenarios/): descriptor
  validation, facts and environment derivation, sample parsing, the collector capture,
  and the record builder with `check`, `fields`, `repository`, `facts`, `telemetry`,
  `record`, and `verify`.
- `tools.llm_load` writes `startedAtEpochMs` into every raw header, and its reader
  accepts sets without it. Nothing else in its behaviour changed; the committed
  rehearsal set still reads.
- [The procedure](../../serving/performance-scenarios.md), and updates to
  [the load guide](../../serving/llm-load-generation.md), the README, CONTRIBUTING, the
  test inventory, and the proof index.
- [`tests/serving/test_performance_scenarios.py`](../../../tests/serving/test_performance_scenarios.py).

No chart, template, render, Terraform resource, API behaviour, recording rule, or
dashboard panel changed.

## Checks run on the change

Every command ran from the repository root in Git Bash, inside the locked environment,
after the committed record was promoted, with no cluster contacted by any of them.

```text
python -m pytest tests/serving/test_performance_scenarios.py -q          117 passed
python -m pytest tests/serving/test_llm_load.py -q                        196 passed
python -m pytest -q                                                       9012 passed, 1 failed, 30 skipped, 14 deselected
ruff format --check .                                                     395 files already formatted
ruff check .                                                              All checks passed!
python -m mypy                                                            Success: no issues found in 219 source files
python -m tools.performance_scenarios check                               descriptor validated
python -m tools.performance_scenarios verify --dir docs/proof/serving --prefix v1-s4-004-pr1-
                                                                          ok; usable=True
python -m tools.llm_load check                                            not started (offline profile validation only)
scripts/environment/performance-scenarios.sh check                        the descriptor validated
python -m tools.inference_dashboard                                       ok  29 panel(s)
git diff --check                                                          (no output)
```

The one failure was `test_no_committed_file_carries_a_personal_filesystem_path` in
`tests/security/test_security_baseline.py`. It found a home-directory path written out
as a sample in the new suite's refusal test. The samples are now assembled at run time,
and the two affected modules then passed together: 863 passed.

The environment-script safety suites, the test strategy suite, and the test inventory
suite were run after the script was registered and the documents amended, and passed.
`bash -n scripts/environment/performance-scenarios.sh` passed. `shellcheck` is not installed on this host and was not run, and no CI gate runs it over `scripts/`.

## What was not run, and why

| Not run | Why |
|---|---|
| `kind` | Not the V1 reference provider; the descriptor does not describe it and a run on it is refused |
| Two replicas of either tier | The descriptor refuses it: the forward reaches one pod, and the multi-replica profile was refused at capacity on this host in V1-S3-011-PR1 |
| A level above concurrency 4 | The committed load profile names three levels. A new level is a new profile version and a separate decision |
| Varied prompts | The profile fixes one fixture |
| A load path through the Service without a port-forward | The load tool accepts a loopback target only |
| Any saturation or degradation analysis | V1-S4-004-PR2's scope |
| A second host | None is available to this project |

## Acceptance criteria

This PR's boundary is execution and capture. The story's criteria are listed with what
this PR does for each; the analysis and publication are PR2's.

| Criterion | Status |
|---|---|
| At least baseline and higher-load scenarios are compared | **Executed, not compared.** Baseline `c1` and higher-load `c2` and `c4` ran twice with identical capture. The comparison is PR2's |
| P50/P95/P99, throughput, errors, resource use, and tokens where available | **Captured and recorded** per phase and per run; errors were zero |
| Saturation statement specific to the provider, host, model, runtime, and profile, naming the experiment boundary | **Not made here, by design.** Every identity it would need is recorded. `saturationJudged` is false |
| The report refuses portable capacity, production SLO, and universal benchmark interpretations | **Met for this record and ADR 0013.** The published report is PR2's |
| Raw evidence supports the summary | **Met, and checked.** The record regenerates exactly from the committed raw sets, samples, telemetry, windows, and environment, and every counter reconciles with the raw sets |

## Limitations

- One provider, one host, one release, one prompt, and two repetitions in one window.
  The node and its virtual machine were shared with 12 other running pods.
- Every latency includes a loopback port-forward to one API pod.
- The prompt cache serves nearly all of every prompt after the first.
- Resource samples are about 2–4 s apart and their placement is uncertain by up to
  0.9 s under load. The collector locates events to a 30-second scrape.
- The warm-up phases hold two samples each.
- The repository was not committed when the run was made. Its file digests are recorded,
  and the review changes below are listed against them.

## Authorisation

Required: **yes**. The run installed a release into a cluster the host owner owns,
loaded a real model, sent 366 real inference requests, and read the node's cgroup
counters.

Granted by: the host owner, in the session that ran it, for `docker-desktop`. The
cluster was not created, reset, or reconfigured, and no workload of another project was
touched. Each attempt's release was uninstalled; after attempt 3 the workflow found no
object with the release's instance label and an unchanged claim count. The
Terraform-owned namespace and model cache claim remain, as after every earlier run.

Sensitive values removed before committing: host name, user account, absolute
filesystem paths, the kubeconfig and its path, the API server address, node and
Service addresses, and the names of other projects' workloads. Pod names, the
namespace, and image digests inside the cluster are reproduced as emitted.
