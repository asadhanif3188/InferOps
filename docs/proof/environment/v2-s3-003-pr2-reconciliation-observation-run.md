# V2-S3-003-PR2: the reconciliation observation, executed on one provider

Date: 2026-10-05

This page records what the change that adds the reconciliation collection executed
on a cluster, what it observed, and what that does and does not establish. The
collection and the record are described in
[the reconciliation evidence document](../../environment/reconciliation-evidence.md).
The operation is `observe` of
[`scripts/environment/argocd-application.sh`](../../../scripts/environment/argocd-application.sh).

> [!IMPORTANT]
> **One provider, one aborted attempt, and two runs.** On the `docker-desktop`
> provider, on one host, on one day, the `observe` operation read one Argo CD
> Application while the procedure applied it, after the apply, and while the
> procedure removed it. The operation was not executed on `kind`.
>
> **Run 3 is the run of the committed procedure, tool, and driver.** An
> independent review followed the first commit of this change. It changed all
> three, so the sequence ran again. The records of run 3 are what the committed
> tool built during the run.
>
> **Attempt 1 was aborted, and it is kept.** Its preparation failed, the driver
> did not stop, and the operator then made a mistake. [The section on attempt
> 1](#attempt-1-aborted) says what the transcript holds and what it does not.
>
> **The records of attempt 1 and of run 2 were built after the fact.** The tool
> changed after each. Those five records are what the committed tool builds from
> the directories that the two executions wrote.
>
> **What Argo CD reported is recorded apart from what a caller received.** One
> caller request was sent in each run, and each was answered. A sync state and a
> health state are not a caller outcome.
>
> **No claim moves, and this is not a run of the first experiment.** This change
> adds no record to the evidence pack and registers no claim.

## Evidence levels on this page

| Evidence | Level | What executed |
|---|---|---|
| Run 2 and run 3 | `C2` | The procedure, with the real tools, on a real cluster of one provider, with a real Argo CD, the real serving runtime, and the real model |
| Attempt 1 | `C2`, for the collection only | The procedure and a real Argo CD, on the same cluster. No workload object of the release was applied, and no model was loaded |
| The records | No level of their own | The evidence tool, offline, on the directories that `observe` wrote. The tool reads files and Git objects |

The levels are defined in [the evidence levels](../../testing/evidence-levels.md).
`C2` here is bounded to this provider, this host, one replica of each tier, one
commit, and the observations listed. It is not a statement about load, duration,
or another environment.

## The environment

| Property | Value |
|---|---|
| Provider | `docker-desktop` |
| Cluster | One node, `desktop-control-plane` |
| Kubernetes | Server v1.36.1. `kubectl` client v1.36.1 |
| Argo CD | 3.5.3, installed by [the bootstrap procedure](../../environment/argocd-bootstrap.md) from the pinned manifest, SHA-256 `1a87025d8eb2eae621653fd312fb9ca51df1b4b3b6992a030e3a9ef38e45c448` |
| Repository | `HEAD` and `main` of the remote were both `40452957d8f602357ecc512dc643cb820db57202` in attempt 1 and in run 2. In run 3, `HEAD` was the first commit of this change, `4dfb69e`, with the review's changes in the working tree, and `main` of the remote was unchanged |
| API image | `localhost/inferops-api@sha256:8d2b578c4322238734890a0424a2733f6f3269a0a5d54706c8664e9f49a222cd`, built on this host and published to no registry |

Each transcript prints these values at its step 0. The owner of the host said
that the cluster was created on the day of the run, and that Docker Desktop runs
it in its `kind` mode. No transcript holds either statement.

**The bytes that ran differ between the three executions.** Each transcript
prints the SHA-256 of the procedure and of the tool at its step 0.

| File | Attempt 1 | Run 2 | Run 3, and the committed file |
|---|---|---|---|
| `argocd-application.sh` | `03951f9e…` | `03951f9e…` | `dc35b9ac0e81d0ae94456c7e50bfec7450e987a138632e90dc13d46e0830f0a3` |
| `lib.sh` | `b969003e…` | `b969003e…` | `b969003e21605e57bf4714a84cf021286846d8b3c87ac3363442027fd79a46bd` |
| `tools/reconciliation_evidence/core.py` | `b5be26a9…` | `3d69488b…` | `affa06c7d41976dc14c49cb82c3337fb4d4bdb26ad2fd7ec5de75b27fa699e11` |
| [The driver](v2-s3-003-pr2-reconciliation-observation-run-driver.txt) | Not kept | Not kept | `ed738b2f23676d76384580d304cdab5a6782453518e1040d9c21f538fc15a954` |

**No transcript prints the SHA-256 of the driver.** The value for run 3 was
computed by hand before the run, and the file was not edited afterwards. The
drivers of attempt 1 and of run 2 are not committed.
[The section on the changes](#what-changed-between-the-executions) says how
they differed.

**The Kubernetes version is not the one of the earlier runs.**
[The runs of 2026-10-04](v2-s3-002-pr2-argocd-application-run.md) used server
v1.34.3. No earlier record of this repository holds an execution of the
bootstrap procedure or of the Application procedure on v1.36.1.

**Argo CD read `main` of the remote, and this change was not in it.** The two
Application manifests were applied from the working tree. This change does not
edit them. The commit that Argo CD resolved holds none of this change.

## Attempt 1, aborted

[The transcript](v2-s3-003-pr2-reconciliation-observation-attempt-1-transcript.txt)
holds the driver's output of the attempt, from 11:13:21Z until the driver was
stopped, and the cleanup that the operator ran by hand from 11:29:31Z.

**What the transcript holds.**

1. **The refusals and the first observation ran.** `observe` refused with no
   provider and with no bound. On a cluster without Argo CD, two reads of the
   Application did not answer, and `observe` recorded both as `unanswered`. The
   record counted no settled sample.
2. **The images and the prerequisite layer were prepared.**
3. **The throwaway Helm release failed.** The preparation fills the model cache
   claim from a local seed image, through the chart's acquisition job.
   `helm install` reported `job inferops-inferops-llm-model-acquisition failed:
   BackoffLimitExceeded`, and exited 1.
4. **The driver did not stop.** Its first version ran every step whatever the
   step before returned. It uninstalled the throwaway release, installed
   Argo CD, observed that no Application existed, and started the apply.
5. **The apply did not return.** The transcript ends in the output of the
   procedure's wait, with no exit status.
6. **The cleanup.** `remove --confirm` and the bootstrap's `remove --confirm`
   both exited 0. The cluster then held the five namespaces it started with.

**What the transcript does not hold.** The operator did four things outside the
driver. No transcript of them was kept.

- **The operator read the failed pod.** `kubectl` printed these two lines for
  the pod of the acquisition job:

  ```text
  main acquire-model {"terminated":{"containerID":"containerd://6600a1c9…","exitCode":137,"finishedAt":"2026-10-05T11:20:34Z","reason":"OOMKilled","startedAt":"2026-10-05T11:20:21Z"}} {}
  acquire-model {"limits":{"cpu":"2","memory":"128Mi"},"requests":{"cpu":"100m","memory":"32Mi"}}
  ```

  They are copied from the operator's terminal. The container was stopped as
  `OOMKilled`, 13 seconds after it started, with a memory limit of 128Mi, which
  is the chart's default.
- **The operator stopped the driver with a command that did not stop the shells
  it had started.** The driver went on to step 7 and beyond.
- **The operator ran the prerequisite layer's `destroy` while the apply was
  waiting.** The operator believed that the driver had stopped, and meant to
  return the cluster to its first state. The destination namespace was deleted
  under the Application. From sample 11, at 11:27:45Z, Argo CD reported that
  the namespace was being terminated.
- **The operator stopped the driver's processes, and ran one more `observe`,**
  from 11:28:57Z to 11:29:02Z.

**What Argo CD reported in attempt 1.** The observation that ran beside the apply
wrote 23 samples of 80 before it was stopped, so
[its record](v2-s3-003-pr2-reconciliation-observation-attempt-1-apply.record.json)
is not complete: 57 samples are `not-taken`.

| Samples | Application read | What was reported |
|---|---|---|
| 1 to 5 | `absent` | Nothing. The object read returned a job and a pod of the acquisition |
| 6 to 8 | `reported` | An Application with no status. All five required fields are `missing` |
| 9 | `reported` | `OutOfSync`, `Missing`, operation `Running`. The operation revision is `missing` |
| 10 | `reported` | The same states. The operation message is "waiting for deletion of hook batch/Job/inferops-inferops-llm-model-acquisition" |
| 11 to 13 | `reported` | The operation message says that the job could not be created, because the namespace was being terminated |
| 14 to 23 | `reported` | The operation message says that the namespace was not found |

No sample of attempt 1 is settled.
[The record after the abort](v2-s3-003-pr2-reconciliation-observation-attempt-1-after-abort.record.json)
holds three samples, each `OutOfSync`, `Missing`, with a `Running` operation.

**What attempt 1 shows, and what it does not.**

- **One execution of the acquisition job failed, on this Kubernetes version, at
  the chart's memory limit.** The same preparation completed in each of the
  three runs of 2026-10-04, on v1.34.3, and it completed here in run 2 and in
  run 3 at a limit of 2Gi. The cause was not investigated. This change edits no
  chart file.
- **A job and a pod of the acquisition were in the namespace after the
  `helm uninstall`.** The object read lists them in samples 1 to 8. Argo CD then
  reported that it waited for the deletion of a job of that name.
- **No download of the model was observed.** The Application's values select
  the download source. Argo CD reported that it could not create the
  acquisition job, and no sample lists a pod other than the one of the
  throwaway release. That a download did not start is inferred from those
  reports. No network observation was made, and no job log was read.
- **A new Application has no status for a time.** For three samples the object
  existed and reported no sync state, no health state, and no operation. The
  record holds those fields as `missing`.

## Run 2

[The transcript](v2-s3-003-pr2-reconciliation-observation-run-2-transcript.txt)
holds the run, from 11:34:20Z to 11:52:08Z.

| Step | Result |
|---|---|
| `observe` with no provider, and with no bound | Refused, exit 1 |
| `observe` before Argo CD was installed | Exit 0. Two samples, both `unanswered` |
| The images, the prerequisite layer, the throwaway release, and Argo CD | Each exit 0 |
| `observe`, with no Application | Exit 0. Three samples, each `absent` |
| `observe` into the directory of that observation | Refused, exit 1, `observation-directory-exists` |
| `observe`, 80 samples, beside `apply` | Both exit 0 |
| `verify` | Exit 0 |
| `observe`, 5 samples, after the apply | Exit 0. Five samples, each settled |
| One caller request | HTTP 200 in 0.73 seconds |
| `observe`, 40 samples, beside `remove --confirm` | Both exit 0 |
| The bootstrap's `remove --confirm`, and the prerequisite layer's `destroy` | Each exit 0. The cluster then held the five namespaces it started with, and no custom resource definition |

**Beside the apply**, in
[the record](v2-s3-003-pr2-reconciliation-observation-run-2-apply.record.json),
from 11:43:43Z to 11:48:41Z:

| Samples | Application read | Sync | Health | Operation | Settled |
|---|---|---|---|---|---|
| 1 to 6 | `absent` | not collected | not collected | not collected | No |
| 7 to 12 | `reported` | `missing` | `missing` | `missing` | No |
| 13 | `reported` | `OutOfSync` | `Missing` | `Running`, with no revision | No |
| 14 to 15 | `reported` | `OutOfSync` | `Missing` | `Running`, at the resolved commit | No |
| 16 | `reported` | `OutOfSync` | `Healthy` | `Succeeded` | No |
| 17 to 21 | `reported` | `Synced` | `Progressing` | `Succeeded` | No |
| 22 to 80 | `reported` | `Synced` | `Healthy` | `Succeeded` | Yes |

59 of 80 samples are settled. Sample 22 is the first, at 11:45:07Z.

**After the apply**, in
[the record](v2-s3-003-pr2-reconciliation-observation-run-2-steady.record.json):
five samples, each settled.

**Beside the removal**, in
[the record](v2-s3-003-pr2-reconciliation-observation-run-2-remove.record.json),
from 11:49:34Z to 11:51:19Z:

| Samples | Application read | Sync | Health | Deletion timestamp | Objects read | Settled |
|---|---|---|---|---|---|---|
| 1 to 5 | `reported` | `Synced` | `Healthy` | `missing` | 26 | Yes |
| 6 to 7 | `reported` | `Synced` | `Healthy` | 11:49:48Z | 26 | No |
| 8 to 10 | `reported` | `OutOfSync` | `Progressing` | 11:49:48Z | 9, 6, and 3 | No |
| 11 to 40 | `absent` | not collected | not collected | not collected | 0 | No |

**In samples 6 and 7 the Application had a deletion timestamp, and it still
reported `Synced` and `Healthy`.** The tool that ran in run 2 counted both as
settled, and the transcript prints seven settled samples. The committed tool
reads the deletion timestamp, and the committed record counts five.

## Run 3

[The transcript](v2-s3-003-pr2-reconciliation-observation-run-3-transcript.txt)
holds the run, from 12:29:25Z to 12:50:38Z. It is the run of the committed
procedure, tool, and driver.

| Step | Result |
|---|---|
| `observe` with no provider, and with no bound | Refused, exit 1 |
| `observe` before Argo CD was installed | Exit 0. Two samples, both `unanswered` |
| The images, the prerequisite layer, the throwaway release, and Argo CD | Each exit 0. The throwaway release left no object |
| `observe`, with no Application | Exit 0. Three samples, each `absent` |
| `observe` into the directory of that observation | Refused, exit 1, `observation-directory-exists` |
| `observe`, 80 samples, beside `apply` | Both exit 0 |
| `verify` | Exit 0 |
| `observe`, 5 samples, after the apply | Exit 0. Five samples, each settled |
| One caller request | HTTP 200 in 10.85 seconds |
| `observe`, 40 samples, beside `remove --confirm` | Both exit 0 |
| The bootstrap's `remove --confirm`, and the prerequisite layer's `destroy` | Each exit 0. The cluster then held the five namespaces it started with, and no custom resource definition |

### The observation beside the apply

[The record](v2-s3-003-pr2-reconciliation-observation-run-3-apply.record.json)
holds 80 samples, from 12:40:05Z to 12:45:22Z. The interval was 3 seconds. It is
the wait after a sample. Each sample also makes two reads, and two consecutive
samples were 3 to 5 seconds apart.

| Samples | Application read | Sync | Health | Operation | Objects read | Settled |
|---|---|---|---|---|---|---|
| 1 to 5 | `absent` | not collected | not collected | not collected | 0 | No |
| 6 to 18 | `reported` | `missing` | `missing` | `missing` | 0 | No |
| 19 to 20 | `reported` | `OutOfSync` | `Missing` | `Running`, with no revision | 0, then 1 | No |
| 21 to 25 | `reported` | `OutOfSync` | `Missing` | `Running`, at the resolved commit | 3 | No |
| 26 | `reported` | `OutOfSync` | `Healthy` | `Running` | 26 | No |
| 27 to 33 | `reported` | `Synced` | `Progressing` | `Succeeded` | 26 | No |
| 34 to 80 | `reported` | `Synced` | `Healthy` | `Succeeded` | 26 | Yes |

- **47 of 80 samples are settled.** Sample 34 is the first, at 12:42:24Z.
- **Argo CD resolved `main` to one commit**,
  `40452957d8f602357ecc512dc643cb820db57202`, in every sample that reports a
  commit.
- **The record holds 22 transitions.** Nine are the change from an absent
  Application to one with no status.
- **In samples 6 to 18 the Application existed and reported nothing.** The first
  of those samples is at 12:40:28Z and the last at 12:41:14Z, which is 46
  seconds. In run 2 it was six samples and 19 seconds. The tool holds each
  required field as `missing`, and it counts none of those samples as settled.
- **Sample 26 reports `Healthy` beside `OutOfSync`,** and the next seven samples
  report `Progressing`. Run 2 has one such sample too. The observation reads no
  pod state, so it does not show whether a pod was ready. `settled` is false for
  the sample, because the sync state is not `Synced`.
- **The comparisons with the provenance found nothing.** The tool read the
  provenance at the reported commit in 62 samples, release identifier
  `eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae`.

  | Comparison | Made in | Not made in | Findings |
  |---|---|---|---|
  | The commit of the last operation and of the last history entry | 60 samples | 2, which report neither | 0 |
  | The source that the live Application declares | 62 samples | 0 | 0 |
  | The three labels of the release objects | 61 samples | 1, whose object read returned no object | 0 |

  From sample 26 the object read returned 26 objects, and each carries the three
  labels that the provenance derives.

### The observation after the apply

[The record](v2-s3-003-pr2-reconciliation-observation-run-3-steady.record.json)
holds five samples, from 12:46:33Z to 12:46:46Z. Each is `Synced`, `Healthy`,
with a `Succeeded` operation at the resolved commit, and each is settled. No
field changed between two samples.

### The caller request

One request was sent through a port-forward to the API Service, between the
observation after the apply and the observation beside the removal. No sample
was taken while it was sent, and nothing in that step reads Argo CD. The
response was HTTP 200 in 10.85 seconds, with the content "Ready.".

**This is one request in each run.** In run 2 the response took 0.73 seconds.
Nothing on this page explains the difference. No request was sent while Argo CD
reported `Progressing`, `OutOfSync`, or no status.

### The observation beside the removal

[The record](v2-s3-003-pr2-reconciliation-observation-run-3-remove.record.json)
holds 40 samples, from 12:47:26Z to 12:49:37Z.

| Samples | Application read | Sync | Health | Deletion timestamp | Objects read | Settled |
|---|---|---|---|---|---|---|
| 1 to 5 | `reported` | `Synced` | `Healthy` | `missing` | 26 | Yes |
| 6 to 8 | `reported` | `OutOfSync` | `Progressing` | 12:47:45Z | 8, 6, and 0 | No |
| 9 to 40 | `absent` | not collected | not collected | not collected | 0 | No |

- **Run 3 has no sample that reports `Synced` and `Healthy` beside a deletion
  timestamp.** Run 2 has two. Run 3 did not execute that rule of the tool on a
  sample of its own.
- **The change to an absent Application is a transition to `not-collected`.**
  No state of sample 8 is carried into sample 9.

## What changed between the executions

| After | Found | Change |
|---|---|---|
| Attempt 1 | The driver ran every step after a failed preparation | A failed preparation step ends the driver |
| Attempt 1 | The acquisition job of the throwaway release was stopped at 128Mi | The throwaway release sets that job's memory limit to 2Gi. The Application sets no such value |
| Attempt 1 | The record reported nine transitions into a sample that was never taken | No transition leads to a `not-taken` sample or from one |
| Run 2 | The first record of the observation beside the apply was 1.17 MB, because 65 samples repeated one list of 26 objects | Each distinct list of objects is held once, as `objectSets` |
| Run 2 | Samples 6 and 7 of the removal were counted as settled | A sample with a deletion timestamp is not settled |
| Run 2, by the review | See [the validation record](v2-s3-003-pr2-validation.md#what-the-review-found) | The procedure, the tool, and the driver each changed |

## The records

| Record | Samples | Built | SHA-256 |
|---|---|---|---|
| [Attempt 1, beside the apply](v2-s3-003-pr2-reconciliation-observation-attempt-1-apply.record.json) | 80, of which 57 `not-taken` | After the fact | `94ae8e46b9aad0e86c1284009838804605dedc7cdff51b04fed78aebc17554f6` |
| [Attempt 1, after the abort](v2-s3-003-pr2-reconciliation-observation-attempt-1-after-abort.record.json) | 3 | After the fact | `455814627cfa4ab0e70898142b44baecab1a1b08223aeac5f52453ffb2560382` |
| [Run 2, beside the apply](v2-s3-003-pr2-reconciliation-observation-run-2-apply.record.json) | 80 | After the fact | `aefec3ae20238c1693835012083dedc9cd64166bc9500b3853f68f6a1cf6ab51` |
| [Run 2, after the apply](v2-s3-003-pr2-reconciliation-observation-run-2-steady.record.json) | 5 | After the fact | `4f9009787514bf20d7eef6f8859c94fbcd5f79119d0405fb41c8120db9a878ed` |
| [Run 2, beside the removal](v2-s3-003-pr2-reconciliation-observation-run-2-remove.record.json) | 40 | After the fact | `040c73c1be6f1880f0eb7e9989a5522761c4c3be8b8e36173f9bf401c76a85be` |
| [Run 3, beside the apply](v2-s3-003-pr2-reconciliation-observation-run-3-apply.record.json) | 80 | In the run | `0641cc90e46c231c5a9610a8daaf852ec772d77cbe3a95b82f1f1d97bd662d7c` |
| [Run 3, after the apply](v2-s3-003-pr2-reconciliation-observation-run-3-steady.record.json) | 5 | In the run | `68d6de9164f00382dd5b204a7a999141d7e2744a17cb788dbe9731e6d810a144` |
| [Run 3, beside the removal](v2-s3-003-pr2-reconciliation-observation-run-3-remove.record.json) | 40 | In the run | `eb84be6a5bada81dc07fdc120823cac1b71eaac3b0fcd6bd77ecb92f5d14b00b` |

- **"After the fact" means built by the committed tool from the directory that
  the execution wrote.** The transcript of run 2 prints the SHA-256 and the
  summary of each first build, by the tool as it was then. Those values are not
  the ones of the committed files. The transcript of attempt 1 prints neither
  record of that attempt: the operator built both by hand.
- **The transcript of run 3 prints another SHA-256 than this table, for the same
  content.** The host wrote each record with CRLF line ends, and the transcript
  prints the SHA-256 of that file. The committed file has LF line ends. With
  the carriage returns removed, the three files that the run wrote have the
  SHA-256 values of this table. That was computed by hand.
- **The records of the short observations are not committed**: with no
  controller and with no Application, in each execution. The transcripts print
  every sample of those that the driver built.
- **A reader cannot build the records again from this repository.** The
  directories are under `.artifacts/`, and they are not committed.

## What was redacted

The three transcripts are the output of the driver, with three changes: terminal
color codes are removed, the absolute path of the repository on the host is
replaced by `<repository>`, and trailing white space is removed. Nothing else was
changed. The transcript of attempt 1 ends with the cleanup, which the operator
ran by hand.

## What this does not establish

- **That the workload serves requests.** Two requests were answered, one in each
  run, with no load and no bound.
- **Anything a sync state or a health state says about a caller.** No request
  was sent while the reported states changed.
- **How long reconciliation takes.** The times on this page are sample times of
  two runs. No bound was set, and nothing was measured against one.
- **That Argo CD applies a later commit of `main`.** One commit was resolved.
- **That self-heal reverts a change.** No manual change was made.
- **That a finding is reported on a cluster.** Every comparison on the cluster
  found the sample and the provenance equal.
- **That an unanswered read is recorded on a cluster with Argo CD installed.**
  The unanswered samples are from a cluster without the Application's resource
  type. No read failed while Argo CD ran.
- **Why the acquisition job was stopped**, or that it is stopped on every
  cluster of this version. One execution failed, and two completed at a raised
  limit.
- **That the Application's own acquisition job completes within its limit when
  it has to fill the claim.** In both runs the throwaway release had completed
  first. No claim listing and no job log was read.
- **That the committed records of attempt 1 and of run 2 are what those
  executions would have built.** The tool changed.
- **Anything about `kind`.**
- **Availability, latency, capacity, or cost.** Nothing was measured.
- **A result of the first experiment.** No run on this page is a run of it.
