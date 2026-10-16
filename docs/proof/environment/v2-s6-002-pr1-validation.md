# V2-S6-002-PR1 validation: the Q2 runtime startup characterization

Status: **one characterization ran, [`q2-1`](../experiments/v2-q2/runs/q2-1/result.md),
and it is `CHARACTERIZED`: each of the 16 rules held, and S = 11,000 ms. Evidence level
C2, bounded to the docker-desktop provider with one node, in the environment of `q1-1`.
No claim is registered.** The change has four commits. The first registered freeze
revision 1, the tool, and the driver, before any characterization. The second
registered revision 2, before any characterization, because a precondition of revision
1 could not hold. The third adds the run. The fourth closes what the independent review
found.

| Property | Value |
|---|---|
| Branch | `test/v2-s6-002-q2-runtime-startup` |
| Base | `486ca49ae99ed7257a503e291d5710be88f7ce26`, the merge of `V2-S6-001-PR2` |
| Freeze record | [`v2-q2/freeze-r2.v1alpha1.json`](../experiments/v2-q2/freeze-r2.v1alpha1.json), registered by this change. It supersedes [revision 1](../experiments/v2-q2/freeze-r1.v1alpha1.json), registered by the first commit of this change, under which no characterization ran |
| Driver | [`v2-q2/procedure/q2-driver.txt`](../experiments/v2-q2/procedure/q2-driver.txt), a pinned input of the record |
| Tool | [`tools/runtime_startup`](../../../tools/runtime_startup/core.py) |
| Page | [Q2: the runtime startup characterization](../../environment/runtime-startup-characterization.md) |
| Suite | [`tests/domain/test_runtime_startup.py`](../../../tests/domain/test_runtime_startup.py) |
| Qualified environment | [`q1-1`](../experiments/v2-q1/runs/q1-1/result.md), `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461` |

## What the story asks of this change

Story `V2-S6-002` characterizes the qualified release before any result-bearing
reliability run. This change is its first part: three controlled runtime restarts in the
qualified environment, with every observation kept, and S, the maximum interval from
the creation of a replacement runtime pod to its first Ready condition, stated by a
record. Later work derives bounds from S. This
change derives none.

## What this change adds

- **`tools/runtime_startup`.** It reads one directory that the driver writes and prints
  one record whose result is `CHARACTERIZED`, `INCONCLUSIVE`, or `REFUSED`. It contacts
  no cluster. Its 16 rules are the 16 acceptance criteria of the freeze record, with the
  same statements. Seven are preconditions: the phase `up` completed at the executing
  commit, the working tree was clean, the frozen inputs of Q2 and of Q1 are at their
  pins, the delivery paths equal the desired revision, the environment digest is the one
  `q1-1` states, the release and the runtime image are those of `q1-1`, the API
  Deployment runs the API image that the phase `up` declared (since revision 2), and both
  Deployments are at 2 Ready replicas. A precondition that is not held makes the
  result `REFUSED`. Any other rule that is not held makes it `INCONCLUSIVE`. S has a value
  only when the result is `CHARACTERIZED`.
- **The driver.** Its phases `up` and `down` run the phases of the Q1 driver without a
  change, so the release is prepared and removed as for `q1-1`. Its phase
  `characterize` asks the tool for the preconditions and then runs three restarts, one
  at a time, with a watch of the runtime pods around each and one completion to each
  replacement after it.
- **The freeze record, revision 1.** Its material scope holds the whole material scope of
  the Q1 freeze record, the Q2 driver, the import closure of the Q2 tool, the Q1 freeze
  record, and the record of `q1-1`: 195 pinned inputs. It states the restart, the
  measurement, the rule that derives S, and no value of S.
- **The layout check admits the Q2 directories.** `tools/experiment_evidence` lists a
  directory of `v2-q2/runs/` as a qualification, as it lists one of `v2-q1/runs/`, and
  names `tools.runtime_startup --check` as its check. The edit moves the three pins of
  `tools/experiment_evidence` in revision 2 of the Sprint 5 integration validation again;
  its two attempts are finished, and the edit moves no pin of the Q1 or the Q2 record.

