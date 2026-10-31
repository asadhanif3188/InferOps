# Validation: the three runs of V2-E02A (V2-S7-001-PR2)

Status: **C2, on one provider.** This change executed the runs of V2-E02A under revision 4 of
its freeze record. Three runs are counted, and each state is `PASSED`. V2-E02A is a
characterization with validity criteria alone, so that state says that a run is valid. It
is not a reliability pass: requests failed in each run. This record does not classify the set,
and it does not decide that the baseline is eligible for the comparison with V2-E02B.

## What the change adds

- [The G1 observation](v2-s7-001-pr2-g1-observation/observation.md), with
  [its driver](v2-s7-001-pr2-g1-observation-driver.txt). It is the first evidence of the
  change, and it was committed before the first run.
- The run directories [`e02a-1`](../experiments/v2-e02a/runs/e02a-1/result.md),
  [`e02a-2`](../experiments/v2-e02a/runs/e02a-2/result.md), and
  [`e02a-3`](../experiments/v2-e02a/runs/e02a-3/result.md).
- One correction of each run: [`e02a-1`](../experiments/v2-e02a/corrections/e02a-1/correction-1.v1alpha1.json),
  [`e02a-2`](../experiments/v2-e02a/corrections/e02a-2/correction-1.v1alpha1.json), and
  [`e02a-3`](../experiments/v2-e02a/corrections/e02a-3/correction-1.v1alpha1.json).
- [The assembly script](v2-s7-001-pr2-run-assembly.txt), which computed the verdict inputs and
  wrote each run directory after the runs, and [the host memory logs](v2-s7-001-pr2-host-memory/).
- Statements in the documentation that said that no run of V2-E02A exists are updated.

The change makes no GitOps switch, registers no freeze record, and changes no frozen input. It
changes no criterion, bound, window, fault, topology, profile, or exclusion. `python -m
tools.experiment_freeze --changes` lists no moved input of revision 4.

## The prerequisites, checked before any run

| Prerequisite | How it was checked | Outcome |
|---|---|---|
| `V2-S7-001-PR1` is merged | `git merge-base --is-ancestor` | Held |
| `V2-S7-003-PR1` is merged | `git merge-base --is-ancestor` | Held, in the merge `ff45093` |
| The G1 switch carries its owner authorization | No tool reads it. The merge of pull request #159 is the record, and the repository owner confirmed that in the session of this change | Held, by the statement of the owner |
| Revision 4 is the latest revision of V2-E02A | `python -m tools.experiment_e02a plan` | Held: revision 4, `3630fbf2…` |
| The desired-state files on `main` have the digests of revision 4 | `sha256sum`, and P2 of each run | Held: `f7eaab84…` and `e0b2507c…` |
| The desired-state tool and the independent target comparison pass | `python -m tools.gitops_desired_state --check`, `python -m tools.baseline_profile --check` | Held. The check states that the desired state selects the baseline |
| The frozen inputs have not moved | `python -m tools.experiment_freeze --check` and `--changes` for revision 4 | Held: 32 records, unchanged |
| The lineage holds | `python -m tools.experiment_preregistration --check`, `python -m tools.environment_qualification --check`, `python -m tools.experiment_bounds --check` | Held |
| The live release is 2 API + 1 runtime at the merged revision | [The G1 observation](v2-s7-001-pr2-g1-observation/observation.md) | Held in attempt `g1-2`. Attempt `g1-1` stopped in its preparation, and it is kept |
| The fault is authorized | The repository owner authorized in the session: the start of Docker Desktop, one observation, and the runs until three are counted, at most six starts | Held, by the statement of the owner |

P1 and P2 of the control were also executed on the checkout in `dry-run-2`, before the first
run. It is a dry run: it issued no cluster command and spent no identifier. It stopped at P3,
because its scenario answers no cluster read.

## What executed

Each run started from a clean checkout of `main` at `ff45093` and a clean cluster, and each ran
P1 to P8, the collection, the fault, the observation, and C1 to C4. The evidence was assembled
on the branch of this change after the runs. A commit of the branch is not the executing
revision of a run.

| Run | Started | Finished | Fault | State |
|---|---|---:|---:|---|
| `e02a-1` | 13:27:58Z | 14:33:10Z | 13:41:35.149Z | `PASSED` |
| `e02a-2` | 14:35:34Z | 15:35:58Z | 14:47:01.042Z | `PASSED` |
| `e02a-3` | 15:36:41Z | 16:42:32Z | 15:47:24.552Z | `PASSED` |

Three of the six runs that one revision allows were started. None was repeated, and none was
left out. The operator read the session identifier of the container engine before each start,
and it was the same from the start of `g1-2` to the end of `e02a-3`. No committed file holds
those reads.

