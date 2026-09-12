# V1-S3-011-PR2 — a release broken on purpose, and rolled back

Date captured: 2026-09-12

Classification: **local real evidence**, redacted. Evidence class `local-real-cpu`,
certification ceiling `C2`. A real release was installed, upgraded with a
controlled change, upgraded again with a fault the cluster could not run, the
failure was detected off the workload the fault was injected into, the release was
rolled back to its last known-good revision, and a real model answered again.
Nothing here is mock, synthetic, or estimated.

This is `V1-S3-008`'s experiment, executed for the first time. Its procedure
document had said, correctly, that it was **written and never run**.

Produced by:

```text
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/helm-upgrade-rollback.sh run \
    --values <host values file> --confirm-real-kubernetes
```

## Provenance

| Input | Immutable identifier |
|---|---|
| Provider | `docker-desktop` (the V1 reference provider) |
| Cluster / context | `docker-desktop` / `docker-desktop` |
| Kubernetes | server `v1.34.3` |
| Node image | `kindest/node@sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48` — **Docker Desktop's choice, recorded and not enforced as an InferOps pin** |
| Chart | `inferops-llm-0.3.0` |
| Helm | `v3.19.0+g3d8990f` |
| kubectl | `v1.34.3` |
| Model revision | `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| Model SHA-256 | `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Serving runtime | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |

## The lifecycle, revision by revision

| Stage | Revision | Status | Outcome | Service version | Rendered artifact bytes | Release test | Ready (ms) |
|---|---:|---|---|---|---:|---|---:|
| baseline | 1 | deployed | healthy | *(unset)* | 1 834 426 016 | passed | 16 259 |
| candidate | 2 | deployed | healthy | `v1-s3-008-candidate` | 1 834 426 016 | passed | 11 123 |
| unhealthy-candidate | 3 | deployed | **failed** | `v1-s3-008-candidate` | **1** | not run | — |
| rollback | 4 | deployed | healthy | `v1-s3-008-candidate` | 1 834 426 016 | passed | 451 |

Revision 4 is a rollback to revision 2, which is why it carries the candidate's
service version: revision 2 was the **last known-good** revision, and the
controlled change that reached the workload at revision 2 is part of what a
rollback restores.

**The controlled change reached the workload.** `telemetry.serviceVersion` was set
to `v1-s3-008-candidate`, it appeared as `INFEROPS_SERVICE_VERSION` in the release's
rendered ConfigMap, and the serving pod's name changed from
`…-runtime-75d47d6578-c9b7w` to `…-runtime-699f778579-fn7hb` — a new ReplicaSet,
which is what a change reaching the pod template produces. A value that reached
neither would have produced a revision Helm recorded and the cluster never
applied, and rolling *that* back would prove nothing.

## The injected fault, and where it landed

| | |
|---|---|
| Mechanism | `model-artifact-byte-count-mismatch` |
| Injected | `model.artifact.sizeBytes=1` against a 1 834 426 016-byte artifact |
| Scoped to the workload by | `model.acquisition.enabled=false`, on the same upgrade |
| Fails in | the `verify-model` init container of `serving-runtime` |
| Candidate pod | `…-runtime-964cc8455-96gsw` |
| Pod still serving throughout | `…-runtime-699f778579-fn7hb` |