## Decisions this change makes

1. **A restart is a rollout restart of the runtime Deployment.** It is controlled and it
   is not the fault of a reliability experiment: the Deployment controller replaces the
   pods under the chart's rollout bounds, and no pod is deleted by name. Under those
   bounds one restart replaces both runtime pods, one after the other. So three restarts
   give six observations, and S is the maximum of the six. A rule holds that the second
   replacement of each restart was created no earlier than the first was Ready.
2. **The interval is from the creation of the pod to its first Ready condition.** The
   creation includes the scheduling and the verification of the model by the init
   container. Ready is the condition that the kubelet sets from the readiness probe on
   `/health`, which answers 503 while the model loads. The two parts of the interval are
   stated beside it. Both instants are cluster timestamps of whole seconds.
3. **Ready is confirmed by one completion of each replacement.** It is sent after the
   rollout of its restart completed. It is not a part of the interval.
4. **The environment is the one `q1-1` selected, and Q1 does not run again.** The Q1
   freeze record allows a later qualification only after the environment or a frozen
   input changes. So Q2 runs the phase `up` of the Q1 driver and compares the capacity
   record of that phase with `q1-1`: the tool computes the environment identity with the
   function of the Q1 tool, and compares the release identifier and the runtime image
   with the record of `q1-1`. Revision 1 compared the API image digest with it too;
   revision 2 compares it with the digest that the phase `up` declared.
5. **The driver requests no restart after a refusal.** It asks the tool for the
   preconditions with `--preconditions` before the first restart, and it requests no
   later restart after a rollout that did not complete within 1800 s.

## What the first commit got wrong: revision 1

The first commit registered revision 1. Its precondition `release-qualified` held the
API Deployment to the API image digest that the record of `q1-1` states. That cannot
hold: the phase `up` of the Q1 driver builds the API image again, and on 2026-10-15 the
phase `up` of the work directory `q2run-1`, at the first commit, reported
`sha256:cf30eac7cc2a75f9a91dac62c8c09a6080de5b2725d2b37262c15bafe924120d`, where `q1-1`
states `sha256:5b4be2da31141bc43c0fa65133b4377ef002a3ff922278cda98ba247a244c7e1`. The
freeze tool listed no changed input of the Q1 record, and the Dockerfile copies only
`src/inferops` and three paths of `tools/`, which the Q1 record pins. The build inputs
were unchanged, and the digest was another one. The digest is the manifest-list digest.
The independent review found that the transcripts show more: the builds of `q1-1`, of
`q2run-1`, and of `q2-1` each printed the same image manifest, `sha256:bba83fa7…`, and
the same config, `sha256:cd65ca24…`, and another attestation manifest. That is what the
build printed; no rule reads it.

What was done, in order:

1. The phase `up` completed, with exit status 0.
2. **No characterization ran under revision 1.** No identifier was spent. Instead, the
   operator read the capacity collection, the provenance, and the Deployments once into a
   scratch directory outside the repository, with a header written by hand, and ran
   `python -m tools.runtime_startup --preconditions` on it. Six preconditions were held.
   `release-qualified` was not held, with the detail "the declared API image is not the
   one q1-1 states". The environment digest was the one of `q1-1`. That reading is an
   operator check: it is not committed, and it is not a characterization.
3. The phase `down` removed the release. The namespaces and the custom resource
   definitions after it were those before the phase `up`.
4. The second commit registers revision 2, which holds the API Deployment to the digest
   that the phase `up` declared, as Q1 does. It changes no other rule, bound, or step.
   It classifies the two pins that moved: the tool (material) and the driver (not
   material: it names revision 2).

## The run

Under revision 2, at the commit `65bd9bb`, with the work directory `q2run-2`, on
2026-10-15 (UTC):

