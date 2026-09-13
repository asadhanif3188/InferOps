# The continuous-integration gate matrix

Status: **accepted matrix**, in
[ADR 0012](../architecture/decisions/ADR-0012-continuous-integration-service.md).
It lists every automated gate, the commands it runs, the test layers it belongs to,
the public claims it defends, and — for each one — what a passing result may not be
used to say.

The authoritative form is
[`ci-gate-matrix.v1alpha1.json`](ci-gate-matrix.v1alpha1.json). That file and the
committed workflows are compared in both directions by
[`tests/testing/test_ci_gate_matrix.py`](../../tests/testing/test_ci_gate_matrix.py):
a job with no row here and a row here with no job are each a failing build.

Layer names, lane names, and what each layer may certify are in
[the test strategy](test-strategy.md). Claim identifiers are in
[the claim and test matrix](claim-test-matrix.md). Level meanings are in
[the certification document](certification.md).

> [!IMPORTANT]
> **The nine gates `V1-S4-001-PR1` introduced have passed on GitHub Actions; the two
> gates `V1-S4-001-PR2` adds have not run there.** The nine passed on 2026-09-13, on
> the pull-request run for commit `0c84d79` and again on the push to `main` at
> `f212090`, after a first hosted run had failed three of them on two defects a
> Windows host could not show. That is observed through the service's public API and
> is not promoted into a record: a job log expires, and a passing run is still not
> evidence for a claim until ADR 0005 D5's promotion has been done. Every command in
> the two new gates was run by hand, on one Windows host, with Windows builds of the
> pinned tool versions — and "close to what the runner will do" has already been
> wrong once in this lane.
>
> Running the infrastructure checks by hand before writing them down was not
> ceremony either. It found that CONTRIBUTING's statement that a `helm lint` with no
> values "is expected to fail" was false — lint reports the chart's guards as
> `[INFO]` and exits 0 — and that tflint silently ignores a configuration it is not
> handed by absolute path.

## The one rule this follows

**A gate may enforce a claim. It may not raise what the claim rests on.** Every
ceiling in the table below is inherited from the evidence class the strategy already
gave the layer, never restated here — because a ceiling written in two places is a
ceiling that can be raised in one of them. Automating the mock lane makes it run on
every change; it does not make a mock certify a runtime, and rendering a chart on
every change does not make it a chart that installs.

## The gates

Eleven gates run on every change. All eleven are blocking.

| Gate | Runs | Layers | Claims it defends | Ceiling |
|---|---|---|---|---|
| `code-quality` | `ruff format --check`, `ruff check`, `mypy`, against the locked toolchain | — | none, stated | C0 |
| `default-lane-tests` | `python -m pytest -q`, with no marker expression | unit, contract-and-schema, architecture-inventory, adapter, mock-integration, documentation | sixteen | C1 |
| `expected-failures` | `python -m tools.ci_gates expected-failures` | contract-and-schema, architecture-inventory, documentation | four | C0 |
| `helm-chart` | `helm lint` and `helm template` under both fixtures, `kubeconform` against pinned schemas, the Kubernetes controls, and the chart suite with no skip | architecture-inventory, documentation | two | C0 |
| `terraform` | `terraform fmt`, `init -backend=false`, `validate`, `tflint`, the Terraform controls, and the prerequisite suite with no skip | architecture-inventory | one | C0 |
| `documentation` | link resolution, trailing whitespace, hard tabs | documentation | one | C0 |
| `distribution-build` | `uv build`, then the wheel and the source distribution are inspected | — | none, stated | C0 |
| `api-container-image` | `docker build` of the API image, then its user and its shipped packages | — | none, stated | C0 |
| `dependency-and-image-scan` | `scripts/security/scan-dependencies.sh`, `scripts/security/scan-runtime-image.sh` | security-scan | none, stated | C0 |
| `software-bill-of-materials` | `scripts/security/generate-sbom.sh`, published as lane output | security-scan | none, stated | C0 |
| `secret-scan` | `gitleaks git .` over full history, against the committed allowlist | security-scan | one, still planned | C0 |

"None, stated" is not a blank. A gate either names a claim it defends or records in
the data why it defends none, and a suite refuses a row that does neither — which is
what makes the mapping complete rather than merely present. A formatter defends no
published claim; it is the condition every other gate's result is read under.

