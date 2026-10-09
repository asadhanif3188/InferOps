# V2-S4-003-PR2 validation

Status: **the single-runtime baseline profile exists as a generated release and
a comparison record, and a check holds both. This is static evidence at C0.** The
baseline is two API replicas and one serving runtime replica. No cluster was
read, no run installed the baseline, and no Application reads the profile. No
chart file, contract, binding, Application, Terraform file, desired-state file,
or freeze record was changed, and no claim was registered.

| Property | Value |
|---|---|
| Date | 2026-10-09 |
| Base | `cbaa5b541c4351a02411cb4f34f9a9213c3e183d`, the merge of pull request #130 |
| Branch | `test/v2-s4-003-single-runtime-baseline-profile` |
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
  the capacity preflight page, and the proof index. The test inventory gains one
  module. The new page and this record are added.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| A controlled profile of two API replicas and one runtime replica exists | Reached as a render. The profile is a generated release with `api.replicaCount` 2 and `runtime.replicaCount` 1. No Application reads it, and no run installed it |
| The baseline and the target differ only in the runtime replica count, where practical | Reached at C0, with one stated exception. The two generated values files differ in two values: the runtime replica count and the workload version. The version differs because the two contracts differ in content, and one version names one content |
| Every other claim-relevant target value is preserved | Reached at C0 for the values that a release holds: the workload identity, the model, the runtime image, the resource ceiling, both rollout bounds, the API values, telemetry, and the secret references. The binding, the platform defaults, and both revisions are the target's by declaration |
| A machine-readable comparison refuses an accidental change to workload, model, runtime, or resource inputs | Reached at C0. The record states each difference by JSON pointer. The suite plants each such change, and each is refused at its path |
| The comparison refuses an accidental change to readiness inputs | Reached in part. The chart owns each probe, and both sides name the one chart. One test renders both releases and holds each object equal but for three stated differences. The tool itself does not run Helm, and the baseline declares no hand-written values |
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

**Not run at the first commit.** The whole default lane. `gitleaks` is not
installed on this host. Hosted CI was not read: no pull request existed. No
cluster command ran, because the change reads no cluster.

## Privacy and publicability

The diff was read for private material.

- The baseline release and the comparison record are derived from committed
  files. Each identifier and digest in them is the digest of a committed
  document or of a generated file.
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
