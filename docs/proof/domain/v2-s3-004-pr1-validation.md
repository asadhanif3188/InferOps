# V2-S3-004-PR1 validation

Date: 2026-10-06

What this change adds, what it leaves unchanged, and the checks run over the repository.
The change adds one record:
[freeze revision 3](../experiments/v2-e01/freeze-r3.v1alpha1.json) of the V2-E01 family,
which names the environment of E01-D, the real-deployment part.

**No part of E01 ran.** Nothing was deployed. Argo CD synchronized nothing, and no
completion was sent. One cluster was read with read-only requests. Nothing was
provisioned, downloaded, or published. The change adds no claim and no evidence record. A
freeze record is not evidence.

## Why this change exists

[Freeze revision 2](../experiments/v2-e01/freeze-r2.v1alpha1.json) left one field pending:
the environment identity of E01-D. A part with a pending field cannot run. The Argo CD
installation, the Git desired-state layout, and the Application were built after revision
2 merged. This change names them in a new revision, before the result-bearing run.

## Eligibility, checked before anything was written

- **The base.** `git pull origin main` left `main` at
  `97e8e2f4f1e96a94610aad31085142d624b90f4a`, the merge of pull request 122. The branch
  was created at that commit, and `git status --short` printed nothing.
- **The chain holds the corrected revision.** `tools.experiment_freeze --check` exited 0
  over two records. Revision 2 supersedes revision 1 by its content digest.
- **Revision 2 states the governing criterion without the exception of revision 1.** Its
  hypothesis ends "and no claim-relevant workload intent is written again by hand after
  rendering", and E01-AC5 and E01-AC10 state no exception for a hand-written copy of a
  contract value. A test of the freeze suite holds this.
- **The review and the gate are merged.** Pull request 115 published the independent
  review of the second static run, and pull request 116 narrowed the claim and added the
  review gate. Both are ancestors of the base.
- **No pinned input of revision 2 had moved at the base.**
  `tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json`
  exited 0 at the base. So no change between revision 2 and the base is material to
  the static result. This change edits no pinned input of revision 2.

## One finding before the record was written

