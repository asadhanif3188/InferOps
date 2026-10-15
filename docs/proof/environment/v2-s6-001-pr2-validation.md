# V2-S6-001-PR2 validation: the first Q1 qualification

Status: **one qualification executed on the docker-desktop provider and kept. `q1-1`
is `QUALIFIED`: each of the 17 rules of the frozen Q1 record held. Its environment
identity is the selected environment of E02A and E02B. Its evidence level is C2,
bounded to one provider, one node, one Kubernetes version, and one release. It is not
a result of E02 to E06, it derived no bound, and no claim is registered.** The change
also lets the evidence layout check list a Q1 qualification, which has no
ExperimentRun manifest.

| Property | Value |
|---|---|
| Branch | `test/v2-s6-001-q1-environment-result` |
| Base | `08b89144f76d86cbbcf44de8845d04f018c88453`, the merge of `V2-S6-001-PR1` |
| Freeze record | [`v2-q1/freeze-r1.v1alpha1.json`](../experiments/v2-q1/freeze-r1.v1alpha1.json), revision 1, unchanged by this change |
| Driver | [`v2-q1/procedure/q1-driver.txt`](../experiments/v2-q1/procedure/q1-driver.txt), unchanged by this change |
| Qualification | [`q1-1`](../experiments/v2-q1/runs/q1-1/result.md), `QUALIFIED` |
| Provider | `docker-desktop`, Kubernetes `v1.36.1`, one node |
| Release | `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`, delivered by the Application from `main` at `08b8914` |
| Environment | `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461` |

## What the story asks of this change

Story `V2-S6-001` selects one real environment for the controlled comparison of E02A
and E02B, or keeps a bounded refusal. `V2-S6-001-PR1` froze the qualification. This
change runs it once on the intended local environment, at an exact revision, and
records `QUALIFIED` or `REFUSED`. It may not weaken a replica count, a request, a
limit, or a bound to pass, and it reconciles only the qualification's own evidence.

## The sequence

1. **No tracked file was edited before the qualification.** The branch was created at
   `08b8914`, which was also the remote main. The phases ran from that tree with a clean
   working tree, so the executing commit and the desired revision are the same commit.
2. **The phase `up`** ran from 07:04:55Z to 07:17:45Z and exited 0, with no refusal. Both
   capacity readings were `ACCEPTED`. The API image was built from the engine's cache,
   and the import of the model seed image into the node took 258.2 s, as the transcript
   states.
3. **The phase `qualify`** ran `q1-1` from 07:18:00Z to 07:22:24Z and exited 0. The tool
   exited 0, and the driver printed the result `QUALIFIED` and the 17 rules, each
   `held`.
4. **The phase `down`** ran after it and ended at 07:25:04Z. The namespaces and the
   custom resource definitions equal those read before anything was installed, and no
   persistent volume remains.
5. **Then the run directory was assembled and the code and pages were edited**, in that
   order. Nothing was run again. One identifier was used, and the next qualification,
   if one runs, takes `q1-2`.

## What this change adds

1. **The qualification directory**, `docs/proof/experiments/v2-q1/runs/q1-1/`: every
   file that the phase `qualify` wrote, the record that the tool built, the transcript of
   the three phases, and [the run page](../experiments/v2-q1/runs/q1-1/result.md), with
   one read left out (below).
2. **A status of the layout check for a qualification.** `tools/experiment_evidence`
   refused the committed directory with `evidence-manifest-missing`, because a
   qualification has no ExperimentRun manifest. `V2-S6-001-PR1` said where a
   qualification is committed and did not foresee this. The `repository` command now
   lists each directory of `docs/proof/experiments/v2-q1/runs/` as `qualification`,
   applies the credential-prefix rule and the personal-path rule to each of its files,
   refuses a link, a file that is not UTF-8 text, and a corrections directory of one,
   and still refuses a directory with no manifest under the `runs` directory of any other
   experiment. Five new tests, seven cases with the parametrized one, and the two
   existing tests of the repository listing hold it.
