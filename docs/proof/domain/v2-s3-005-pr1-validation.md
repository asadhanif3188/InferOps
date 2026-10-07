# V2-S3-005-PR1 validation

Date: 2026-10-07

What this change registers, what it leaves unchanged, and the checks run over the
repository. The change adds the result of part E01-D of V2-E01 to the claim and evidence
register, through
[a tenth ledger of register changes](../testing/v2-s3-005-pr1-e01-d-registration.v1alpha1.json).

> [!IMPORTANT]
> **No part of E01 ran in this change.** The run,
> [`20261006-e01-d-1`](../experiments/v2-e01/runs/20261006-e01-d-1/result.md), executed
> once on 2026-10-06 in `V2-S3-004-PR2`. This change contacted no cluster, runtime,
> registry, or model. It changes no file of a run, of a freeze record, or of a review
> record.
>
> **The registration is late, and the record says so.** `V2-S3-004-PR2` ran E01-D and
> published its independent review. It registered no claim, and its validation record
> says that the reconciliation was owed by a later change. A review of the sprint on
> 2026-10-06 reported the claim as missing; it was reported to the author, and no file
> in this repository records that review. This change adds the claim on 2026-10-07.
> The register does not state that the registration happened on the day of the run.
>
> **The evidence is `C2`, and it is bounded.** One run, on the `docker-desktop` provider,
> on one cluster with one node, with one contract, one binding, one API replica, one
> runtime replica, and one completion request. It is not representative evidence.

## Why this change exists

[The validation record of the change that ran E01-D](v2-s3-004-pr2-validation.md)
states that the claim and register reconciliation of the result was not done there and
was owed by a later change. The contribution rules ask that the review of a result
merges before the register change for it, in a separate change, because the review gate
reads one repository state. The review merged with the run, so the register change had
to be a later change.

Three statements in this record rest on something outside the repository. A review of
the sprint, on 2026-10-06, reported that the reconciliation was a required part of the
work and was missing. It reported no defect in the freeze inputs, the raw run, the
result classification, or the review record. It reported that the finding justifies no
repeated run. That review was reported to the author, and no file in this repository
records that review. What the repository does record is the deferral in the earlier
validation record, and that the register held no claim for the run.

This change is the reconciliation, and it is nothing else.

## Eligibility, checked before the change

- **The run and its review are merged.** `git pull origin main` left `main` at
  `2c84793802bd14b5237e15dc6f6a2f1b6515d716`, the merge of pull request 124, which is
  `V2-S3-004-PR2`. The branch of this change was created at that commit.
- **The checkout was clean.** `git status --short` printed nothing before the branch was
  created.
- **The review record has a stable identity.**
  `docs/proof/experiments/v2-e01/reviews/20261006-e01-d-1-review-1.v1alpha1.json` has the
  content digest `46d2b99abc3b09391a56dd652ec0980cda61538dd0c80f05dc8129dba9e55080` at that
  commit. The digest is the SHA-256 of the file's bytes with every CRLF replaced by LF.
- **The review record is about this run.** It names the run `20261006-e01-d-1`, the
  twelve files of the run directory with the digest each file has now, and freeze
  revision 3 with the content digest
  `b4aa013dc482a8f536395c094ab76dc2b753e04d7c139a4b0cadf17c672da739`, which is the record
  that the run's manifest names. Its conclusion on the frozen run is `no-defect-found`,
  and it states that no repeated run is justified.
- **The review gate accepts the reference.** `python -m tools.evidence_index --write`
  builds the index only when the gate passes. It built the index with the new ledger.
  The gate was not changed.
- **No claim-material defect was found in the run, its evidence, or its review while the
  record was written.** The limits that bear on a criterion or on how the verdicts were
  reached are carried into the new record's limitations. The others stay in the review
  record and in the earlier validation record, which the new record cites. None of them
  changes a verdict.

## The identities this change consumes

