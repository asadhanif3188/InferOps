# V2-S4-003-PR2 validation

Status: **the single-runtime baseline profile exists as a generated release and
a comparison record, and a check holds both. This is static evidence at C0.** The
baseline is two API replicas and one serving runtime replica. No cluster was
read, no run installed the baseline, and no Application reads the profile. No
chart file, contract, binding, Application, Terraform file, desired-state file,
or freeze record was changed, and no claim was registered. An independent
review found that the first commit overstated what the check refuses, left one
page behind the list it describes, and compared the record more loosely than
its rule says: see
[what the independent review found](#what-the-independent-review-found).

| Property | Value |
|---|---|
| Date | 2026-10-09 |
| Base | `cbaa5b541c4351a02411cb4f34f9a9213c3e183d`, the merge of pull request #130 |
| Branch | `test/v2-s4-003-single-runtime-baseline-profile` |
| Commits | `e28f8690`: the tool, the profile, the record, the suite, and the page. A second commit: the corrections of the independent review, and the default lane |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0` |
| Evidence level | C0. Every check reads committed files or renders them with the chart tool |
| Claim effect | None. No claim, ledger, register row, dashboard row, or evidence-index entry was added or changed |

## What changed

- `tools/baseline_profile` is new. It declares the baseline, derives the baseline
  release and the desired-state release from their declared inputs, compares the
  two in four layers, and prints one record whose result is `COMPARABLE` or
  `REFUSED`. It reads files and contacts no cluster.
  [The baseline profile page](../../environment/single-runtime-baseline-profile.md)
  describes the declaration, the 12 permitted paths, the rules, and what a record
  does not establish.
- `tests/domain/fixtures/experiment-profiles/single-runtime-baseline/` is new. It
  holds the two generated files of the baseline release.
  `single-runtime-baseline.comparison.v1alpha1.json` beside it is the committed
  comparison record. `.gitattributes` pins both to LF.
- `tests/domain/test_baseline_profile.py` is new.
- Four existing suites are edited. `test_helm_chart.py` gains one render
  comparison. `test_generated_release_drift.py` counts the profile among the
  declared places of a generated file. `test_renderer_input_boundary.py` lists the
  tool among the repository checks. `test_test_inventory.py` gains one number
  word.
- These pages state the profile: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`,
  the architecture index, the system architecture, the Git desired-state page,
  the capacity preflight page, the renderer boundary page, and the proof index.
  The test inventory gains one module. The new page and this record are added.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| A controlled profile of two API replicas and one runtime replica exists | Reached as a render. The profile is a generated release with `api.replicaCount` 2 and `runtime.replicaCount` 1. No Application reads it, and no run installed it |
| The baseline and the target differ only in the runtime replica count, where practical | Reached at C0, with one stated exception. The two generated values files differ in two values: the runtime replica count and the workload version. The version differs because the two contracts differ in content, and one version names one content |
| Every other claim-relevant target value is preserved | Reached in part. Reached at C0 for the values that a generated release holds: the workload identity, the model, the runtime image, the resource ceiling, both rollout bounds, the API values, and the generated telemetry and secret members. The binding, the platform defaults, and both revisions are the target's by declaration. Not reached for what an install adds: the hand-written values, the API image digest, the release name, the namespace, and the chart revision. The baseline declares none of them |
| A machine-readable comparison refuses an accidental change to workload, model, runtime, or resource inputs | Reached at C0. The record states each difference by JSON pointer. The suite plants each such change, and each is refused at its path |
| The comparison refuses an accidental change to readiness inputs | Not reached by the tool. The chart owns each probe, the baseline names no chart, and the record compares no probe. One test renders both releases with the chart of the working tree and one hand-written values file, and holds each object equal but for three stated differences. That test plants no changed probe: it shows that the two generated files change no probe in a render |
| The comparison refuses an accidental change to caller-profile inputs | Not reached. No caller profile exists in this repository. The API values that a caller meets, which are the request timeout, the drain timeout, and the output-token ceiling, are compared |
| The preflight records allocatable resources, reservations, footprint, requests, and rollout headroom | The earlier change of this story reached it. Not changed here |
| Insufficient capacity is refused and the gate is not weakened | The earlier change of this story reached it. Not changed here. The gate gives no footprint for the baseline |

## Decisions taken in this change

**The baseline is rendered from the existing one-replica contract.** Version
`0.1.0` of the reference workload declares a replica range of one and one, and
it differs from version `0.2.0` in the version, the description, and the replica
range. A new contract document with one replica would be a third document of
one workload. So the change adds none, and a test pins the list of valid
contract examples.

**The workload version differs, and that is stated.** A baseline that kept
version `0.2.0` with another replica range would give one version two contents.
The check refuses it under `baseline-version-not-distinct`. The cost is a second
differing value, `ownership.workloadVersion`, and with it one ConfigMap value
and two checksum annotations in a render.

**The baseline is the target's declaration with two fields replaced.** The
binding, the platform defaults, and both revisions are read from the
desired-state release's declaration. A change to one of them moves both sides.

**The profile is outside the Git desired state.** One Application reads
`gitops/`, and a merge that changes a file there changes a cluster where that
Application is applied. The baseline is not desired state. A rule refuses a
profile directory inside that tree, and a test holds that no Application names
the profile.

**The tool compares, and a person writes.** `--check` repairs nothing. `--write`
refuses a comparison whose result is `REFUSED`.

**No pinned input of the first experiment's freeze record is edited.**
`python -m tools.experiment_freeze --changes` names 25 material files that differ
from revision 3 of that record at the base, and 25 with this change.

## Validation at the first commit

Each command ran on the host of the table above.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | No file to reformat |
| `uv run --locked python -m mypy` | No issue in 370 source files |
| `uv run --locked python -m pytest tests/domain/test_baseline_profile.py -q` | 49 passed |
| `uv run --locked python -m pytest tests/architecture/test_helm_chart.py tests/architecture/test_argocd_bootstrap.py tests/domain/test_generated_release_drift.py tests/domain/test_renderer_input_boundary.py tests/domain/test_gitops_desired_state.py tests/domain/test_capacity_preflight.py -q` | 922 passed, 6 skipped. The render comparison ran: `helm` is installed |
| `uv run --locked python -m pytest tests/testing -q` | 8,040 passed, 1 skipped |
| `uv run --locked python -m tools.baseline_profile --check` | `OK       the baseline differs from the target only at the permitted paths` |
| `uv run --locked python -m tools.gitops_desired_state --check` | `OK       the tree holds the declared releases and nothing else` |
| `uv run --locked python -m tools.generated_release --check` | `OK       support-assistant-local-kind: both files are what the declared sources derive` |
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 7 committed collection(s), each record is what its collection gives` |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `git diff --check` against the base | No whitespace error |

**Not run at the first commit.** The whole default lane, which ran at the second
commit. `gitleaks` is not installed on this host, so no secret scan ran at
either commit. Hosted CI was not read: no pull request existed. No cluster
command ran, because the change reads no cluster.

## What the independent review found

Three reviewers read the first commit. None was given this record's
conclusions. One tried to defeat the comparison, one compared each sentence
with the code, and one read the design against what the change was asked to
reach. No reviewer made the comparison report `COMPARABLE` for two releases
that differ at another path, through any committed input.

### What the tool got wrong

- **The record was not compared byte for byte.** The rule
  `baseline-record-stale` says "byte for byte". The first commit removed
  carriage returns from the committed record before it compared, so a record
  with another line ending passed `--check`, and `--write` then wrote it again.
  The values file was already compared strictly. The tool now compares the
  record's bytes, and a test gives it a record with another line ending.
- **The walk of two documents could read two documents as equal.** It made one
  flat list of paths for each side. A sequence and a mapping whose keys spell
  its indexes gave the same paths, and a mapping with the keys `1` and `"1"`
  lost one entry. No committed input reaches that: the render boundary refuses
  such a contract first. So the property rested on the parsers, and nothing
  said so. The walk now reads both sides together, compares a mapping beside a
  sequence whole, and compares a mapping with a key that is not text whole.
  Seven such pairs are a test.
- **The guard for the desired state was a text prefix.** `./gitops/...`,
  `GitOps/...`, `tests/../gitops/...`, and a path with a backslash each passed
  it. Only a replaced declaration reaches it. The directory must now be one
  relative POSIX path of plain segments, and its first segment is compared
  without case. Nine spellings are a test.
- **A failed write printed a path of the host, and its advice was wrong.** The
  release is written before the record. When the record could not be written,
  the command printed the error's own text, which names an absolute path, and
  said that the profile directory may be absent. It now prints the kind of the
  error and its reason, and says that the two files may be out of step. The
  order is not changed: `--check` reports the state, and a second write
  repairs it. A test holds both.
- **Two findings stated the wrong thing.** A replica range of `1.0` was shown
  as `null`, because the tool discarded the stated value before it printed it.
  A missing binding was reported with the contract's path as its subject. The
  detail now shows what the document states, and the subject is
  `<side>: declared inputs`.
- **A target that is not declared ended the command with a traceback.** The
  command now refuses with one line.
- **One branch of the command could not be reached**, and it is removed.

### What the first commit said, and what is true

- **The changelog said that a changed API value, binding, or revision "on
  either side is refused at its path".** It is not. Both sides read the one
  binding, the one defaults file, and the one pair of revisions, so such a
  change moves both sides and the comparison stays `COMPARABLE`. The check then
  fails as drift and as a stale record. The page said this correctly, and the
  changelog contradicted it. The changelog is corrected.
- **The renderer boundary page still said "the six tools".** This change made
  the list seven and did not edit the page. The page now names the tool, and
  says that it writes a generated release.
- **"Both sides name the one chart" was false.** The baseline names no chart.
  The target's Application names one, for the target. Nothing binds a run to
  one chart revision for both sides. The page and the tool's text are
  corrected, and the record states the limit.
- **The record's limits were shorter than the page's.** The committed record
  did not say that the chart revision, the probes, the API image digest, the
  release name, the namespace, and the state of the model cache claim are not
  compared. It states ten limits now, and it stated six.
- **The consequence of the workload version was understated.** The page called
  it one ConfigMap value. The API also states it as a resource attribute of its
  telemetry, so telemetry of the two sides differs in it. The checksum
  annotation differs on the API pod template too, so a change of one installed
  release from one side to the other gives the API Deployment a new pod
  template. The page states both.
- **The contributor guide gave one remedy for two failures.** It said to run
  `--write` after any change to a contract. A change at a path that is not
  permitted gives `REFUSED`, and `--write` refuses. The guide now separates the
  stale case from the refused case. The page and the guide now say that the
  baseline follows the target only while every other member of the two
  contracts stays equal, and that the `0.1.0` contract is a pinned input of a
  freeze record.
- **This record graded two rows too high.** "Every other claim-relevant target
  value is preserved" said "Reached at C0". It is reached in part: an install
  adds inputs that the baseline does not declare. The readiness row said
  "Reached in part". The tool compares no probe, so the row now says that the
  tool does not reach it.
- **The page stated a later experiment as a fact.** No public file defines one.
  The page now says what the baseline is for, and that no such experiment is
  defined here.
- **The README named two permitted differences.** Twelve paths are permitted,
  and the contract's description is one of them.
- **The rollout sentence was weaker than what the chart's page says.** Under
  `maxSurge` 0 a rollout of one replica removes the one pod before its
  replacement is created. The first commit said that the bounds "permit" it.
- **Two test inventory rows were behind their suites.** The drift suite's row
  did not name the profile directory. The row of the new suite said that a
  missing contract leaves the later rules not evaluated, and no test asserted
  those states. The test now asserts them.
- **One test was named for more than it asserts.** It holds the list of
  contract documents, and its name said that the contract is not edited.
- **This record said that each identifier is the digest of a committed document
  or of a generated file.** The files also hold a commit identifier, a model
  artifact digest, and an image digest.

### Noted, and not changed

- **The declaration layer cannot fail in the committed tree.** The baseline is
  built from the target's declaration. The layer is a tripwire on a later edit,
  and the page and the tool now say so.
- **The profile is under a test fixtures path.** A later freeze record would
  pin an experiment input there. The directory is not moved in this change.
- **Three pages count the committed generated releases and do not name the
  profile**: the renderer page, the contracts index, and one README sentence.
  None is false, and none is edited.
- **The render comparison skips on a host without the chart tool.** Nothing
  holds the render statements there. The hosted lane installs the tool.
- **The drift check leaves its compatibility matrix set for the process** when
  none was set before. That is the drift check's behaviour, and its file is a
  pinned input.
- **The tool is larger than the requirement needs.** The contract layer, the
  values layer, the topology rule, and the two rules for committed files do the
  refusing. The other two layers are kept as tripwires.

## Validation at the second commit

Each command ran on the same host, from the working tree that the second commit
holds.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | No file to reformat |
| `uv run --locked python -m mypy` | No issue in 370 source files |
| `uv run --locked python -m pytest tests/domain/test_baseline_profile.py -q` | 74 passed. The first commit held 49 |
| `uv run --locked python -m tools.baseline_profile --check` | `OK       the baseline differs from the target only at the permitted paths` |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 25 material files differ, as at the base |
| `git diff --check` against the base | No whitespace error |

## The default lane

`uv run --locked python -m pytest -q` ran once, on the working tree of the
second commit before this section was written: 19,782 passed, 37 skipped, and
14 deselected, in 25 minutes. No test failed.

The lane skipped 37 tests. The earlier change of this story records 37 skipped
tests on this host, and it states their reasons. The count is the same here. The
reasons were not read again. The render comparison of this change ran: `helm`
is installed.

This section is the one edit after that run. It changes this page only. The
link suite ran again for this page afterwards.

## Privacy and publicability

The diff was read for private material.

- The baseline release and the comparison record are derived from committed
  files. They hold release identifiers, digests of the contract, the binding,
  and the values file, one commit identifier, and the model artifact digest
  and the runtime image digest that the contract pins. Each is already in the
  desired-state release or in a committed contract.
- No credential, secret value, cloud account identifier, model artifact, or path
  of the workstation is in the diff.
- No planning text, prompt, or identifier of a later change is in the diff.

## What this does not establish

- **That a cluster ran the baseline.** No Application reads the profile, and no
  run installed the baseline release.
- **What a caller observes when a runtime pod stops**, under either topology.
- **That a run gives both sides equal hand-written values.** The baseline
  declares none.
- **That one caller profile is applied to both sides.** None exists.
- **That a cluster holds the baseline.** The capacity preflight gives no
  footprint for it.
- **That the baseline reproduces a failure.** The profile is a render.
- **Anything about a rollout of one runtime replica.** The render states the
  target's bounds. No rollout was observed.