3. **The suites and the pages.** The Q1 suite holds that `q1-1` is the one committed
   qualification, that `--check` builds its record again, and that the record is
   `QUALIFIED` with every rule held. The test that no tracked file declares an Argo CD
   custom resource except the two committed manifests names, by exact path, the
   evidence files that hold the Application as a cluster returned it; it now names the
   five reconciliation samples of `q1-1` beside the one file of the E01-D run. The pages that said that no qualification had run
   now say that one ran, each with a dated note.

## Decisions this change makes

- **The capacity gate's read of every pod is not committed.** `capacity/pods.json`
  holds container paths under a home directory in the controller's pods, and the
  publication check refuses such a file. The file was not edited. Its SHA-256 with LF
  is `6f695f25d46e24bbb53a7efc94af8ae745f51032ffbe3e46e4770bcd9d9d2ccd`. Q1 reads the
  stored capacity record, so `--check` is unaffected; the capacity record cannot be
  built again from the directory. The same read was left out of the second capacity
  reading of `V2-S4-005-PR2`, for the same reason.
- **The transcript is edited in three ways, and no other file is.** Terminal colour
  codes are removed, the absolute path of the host is written as `<repository>` on two
  lines, and trailing whitespace is removed from six lines. No tool reads the
  transcript.
- **The layout tool is edited, and the Q1 freeze record is not.** The three files of
  `tools/experiment_evidence` are pinned inputs of both revisions of the Sprint 5
  integration validation and of no revision of Q1. So `experiment_freeze --changes`
  of Q1 revision 1 still says `UNCHANGED`, and a later qualification can run under it.
  The same command now lists three moved pins for Sprint 5 revision 2, and seven for
  revision 1, four of which revision 2 already classified. Both attempts of that
  validation are finished; a later attempt would need a revision that classifies the
  three files. The layout check holds a run's freeze record by its content digest, not
  by its material files, so both attempts still conform.
- **No claim is registered.** The freeze record says that no claim cites a
  qualification, and a register change that bears on a run needs a review record of
  that run first. A qualification is a prerequisite of the reliability experiments and
  raises the level of no claim.
- **No environment decision record is made.** The freeze record asks for one only when
  the local environment is `REFUSED`.

## Parent-story acceptance

| Criterion | State after this change |
|---|---|
| Q1 verifies exact code, release, model, runtime, and provider identities and target topology readiness | **Held, for `q1-1`.** Rules `Q1-AC1` to `Q1-AC16` held. The record states the executing commit and desired revision `08b8914`, release `b5457f49…c9db`, chart `0.6.0`, the API image digest built at the commit, the pinned runtime image and model, controller `v3.5.3`, provider docker-desktop at `v1.36.1`, and 2 API and 2 runtime replicas Ready with 2 Ready endpoints each |
| The local environment is explicitly `QUALIFIED` or `REFUSED` | **Held.** `QUALIFIED` |
| A refusal is preserved and not converted into a weaker target configuration | **Held, and not exercised.** No refusal occurred. The driver changed no replica count, request, limit, or bound of the qualified release: its one Helm value is the acquisition job memory limit of the preparation release, which was removed before the apply. The qualification ran once |
| The selected environment is identical for E02A and E02B | **The environment is selected; the identity comparison is pending.** `q1-1` states the identity and its digest, and the freeze record requires E02A and E02B to share it. No freeze record or run of either exists, and no tool compares two identities yet: that belongs to the work that freezes and runs them |

## Evidence level and limitations

C2: a real cluster, the delivery controller, the real runtime, and the real model, on
one provider and one node. The limitations of the freeze record apply as stated there.
In addition:

- **One qualification.** It shows that the environment held the topology once, at one
  time. It does not show that it holds it on another day or after the host restarts.
- **The capacity margin was 260,870,144 bytes of memory limits.** A change to the
  release that adds memory limits, or a change to the host's memory, can change the
  result.
- **The model cache record is `INCONCLUSIVE`, by design.** Q1 reads 15 of its 17
  rules, as frozen.
- **The startup probe of each API pod failed once, and that of each runtime pod twice,
  before each became Ready.** No pod restarted. Q1 reads readiness and not the start.
