# V1-S5-013-PR1 — a Kubernetes pod restart, run again at a named revision

Date captured: 2026-09-26

Classification: **local real evidence**, `C2`. One serving runtime pod of a real
release was deleted in Docker Desktop's Kubernetes, the Deployment controller replaced
it with a different pod, the replacement mounted the same Terraform-owned claim, the
artifact on that claim was the same file by byte count, SHA-256, inode, and
modification time, no acquisition Job ran, and a real completion came back. The
repository code that did it is named: a fresh clone of `main` at a named commit, with
nothing uncommitted before the first step or after the last. Nothing here is mock,
synthetic, or estimated.

This run exists to close release blocker `b5-pod-replacement-code-unidentified`. The
[2026-09-12 run](v1-s3-003-pr2-kubernetes-pod-restart.md) names only a branch, and the
two later recovery runs each say in their own records that they did not re-prove the
artifact's survival. That record stays exactly as it is and stays cited for what it
did. **This run does not recover what that one ran.** It is a second execution of the
same committed workflow, and it identifies its own code.

Produced by:

```text
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/kubernetes-pod-restart.sh run \
    --values <the clone's merged values file> --confirm-real-kubernetes
```

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `bcad343133ba6fddfe38832a2694e71777cdd006`, the tip of `main` when this change began, in a fresh clone of the public repository; `git status --porcelain --untracked-files=all` printed nothing before the first step and after the last |
| Provider | `docker-desktop`, the V1 reference provider |
| Kubernetes | server `v1.34.3`, one node, `desktop-control-plane` |
| Node image | `kindest/node@sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48`, Docker Desktop's choice and not an InferOps pin |
| Chart | `charts/inferops-llm` at the revision above, version label `inferops-llm-0.3.0` |
| API image | `localhost/inferops-api@sha256:6d565a391412c74a9c0eb1bf31da216b7edb739a906bbd1827ee8a45b74d9b40`, built from the clone at the revision above by `scripts/environment/api-image.sh build` and imported into the node |
| Model seed image | `localhost/inferops-model-seed@sha256:1ac37eb22072a7960c64002f13b28eaf81df091cb2d65ff8ebad066e94fb758d`, built from the clone by `scripts/environment/model-seed-image.sh build` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `Qwen3-1.7B-Q8_0.gguf`, 1 834 426 016 bytes, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Serving runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Helm, kubectl, Terraform | `v3.19.0+g3d8990f`, `v1.34.3`, `1.15.8` |
| Record the tool wrote | [`v1-s5-013-pr1-kubernetes-pod-restart.v1alpha1.json`](v1-s5-013-pr1-kubernetes-pod-restart.v1alpha1.json), committed as the tool wrote it |
| Transcripts | [the preparation](../environment/v1-s5-013-pr1-cluster-prepare-transcript.txt) — images built and imported, values merged, Terraform applied — and [this run](v1-s5-013-pr1-kubernetes-pod-restart-transcript.txt), each with the revision and the status before and after |

**The API image's source is known here.** The earlier Kubernetes runs deployed an API
image whose building source tree no record names. This one was built from the clone
at the revision above, minutes before the run, and its digest is in the preparation
transcript.

## Procedure

From the clone's root, with the clone's own locked environment first on `PATH`,
`INFEROPS_PROVIDER=docker-desktop`, and the values file the preparation merged from
`charts/inferops-llm/ci/real-values.yaml` and the two image overlays:

```text
git rev-parse HEAD && git status --porcelain --untracked-files=all
scripts/environment/kubernetes-pod-restart.sh run --values <merged values> --confirm-real-kubernetes
git rev-parse HEAD && git status --porcelain --untracked-files=all
```

## What was done

```text
terraform apply -> install -> completion -> delete one pod -> replacement -> completion -> uninstall
```

The prerequisites were applied through `scripts/environment/terraform-prerequisites.sh`,
and the workflow installed one release, deleted exactly one pod by name, read the
replacement, asked for a completion again, and uninstalled the release. Nothing else
was deleted.

## Results

| Question | Before | After |
|---|---|---|
| Serving pod | `…-runtime-56546cfdbd-htscj` | `…-runtime-56546cfdbd-tt6m6`, a different UID, same ReplicaSet |
| Release revision | 1 | 1 |
| Claim | `inferops-model-cache`, bound to `pvc-29b3d0cc-aca5-46a5-9cde-40e6aaa22a3c`, mounted read only | the same claim and volume, mounted read only |
| Artifact byte count | 1 834 426 016 | 1 834 426 016 |
| Artifact SHA-256, read inside the cluster | `sha256:061b54da…90cb1a` | the same |
| Artifact inode | 2138770 | 2138770 |
| Artifact modification time, epoch seconds | 1790388256 | 1790388256 |
| `verify-model` init container | exit 0 | exit 0 |
| Acquisition Jobs | 0 | 0 |
| Completion | HTTP 200, adapter `real`, 24 / 29 / 53 tokens | HTTP 200, adapter `real`, 24 / 29 / 53 tokens, in 3 359 ms |

The unchanged inode and modification time are the answer to the question a byte count
and a digest cannot answer: a re-acquired artifact has the same size and the same
digest, and a different inode and modification time. The modification time,
1790388256, is the release's own install-time acquisition on this run, a minute
before the pod was deleted.

| Timing, one run on one host | ms |
|---|---:|
| Deletion to the replacement reporting itself Ready | 13 281 |
| Deletion to a real completion coming back | 21 603 |

Five readiness samples were taken while the replacement came up; four read no ready
replica and one read one. **These are not a benchmark**, a restart service-level
objective, or an availability figure.

## Cleanup

`helm uninstall` left 0 objects carrying the release's instance label, and the
Terraform-owned namespace and claim were both still present, as the workflow's own
cleanup facts record. The prerequisites were left in place for the next run in this
session and removed at the end of it, recorded in
[the scoped cleanup this change ran](../environment/v1-s5-013-pr1-scoped-cleanup.md).

## Limitations

- **One provider.** `docker-desktop`, and nothing here certifies `kind`.
- **One pod, once, one replica.** The replacement window is an outage for any caller
  reaching that Service; nothing here measures it from a caller's side.
- **A deleted pod is not a lost node**, a claim that fails to reattach, or a volume
  that is corrupted.
- **The claim's storage was not tested for durability** across a host failure or a
  Docker Desktop reset.
- **It identifies its own code, not the 2026-09-12 run's.**
- The run was made by the author of this change, an AI coding agent, in the session
  that wrote this record; no second engineer has repeated it.

## Authorisation

Required: **yes**. The run applies prerequisites to and installs into a cluster the
operator owns, loads a real model, deletes a running pod, and sends real inference
requests.

Granted by: the host owner, in the session that ran it, for the `docker-desktop`
provider and not for `kind`. No workload outside the InferOps release was touched,
and Docker Desktop was never reset, disabled, or reconfigured.

Sensitive values removed before committing: the absolute path of the clone, the name
and identifier of one namespace belonging to unrelated work, and the engine's local
build-dashboard identifiers, each replaced by a marker in the transcripts. The
record the tool wrote needed nothing removed. The generated completion text was
never retained.
