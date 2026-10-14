# V2-S5-006-PR1 validation: bounded Sprint 5 integration validation

Status: **two attempts executed on the docker-desktop provider and kept. The first
FAILED, the second PASSED. Neither is a run of E02, E03, E04, E05, or E06, no figure of
either is compared with a bound, and no claim is registered.** The intended level of
both attempts is C2: a real cluster, the real runtime, and the real model, on one
provider and one node. The change also gives each run of the reliability runner its
own network policy, which the first attempt showed is needed on that cluster.

| Property | Value |
|---|---|
| Branch | `test/v2-s5-006-bounded-integration-capture` |
| Base | `2d43331dd14f360c0b7eb4ddd950a42251bc5f8e`, the merge of `V2-S5-007-PR1`, which holds `V2-S5-005-PR1` |
| Freeze records | [revision 1](../experiments/v2-s5-integration/freeze-r1.v1alpha1.json), [revision 2](../experiments/v2-s5-integration/freeze-r2.v1alpha1.json) |
| Driver | [`procedure/run-driver.txt`](../experiments/v2-s5-integration/procedure/run-driver.txt), a pinned input of both revisions |
| Attempts | [`integration-1`](../experiments/v2-s5-integration/runs/integration-1/result.md), FAILED; [`integration-2`](../experiments/v2-s5-integration/runs/integration-2/result.md), PASSED |
| Provider | `docker-desktop`, Kubernetes `v1.36.1`, one node, `kindest/kindnetd:v20260528-9350166c` |
| Release | `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`, delivered by the Application from `main` at `2d43331` |

## What the Sprint 5 review asked for

The first Sprint 5 collective review found that the sprint required a bounded
integration capture and evidence that the runner survives the replacement of a pod,
and that no merged change held either: the collector changes and the runner change
each said that no cluster was read. It asked for one bounded procedure on the
selected local target that shows the in-cluster caller through the API Service, the
infrastructure, Argo CD, telemetry, and operator streams, their UTC clock limits,
the layout check, the analysis replay, the cleanup, and the runner's continuity
across one individually scoped API or runtime pod replacement. It asked that a
network obstruction be resolved inside Sprint 5, by a narrow allowance for the
experiment caller with lifecycle and cleanup controls, and not by disabling the
default deny or by giving the caller the labels of a serving pod.

## The sequence

The order matters, because the freeze records are only worth something when they
precede what they govern. Each commit below was made before the step after it.

1. **The release was prepared** with the phase `up` of a draft of the driver, run
   from outside the tree at `2d43331`, from 08:35:47Z to 08:48:24Z: two capacity
   readings, both ACCEPTED; the API image built at that commit and loaded; the model
   cache claim filled from the local seed image by one preparation Helm release, then
   removed; Argo CD installed by its bootstrap procedure; the Application applied. The
   Application reported `Synced` and `Healthy` at `2d43331`, with two API pods, two
   runtime pods, and the telemetry collector Running.
   [Transcript](../experiments/v2-s5-integration/preparation/up-s5i-1-transcript.txt).
   An earlier phase `up` under the run name `run-1` refused at its first capacity
   reading, because a collection of that name existed on the host from an earlier
   change, and installed nothing:
   [transcript](../experiments/v2-s5-integration/preparation/up-run-1-refused-transcript.txt).
   [The draft driver](../experiments/v2-s5-integration/preparation/draft-driver.txt)
   is committed; its SHA-256 is the one the transcripts print, and its function `up`
   and the helpers that it calls are byte for byte those of the committed driver.
