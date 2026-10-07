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
> published its independent review. It registered no claim. A collective review of
> Sprint 3 on 2026-10-06 found the omission. This change adds the claim on 2026-10-07.
> The register does not state that the registration happened on the day of the run.
>
> **The evidence is `C2`, and it is bounded.** One run, on the `docker-desktop` provider,
> on one cluster with one node, with one contract, one binding, one API replica, one
> runtime replica, and one completion request. It is not representative evidence.

## Why this change exists

The story that ran E01-D requires a claim and register reconciliation of its result.
[The validation record of that change](v2-s3-004-pr2-validation.md) states that the
reconciliation was not done there. The contribution rules ask that the review of a
result merges before the register change for it, in a separate change, because the review
gate reads one repository state. The review merged with the run, so the register change
had to be a later change, and none was planned. The collective review of Sprint 3 found
that the reconciliation was therefore missing from the sprint. It found the freeze inputs, the raw
run, the result classification, and the review record sound, and it stated that the
finding justifies no repeated run. This change is the reconciliation, and it is nothing
else.

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
  record was written.** The limits that the review record and the earlier validation
  record state are carried into the new record's limitations. None of them changes a
  verdict.

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
| GitOps controller | Argo CD `v3.5.3`, core install |
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
> local-docker-desktop binding was accepted into Git at commit
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
  The new register record states these in its limitations.
- **The committed-run check still leaves E01-D out.** `python -m tools.experiment_e01
  --check` judges the two static runs. It does not judge the E01-D run, and its exit
  status says nothing about that run. No runner and no coded analysis exist for E01-D.
  The tests of `tests/testing/test_experiment_e01.py` apply the registered rules to the
  run's files.
- **A new run of any part of E01 is still refused.** `tools/experiment_e01/core.py`, which
  revisions 2 and 3 pin, changed after the E01-D run. This change does not edit that file
  and registers no freeze revision.

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

## What changed

| Area | Files |
|---|---|
| Ledger | `docs/proof/testing/v2-s3-005-pr1-e01-d-registration.v1alpha1.json`, new |
| Register | `docs/testing/claim-evidence-matrix.v1alpha2.json`: the five changes the ledger names |
| Generated | `docs/proof/v1-evidence-index.v1alpha1.json`, `docs/proof/dashboard.md` |
| Tools | `tools/evidence_index`: the ledger path, the code identity rows of a later ledger. `tools/proof_dashboard/core.py`: the new claim in the Kubernetes deployment group |
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
| `pytest tests/testing tests/architecture/test_argocd_bootstrap.py tests/security` | 9,083 passed |
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
this change. The suites named in the table above were.

**What the suites hold for this change.** The review-gate module has 74 tests, 11 of
them new. They plant, for the E01-D run, each refusal that the gate makes: no review
reference, an absent artifact, the review of another run, a run file edited, added, or
removed, and a changed freeze record. The E01 module replaces the test that required the
register to hold no record of the run with six tests that bind the claim to the run, to
revision 3, to the review record, and to its boundary.

**Not run.** No step of E01. No request to a cluster, a registry, or the network. The
hosted checks are read after the change is pushed, and this record does not state their
result.

## Privacy and publicability

The change adds no host path, no credential, no account identifier, no model artifact,
and no generated text. The identifiers it adds are public: commit names, image digests,
content digests, and a model revision. Each was already in the run directory.

## What this does not establish

- Anything that the run does not establish. The register states the list with the claim.
- That the review of the result was independent of the assistant that drove the run. The
  reviewer is another session of the same automated assistant, and the review record
  states its limits. No person and no outside party reviewed the result.
- That the review preceded the register change. The review gate reads one repository
  state. Git history shows that the review record merged in pull request 124, before
  this change began; the gate does not read history.
- That the new record's wording is complete. A suite checks that each command, each
  identifier, and each date in it is in a file it cites. Whether its limitations are
  complete is a reading.
- That Sprint 3 is accepted. A collective review reads the sprint again after this
  change merges.