### Why the lane is selected by `pytest.ini` and not by the workflow

`default-lane-tests` runs `pytest -q` with no `-m` argument. That is deliberate. The
committed marker expression in [`pytest.ini`](../../pytest.ini) is what deselects
`cluster`, `realruntime`, `failure`, and `load`, and it is the mechanism behind
*the default lane cannot execute a real model*. A marker expression typed into the
workflow instead would be a second definition of the lane, changeable without
touching the strategy the suite checks.

### What the two infrastructure gates are, and are not

Both are static. `helm-chart` renders the chart to a file and validates the file;
`terraform` checks the configuration and initialises it with no backend. Neither
reads a kubeconfig, neither can see a cluster, and neither says anything about
whether a release installs or a prerequisite applies — the lifecycle and apply
records under [`docs/proof/`](../proof/) are where those answers live, and they come
from a different lane.

Three details carry more weight than they appear to.

- **The chart's guards are enforced by `helm template`, not by `helm lint`.** Under
  Helm 3.19 a template `fail` is reported by lint as `[INFO]` and lint exits 0: the
  shipped defaults, which the chart refuses outright, lint clean. Schema violations do
  fail lint. So the lint steps are kept for what lint finds, and every values control
  goes through `helm template`.
- **The schemas are pinned.** kubeconform reads its schemas from the `master` branch
  of the schema repository by default. Both the gate and the controls pass a
  `-schema-location` naming one commit, and a suite refuses a kubeconform call without
  it.
- **The tool-backed suites may not skip.** The chart suite's drift check and the
  prerequisite suite's format and validation checks skip where their tool is absent.
  In the one job that installs the tool on purpose, `python -m tools.ci_gates
  no-skips` runs the suite and fails on a single skip.

## What the normal lane may not do

Eight prohibitions are checked rather than reviewed. Each is one plausible line away
from being broken.

| Prohibition | Why |
|---|---|
| No job reaches a Kubernetes cluster | A normal lane that can discover an ambient cluster can mutate an operator's cluster from a pull request. Helm runs only `lint`, `template`, and `version`; Terraform only `fmt`, `init -backend=false`, `validate`, and `version`; and there is no kubectl, no kind, no kubeconfig or kube context, no provider selection, and no environment script. The check reads the file's text rather than its parsed steps, because a cluster can be reached from a script block, an action input, or an environment variable, and only the text sees all three |
| No job downloads the pinned model artifact | ADR 0005 D2's premise is that the lane every change goes through costs nothing. The artifact is 1.71 GiB |
| Every action is pinned by commit SHA | A tag is a name somebody can move. It is the argument this repository already makes for pinning a container image by digest |
| Every workflow declares its token permissions | The default grant is a repository-wide setting a workflow file cannot see. Declaring `contents: read` makes the grant reviewable in the diff that asks for it |
| Every program a gate documents is run by its job | This table is the thing most likely to be written once and then outlive the job it describes. The `distribution-build` row named `unzip` while the job used Python's `zipfile`, in the change that introduced both — harmless, and the exact drift the matrix exists to prevent. The check runs one way: a program the job runs and the matrix does not document is not reported |
| Every downloaded binary is checked against a committed digest | A binary fetched by version alone is a binary whose release somebody can replace. Every `curl` is followed in the same step by `sha256sum --check --strict`, and every digest a job declares is the one recorded in the tool pins below |
| A tool-backed check may not skip where the tool is installed | A skipped drift check in the job that installed Helm is a green gate that checked nothing |
| A negative control must refuse for its recorded reason | A missing tool refuses every input, and a fixture refused because a path was misspelled is refused for nobody's reason. This caught a real case during the change that introduced it: tflint refused all three lint fixtures on a Windows host for a path-resolution error, and only the reason check reported it |

Two more properties are checked for the same reason: every job declares a timeout
inside its lane's budget, because an unbounded job is a six-hour job; and every job
names `ubuntu-24.04` rather than `ubuntu-latest`, because a lane whose runner image
moves underneath it cannot attribute a failure to the change that appeared to cause
it.

