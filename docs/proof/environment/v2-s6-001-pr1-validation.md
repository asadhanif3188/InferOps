# V2-S6-001-PR1 validation: the frozen Q1 qualification workflow

Status: **the Q1 workflow is frozen, and no qualification ran. This change adds the
freeze record, the driver, and the tool that decides `QUALIFIED` or `REFUSED`. Every
directory the tool was given is synthetic, so the evidence level is C0. No cluster was
read, no image was built, and nothing was installed. No environment is qualified or
refused by this change, and no claim is registered.**

| Property | Value |
|---|---|
| Branch | `test/v2-s6-001-q1-qualification-workflow` |
| Base | `78f936900597bdf58b6d6cdd7bf145acd7482def`, the merge of `V2-S5-006-PR1` |
| Freeze record | [`v2-q1/freeze-r1.v1alpha1.json`](../experiments/v2-q1/freeze-r1.v1alpha1.json), registered by this change |
| Driver | [`v2-q1/procedure/q1-driver.txt`](../experiments/v2-q1/procedure/q1-driver.txt), a pinned input of the record |
| Tool | [`tools/environment_qualification`](../../../tools/environment_qualification/core.py) |
| Page | [Q1: the environment and identity qualification](../../environment/environment-qualification.md) |
| Suite | [`tests/domain/test_environment_qualification.py`](../../../tests/domain/test_environment_qualification.py) |

## What the story asks of this change

Story `V2-S6-001` selects one real environment for the controlled comparison of E02A
and E02B, or keeps a bounded refusal. This change is its first part: it fixes the
qualification mechanism before any qualification runs. The second part runs Q1 on the
intended local environment and records the result.

Q1 confirms the exact identities that a result-bearing run records, that two API
replicas and two runtime replicas become Ready, that both runtime replicas verify the
same model, that the Service endpoints reflect the expected replicas, that the delivery
controller reconciles the desired state, and that the caller runner completes real
requests. The result is `QUALIFIED` or `REFUSED`.

## What this change adds

1. **The tool.** `python -m tools.environment_qualification DIRECTORY` reads the
   directory that the driver writes and prints one record. It contacts no cluster. It
   reads the stored records of five existing tools by their schema names, the
   Deployments as one `kubectl get`, and the caller record, which it gives to the
   reader of the runner with its plan. It imports none of the tools whose names the
   renderer input boundary reserves, and it names no controller. 17 rules, each with
   one refusal category. The record states the identities that a result-bearing run
   records, and an environment identity with its SHA-256.
2. **The driver.** Three phases, `up`, `qualify`, and `down`. It runs the existing
   operating procedures and collectors in a fixed order, keeps a refusal of the target
   check as its category only, and reads no cluster state after a refusal of `up`, a
   dirty working tree, a changed material file, or delivery paths that differ from the
   desired revision. It states no result.
3. **The freeze record.** Experiment `v2-q1-environment-qualification`, revision 1, one
   part, `Q1`, at C2. Its 17 acceptance criteria are the 17 rules, with the same
   statements, and a test holds them equal. Its material scope is the import closure
   of the nine tools that the driver runs, the driver, the nine procedures that it
   calls, the in-cluster runner file, the caller profiles, the model and runtime pins,
   the chart, the desired-state tree, the controller manifests, the Terraform
   prerequisite layer, the image build files, the `inferops` package, and the
   dependency lock. The pins were computed with the freeze tool's own
   `material_files`.
4. **The suite, the page, and the indexes.** The suite gives the tool a qualified
   directory and one defect for each rule. The page states each rule.

## Decisions this change makes

- **The target is a constant.** The release key, 2 API replicas, 2 runtime replicas,
  the provider `docker-desktop`, and the pinned model are constants of the tool. The
  command has no option for any of them. A source record of one runtime replica is
  refused, so a refusal cannot become a qualification of a weaker target.
- **Q1 reads the capacity reading taken before the apply.** The capacity gate refuses
  a cluster that already holds the release. The driver takes it after the controller
  is installed and before the Application is applied.