2. **Commit `7f150c2`: revision 1, before any attempt.** One part, seven criteria
   (`S5I-AC1` to `S5I-AC7`), 202 pinned inputs computed by the freeze tool's own
   `material_files`. An independent review of its first draft, before it reached the
   branch and before any attempt, found two high and five medium items; each is
   listed [below](#what-the-pre-run-reviews-found).
3. **Attempt `integration-1`**, from 08:57:57Z to 09:09:01Z, at `7f150c2`. FAILED on
   `S5I-AC2`. Every other criterion held.
4. **Commit `7089a53`: attempt 1 kept, the runner given its own network policy, and
   revision 2.** The run directory of attempt 1 was assembled and its analysis bound
   at a clean checkout of `7f150c2`. Revision 2 classifies four moved inputs, two of
   them material. A pre-run security review of the network policy found no critical
   or high item.
5. **Attempt `integration-2`**, from 10:16:23Z to 10:30:34Z, at `7089a53`. PASSED.
6. **The release was removed** with the phase `down`, from 10:31:59Z to 10:33:33Z.
   The namespaces and the custom resource definitions of the cluster then equal those
   read before the phase `up`, and no persistent volume is left.
   [Transcript](../experiments/v2-s5-integration/preparation/down-s5i-1-transcript.txt).
7. **This commit**: the run directory of attempt 2, the preparation transcripts, and
   the pages that said that no run directory of the layout exists.

## The two attempts

| | `integration-1` | `integration-2` |
|---|---|---|
| Revision, commit | 1, `7f150c2` | 2, `7089a53` |
| Caller | 6 requests, each `timeout`; end state `duration` | 98 requests, each `success`; end state `duration` |
| Deleted API pod | `inferops-inferops-llm-c66d85b99-p72ls` | `inferops-inferops-llm-c66d85b99-27s46` |
| Runner pod | one UID, 0 restarts, `Succeeded` | one UID, 0 restarts, `Succeeded` |
| Timeline streams | 4 × 200 readings, all answered | 4 × 200 readings, all answered |
| Telemetry | 288 query reads, all answered: 216 series, 72 no series | 288 query reads, all answered: 249 series, 39 no series |
| Event log | 1 `fault-injection-started`, 1 `fault-injection-finished` | the same |
| Layout check, replay | conforms; replays, `code differs`, `revision held` | conforms; replays, `code same`, `revision held` |
| Cleanup | Job and ConfigMap deleted; nothing labelled for the run left | Job, ConfigMap, and network policy deleted; nothing labelled for the run left |
| State | FAILED on `S5I-AC2` | PASSED |

`code differs` for attempt 1 is expected: its analysis was bound at `7f150c2`, and
`7089a53` edits `tools/reliability_runner/core.py` and `__main__.py`, which are
sources of the analysis. The replay computes the stored bytes with the present code.

### Why attempt 1 failed, and what was changed

The network plugin of this cluster starts the `kube-network-policies` controller,
and the release's API policy admits only the pods of the release and the named
collector. The runner carries no release label, by design. Three readings agree that
the policy dropped its requests: six requests with no answer at the client deadline,
`api-requests-by-outcome` with no series in each of its 36 reads, and no line of the
run in the logs of the API pods, read by the operator after the attempt. That is an
inference; no reading states a verdict of the plugin. The V1 measurement that this
plugin does not enforce was of an earlier build on the cluster before it was made
again on 2026-10-05.

The change adds the allowance that the review describes and nothing wider:

- **One network policy for each run**, first in the List that `start` creates, with
  the name and the labels of the run. It selects the API pods by the selector of the
  committed render and admits, on TCP 8090, the pods labelled with the runner's name
  and the run identifier. Ingress only.
- **The release's policies are not edited**, and the runner still carries no label of
  the release. Policies add up, so while the policy exists the API admits one more
  set of pods.
- **Lifecycle.** `start` refuses an existing policy of the run's name. `cleanup`
  deletes it after the Job and the ConfigMap and fails when it is still present. The
  time to live of the Job does not remove it.
- **Bound of the claim.** Any pod in the namespace that carries the two labels is
  admitted while the policy exists. [The runner page](../../serving/reliability-runner.md#the-network-policy-of-a-run)
  says so.

## What the pre-run reviews found

Two independent reviews read the procedure before an attempt used it. What they found
is what the first drafts got wrong.

**The review of the first draft of revision 1 and of the driver** (two high, five
medium, four low):

- The two collectors were started together, and each rewrites the project kubeconfig
  through one temporary file when it starts; a race could refuse a collector for a
  reason that is not the system's. The driver now starts the second when the first
  states that it samples, with a bound, and refuses an attempt whose collector ended.
- The first draft took 110 timeline samples. The collector is bounded by samples and
  not by time, and with fast reads it could have ended before the analysis window.
  The driver takes 200, and states for each attempt whether the last reading covered
  the window. Both did.
- The first draft did not refuse a release that was not at the state its declaration
  expects. The driver now refuses unless the Application is `Synced` and `Healthy` at
  the remote main and each Deployment reports 2 Ready replicas, and it deletes only a
  Ready API pod.
- The scripts call `python`. The driver now puts the locked environment first.
- The readings of the runner pod, on which `S5I-AC3` rests, were only in the
  transcript. They are now evidence files, with the facts the driver read.
- `S5I-AC2` compares instants of two clocks. The driver now reads the node's clock
  between two host instants at the start and the end, and the criterion holds only
  with a margin larger than that bound.

**The security review of the network policy** found no critical or high item. It
found that the first wording of the runner page overclaimed: "it admits one run" was
true of the selector and not of who can create a pod with those labels, "it changes
no rule of the release" left out that the effective set of admitted pods grows, and
the page said that `create` makes the policy before the Job, which `kubectl` attempts
in order and does not guarantee. The page now says each. It also found two gaps in
the new test, closed in the same commit: bare pods of the render were not checked
against the admitted labels, and the port of the release's own API policy was not
compared.

## Other corrections this change made to itself

- **The first commit broke one test.** `7f150c2` added a row to the freeze registry.
  The E01-D review record states the digest of the registry as it was reviewed, and
  one test compared that digest with the whole file of today. The test now rebuilds
  the registry without the rows registered after the review, as the test of the
  earlier review already did. The review record is unchanged. `7089a53` carries the
  fix.
- **A statement of the first result page was wrong before commit.** It said that the
  replacement pod of attempt 1 was Ready "at the next reading". The pods stream shows
  one reading in between that lists it as not Ready. The committed page states the
  reading.

## Evidence level and limitations

- **Intended level C2, for each attempt.** A real cluster, the delivery controller,
  the real runtime, and the real model. One provider, one node, one release, and one
  attempt each. Not representative, and it does not reach C3.
- **Caller truth.** The caller record is the caller's own. The telemetry is not: in
  attempt 2 the API's counter last stated 78 successes, and the caller recorded 98.
  This change does not explain the difference.
- **Clocks.** The caller record uses the runner pod's clock and the streams use the
  host's. The node-clock readings bound the difference by 0.902 s in attempt 2.
- **Only an API pod was replaced.** The review allows an API or a runtime pod; a
  runtime pod was not replaced, and nothing here says what a caller sees then.
- **Operator reads outside the procedure** are stated in the result page of attempt 1:
  one read of the runner's log during the attempt, and reads of the API pods' logs and
  of the plugin's log after it. None changed anything, and the driver read none.
- **The network-policy notes are inferences.** The pages that state that the local
  plugin does not enforce policy now carry a dated note; deferred risk `DR-04` is not
  re-assessed and stays open, and ADR 0004's risk `R7` and the chart's comment are
  not edited.

## Validation

The commands and results that this commit's state was checked with, from the
repository root unless stated, are below. The independent review of this commit,
the full default lane, and the hosted workflow are recorded in a later section.

| Command | Result |
|---|---|
| `python -m tools.experiment_freeze --check` | `PASSED: 5 freeze record(s), every rule held` |
| `python -m tools.experiment_freeze --changes docs/proof/experiments/v2-s5-integration/freeze-r2.v1alpha1.json` | `UNCHANGED` |
| `python -m tools.experiment_run repository` | `manifests  5: 3 pre-schema, 2 conforming, 0 refused` |
| `python -m tools.experiment_evidence repository` | `runs       5: 3 pre-schema and not checked, 2 conforming, 0 refused` |
| `python -m tools.analysis_replay repository` | `runs        5: 3 pre-schema and not replayed, 0 with no analysis, 2 replayed, 0 refused` |
| `python -m tools.analysis_replay verify` on each attempt | `replayed`, `revision  held` |
| `python -m tools.experiment_timeline check`, `tools.experiment_telemetry check`, `tools.experiment_events check`, `tools.reliability_runner verify --plan` | Each passed in each attempt; the transcripts, step E10, hold the output |
| `python -m tools.evidence_index --check`, `--gate` | Both passed at `7f150c2`; the index does not read the integration directory, because no ledger bears on it |