The cluster prohibition changed shape in `V1-S4-001-PR2`. It used to refuse the text
`helm ` and `terraform ` anywhere in the workflow, which was right while neither tool
had a job and could not survive the change that gave them one. It now refuses what
reaches a cluster rather than the names of the tools that sometimes do, and it is one
function, [`tools/ci_gates/workflow_boundary.py`](../../tools/ci_gates/workflow_boundary.py),
shared by the suite and the controls. It reports the first property as
`cluster-free-lane-reaches-no-cluster` and the pinned runner as
`cluster-free-lane-runs-on-the-pinned-hosted-image`, and a fixture breaks each.

## A lane that needs a cluster

No workflow for the `cluster-smoke` or `real-runtime` lane is committed. What labels a
capable runner is the half of ADR 0005 D6 that is still open, and a committed workflow
would have to name one. Both lanes stay `manual`.

What is committed is the boundary such a workflow has to satisfy, enforced by the same
checker against fixtures under
[`tests/testing/fixtures/workflow-boundary/`](../../tests/testing/fixtures/workflow-boundary/),
so that the first real one meets a check rather than a paragraph. Every rule below has
a fixture that breaks it and nothing else.

| Rule | What it requires |
|---|---|
| `dispatch-only` | `workflow_dispatch` is the only trigger. No pull request, push, or schedule starts a cluster lane |
| `provider-is-a-required-choice-with-no-default` | A `provider` input that is required, a `choice`, offers exactly the providers [the provider contract](../environment/local-cluster-provider-contract.v1alpha1.json) admits, and has no default |
| `provider-handed-to-every-job` | Every job receives `INFEROPS_PROVIDER` from that input |
| `runs-where-the-external-cluster-is` | Every job runs on a `self-hosted` runner and on no hosted image. An externally owned local cluster is not reachable from a disposable virtual machine |
| `cluster-reached-only-through-the-provider-guard` | No kubectl, no direct Helm or Terraform subcommand that reaches a cluster, and only environment scripts that call `inferops::resolve_target` |
| `consumes-an-external-cluster` | Never `cluster-up.sh` or `cluster-down.sh` |
| `model-free-lane-downloads-nothing` | A model-free lane names no model tooling, and a model-free lane that installs names no real profile — a real release runs an acquisition job |
| `authorization-is-an-explicit-input` | A lane that requires authorization declares a required boolean `authorize` input defaulting to false, and every job waits on it |
| `read-only-token`, `timeout-within-the-lane-budget`, `actions-pinned-by-commit-sha` | The rules every workflow meets, whatever its lane |

Writing the rules down found a gap. The cluster-smoke lane is built from `smoke.sh`,
`cluster-verify.sh`, `preflight.sh`, and `verify-clean.sh`, and none of them calls the
provider guard — `smoke.sh` still calls the older kind-only identity check. A
dispatched cluster-smoke workflow could not use them under these rules. The valid
fixture uses `target-detect.sh` and `helm-lifecycle.sh` instead, and a test asserts
the gap still exists, so closing it has to update this paragraph.

## The expected-failure controls

`expected-failures`, `helm-chart`, and `terraform` each carry controls: the published
commands, run against inputs that must be refused and inputs that must be accepted,
with the **exit status** read — which is the only thing a workflow can read. A rule
proved inside a pytest process is a rule the gate itself cannot enforce.

The positive groups are not decoration. A validator broken into refusing everything
would pass a suite of negative controls perfectly, and a gate that read only the
negatives would report that as health. Every group also declares a minimum count, so a
glob that matched nothing fails instead of producing an empty, passing run.

### Without a tool: `python -m tools.ci_gates expected-failures`

Sixty-two controls run, in eight groups.

| Group | Command | Inputs | Required exit |
|---|---|---|---|
| `contract-refused` | `python -m tools.contract_validation` | every document in `contracts/workload/examples/invalid/` | non-zero |
| `contract-accepted` | `python -m tools.contract_validation` | every document in `contracts/workload/examples/valid/` | zero |
| `manifest-refused` | `python -m tools.workload_policy` | every bundle in `tests/security/fixtures/workload-policy/invalid/` | non-zero |
| `manifest-accepted` | `python -m tools.workload_policy` | the two committed chart renders | zero |
| `workflow-refused` | `python -m tools.ci_gates.workflow_boundary` | the twenty-one workflows in `tests/testing/fixtures/workflow-boundary/invalid/` | non-zero |
| `workflow-accepted` | `python -m tools.ci_gates.workflow_boundary` | the two valid dispatch shapes and every committed workflow | zero |
| `ownership-refused` | `python -m tools.ci_gates.ownership_overlap` | four renders and two Terraform configurations that reach across the ownership inventory | non-zero |
| `ownership-accepted` | `python -m tools.ci_gates.ownership_overlap` | each committed render, with the committed Terraform configuration | zero |

