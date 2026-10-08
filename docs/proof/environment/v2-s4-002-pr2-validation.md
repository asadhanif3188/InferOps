# V2-S4-002-PR2 validation

Status: **one run observed two serving runtime replicas that read one verified
artifact from the one Terraform-owned claim, on the `docker-desktop` provider. The
record of that run has the result `PASSED`.** Both runtime pods ran on one node.
The run establishes nothing about the loss of that node. No storage design, chart
value, contract, binding, or Terraform file was changed, and no claim was
registered.

| Property | Value |
|---|---|
| Date | 2026-10-08 |
| Base | `4df31fd86363a6ee5b5b6a0023f3355f5c1bfc5f`, the merge of pull request #128 |
| Branch | `test/v2-s4-002-multi-runtime-model-cache` |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0`; Terraform `v1.15.8`; Docker engine `29.8.1`; `kubectl` client `v1.36.1` |
| Cluster | Docker Desktop Kubernetes, context `docker-desktop`, server `v1.36.1`, one node, default storage class `standard` |
| Evidence level | C0 for the static tests. C2 for the one run: the pinned runtime image and the pinned model ran on a real cluster |
| Claim effect | None. No claim, ledger, register row, dashboard row, or evidence-index entry was added or changed |

## What changed

- `tools/runtime_model_cache` is new. It reads one collection directory and prints
  one record. It reads files and contacts no cluster.
  [The observation page](../../environment/runtime-model-cache-observation.md)
  describes the collection, the 17 rules, the result states, and what a record
  does not establish.
- `tests/domain/test_runtime_model_cache.py` is new. It holds the tool to
  collections that the suite writes, and it builds the record of the committed run
  again from the committed collection.
- `tests/architecture/test_helm_chart.py` gained two tests on the desired-state
  render.
- The run is committed: its driver, its transcript, its collection, and its record.
- Eight pages, the two-replica contract fixture's comments, the chart's README,
  and the runtime template's comment gained a dated statement of what the run
  observed. Four index pages gained a row or a paragraph. The comment edit
  changes no rendered byte.

**Nothing that a release is derived from was edited.** The chart's templates
render the committed renders, byte for byte. The contract fixture gained two
comment lines, and `tools.gitops_desired_state --check` still exits 0: the
contract digest is computed from the parsed document.

## Decisions taken in this change

| # | Decision | Why | What it costs |
|---|---|---|---|
| 1 | The storage boundary is reused as it is. No second claim, no `ReadWriteMany`, no per-replica cache, no chart value | The pod template already mounts the Terraform-owned claim read only and verifies the artifact in each pod. The requirement names reuse | Both runtime pods must run on the node that holds the claim's volume. See [the access mode](#the-claims-access-mode-and-placement) |
| 2 | The observation is a tool and a run driver. It is not a new procedure under `scripts/environment/` | One run was needed. A later change owns endpoint collection and the experiment evidence layout | A second run needs the driver to be copied and run by hand. No script holds the target check for the collection itself: the driver names the `docker-desktop` context in each `kubectl` call, and the three procedures it calls verify the target before they write |
| 3 | The expected identity is read from committed files before any pod is read, and the collection stores it | A record must not compare the cluster with itself | A record states the identity of the tree it ran from. A later tree may declare another |
| 4 | The rules were committed before the run, in commit `c04bc776`. The run executed at that commit with a clean working tree | A criterion written after the observation is not a criterion | Three commits instead of two |
| 5 | The V1 multi-replica capacity preflight ran before the Application was applied, with its own measuring program and its own figures. No capacity gate for the V2 topology was written | It is the one accepted capacity rule for two API replicas and two runtime replicas. A test holds that its figures are this release's sums plus one small pod. Another change owns the V2 gate | The reading does not include rollout headroom or the acquisition hook's pod, and it counts a pod with no request as zero. See [the capacity reading](#the-capacity-reading) |
| 6 | Each runtime pod was sent one model listing and one completion through a port-forward to that pod | A Service cannot be asked which replica answered. The V1 multi-replica procedure states why | The two completions are not caller requests. They bypass the API and the Service |
| 7 | The mount table and the artifact's file identity were read with `kubectl exec` | The pod specification states a mode. The mount table states the mode in effect, and one inode states that the two containers see one file | `kubectl exec` is not a read request. It runs `cat` and `stat` in the runtime container |
| 8 | The collection is committed, and the record is built from it | `--check` and one test build the record again. A reader can check the record against the reads | 19 files of the collection, and the record. The pod listing holds pod addresses and container identifiers of a cluster that no longer holds them |
| 9 | No claim is registered | The contributing guide registers an executed result in a change of its own, after review | The register does not say that the model cache was observed under two replicas |

## The run

Run `run-1`, 2026-10-08, 09:52:51Z to 10:58:27Z.

| Item | Value |
|---|---|
| Executing commit | `c04bc77647fcfe15634012c688f39e95ba8d93ad`, with a clean working tree |
| Commit the controller reported | `4df31fd86363a6ee5b5b6a0023f3355f5c1bfc5f`, which `refs/heads/main` on the remote named. `git diff` between the two commits is empty for `charts`, `gitops`, and `infra/argocd` |
| Driver | [`v2-s4-002-pr2-runtime-model-cache-run-driver.txt`](v2-s4-002-pr2-runtime-model-cache-run-driver.txt), SHA-256 `6901285ac913e4d1885e240f7264e270eb49b420e7235b9c92913afb4e6413f9`. It ran from a copy in a directory that Git ignores |
| Transcript | [`v2-s4-002-pr2-runtime-model-cache-run-1-transcript.txt`](v2-s4-002-pr2-runtime-model-cache-run-1-transcript.txt) |
| Collection and record | [`v2-s4-002-pr2-runtime-model-cache-run-1/`](v2-s4-002-pr2-runtime-model-cache-run-1/record.v1alpha1.json) |
| Tool at the run | `tools/runtime_model_cache/core.py`, SHA-256 `b194252a348a19422df5a8864638bf2cf0831d415c0e2253d721234ae8a5ea24` |
| Values file of the release | SHA-256 `314a34829e7b44c62402249f1e93ba4493ec5b019ca7becdd1a5595025d6b6f9` |
| API image | `localhost/inferops-api@sha256:d3a3112a56e91812d0627115776c23b483f8141e15b6aab05e965fcf240f4413`, built at the executing commit from the build cache |
| Model seed image | `localhost/inferops-model-seed@sha256:fb68b706718132f8e580d92f5db88575d07b0ef0cefe0be873c4ef1023a00430` |
| Download | None by the preparation release: it read the artifact from the seed image. The Application's hook ran on a filled claim. Its log was not read |

**What ran, in order.** The prerequisite layer created the namespace and the claim.
One preparation Helm release of the V1 real values, with one runtime replica,
filled the claim from the seed image and was uninstalled. The bootstrap procedure
installed Argo CD `v3.5.3`. The V1 capacity preflight ran. The Application
procedure applied the project and the Application, and Argo CD synced the release
from `main`. The driver waited for the two rollouts, read the cluster, and built
the record. Then it removed the Application, Argo CD, and the prerequisite layer.

**The cluster after the run.** The namespaces and the custom resource definitions
are the ones the run found: `diff` printed nothing for either. No PersistentVolume
is left. The two images stay in the node's image store, as the seed-image
procedure states.

### The capacity reading

| Reading | Value |
|---|---|
| Engine | 12 processors, 10,430,685,184 bytes. The profile's floor is 4 and 9,126,805,504 |
| Allocatable, one schedulable node | 12,000 millicores, 10,430,685,184 bytes |
| Already requested | 950 millicores, 304,087,040 bytes |
| Uncommitted | 11,050 millicores, 10,126,598,144 bytes |
| Required by the V1 profile, with headroom | 2,810 millicores, 8,657,043,456 bytes |
| Preflight | Exit 0: `capacity      sufficient; nothing has been installed` |

The reading was taken after Argo CD was installed and before the Application was
applied. **The preflight counts requests. The pods of the Argo CD installation
state none, so the reading counts them as zero.** What they used was not read.
After the release was up, the node reported 3,250 millicores and 4,770 MiB of
requests, and 8,070 MiB of memory limits against 9,947 MiB allocatable. That is one
`kubectl describe node`, read by hand after the collection.

The V1 record of 2026-09 refused this provider for this shape, 172,765,184 bytes
short. This reading is of another day and another cluster state: the earlier one
counted workloads of other namespaces, and this cluster held none. **Neither
reading is a capacity gate for this topology.**

### What the record states

All 17 rules are `held`. The result is `PASSED`.

| Subject | Observed |
|---|---|
| Replicas | 2 serving runtime pods, `…-dk2nc` and `…-j82km`, each Ready since 10:48:11Z, each with 0 restarts |
| Placement | Both on `desktop-control-plane`, the one node |
| Runtime image | Each pod declares, and each reports, `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model argument | Each is given `/models/Qwen3-1.7B-Q8_0.gguf` and the alias `qwen3-1.7b-q8_0` |
| Claim | `inferops-model-cache`: Bound, `ReadWriteOnce`, class `standard`, managed by Terraform with the `prerequisite` lifecycle, with no Helm label or annotation. It is the one claim of the namespace. Its volume is a host path with node affinity to `desktop-control-plane` and reclaim policy `Delete` |
| Declared mode | `readOnly: true` on the volume, on the runtime mount, and on the verification mount, in each pod. The kubelet reports `readOnly: true` and `recursiveReadOnly: Disabled` for each runtime mount |
| Mode in effect | The mount table of each runtime container lists `/models` with `ro,relatime`, on device `8:48`, file system `ext4` |
| Directory | Each mount's root ends in `…_inferops-release_inferops-model-cache/Qwen--Qwen3-1.7B-GGUF/90862c4b9d2787eaed51d12237eafdfe7c5f6077`. The two roots are equal |
| File | Each runtime container sees device 2096, inode 1097160, and 1,834,426,016 bytes: one file, with the pinned byte count |
| Verification | In each pod `verify-model` exited 0, at 10:44:47Z and 10:44:49Z. Each log holds `/models/Qwen3-1.7B-Q8_0.gguf: OK` and `model artifact verified: byte count and SHA-256`. Each script holds the pinned SHA-256 `061b54da…6590cb1a` |
| Model listing | Each runtime answered 200 with the alias and the same metadata: 1,720,574,976 parameters, 1,828,474,880 bytes, vocabulary 151,936, type `Q8_0` |
| Completion | Each runtime answered 200 with 16 completion tokens and 15 prompt tokens, finish reason `length` |
| Readiness while loading | 31 samples for each pod. In 22 of them the runtime container was running and not ready, from 10:44:55Z. The first Ready sample is 10:48:10Z. The cluster's events report 19 startup-probe answers of 503 for each pod |

