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
- **No pinned input of revision 2 moved.**
  `tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json`
  exited 0. So no change since revision 2 is material to the static result, and that
  result is consumed as it is.

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
| [`tests/testing/test_experiment_freeze.py`](../../../tests/testing/test_experiment_freeze.py) | Revision 3's pin, written out. Ten tests of revision 3, and one of an edit to a superseded record. The tests that plant a next revision now plant revision 4 |
| [The experiments page](../experiments/README.md), `CONTRIBUTING.md`, `CHANGELOG.md`, [the proof index](../README.md), the test inventory | Revision 3 described |
| ADR 0018, ADR 0019, [the Application document](../../environment/argocd-application.md) | One dated note each, on the open item that asked for this revision |

No file under `tools/`, `src/`, `charts/`, `gitops/`, `infra/`, or `scripts/` changed. The
freeze checker and the E01 runner are pinned inputs, and neither was edited.

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
- **The verification rules.** For E01-AC8, E01-AC9, and E01-AC10: which file and which
  field is compared with which value.
- **The remaining freeze fields.** The repetition count is unchanged: one deployment and
  one completion. The evidence paths, the abort conditions, and the cleanup are stated
  for this environment. Two abort conditions are added.
- **The pins.** 158 inputs. `inputChanges` classifies the 84 that revision 2 did not pin.
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
  the three digests, and the Application's fields from the committed files. No test
  compares them with the files afterwards: a test that did would fail on a later,
  legitimate change of the release, and the pins already report such a change.
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

Run on 2026-10-06 over the working tree of the first commit of this change.

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
| The default lane, `pytest -q` | 18,787 passed, none failed, 36 skipped, 14 deselected, in 53 minutes 45 seconds |

## What the independent review found

The independent review ran on the staged tree of this commit. The next commit of this
change records what it found and what was corrected.

## Privacy and publicability

The record names one node, one context, and tool versions. It names no host name, no
user name, no local path, no account identifier, and no credential. The repository URL
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
- **That the E01 runner executes revision 3.** It executes revision 2.
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