The ownership check compares **kinds**, because the inventory assigns kinds: a render
may carry none the inventory gives to Terraform or to the control plane (a Helm test
hook is exempt from the second), the configuration may declare none the inventory gives
to Helm or the control plane, and no kind may appear on both sides.

### With Helm and kubeconform: `python -m tools.ci_gates kubernetes-failures`

Eighteen controls run, in five groups. Nothing starts unless `helm` and `kubeconform`
are found at the pinned versions, and a refusal passes only if its output contains the
reason
[`expected-refusals.json`](../../tests/architecture/fixtures/infrastructure/expected-refusals.json)
records for its fixture.

| Group | Command | Inputs | Required result |
|---|---|---|---|
| `values-refused` | `helm template` with the real fixture and one override | nine values overrides the schema or a guard refuses | the render refuses, for the recorded reason |
| `render-refused-by-policy` | `helm template`, then `python -m tools.workload_policy` | one override that switches the network policy off | the render succeeds and the policy refuses |
| `schema-refused` | `kubeconform -strict` against the pinned schemas | four manifests with an unknown field, a wrong type, a missing name, and a removed API | refused, for the recorded reason |
| `render-accepted` | `helm template`, `kubeconform`, then the workload policy | both committed values fixtures | every stage succeeds |
| `schema-accepted` | `kubeconform -strict` against the pinned schemas | both smoke manifests | zero |

### With Terraform and tflint: `python -m tools.ci_gates terraform-failures`

Six controls run, in four groups. The same two conditions apply. Each fixture is
copied into a temporary directory first, so `init` never writes beside a committed
file.

| Group | Command | Inputs | Required result |
|---|---|---|---|
| `terraform-format-refused` | `terraform fmt -check -recursive` | a module whose assignments are misaligned | refused |
| `terraform-validate-refused` | `terraform init -backend=false`, then `terraform validate` | a module that reads an undeclared variable | init succeeds and validate refuses |
| `terraform-lint-refused` | `tflint` with the committed configuration | three modules, each breaking one rule | refused, naming the rule |
| `terraform-accepted` | format, init, validate, and lint | the committed configuration | every stage succeeds |

One lint fixture breaks `terraform_documented_variables`, which is in the `all` preset
the committed [`.tflint.hcl`](../../infra/terraform/.tflint.hcl) selects and not in
tflint's default. It is refused only when that file was actually read, which is the
point: a measured run with the configuration present but not passed by absolute path
linted on the defaults and passed.

## Tool pins

| Tool | Pinned as | Version |
|---|---|---|
| `actions/checkout` | commit SHA | v5.0.1 |
| `astral-sh/setup-uv` | commit SHA | v10.1.0 |
| `actions/upload-artifact` | commit SHA | v7.0.1 |
| `aquasecurity/setup-trivy` | commit SHA | v0.3.1 |
| `trivy` | release version, installed by the pinned action | v0.74.0 |
| `gitleaks` | SHA-256 of the release archive, checked after download | 8.30.1 |
| `helm` | SHA-256 of the release archive, checked after download | v3.19.0 |
| `kubeconform` | SHA-256 of the release archive, checked after download | v0.8.0 |
| `kubernetes-json-schema` | commit SHA of the schema repository, in the schema location | Kubernetes 1.34.0 standalone-strict |
| `terraform` | SHA-256 of the release archive, checked after download | 1.15.8 |
| `tflint` | SHA-256 of the release archive, checked after download | 0.64.0 |
| `runner image` | runner label | ubuntu-24.04 |

Every archive is checked against a digest committed in the workflow rather than
against the checksum file published beside it. A checksum served from the same place
as the artifact proves the download was not corrupted and nothing else. Each digest
recorded here was computed from the downloaded archive and matched the publisher's own
checksum on the day it was pinned.