### What the run showed that no rule reads

**Both API pods were restarted once by their startup probe.** Each API container
started at 10:43:29Z or 10:43:30Z. The kubelet reported `Container api failed
startup probe, will be restarted` for both at 10:44:25Z, and each container ended
with exit code 137. Each container's own log shows that it began to listen at
10:44:37Z, after the kubelet's decision. The second start of each passed. In that
minute the two verification containers each read the 1.83 GB artifact, and at
10:44:51Z both runtimes began to load it. **The cause was not measured.** No
processor or disk reading was taken. The V1 records are of one API replica beside
one runtime. The preparation release of this run, with one of each, restarted no
API pod. This was read by hand between the collection and the cleanup, with read
requests, and it is in the transcript under its own heading.

**Two control-plane pods restarted during the run.** Before the run
`kube-controller-manager` and `kube-scheduler` each reported 2 restarts. After it
each reported 6, the last about 31 minutes before 10:58Z. The transcript has no
other reading of them, and the cause was not read.

**Argo CD reported the health state `Progressing` after both rollouts returned.**
The Application procedure's `verify` ran after 10:48:26Z and printed the sync state
`Synced`, the health state `Progressing`, and a last comparison at 10:46:07Z. No
later reading of that state was taken.

**The step that loads the seed image into the node ran for about 25 minutes.** The
transcript prints no time between 09:52:51Z and 10:35:27Z. The duration is from
the operator's clock and is not evidence.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| Reuse the Terraform-owned claim | Reached, and observed once: the one claim of the namespace carries the prerequisite layer's labels and no release marker, and both runtime pods mount it |
| Mount read only where supported | Reached as configuration before this change. Observed once on this provider's `standard` class: the option in effect is `ro` in each runtime container. **No write was attempted** |
| Preserve the model SHA and revision verification | Not changed. Observed once for two pods: each pod's own init container compared the pinned digest and exited 0 before its runtime started |
| Tests that both replicas use one model identity | Reached as static tests on the render, and as rules of the record |
| On a capable environment, both become Ready | Observed once: both Ready at 10:48:11Z, and each answered one completion afterwards |
| If capacity refuses, preserve the refusal | The V1 preflight did not refuse. The driver would have ended before the apply, and the tool would have given `REFUSED`. That path is held by a test, and it was not executed |

