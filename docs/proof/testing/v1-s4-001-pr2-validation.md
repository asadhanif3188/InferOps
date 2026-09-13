# V1-S4-001-PR2 change validation

Date: 2026-09-13

Change: the `helm-chart` and `terraform` gates in the committed default-lane workflow,
[the amendment to ADR 0012](../../architecture/decisions/ADR-0012-continuous-integration-service.md)
(D2 narrowed, D7 added), the infrastructure and workflow-boundary controls, and
[the extended gate matrix](../../testing/ci-gate-matrix.md).

Classification: **local static evidence for the change itself.** Every result below
was produced on one Windows host by running commands over files in this repository,
by rendering the chart, by validating the Terraform configuration with no backend, and
by reading two public job listings from the service's API. No cluster was created,
selected, or contacted, no kubeconfig was read, no plan was made, no state was read, no
model was downloaded, no runtime was started, and **neither new gate was executed on
GitHub Actions**.

Claim boundary: two gates are committed as jobs and as matrix rows, they reach no
cluster and a checker refuses anything that would, every tool they download is
checked against a committed digest, every infrastructure fixture is refused **for its
recorded reason** by the pinned tool, the tool-backed suites run with no skip, and the
rules a cluster-lane workflow must satisfy are enforced against fixtures. Every command
produced the result recorded below **on this host, with Windows builds of the pinned
versions**.

**What this record does not establish.** It is not evidence that either new gate
passes on a hosted Ubuntu runner. It is not evidence that the chart installs, that a
pod schedules, that a rendered NetworkPolicy is enforced, or that the Terraform
configuration applies — nothing here reached a cluster, by construction. It is not
evidence for any claim about a runtime or a model, and it raises no certification
ceiling: every new gate is `local-static` and stops at `C0`. It commits no workflow for
a cluster lane and labels no runner capable.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python, in the locked environment | `3.12.12` |
| `uv` | `0.9.16` |
| `pytest` | `8.4.2` |
| `jsonschema` | `4.26.0` |
| `PyYAML` | `6.0.3` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |
| Git | `2.45.1.windows.1` |
| Helm | `v3.19.0+g3d8990f` |
| kubeconform | `v0.8.0`, Windows release archive |
| Terraform | `v1.15.8`, `windows_386` |
| TFLint | `0.64.0`, bundled Terraform ruleset `0.15.0` |
| Trivy | `0.74.0`, used only for the measurement below |
| Gitleaks | `8.30.1`, Windows release archive |

The workflow installs the `linux_amd64` archives of Helm, kubeconform, Terraform, and
TFLint. Each Linux digest committed in the workflow was computed from the downloaded
archive on this host and matched the publisher's own checksum file. Locally, the
kubeconform, TFLint, and Gitleaks Windows archives were downloaded and checked the same
way; Helm and Terraform were binaries already installed on this host, which report the
pinned versions and whose archives were **not** checked here. Every binary is the pinned
release built for another platform, and "the same release on another platform" has been
wrong once already in this lane.

The container engine was not running during these runs. No gate this change adds uses
one; the consequence for the default lane is recorded under its result.

## Commands and results

### The suites this change adds and extends

```text
uv run --locked python -m pytest tests/testing -q
1740 passed in 11.09s
```

`tests/testing/test_infrastructure_gates.py` is new. `tests/testing/test_ci_gate_matrix.py`
is extended with checks that every downloaded tool is pinned in the matrix at the
version the controls require, that every `curl` is followed by a digest check, that
every kubeconform call names the pinned schema source, that the Terraform job runs what
the wrapper's `check` action runs, and that the document publishes every lane rule and
the control counts each runner produces.

### The full default lane

```text
uv run --locked python -m pytest -q
8493 passed, 31 skipped, 14 deselected in 217.23s
```

PR1's record reported `8301 passed, 30 skipped, 14 deselected` for the same command. The
one additional skip is not this change: the telemetry collector suite skips its engine
check with "the pinned collector image is not present locally", because the container
engine was stopped on this host for these runs and was running for PR1's. The fourteen
deselected are the `realruntime` tests the committed marker expression excludes.

### Formatting, lint, and types

```text
uv run --locked ruff format --check .           369 files already formatted
uv run --locked ruff check .                    All checks passed!
uv run --locked python -m mypy                  Success: no issues found in 202 source files
```

The first mypy run reported seven errors, all in this change's own code: a YAML `on:`
key looked up with a boolean against a dictionary typed as string-keyed, two unpacked
environment mappings that could be `None`, a loop variable reused across two types
(which mypy also reported as an unreachable statement), and a test monkeypatching
`shutil` through a module that does not export it. All seven are fixed.