| Identity | Value |
|---|---|
| Run | `docs/proof/experiments/v2-e01/runs/20261006-e01-d-1`, twelve files |
| Run manifest, content digest | `62255edaa5c078f6a1f67af140b923d2ef63e8b40d24c8919691aa37653c5733` |
| Result page, content digest | `36757bf257417b489aca9cd018622d6a1a4690cc475d58faf3724bea1552ac0a` |
| Outcome and level, as the run recorded them | E01-D `PASSED`, `C2` |
| Executing commit | `ad725905a7838e8210e54a29de7913bc0c7c49e5` |
| Freeze record | revision 3, `docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json`, content digest `b4aa013dc482a8f536395c094ab76dc2b753e04d7c139a4b0cadf17c672da739` |
| Freeze registry, content digest | `9da8814c91b8817a2e27e94c7cc0d6addc7a9a54f4e278ac7baf69f24fcb38bc` |
| Review record | `docs/proof/experiments/v2-e01/reviews/20261006-e01-d-1-review-1.v1alpha1.json`, content digest `46d2b99abc3b09391a56dd652ec0980cda61538dd0c80f05dc8129dba9e55080` |
| Provider and cluster | `docker-desktop`, one node, `desktop-control-plane`, Kubernetes `v1.36.1` |
| GitOps controller | Argo CD `v3.5.3`, installed from the pinned manifest that freeze revision 3 names as the core install. No file of the run shows the install profile |
| Contract and binding | `contracts/workload/examples/valid/synchronous-llm-local.yaml` on `local-docker-desktop` |
| Release | `releaseId` `eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae`, generated values digest `1849af0c88c2ef646b4f6eddfb515ba5fd3f3cbc5ac44950a35b9bf8cec864ce` |
| Runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model | `qwen3-1-7b-q8-0`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| API image, the digest the run supplied | `localhost/inferops-api@sha256:dfb772f2e0cc36e343ef95cd16718e9e9330898685e579b34de15a8ceb6a24dd` |

The second static run, `20261003-e01-abc-1`, is also consumed. One rule of E01-AC10
rests on it, so the new record cites its manifest, and the ledger references
[its review record](../experiments/v2-e01/reviews/20261003-e01-abc-1-review-1.md), content
digest `b8fd1f281f56301504cf91267121a1e9b1aab70e0755a6e14c86c9ab84cf8464`.

## What the ledger changes

The tenth ledger is the sixth written after `v1.0.0`. The evidence index undoes it, with
the five before it, to recompute the pack that the release was cut over.

1. **It adds one claim, with one record.** The claim is
   `the-e01-real-deployment-run-served-one-completion-from-the-release-reconciled-from-git`.
   Its status is `certified`, on one record at `C2`. It is appended to the register, so
   no existing pointer into the register moves.
2. **It appends a dated note to the limitation of two planned claims.**
   `the-platform-serves-a-workload-the-contract-describes` said that every real run so
   far deployed from a feasibility manifest or from the Helm chart.
   `deployment-values-derive-only-from-a-validated-document` said that no supported
   deployment or GitOps path consumes the generated files. Beside the new claim, each
   sentence would contradict the register. Each claim keeps its earlier text word for
   word, gains sentences dated 2026-10-07, stays `planned`, and cites no record. One run
   with one contract on one provider does not establish either general statement.
3. **It replaces one clause in the second static run's claim.** The clause said that
   E01-D "has not run". The static run still does not establish that the release input
   deploys or serves.
4. **It replaces one surface reason.** The reason for the evidence index named nine
   ledgers.

**The claim.**

> In one run on 2026-10-06, on the docker-desktop provider, on one cluster with one node,
> the release rendered from the unmodified V1 synchronous reference contract on the
> local-docker-desktop binding was accepted into Git, was read by the run at commit
> ad725905a7838e8210e54a29de7913bc0c7c49e5, was reconciled by Argo CD into Kubernetes,
> and answered one completion request through the InferOps API with HTTP 200 and one
> choice whose assistant message is not empty, with the real runtime and the real model
> that the generated values name. The run answers the criteria E01-AC8, E01-AC9, and
> E01-AC10 that freeze revision 3 registers for E01-D, and each holds.

The statement is in the past tense and names one run. It does not say that the platform
deploys or serves a contract in general. The two planned claims that would say so stay
planned.

**What the claim does not establish.** The register states it with the claim: a second
request; another provider, Kubernetes version, node count, storage class, workload
shape, contract, or binding; that Argo CD applies a later commit; a caller outcome from a
sync state, a health state, pod readiness, or a replica count; that the acquisition hook
downloads the model into an empty claim; latency, throughput, capacity, availability, or
behaviour under overload; reliability under failure, high availability, or tolerance of
the loss of a pod, a node, a zone, or a region; that a service-level objective
is met; representative evidence, `C3`, or operational evidence, `C4`; a cost, a
saving, a return on investment, or a business effect; that a person reviewed the result;
or production readiness.