| Parent-story criterion | State after this change |
|---|---|
| The reference runtime replica count is 2 | Declared by the earlier change. Observed once here |
| Both replicas use the same pinned real runtime and model identity | Observed once on one provider: one image digest, one file, one verification per pod, one reported model |
| The runtime rollout uses `maxUnavailable` 1 and `maxSurge` 0 | Rendered by the earlier change. The live Deployment was not read for it, and **no rollout ran** |
| The runtime's readiness stays false until real inference is possible | Partly observed. Each runtime was not ready in 22 samples while it ran and answered 503, and each answered a completion after it was Ready. **No request was sent to a runtime that was not ready** |
| The V1 model-cache ownership and integrity are preserved | Observed once: Terraform's claim, no second claim, read-only mounts, and the pinned digest verified in each pod |

## Validation at the first commit

Commit `c04bc776`. These ran on the working tree that became that commit.

| Check | Result |
|---|---|
| `ruff check`, `ruff format --check` | Clean: 664 files formatted |
| `mypy` | No type error in 361 source files |
| `tests/testing`, `tests/security`, the new suite, and the chart suite | 9,396 passed, 1 skipped, in 7 minutes 2 seconds |
| `tools.runtime_model_cache --check` | Exit 0: no committed run existed |
| `git diff --check` | Clean |
| The default lane | Not run at this commit |

