# V2-S3-003-PR2: the reconciliation observation, executed on one provider

Date: 2026-10-05

This page records what the change that adds the reconciliation collection executed
on a cluster, what it observed, and what that does and does not establish. The
collection and the record are described in
[the reconciliation evidence document](../../environment/reconciliation-evidence.md).
The operation is `observe` of
[`scripts/environment/argocd-application.sh`](../../../scripts/environment/argocd-application.sh).

> [!IMPORTANT]
> **One provider, one aborted attempt, and one run.** On the `docker-desktop`
> provider, on one host, on one day, the `observe` operation read one Argo CD
> Application while the procedure applied it, after the apply, and while the
> procedure removed it. The operation was not executed on `kind`.
>
> **Attempt 1 was aborted, and it is kept.** Its preparation failed: the chart's
> model acquisition job was stopped as out of memory. The driver did not stop
> there, and the operator then made a mistake. [The section on attempt
> 1](#attempt-1-aborted) says what happened. Its transcript and two records are
> committed.
>
> **What Argo CD reported is recorded apart from what a caller received.** One
> caller request was sent in run 2, and it was answered. A sync state and a health
> state are not a caller outcome.
>
> **The records were built again after the run.** The evidence tool changed after
> run 2, because of what the two executions showed. The committed records are what
> the changed tool builds from the directories that the run wrote.
> [The section on the records](#the-records) says what changed.
>
> **No claim moves, and this is not a run of the first experiment.** This change
> adds no record to the evidence pack and registers no claim.

## Evidence levels on this page

| Evidence | Level | What executed |
|---|---|---|
| The two executions below | `C2` | The procedure, with the real tools, on a real cluster of one provider, with a real Argo CD, the real serving runtime, and the real model |
| The records | Derived from `C2` collections | The evidence tool, on the directories that `observe` wrote. The tool reads files and Git objects |

The levels are defined in [the evidence levels](../../testing/evidence-levels.md).
`C2` here is bounded to this provider, this host, one replica of each tier, one
commit, and the observations listed. It is not a statement about load, duration,
or another environment.

## The environment

| Property | Value |
|---|---|
| Provider | `docker-desktop`: Docker Desktop, engine 29.7.2, with its Kubernetes cluster in the `kind` mode |
| Cluster | One node, `desktop-control-plane`. Created on the day of the run |
| Kubernetes | Server v1.36.1, with containerd 2.3.1. `kubectl` client v1.36.1 |
| Argo CD | 3.5.3, installed by [the bootstrap procedure](../../environment/argocd-bootstrap.md) from the pinned manifest, SHA-256 `1a87025d8eb2eae621653fd312fb9ca51df1b4b3b6992a030e3a9ef38e45c448` |
| Repository | `HEAD` and `main` of the remote were both `40452957d8f602357ecc512dc643cb820db57202`. This change was in the working tree, not committed |
| Procedure | `argocd-application.sh`, SHA-256 `03951f9e0082cf35806b0e914dfe56323f8eb044c77ac1e9861acc3b6cee2140`, with `lib.sh`, SHA-256 `b969003e21605e57bf4714a84cf021286846d8b3c87ac3363442027fd79a46bd` |
| API image | `localhost/inferops-api@sha256:8d2b578c4322238734890a0424a2733f6f3269a0a5d54706c8664e9f49a222cd`, built on this host and published to no registry |
| Driver | [`v2-s3-003-pr2-reconciliation-observation-run-driver.txt`](v2-s3-003-pr2-reconciliation-observation-run-driver.txt) |

**The Kubernetes version is not the one of the earlier runs.**
[The runs of 2026-10-04](v2-s3-002-pr2-argocd-application-run.md) used server
v1.34.3. The cluster of this page is a new cluster at v1.36.1. This is the first
execution of the bootstrap procedure and of the Application procedure on that
version.

**Argo CD read `main` of the remote, and this change was not in it.** The two
Application manifests were applied from the working tree. This change does not
edit them. The commit that Argo CD resolved holds none of this change.

## Attempt 1, aborted

[The transcript](v2-s3-003-pr2-reconciliation-observation-attempt-1-transcript.txt)
holds the attempt, from 11:13:21Z, and the cleanup after it.

1. **The refusals and the first observation ran.** `observe` refused with no
   provider and with no bound. On a cluster without Argo CD, two reads of the
   Application did not answer, and `observe` recorded both as `unanswered`. The
   record counted no settled sample.
2. **The images and the prerequisite layer were prepared.**
3. **The throwaway Helm release failed.** The preparation fills the model cache
   claim from a local seed image, through the chart's acquisition job. Kubernetes
   stopped that job's container as `OOMKilled`, with exit code 137, 13 seconds
   after it started, at the chart's memory limit of 128Mi. `helm install`
   reported `BackoffLimitExceeded`.
4. **The driver did not stop.** Its first version ran every step whatever the
   step before returned. It uninstalled the throwaway release, which left the
   failed job and its pod. It installed Argo CD, observed that no Application
   existed, and started the apply over a claim that held no model.
5. **The operator made a mistake.** The operator stopped the driver with a
   command that did not stop the shells it had started. The operator then ran
   the prerequisite layer's `destroy`, to return the cluster to its first state,
   while the apply was still waiting. The destination namespace was deleted
   under the Application.
6. **The operator stopped the driver's processes, observed the state, and
   cleaned up.** `remove --confirm` and the bootstrap's `remove --confirm` both
   exited 0. The cluster then held the five namespaces it started with.

**What Argo CD reported in attempt 1.** The observation that ran beside the apply
wrote 23 samples of 80 before it was stopped, so
[its record](v2-s3-003-pr2-reconciliation-observation-attempt-1-apply.record.json)
is not complete: 57 samples are `not-taken`.

| Samples | Application read | What was reported |
|---|---|---|
| 1 to 5 | `absent` | Nothing. The object read returned the failed job and its pod |
| 6 to 8 | `reported` | An Application with no status. All five required fields are `missing` |
| 9 | `reported` | `OutOfSync`, `Missing`, operation `Running`. The operation revision is `missing` |
| 10 | `reported` | The same states. The operation message is "waiting for deletion of hook batch/Job/inferops-inferops-llm-model-acquisition" |
| 11 to 13 | `reported` | The operation message says that the job could not be created, because the namespace was being terminated |
| 14 to 23 | `reported` | The operation message says that the namespace was not found |

No sample of attempt 1 is settled.
[The record after the abort](v2-s3-003-pr2-reconciliation-observation-attempt-1-after-abort.record.json)
holds three samples, each `OutOfSync`, `Missing`, with a `Running` operation.

**What attempt 1 shows.**

- **On this Kubernetes version, the chart's acquisition job did not complete at
  its memory limit when it copied the artifact.** The same preparation completed
  in each of the three runs of 2026-10-04, on v1.34.3. One execution failed
  here. The cause was not investigated, and this change edits no chart file.
- **`helm uninstall` left the failed hook job.** Argo CD then waited for the
  deletion of a job of the same name.
- **No model was downloaded.** The Application's values select the download
  source. Argo CD reported that it could not create the acquisition job. No
  sample lists a job that Argo CD created. The absence of a download is
  inferred from those reports. No network observation was made.
- **A new Application has no status for a time.** For three samples the object
  existed and reported no sync state, no health state, and no operation. The
  record holds those fields as `missing`.

## Run 2

[The transcript](v2-s3-003-pr2-reconciliation-observation-run-2-transcript.txt)
holds the run, from 11:34:20Z to 11:52:08Z. The driver had two changes: a failed
preparation step ends it, and the throwaway Helm release sets the memory limit
of the acquisition job to 2Gi. The Application sets no such value.

| Step | Result |
|---|---|
| `observe` with no provider, and with no bound | Refused, exit 1, before any read |
| `observe` before Argo CD was installed | Exit 0. Two samples, both `unanswered` |
| The images, the prerequisite layer, the throwaway release, and Argo CD | Each exit 0. The acquisition job of the throwaway release completed at the raised limit |
| `observe`, with no Application | Exit 0. Three samples, each `absent` |
| `observe` into the directory of that observation | Refused, exit 1, `observation-directory-exists` |
| `observe`, 80 samples, beside `apply` | Both exit 0. See below |
| `verify` | Exit 0 |
| `observe`, 5 samples, after the apply | Exit 0. Five samples, each settled |
| One caller request | HTTP 200 in 0.73 seconds |
| `observe`, 40 samples, beside `remove --confirm` | Both exit 0. See below |
| The bootstrap's `remove --confirm`, and the prerequisite layer's `destroy` | Each exit 0. The cluster then held the five namespaces it started with, and no custom resource definition |

### The observation beside the apply

[The record](v2-s3-003-pr2-reconciliation-observation-run-2-apply.record.json)
holds 80 samples, from 11:43:43Z to 11:48:41Z. The interval was 3 seconds. Two
consecutive samples were 3 to 5 seconds apart, because each sample makes two
reads.

| Samples | Application read | Sync | Health | Operation | Settled |
|---|---|---|---|---|---|
| 1 to 6 | `absent` | not collected | not collected | not collected | No |
| 7 to 12 | `reported` | `missing` | `missing` | `missing` | No |
| 13 | `reported` | `OutOfSync` | `Missing` | `Running`, with no revision | No |
| 14 to 15 | `reported` | `OutOfSync` | `Missing` | `Running`, at the resolved commit | No |
| 16 | `reported` | `OutOfSync` | `Healthy` | `Succeeded` | No |
| 17 to 21 | `reported` | `Synced` | `Progressing` | `Succeeded` | No |
| 22 to 80 | `reported` | `Synced` | `Healthy` | `Succeeded` | Yes |

- **59 of 80 samples are settled.** Sample 22 is the first, at 11:45:07Z.
- **Argo CD resolved `main` to one commit**,
  `40452957d8f602357ecc512dc643cb820db57202`, in every sample that reports a
  commit.
- **The record holds 22 transitions.** Nine are the change from an absent
  Application to one with no status.
- **In samples 7 to 12 the Application existed and reported nothing.** That
  lasted about 20 seconds. The tool holds each required field as `missing`, and
  it counts none of the six samples as settled.
- **Sample 16 reports `Healthy` beside `OutOfSync`.** The next sample reports
  `Progressing`. One sample reported a healthy state before the pods of the
  release were ready. `settled` is false for it, because the sync state is not
  `Synced`.
- **The comparison with the provenance found nothing.** The tool compared 68
  samples with the release that the commit holds, release identifier
  `eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae`. It
  compared the source of the live Application in each, and the labels of the
  release objects in 67. It reports no finding. From sample 16 the object read
  returned 26 objects, and each carries the three labels that the provenance
  derives.

### The observation after the apply

[The record](v2-s3-003-pr2-reconciliation-observation-run-2-steady.record.json)
holds five samples. Each is `Synced`, `Healthy`, with a `Succeeded` operation at
the resolved commit, and each is settled. No field changed between two samples.

### The caller request

One request was sent through a port-forward to the API Service, after the
observation. Nothing in that step reads Argo CD. The response was HTTP 200 in
0.73 seconds, with the content "Ready.".

**This is one request.** It is the only caller evidence on this page. No request
was sent while Argo CD reported `Progressing`, `OutOfSync`, or no status.

### The observation beside the removal

[The record](v2-s3-003-pr2-reconciliation-observation-run-2-remove.record.json)
holds 40 samples, from 11:49:34Z to 11:51:19Z.

| Samples | Application read | Sync | Health | Deletion timestamp | Objects read | Settled |
|---|---|---|---|---|---|---|
| 1 to 5 | `reported` | `Synced` | `Healthy` | `missing` | 26 | Yes |
| 6 to 7 | `reported` | `Synced` | `Healthy` | 11:49:48Z | 26 | No |
| 8 to 10 | `reported` | `OutOfSync` | `Progressing` | 11:49:48Z | 9, 6, and 3 | No |
| 11 to 40 | `absent` | not collected | not collected | not collected | 0 | No |

- **In samples 6 and 7 the Application was being deleted, and it still reported
  `Synced` and `Healthy`.** The first build of the record counted both as
  settled. The tool now reads a deletion timestamp, and it counts neither.
- **The change to an absent Application is a transition to `not-collected`.**
  No state of sample 10 is carried into sample 11.

## The records

The evidence tool changed three times between attempt 1 and this commit. Each
change came from what the executions showed.

| Change | Why |
|---|---|
| No transition leads to a `not-taken` sample or from one | The record of attempt 1 reported nine transitions into a sample that was never taken |
| Each distinct list of objects is held once, as `objectSets` | The first record of the observation beside the apply was 1.17 MB, because 65 samples repeated one list of 26 objects |
| A sample with a deletion timestamp is not settled | Samples 6 and 7 of the removal, above |

**The committed records are what the changed tool builds from the directories
that the executions wrote.** The transcript of run 2 prints the SHA-256 of each
first build, and those are not the SHA-256 of the committed files. The summary
lines in the transcript count seven settled samples for the removal, and the
committed record counts five.

The directories are under `.artifacts/`, and they are not committed. A reader
cannot build the records again from this repository.

| Record | Samples | SHA-256 |
|---|---|---|
| [Attempt 1, beside the apply](v2-s3-003-pr2-reconciliation-observation-attempt-1-apply.record.json) | 80, of which 57 `not-taken` | `29ef1b3317b67f822d2894cdfc23b860ce945bbd7dc605a0e125abaa5edd8c01` |
| [Attempt 1, after the abort](v2-s3-003-pr2-reconciliation-observation-attempt-1-after-abort.record.json) | 3 | `c514ced65f7b8f6350c6e83ce1a357f02bb9a2f80607da7ada7f2854d93eca97` |
| [Run 2, beside the apply](v2-s3-003-pr2-reconciliation-observation-run-2-apply.record.json) | 80 | `24fa1db10bc9052a6f16b1726ded43e0fe825bdf1a68e4a55562d3b2f0bec40e` |
| [Run 2, after the apply](v2-s3-003-pr2-reconciliation-observation-run-2-steady.record.json) | 5 | `b04e4abfa84ac99598ab8f97bf3cd8119508821b9e50eef4db286d9d38e20b01` |
| [Run 2, beside the removal](v2-s3-003-pr2-reconciliation-observation-run-2-remove.record.json) | 40 | `77b7093b3cf2ba7172edce85cf1a3fe5c14bfa9fbc4e80a38e0911b52eb0ef84` |

The records of the two short observations of run 2, with no controller and with
no Application, are not committed. The transcript prints every sample of both.

## What was redacted

The two transcripts are the output of the driver, with three changes: terminal
color codes are removed, the absolute path of the repository on the host is
replaced by `<repository>`, and trailing white space is removed. Nothing else was
changed. The transcript of attempt 1 ends with the cleanup, which the operator
ran by hand.

## What this does not establish

- **That the workload serves requests.** One request was answered, once, with no
  load and no bound.
- **Anything a sync state or a health state says about a caller.** No request
  was sent while the reported states changed.
- **How long reconciliation takes.** The times on this page are sample times of
  one run. No bound was set, and nothing was measured against one.
- **That Argo CD applies a later commit of `main`.** One commit was resolved.
- **That self-heal reverts a change.** No manual change was made.
- **That a finding is reported on a cluster.** Every comparison on the cluster
  found the sample and the provenance equal.
- **That an unanswered read is recorded on a cluster with Argo CD installed.**
  The two unanswered samples are from a cluster without the Application's
  resource type. No read failed while Argo CD ran.
- **Why the acquisition job ran out of memory**, or that it does so on every
  cluster of this version. One execution failed, and one succeeded at a raised
  limit.
- **That the Application's own acquisition job downloads the model within its
  limit.** In run 2 the claim held the model already.
- **That the committed records can be rebuilt.** The directories are not
  committed.
- **Anything about `kind`.**
- **Availability, latency, capacity, or cost.** Nothing was measured.
- **A result of the first experiment.** This run is not a run of it.