### The workflow-equivalent commands

```text
helm lint charts/inferops-llm --strict --namespace inferops-platform --values charts/inferops-llm/ci/real-values.yaml   exit 0
helm lint charts/inferops-llm --strict --namespace inferops-platform --values charts/inferops-llm/ci/mock-values.yaml   exit 0
helm template ... real-values.yaml | kubeconform -strict -summary -kubernetes-version 1.34.0 -schema-location <pinned> -
  Summary: 23 resources found parsing stdin - Valid: 23, Invalid: 0, Errors: 0, Skipped: 0                               exit 0
helm template ... mock-values.yaml | kubeconform ... -
  Summary: 9 resources found parsing stdin - Valid: 9, Invalid: 0, Errors: 0, Skipped: 0                                 exit 0
kubeconform ... deploy/smoke/hello-world.yaml deploy/smoke/verify-job.yaml
  Summary: 5 resources found in 2 files - Valid: 5, Invalid: 0, Errors: 0, Skipped: 0                                    exit 0
terraform fmt -check -recursive infra/terraform                                                                          exit 0
terraform -chdir=infra/terraform/environments/local init -backend=false -input=false                                     exit 0
terraform -chdir=infra/terraform/environments/local validate      Success! The configuration is valid.                   exit 0
tflint --recursive --chdir=infra/terraform --config=<absolute path>/infra/terraform/.tflint.hcl --format=compact          exit 0
```

The lint steps were run with `set -euo pipefail` semantics as the workflow runs them,
and both renders were piped with `pipefail` set.

### The controls

```text
uv run --locked python -m tools.ci_gates expected-failures      62 controls produced the exit status the repository requires of them   exit 0
uv run --locked python -m tools.ci_gates kubernetes-failures    18 controls produced the exit status the repository requires of them   exit 0
uv run --locked python -m tools.ci_gates terraform-failures      6 controls produced the exit status the repository requires of them   exit 0
uv run --locked python -m tools.ci_gates no-skips helm          tests/architecture/test_helm_chart.py ran 201 tests with none skipped             exit 0
uv run --locked python -m tools.ci_gates no-skips terraform     tests/architecture/test_terraform_prerequisites.py ran 96 tests with none skipped exit 0
```

| Runner | Group | Controls | Required | Observed |
|---|---|---|---|---|
| `expected-failures` | `contract-refused` | 16 | non-zero | all 1 |
| | `contract-accepted` | 3 | zero | all 0 |
| | `manifest-refused` | 9 | non-zero | all 1 |
| | `manifest-accepted` | 2 | zero | all 0 |
| | `workflow-refused` | 21 | non-zero | all 1 |
| | `workflow-accepted` | 3 | zero | all 0 |
| | `ownership-refused` | 6 | non-zero | all 1 |
| | `ownership-accepted` | 2 | zero | all 0 |
| `kubernetes-failures` | `values-refused` | 9 | render refuses, for the recorded reason | all `[1]` |
| | `render-refused-by-policy` | 1 | render succeeds, policy refuses | `[0, 1]` |
| | `schema-refused` | 4 | refused, for the recorded reason | all `[1]` |
| | `render-accepted` | 2 | render, schema, and policy all succeed | both `[0, 0, 0]` |
| | `schema-accepted` | 2 | zero | both `[0]` |
| `terraform-failures` | `terraform-format-refused` | 1 | refused | `[3]` |
| | `terraform-validate-refused` | 1 | init succeeds, validate refuses | `[0, 1]` |
| | `terraform-lint-refused` | 3 | refused, naming the rule | all `[2]` |
| | `terraform-accepted` | 1 | format, init, validate, and lint all succeed | `[0, 0, 0, 0]` |

The counts in this table are the runners' own, and the counts the gate matrix publishes
are compared to the runners by a test rather than typed beside them.

### The negative demonstrations

Each statement below appears in a comment, a document, or a limitation this change
publishes, and each was run rather than assumed.