The Terraform provider is pinned by the committed lock file, which `init` checks, and
the control runner refuses a tool reporting any version other than the one above.

`gitleaks git .` and not `gitleaks detect`. The latter still runs at 8.30.1 and is
deprecated in the tool's own source, and a gate built on a deprecated alias is a
gate that breaks on an upgrade nobody reviewed.

## Lane artifacts, and what may not cite them

The two scanning gates publish their JSON output and the bill-of-materials gate
publishes its CycloneDX documents, both for 30 days — the retention the
`default-checks` lane declares in the strategy data.

**Nothing there may be cited as the evidence for a published claim.** ADR 0005 D5's
rule is that a lane's raw output expires and that evidence for a claim is promoted
into a committed, redacted record under [`docs/proof/`](../proof/) before the window
closes. The two bills of materials under
[`docs/proof/security/sbom/`](../proof/security/sbom/) are such a promotion, made by
hand in `V1-S2-006`; this gate does not regenerate or replace them.

## What is not here

| Not in this lane | Where it belongs |
|---|---|
| A committed capable-runner workflow for the `cluster-smoke` and `real-runtime` lanes | Not scheduled, and blocked on ADR 0005 D6: committing one would name a runner label. The boundary it must satisfy is above, and both lanes stay `manual` |
| Moving the cluster-smoke scripts onto the provider guard | Not scheduled. A test asserts the gap still exists |
| A Trivy misconfiguration gate over the renders or the Terraform configuration | Not adopted, on a measurement. At `HIGH` and `CRITICAL`, Trivy v0.74.0 refuses both committed renders on one finding — `KSV-0109` reads the environment name `INFEROPS_MAX_OUTPUT_TOKENS` as a stored secret — refuses one of the nine insecure workload-policy fixtures, and has no check for any `kubernetes_*` Terraform resource: a privileged, host-network pod declared in Terraform scanned clean. The accepted workload policy is the rendered-manifest policy here, and the prerequisite suite's forbidden-provider, forbidden-resource, and secret-material rules are the Terraform ones |
| `bash -n` and `shellcheck` over `scripts/` | Not scheduled. Those scripts belong to the cluster and host lanes, and adding their gate to this lane without their lane would suggest the lane covers them |
| Certification of the claims the scanning gates touch | After a run on the service is promoted into a record. The gates have passed there; nothing has been promoted |
| Correcting the security records that still say no job has executed on the service | Not scheduled. `SECURITY.md`, the security README, the threat model, DR-11, ADR 0008, and the security baseline data carry their own suites and residual-risk wording |

## Limitations

- **The two new gates have not run on the service.** Their commands were run on one
  Windows host with Windows builds of the pinned versions. The nine older gates have
  passed there, twice, and no run of either set is promoted into a record.
- **A vulnerability scan is not deterministic.** Its database changes daily, so an
  unchanged commit can pass today and fail tomorrow. A green result dates rather
  than proves, and a new advisory turning `main` red is the gate working.
- **The lane is not hermetic.** Five gates consume the network: the two scanning gates
  pull a database and an image, and the secret-scan, `helm-chart`, and `terraform`
  gates download pinned archives — the last two also read schemas from a pinned commit
  and a provider checked against the lock file.
- **The lane rules read text.** A workflow can hand a cluster to a script; the
  cluster-free rule refuses every environment script, and the dispatch rules admit
  only scripts whose text calls the provider guard. That is a property of the scripts'
  text, not a proof of their behaviour.
- **The ownership check compares kinds and reads Terraform as text.** It would not see
  two owners of a kind the inventory does not name, and it resolves no module and no
  variable.
- **The whitespace and hard-tab checks are copied from CONTRIBUTING**, not read from
  it. Nothing compares the two, so they can drift.
- **`git diff --check` is a local check and is not a gate.** On a clean checkout it
  has nothing to read, so a step running it could not fail; a gate that cannot fail is
  worse than no gate, because it appears in the table. CONTRIBUTING keeps it where it
  works, which is before a change is opened.
- **Nothing here can support a claim above C1.** Every gate reads files, drives the
  deterministic mock, renders, validates, or scans what is pinned. The claims about a
  real runtime and a real cluster take no support from this workflow at all.
