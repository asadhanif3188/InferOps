# Independent review of the V2-E02A runs

Date: 2026-11-01

This page reports one independent review of the three runs of V2-E02A:
[`e02a-1`](../runs/e02a-1/result.md), [`e02a-2`](../runs/e02a-2/result.md), and
[`e02a-3`](../runs/e02a-3/result.md). One machine-readable record of each run holds the same
content with the digest of each file of that run:
[`e02a-1`](e02a-1-review-1.v1alpha1.json), [`e02a-2`](e02a-2-review-1.v1alpha1.json), and
[`e02a-3`](e02a-3-review-1.v1alpha1.json).

A review record is not evidence of a run. It states what one reviewer found in the committed files.

> [!IMPORTANT]
> **The reviewer found no material discrepancy.** With code of its own, which imports nothing from
> this repository, it computed each figure from the raw files, and each equals the run analysis.
> It judged each criterion, and on the stream reading of `E02A-AC2` each run is `PASSED`.
>
> **On the other reading no run is counted.** On the readings of a field that a later rule reads,
> each run is `INCONCLUSIVE`. The reviewer did not decide which reading the record intends. The
> repository owner approved the stream reading after the evidence was read, and the reviewer could
> not confirm that approval from a file.
>
> **The reviewer is an automated session.** It is another session of the assistant that drove the
> runs. It is not a person, and it is not outside the project.
>
> **The reviewer ran no tool of this repository.** `E02A-AC7` names two of them, so its verdict
> rests in part on the validation record.

## What was reviewed

| Item | Value |
|---|---|
| Runs | `docs/proof/experiments/v2-e02a/runs/e02a-1`, `e02a-2`, and `e02a-3` |
| Freeze record | Revision 4, content digest `3630fbf204ecc6b0d37a5a9d0ebf56caa05c0f46bbd77f9f01d8640c181c3b0e` |
| Registry | Content digest `3ca17126dba668ea60e0e181b1d19e5f4c6d68c6cefd4a7c03d8e6e7ea028984` |
| Executing commit of each run | `ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b` |
| Reviewed revision | `6abac971a0d24e7a8de27d5c0a0ec726144594d1`, the first commit of `V2-S7-002-PR1` |
| Start and end, as the reviewer reported them | 2026-11-01T07:39:00Z to 2026-11-01T07:48:11Z |
| Tree state before and after | `git status --porcelain --untracked-files=all` printed no line |
| Access | Read-only |

The brief told the reviewer to derive each figure first and to read the classification record and
the baseline report last. It named no expected finding. The brief and the report of the reviewer
are not committed, so the repository does not prove what they said.

## What the reviewer did

- It compared the digest of each file with the manifest of its run, and each of the 16 listed
  files of each run equals.
- It judged `E02A-AC1` to `E02A-AC6` from the raw files, and the part of `E02A-AC7` that files
  decide. It applied the clock policy where a verdict crosses two clocks. No verdict fell inside a
  margin in a way that changes it.
- It computed the clock bound of each run: 817 ms, 979 ms, and 675 ms.
- It computed the failed requests, each failure episode, the largest gap between two successes,
  the requests failed since the fault, the stabilized recovery, and the zero-Ready intervals.
  Each equals `analysis.json`.
- It applied the eligibility rule. The failure-episode condition holds in 3 of 3, and on the send
  instant of the first failed request in 2 of 3 with one not judged. The zero-Ready condition holds
  in 3 of 3 on the first reading and in 0 of 3 on the outer start.
- It computed the medians that the record of V2-E02B names: 2 and 4,065 ms.
- It read the executing commit with Git. The commit holds the freeze record and the two 2+1
  desired-state files with their digests.

## Findings

Four findings, none material. The session that wrote this record made each correction after the
review, and the reviewer did not read them.

| Id | What the reviewer found | Disposition |
|---|---|---|
| F1 | The report said that a failure episode starts about 30 s after the fault. That start is the completion of the first failed request. The failed requests were sent up to about 5 s after the fault, one of them 111 ms before it, and were in flight for about 26 s to 31 s. caller-failure-episode-ms does not hold that time. max-success-gap-ms holds it. | Corrected: this change, in the baseline report and in the limitations of the classification record |
| F2 | requests-failed-since-fault is 2 in each run, and the caller profile has 2 workers. The report did not state that. The reviewer marked this as an interpretation, at about 80 percent confidence, that the count carries little information for a later comparison. | Corrected: this change, as a limit of the figure. The record states the two facts and does not state the interpretation |
| F3 | A sentence of the report could be read as saying that the verdict took a figure that is not held. | Corrected: this change, in the baseline report |
| F4 | The limitation named the readyReplicas count alone. availableReplicas has the same gaps, unavailableReplicas has no value in the first or the last reading, and no statement says which fields a reading has to hold. | Corrected: this change, in the baseline report and in the limitations of the classification record, which name availableReplicas and state that the record does not say which fields |

## What the reviewer could not verify

- That python -m tools.experiment_evidence check accepts the run directory and that python -m tools.analysis_replay verify reproduces the run analysis byte for byte, which E02A-AC7 reads. The reviewer ran neither. It compared each digest and computed the figures with code of its own. The validation record states the two commands.
- That the reader accepts the caller record with the plan, which E02A-AC3 reads. The reviewer checked the structure and the header.
- That the node stayed Ready at each instant of the window. The transcript holds 21 or 22 reads with no read instant, and the Ready heartbeat times leave the first 35 s to 39 s and the last 15 s to 46 s of each window with no read.
- The identity of the other pods of the namespace. pods.jsonl counts them.
- That the repository owner approved the reading of E02A-AC2. The correction of each run states it, and no file holds it.
- Which reading of E02A-AC2 the freeze record intends.
- The memory of the host and whether paging changed a figure. The reviewer did not examine them.
- That the cluster returned the streams as committed, and the instants in them. The reviewer contacted no cluster, and one earlier session wrote each file.

## What this review does not establish

- That a person reviewed the run. The reviewer is an automated session.
- That the reviewer is independent of the assistant that drove the run. It is another session of it.
- That the claim and the register statements about this run are correct. None existed at the reviewed revision.
- That the corrections made after the review are correct. The reviewer did not read them.
- That the owner approval of the reading of E02A-AC2 was right, or that the reading is the one the record intends.
- Anything that the run itself does not establish: that one runtime replica is or is not acceptable for any service, node failure, overload, sustained capacity, production availability, a cause, or anything about another provider, node, release, or caller workload.