| Statement | Command | Observed |
|---|---|---|
| `helm lint` does not enforce the chart's guards | `helm lint charts/inferops-llm --strict --namespace inferops-platform`, with no values | exit `0`, each guard printed as `[INFO] Fail: ...` |
| `helm template` does | the same, as `helm template` | exit `1`, `profile is required and has no default` |
| Without `pipefail`, a render that fails passes the schema step | the failing render piped to kubeconform | `0 resource found`, exit `0`; with `pipefail`, exit `1` |
| tflint does not apply a configuration it is not handed | `tflint` on `lint-undocumented-variable` with no `--config` | exit `0` |
| With the committed configuration it does | the same, with the configuration by absolute path | exit `2`, `terraform_documented_variables` |
| A missing tool stops the family before any control | `kubernetes-failures` with neither tool on `PATH` | exit `1`, two `not on PATH` refusals, no control run |
| A tool at another version stops it too | `kubernetes-failures` with a locally built kubeconform first on `PATH` | exit `1`, `kubeconform reports 'development'; this gate is pinned to 'v0.8.0'` |

## What running the checks by hand found

Four things were wrong before this change wrote anything down, and one was wrong in the
change itself.

**CONTRIBUTING said something false about `helm lint`.** It said a lint with no
`--values` "is expected to fail with that refusal rather than to pass". Under Helm
3.19 it passes: lint reports a template `fail` as `[INFO]` and exits 0, and only a
values-schema violation fails it. The sentence is corrected in place with a note saying
what it used to claim, and the values controls render rather than lint.

**tflint silently ignores a configuration it is not handed by absolute path.** Under
`--recursive`, a `.tflint.hcl` present in the `--chdir` directory was not applied and
the lint passed on tflint's defaults; a relative `--config` was resolved against each
module and failed to load. Only an absolute path reached every module. The gate passes
one, and `lint-undocumented-variable` fails only when the configuration is read.

**kubeconform validates against a moving target by default.** Its schemas are fetched
from the `master` branch of the schema repository. The gate, the controls, and
CONTRIBUTING now name commit `970cc70507e1880a7a3b64184b6aad417a1d8d85`.

**The cluster-smoke lane's own scripts do not call the provider guard.** `smoke.sh`
calls the older kind-only identity check, and `cluster-verify.sh`, `preflight.sh`, and
`verify-clean.sh` call neither. A dispatched cluster-smoke workflow could not use them
under ADR 0012 D7. Closing that is environment-script work outside this change; a test
asserts the gap still exists.

**This change's own reason check caught its own runner.** The first run of
`terraform-failures` reported three of six controls failed: tflint had refused all
three lint fixtures, which is what the controls ask for, but for
`Rel: can't make <scratch>\fixture relative to` the repository — the temporary
directory is on another drive on this host, and `--chdir` must be expressible relative
to the working directory. Without the recorded reason those three would have passed.
The runner now runs tflint from inside the fixture's temporary copy.

## A Trivy misconfiguration gate, measured and not adopted

The objective names Terraform security checks and rendered-manifest policy validation,
and Trivy is already pinned in this lane. It was measured before being chosen.

| Target | Command | Result |
|---|---|---|
| The committed Terraform configuration | `trivy config --severity HIGH,CRITICAL --exit-code 1 infra/terraform` | clean |
| A `kubernetes_pod_v1` declared in Terraform with `privileged`, `host_network`, `run_as_user = 0`, and a `latest` tag | the same | **clean**, exit `0` |
| An AWS security group rule open to `0.0.0.0/0` | the same | refused, exit `1` |
| Both committed chart renders | the same, over `charts/inferops-llm/ci/rendered` | refused, exit `1`: one `HIGH` finding each, `KSV-0109`, reading the environment name `INFEROPS_MAX_OUTPUT_TOKENS` in the runtime ConfigMap as a stored secret |
| The nine insecure workload-policy fixtures | the same | one refused (`root-and-privileged-container.yaml`, two findings); eight clean |

So a Trivy gate over this Terraform could not fail on any resource type it declares,
and a Trivy gate over the renders would refuse the committed chart on a false positive
while passing eight of nine manifests the accepted policy refuses. The rendered-manifest
policy is the accepted workload policy, run on a fresh render; the Terraform security
rules are the prerequisite suite's forbidden-provider, forbidden-resource-type,
host-path, and secret-material checks, now required to run without a skip. Adopting a
second engine would have been a second severity policy nobody agreed to, with an
exception recorded for a finding that is not a secret.

## The service, observed

The nine gates `V1-S4-001-PR1` introduced were read back from the service's public API
on 2026-09-13. Job names and conclusions only; no log was retrieved.

| Run | Event | Commit | Jobs | Conclusion |
|---|---|---|---|---|
| `34706894182` | `pull_request` | `aeb1b9d` | 9 | failure — the run PR1's record describes |
| `34742582972` | `pull_request` | `0c84d79` | 9 | **success**, every job |
| `34743164167` | `push` to `main` | `f212090` | 9 | **success**, every job |