## Validation at the second commit

| Check | Result |
|---|---|
| `tools.runtime_model_cache --check` | Exit 0: 1 committed run, and its record is what its collection gives |
| `tools.gitops_desired_state --check`, `tools.generated_release --check` | Exit 0 for each |
| `helm template`, both committed fixtures | Each render is the committed render, after the comment edit |
| `ruff`, `mypy` | Clean |
| The default lane | Not run before this commit. See the later section of this record |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it |
| Hosted CI | Not read: no pull request existed when this record was written |

## The first experiment's freeze

This change edits two files that the freeze records of the first experiment pin:
the chart's `README.md` and `templates/runtime-deployment.yaml`. Both were already
listed as moved at the base. `tools.experiment_freeze --check` exits 0, and no
freeze record, run, or review record was edited.

## Privacy and publicability

The diff, the transcript, and the collection were read for private material.

- The transcript is redacted in two ways: terminal colour codes are removed, and
  the absolute path of the checkout, which Terraform prints twice, is written as
  `<repository>`.
- The collection holds pod addresses, a node address, container identifiers, and
  a volume path inside the engine's virtual machine. Each names an object of a
  cluster state that the cleanup removed. None is a path of the workstation.
- No response body was kept. The two completion files hold a status, a model
  name, a finish reason, and two token counts.
- No credential, secret value, cloud account identifier, or model artifact is in
  the diff.

## What this does not establish

- **Node-loss resilience.** Both runtime pods ran on the one node, and the claim's
  volume has node affinity to it. Same-node pod redundancy says nothing about the
  loss of that node.
- **That a caller is served when one runtime pod is unavailable.** No pod was
  removed. No request was sent through the API or through a Service by the
  collection.
- **Anything about a rollout.** No pod template changed.
- **That readiness is false whenever inference is impossible.** No request was sent
  to a runtime that was not ready.
- **That the cache cannot be written.** No write was attempted from a runtime
  container. The acquisition hook mounts the claim writable.
- **That the acquisition hook can mount the claim while two runtime pods hold it.**
  The hook ran before the Deployments existed. An upgrade was not run.
- **That two runtime pods fit beside two API pods without a restart.** Both API
  pods were restarted once in this run.
- **Capacity.** One reading of a V1 preflight passed on one host on one day.
- **Any performance figure.** No time in this record is a latency, a throughput,
  or a model-load measurement. Two concurrent loads were observed once and not
  measured.
- **Another provider, storage class, or node count.** The run was on Docker
  Desktop Kubernetes with one node and the `standard` class. `kind` executed
  none of it.
- **That the collection is what the cluster held.** The record is the tool's
  output for the committed files. The driver wrote those files once.
- **A second run.** One run exists. Its result was not repeated.
