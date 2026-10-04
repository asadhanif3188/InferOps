# V2-S3-002-PR2: the Argo CD Application, executed on one provider

Date: 2026-10-04

This page records what the change that adds the Argo CD Application executed, what
it observed, and what that does and does not establish. The decision is
[ADR 0019](../../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md).
The rules are in
[the Argo CD Application document](../../environment/argocd-application.md). The
procedure is
[`scripts/environment/argocd-application.sh`](../../../scripts/environment/argocd-application.sh).

> [!IMPORTANT]
> **One provider, three runs.** On the `docker-desktop` provider, on one host, on
> one day, the procedure applied one Application and its project. Argo CD applied
> the generated release at the commit that `main` named, twice in each run. The
> procedure was not executed on `kind`.
>
> **One request returned no response.** The second caller request of run 1
> returned no HTTP response. The cause was not observed. The inferred cause is
> the driver: a port-forward that outlived the first request. Runs 2 and 3 used a
> corrected driver, and all four of their requests were answered. All three
> transcripts are kept.
>
> **Run 3 is the run of the committed procedure.** An independent review followed
> the first commit of this change. It changed the procedure, so the sequence ran
> again.
>
> **What Argo CD reported is recorded apart from what a caller received.** A sync
> state and a health state are not a caller outcome.
>
> **No claim moves, and this is not a run of the first experiment.** This change
> adds no record to the evidence pack and registers no claim. The first
> experiment's real-deployment part runs under its own frozen revision.

## Evidence levels on this page

Three kinds of evidence are on this page. They are not interchangeable.

| Evidence | Level | What executed |
|---|---|---|
| The static suite, `tests/architecture/test_argocd_application.py` | `C0` | Nothing. It reads the two manifests, the inventory, and the procedure as text |
| The executed suite, `tests/architecture/test_argocd_application_procedure.py` | `C1` | The committed procedure and manifests, with `kubectl`, `kind`, `docker`, and `sleep` replaced by recording stubs |
| The three runs below | `C2` | The procedure, with the real tools, on a real cluster of one provider, with the real serving runtime and the real model |

The levels are defined in [the evidence levels](../../testing/evidence-levels.md).
`C2` here is bounded to this provider, this host, one replica of each tier, and
the observations listed. It is not a statement about load, duration, or another
environment.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `293767b`, the merge of pull
  request 119, which added the Git desired-state layout. Pull requests 117 and
  118 added the Argo CD bootstrap decision and its procedure.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0
  with `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set
  `1d40b33f…` and the pack `652e9051…`, and `CURRENT` with the set `0271ae27…` and
  the pack `222bc533…`.
- **The freeze records.** `python -m tools.experiment_freeze --check` passed for
  both records. This change edits no file that a freeze record pins.
- **The cluster.** The `docker-desktop` cluster existed before the runs. This
  change did not create, enable, reset, reconfigure, or delete it.
- **The remote.** `git ls-remote origin refs/heads/main` returned
  `293767b6c27d858e911e5e43104ad74fbfac4b02` in each run. Argo CD read that commit.
  It holds the chart and the generated release. It does not hold this change: the
  two manifests were applied from the working tree, and Argo CD does not read
  them from Git.

## The environment of the runs

| Field | Value |
|---|---|
| Provider | `docker-desktop`, selected with `INFEROPS_PROVIDER=docker-desktop` |
| Cluster | One node |
| Server version | `v1.34.3` |
| Container runtime | `containerd://2.2.0` |
| Node image digest | `sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48` |
| `kubectl` client | `v1.34.3`, placed on `PATH` for the runs |
| Helm | `v3.19.0`, used by the preparation only |
| Argo CD | `v3.5.3`, installed by [the bootstrap](../../environment/argocd-bootstrap.md), whose procedure SHA-256 was `9f35dcfc8eb997090259418043882c28763cf199b568dfdd943ed1c0d9477c25`, unchanged by this change |
| Shell | Git Bash, on Windows 11 |
| Repository revision | Runs 1 and 2: `293767b`, with this change in the working tree and not committed. Run 3: `f2ef48f`, the first commit of this change, with the review's corrections in the working tree |
| `lib.sh` SHA-256 | `b969003e21605e57bf4714a84cf021286846d8b3c87ac3363442027fd79a46bd`, unchanged by this change |
| Project manifest SHA-256 | `34048090184f9bb3721b823266e1be3d0478b331ca4e66c15a0948a4742dfc39`, in every run |
| Application manifest SHA-256 | `42eb763ef6711ad134fdf909ae6541eab70163fa8ab11251fe066d7915d946dd`, in every run |
| API image | `localhost/inferops-api@sha256:8d2b578c4322238734890a0424a2733f6f3269a0a5d54706c8664e9f49a222cd`, built on this host and published to no registry |
| Runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model | `qwen3-1-7b-q8-0`, at revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |

The runs were made from a working tree, so a commit does not identify the bytes
that ran. Each operation printed the SHA-256 of the procedure, of `lib.sh`, and
of the two manifests. The two manifests are pinned to LF line endings, so the
digests above name the committed bytes.

Six facts on this page are not in a transcript. They were read on the host on the
day of the runs, by hand: the operating system, the shell, the Helm version, the
node count, that the host's default `kubectl` is two minors from the server, and
the reproduction described under run 1.

## The driver, and what it prepares

[`v2-s3-002-pr2-argocd-application-run-driver.txt`](v2-s3-002-pr2-argocd-application-run-driver.txt)
ran the whole sequence and printed each command with its exit status. It
prepares the cluster, runs the procedure, and returns the cluster to the state
it found. The committed driver is the one run 3 used.

**The model was not downloaded, as far as the hook's log shows.** The
Application's hand-written values select the download source. On an empty claim,
the acquisition hook would download 1.83 GB. The driver therefore fills the claim
first, from a model seed image that already existed on the host: it installs one
throwaway Helm release with the seed-image values, and uninstalls it before the
Application is applied. The claim keeps the artifact. During the first apply of
each run, the driver read the log of the hook's pod once, before Argo CD removed
the hook. In each run that read held one line:
`model artifact already present and verified; nothing to acquire`. The driver
did not read the hook of the second apply.

The throwaway release also gave the driver a real case for one refusal: `apply`
was attempted while that release was recorded, and it refused.

## Run 1: one caller request returned no response

Transcript:
[`v2-s3-002-pr2-argocd-application-run-1-transcript.txt`](v2-s3-002-pr2-argocd-application-run-1-transcript.txt).
From 06:05:58Z to 06:17:08Z. Procedure SHA-256
`cd6bba416ca676fa055db53cb5cd062e288c3c5df574aa2e7a8784577d43f39a`. No commit
holds those bytes.

**Observed.** Every step had the same result as in run 2, except step 23. The
first caller request, at step 14, returned HTTP 200 in 0.94 seconds. The second,
at step 23, after a removal and a second apply, returned no response:

```text
http_status=000 seconds=0.084046
curl: (52) Empty reply from server
[exit 52]
```

Before that request, `kubectl rollout status` had reported the API and runtime
Deployments rolled out, and the procedure had reported a succeeded sync.

**What is known about the cause.** The driver of run 1 started the port-forward
through a shell function, in the background:

```sh
k() { kubectl --context docker-desktop "$@"; }
k port-forward "service/${API_SERVICE}" 18090:8090 -n "${NAMESPACE}" >/dev/null 2>&1 &
local forward=$!
...
kill "${forward}" 2>/dev/null
```

A background job that runs a shell function is a subshell. On this host, killing
it leaves `kubectl` running. That part was reproduced after the run, by hand: a
forward started the same way was still listening on its port after the `kill`.
The reproduction is not in a transcript. Both requests of run 1 used local port
18090. The forward of step 14 pointed at a pod that the removal at step 19
deleted.