- **The images were cached.** The phase `up` built the API image from the engine's
  cache and loaded the two images. A host without them takes longer; the bounds of the
  driver were not approached.

## Validation

Each command ran on the Windows host from Git Bash, at the tree of the first commit of
this change, except the default lane, which ran before the correction of one test that
it found (below).

| Command | Result |
|---|---|
| `bash docs/proof/experiments/v2-q1/procedure/q1-driver.txt up q1run-1` | `driver exit 0`, no `upRefusal` |
| `bash docs/proof/experiments/v2-q1/procedure/q1-driver.txt qualify q1run-1 q1-1` | Tool exit 0, `result: QUALIFIED`, 17 rules held |
| `bash docs/proof/experiments/v2-q1/procedure/q1-driver.txt down q1run-1` | `driver exit 0`; the namespaces and the custom resource definitions equal those before the run |
| `uv run --locked python -m tools.environment_qualification --check` | `PASSED: 1 committed qualification(s), each record is what its directory gives` |
| `uv run --locked python -m tools.experiment_evidence repository` | `runs       6: 3 pre-schema and not checked, 1 qualification(s) with the text rules only, 2 conforming, 0 refused` |
| `uv run --locked python -m tools.experiment_run repository` | `manifests  5: 3 pre-schema, 2 conforming, 0 refused`, unchanged |
| `uv run --locked python -m tools.analysis_replay repository` | `runs        5: 3 pre-schema and not replayed, 0 with no analysis, 2 replayed, 0 refused`, unchanged |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 6 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes` of Q1 revision 1 | `UNCHANGED` |
| `uv run --locked python -m tools.experiment_freeze --changes` of Sprint 5 revision 2 | 3 moved pins, the files of `tools/experiment_evidence`, as stated above |
| `uv run --locked python -m ruff check .`, `ruff format --check .` | Passed |
| `uv run --locked python -m mypy`, and with `--platform linux` | No issue in 418 source files, on each platform |
| Targeted suites: `tests/domain/test_environment_qualification.py`, `tests/testing/test_experiment_evidence_layout.py`, `tests/testing/test_experiment_freeze.py`, `tests/testing/test_analysis_replay.py`, `tests/testing/test_experiment_e01.py`, `tests/testing/test_experiment_review.py`, `tests/testing/test_test_inventory.py`, `tests/domain/test_renderer_input_boundary.py`, `tests/contracts/test_experiment_run_v1alpha1.py`, `tests/testing/test_document_links.py`, `tests/security/test_security_baseline.py`, `tests/testing/test_test_strategy.py`, `tests/architecture/test_argocd_bootstrap.py` | 4,686 passed, 3 skipped |
| `uv run --locked python -m pytest -q`, before the first commit | 22,486 passed, 39 skipped, 14 deselected, 2 failed, in 60 min. Both failures are stated below |
| `git diff --check` of the staged change | Clean |
| A search of the diff for host paths, account identifiers, credentials, and private planning references | No match. The public repository URL and the names of Kubernetes fields and of one secret reference in the controller's pods occur in the collections, as in earlier runs |

Not run: `shellcheck`, which is not installed on this host. The hosted CI lanes were
not observed.

### What the default lane found before the first commit

- **A guard test refused the committed reconciliation samples.**
  `test_no_application_set_and_no_cluster_registration_is_committed` reads every
  tracked file for an Argo CD custom resource and allows the two committed manifests
  and one evidence file by path. The five `reconciliation/sample-00N.application.json`
  files of `q1-1` are the Application as the cluster returned it, so they matched. The
  targeted suites had not run that module. The test now names them, and it still holds
  that each is under the proof records, carries a status and an identifier that only a
  cluster writes, is the committed Application, and holds no cluster secret type.
- **One test of the bootstrap procedure exited 141 once.**
  `test_install_creates_the_marked_namespace_and_then_applies` runs the procedure
  against stubs, and its script ended with status 141, a broken pipe, while the lane
  ran. It passed alone, and this change touches neither the procedure nor its suite.
  The earlier record of `V2-S6-001-PR1` states a similar failure of a stub run in
  another procedure suite.
