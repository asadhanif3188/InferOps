# V2-S3-004-PR2 validation

Date: 2026-10-06

What this change executed, what it checked before and after, and how. The change adds
one run of part E01-D of V2-E01, under
[revision 3 of the freeze record](../experiments/v2-e01/freeze-r3.v1alpha1.json), and it
changes the committed-run check after that run.
[The experiments page](../experiments/README.md#the-e01-d-run) describes the run.

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
> **No code judged the run.** The automated assistant session that drove the run applied
> the registered verification rules. It is not independent of the run.
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
| The E01-D tests of [`tests/testing/test_experiment_e01.py`](../../../tests/testing/test_experiment_e01.py) | `C0` | Nothing of the experiment. They read the committed files of the run and revision 3 |
| The other tests of that module and [`tests/testing/test_experiment_freeze.py`](../../../tests/testing/test_experiment_freeze.py) | `C0` | The E01 runner and the freeze check, in temporary repositories. A test execution is not result evidence |

The levels are defined in [the evidence levels](../../testing/evidence-levels.md).

## Eligibility, checked before the run

| Condition | How it was checked | Result |
|---|---|---|
| Revision 3 is merged and registered | `git log` on `main`; the registry row; `tools.experiment_freeze --check` | Merged by pull request 123 as `ad725905`. Registered with the digest `b4aa013d…`. Exit 0 |
| Revision 3 supersedes the latest merged revision | `metadata.supersedes` of revision 3 | It names revision 2 by path and digest |
| No experiment-path change merged since revision 3 | `tools.experiment_freeze --changes` for revision 3, in step P2 of the run | Exit 0: every material file matches. The executing commit is the commit that merged revision 3 |
| The working tree was clean, and `main` on the remote named the executing commit | Step P1 of the run | The status printed nothing. Both commits are `ad725905a7838e8210e54a29de7913bc0c7c49e5` |
| The environment is the one that revision 3 names | Step P3 of the run: thirteen attributes compared | Each is equal. `environment.json` holds the comparison |
| The review gate of the earlier corrective change is merged | `tools.evidence_index --gate`; the gate's suite | Present. Exit 0 |
| The run is authorized | The maintainer asked for this change, whose purpose is the run | The environment names no paid provider. The model was not downloaded by a registered step: the claim was filled from a seed image on the host |

Before the driver started, the cluster was read with read-only requests, and the two
freeze commands and the desired-state check were run once by hand. Each read gave what
the run then recorded. These reads deployed nothing and sent no request. The driver's
three inline Python passages were compiled, and the one that summarises the completion
was run on a response file written by hand, outside the repository. No step of the part
was executed before the run, and no rehearsal took place.

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
| Apply returned, rollouts complete | 12:13:19Z, 12:13:37Z: 18 seconds, against a deadline of 600 seconds |
| Readiness request | One. HTTP 200 |
| Completion request | One, no retry. HTTP 200, one choice, assistant message of 6 characters, model `qwen3-1-7b-q8-0` |
| Parameters supplied | One: `api.image.digest` |
| Abort conditions met | None |
| Cleanup | Each removal ended with exit status 0. The namespaces and the custom resource definitions after the run equal those of step P3 |

| Criterion | Verdict | Rests on |
|---|---|---|
| E01-AC8 | Holds | `completion.json`; the rules of E01-AC9 |
| E01-AC9 | Holds | `argo.json`, `provenance.json`, `release.json`, `pods.json`, `completion.json` |
| E01-AC10 | Holds | `argo.json`, the committed Application manifest, three tests in the transcript, and the consumed static result |

**How the verdicts were applied.** The session that drove the run compared each value
that a rule names, with a script that is not committed. The manifest states every
compared value beside its rule, so a reader can compare them again from the files. The
default-lane suite holds those values to the cited files. It does not judge the run.

**What the driver added to the registered commands.** The driver's header lists each
addition: the date and the tool versions, a read of the custom resource definitions in
step P3, the digest of the model seed image, a wait of at most 30 seconds for the
port-forward before the one readiness request, a read of the revision that Argo CD
reports after the apply, the removal of carriage returns from two redirected records,
and a print of the pod phases. None of them sends a request to the release, and none
changes an object.

## One observation outside the criteria

The API pod requested the image by the digest that the run supplied, `sha256:dfb772f2…`.
Its container status reports the image identity `localhost/inferops-api@sha256:8d2b578c…`.

After the run, one read-only command asked the node's image store:
`docker exec desktop-control-plane crictl inspecti` for the supplied digest. It returned
the image identifier `sha256:1205e5a1…` with both digests in `repoDigests`. That
identifier is the configuration digest that the build of step P4 exported, as the
transcript shows. Every layer of that build came from the build cache. The earlier digest
is of a build before this run, which the node still held.

- This read is not a registered step, and its output is not in the transcript.
- The pod status alone does not show which digest the container was started from.
- No E01-D criterion names the API image digest. The rule of E01-AC10 compares the
  parameter on the Application with the digest of step P4, and they are equal.

## The committed-run check, changed after the run

`tools.experiment_e01 --check` read every directory under `runs/` as a static run. It
returned one finding for the E01-D directory: the manifest names no revision that the
analysis knows. Revision 3 states this, and leaves the correction to the change that
commits the run.

The edit is one function, `committed_runs`, and one pattern. The listing leaves out a
directory named `YYYYMMDD-e01-d-N`. Every other directory is still listed.

| Consequence | Evidence |
|---|---|
| One pinned input of revisions 2 and 3 differs from its pin | `tools.experiment_freeze --changes` reports `tools/experiment_e01/core.py` for each record and exits 1 |
| A new run of any part is refused | The precondition of both records. This change registers no revision and classifies nothing |
| The E01-D run is not affected | It executed before the edit, and its step P2 reports no difference. Its steps do not run the runner |
| Thirteen tests failed with the edit and no other change | They build temporary repositories from the runner in the tree and the pins of revision 2 |
| The suites now rebuild the pinned runner | [`tests/support/e01_pinned_runner.py`](../../../tests/support/e01_pinned_runner.py) puts back the two passages that the edit replaced, and requires the digest that both records pin |
| The listing is the only difference from the pinned runner | The same requirement. Another edit to the runner fails it |

The temporary repositories of the suites therefore hold the pinned runner, not the runner
in the tree. Most of those tests import the runner in the tree and point it at the
temporary repository. One test starts the temporary repository's own runner: it executes
the pinned content.

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

Run on 2026-10-06, after the run and the edit.

| Check | Result |
|---|---|
| The driver | Exit 0. Every command in the transcript ended with exit status 0 |
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
| The default lane, `pytest -q` | 18,801 passed, none failed, 36 skipped, 14 deselected, in 33 minutes 11 seconds. Documents were edited while it ran |
| The document, evidence, security, and scaffolding suites, and the Application suite, on the final tree | 9,260 passed, none failed, in 4 minutes 8 seconds |

**The lane did not run over one fixed tree.** It started after the runner edit, the
support module, and the tests were written. The experiments page, the changelog, the
test inventory, three other documents, and this page were written while it ran. The
second row is the suites that read those documents, run again over the staged tree of
this commit. No whole lane ran over that tree.

## Privacy and publicability

- The transcript is the driver's output with three kinds of text replaced: 486 terminal
  colour codes removed, three occurrences of the repository's absolute path on the host
  replaced by `<repository>`, and two Docker build links replaced by
  `<build details link>`. The unredacted transcript is not committed.
- `completion.json` holds the length of the assistant message and not its text. The
  response body is not committed.
- `argo.json` and `pods.json` are the objects as the cluster returned them. They hold
  cluster-internal addresses, object identifiers, and image references. They hold no
  Secret value: the pods mount no Secret that the run read, and the Application holds no
  credential.
- The files name one node, one context, tool versions, and the public repository URL.
  They name no host name, no user name, no account identifier, and no local path.
- The diff was searched for drive-letter paths, home directories, private planning file
  names, and the identifiers of other changes.

## What this does not establish

- **Behaviour on another provider, Kubernetes version, node count, or storage class.**
- **That a second request is answered, or any latency, throughput, capacity, or
  availability.** The run sent one request.
- **A caller outcome from a sync state or a health state.**
- **That Argo CD applies a later commit of `main`.** The run observed one commit.
- **That no model download happened in the run.** No step observes it.
- **That the acquisition hook fills an empty claim.**
- **That the verdicts are independent.** The session that drove the run applied them.
- **That the E01-D run is judged again by code.** No command does that.
- **That a new static run would pass.** It is refused until a later revision classifies
  the runner edit.
- **Reliability under failure, or production readiness.**

## Acceptance

| Criterion | Status |
|---|---|
| An E01-D freeze revision merges before the result-bearing run | Reached by the earlier change of this story. The run executed at the commit that merged it |
| The exact contract is validated and rendered from a clean revision | Reached: step D1 derived the release at the executing commit, from a clean tree, and it equals the release in Git |
| The generated desired state is accepted in Git and reconciled by Argo CD | Reached on one provider: `argo.json` |
| A real model completion returns through the supported API | Reached once: `completion.json` |
| The contract, render, Git, runtime, model, and environment identities are recorded | Reached: the run's manifest and its files |
| The evidence is C2 and bounded to the executed environment | Reached. The run record states the bound |
