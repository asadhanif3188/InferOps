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
7. **Commit `10b3e89`**: the run directory of attempt 2, the preparation transcripts,
   and the pages that said that no run directory of the layout exists.
8. **The commit after the independent review** of the three commits above: the first
   correction of the first attempt, the operator read of the plugin, and the wording
   that the review found too firm. No attempt ran after it.

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
- **The network-policy notes are inferences.** Four current pages that state that the
  local plugin does not enforce policy now carry a dated note: the provider contract,
  the troubleshooting guide, deferred risk `DR-04`, and the list of security limits in
  the README. Others say the same and are not edited: ADR 0004's risk `R7`, the
  security method's row for `DR-04`, the workload policy page, the security baseline
  record, the README's summary of what V1 is not, which describes V1, and the chart's
  comment, which this change does not touch because the chart
  is pinned by the E01 freeze records. `DR-04` is not re-assessed and stays open. The
  log lines of the plugin's policy controller that these notes cite are an operator
  read, [kept beside the run directories](../experiments/v2-s5-integration/preparation/kindnet-policy-controller-read.txt).
- **The driver's pin moved without being called material.** Revision 2 classifies the
  driver as not material, because only the record that it checks the pins against
  changed. That constant decides which pins an attempt is held to, so a reader can
  weigh it otherwise.

## What the independent review of this change found

One reviewer read the three commits, recomputed the figures of the result pages from
the evidence files, and checked the manifests, the freeze records, the network
policy, the public safety of the transcripts, and the pages. Every recomputed figure
matched. It found one high, three medium, and three low items, and each is fixed in
the commit that follows the review:

- **High: the cause of the first failure was stated as observed in five places.** The
  result page and this record said it was an inference, and the CHANGELOG entry, the
  experiments page, the runner page, and a test docstring said that the plugin
  enforces the policy, or that the attempt observed or showed that it does. Each now
  says that three readings point to the policy. Revision 2 says the same as the first
  draft did; it is pinned, and the experiments page states the overstatement.
- **Medium: the log line of the policy controller was cited and kept nowhere.** It is
  now an operator read beside the run directories, made again while the same container
  of the plugin ran.
- **Medium: stale current text.** The status line of the runner page still said that no
  run was started in a cluster, and so did a note of the test inventory; the README's
  list of security limits had no dated note; and this record said that every page
  that states non-enforcement carries one. Each is corrected, and the test that held
  the old status line now holds the new one.
- **Medium and low: four statements of the first attempt's result page.** It said that
  the analysis states no success gap, when it states the gap as not computable; its
  row for `S5I-AC6` omitted that the replay prints `code differs`; it gave outer bounds
  for the clock readings without the readings; and it cited no file for the policy
  controller. The run directory is committed, so it is not edited: the layout's first
  correction in the proof tree, `corrections/integration-1/correction-1.v1alpha1.json`,
  states the four. The layout check reads it, and the digests of the run do not move.
- **Low: the experiments page said that the procedure and the criteria of revision 2
  are those of revision 1.** Step 5 and `S5I-AC7` name the network policy; the page now
  says so.
- **Low: the driver's pin classified as not material.** Stated as a limitation above.

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
| `python -m tools.evidence_index --check`, `--gate` | Both passed at `7f150c2` and at `10b3e89`; the index does not read the integration directory, because no ledger bears on it |

### The default lane and the static checks, at `10b3e89`

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q -p no:cacheprovider` | **1 failed, 22,341 passed, 39 skipped, 14 deselected** in 5,084.58 s. The failure is `tests/architecture/test_argocd_application_procedure.py::test_an_argocd_the_bootstrap_did_not_install_refuses[remove-unmarked]`: the stubbed script printed nothing. This change edits neither that script, its suite, nor `lib.sh`. The module, run again alone at the same commit, passed: 121 passed in 897.56 s. The run took longer than usual because a review and other suites ran on the host beside it |
| `python -m mypy` and `python -m mypy --platform linux` | No issues in 414 source files, each |
| `ruff format --check .`, `ruff check .` | 751 files already formatted; all checks passed. The count includes Markdown files |
| `git diff --check` | No finding |
| `git ls-files -s scripts/environment/reliability-runner.sh` | Mode `100755`, unchanged |
| `gitleaks` | Not installed on this host. The hosted workflow runs it |

### After the review fixes

The suites that the fixes touch, at the commit that follows the review:
`tests/serving/test_reliability_runner.py`, `tests/testing/test_test_inventory.py`,
`tests/testing/test_document_links.py` (1,910 passed together), and
`tests/testing/test_experiment_evidence_layout.py`,
`tests/contracts/test_experiment_run_v1alpha1.py`, `tests/testing/test_experiment_freeze.py`,
the repository test of the replay, `tests/testing/test_evidence_levels.py`,
`tests/security/test_security_baseline.py`, and `tests/architecture/test_argocd_bootstrap.py`
(2,158 passed, 3 skipped together). The layout's `repository` command reads the
correction of the first attempt and still reports 2 conforming run directories.

### The first hosted run, and the change that followed it

The pull request's hosted workflow ran its default-lane job on the merge of `c6a3dec`
into `main`. Its log, as the owner passed it on, ends at 94 % of the lane; the summary
of the failures is not in it. Up to there it shows one failure, at the position that
`test_the_repository_command_replays_the_committed_attempts` of the replay suite takes
in the order of collection. The test is named from that position, not from the log.

That test required `revision  held` for both attempts. The hosted checkout holds one
commit, the merge, and so neither commit that the attempts state; there the command
states `revision  not-checked`, as it is built to. The same test, run in a clone of
depth 1 of the branch, failed at that assertion, and passed in this repository's full
clone. The commit after `c6a3dec` changes only the test: it reads which stated commits
the clone holds with `git cat-file`, and requires `held` for those and `not-checked` for
the rest. It then passed in the clone of depth 1 and in the full clone. In the clone of
depth 1, the test files that follow the 94 % point and the suites that this change
touches gave 3,260 passed, 5 skipped, and 6 failed. The 6 failures are E01 suites,
which the hosted log shows passing; they fail only when the environment of this
repository runs the files of another checkout.

The other jobs of the hosted workflow, and a hosted run of the commit that follows,
were not observed here.

### Not run

- **A complete hosted run.** This host has no GitHub command-line client. The one
  hosted log that was passed on is described above; no other job was observed.
- **Helm, Terraform, and the image builds.** This change edits no chart, no Terraform,
  and no image file.
- **A replacement of a runtime pod.** The review allows an API or a runtime pod, and
  the frozen procedure deletes one API pod.