1. The phase `up` of the Q1 driver ran from 12:55:43 to 13:05:14 and exited 0. The
   controller reported the Application `Synced` and `Healthy` at `486ca49`. The API image
   build reported `sha256:218cc858ad7788c7b309140e8255d558100ca5ef06fe15cd7b48d059241dff9b`,
   a third digest for the same inputs.
2. The characterization `q2-1` ran from 13:05:33 to 13:08:07. The 7 preconditions were
   held before the first restart. Three restarts ran, each rolled out 21.8 s to 22.6 s
   after its request, and each replaced the two runtime pods one after the other. After
   each, the controller reported the Application `Synced` and `Healthy`: the rollout
   restart's annotation of the pod template did not put the Application out of sync in
   this run. Each replacement answered one completion with HTTP status 200.
3. The tool exited 0: `CHARACTERIZED`. The six intervals from creation to Ready were
   11,000, 11,000, 11,000, 11,000, 10,000, and 11,000 ms. **S = 11,000 ms.**
4. The phase `down` exited 0 and ended at 13:09:53. The namespaces and the custom
   resource definitions after it were those before the phase `up`.

[The run page](../experiments/v2-q2/runs/q2-1/result.md) gives each observation with its
two parts, the identities, and what is not committed.

## Parent-story acceptance

| Criterion | State after this change |
|---|---|
| Q2 executes 3 controlled runtime starts or restarts and freezes S as the maximum start-to-Ready interval | **Met for this environment.** Three controlled restarts, six observations, all kept; the committed record of `q2-1` states S = 11,000 ms, and `tools.runtime_startup --check` builds it again |
| The other criteria of the story | **Pending: later work.** This change derives no bound |
| Qualification data is not promoted as a benchmark or as result-bearing reliability proof | **Held:** the record states no average, percentile, or rate, the pages say that S is not a startup benchmark, and no claim cites S |

## Evidence level and limitations