Revision 2's E01-AC10 said that the release "is installed from the generated values file
and one hand-written values file only, with no parameter override".
[ADR 0019](../../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
D5, accepted one day after revision 2, delivers the values in another way: the generated
values file, hand-written values inside the Application, and one Helm parameter,
`api.image.digest`, which the operator supplies. On that delivery the clause cannot hold,
whatever a run observes.

The work stopped at this point. The repository maintainer approved one change, on
2026-10-06: revision 3 replaces that clause with the ownership property that the
criterion exists to test. No other criterion changes.

**This is a change to a frozen criterion, and it is recorded as one.** `criteriaChanges`
in the record holds the earlier statement, the new statement, the reason, and the
approval. Two facts bound it:

- No E01-D run had executed under any revision, and no E01-D result existed.
- Runs of the same Argo CD path had executed on the same provider, on 2026-10-03,
  2026-10-04, and 2026-10-05. They applied the same release with the same parameter, and
  they sent caller requests. They are not E01-D runs. The change was written with
  knowledge of them, and the record says so in `criteriaChanges` and in `history`.

## What changed

| File | Change |
|---|---|
| [`freeze-r3.v1alpha1.json`](../experiments/v2-e01/freeze-r3.v1alpha1.json) | New. Revision 3 |
| [`registry.v1alpha1.json`](../experiments/registry.v1alpha1.json) | One row added: the content digest of revision 3. The two earlier rows are unchanged |
| [`tests/testing/test_experiment_freeze.py`](../../../tests/testing/test_experiment_freeze.py) | Revision 3's pin, written out. Thirteen tests of revision 3, and one of an edit to a superseded record. The tests that plant a next revision now plant revision 4 |
| [`tests/testing/test_experiment_review.py`](../../../tests/testing/test_experiment_review.py) | One existing assertion changed. The published review names the registry digest that the second run recorded. Registering revision 3 adds a row, so the file's digest moved. The test now rebuilds the registry of two rows from today's file and compares with that |
| [The experiments page](../experiments/README.md), `CONTRIBUTING.md`, `CHANGELOG.md`, [the proof index](../README.md), the test inventory | Revision 3 described |
| ADR 0018, ADR 0019, [the Application document](../../environment/argocd-application.md) | One dated note each, on the open item that asked for this revision |

No file under `tools/`, `src/`, `charts/`, `gitops/`, `infra/`, or `scripts/` changed. The
freeze checker and the E01 runner are pinned inputs, and neither is edited by this
change. One edit of the runner was tried and taken back out;
[the review section](#what-the-independent-review-found) says why.

### What revision 3 holds

- **The environment identity.** Provider `docker-desktop`. One cluster at Kubernetes
  v1.36.1, through the context `docker-desktop`. One node, `desktop-control-plane`, on
  `amd64`, with no taint. The default storage class `standard`, with the provisioner
  `rancher.io/local-path`. Argo CD v3.5.3 from the pinned core install manifest. The
  runtime image by digest. The model by repository, revision, file, SHA-256, and size.
  The record separates the attributes that must be equal for a run to start from the
  ones a run records again.
- **The API image digest is not named.** No InferOps API image is published. The run
  builds the image at the commit it executes and records the digest. The record says
  that it cannot name a digest before the image exists.
- **The Git and Argo CD path.** The release directory, its release identifier and
  digests, the Application, its project, the repository, the followed branch, and the
  sync policy.
- **The steps.** Seven preparation steps and six run steps, each with its commands and
  what it must return. Three statements of revision 2's E01-D procedure are replaced,
  and `procedureChanges` lists each with the earlier text and the reason.
- **Every other difference from revision 2.** `fieldChanges` holds twelve rows, each
  with revision 2's text and the reason.
- **The verification rules.** For E01-AC8, E01-AC9, and E01-AC10: which file and which
  field is compared with which value.
- **The remaining freeze fields.** The repetition count is unchanged: one deployment and
  one completion. The evidence paths, the abort conditions, and the cleanup are stated
  for this environment. Two abort conditions are added.
- **The pins.** 160 inputs. `inputChanges` classifies the 86 that revision 2 did not
  pin.
- **Every file changed since revision 2 merged.** 132 files, from `git diff
  --name-status a5b6a5d..97e8e2f`: 78 added, 54 changed, none deleted. 18 are on the
  E01-D path and are pinned. 114 are not, and each has a category and a reason.

### What was read from the cluster

On 2026-10-06, through the context `docker-desktop`, with `kubectl` and a request timeout:

| Read | Returned |
|---|---|
| `kubectl version -o json` | Client v1.36.1, server v1.36.1 |
| `kubectl get nodes -o wide`, `-o json` | One node, `desktop-control-plane`, Ready, role `control-plane`, v1.36.1, Debian GNU/Linux 13 (trixie), kernel `6.18.40.1-microsoft-standard-WSL2`, `containerd://2.3.1`, `amd64`, 12 CPU, 10186220Ki memory, no taint |
| `kubectl get storageclass` | `hostpath` and `standard`. `standard` is the default. Both use `rancher.io/local-path`, reclaim policy `Delete`, binding mode `WaitForFirstConsumer` |
| `kubectl get ns` | `default`, `kube-node-lease`, `kube-public`, `kube-system`, `local-path-storage` |
| `kubectl get` of the release namespace and of the namespace `argocd` | Neither exists. The server has no Application resource type |

A first set of the same reads, earlier on the same day, was refused at the connection:
the cluster was not running. The operator started it, and the reads above followed.

`docker`, `helm`, `terraform`, and `uv` printed their versions. `docker images` listed
the API image, the model seed image, and the runtime image on the host. No command
changed the cluster or the host.

**The identity was not read through the repository's provider verification.** That
verification, `inferops::resolve_target`, runs inside the mutating procedures. The reads
above used `kubectl` with the context named. The first preparation step of E01-D that
loads an image runs the verification.

## Checks that the record is what it says

- **The scope and the pins are the same set.** The generator computed the material files
  of the new scope in the working tree at `97e8e2f`, and pinned each. It refused a scope
  that matched a file Git does not track. Afterwards,
  `tools.experiment_freeze --changes` for revision 3 exited 0.
- **Every pin of revision 2 is kept.** The generator asserted that each of the 74 has
  the digest revision 2 pinned, and a test holds it.
- **No added pin is on the static path.** The generator asserted that no added file is
  in the material scope of revision 2.
- **The named release is the committed one.** The generator read the release identifier,
  the digests, and the Application's fields from the committed files. A test compares
  them with those files while the files have their pinned content, and is skipped
  after one of them changes.
- **The listed files are the ones Git reports.** A test compares the 132 rows with
  `git diff --name-status` between the two commits. It is skipped in a checkout that
  lacks either commit, which includes the hosted lane's shallow clone.
- **One criterion statement differs.** A test compares every statement with revision 2.

The generator is a scratch script and is not committed. It is not evidence.

## Commands

```sh
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

## Results

Run on 2026-10-06. The table is the final tree, the one the second commit holds.

| Check | Result |
|---|---|
| `tools.experiment_freeze --check` | Exit 0: 3 freeze records, every rule held |
| `tools.experiment_freeze --changes`, revision 3 | Exit 0: every material file matches |
| `tools.experiment_freeze --changes`, revision 2 | Exit 0: every material file matches |
| `tools.experiment_e01 --check` | Exit 0: 2 runs, each agrees with its own evidence |
| `tools.evidence_index --check` and `--gate` | Exit 0 |
| `tools.proof_dashboard --check` | Exit 0 |
| `tools.generated_release --check` | Exit 0 |
| `tools.gitops_desired_state --check` | Exit 0 |
| `ruff format --check .`, `ruff check .`, `mypy` | Clean |
| `git diff --check` | Exit 0 |
| The default lane, `pytest -q` | **18,789 passed, 1 failed**, 36 skipped, 14 deselected, in 30 minutes 54 seconds |
| The module of the failed test, run alone three times afterwards | 93 passed, each time |

**The default lane ran three times, and every run is reported.**

| Tree | Result |
|---|---|
| The first commit | 18,787 passed, none failed, 36 skipped, 14 deselected, in 53 minutes 45 seconds |
| The review corrections, with the runner edited | 18,777 passed, **14 failed**, 36 skipped, 14 deselected, in 38 minutes 53 seconds. The review section says what failed and what was done |
| The final tree | 18,789 passed, **1 failed**, 36 skipped, 14 deselected |

The one failure on the final tree is
`tests/architecture/test_argocd_bootstrap_procedure.py::test_install_refuses_manifest_bytes_that_are_not_the_pin`.
That module executes the bootstrap procedure against stub programs. This change edits
neither the procedure nor the module. The module passed in the first two lanes, and it
passed three times alone after the third. The cause of the one failure was not
investigated. The failure is recorded as it happened, and the whole lane was not run a
fourth time.

## What the independent review found

One independent review read the staged tree of the first commit, `74c0064`, read-only. The
reviewer is a separate session of the automated assistant that wrote the change. It is
not a person, and it is not outside the project. It ran no test and contacted no cluster.
The first commit is kept as it was, and the second commit holds the corrections.

**What the first commit got wrong.**

| Finding | What was wrong | Correction |
|---|---|---|
| The completion command could not produce the status that E01-AC8 judges | The registered command had no status output, and it printed the generated text into the transcript, which the record says is not kept | The command writes the body to an ignored file and prints the status. `completion.json` is derived from both |
| The registered evidence directory is one that the pinned E01 check refuses | `tools.experiment_e01 --check` reads every directory under `runs/` and knows revisions 1 and 2 only. The first commit said nothing about this. The default lane will fail when an E01-D run is committed there | **Not fixed. Stated.** See below |
| "No step reads it" was false for four listed files | Step D6 ran a whole test module, and other tests of that module read four documents that the record listed as read by no step. `pytest.ini` and `conftest.py` were not pinned | Step D6 selects the three tests that the rule rests on. They read pinned files only. The two configuration files are pinned, and the four reasons are corrected |
| The identity precondition could not be met | Step P3 was to compare every identity attribute, and some do not exist until a later step | The record names the step that reads or establishes each attribute |
| The wait was weaker than revision 2's, and the record said that it was the same | Two waits of 600 seconds each, and a wait that ended at its bound made the part INCONCLUSIVE, which permits a new run | One deadline of 600 seconds for both. A release that is not ready then makes the part FAILED |
| "Three statements are replaced" understated the differences | Eleven further differences from revision 2 were not listed, among them a rewritten cleanup that dropped four items | `fieldChanges` lists twelve rows with revision 2's text. The cleanup states the count after removal, the verify before removal, and the images it leaves |
| An abort condition and a limitation had no observation | The record said as fact that the acquisition hook downloads nothing. No step reads it | The record says that it is expected and not observed |
| The purpose statement overstated what was unchanged | Two field entries that cover the static parts differ from revision 2 | The statement names both |
| This record omitted a changed test | The review test's assertion was changed and not listed | Listed above, in the changelog, and in the inventory |
| A test's name claimed more than it checked | The test of the 132 files compared the record with itself | It is renamed, and a second test reads Git |
| No test bound the record's repeated values to the files | The first commit argued against such a test | A test compares them while the files have their pinned content |

Smaller corrections: a limitation named Python packages that the API image does not
install; the residue query is now repeated with a bound, as the earlier driver did; the
network statement names the downloads it had omitted; E01-AC10 names the chart's own
defaults and the record says which two rules measure "restates"; the static run's
manifest is named with its digest; one doubled comma; the count "six procedures" counted
a library.

**One finding is stated and not fixed.** The first correction of the evidence-directory
finding changed one function of the runner, so that the check left out an E01-D run
directory, and classified the edit in the record as not material. The default lane then
failed 14 tests. Thirteen failed because the static suite builds its temporary
repositories from the runner's current bytes and revision 2's pins: with the runner
edited, every such run is refused. One failed for another reason, corrected below. The
classification was written before the lane ran, and the lane showed that the edit has
a consequence the classification did not state. The edit was taken back out. The
record now says that the change that commits an E01-D run must change the check after
the run, what that moves, and that a later run of any part then needs a later
revision. The evidence directory stays under `runs/`, because the review gate reads
runs only there.

The fourteenth failure: the record now quotes revision 2's text where it replaces it,
and that text names the change that registered revision 2. The test that lists the
identifiers a record may name was corrected to expect it.

**Wrong counts in the first commit.** It stated 158 pins and 84 added. The second commit
pins 160 and adds 86, because two configuration files were missing.

**Not changed.** The reviewer noted that content defects are still planted in revision 2
only, so the larger scope of revision 3 is exercised by one test over the committed
tree. That is left as it is. The reviewer could not check the values read from the
cluster.

**Revision 3 was regenerated after the review.** Its content digest in the first commit
was `798309f8…`. It was regenerated three times after that, and in the second commit
it is the one the registry holds. The record was
not merged between the two, so no merged record was edited.

## Privacy and publicability

The record names one node, one context, and tool versions. It names no host name, no
user name, no local path, no account identifier, and no credential. It names this
change's identifier and, inside a quotation of revision 2, the identifier of the change
that registered revision 2. The identifiers of other earlier changes appear in lower
case inside the file names of their records. The repository URL
in it is the public one that the Application manifest already holds. The diff was
searched for drive-letter paths, home directories, private planning file names, and
story identifiers other than this change's own.

## What this does not establish

- **Any result of E01-D.** The part has not run.
- **That the environment is the same when the run starts.** The run reads it again and
  refuses on a difference.
- **That the steps succeed.** They follow the sequence of earlier runs on this provider,
  and they were not executed for this record.
- **That the changed criterion would have been written the same way without the earlier
  runs.** It was written after them.
- **That an E01-D verdict is computed by code.** No runner and no coded analysis exist
  for E01-D. A person applies the registered rules, and a driver is not a pinned input.
- **That a committed E01-D run is judged again.** No command does that.
- **That the default lane accepts a committed E01-D run.** It does not yet.
- **That the E01 runner executes revision 3.** It executes revision 2.
- **That no model download happens in the run.** No step observes it.
- **Behaviour on `kind`, on another Kubernetes version, or on more than one node.**

## Acceptance

| Criterion | Status |
|---|---|
| An E01-D freeze revision is committed before the result-bearing run. It names the environment identity and the Git and Argo CD path, and it classifies each experiment-path change since the superseded revision | Reached in this change, when it merges |
| The frozen acceptance criteria are unchanged | Reached for E01-AC1 to E01-AC9. **Not reached for E01-AC10**: one clause changed, with approval, and the record states it |
| The exact contract is validated and rendered from a clean revision | Pending. The run owns it |
| The generated desired state is accepted in Git and reconciled by Argo CD | Pending. The run owns it |
| A real model completion returns through the supported API | Pending. The run owns it |
| The identities are recorded | Pending. The run owns it |
| The evidence is C2 and bounded to the executed environment | Pending. The run owns it |
