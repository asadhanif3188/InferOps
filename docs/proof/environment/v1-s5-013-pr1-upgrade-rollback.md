# V1-S5-013-PR1 — a release broken on purpose and rolled back, run again at a named revision

Date captured: 2026-09-26

Classification: **local real evidence**, `C2`. A real release was installed, upgraded
with a controlled change, upgraded again with a fault the cluster could not run, the
failure was detected off the workload the fault was injected into, the release was
rolled back to its last known-good revision, and a real model answered again. The
repository code that did it is named: a fresh clone of `main` at a named commit, with
nothing uncommitted before the first step or after the last. Nothing here is mock,
synthetic, or estimated.

This run exists to close release blocker `b4-upgrade-rollback-code-unidentified`. The
[2026-09-12 run](v1-s3-011-pr2-upgrade-rollback.md) names no revision of this
repository, and its chart and workflow are identified only by a version label ten
chart states have carried. That record stays exactly as it is and stays cited for what
it did. **This run does not recover what that one ran.** It is a second execution of
the same committed workflow, and it identifies its own code.

Produced by:

```text
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/helm-upgrade-rollback.sh run \
    --values <the clone's merged values file> --confirm-real-kubernetes
```

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `bcad343133ba6fddfe38832a2694e71777cdd006`, the tip of `main` when this change began, in a fresh clone of the public repository; `git status --porcelain --untracked-files=all` printed nothing before the first step and after the last |
| Provider | `docker-desktop`, the V1 reference provider |
| Kubernetes | server `v1.34.3`, one node |
| Node image | `kindest/node@sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48`, Docker Desktop's choice and not an InferOps pin |
| Chart and workflow | `charts/inferops-llm`, `scripts/environment/helm-upgrade-rollback.sh`, and `tools/helm_upgrade_rollback`, all at the revision above; chart version label `inferops-llm-0.3.0` |
| API image | `localhost/inferops-api@sha256:6d565a391412c74a9c0eb1bf31da216b7edb739a906bbd1827ee8a45b74d9b40`, built from the clone at the revision above |
| Model seed image | `localhost/inferops-model-seed@sha256:1ac37eb22072a7960c64002f13b28eaf81df091cb2d65ff8ebad066e94fb758d`, built from the clone |
| Model | revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Serving runtime | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Helm, kubectl | `v3.19.0+g3d8990f`, `v1.34.3` |
| Record the tool wrote | [`v1-s5-013-pr1-upgrade-rollback.v1alpha1.json`](v1-s5-013-pr1-upgrade-rollback.v1alpha1.json), committed as the tool wrote it |
| Transcripts | [the preparation](v1-s5-013-pr1-cluster-prepare-transcript.txt) and [this run](v1-s5-013-pr1-upgrade-rollback-transcript.txt), each with the revision and the status before and after |

## Procedure

From the clone's root, with the clone's own locked environment first on `PATH`,
`INFEROPS_PROVIDER=docker-desktop`, and the values file the preparation merged from
`charts/inferops-llm/ci/real-values.yaml` and the two image overlays:

```text
git rev-parse HEAD && git status --porcelain --untracked-files=all
scripts/environment/helm-upgrade-rollback.sh run --values <merged values> --confirm-real-kubernetes
git rev-parse HEAD && git status --porcelain --untracked-files=all
```

## The lifecycle, revision by revision

| Stage | Revision | Outcome | Service version | Rendered artifact bytes | Release test | Ready (ms) |
|---|---:|---|---|---:|---|---:|
| baseline | 1 | healthy | *(unset)* | 1 834 426 016 | passed | 16 400 |
| candidate | 2 | healthy | `v1-s3-008-candidate` | 1 834 426 016 | passed | 20 646 |
| unhealthy-candidate | 3 | **failed** | `v1-s3-008-candidate` | **1** | not run | — |
| rollback | 4 | healthy | `v1-s3-008-candidate` | 1 834 426 016 | passed | 776 |

Revision 4 is a rollback to revision 2, the last known-good revision, which is why it
carries the candidate's service version. The controlled change was
`telemetry.serviceVersion`, read back from the release's ConfigMap as
`INFEROPS_SERVICE_VERSION`.

## The fault, detection, and recovery

The fault was `model.artifact.sizeBytes=1`, aimed at the serving runtime with the
acquisition hook left out of that one upgrade, so the hook could not act on it.

| | |
|---|---|
| Signal | `init-container-nonzero-exit` on the serving runtime's `verify-model` container, exit 1, reason `Error` |
| Fault to detection | **6 949 ms** |
| Rollback | **1 986 ms** |
| Detection to a real completion | **11 053 ms**, HTTP 200, adapter `real`, 23 / 12 / 35 tokens, the completion itself 2 672 ms |
| Readiness probes in the failure window | 4 of 4 answered, over 8 267 ms, because the failing candidate never became ready |
| Runtime reloaded by the rollback | no |

Detection and rollback were both performed by the operating script, which the
operator started; there is no automated trigger.

## Cleanup

`helm uninstall` took 1 466 ms and left 0 objects carrying the release's instance
label. The Terraform-owned namespace was present afterwards, and the claim count was
1 before and 1 after. The prerequisites were removed at the end of the session,
recorded in [the scoped cleanup this change ran](v1-s5-013-pr1-scoped-cleanup.md).

## Limitations

- **One provider.** `docker-desktop`. Nothing here certifies `kind`.
- **One host, one moment, one replica of each tier, one injected fault.** No
  throughput, latency, capacity, or concurrency figure is published from it, and it
  says nothing about faults it does not inject, including a runtime that starts and
  answers wrongly.
- **The rollback restores a revision created minutes earlier on the same cluster.**
  Nothing here is about rolling back across a chart version, a schema change, or a
  persisted-state migration.
- **The three timings are one run's.** The 2026-09-12 run measured 6 425, 1 512, and
  7 983 ms for the same three intervals on code nothing identifies. The two are not a
  trend, a spread, or a service-level objective.
- **It identifies its own code, not the 2026-09-12 run's.**
- The run was made by the author of this change, an AI coding agent, in the session
  that wrote this record; no second engineer has repeated it.

## Authorisation

Required: **yes**. The run installs into a cluster the operator owns, loads a real
model, deliberately breaks a candidate, rolls it back, and sends a real inference
request.

Granted by: the host owner, in the session that ran it, for the `docker-desktop`
provider and not for `kind`. No workload outside the InferOps release was touched,
and Docker Desktop was never reset, disabled, or reconfigured.

Sensitive values removed before committing: the absolute path of the clone, the name
and identifier of one namespace belonging to unrelated work, and the engine's local
build-dashboard identifiers, each replaced by a marker in the transcripts. The
record the tool wrote needed nothing removed. The generated completion text was
never retained.