- **Q1 reads 15 of the 17 rules of the model cache record.** The other two state the
  V1 multi-replica capacity preflight and samples of the start. Q1 runs neither, so
  that record can be `INCONCLUSIVE` while its model identity rules are held. The V2
  capacity gate decides capacity.
- **A target refusal is kept as a category.** The message of the target check can
  name a context, and a context name can hold an account identifier.
- **The tool does not build the source records again.** It reads the stored records.
  Building the provenance record and the provenance comparison of the reconciliation
  record again needs Git objects of the desired revision, which a shallow clone does not
  hold, and the tools of three of the five records are ones that the renderer input
  boundary reserves, so the tool may not import them. The capacity record and the
  endpoint record could be built again without either obstacle; the tool reads them as
  stored too, so that every source is read one way. The page and each record state this
  limit. The caller record is the exception: the tool gives it to the reader of the
  runner with its plan.

## Parent-story acceptance

| Criterion | State after this change |
|---|---|
| Q1 verifies exact code, release, model, runtime, and provider identities and target topology readiness | **Mechanism frozen; not executed.** Rules `Q1-AC1` to `Q1-AC16` decide it. The run is the second part |
| The local environment is explicitly `QUALIFIED` or `REFUSED` | **Pending.** The tool states one of the two. No qualification ran |
| A refusal is preserved and not converted into a weaker target configuration | **Mechanism frozen.** The target is a constant, the driver changes no replica count, request, limit, or bound, and the repetition rule of the record keeps every qualification. Tests hold the constants and the driver text |
| The selected environment is identical for E02A and E02B | **Pending.** A record states the environment identity and its digest, and the record's selection rule requires E02A and E02B to share it. No run of either exists, and no comparison of identities was made |

## Evidence level and limitations

C0. Every directory is synthetic. The figures in it are invented, except the pinned
model, the pinned runtime image, and the RP-1 profile, which are the committed files.
The caller records were written by the loop of the runner against scripted answers.
The driver was checked with `bash -n` only. It was not executed.

## Validation

Each command ran on the Windows host from Git Bash, at the tree of the first commit
of this change, before the independent review.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 22,453 passed, 39 skipped, 14 deselected, **1 failed**: `tests/architecture/test_argocd_application_procedure.py::test_a_live_object_that_is_not_the_committed_one_is_a_finding[project-pin-apply]`, whose stub run printed nothing. The whole module then passed alone, 121 passed. This change edits no file that the module reads. The failure is stated as a flake of a stub run on this host, and not as a pass |
| `python -m pytest tests/domain/test_environment_qualification.py tests/testing/test_experiment_freeze.py tests/testing/test_analysis_replay.py tests/testing/test_experiment_e01.py tests/testing/test_experiment_review.py tests/testing/test_test_inventory.py tests/domain/test_renderer_input_boundary.py tests/architecture/test_argocd_bootstrap.py tests/domain/test_generated_release_drift.py -q` | 2,366 passed, 3 skipped |
| `python -m pytest tests/domain/test_environment_qualification.py tests/testing/test_document_links.py -q` | 439 passed |
| `uv run --locked python -m ruff check .`, `ruff format --check .` | Passed; 757 files formatted |
| `uv run --locked python -m mypy`, and with `--platform linux` | No issue in 418 source files, on each platform |
| `python -m tools.experiment_freeze --check` | `PASSED: 6 freeze record(s), every rule held` |
| `python -m tools.experiment_freeze --changes` of the Q1 record and of Sprint 5 revision 2 | Unchanged |
| `python -m tools.experiment_freeze --changes` of E01 revision 3 | 30 moved pins, each of a file that this change does not touch. They moved in earlier merged changes |
| `python -m tools.environment_qualification --check` | `PASSED: 0 committed qualification(s)` |
| `bash -n docs/proof/experiments/v2-q1/procedure/q1-driver.txt` | No syntax error |
| `git diff --check` | Clean |
| A search of the diff for host paths, account identifiers, credentials, and private planning references | No match |

Not run: the driver itself, any cluster read, any image build, and `shellcheck`, which
is not installed on this host. The hosted CI lanes were not observed.

## What the independent review found

The independent review runs after the first commit of this change. The commit that
follows it records what the review found here.