**Why the upgrade sets two values, and why that is not a weakened fault.** The
accepted fault is unchanged: the same mechanism, the same values path, the same
injected value. What execution showed is that the same byte count also renders
into the **model acquisition hook**, which runs `pre-upgrade` at weight `-5`,
before any workload object is updated. Asked to acquire a one-byte artifact the
hook fails, Helm abandons the upgrade, and no unhealthy serving pod is ever
created — so there is nothing at the workload to detect and nothing to recover.
That is exactly what the first attempt produced, and it is recorded under
[failed attempts](#failed-attempts-and-defects-execution-found) below. Not
rendering the hook for the one upgrade that carries the fault puts the fault back
where the descriptor has always said it lands. The rollback restores both values
together, because a rollback restores a revision rather than a value.

## Detection

| | |
|---|---|
| Signal | `init-container-nonzero-exit` — **decisive** |
| Read off | `serving-runtime` / `verify-model`, the workload the fault was injected into |
| Container exit code | 1, reason `Error` |
| Detected after | 6 425 ms |

A **deadline** was not accepted as a detection. `progress-deadline-exceeded` is a
statement about elapsed time rather than about health, and a deadline reached
sooner than a healthy rollout is allowed to take would be a slow start reported as
a failure. The workflow refuses that reading outright and this run did not need it.

## Rollback and recovery

| | ms |
|---|---:|
| Fault injected | 0 |
| Failure detected | 6 425 |
| Rollback started | 8 382 |
| Rollback finished | 9 894 |
| Real completion served again | 14 408 |
| **Rollback duration** | **1 512** |
| **Detection to a served completion** | **7 983** |

**Not a benchmark.** One run, one host, one moment. The recovery figure is
measured from the moment the failure was *detected* — by a script that was already
watching — to the moment a real completion came back. It is not a time-to-detect
for an operator who was not watching, and it is not an outage duration.

## What a caller saw

| | |
|---|---|
| Probe | `GET /health/ready` through the release's API Service |
| Interval | 2 000 ms |
| Probes across the failure window | 3 |
| Answered | 3 |
| Refused | 0 |
| Window | 6 143 ms |

**Every probe answered.** The failing candidate never became ready, so the
Service kept selecting the pod that was already serving, and a caller in front of
that Service saw no interruption. That is a property of a single-replica rollout
whose *new* pod fails rather than of anything resilient: had the fault made the
*running* pod unhealthy, this record would look very different, and this
experiment does not inject that fault.

`runtimeReloaded: false` in the record says the same thing from the other side —
the rollback restored the revision the serving pod was already running, so that
pod was never replaced and the runtime never reloaded the model.

## Real inference after the rollback

| | |
|---|---|
| HTTP | 200 in 2 375 ms |
| Adapter kind | `real` |
| Model | `qwen3-1-7b-q8-0` at revision `90862c4b…` |
| Runtime | `llama.cpp llama-server` at the pinned digest |
| Tokens | 23 prompt + 12 completion = 35 |
| Content | 55 characters, **not retained** |
| Token usage declared | yes |

`requestIdEchoed` and `correlationIdEchoed` are both **false** in the record. The
API does not echo those two headers back on this path. That is recorded as
observed rather than asserted, and it is not a failure of the rollback.

## Cleanup

| | |
|---|---|
| `helm uninstall` | 740 ms |
| Objects carrying the release's instance label afterwards | 0 |
| Terraform-owned namespace | present |
| Persistent volume claims before / after | 1 / 1 |

## Failed attempts, and defects execution found

Five attempts were made. Four failed, none is hidden, and each one found a defect
that no render, lint, or test could have found — which is the argument for running
a workflow that has only ever been read.

**Attempt 1 — the fault destroyed the model artifact.** The injected byte count
rendered into the model acquisition hook as well as into the serving runtime. The
hook found an artifact that did not match its pins, **deleted it**, could not
replace it, and left the Terraform-owned claim empty; the upgrade failed at the
hook, no unhealthy serving pod was ever created, and the rollback would have had
nothing to roll back to. Two fixes followed, and both stand on their own merits:
the acquisition hook now stages a replacement beside the artifact and moves it
over only once it verifies, so a failed acquisition leaves the claim exactly as it
found it; and the unhealthy-candidate upgrade does not render the hook, so the
fault reaches the workload it was designed for. *(The run also ended in a shell
parse error, which was an operator mistake — the script file was edited while bash
was still executing it — and not a defect in the workflow.)*

**Attempt 2 — a facts variable collided with a `readonly` constant.** The evidence
writer passed `INFEROPS_NAMESPACE` as a command-prefix assignment, and `lib.sh`
declares that name `readonly` for the *smoke* namespace, a different namespace
entirely. Bash refused the assignment, the whole prefix failed, and the run died
at `INFEROPS_NAMESPACE: readonly variable` **after a complete and successful
lifecycle**, with every stage recorded and no record written. The name is now
`INFEROPS_NAMESPACE_FACT`, in this workflow and in the pod-restart one, and a test
now refuses any environment script that assigns a name `lib.sh` freezes.

**Attempt 3 — the ConfigMap was read by label selector.** The release carried one
ConfigMap when this workflow was written and carries three now — the runtime
configuration, the telemetry scrape configuration, and the collector's. A selector
returns all three and the record took the first, which is the collector's and
carries none of the fields it needed. The run reached the end of a successful
rollback and then failed writing its record, reporting only that
`release.profile` was not a string. Both reads now name the ConfigMap the
descriptor names.

**Attempt 4 — two defects, one after the other.** The impact prober sampled every
5 000 ms and the injected fault is detected in about 7 000 ms, so only two probes
fitted into a window the descriptor requires three across. The interval is now
2 000 ms: the requirement of at least three probes is unchanged, and what changed
is the sampling rate that makes it reachable, which is more evidence rather than
less. Then the residue check — asked once, the instant `helm uninstall --wait`
returned — reported two terminating pods as residue. `--wait` waits for the
objects Helm deleted itself; a Deployment's pods are removed afterwards by the
garbage collector, on the controller manager's schedule. Both certification
scripts had already been fixed for exactly this during `V1-S3-011-PR1`; this one
had never been run, so it had never been fixed. It now asks repeatedly inside the
uninstall budget, and the objects were gone moments later.

**Attempt 5 — passed**, and is the run this record describes.

## Limitations

- **One provider.** `docker-desktop`. Nothing here certifies `kind`.
- **One host, one moment, one replica of each tier.** No throughput, latency,
  capacity, or concurrency figure is published from this record.
- **One injected fault.** A byte count the mounted artifact cannot match.
  Detecting it says nothing about faults this experiment does not inject —
  including a runtime that starts and answers wrongly.
- **The rollback restores a revision this experiment created minutes earlier on
  the same cluster.** Nothing here says anything about rolling back across a
  chart version, a schema change, or a persisted-state migration.
- **No load.** The impact record is one readiness probe at a fixed interval
  through one forward. It bounds what a single caller saw and measures no
  throughput, no latency distribution, and no in-flight request.
- **No GitOps controller, no progressive delivery, no automated rollback
  trigger.** Detection and rollback were both performed by the operating script,
  which a human started.

## Authorisation

Required: **yes**. The run installs into a cluster the operator owns, loads a real
model, deliberately breaks a candidate, rolls it back, and sends a real inference
request.

Granted by: the host owner, in the session that ran it, for the `docker-desktop`
provider specifically. No workload outside the InferOps release was touched, and
Docker Desktop was never reset, disabled, or reconfigured.

Sensitive values removed before committing: host name, user account, absolute
filesystem paths, the operator's kubeconfig and its path, the API server address,
and any certificate, key, or token. The generated completion text was never
retained by the workflow and does not appear here.