That corrects a limitation several documents still published — "no run has passed" —
in the documents this change edits: the gate matrix, ADR 0012, ADR 0005, the strategy
data and document, CONTRIBUTING, and both READMEs. It does **not** certify a claim. The
observation is of job conclusions through an API, no log or artifact is promoted, and
ADR 0005 D5 still requires a promoted record before a lane result is evidence. The
security records that make the same statement are named in the gate matrix as a
follow-up rather than edited here.

## What was not run, and why

| Not run | Why |
|---|---|
| Either new gate on GitHub Actions | The workflow runs when the branch is pushed and a pull request opens. Until then the two jobs are configuration |
| Any Kubernetes or Terraform operation that reaches a cluster | Out of this lane by construction and out of this PR's boundary. No provider was selected, no kubeconfig was read, no `plan`, `apply`, or `destroy` was run |
| A dispatched cluster-smoke or real-runtime workflow | None is committed. What labels a capable runner is ADR 0005 D6's open half |
| Any real-runtime or model operation | Out of this PR's boundary. No model was downloaded and no runtime was started |
| The API image build, the dependency and image scans, and the bill-of-materials generation | Unchanged by this change — no Dockerfile, lockfile, image pin, or scan script is touched — and the container engine was stopped on this host |
| `shellcheck` | Not installed on this host, not in this lane, and no script is changed |

## The diff

The published diff was read in full, and searched for host paths, identities, and
planning content. It carries no credential, no model artifact, no Terraform state or
working directory, no personal filesystem path, and nothing copied from a private
planning document. The Terraform fixtures were initialised only in temporary copies, so
no `.terraform/` directory or lock file was created beside them. `git diff --check`
reports nothing.

The control runner replaces its temporary directory with `<scratch>` before any output
leaves it, and a test requires that no published command carries the repository's host
path. The one kubeconfig path any fixture names is the project-scoped relative path the
environment scripts already publish.

Counts published in prose are derived rather than typed: the eleven gates, the sixty-two,
eighteen, and six controls, and the lane rules the matrix names are each compared to
the data or the runner by a test. Two counts were found wrong while writing this change
and corrected — the document first said sixty controls, before two workflow fixtures
were added for the two rules no fixture had yet broken, and the first draft of the
minimums set `values-refused` to eight when nine fixtures exist.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Gate matrix maps every check to a V1 claim | **Met**. Both new gates name the claims they defend — `no-resource-in-the-architecture-has-two-owners` for both, and the manifest-policy claim for `helm-chart` — and the `expected-failures` row gains the ownership claim. Each claim shares a layer with its gate, which a test requires |
| Invalid contract and insecure manifest fixtures fail | **Met, and extended.** The PR1 controls still pass; nine invalid values overrides, one policy-refused render, four schema-invalid manifests, five broken Terraform modules, twenty-one broken workflows, and six ownership overlaps are refused, the tool-backed ones for their recorded reason |
| Mock path runs in normal CI | **Met**, unchanged. `default-lane-tests` runs the default lane, which includes the mock integration layer |
| Real-runtime/Kubernetes workflows are separately labelled | **Met as rules, not as a workflow.** ADR 0012 D7 and the matrix publish what a cluster-lane workflow must satisfy, enforced against two valid shapes and a fixture per rule. No such workflow is committed, and the reason is recorded |
| CI does not download the full model unless explicitly scheduled | **Met**, and now also enforced for a cluster lane: a model-free lane that installs may not name the real profile |

## Limitations

- **Neither new gate has run on the service.** Every result above is from one Windows
  host, with Windows builds of the pinned releases. The nine older gates have passed
  there; that says nothing about two jobs that download four archives and run tools no
  Windows run can stand in for exactly.
- **The lane rules read text.** A workflow can hand a cluster to a script. The
  cluster-free rule refuses every environment script, and the dispatch rules admit only
  scripts whose text calls `inferops::resolve_target` — a property of the text, not a
  proof of what the script does.
- **The ownership check compares kinds and reads Terraform as text.** It would not see
  two owners of a kind the inventory does not name, and it resolves no module or
  variable.
- **Five gates now consume the network.** Two new ones download pinned archives, read
  schemas from a pinned commit, and fetch the provider the lock file pins.
- **The dispatch rules have never met a real workflow.** They are held to fixtures
  written alongside them, by the same hand. The first committed cluster workflow is the
  first independent test of whether they are the right rules.
