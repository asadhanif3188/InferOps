# V2-S3-004-PR2 validation

Date: 2026-10-06

What this change executed, what it checked before and after, and how. The change adds
one run of part E01-D of V2-E01, under
[revision 3 of the freeze record](../experiments/v2-e01/freeze-r3.v1alpha1.json). It
changes the committed-run check after that run, and it publishes one independent review
of the run. [The experiments page](../experiments/README.md#the-e01-d-run) describes the
run.

> [!IMPORTANT]
> **E01-D ran once, and it PASSED.** Run
> [`20261006-e01-d-1`](../experiments/v2-e01/runs/20261006-e01-d-1/result.md) executed on
> 2026-10-06 on the `docker-desktop` provider, at the merged commit `ad725905`. Each of
> E01-AC8, E01-AC9, and E01-AC10 holds. The evidence is `C2`. It is bounded to one
> provider, one cluster with one node, and one run, and it is not representative.
>
> **The run sent one completion request.** It does not establish that a second request
> is answered. What Argo CD reports is not a caller outcome: the one request is the only
> evidence that the release served.
>
> **No runner judged the run.** The automated assistant session that drove the run applied
> the registered verification rules. It is not independent of the run.
> [An independent review](#what-the-reviews-found) applied the rules again and found no
> defect in the verdicts. The reviewer is another session of the same assistant.
>
> **One pinned input moved after the run.** The committed-run check now leaves an E01-D
> run out. That edit is in `tools/experiment_e01/core.py`, which revisions 2 and 3 pin. A
> new run of any part is refused until a later revision classifies the edit.
>
> **This change registers no claim.** The register, the evidence index, and the
> dashboard are unchanged. A register change that bears on this run must reference an
> independent review record of this run, and the contribution rules ask that the review
> merges first. The claim and register reconciliation of E01-D is owed by a later change.

## Evidence levels on this page

| Evidence | Level | What executed |
|---|---|---|
| [Run `20261006-e01-d-1`](../experiments/v2-e01/runs/20261006-e01-d-1/result.md) | `C2` | The registered steps, with the real tools, on a real cluster of one provider, with a real Argo CD, the real runtime, and the real model. One completion request. Bounded to the environment that the run's `environment.json` records |
| The E01-D tests of [`tests/testing/test_experiment_e01.py`](../../../tests/testing/test_experiment_e01.py) | `C0` | Nothing of the experiment. They read the committed files of the run, revision 3, and the review record |
| The other tests of that module and [`tests/testing/test_experiment_freeze.py`](../../../tests/testing/test_experiment_freeze.py) | `C0` | The E01 runner and the freeze check, in temporary repositories. A test execution is not result evidence |
| [The review record](../experiments/v2-e01/reviews/20261006-e01-d-1-review-1.md) | None | It is not evidence of the run |

The levels are defined in [the evidence levels](../../testing/evidence-levels.md).

## Eligibility, checked before the run

| Condition | How it was checked | Result |
|---|---|---|
| Revision 3 is merged and registered | `git log` on `main`; the registry row; `tools.experiment_freeze --check` | Merged by pull request 123 as `ad725905`. Registered with the digest `b4aa013d…`. Exit 0 |
| Revision 3 supersedes the latest merged revision | `metadata.supersedes` of revision 3 | It names revision 2 by path and digest |
| No experiment-path change merged since revision 3 | `tools.experiment_freeze --changes` for revision 3, in step P2 of the run | Exit 0: every material file matches. The executing commit is the commit that merged revision 3 |
| The working tree was clean, and `main` on the remote named the executing commit | Step P1 of the run | The status printed nothing. Both commits are `ad725905a7838e8210e54a29de7913bc0c7c49e5` |
| The environment is the one that revision 3 names | Step P3 of the run: thirteen attributes compared | Each is equal. `environment.json` holds the comparison. Two of the thirteen are literals of the driver, not reads: the provider identifier and the context name. The procedures verify the target themselves, and the transcript holds their lines |
| The review gate of the earlier corrective change is merged | `tools.evidence_index --gate`; the gate's suite | Present. Exit 0 |
| The run is authorized | The maintainer asked for this change, whose purpose is the run | The environment names no paid provider. The preparation filled the claim from a seed image on the host. The run did not observe whether the acquisition hook downloaded anything |

**What was run before the driver started.** These commands were run by hand, once each,
on the same day:

- the reads of step P3: the server version, the nodes, the storage classes, the
  namespaces, and the custom resource definitions;
- the two freeze commands of step P2;
- the desired-state check of step D1;
- the version commands of the tools, and a list of the images on the host.

Each gave what the run then recorded. None of them applied the Application, changed an
object, or sent a request. The driver's three inline Python passages were compiled, and
the one that summarises the completion was run on a response file written by hand,
outside the repository. Under the rule of revision 3, an attempt is an execution that
applies the Application and sends a completion. No such execution preceded the run. That
is the statement of the session that drove the run, and no file proves it.

## The run

One attempt. No run was refused, aborted, or repeated.

| Item | Value |
|---|---|
| Run identifier | `20261006-e01-d-1` |
| Start and end | 2026-10-06T12:03:47Z to 2026-10-06T12:15:17Z |
| Executing commit | `ad725905a7838e8210e54a29de7913bc0c7c49e5` |
| Freeze record | Revision 3, content digest `b4aa013dc482a8f536395c094ab76dc2b753e04d7c139a4b0cadf17c672da739` |
| Provider and cluster | `docker-desktop`, Kubernetes v1.36.1, node `desktop-control-plane`, default storage class `standard` |
| API image digest of the run | `sha256:dfb772f2e0cc36e343ef95cd16718e9e9330898685e579b34de15a8ceb6a24dd` |
| Commit that Argo CD reports | `ad725905a7838e8210e54a29de7913bc0c7c49e5`, synced, operation succeeded |
| Apply returned, rollouts complete | 12:13:19Z, 12:13:37Z: 18 seconds, against a deadline of 600 seconds. It is a warm start: step P6 had started the same images on the same node about two minutes earlier |
| Readiness request | One. HTTP 200 |
| Completion request | One, no retry. HTTP 200, one choice, assistant message of 6 characters, model `qwen3-1-7b-q8-0` |
| Parameters supplied | One: `api.image.digest` |
| Abort conditions met | None on the evidence. One cannot be determined: whether the hook started a download |
| Cleanup | Each removal ended with exit status 0. The namespaces and the custom resource definitions after the run equal those of step P3 |

| Criterion | Verdict | Rests on |
|---|---|---|
| E01-AC8 | Holds | `completion.json`; the rules of E01-AC9 |
| E01-AC9 | Holds | `argo.json`, `provenance.json`, `release.json`, `pods.json`, `completion.json` |
| E01-AC10 | Holds | `argo.json`, the committed Application manifest, the pytest summary in the transcript, and the consumed static result |

**How the verdicts were applied.** The session that drove the run compared each value
that a rule names, with a script that is not committed. The manifest states every
compared value beside its rule. Since the review, the default-lane suite applies each
rule again to the committed files and requires the recorded verdict. For two rules it
reads less than a structured file: the admission rule is read from the pytest summary
in the transcript, and the eight-character rule from the consumed static run. That run's
manifest has the digest that revision 3 pins, `ae2e005b…`, and records that E01-AC5
holds. The run's own manifest cites step D6 for that rule and does not state those two
values.

**What the driver added to the registered commands.** Its header lists seven additions:
the date and the tool versions, a read of the custom resource definitions in step P3,
the digest of the model seed image, a wait of at most 30 seconds for the port-forward
before the one readiness request, a read of the revision that Argo CD reports after the
apply, the removal of carriage returns from two redirected records, and a print of the
pod phases. The header does not list these, which the driver also ran:

- `sha256sum` of the freeze record and the registry in step P2;
- `unset INFEROPS_KIND_CLUSTER_NAME`, before the procedures;
- a refusal when the evidence directory exists;
- a second call of five commands, to capture what the first printed;
- `uname -s`, and three inline Python passages that write `environment.json`,
  `release.json`, and `completion.json`;
- `cat` of the forward log, the readiness body, `provenance.json`, and four lists;
- in the cleanup: a read of the Deployments in the namespace, two `diff` commands, two
  `docker image ls` commands, and a final `sha256sum`.

None of them sends a request to the release, and none changes a cluster object. The read
after the apply and the registered verify took 16 seconds of the 600.

**Where the run files fall short of what revision 3 registers.** The files are evidence
and are not edited.

- **`commands.txt` is not the exact commands.** It has no shell quoting, it lists once a
  command that ran twice, and it omits `unset`, `sed`, `uname`, `python -c`, and `kill`.
  `driver.txt` holds the exact commands.
- **`transcript.txt` does not hold every output.** The output of three commands of step
  P3 was redirected to files that Git ignores. The five residue queries of step P6 show
  no exit status. The export, and the port-forward in the background, show none either.
  Each of the 79 exit statuses that the transcript shows is 0.
- **Four version strings differ in form from those of revision 3.** Helm and uv carry a
  build suffix, Terraform a name prefix, and the host operating system reads
  `MINGW64_NT-10.0-26200` where the record says Windows. Revision 3 attaches no refusal
  to them.
- **The driver has weaknesses that this run did not meet.** It does not check that the
  port-forward process is alive, so another listener on the port could have answered.
  It writes `requestsSent: 1` whatever curl returned. A failed step D1 or a failed
  verify would not have stopped it before the completion. It has no trap, and its last
  command decides its exit status. In this run the forward log shows that it listened,
  curl ended with exit status 0, and steps D1 and D3 each ended with exit status 0.

## One observation outside the criteria

The API pod requested the image by the digest that the run supplied, `sha256:dfb772f2…`.
Its container status reports the image identity `localhost/inferops-api@sha256:8d2b578c…`.

After the cleanup, the session that drove the run asked the node's image store with one
read-only command. It is not a registered step, and its output is not in the transcript.

```text
$ docker exec desktop-control-plane crictl inspecti -o json localhost/inferops-api@sha256:dfb772f2e0cc36e343ef95cd16718e9e9330898685e579b34de15a8ceb6a24dd
id          sha256:1205e5a16bdabc784cf57b0df95c4f2ee5701298db3f368f0ad2a111252c799c
repoTags    localhost/inferops-api:dev
repoDigests localhost/inferops-api@sha256:8d2b578c4322238734890a0424a2733f6f3269a0a5d54706c8664e9f49a222cd
            localhost/inferops-api@sha256:dfb772f2e0cc36e343ef95cd16718e9e9330898685e579b34de15a8ceb6a24dd
```

The three values are quoted from the JSON that the command printed. The same command for
the earlier digest printed the same three values.

- The identifier is the configuration digest that the build of step P4 exported: the
  transcript shows it. Every layer of that build came from the build cache.
- The earlier digest is the API image digest in the transcripts of 2026-10-04 and
  2026-10-05.
- The committed files of the run do not tie the serving API container to the build of
  step P4. This read does, and it was made by the session that drove the run.
- No E01-D criterion and no abort condition names the API image digest. The rule of
  E01-AC10 compares the parameter on the Application with the digest of step P4, and
  they are equal.

## The committed-run check, changed after the run

`tools.experiment_e01 --check` read every directory under `runs/` as a static run. Before
the edit, in this session, it reported one finding for the E01-D directory: the manifest
names no revision that the analysis knows. That output is not committed. Revision 3
states the defect, and leaves the correction to the change that commits the run.

The edit is the function `committed_runs`, one helper, and one pattern. The listing
leaves a directory out when two things hold: its name is `YYYYMMDD-e01-d-N`, and its own
manifest names part E01-D and no other. Every other directory is listed. The command
prints the number of runs it checked. It does not print what it left out.

| Consequence | Evidence |
|---|---|
| One pinned input of revisions 2 and 3 differs from its pin | `tools.experiment_freeze --changes` reports `tools/experiment_e01/core.py` for each record and exits 1 |
| A new run of any part is refused | The precondition of both records. This change registers no revision and classifies nothing |
| The E01-D run is not affected | Its step P2 reports no difference, and its steps do not run the runner. The run and the edit are in one commit, so Git history does not order them. The transcript supports the order and does not prove it |
| Tests failed with the edit and no other change | Thirteen in this session, before the fixtures changed. The count is not reproducible from this tree |
| The suites now rebuild the pinned runner | [`tests/support/e01_pinned_runner.py`](../../../tests/support/e01_pinned_runner.py) puts back the two passages that the edit replaced, and requires the digest that both records pin |
| The listing is the only difference from the pinned runner | The same requirement. Another edit to the runner fails it |
| A static run under an E01-D name is still checked | A test copies the second static run into such a directory. The listing returns it, and the check reports it |

**Which runner the suites execute.** The temporary repositories hold the pinned runner,
not the runner in the tree. A test that uses such a repository calls the runner in the
tree in its own process. The second render of each run starts a second process from the
temporary repository, and that process executes the pinned runner. One test starts the
whole command from the temporary repository, and it executes the pinned runner only.
The copies that the freeze suite checks for "no moved input" now hold the pinned runner
by construction. One test reads the runner in the tree against its pins.

## Commands

```sh
bash .artifacts/e01-d/driver.sh 20261006-e01-d-1
uv run --locked python -m tools.experiment_freeze --check
uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json
uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json
uv run --locked python -m tools.experiment_e01 --check
uv run --locked python -m tools.evidence_index --check
uv run --locked python -m tools.evidence_index --gate
uv run --locked python -m tools.proof_dashboard --check
uv run --locked python -m tools.generated_release --check
uv run --locked python -m tools.gitops_desired_state --check
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked python -m pytest -q
git diff --check
```

The driver is committed as
[`driver.txt`](../experiments/v2-e01/runs/20261006-e01-d-1/driver.txt). It ran from a
directory that Git ignores, so that the working tree was clean in step P1.

## Results

Run on 2026-10-06. The table is the final tree, the one the second commit holds. The
suite counts are what this session's terminal printed. No committed file proves them.

| Check | Result |
|---|---|
| The driver | It was not refused, and it ran to its last command. Its own exit status says nothing more |
| `tools.experiment_freeze --check` | Exit 0: 3 freeze records, every rule held |
| `tools.experiment_freeze --changes`, revision 3 | Before the edit, in the run: exit 0. After the edit: **exit 1**, one changed file, `tools/experiment_e01/core.py` |
| `tools.experiment_freeze --changes`, revision 2 | After the edit: **exit 1**, the same one file |
| `tools.experiment_e01 --check` | Exit 0: 2 runs, each agrees with its own evidence. The E01-D run is not among them |
| `tools.evidence_index --check` and `--gate` | Exit 0 |
| `tools.proof_dashboard --check` | Exit 0 |
| `tools.generated_release --check` | Exit 0 |
| `tools.gitops_desired_state --check` | Exit 0 |
| `ruff format --check .`, `ruff check .`, `mypy` | Clean |
| `git diff --check` | Exit 0 |
| The default lane, `pytest -q` | **18,824 passed, 2 failed**, 36 skipped, 14 deselected, in 49 minutes. Both failures were corrected afterwards, and no whole lane ran after the corrections. See below |
| The three modules that the corrections touch, afterwards | First run: 1,151 passed, **1 failed**. Second run: 1,152 passed, none failed |
| The document, evidence, security, and scaffolding suites, and the Application suite, on the final tree | 9,382 passed, none failed, in 4 minutes 36 seconds. This row was written after that run, and nothing else changed |

**The default lane ran twice, and each run is reported. Neither ran over the final tree.**

| Tree | Result |
|---|---|
| Before the first commit, while its documents were being written | 18,801 passed, none failed, 36 skipped, 14 deselected, in 33 minutes 11 seconds. It did not run over one fixed tree. The suites that read the documents then passed over the staged tree of the first commit: 9,260 tests, in 4 minutes 8 seconds |
| The second commit, before two corrections | 18,824 passed, **2 failed**, 36 skipped, 14 deselected, in 49 minutes |

**The two failures of the second lane were defects of this change.**

- `tests/architecture/test_argocd_bootstrap.py` holds which tracked files declare an Argo
  CD custom resource. The run's `argo.json` is the Application as the cluster returned
  it, so it matches. **The first commit fails this test.** The first lane did not show
  it, because the run directory was not tracked while that lane ran, and the suites
  that ran over the first commit's tree did not include this module. The test now
  names that one file as evidence, by its exact path, and holds that it is a record of
  the committed Application. A second such file fails it.
- `tests/security/test_security_baseline.py` found a home-directory path in the new
  tests: a string that one of them plants to show that the host-path pattern finds it.
  The string is now built when the test runs.

**One failure was not explained.** After those two corrections, the three touched
modules ran together: `test_a_second_process_from_another_checkout_aborts_the_run`
failed once. Its output was not kept. The same three modules then passed, and that test
with the three others that use a temporary repository passed five more times. That
test passed in both whole lanes. The cause was not found. It starts a second Python
process, and the failing run started right after the formatter and the type checker
had run.

## What the reviews found

Two automated sessions read the first commit, `2f2e1ff`, read-only. Each is a separate
session of the assistant that wrote the change. Neither is a person, and neither is
outside the project. The first commit is kept as it was, and the second commit holds the
corrections. No file of the run directory changed between the two commits.

**The review of the result.**
[Its record](../experiments/v2-e01/reviews/20261006-e01-d-1-review-1.md) is published
with this change. The reviewer applied each registered rule to the raw files. It found
no defect in the verdicts or the outcome, and it found that a rerun is not justified. It
listed fourteen findings, none claim-material. The record gives each with its
disposition. It also says what the reviewer could not verify, and that the reviewer read
uncommitted files under `.artifacts/`, which the brief did not ask for.

**What the first commit got wrong, by the review of the result.**

| Finding | What was wrong | Correction |
|---|---|---|
| A sentence contradicted the one before it | This page said that no step of the part was executed before the run, after saying that commands of steps P2, P3, and D1 were run by hand | The page lists what was run, and says what an attempt is under revision 3 |
| An unobserved fact was stated | This page said that the model was not downloaded by a registered step. The hook ran inside step D3, and nothing observes it | The page says what the preparation did and what the run did not observe |
| The redaction was understated | Three kinds of replaced text were stated. Line endings were also changed on 77 lines, and trailing whitespace was removed from 7 | Stated here and on the experiments page. The manifest and the result page keep their text |
| The driver's additions were understated | This page said that the driver's header lists each addition | The page lists the others |
| The run files fall short of the registered form | `commands.txt`, `transcript.txt`, two attributes of `environment.json`, and the cited evidence of one rule | **Not corrected: they are run files.** Stated above |
| The listing left out by name only | A static run in a directory named as an E01-D run would not have been checked | The listing also reads the directory's manifest. A test plants the case |
| "Every command ended with exit status 0" | Three command lines show no status | Reworded |

**What the first commit got wrong, by the review of the code and the documents.** It
reported ten findings, none critical.

| Finding | What was wrong | Correction |
|---|---|---|
| A test's name claimed more than it checked | The test of the compared identities never read `pods.json`, the response's model, or the hand-written values. Three of six rules of E01-AC9 were unchecked | The suite applies every rule to the committed files and requires the recorded verdict |
| No test planted a defect in the E01-D run | Nothing showed that the tests fail on a wrong file | Fourteen planted defects in a copy, each found by what the file says. A changed, an added, and an absent file are found |
| The host-path pattern missed three forms | A doubled backslash, a drive with a slash, and a drive as a POSIX directory | The pattern covers them, a test plants each form, and the checkout's own location is searched for |
| "Keeps no generated text" claimed more than the test read | It reads the summary file only | Renamed, and the docstring states the scope |
| A wrong statement about the runner the suites execute | This page said that one test executes the pinned runner. The second process of every temporary-repository test does | Stated above, and in two comments |
| Unreproducible or empty statements | "The driver: exit 0", the redaction counts, the thirteen failed tests, "no account identifier" | Reworded here and below |
| Stale statements elsewhere | Two passages of the experiments page spoke of E01-D as not yet able to run | Qualified. The register's claim texts that say E01-D has not run are dated statements of earlier ledgers, and the matrix page now says so |
| Pattern and listing details | `match` accepted a trailing newline, and a test compared a sorted list | `fullmatch`, and a set |
| Support module details | A singular comment, and an unhelpful error for a missing pin | Corrected |
| The inventory omitted the freeze suite's changed fixture | | Added |

**Not changed.**

- The command does not print the directories it leaves out. That needs an edit to a
  second pinned file.
- The driver's weaknesses. The driver is evidence of this run. A later run needs a
  corrected driver.
- A test does not require that the runner is the only moved input. The repository does
  not block a merge that changes a pinned file, and such a test would.

**Counts.** Neither review found a wrong count in the first commit. Both found counts
that the repository cannot reproduce: the suite totals, the redaction count, and the
thirteen failed tests. Each is now stated as what this session observed.

## Privacy and publicability

- The transcript is the driver's output with these changes: terminal colour codes
  removed, three occurrences of the repository's absolute path on the host replaced by
  `<repository>`, two Docker build links replaced by `<build details link>`, CRLF line
  endings changed to LF, and trailing whitespace removed. The unredacted transcript is
  not committed, so the count of colour codes, 486, cannot be checked from the
  repository.
- `completion.json` holds the length of the assistant message and not its text. The
  response body is not committed.
- `argo.json` and `pods.json` are the objects as the cluster returned them. They hold
  cluster-internal addresses, object identifiers, and image references. They hold no
  Secret value: the pods mount no Secret that the run read, and the Application holds no
  credential.
- The files name one node, one context, tool versions, and the public repository URL,
  which carries the account name of the repository's owner. They name no host name, no
  user name of the host, and no local path.
- The diff was searched for drive-letter paths, home directories, private planning file
  names, and the identifiers of other changes.

## What this does not establish

- **Behaviour on another provider, Kubernetes version, node count, or storage class.**
- **That a second request is answered, or any latency, throughput, capacity, or
  availability.** The run sent one request, after a warm start.
- **A caller outcome from a sync state or a health state.**
- **That Argo CD applies a later commit of `main`.** The run observed one commit.
- **That no model download happened in the run.** No step observes it.
- **That the acquisition hook fills an empty claim.**
- **That the verdicts are independent.** The session that drove the run applied them, and
  the reviewer is another session of the same assistant.
- **That the cluster returned the committed files.** The suite reads the files. One
  session wrote them.
- **That a new static run would pass.** It is refused until a later revision classifies
  the runner edit.
- **Any register claim about E01-D.** None exists.
- **Reliability under failure, or production readiness.**

## Acceptance

| Criterion | Status |
|---|---|
| An E01-D freeze revision merges before the result-bearing run | Reached by the earlier change of this story. The run executed at the commit that merged it |
| The exact contract is validated and rendered from a clean revision | Reached: step D1 derived the release at the executing commit, from a clean tree, and it equals the release in Git |
| The generated desired state is accepted in Git and reconciled by Argo CD | Reached on one provider: `argo.json` |
| A real model completion returns through the supported API | Reached once: `completion.json` |
| The contract, render, Git, runtime, model, and environment identities are recorded | Reached: the run's manifest and its files |
| The evidence is C2 and bounded to the executed environment | Reached for the run record. **The claim and register reconciliation is pending**: no register claim holds the result, and it is owed by a later change that references the review record |
