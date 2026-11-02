# The observation of the G1 switch: 2 API + 1 runtime at the merged revision

This page states a bounded, non-result observation. It is not a run of V2-E02A, it spends
no run identifier, and it states no result of any experiment.

- **What executed:** [the observation driver](../v2-s7-001-pr2-g1-observation-driver.txt),
  on the docker-desktop provider, with one node, on 2026-10-31.
- **The G1 merge:** `ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b`, the merge of pull request
  #159, which holds the G1 switch and revision 4 of the V2-E02A freeze record.
- **The owner authorization:** the record of the G1 authorization is that merge. On
  2026-10-30 the repository owner confirmed in the session of this change that the merge
  was the authorization of the switch. No tool reads this authorization.
- **The outcome:** OBSERVATION HELD in attempt `g1-2`. Attempt `g1-1` stopped in its
  preparation, and it is kept.

> **Correction, 2026-11-02.** The third item above is not a pre-merge authorization. No
> authorization of the G1 merge, `ff45093`, was given before it merged. The statement of
> 2026-10-30 came seven days after the merge. It came before the first installation of the
> release and before the first fault, and it does not change the time of the merge. See
> [the deviation page](../v2-s7-004-pr1-switch-deviations.md).

## The two attempts

| Attempt | Date | What happened | File |
|---|---|---|---|
| `g1-1` | 2026-10-30 | Stopped at the import of the model seed image, with an error from the container engine. No release was installed. | [transcript](attempt-g1-1-transcript.txt) |
| `g1-2` | 2026-10-31 | Each condition below held, and the cleanup restored the namespaces and the custom resource definitions. | [transcript](attempt-g1-2-transcript.txt) |

**What `g1-1` recorded.** The transcript states that the import failed with an error from
the container engine. The rest of this paragraph is what the operator read on the host. No
file of this directory holds those reads. Windows recorded a low virtual memory condition
at 11:18:54Z, and the log of the container engine states that its virtual machine stopped
at 11:20:14Z and that the engine restarted. Other applications held much of the memory of
the host. The two records are close in time, and this does not establish that one caused
the other. The host restarted before `g1-2`, and the owner closed applications.

## The conditions of `g1-2`

Step 10 of the transcript states each condition with the value that it read.

| Condition | Read |
|---|---|
| The remote main | `ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b` |
| The release document at that commit | `f7eaab84…` |
| The generated values at that commit | `e0b2507c…` |
| The Application | `Synced`, `Healthy`, at that commit |
| API `readyReplicas` | 2 |
| Runtime `readyReplicas` | 1 |
| API Ready endpoints | 2 |
| Runtime Ready endpoints | 1 |
| The Application verification | exit 0 |
| The release identifier | `ecc4b9cf…`, the release of revision 4 |

The [reconciliation record](attempt-g1-2-reconciliation.json) holds five samples of the
controller. Each is settled, and each states the one resolved revision above. The
[provenance record](attempt-g1-2-provenance.json) states the release at that commit.
Step 9 of the transcript lists one disruption budget, for the API tier, and none for the
runtime tier.

The state was reached 510 s after the driver started. The transcript line says "the wait
ended after 510 s", and that figure counts from the start of the driver and not from the
start of the wait.

## The host during `g1-2`

[The host memory log](attempt-g1-2-host-memory.csv) has one reading each minute. The driver
does not write it: a separate process of the operator wrote it, for the decision to start
the runs.

| Reading | Value |
|---|---:|
| Lowest available physical memory | 0.33 GB |
| Lowest free commit | 7.98 GB |
| Largest working set of the virtual machine | 6.46 GB |
| Largest page file use | 3,069 MB |

The operator read the session identifier of the container engine before and after the
attempt, and it did not change. No file of this directory holds those reads. No caller ran
in this attempt, so these figures are not those of a run.

## What this establishes, and what it does not

It establishes that, at one time, on one provider, the Application delivered the release
of the merged G1 revision, with 2 API replicas and 1 runtime replica, as its controller and
the Deployments and the endpoints reported. It is the first installation of this release.

It does not establish:

- that a caller reaches this release: no caller request was sent;
- any figure of V2-E02A: no fault was injected, and no run started;
- the behaviour of the release while a pod is lost;
- that the host has enough memory for a run: a run adds the collectors, the runner, and the
  requests;
- that the owner authorization is held by a tool: it is stated by the merge and by the owner;
- that the G1 merge was authorized before it merged (2026-11-02: it was not, and
  [the deviation page](../v2-s7-004-pr1-switch-deviations.md) states the merge).

## How the files were prepared

The transcripts are the output of the driver, with these changes alone: ANSI colour codes
and carriage returns are removed, trailing whitespace is removed, the path of the repository
is replaced by `<repository>`, and the local links of the image builds are replaced by a
fixed text. The reconciliation and provenance records are unchanged. The host memory log has
LF line ends.