## The figures

| Run | Failed in the window | Caller failure episode | Largest time between two successes | Runtime at zero Ready endpoints, inner and outer | Stabilized recovery |
|---|---:|---:|---:|---:|---:|
| `e02a-1` | 2 of 365 | 4,276 ms | 29,896 ms | 17,342 ms, 26,813 ms | 96,469 ms |
| `e02a-2` | 2 of 366 | 3,682 ms | 30,427 ms | 14,837 ms, 23,792 ms | 94,752 ms |
| `e02a-3` | 2 of 342 | 4,065 ms | 29,893 ms | 14,949 ms, 23,448 ms | 96,808 ms |
| Median, as `tools.analysis_replay aggregate` states it | 2 | 4,065 ms | 29,896 ms | not an aggregate metric | 96,469 ms |

No criterion of V2-E02A compares these figures with a bound. The stabilized recovery is a rule
of the analysis, and it is not a measured recovery of the service. Each result page states the
remaining measurements of the record.

## What the review of the runs had to decide

The review of each run judged the seven validity criteria from the evidence. The assembly
script computes each input, and it ends with the reason when one does not hold, so that no page
can state a verdict for it. Three decisions need a reader's attention.

**E02A-AC2 was judged on the readings of each stream, and the owner approved that reading
after the evidence was read.** The criterion limits the time between
two consecutive readings of a stream that have a value. Each reading of the four streams
answered, and the largest time between two in any run was 5.796 s. The API omits a count of a Deployment
that is zero, so while no runtime pod is Ready, the runtime `readyReplicas` count has no value,
and the largest time between two readings with a value of that one count is more than 10 s:
25.1 s, 22.4 s, and 22.0 s in the three runs. The header of the deployments stream states that
omission, and the freeze record does not. The stream states the other fields of those readings.
On the readings of that one count each run would be `INCONCLUSIVE` for the reason
`stream-incomplete`, and none would be counted, as would each run of a one-replica release. The
record does not state which reading applies. The first draft of the pages chose the stream
reading after the evidence was read, and both independent reviewers flagged that. The repository
owner approved the stream reading on 2026-10-31, in the session of this change. No tool reads
that approval. It is stated here and in the correction of each run, and `V2-S7-002-PR1` reads
it. It changes no text of the record.

**The last completion before the window is compared under the clock policy.** In `e02a-1`
request 50 finished 38 ms before the window start, inside the margin of 818 ms, so no order of
those two instants is stated. The verdict does not need one: request 50 and the request before
it both succeeded, so the last completion before the window succeeded whichever it is. Each
page states the number of such requests.

**The model file of the replacement pod was not compared directly.** The record leaves that
comparison to the review, and the procedure read the model verification log of the first
runtime pod alone. The cluster was removed, so the digest is not available. The indirect
evidence is on each result page. This limitation stands for each run under revision 4.

## The host

The operator read the memory of the host each minute, in a process apart from the procedure.
The capacity gate does not read the host. The host has 15.7 GB of physical memory. These are
operational readings, and no criterion reads them.

| Attempt | Lowest available physical memory | Lowest free commit | Largest working set of the virtual machine | Largest page file use |
|---|---:|---:|---:|---:|
| `g1-2` | 0.33 GB | 7.98 GB | 6.46 GB | 3,069 MB |
| `e02a-1` | 0.56 GB | 7.56 GB | 7.20 GB | 3,897 MB |
| `e02a-2` | 0.68 GB | 7.52 GB | 7.24 GB | 3,597 MB |
| `e02a-3` | 0.68 GB | 7.19 GB | 7.93 GB | 4,119 MB |

As [the observation page](v2-s7-001-pr2-g1-observation/observation.md) states, the operator read
a low virtual memory condition on the host before `g1-1` stopped. After that, a run started only
with at least 9 GB of free commit,
and only after the observation held with the virtual machine up and with free commit at or
above 5 GB. The owner decided these conditions in the session. The available physical memory
was low in each run, and the page file was in use, so the host paged. This record does not
establish whether paging changed a figure of a run.

## Validation