**Why no historical record was rewritten.** The nine earlier ledgers, the three freeze
records, the registry, the three run directories, the two review records, and the
validation record of the run are unchanged, except for one dated note at the top of that
validation record, which the next section describes. The claim is added by a new ledger,
and each changed field keeps its earlier value in that ledger as the value before the
change.

## What is not corrected, and why

- **The first static run's claim still says that E01-D "has not run".** The clause is in
  what that claim does not establish. A change to that claim bears on run
  `20261002-e01-abc-1`. No review record of that run exists, and the review gate refuses
  such a change without one. This change creates no review. The clause describes the
  state on 2026-10-02. A test holds the refusal, and it holds that the clause is still
  there, so the next change that can correct it fails that test until it does.
- **The evidence records of the two static runs say the same, and they are unchanged.**
  Each is a dated record of its run.
- **The run files are unchanged.** The review record lists three run files whose text
  differs from what executed or from what the freeze record defines: the manifest and the
  result page name three of the five transformations of the transcript, `commands.txt`
  is not the exact commands, and the driver's header does not list every added command.
  One limitation of the new register record states the three.
- **The committed-run check still leaves E01-D out.** `python -m tools.experiment_e01
  --check` judges the two static runs. It does not judge the E01-D run, and its exit
  status says nothing about that run. No runner and no coded analysis exist for E01-D.
  The tests of `tests/testing/test_experiment_e01.py` apply the registered rules to the
  run's files.
- **A new run of any part of E01 is still refused.** `tools/experiment_e01/core.py`, which
  revisions 2 and 3 pin, differs from its pin. The change that added the run also made
  that edit, in one commit; the review record calls the order, run first, supported and
  not proven. This change does not edit that file and registers no freeze revision.

## One dated note in the earlier validation record

[The validation record of `V2-S3-004-PR2`](v2-s3-004-pr2-validation.md) says that the
reconciliation is pending. The new register record cites that page, so a reader arrives
at it from the register. One note, dated 2026-10-07, is added under its opening notice.
The note says that this change added the claim, and that the page's statements about a
pending reconciliation describe 2026-10-06. No other text of the page changed.

## One change to the evidence index tool

The new record is the first record with executed target behaviour that a ledger written
after the release adds. The index reads how each such record identifies the repository
code that ran. Until this change it read that from two ledgers only, both inside the
released pack, which cannot change. The index now also reads `codeIdentity` rows from a
ledger written after the release. A record is still read once: a second reading raises.
The new ledger states one row, `stated-revision`: the run manifest names the commit it
executed, with a clean working tree before the run.

The review gate, the released-pack recomputation, and the register rules are unchanged.

