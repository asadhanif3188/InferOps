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

The story asks that Q1 confirm the exact identities that a result-bearing run
records, that two API replicas and two runtime replicas become Ready, that both runtime replicas verify the
same model, that the Service endpoints reflect the expected replicas, that the delivery
controller reconciles the desired state, and that the caller runner completes real
requests. The result is `QUALIFIED` or `REFUSED`.

## What this change adds

1. **The tool.** `python -m tools.environment_qualification DIRECTORY` reads the
   directory that the driver writes and prints one record. It contacts no cluster. It
   reads the stored records of five existing tools by their schema names, the
   Deployments as one `kubectl get`, the caller record, which it gives to the
   reader of the runner with its plan, and copies of the two pin files, which it
   holds to the content that the freeze record pins. It imports none of the tools whose names the
   renderer input boundary reserves, and it names no controller. 17 rules, each with
   one refusal category. The record states the identities that a result-bearing run
   records, and an environment identity with its SHA-256.
2. **The driver.** Three phases, `up`, `qualify`, and `down`. It runs the existing
   operating procedures and collectors in a fixed order, keeps a refusal of the target
   check as its category only, keeps the reason of a refusal or a failure of `up` as
   `upRefusal`, and reads no cluster state after one, after a dirty working tree, a
   changed material file, or delivery paths that differ from the desired revision. It
   keeps the record whether the result is `QUALIFIED` or `REFUSED`. It states no
   result.
3. **The freeze record.** Experiment `v2-q1-environment-qualification`, revision 1, one
   part, `Q1`, at C2. Its 17 acceptance criteria are the 17 rules, with the same
   statements, and a test holds them equal. Its material scope is the import closure
   of the nine tools that the driver runs, the driver, the nine procedures that it
   calls and the bootstrap record of the controller, the in-cluster runner file, the
   caller profiles, the model and runtime pins, the chart, the desired-state tree with
   the contract and the environment binding it is rendered from, the controller
   manifests, the Terraform
   prerequisite layer, the image build files, the `inferops` package, and the
   dependency lock: 189 files. The pins were computed with the freeze tool's own
   `material_files`.
4. **The suite, the page, and the indexes.** The suite gives the tool a qualified
   directory and one defect for each rule. The page states each rule.

## Decisions this change makes

- **The target is a constant.** The release key, 2 API replicas, 2 runtime replicas,
  and the provider `docker-desktop` are constants of the tool. The model and the
  runtime image are the ones that the two pin files pin, and the freeze record pins
  each of those files by content. The command has no option for any of them. A
  source record of one runtime replica is refused, so a refusal cannot become a
  qualification of a weaker target.
- **The pins are read from the directory.** The driver copies the two pin files into
  the directory, and the tool holds each copy to the content that the freeze record
  pins. So `--check` builds a committed record again after a later change of a pin
  in the checkout, such as the rotation of the runtime image pin.
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
| A refusal is preserved and not converted into a weaker target configuration | **Mechanism frozen.** The target is a constant. The driver changes no replica count, request, limit, or bound of the qualified release; its one Helm value is the acquisition job memory limit of the preparation release, which is removed before the apply. It keeps the reason of a refusal of `up` and the record of a refused qualification. The repetition rule of the freeze record keeps every qualification. Tests hold the constants and the driver text. The driver did not run |
| The selected environment is identical for E02A and E02B | **Pending.** A `QUALIFIED` record states the environment identity and its digest, and the freeze record's selection rule requires E02A and E02B to share it. No tool compares two identities yet, no freeze record of E02A or E02B exists, and no run of either exists |

## Evidence level and limitations

C0. Every directory is synthetic. The figures in it are invented, except the pinned
model, the pinned runtime image, and the RP-1 profile, which are the committed files.
The caller records were written by the loop of the runner against scripted answers.
The driver was checked with `bash -n` only. It was not executed.

## Validation

Each command ran on the Windows host from Git Bash, at the tree of the second commit
of this change, after the corrections of the independent reviews.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 22,476 passed, 39 skipped, 14 deselected, 0 failed |
| `python -m pytest tests/domain/test_environment_qualification.py tests/testing/test_experiment_freeze.py tests/testing/test_analysis_replay.py tests/testing/test_experiment_e01.py tests/testing/test_experiment_review.py tests/testing/test_test_inventory.py tests/domain/test_renderer_input_boundary.py tests/architecture/test_argocd_bootstrap.py tests/domain/test_generated_release_drift.py -q` | 2,387 passed, 3 skipped |
| `python -m pytest tests/domain/test_environment_qualification.py tests/testing/test_document_links.py -q` | 461 passed |
| `uv run --locked python -m ruff check .`, `ruff format --check .` | Passed |
| `uv run --locked python -m mypy`, and with `--platform linux` | No issue in 418 source files, on each platform |
| `python -m tools.experiment_freeze --check` | `PASSED: 6 freeze record(s), every rule held` |
| `python -m tools.experiment_freeze --changes` of the Q1 record and of Sprint 5 revision 2 | Unchanged |
| `python -m tools.experiment_freeze --changes` of E01 revision 3 | 30 moved pins, each of a file that this change does not touch. They moved in earlier merged changes |
| `python -m tools.environment_qualification --check` | `PASSED: 0 committed qualification(s)` |
| `bash -n docs/proof/experiments/v2-q1/procedure/q1-driver.txt` | No syntax error |
| `git diff --check` | Clean |
| A search of the diff for host paths, account identifiers, credentials, and private planning references | No match |