| Command | Result |
|---|---|
| `python -m tools.experiment_evidence check` on the three run directories | ok: 16 evidence files each, 14 raw, no correction |
| `python -m tools.analysis_replay verify` on the three run directories | Each `analysis.json` replayed, with the code the same and the revision held |
| `python -m tools.analysis_replay aggregate` for four metrics | 3 counted runs, the medians above |
| `python -m tools.experiment_freeze --changes` for revision 4 | `UNCHANGED` |
| A scan of the public diff for local paths, account names, credentials, and private planning material | No finding. The first scan found one local path, which the first redaction missed, before any commit |
| `git diff --check` | No finding |
| `tools.reliability_runner` `read_record` with the plan of each run | Each caller record accepted, with the plan digest, and the target the API Service |
| `uv run --locked python -m pytest -q`, the full default lane, in a clean clone at `ee16338` | 23,508 passed, 42 skipped, 14 deselected, in 54 min 3 s |
| `ruff check .`, `ruff format --check .`, `mypy`, and `mypy --platform linux`, at `1508610` | No finding. `ee16338` changes one test module, and ruff and mypy passed on it |
| The repository listings of `tools.experiment_evidence`, `tools.analysis_replay`, and `tools.experiment_run`, at `1508610` | 5 conforming runs, 5 replayed, 5 conforming manifests, 0 refused |

## What the runs showed about the harness

These are facts about the frozen path. This change alters none of them, because each file is a
pinned input.

- **The driver and the control executed on a cluster for the first time, and each of the three
  runs reached its outcome without a change to them.**
- **The cleaning of the live port misses one form of the repository path.** Terraform prints the
  path with doubled backslashes, which `tools/experiment_e02a/ports.py` does not replace. The
  assembly script replaces it, so the committed transcripts hold no such path.
- **The procedure does not collect the model verification log of a replacement pod.** The
  section above states what follows from that.

## What is deferred

- `V2-S7-002-PR1` classifies the set of runs and decides the comparison eligibility.
- `V2-S7-003-PR2` restores the 2+2 desired state, in a second merge that the owner authorizes.
  The desired state on `main` stays at the baseline until then.
- This change registers no claim. The evidence register, the dashboards, and the public claims
  are unchanged.

## Independent review of the first commit

Two independent reviews read the commit `5c2b643`. One recomputed each verdict and figure from
the raw files. The other read the guards, the driver, and the assembly script. They confirmed
each figure of the result pages, each manifest hash, each state under the outcome rules, that no
frozen input moved, and that no local path or credential is in the diff.

| Finding | Severity | What the first draft got wrong | Disposition |
|---|---|---|---|
| Two digests of each manifest are of the wrong kind | High | The assembly script wrote the SHA-256 of the file bytes of the binding and the contract. The fields hold the digests that the release records. No check reads them | The correction of each run states the two right values |
| The state of each run depends on an unstated reading of `E02A-AC2` | High | The row stated a bare `Held`, and the caveat was further down the page | The owner approved the reading, and the correction of each run states it |
| A guard was missed | High | `test_no_run_analysis_or_procedure_exists` of the analysis records still said that no run exists, and it failed | Replaced by a guard that names the three runs |
| The result pages state that the record was accepted with the plan, and the script did not check it | High | The statement was true and unverified | `read_record` with the plan accepts each record. The correction of each run states it |
| This page said that the record states the omission of a zero count | Medium | The freeze record does not. The stream header does | Reworded |
| Host statements had no committed evidence | Medium | The pages stated them as facts, and a heading stated a cause | Marked as what the operator read. The cause is removed |
| Six living pages still said that no run exists | Medium | The first sweep missed them | Updated |
| Three wording and scope points of `E02A-AC1`, `AC5`, and `AC6` | Low | The pages did not state them | The correction of each run states them |

The full lane then found one guard that neither review found. `test_no_application_set_and_no_cluster_registration_is_committed`
failed, because each run transcript holds the Application as the cluster returned it. The guard now names
the three transcripts. It holds that each command whose output matches is a read of the verb
`application`, and it holds each such output as it holds the other evidence files.

Neither review read the commits that fix these findings. The layout check, the replay, and the full lane
ran on them. Hosted CI runs when the pull request opens, so this record does not state it.

**The assembly script and the observation driver stay as they ran**, so they remain the record of
what executed. Their known limits are these. The script writes the two digests above. It copies
files before its last checks, it does not filter the pods stream on an answered read, and it does
not itself run the layout check. Each pods reading of the three runs answered, and the layout check
ran afterwards. The driver prints its verdict before its cleanup, and the cleanup does not reach
its exit status. In attempt `g1-2` each cleanup step exited 0, and both comparisons after it
found no difference.

## What this does not establish

- That the service stayed available. Requests failed in each run.
- That one runtime replica is or is not acceptable for any service.
- Node failure, overload, sustained capacity, or production availability.
- The cause of a failure, of a gap, or of a recovery.
- That the model file of a replacement pod is the file of the record. The evidence is indirect.
- That paging on the host changed no figure.
- That the owner authorization, or the approval of the reading of `E02A-AC2`, is held by a tool.
  Each is stated by the owner.
- Anything about another provider, node, release, or caller workload.
- The classification of the set, or the eligibility for the comparison with V2-E02B.
