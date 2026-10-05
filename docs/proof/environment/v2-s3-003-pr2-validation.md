# V2-S3-003-PR2 validation

Date: 2026-10-05

What this change checked before it was committed, and how. What it adds is described
in [the reconciliation evidence document](../../environment/reconciliation-evidence.md).
This page is about the checks run over the repository after the operation, the tool,
the suites, and the documents were written.

> [!IMPORTANT]
> **The observation ran on one provider.** On 2026-10-05, on the `docker-desktop`
> provider, the `observe` operation read one Application beside an apply, after
> it, and beside a removal, in two runs.
> [The record of the runs](v2-s3-003-pr2-reconciliation-observation-run.md) is the
> `C2` evidence of this change, and it says what the runs do not establish. A
> first attempt was aborted, and it is kept there.
>
> **Two independent reviews followed the first commit.**
> [The section below](#what-the-review-found) lists what they found and what the
> first commit got wrong. The procedure, the tool, and the driver changed, and
> the last run is the run of the committed bytes.
>
> **What Argo CD reports is not a caller outcome.** One caller request was sent
> in each run. Nothing else on this page is evidence that a request was answered.
>
> **No claim moves.** The change adds no record to the evidence pack and registers
> no claim.

## Evidence levels on this page

| Evidence | Level | What executed |
|---|---|---|
| [`tests/domain/test_reconciliation_evidence.py`](../../../tests/domain/test_reconciliation_evidence.py) | `C0` | The evidence tool, on directories that the suite wrote, and Git, to read the commit that `HEAD` names. Two of its tests read the eight committed records as files |
| The `observe` cases of [`test_argocd_application_procedure.py`](../../../tests/architecture/test_argocd_application_procedure.py) | `C1` | The committed procedure, with `kubectl`, `kind`, `docker`, and `sleep` replaced by recording stubs. Four cases then give the written directory to the evidence tool |
| [`tests/architecture/test_argocd_application.py`](../../../tests/architecture/test_argocd_application.py) | `C0` | Nothing. It reads the procedure and the documents as text |
| [The runs of 2026-10-05](v2-s3-003-pr2-reconciliation-observation-run.md) | `C2` | The procedure, with the real tools, on a real cluster of one provider, with a real Argo CD. Bounded to that provider, that host, one day, and one commit |

The levels are defined in [the evidence levels](../../testing/evidence-levels.md).

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `4045295`, the merge of pull
  request 121, which added the desired-state provenance tool.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0
  with `RELEASED v1.0.0` with the set `1d40b33f…` and the pack `652e9051…`, and
  `CURRENT` with the set `0271ae27…` and the pack `222bc533…`. The command was run
  after this change was written. It was not run on `main` in this session.
- **The frozen experiment.** After the last edit, `python -m
  tools.experiment_freeze --check` exited 0 for both freeze records, and `python
  -m tools.experiment_e01 --check` exited 0 for both runs. This change edits no
  file that a freeze record pins. Neither command was run before the first edit
  in this session.

## What changed

- **[`scripts/environment/argocd-application.sh`](../../../scripts/environment/argocd-application.sh)**
  — a fourth operation, `observe`. It reads and does not mutate. The bytes of the
  procedure changed, so its SHA-256 is no longer the one that the transcripts of
  2026-10-04 print. Those transcripts are unchanged.
- **[`tools/reconciliation_evidence`](../../../tools/reconciliation_evidence/core.py)**
  — a new tool. It reads the directory that `observe` writes and prints one
  record. It reads no cluster and writes nothing.
- **[`tests/domain/test_reconciliation_evidence.py`](../../../tests/domain/test_reconciliation_evidence.py)**
  — a new default-lane suite, with 111 cases.
- **Two existing suites of the procedure.** The executed suite went from 95 cases
  to 121: 20 cases of `observe`, and 6 more argument cases. The static suite went
  from 35 cases to 36.
- **One other existing suite.** The render-boundary suite lists the new tool
  beside the four repository checks, because the tool names three of them.
- **[The reconciliation evidence document](../../environment/reconciliation-evidence.md)**
  — a new document. It also states the boundary for a manual change.
- **[The record of the runs](v2-s3-003-pr2-reconciliation-observation-run.md)**,
  with three transcripts, eight records, and the driver.
- **`.gitattributes`** pins those evidence files to LF line ends.
- **Indexes and living documents**: the architecture index, the system
  architecture, the Argo CD Application document, the Argo CD bootstrap record's
  page, the provider contract, the desired-state provenance document, the
  renderer input boundary document, the proof index, the contributor guide, the
  README, the test inventory, and the changelog.

**What did not change.** No file under `charts/`, `src/`, `gitops/`, `infra/`,
`contracts/`, or `.github/`. No decision record. No ownership row. No security
control. No claim. The four mutations of the procedure are the same four.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| A collector for the desired revision, the observed revision, the sync state, and the health state | Reached as an operation and a tool, executed against stubs and on one provider. `observe` reads the Application a stated number of times, and the tool reports `followedRevision`, `resolvedRevision`, `syncStatus`, `healthStatus`, and the last operation at each sample |
| Transitions | Reached as a computation on samples. A transition is a difference in one of eight fields, or in the read of the Application, between two consecutive samples. Run 3 observed 22 transitions beside the apply and 11 beside the removal |
| A bounded collection | Reached. The count and the interval have no default and have limits of 120 and 30 seconds. The time that one read takes is not bounded |
| Tests for missing and unavailable fields | Reached. See [the next section](#missing-stays-missing) |
| A statement that Argo CD state is reconciliation evidence and not caller truth | Reached in the document, in the output of `observe`, and in every record. A test holds each of the three |
| The boundary for an experiment or a break-glass change | Reached as a document: six rules, each with how it is held. Three are held by review, two are not enforced, and one is tested against stubs. No mechanism was added. Three of the six are in no decision record, and the document says so |
| Diagnostics that hold no secret | Reached as a bound and a heuristic. The record is built from an allowlist, every text value is bounded, and the redaction has stated gaps |
| A bounded observation on a cluster, recorded at `C2` | Reached on one provider. Each run made five observations, of 2, 3, 80, 5, and 40 samples. The observation of attempt 1 was stopped at 23 samples of 80, and its record says that it is not complete |

## Missing stays missing

The suite holds these properties of the tool. Each is a test on a directory that
the suite wrote.

| Property | Cases |
|---|---|
| A required field that is absent, null, empty, a number, or a mapping has a state other than `reported`, carries no value, and makes the sample not settled with a reason | 25: five fields, five changes each |
| A missing parent leaves each field below it missing | 5 |
| An Application with no status reports no state | 1 |
| A read that did not answer, an absent Application, and an answer that is not one JSON object report no field | 5 |
| No combination of absent required fields is settled | 31 combinations, in one case |
| A value is not carried across a read that did not answer | 1 |
| An Application with a deletion timestamp is not settled | 3 |
| An object without metadata is not settled | 3 |
| A comparison that could not be made is recorded as not compared | 4 |
| Objects beyond the limit are not said to agree | 1 |
| No count is given where no object was read | 1 |
| The command exits 0 with a record of reads that did not answer, and the record counts no settled sample | 1 |

## The cluster

No transcript of the three steps below was kept. The owner of the host and the
operator state them.

1. **The first cluster did not start.** Docker Desktop was started, and its
   Kubernetes cluster reported `failed to start`, twice. It was not reset by this
   change: a reset deletes the cluster.
2. **The owner of the host made a new cluster.** Its first form had two nodes.
   The provider guard refused it, with `provider-mismatch`, because this project
   has observed one node as the shape of Docker Desktop. The guard was not
   changed and not bypassed.
3. **The owner made a cluster of one node, at Kubernetes v1.36.1.** The runs
   used it. The earlier runs used v1.34.3.

[The record of the runs](v2-s3-003-pr2-reconciliation-observation-run.md) holds
attempt 1, which was aborted, run 2, and run 3.

### One client-side check, before the runs

The tool reads the labels of an object as one line of JSON after two tab
characters. Before a cluster was available, a real `kubectl` client, version
v1.36.1, printed that form for two local files, with `patch --local` and the
output template of `observe`. No transcript of that check was kept. Each run then
read the labels of 26 applied objects in that form.

## What the review found

Two independent reviews followed the first commit, `4dfb69e`. One read the
procedure, the tool, the suites, and the driver, and built inputs against the
tool. One read the documents against the transcripts and the records. Neither
contacted a cluster.

**The first found no way to make a sample settled that lacks a required field,
and no unanswered, absent, or unreadable read that was read as a state.** It
found the defects below.

| Found in the first commit | What was true | Change |
|---|---|---|
| The labels section said `compared`, with no finding, when a read returned more than 200 objects | The tool compared the first 200 by name and dropped the rest. Fifty objects with another workload label passed | The section says `compared-in-part` and counts the objects that were not compared. A test plants the fifty |
| A sample with no other revision was `compared`, with no revision finding | The tool had compared the resolved revision with the provenance that was read at it. A test asserted that shape under a name that said the opposite | The resolved revision is not compared. Each of the three comparisons has a state of its own. The test asserts `not-compared` |
| Only a message was bounded and redacted | A repository address with a credential in it reached the record twice. A sync state of 5 MB gave a record of 15 MB | Every text value is bounded at 256 characters, loses an address user, and is `malformed` when it is credential-shaped. A list of value files is bounded at 20 |
| `observation-directory-exists` printed "Nothing was read." | The target had been verified first, which reads the cluster | The check comes before the verification, and the test asserts no `kubectl` call |
| The driver read a query that did not answer as no object left | An empty output passed its guard | The driver ends when the query fails |
| Three preparation commands of the driver were not guarded | A failed `values` command left an empty file that `helm install` accepts. An abort cleaned up nothing and said nothing about it | Each is guarded. An abort prints the commands that clean up |
| A count with 5,000 digits raised an error of Python | The command printed a traceback | A count has at most six digits |
| The pattern of a sample file matched digits that are not ASCII | 123 samples that nobody took appeared | The pattern is `[0-9]` |
| A collection with more samples than it was asked for was complete | The test pinned that | Complete means exactly the samples that were asked for |
| `objectCount` was 0 for an object read that did not answer | Zero is a count | It is null |
| An object without metadata was read as not being deleted | An absent deletion timestamp was `missing` | Without metadata the field is `malformed`, and the sample is not settled |
| The directory was created with `mkdir -p` after the check | Two observations of one name could both pass | The directory is created without `-p`, and a failure is a refusal |
| A test was named for running no process and writing no file | It reads the imports of the tool's three files. The tool calls the provenance tool, which runs Git | The name and the docstring say what it reads |

**The second found every number, time, exit code, and SHA-256 of the run record
equal to the transcripts and the records.** It found these statements wrong or
without support.

| The first commit said | What was true | Change |
|---|---|---|
| Kubernetes stopped the acquisition job as `OOMKilled`, with exit code 137, after 13 seconds | The transcript holds `BackoffLimitExceeded` and no more. The operator had read the pod by hand | The run record quotes the two lines from the operator's terminal and says that no transcript holds them. Three documents no longer state the cause as observed |
| The committed driver is the driver | The committed file had been edited after run 2, and it would have failed on the records that run 2 built | Run 3 ran the committed driver. The run record states which bytes ran in each execution, and that the two earlier drivers are not committed |
| The transcript holds the attempt and the cleanup, and the operator stopped the driver, destroyed the prerequisite layer, and observed the state | The transcript holds none of the three operator actions | The run record separates what the transcript holds from what the operator states |
| Both executions ran the real serving runtime and the real model | No workload object was applied in attempt 1 | The level table has a row for attempt 1 |
| One sample reported `Healthy` before the pods of the release were ready | The observation reads no pod state | The three documents state the two reported states and that no pod state was read |
| The collection reads no pod specification | The object read requests whole objects, and `kubectl` filters them | The document says what is requested and what is written |
| The boundary section decides no new mechanism | True, but three of its six rules are in no decision record, and it adds an exception that ADR 0019 does not state | The section names the three rules and the exception as proposed |
| Self-heal reverts a change to a managed field | Three runs each observed one change to a replica count reverted | The sentence states that |
| The two other revisions differ while an operation is in progress | In every record they were missing or equal | The sentence states that |
| The tool changed three times between attempt 1 and the commit | It changed once before run 2 and twice after | The run record has a table of the bytes of each execution |
| The first acceptance row is met | The three labels name no commit and no release | The row says partly met |
| No function was given a value that was read from a cluster | The next sentence said the opposite | The sentence is about the suite |
| The provider contract: `v1.34.3` both times it was read | The runs read `v1.36.1` | The row states both |
| The renderer boundary document: the tool names two tools | It names three | Corrected |
| Four observations of run 2 | Five | Corrected in this record |
| "Safe diagnostics" | The redaction is a heuristic | The heading is "Bounded diagnostics" |

**The header of the committed driver is wrong in two places, and it was not
edited.** It says that the driver makes four observations, and it makes five. It
says that the driver returns the cluster to the state it found, and the two
images stay in the node. An edit would make the committed driver another file
than the one that ran in run 3.

**Left as it is, and stated.** `settled` reads no condition and no queued
operation, and it does not check the kind or the name of the object. The
redaction does not know three shapes that the document names. The largest count
of 120 samples was not executed. The refusal of a directory that is created
during the start was executed nowhere.

## Commands and results

Run on the reference host, from Git Bash.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 18,767 passed, 36 skipped, and 14 deselected, in 49 minutes 47 seconds. Nothing else ran beside it |
| `uv run --locked ruff check .` | Passed |
| `uv run --locked ruff format --check .` | 647 files already formatted |
| `uv run --locked mypy` | No issues in 354 source files |
| `bash -n scripts/environment/argocd-application.sh` | Exit 0 |
| `uv run --locked python -m tools.experiment_freeze --check` | Passed: 2 freeze records |
| `uv run --locked python -m tools.experiment_e01 --check` | Passed: 2 runs |
| `uv run --locked python -B -m tools.evidence_index --gate` | Exit 0 |
| `uv run --locked python -m tools.gitops_desired_state --check` | Passed |
| `uv run --locked python -m tools.generated_release --check` | Passed |
| `git diff --check` | Exit 0 |

**After the whole lane ran, this record alone was edited, to state its result.** The other rows ran after the last
edit and before the lane.

**The lane's run before that one had one failure.** It ran while the other rows of
this table ran beside it: 1 failed, 18,766 passed, 36 skipped, and 14 deselected.
The failure was `test_a_run_writes_evidence_the_judge_agrees_with` of
`tests/testing/test_experiment_e01.py`, with a directory that was not found under
pytest's temporary directory. This change edits neither that suite nor the tool it
executes. The test passed alone, its module passed with 93 cases, and the whole
lane then passed with nothing beside it. The cause was not established.

Before the first commit, the whole lane had run once at an earlier state of this
change: 18,741 passed, 36 skipped, and 14 deselected. The suites that the change
touches then ran again before that commit: 8,123 passed in one command, and the
121 cases of the executed suite in another.

**Not run.**

- **`shellcheck`.** It is not installed on the reference host. The hosted lint
  job runs it.
- **The hosted workflows.** They run when the change is pushed.
- **The Helm, Terraform, and image checks.** This change edits no chart, no
  Terraform file, and no image.
- **Anything on `kind`.**

## What this does not establish

- **That `observe` works on another cluster**, another Kubernetes version, or
  another Argo CD release.
- **That a read which fails beside a running Argo CD is recorded.** That case
  ran against stubs only.
- **That a reported state is true.** The tool records what was reported.
- **Anything about a caller.**
- **That the boundary for a manual change is followed.** No admission control
  exists. Review holds three of its six rules, and nothing enforces two.
- **That the record holds no secret.** It is built from an allowlist, and the
  redaction is a heuristic.
- **Anything about `kind`.**

## Acceptance

| Criterion of the story | State after this change |
|---|---|
| An applied workload traces to a Git revision and to render provenance | Partly met on one provider, for one commit. In each run, the commit that Argo CD reported resolved to one release, and 26 applied objects carried the three labels that the release derives. The labels name no commit and no release. No applied object carries the release identifier, and the commit that Argo CD reports is not shown to be the commit it applied |
| The desired revision, the observed revision, and the reconciliation state are collectable | Met on one provider. Not shown on `kind` |
| GitOps state stays separate from caller health | Met as a rule that tests hold in the output and in every record. In each run, one caller request was sent apart from the observations. No caller measurement reads the record |
| A manual `kubectl` change is for an experiment or a break-glass action only | Met as a document. Nothing enforces it, and three of its rules are proposed and in no decision record |

**What stays open.** The release identifier on an applied object, a way to
suspend reconciliation, a decision record for the three proposed rules, a record
format for a break-glass action, the acquisition job's memory limit on this
Kubernetes version, and `kind`.
[The reconciliation evidence document](../../environment/reconciliation-evidence.md#not-applied-yet)
lists each.