The third commit of this change applies the same rule to the `codeRevisions` rows of
such a ledger. [The hardening before the merge](#the-hardening-before-the-merge) says
what was open and what is refused now.

## What changed

| Area | Files |
|---|---|
| Ledger | `docs/proof/testing/v2-s3-005-pr1-e01-d-registration.v1alpha1.json`, new |
| Register | `docs/testing/claim-evidence-matrix.v1alpha2.json`: the five changes the ledger names |
| Generated | `docs/proof/v1-evidence-index.v1alpha1.json`, `docs/proof/dashboard.md` |
| Tools | `tools/evidence_index`: the ledger path, the code identity rows and, in the third commit, the code revision rows of a later ledger. `tools/proof_dashboard/core.py`: the new claim in the Kubernetes deployment group |
| Tests | `tests/testing/test_experiment_e01.py`, `test_result_review_gate.py`, `test_evidence_post_release.py`, `test_evidence_index.py` |
| Pages | `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/proof/README.md`, `docs/proof/experiments/README.md`, `docs/proof/v1-evidence-index.md`, `docs/testing/claim-evidence-matrix.md`, the test inventory, this record, and the one note in the earlier validation record |

## Results

Run on one Windows host, from Git Bash, on 2026-10-07. Each module command has the prefix
`uv run --locked --offline --no-sync python -B -m`.

| Check | Result |
|---|---|
| `uv run --locked --offline --no-sync ruff format --check .` | Exit 0: 653 files already formatted |
| `uv run --locked --offline --no-sync ruff check .` | Exit 0 |
| `mypy` | Exit 0: no issues in 355 source files |
| `tools.generated_release --check` | Exit 0 |
| `tools.gitops_desired_state --check` | Exit 0 |
| `tools.experiment_freeze --check` | Exit 0: 3 freeze records, every rule held |
| `tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json` | **Exit 1**, as before this change: `tools/experiment_e01/core.py` differs from its pin. This is the refusal of a new run. It is not a failed result |
| `tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | **Exit 1**, as before this change, for the same one file. This change does not edit that file |
| `tools.experiment_e01 --check` | Exit 0: 2 runs. **It does not judge the E01-D run** |
| `tools.evidence_index --check` | Exit 0 |
| `tools.evidence_index --gate` | Exit 0. Released `v1.0.0` set `1d40b33f...` and pack `652e9051...`, recomputed by undoing the six post-release ledgers. The current pair is another, after 22 post-release register changes |
| `tools.proof_dashboard --check` | Exit 0 |
| `git diff --check` | Exit 0 |
| `pytest tests/testing tests/architecture/test_argocd_bootstrap.py tests/security`, in the first commit | 9,083 passed |
| `pytest tests/testing tests/security tests/architecture`, after the corrections of the independent review | 12,485 passed, 3 skipped |
| The default lane, `pytest -q`, second run, after the corrections of the independent review | **0 failed**, 18,946 passed, 36 skipped, 14 deselected, in 29 min 8 s |
| The default lane, `pytest -q`, first run | **3 failed**, 18,929 passed, 36 skipped, 14 deselected, in 27 min 49 s. The next paragraph says what failed |

**The three failures, and what they found.** Each was a defect of this change, and each
is corrected.

- Two tests of `tests/architecture/test_argocd_bootstrap.py` hold the list of build and
  tool files that name Argo CD. The first form of the new claim identifier held the
  words `argo-cd`, and `tools/proof_dashboard/core.py` lists claim identifiers, so the
  tool file joined that list. The identifier was shortened to
  `the-e01-real-deployment-run-served-one-completion-from-the-release-reconciled-from-git`.
  The tripwire was not widened.
- One test of `tests/security/test_security_baseline.py` refuses a reserved term outside
  a sentence that denies it. The experiments page began a sentence with one such term,
  where it named a service-level objective. The wording is now "That a service-level objective is met", in the register and on
  each page.

The default lane was not run again after these two corrections in the first commit of
this change. The suites named in the table above were. The second run of the lane is
over the tree after the corrections of the independent review. After that run, this
Results section was written, the evidence index was regenerated, because the new record
cites this page, and the two digests on the index page were updated. The `tests/testing`
and `tests/security` suites, which read those files, then ran again and passed. The
skipped and deselected tests are not passes.

**What the suites hold for this change.** The review-gate module has 75 tests, 12 of
them new. They plant, for the E01-D run, each refusal that the gate makes: no review
reference, an absent artifact, the review of another run, a run file edited, added, or
removed, and a changed freeze record. The E01 module replaces the test that required the
register to hold no record of the run with six tests that bind the claim to the run, to
revision 3, to the review record, and to its boundary.

**Not run.** No step of E01. No request to a cluster, a registry, or the network. The
hosted checks are read after the change is pushed, and this record does not state their
result.

## What the independent review of this change found

Two automated reviewing sessions read the first commit of this change, `aa57a58`,
read-only. One compared the new claim and record with the files of the run and with its
review record. One read the code and the tests. Each is another session of the automated
assistant that wrote the change. Neither is a person, and their reports are not
committed. The second commit of this change holds the corrections.

| Finding | What the first commit said | Correction |
|---|---|---|
| Statements about a review outside the repository had no marker | The claim, the record, the ledger, and five pages said that a collective review "found the omission", and that it found the run and its review "sound". No committed file records that review, and an earlier record retired "sound" as an undefined word | Each place now says that the review was reported and that no file in this repository records it, and states what the repository does record: the deferral in the earlier validation record |
| A component note was stronger than its source | The record said that Argo CD "read the release directory from the remote repository". The review record lists that as not verified, and Argo CD reads the chart path and one values file | The note states what the Application names and what Argo CD reported, and that the run does not verify the read |
| A component note stated a tie that the evidence does not hold | The record said that the API replica ran "from an image that step P4 built". The review record says that the committed evidence does not tie the serving container to that image | The note states what the pod requested and what the container status reports. The code-revision note says what the tie rests on |
| The claim did not say that its review never read it | The claim and the record cite the review of the result. That review read a commit with no register statement | The claim's limitation and one record limitation say so |
| The record carried fewer limits than this page said | This page said that the limits of the earlier records "are carried". Ten were not, among them: an uncommitted script compared the values, one session wrote every file, no file proves that no earlier attempt took place, and the driver does not check the port-forward | Four limitations are added and three are extended, which carry eight of the ten. Two stay in the cited records: the digest that `sha256sum` printed in step P2, and the order of the run and the runner edit, which this page now states. This page now says which kind of limit is carried |
| The statement named the wrong event for the commit | "was accepted into Git at commit ad725905". The release files entered Git in an earlier change; the run read them at that commit | "was accepted into Git, was read by the run at commit ad725905" |
| The ledger description contradicted the change | "edits no dated record", while the change adds a dated note to one | The description names the one note |
| Two current pages were stale | The Application page and one sentence of the experiments page still said that no register claim holds or cites the result | Both corrected |
| "Independent review" had no qualifier in three new passages | Three pages said "the independent review of the run" | Each says that the reviewer is an automated session of the same assistant |
| A malformed code-identity row was a traceback | A row with a missing member raised `KeyError`, and the command did not report a refusal | Each row is checked, and a malformed one is a refusal |
| A ledger could read a record that it did not add | A row for a record of another ledger, or for no record, was accepted | A ledger written after the release reads only a record that it adds. Tests plant each case |
| Three tests could check the wrong thing | A test read the manifest's rules by position, split file names on spaces, and compared a count with a number that had no source | The rules are read by member name, the names by line, and the count against the manifest |

One finding is not acted on. The reviewer of the code noted that the earlier tests of the
review gate assert the text of a refusal and not the ledger that refused. Those tests are
unchanged in what they assert. The new tests for the registration ledger assert its name.

The reviewers ran no step of E01, contacted no cluster, and did not verify the figures of
the default lane.

## The hardening before the merge

Date: 2026-10-07, after the two commits above. Before the merge, the maintainer asked for
one more check in the index tool. No file in this repository records that request. The
third commit of this change holds the check. It changes no register statement, no
ledger, no claim, and no file of a run, of a freeze record, or of a review record.

**What was open.** The second commit made the index check each `codeIdentity` row of a
ledger written after the release. It did not check the `codeRevisions` rows of the same
ledgers. The index read every `codeRevisions` row of every ledger into one table. So a
ledger written after the release could state a revision for a record of another ledger,
a second row for one record replaced the first with no refusal, and a row with a missing
member was a `KeyError` and not a refusal.

**The rule now.** For each ledger written after the release, the index build refuses,
with a `ValueError` that the command reports:

| Case | Refusal |
|---|---|
| `codeRevisions` is absent or is not a list | `a ledger's codeRevisions is not a list` |
| A row is not an object with a `recordId`, a `note` that is not empty, and an `entries` list. The list may be empty: the note then says why the record names no revision | `a codeRevisions row is not an object ...` |
| An entry is not an object with a `value`, a `relation`, a `path`, and a `quote`, each a text that is not empty | `a codeRevisions entry of <record> is not an object ...` |
| A relation is not one of the five published relations | `no code revision relation ...` |
| The row names a record that the same ledger does not add: a record of another ledger, or no record | `... which is not a record that ledger adds` |
| The row names a record that the ledger adds and that did not execute its target behaviour | `... which is not an executed record` |
| A record is read a second time | `records read twice for their code revision` |
| An executed record has no reading | `no ledger reads the code revision of the executed record ...`, which the tool already made |

The same check now refuses a `codeIdentity` row for a record that the ledger adds and
that did not execute its target behaviour. The second commit checked that the ledger
adds the record, and not that the record executed.

The four ledgers inside the released pack are read as before, and the new check does not
read them. The first of them reads 31 records that the migration held and that it does
not add, so the ownership rule cannot apply to it. The released pack is recomputed from
those four ledgers only, and a test changes, removes, and breaks the new ledger's
revision reading and requires the same released pair each time.

**What the check does not do.** It does not check the shape of a ledger's register
changes, which it reads to find the records that the ledger adds: the register rules
check that shape when the changes are applied, and a ledger whose changes are malformed
can still end this check with an error that is not a refusal. It reads
`targetBehaviourExecuted` as the rest of the tool does, as true or false, and does not
require the JSON value `true`. It does not read the cited file. That each quote is in
the file that the row names, and that the record cites that file, is still a test of the
committed ledgers and not a refusal of the build. Among the four released ledgers a
second reading of one record is still not a refusal of the build; a test holds that each
executed record has one reading.

**Tests.** `tests/testing/test_evidence_index.py` gains 41 tests, and the module has 580 with them.
They plant each case of the table on the E01-D registration ledger: the row moved to the
ledger before and to the one two before, with and without the registration ledger's own
row; a row in the registration ledger for a record of a released ledger, for the record
of an earlier post-release ledger, and for no record; the reading removed and repeated;
eight malformed rows; seven malformed entries; three relations outside the published
five; a ledger planted after the registration ledger; a row with no entry and no note;
a reading of an added record that executed nothing. Each of the five published relations
is still accepted, and so is a row with no entry and a note. Run against the tool as the
second commit left it, 34 of these tests fail.

**The review of the third commit.** One automated reviewing session read the staged
change read-only before it was committed. It is another session of the automated
assistant that wrote the change, it is not a person, and its report is not committed.
It found no behaviour change for the released ledgers or the released pack. It found
these, and each is corrected in the same commit:

| Finding | What the draft said or did | Correction |
|---|---|---|
| This section overstated the released ledgers | It said that the four released ledgers read records "that no ledger added". That is true of the first only; the second and third read records that they add | The paragraph names the first ledger and its 31 records |
| A sentence in the tool and in the changelog overstated the identity check | "only for an executed record that it adds", while the `codeIdentity` check did not require that the record executed | The check requires it, and a test plants the case |
| A reading that stated nothing was accepted | A row with no entry and an empty note | The note must not be empty |
| Two tests did not prove their names | One named a ledger after the registration and used the ledger before it; one named the released ledgers and did not build the index with them | The first plants a ledger after the registration; the second builds the index and compares each reading |

The reviewer also listed the unchecked shape of the register changes, which the
paragraph above now states.

**Checks of the third commit.** Run on the same host, from Git Bash, on 2026-10-07.

| Check | Result |
|---|---|
| `ruff format --check .`, `ruff check .`, `mypy` | Exit 0: 653 files, 355 source files |
| `pytest tests/testing/test_evidence_index.py -q` | 580 passed |
| `pytest tests/testing/test_result_review_gate.py -q` | 75 passed |
| `pytest tests/testing/test_evidence_post_release.py -q` | 61 passed |
| `pytest tests/testing/test_experiment_e01.py -q` | 128 passed |
| `tools.evidence_index --check` and `--gate` | Exit 0. Released `v1.0.0` set `1d40b33f...` and pack `652e9051...`, as before |
| `tools.proof_dashboard --check` | Exit 0 |
| `tools.experiment_freeze --check` | Exit 0: 3 freeze records |
| `git diff main -- docs/proof/experiments/v2-e01` | No output: no run, freeze, registry, or review file differs from `main` |
| `git diff --check` | Exit 0 |
| The default lane, `pytest -q`, third run | **0 failed**, 18,987 passed, 36 skipped, 14 deselected, in 48 min 47 s. The skipped and deselected tests are not passes |

After the lane ran, its figures were written into this table, the evidence index was
regenerated, because the new record cites this page, and the two digests on the index
page were updated. The `tests/testing` and `tests/security` suites then ran again and
passed. The hosted checks ran on the second commit before this hardening, and they run
again on the third; this record does not state their result.

## Privacy and publicability

The change adds no host path, no credential, no account identifier, no model artifact,
and no generated text. The identifiers it adds are public: commit names, image digests,
content digests, and a model revision. Each was already in the run directory.

## What this does not establish

- Anything that the run does not establish. The register states the list with the claim.
- That the review of the result was independent of the assistant that drove the run. The
  reviewer is another session of the same automated assistant, and the review record
  states its limits. No person and no outside party reviewed the result.
- That the review of the result covered this claim. The review read a commit that held
  no register statement about the run, and its record says that it does not establish
  that a reconciliation is correct.
- That the review preceded the register change. The review gate reads one repository
  state. Git history shows that the review record merged in pull request 124, before
  this change began; the gate does not read history.
- That the new record's wording is complete. A suite checks that each command, each
  identifier, and each date in it is in a file it cites. Whether its limitations are
  complete is a reading.
- That Sprint 3 is accepted. A collective review reads the sprint again after this
  change merges.