**What is inferred and not observed.** That the request of step 23 reached that
older forward. The driver discarded the output of the forward, so the transcript
does not show which process answered. The inference is consistent with the
response time and with the reproduction. It is not excluded that the request
failed for another reason.

**What run 1 therefore does not show.** That a request was answered after the
second apply. Runs 2 and 3 show that.

## Run 2: the same sequence, with the driver corrected

Transcript:
[`v2-s3-002-pr2-argocd-application-run-2-transcript.txt`](v2-s3-002-pr2-argocd-application-run-2-transcript.txt).
From 06:24:18Z to 06:34:27Z. Procedure SHA-256
`3d174660306c04003d533d6ee50ece26b79a71bd181018f031290e87c53271c1`, which is the
procedure of the first commit of this change.

Two things changed between run 1 and run 2, and neither was a response to the
content of the failed request:

- **The driver.** The port-forward is started directly and not through a shell
  function, each request takes its own local port, and the forward's output is
  printed.
- **The procedure.** `apply` reads the Application's generation and last
  comparison time before it applies, and does not accept a comparison from
  before the apply.

Every step had the result that the table under run 3 gives. Both caller requests
returned HTTP 200, in 1.52 and 0.83 seconds.

## Run 3: the same sequence, after the review's corrections

Transcript:
[`v2-s3-002-pr2-argocd-application-run-3-transcript.txt`](v2-s3-002-pr2-argocd-application-run-3-transcript.txt).
From 07:11:58Z to 07:20:35Z. Procedure SHA-256
`3dfdae335eec7d264373602f2c31f557b684d943f4ae75364f460bdb78885fe2`, which is the
procedure of the second commit of this change.
[The review](#what-the-independent-review-found) says what changed.

| Step | What ran | Result |
|---|---|---|
| 1 | `verify`, with no provider selected | Refused: `no-provider-selected`. No cluster was contacted |
| 2 | `apply`, with no digest | Refused: `api-image-digest-not-given`. No cluster was contacted |
| 3 | `apply`, before Argo CD was installed | Refused: `argocd-not-installed-by-the-bootstrap` |
| 4 to 6 | Preparation: the prerequisite layer, the throwaway Helm release, and the Argo CD bootstrap | Each exited 0 |
| 7 | `apply`, while the Helm release was recorded | Refused: `helm-release-present`. Nothing was applied |
| 8 | Preparation: uninstall the Helm release | No release object and no Helm record remained. The claim remained |
| 9 | `verify`, before any apply | Failed: the two objects do not exist |
| 10 | `remove --confirm`, before any apply | Failed: nothing is left to remove |
| 11 | `apply` | Exited 0. Argo CD reported a succeeded sync at `293767b6c27d858e911e5e43104ad74fbfac4b02`. The whole live spec of both objects was the committed one |
| 12 | `verify` | Exited 0, with the same comparison |
| 13 | The cluster, asked with plain `kubectl` | 26 objects with the release label, the claim, and no Helm record. The API and runtime Deployments rolled out. The collector Deployment was not waited for |
| 14 | One caller request | HTTP 200 in 0.93 seconds |
| 15 | A manual change: the API Deployment scaled from 1 replica to 2 | The Deployment declared 1 replica again 4 seconds after the driver read the clock |
| 16 | `apply` again | Exited 0. The generation did not change, and the current report was accepted |
| 17 | The bootstrap removal, while the Application existed | Refused: `argocd-custom-resources-present`. Nothing was deleted |
| 18 | `remove`, without `--confirm` | Stopped at the argument check. No cluster was contacted |
| 19 | `remove --confirm` | Exited 0 |
| 20 | The cluster, asked with plain `kubectl` | No Application, no project, no object with the release label. The namespace and the claim remained |
| 21 | `verify`, after the removal | Failed: the two objects do not exist |
| 22 | `apply`, after a removal | Exited 0, at the same commit |
| 23 | One caller request | HTTP 200 in 0.85 seconds |
| 24 | `remove --confirm` | Exited 0 |
| 25 | Cleanup: the bootstrap removal, and `terraform destroy` of the prerequisite layer | Each exited 0 |
| 26 | The cluster, asked with plain `kubectl` | The namespaces that existed before the run, and no custom resource definition |

### What Argo CD reported during the first apply of run 3

The procedure read the Application every 10 seconds, eight times.

| Read | Sync state | Health state | Sync operation | Last comparison with Git | Digest compared |
|---|---|---|---|---|---|
| 1 to 4 | none | none | none | none | none |
| 5 | `OutOfSync` | `Missing` | `Running`, no revision yet | 07:15:07Z | the given digest |
| 6 and 7 | `OutOfSync` | `Missing` | `Running`, at `293767b…` | 07:15:07Z | the given digest |
| 8 | `Synced` | `Progressing` | `Succeeded`, at `293767b…` | 07:16:15Z | the given digest |

The procedure returned at read 8. **The health state was `Progressing` when it
returned.** The procedure does not wait for a health state, and its result does
not depend on one. The driver then waited for the API and runtime Deployments
with `kubectl rollout status`, which reads Kubernetes and not Argo CD.

The first apply of run 2 took four reads, and that of run 1 took seven. The
time to a succeeded sync was not measured as a figure, and it differed between
runs.

### What Argo CD created

In each run, Argo CD's sync result listed 22 objects. Two were hooks in the
`PreSync` phase, the acquisition ServiceAccount and Job, both reported
`Succeeded`. Neither was in the later listing of labelled objects. Their deletion
was not observed as an event. The other 20 were the release objects: 3
Deployments, 3 Services, 3 ConfigMaps, 3 ServiceAccounts, 6 NetworkPolicies, 1
Role, and 1 RoleBinding. Kubernetes derived 3 ReplicaSets and 3 Pods from the
Deployments, which is the 26 objects of step 13.

- **Every kind is one the project admits.**
- **No pod from the chart's `helm test` hook was in the listing.**
- **No Helm release was recorded.** `kubectl get secrets -l owner=helm` returned
  nothing. `helm list` was not run.
- **The namespaces after the apply were the ones before it**, plus `argocd` and
  `inferops-release`, which the preparation created. Objects in other namespaces
  were not listed.

The three pods reported these image identities, in each run:

| Container | Image identity |
|---|---|
| `api` | `localhost/inferops-api@sha256:8d2b578c4322238734890a0424a2733f6f3269a0a5d54706c8664e9f49a222cd` |
| `runtime` | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| `collector` | `docker.io/prom/prometheus@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996` |

The API image is the digest the operator gave to `apply`. The runtime image is
the digest the generated values hold.

### The live objects, compared with the committed manifests

Run 3 is the first run in which the procedure compared the whole spec. After each
of its three applies, and in `verify`, the procedure printed that the live
project and the live Application each record the SHA-256 of the committed
manifest, and that the whole spec of each is the committed one. Argo CD had
written the Application's status by then, and its spec was unchanged.

Runs 1 and 2 compared nine fields of the Application and none of the project.

### The caller requests

Each request was one `POST /v1/chat/completions`, through a port-forward to the
API Service, with the model identifier the release serves and one short user
message. The command reads nothing from Argo CD.

| Request | After | HTTP status | Seconds | Completion tokens |
|---|---|---|---|---|
| Run 3, step 14 | The first apply | 200 | 0.93 | 3 |
| Run 3, step 23 | A removal and a second apply | 200 | 0.85 | 3 |
| Run 2, step 14 | The first apply | 200 | 1.52 | 3 |
| Run 2, step 23 | A removal and a second apply | 200 | 0.83 | 3 |
| Run 1, step 14 | The first apply | 200 | 0.94 | 3 |
| Run 1, step 23 | A removal and a second apply | none | 0.08 | none |

Each answered request returned a `chat.completion` object with the adapter kind
`real` and the model reference `qwen3-1-7b-q8-0`.

**These are six requests, one at a time.** They are not a measurement of
latency, and five answers of six are not an availability figure. A port-forward
resolves the Service and reaches a pod behind it. It does not traverse the
Service's virtual IP, and the release's network policy does not apply to it.

### The manual change

The driver read the clock, requested 2 replicas with `kubectl scale`, and read
the Deployment once a second.

| Run | Clock read | Declared 2 replicas | Declared 1 replica again | Last operation Argo CD reported afterwards |
|---|---|---|---|---|
| 1 | 06:12:00Z | 06:12:01Z | 06:12:03Z | Automated, 06:12:01Z to 06:12:02Z, `Succeeded` |
| 2 | 06:29:51Z | 06:29:52Z | 06:29:53Z | Automated, 06:29:51Z to 06:29:52Z, `Succeeded` |
| 3 | 07:16:52Z | 07:16:53Z | 07:16:56Z | Automated, 07:16:53Z to 07:16:56Z, `Succeeded` |

In run 3 the driver also read the last operation before the change: automated,
07:15:46Z to 07:16:15Z. The operation reported afterwards is therefore a later
one. Runs 1 and 2 did not read it before the change, so in those runs the
operation is attributed to the change by its time only.

**This is a check of the configured sync policy and not the drift experiment.**
It has one observation in each run, at a resolution of one second. It sent no
request during the change, applied no bound, and did not record what the pods
did.

### The removal

`remove --confirm` added the resource finalizer, deleted the Application, found
no object with the release label, deleted the project, and found the claims
unchanged. `kubectl`, asked directly afterwards, agreed: no Application, no
project, no release object, and the claim `inferops-model-cache` present. It ran
twice in each run, six times in all.

`kubectl` printed one warning at the finalizer: it prefers a finalizer name with a
path. The name is the one upstream documents for a cascade.

## What the runs establish

On `docker-desktop`, at server `v1.34.3`, on 2026-10-04:

- **Argo CD applied the generated release.** The pinned core installation, with
  one committed project and one Application, resolved `main` to a commit and
  applied the chart with the generated values of that commit, the hand-written
  values, and the digest parameter. It did so six times: twice in each run.
- **A caller request was answered after an apply**, five times of six. In runs 2
  and 3 all four were answered.
- **One manual change to the replica count was reverted**, once in each run,
  within 2 to 4 seconds of the clock read.
- **The live project and the live Application had the committed spec**, in run 3,
  after Argo CD had written to the Application.
- **The removal deleted the release objects and kept the prerequisites**, six
  times.
- **Four of the procedure's eight named refusals ran on the host**: no provider
  and no digest, which stop before any cluster call, and no Argo CD and a
  recorded Helm release, which read the cluster. Each ran once in each run.
- **The bootstrap removal refused while the Application existed**, once in each
  run, at its first check.
- **The chart's acquisition hook ran before the sync.** Its log, read once in
  each run, said that it acquired nothing.

## What the runs do not establish

- **Anything about `kind`.** A run on one provider certifies no other provider.
- **That Argo CD applies a later commit of `main`.** `main` did not move during
  any run. How long Argo CD takes to notice a commit was not measured.
- **That the workload stays up, or serves under load.** Each caller observation
  is one request.
- **That self-heal holds within a bound, or without caller impact.** No request
  was sent during the manual change.
- **That the acquisition hook downloads and verifies the model under Argo CD.**
  The claim was filled before the apply.
- **That `apply` accepts only a comparison made after it changed an existing
  Application.** No run applied a second digest. That path is executed against
  stubs.
- **That the four refusals not executed here fire on a cluster**: a destination
  that is not prepared, a foreign Argo CD custom resource, a controller with no
  ready replica, and a live Application with another destination. Of
  `argocd-not-installed-by-the-bootstrap`, only the case of no namespace ran.
- **That a live object which differs from the committed one is found on a
  cluster.** Every comparison in run 3 found them equal. The finding is executed
  against stubs.
- **That a cascade which does not finish is recoverable.** Every cascade
  finished.
- **That the request of run 1, step 23, failed because of the driver.** That is
  an inference, stated above.
- **Capacity.** Argo CD's four pods ran beside the release with no resource
  request or limit. Nothing was measured.
- **A result of the first experiment.**

## The security baseline

No row was added. One control changed, and one threat and one deferred risk
were reworded.

| Row | Before | After |
|---|---|---|
| Control | `no-argocd-custom-resource-is-committed`: an absence | `restrict-the-argocd-application-to-one-destination`: the two manifests are the only Argo CD custom resources committed, and the project admits one destination namespace, eight namespaced kinds, and no cluster-scoped kind |
| Threat `T-24`, residual risk | The one enforced control is an absence | The one enforced control restricts one Application. It does not narrow the controller. On a cluster where the Application is applied, whoever can change the followed branch changes what runs in that namespace |
| Deferred risk `DR-14` | A project that limits destinations and kinds would narrow the grant | The committed project restricts one Application and does not narrow the grant |

**The procedure's own refusals are not registered as controls.** The baseline
counts eight guards in the host scripts, and that count is unchanged. Registering
the refusals of this procedure is not done by this change.

**The project admits Role and RoleBinding.** The chart's collector needs them.
Whoever can change `main` can therefore bind a role inside the destination
namespace, on a cluster where the Application is applied. ADR 0019 D3 states it.

[The record of the bootstrap run](v2-s3-001-pr2-argocd-bootstrap-run.md) names the
control by its earlier identifier. That record is history and is not edited.

## What changed

| Area | Change |
|---|---|
| Decision | [ADR 0019](../../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md), added. Dated notes in ADR 0017 and ADR 0018. The decision-authority record and its document gain one row |
| Manifests | `infra/argocd/workloads-project.yaml` and `infra/argocd/local-docker-desktop-support-assistant.yaml`, added, pinned to LF in `.gitattributes` |
| Procedure | `scripts/environment/argocd-application.sh`, added |
| Tests | `tests/architecture/test_argocd_application.py` and `tests/architecture/test_argocd_application_procedure.py`, added. The bootstrap suite, the lifecycle-safety suite, the provider-contract suite, the desired-state suite, and the inventory suite's number-word table, changed. One comment changed in the renderer-boundary suite |
| Ownership | One owner, one lifecycle, and two rows added. Two rows reworded, and two rows gained a referrer |
| Documents | [The Argo CD Application document](../../environment/argocd-application.md), added. The bootstrap record, the desired-state document, the ownership document, the architecture index, the system architecture, the security documents, the contract documents and the binding examples' page, the renderer document, the test inventory, the proof index, the README, CONTRIBUTING, the changelog, and the page under `gitops/`, changed |
| Evidence | This page, three transcripts, and the driver |

No chart file, Terraform file, workflow, schema, or file under `src/` changed.
`lib.sh` and the bootstrap procedure did not change. `tools/gitops_desired_state`
changed in one comment, and one binding example changed in one comment.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| One Argo CD Application for the reference workload path | Reached. One Application and its project, held by a test to the one declared release |
| Sync and self-heal configured, with pruning disabled by default | Reached. Held by a test over the manifest and by the procedure over the whole live spec |
| Safety and static tests | Reached. A static suite and an executed suite against stubs |
| On a selected cluster, Argo CD reconciles generated real workload state | Reached on `docker-desktop`, for one commit of `main`. Not on `kind`. No later commit was observed |
| Argo CD sync and health are not the caller-health truth | Reached as a decision, in the procedure's output, and in the runs: the caller requests read nothing from Argo CD |
| No Argo Rollouts and no automatic rollback | Reached. A test refuses a rollout or analysis object |

The parent story's criteria:

| Criterion | Status |
|---|---|
| A reference GitOps layout exists | Met by the earlier change of this story |
| One Argo CD Application reconciles generated desired state | Met on `docker-desktop`, for one commit |
| An accepted Git revision is the promotion boundary for the proof environment | Met as a decision and a configuration. One commit was resolved and applied. A later commit was not observed. The API image digest is outside the boundary |
| Self-heal supports the drift experiment; pruning stays disabled | Met as a configuration. One manual change was reverted in each run. The drift experiment itself is not run here |
| No duplicate hand-maintained Helm values become authoritative | Met. Two tests hold that the hand-written values set nothing the generated values hold |

## Results

At the second commit of this change, with every file staged:

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 18,521 passed, 36 skipped, 14 deselected, in 25 min 9 s |
| `uv run --locked python -m pytest tests/architecture/test_argocd_application_procedure.py -q` | 95 passed, in 7 min 14 s |
| `uv run --locked python -m pytest tests/architecture/test_argocd_application.py -q` | 35 passed |
| `uv run --locked ruff check .`, `ruff format --check .`, `mypy` | Passed |
| `python -m tools.gitops_desired_state --check`, `tools.generated_release --check`, `tools.experiment_freeze --check` | Passed |
| `bash -n scripts/environment/argocd-application.sh` | Passed |
| `git diff --check` | Clean |

One earlier attempt at the lane was stopped by hand. A pattern in the executed
suite's `kubectl` stub answered the status read with the digest, so every `apply`
case ran until its 180-second limit. The pattern was made exact, and the suite
and the lane were run again. The procedure did not change.

At the first commit, every test directory passed after one number-word table was
extended to seventy-one, and the executed suite had passed in two parts, before
and after the procedure's change between run 1 and run 2.

## What the independent review found

Two reviewers read the first commit. One read the procedure, the manifests, the
suites, and the driver. The other compared every document with the transcripts.
Neither changed a file. Their findings, and what the second commit did:

| Finding | What the first commit had | Correction |
|---|---|---|
| The live project was never read | `verify` and `apply` compared nine fields of the Application and none of the project. A project edited to admit every kind passed | The procedure compares the whole spec of both live objects with the committed manifests. Run 3 executed it |
| Most of the Application's spec was not compared | A sync option, a second source, another values file, an ignored difference, or another digest passed, and the output said "the one that was decided" | The same whole-spec comparison, with the digest. Eight executed cases plant a difference |
| The recorded SHA-256 was written and never compared | `verify` passed on objects applied from other bytes | `verify` and `apply` compare the recorded SHA-256 with the committed file |
| A refusal could follow a mutation | The project was applied before the Application manifest was read | Both documents are built before the first apply. A case holds it |
| A stale report could end the wait | A comparison that started before the apply and finished after it carried a new time and the earlier digest | The wait also requires the digest that Argo CD compared and applied. A case holds it. No run applied a second digest |
| The removal cascaded without reading the live Application | A live Application with another destination would have been cascaded, and the residue question asks in one namespace | A new refusal, `live-application-differs`, before the first mutation. Four cases |
| The JSON patches were never parsed in a test | A malformed patch passed every case | The cases parse each patch and compare it whole |
| The secret-read test had a branch that could not match | It read one spelling of one word | It reads every command for the word in either number, and compares the one command exactly |
| A direct `kubectl` call was not seen | The allow-list read only calls through the wrapper | A test holds that every call goes through the wrapper |
| The summary stated the cause of the failed request as a fact | "The cause was the driver" | The cause was not observed. The inferred cause is stated as an inference, here and in the changelog |
| A wrong count of applies | "three times across two runs" | Twice in each run: four times when it was written, six with run 3 |
| A wrong count of refusals not executed | "the two refusals not executed here" omitted `destination-not-prepared` | The list is complete, and it says which case of the bootstrap refusal ran |
| Other documents described one run and one answered request | ADR 0019, the Application document, the README, the system architecture, the architecture index, the desired-state document, and the ownership document | Each states three runs, and five answered requests of six |
| Sentences that nothing installs a release from generated values | The README, the architecture index, the system architecture, three contract documents, the renderer document, and six inventory notes read as current | Each is scoped: no workflow or Helm procedure does, and one Application applied the chart with them on one provider |
| ADR 0017 and ADR 0018 status tables were not amended | D2, D5, and D9 of ADR 0017, and D3 and D8 of ADR 0018, still described the earlier state | Dated notes in each cell. R5 and R6 of ADR 0017 carry the amendment in the status column |
| "Nine decisions are accepted" | D7 is accepted for one provider only, as D2 is | Eight are accepted, and D2 and D7 are accepted for `docker-desktop` and proposed for `kind` |
| A refusal's scope was understated | `foreign-argocd-custom-resource` also applies to `verify`, and no case executed it | The table and the header say so, and a case executes it |
| The bootstrap documents said one removal refused | Each run refused once, and the cleanup removals were not counted | The documents say what each run of this procedure did |
| A security row cited a run that held no Application | The method row and its data linked the bootstrap run only | The Application run is added as evidence |
| The driver's comment contradicted its sequence | "uninstalled before Argo CD is installed" | Corrected. The driver also prints three exit statuses it discarded, and reads the last operation before the manual change |
| "Two seconds later" | Run 2 only, at a resolution of one second. Run 1 took three | The three runs are tabled, with the resolution |
| Statements not in a transcript | `helm list`, both Deployments "rolled out", the deletion of the hooks, "one operation" | Each is restated as what was read |

Not changed, and why:

- **The kinds are compared with the committed render, and not with a render of
  the Application's own values.** A chart change that adds a kind only under
  those values would pass the test and fail the sync. That failure is visible,
  and the limit is stated in the suite's inventory note.
- **The bootstrap procedure prints "no Application exists, so it reconciles
  nothing" after an install.** It does not check. The line is true after a first
  install and can be false after an install over a live installation. The
  procedure is unchanged so that its recorded runs still name its bytes.
- **No case reaches a time limit**, and the diagnostics path is not executed.
  The suite's inventory note says so.

## Gates that do not apply, and work not executed

- **`kind`.** Not executed. No release is declared for the `local-kind` binding.
- **A change of `main` while the Application was applied.** Not executed. It
  needs a merge.
- **The acquisition download under Argo CD.** Not executed. A 1.83 GB download
  was not authorized.
- **The first experiment's real-deployment part.** Not executed. Its freeze
  revision does not yet name this Application.
- **Terraform, chart, and workflow gates.** No Terraform file, chart file, or
  workflow changed. The chart suite ran in the default lane.
- **`shellcheck`.** Not installed on this host. `bash -n` passed.
- **The claim register.** No claim is added or changed.

## Privacy and publicability

- The transcripts are the driver's output with three redactions, and nothing
  else was edited: terminal colour codes were removed, the absolute path of the
  checkout was replaced with `<repository>`, and the name of one namespace that
  is not this project's was replaced.
- The request and its answer are a fixed test message and one word. No prompt or
  response of a person is recorded.
- No Secret value was read. The Helm release records were listed by name.
- The API image digest names a local build and identifies no person.
- The transcripts hold one local time in each run, printed by Helm, which shows
  the host's time zone.

## What this does not establish

- That the platform deploys workloads continuously. An operator applied the
  Application, and each run removed it.
- That a merge to `main` was reviewed, or that a later merge is applied.
- Anything about `kind`, another host, more than one replica, load, latency,
  availability, capacity, or cost.
- That the controller is limited to one namespace. The project limits one
  Application.
- Any property of the first experiment.