At the first commit, before the reviews, the default lane gave 22,453 passed, 39
skipped, and 1 failed: a stub run of `tests/architecture/test_argocd_application_procedure.py`
printed nothing, and that module then passed alone, 121 passed. The lane at the second
commit had no failure.

Not run: the driver itself, any cluster read, any image build, and `shellcheck`, which
is not installed on this host. The hosted CI lanes were not observed.

## What the independent review found

Two independent reviews read the first commit, `7d3d19b`: one of the code, the
driver, and the suite, and one of the pages against the code. Neither found a way to
a false `QUALIFIED`. Each finding below is what the first commit got wrong, and the
second commit corrects it. No qualification ran before or after the correction, so
revision 1 of the freeze record was corrected in place before any run used it, and
its registry pin moved with it.

**The review of the code** (one high, four medium, seven low):

- **High: a refused qualification kept no record.** The driver wrote the record only
  when the tool exited 0, and the tool exits 5 when the result is `REFUSED`. So every
  refusal ended with no record, against the one property that Q1 exists to keep. The
  driver now keeps the record for exit 0 and exit 5, and a test holds that text.
- **Medium: a time that is not a date raised an error.** A value such as month 13
  matched the pattern and then raised in the parser, so the tool printed a traceback
  and no record. It now reads such a value as not read. A tier or a rule identifier
  that is not text raised too; it is now left out. A test holds each case.
- **Medium: a `QUALIFIED` record could state no environment identity.** No rule
  required it, while the freeze record says that a `QUALIFIED` record states it.
  `context-unambiguous` now requires a readable identity.
- **Medium: a refusal of the phase `up` left no qualification directory.** The phase
  `up` refused a dirty working tree, a delivery-path difference, a changed material
  file, and a cluster that already held the release before it wrote its start time,
  so `qualify` could not run. The phase now writes its start time first and keeps
  each reason as `upRefusal`, which five rules read. The first commit said that
  `qualify` writes a `REFUSED` record in those cases; that was true only when the
  fault appeared after `up`.
- **Medium: a reused identifier copied the collections of an earlier qualification.**
  The collectors name their directories by the identifier. `qualify` now refuses an
  identifier that a collector already used.
- **Low:** a provenance comparison of two absent revisions read as agreement (it now
  requires the revision); only the first reconciliation sample was held to the end
  of the qualification (the last is held too); a failed read of the namespaces did
  not refuse (it refuses now); the bootstrap record of the controller was not pinned
  (it is pinned now). Two were left as they are: a provenance refusal is stated as
  an absent file, with its message in the transcript, and the driver's direct
  commands name the context, as the earlier drivers do (stated below). The size of
  the tool module was noted and not changed: earlier tools of this repository have
  modules of that size.

**The review of the pages** (three high, six medium, nine low):

- **High: "the driver changes no limit" was false.** The preparation release, which
  is removed before the apply, raises the memory limit of its acquisition job. The
  pages now say that the driver changes no replica count, request, limit, or bound
  of the qualified release, and name that one value. The test that claimed to hold
  requests and limits checked neither; it now holds that the driver sets exactly
  that one value, on the preparation release, before the apply.
- **High: the freeze record said that the target check runs before each read and
  each mutation.** It runs inside each operating procedure. The driver's direct
  kubectl and Helm commands name the context and run none. The record now says so,
  and states it as a limitation.
- **High: `--check` could not build a committed record again after a pin moves.**
  The tool read the model pin and the runtime image pin from the checkout, and the
  runtime image pin is due to rotate. The driver now copies both files into the
  directory, and the tool holds each copy to the content that the freeze record pins.
- **Medium:** "the model is a constant of the tool" was false (it is the pinned file);
  `Q1-AC17` said "each other reading" while the tool read four instants (the
  statement now names them, and the last sample is read too); "a later run compares
  its identity" stated a rule as a fact while no tool compares (the pages now say
  that no tool compares yet); the first commit published how later qualification
  work divides the bounds, which is not implementation of this change (the pages now
  say "later work"); the count of one validation command was 439 where a clean run
  gives 440 (the commands were run again for this commit, below); `files` was said to
  list each file that the tool read, while it lists the files of the directory.
- **Low:** the page now says that Q1 reads the first capacity reading when the first
  refused, that the phase `up` applies the prerequisite layer and refuses differing
  delivery paths, that the namespaces are compared with those read before anything
  was installed, and that the three reconciliation comparisons must each be
  `compared`. The README says that a driver collects and a tool decides. The freeze
  record lists the refused caller log and the pin copies among its evidence paths,
  pins the contract and the environment binding that the desired state is rendered
  from, and states that the controller version is the pinned one and not a reported
  one. This record says what the story asks of Q1, and no longer states it as what
  Q1 does. One finding is older than this change and is not corrected here: the
  experiments index says that one pinned input of E01 revision 3 differs from its
  pin, while the freeze tool lists 30.
