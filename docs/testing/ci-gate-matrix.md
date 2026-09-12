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
> **No job below has ever run on GitHub Actions.** The workflow is committed, every
> command in it was run by hand on one Windows host, and what a hosted Ubuntu runner
> does with them is untested until the first pull request opens. A committed
> workflow is a configuration; a configuration is not a result. That distinction is
> the same one [ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
> D5 makes about evidence, and it is why the two claims the scanning gates touch are
> still uncertified: the scanner was run once, by hand, and nothing makes it recur.
>
> Running it that once was not ceremony. It found that the committed
> `.gitleaks.toml` had never parsed — its allowlist patterns were tables where the
> tool requires strings — so the scanner had been refusing the whole file and
> scanning nothing since `V1-S0-009`, under a test that read the file with a regular
> expression and never asked the question the tool asks.

## The one rule this follows

**A gate may enforce a claim. It may not raise what the claim rests on.** Every
ceiling in the table below is inherited from the evidence class the strategy already
gave the layer, never restated here — because a ceiling written in two places is a
ceiling that can be raised in one of them. Automating the mock lane makes it run on
every change; it does not make a mock certify a runtime.

## The gates

Nine gates run on every change. All nine are blocking.

| Gate | Runs | Layers | Claims it defends | Ceiling |
|---|---|---|---|---|
| `code-quality` | `ruff format --check`, `ruff check`, `mypy`, against the locked toolchain | — | none, stated | C0 |
| `default-lane-tests` | `python -m pytest -q`, with no marker expression | unit, contract-and-schema, architecture-inventory, adapter, mock-integration, documentation | sixteen | C1 |
| `expected-failures` | `python -m tools.ci_gates expected-failures` | contract-and-schema, documentation | three | C0 |
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

## What the normal lane may not do

Five prohibitions are checked rather than reviewed. Each is one plausible line away
from being broken.

| Prohibition | Why |
|---|---|
| No job reaches a Kubernetes cluster | A normal lane that can discover an ambient cluster can mutate an operator's cluster from a pull request. There is no `kubectl`, no `helm`, no `terraform`, no `kind`, and no provider selection in the workflow, and the check reads the file's text rather than its parsed steps — because a cluster can be reached from a script block, an action input, or an environment variable, and only the text sees all three |
| No job downloads the pinned model artifact | ADR 0005 D2's premise is that the lane every change goes through costs nothing. The artifact is 1.71 GiB |
| Every action is pinned by commit SHA | A tag is a name somebody can move. It is the argument this repository already makes for pinning a container image by digest |
| Every workflow declares its token permissions | The default grant is a repository-wide setting a workflow file cannot see. Declaring `contents: read` makes the grant reviewable in the diff that asks for it |
| Every program a gate documents is run by its job | This table is the thing most likely to be written once and then outlive the job it describes. The `distribution-build` row named `unzip` while the job used Python's `zipfile`, in the change that introduced both — harmless, and the exact drift the matrix exists to prevent. The check runs one way: a program the job runs and the matrix does not document is not reported |

Two more properties are checked for the same reason: every job declares a timeout
inside its lane's budget, because an unbounded job is a six-hour job; and every job
names `ubuntu-24.04` rather than `ubuntu-latest`, because a lane whose runner image
moves underneath it cannot attribute a failure to the change that appeared to cause
it.

## The expected-failure controls

`expected-failures` is the acceptance criterion *invalid contract and insecure
manifest fixtures fail*, made into a gate. It runs the published commands from a
shell and reads the **exit status**, which is the only thing a workflow can read —
a rule proved inside a pytest process is a rule the gate itself cannot enforce.

Thirty controls run, in four groups:

| Group | Command | Inputs | Required exit |
|---|---|---|---|
| `contract-refused` | `python -m tools.contract_validation` | every document in `contracts/workload/examples/invalid/` | non-zero |
| `contract-accepted` | `python -m tools.contract_validation` | every document in `contracts/workload/examples/valid/` | zero |
| `manifest-refused` | `python -m tools.workload_policy` | every bundle in `tests/security/fixtures/workload-policy/invalid/` | non-zero |
| `manifest-accepted` | `python -m tools.workload_policy` | the two committed chart renders | zero |

The two positive groups are not decoration. A validator broken into refusing
everything would pass a suite of negative controls perfectly, and a gate that read
only the negatives would report that as health. Each group also declares a minimum
count, so a glob that matched nothing fails instead of producing an empty, passing
run.

## Tool pins

| Tool | Pinned as | Version |
|---|---|---|
| `actions/checkout` | commit SHA | v5.0.1 |
| `astral-sh/setup-uv` | commit SHA | v10.1.0 |
| `actions/upload-artifact` | commit SHA | v7.0.1 |
| `aquasecurity/setup-trivy` | commit SHA | v0.3.1 |
| `trivy` | release version, installed by the pinned action | v0.74.0 |
| `gitleaks` | SHA-256 of the release archive, checked after download | 8.30.1 |
| `runner image` | runner label | ubuntu-24.04 |

The gitleaks archive is checked against a digest committed here rather than against
the checksum file published beside it. A checksum served from the same place as the
artifact proves the download was not corrupted and nothing else.

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
| Helm lint and template, rendered-manifest schema and policy validation, Terraform format, validate and security checks, and the ownership-overlap check | `V1-S4-001-PR2`. Until then the `helm`, `kubeconform`, and `terraform` commands CONTRIBUTING publishes are run by hand |
| A capable-runner workflow for the `cluster-smoke` and `real-runtime` lanes | `V1-S4-001-PR2`. Both lanes stay `manual`; no runner is labelled capable and the second half of ADR 0005 D6 stays open |
| `bash -n` and `shellcheck` over `scripts/` | Not scheduled. Those scripts belong to the cluster and host lanes, and adding their gate to this lane without their lane would suggest the lane covers them |
| Certification of the two claims the scanning gates touch | After a run **on the service**, promoted into a record. One run by hand on one host moved the `security-scan` layer to `implemented`; it says nothing about the next change |

## Limitations

- **No job here has run on the service.** Every command was executed locally on one
  Windows host; the runner behaviour is untested.
- **A vulnerability scan is not deterministic.** Its database changes daily, so an
  unchanged commit can pass today and fail tomorrow. A green result dates rather
  than proves, and a new advisory turning `main` red is the gate working.
- **The lane is not hermetic.** Three gates consume the network: two pull a
  vulnerability database and a container image, and one downloads a pinned archive.
  It is cheap and reproducible rather than isolated.
- **The whitespace and hard-tab checks are copied from CONTRIBUTING**, not read from
  it. Nothing compares the two, so they can drift.
- **`git diff --check` is a local check and is not a gate.** On a clean checkout it
  has nothing to read, so a step running it could not fail; a gate that cannot fail is
  worse than no gate, because it appears in the table. CONTRIBUTING keeps it where it
  works, which is before a change is opened.
- **The image-scan gate pulls the pinned runtime image**, which carries 392 operating
  system packages. That pull has never been timed on a hosted runner and shares the
  lane's fifteen-minute budget with the scan itself.
- **Nothing here can support a claim above C1.** Every gate reads files, drives the
  deterministic mock, or scans what is pinned. The claims about a real runtime and a
  real cluster take no support from this workflow at all.