The run is evidence at C2: a real cluster, the delivery controller, the real runtime,
and the real model on one provider and one node. A characterization is a prerequisite and
not a result, and its level raises no claim. The tool's suite is evidence at C0 over
synthetic directories. Read S with the limitations of [the run
page](../experiments/v2-q2/runs/q2-1/result.md#what-this-does-not-establish-and-what-to-read-with-it):
the six starts were warm, every interval lies close to the probe period of 10 s, and the
resolution is one second. The detail string of `release-qualified` says "with the images
of q1-1" although the API image is the digest that the phase `up` declared; the rule's
statement is right, and the tool is a pinned input of revision 2, so the string is kept.

## Validation

Run from Git Bash on the Windows workstation. The first two rows were run before the
first commit, the next rows before the second commit, and the rows from
`tools.runtime_startup --check` on after the run.

| Command | Result |
|---|---|
| `python -m pytest` over eleven suites before the first commit: `test_runtime_startup`, `test_environment_qualification`, `test_experiment_freeze`, `test_analysis_replay`, `test_experiment_e01`, `test_experiment_review`, `test_test_inventory`, `test_renderer_input_boundary`, `test_argocd_bootstrap`, `test_document_links`, `test_experiment_evidence_layout` | 3,001 passed, 3 skipped; after the leak fixes of the first commit, the three suites it edited again, 677 passed, 2 skipped |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 7 freeze record(s), every rule held` at the first commit, and `PASSED: 8` at the second |
| `uv run --locked python -m tools.experiment_freeze --changes` of the Q1 and the Q2 records | Unchanged |
| `bash -n docs/proof/experiments/v2-q2/procedure/q2-driver.txt` | No syntax error |
| `python -m pytest` over seven suites before the second commit: `test_runtime_startup`, `test_document_links`, `test_analysis_replay`, `test_experiment_e01`, `test_experiment_review`, `test_experiment_freeze`, `test_experiment_evidence_layout` | 1,222 passed, 3 skipped |
| `uv run --locked python -m tools.runtime_startup --check` | `PASSED: 1 committed characterization(s), each record is what its directory gives` |
| `uv run --locked python -m tools.experiment_evidence repository` | `runs 7: 3 pre-schema and not checked, 2 qualification(s) with the text rules only, 2 conforming, 0 refused` |
| A search of the run directory and the transcript for host paths, account names, and home directories | No match after the redaction; `capacity/pods.json` is not committed |

## What the independent review found

Two independent reviews read the three commits after the run: one of the tool, the
driver, and the tests, and one of the evidence and the pages against the committed
files. The reviewers are automated sessions. Neither found a defect that changes the
result or S: every figure of the run page matched the raw files, and the tool's rules
could not be made to pass a wrong directory. The fourth commit closes what they found,
and leaves the tool, the driver, and the freeze record unchanged, because each is a
pinned input of revision 2 and the run executed under them.

**What the first draft of the evidence got wrong, corrected in place:**

- **The starts were called warm by comparison with the wrong reading.** The run page and
  the Q2 page compared the six intervals only with the first starts of `q1-1`, 51 s. The
  watch of `r1` holds the first runtime pods of this same phase `up`, started just after
  the claim was filled: 21 s. Both readings are now stated, neither as an observation of
  Q2, and the pages no longer say why the starts were shorter.
- **The preconditions were described as "the images of `q1-1`"** in this record and on
  the Q2 page, which is false under revision 2 for the API image. Corrected. The same
  words remain in pinned files: the module docstring of the tool, a comment of the
  driver, and the material-scope description of revision 2; the page states it.
- **The API image was described as unknown content.** The transcripts show that the three
  builds printed the same image manifest and config and another attestation manifest;
  only the manifest-list digest, which the chart is given, differs. Now stated.
- **The same-second order was named for `r1` only.** It occurred in each of the three
  restarts. Corrected on the run page.
- **The README said "six warm restarts".** There were three restarts and six
  replacements. Corrected.
- **The layout page counted one `qualification` line**, and three of its passages named
  only `v2-q1/runs`. Corrected.
- **The experiments page had no index rows and no status entry for Q2.** Added.
- **Rule statements stronger than the checks.** `ready-serves` reads the content of each
  completion file and not when or through which port-forward it was sent;
  `environment-qualified` does not compare the instant of the capacity reading with the
  apply. Both are now stated on the page and on the run page. The freeze statements are
  kept.
- **Two values of the run are in the host's local time**, the `restartedAt` annotation
  and the Helm `LAST DEPLOYED` line, though the run page said that all instants are UTC.
  Now stated; the raw files are not edited.
- **Smaller corrections:** the start of the phase `up` (12:55:43 printed, 12:55:45 in its
  start file), the end of the characterization (13:08:07.558 is the final header; the
  driver printed 13:08:09.049 after the record), the order of the copy of the capacity
  collection in the procedure, what the two waits of the driver do not enforce, the
  driver comment about when the last replaced pod terminates, the definition of S in
  this record (from the creation of a pod, not from a runtime start), the suites named
  in the validation table, the citation of ADR 0002 for `/health`, and the reason for a
  maximum (later work needs a conservative input; S is not a threshold).

**What the review found in the tests, closed by the fourth commit:** each defect case now
asserts the exact state of its rule and the exact set of other rules that it breaks; the
equality boundary of `one-at-a-time`, a removal after Ready, an image identifier without
the reference, a status of `true`, and each header state `unread` have their own cases;
and a driver test holds that the restarts are the body of the branch that the exit
status 0 of the precondition check opens.

**What stays open, owed to a later revision of the freeze record** (stated on [the Q2
page](../../environment/runtime-startup-characterization.md#measured-gaps-of-the-tool)):
a pod identifier of another form raises instead of refusing, and the suite holds that
gap; a later revision breaks the rebuild of `q2-1` unless `--check` rebuilds a
characterization under the revision its header names; `preparation-completed` reads the
absence of a refusal; no rule compares a cluster instant with a host instant; the driver
has no trap; and the detail string of `release-qualified` and the sentence "a pod that
replaces a deleted pod" of the record are imprecise.
