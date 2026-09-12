# V1-S4-001-PR1 change validation

Date: 2026-09-12

Change: [ADR 0012](../../architecture/decisions/ADR-0012-continuous-integration-service.md),
[the continuous-integration gate matrix](../../testing/ci-gate-matrix.md), and the
committed default-lane workflow.

Classification: **local static evidence for the change itself.** Every result below
was produced on one Windows host by running commands over files in this repository,
by building one container image, and by running three scanners. No cluster was
created or contacted, no model was downloaded, no runtime was started, no request was
served, and **no job was executed on GitHub Actions**.

Claim boundary: nine gates are committed as a workflow and as a matrix, the two agree
in both directions, the matrix maps every gate to the claims it defends or to a
recorded reason it defends none, the normal lane cannot reach a cluster or fetch the
model and neither is asserted, every action is pinned by commit SHA, and every
command the workflow runs produced the result recorded below **on this host**.

**What this record does not establish.** It is not evidence that any job passes on a
hosted Ubuntu runner; none has run there, and the first pull request is the first
execution. It is not evidence that the repository is free of vulnerabilities or
credentials — a scan reports what its database and rules knew on the day it ran. It
is not evidence for any claim about a runtime, a cluster, or a model, and it raises no
certification ceiling: automating the mock lane leaves a mock at `C1`.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.6` |
| `uv` | `0.9.16` |
| `pytest` | `8.4.2` |
| `jsonschema` | `4.26.0` |
| `PyYAML` | `6.0.3` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |
| Docker | `29.7.2`, build `a7dcaa6` |
| Trivy | `0.74.0` |
| Gitleaks | `8.30.1`, run from `zricethezav/gitleaks:v8.30.1` |

Gitleaks is not installed on this host. It was run from its published container
image, which is why this record names an image rather than a binary. The workflow
installs the binary from the same release and checks it against a committed SHA-256.

## Commands and results

### The gate-matrix suite this change adds

```text
python -m pytest tests/testing -q
1541 passed
```

Before this change the same command reported `1512 passed`. The twenty-nine new
results are `tests/testing/test_ci_gate_matrix.py`, parametrised across nine gates,
one workflow, and four prohibitions.

### The full default lane

```text
uv run --locked python -m pytest -q
8291 passed, 30 skipped, 14 deselected in 439.00s
```

The Sprint 3 completion review recorded `7876 passed, 30 skipped, 14 deselected` for
the same command. This change adds no skip and removes none, and the fourteen
deselected are the existing `realruntime` tests the committed marker expression
excludes — which is the lane property being automated, observed in the run that
automates it.

### Formatting, lint, and types

```text
uv run --locked ruff format --check .           359 files already formatted
uv run --locked ruff check .                    All checks passed!
uv run --locked python -m mypy                  Success: no issues found in 197 source files
```

### The expected-failure controls

```text
uv run --locked python -m tools.ci_gates expected-failures
30 controls produced the exit status the repository requires of them
exit 0
```

| Group | Controls | Required exit | Observed |
|---|---|---|---|
| `contract-refused` | 17 | non-zero | all 1 |
| `contract-accepted` | 3 | zero | all 0 |
| `manifest-refused` | 8 | non-zero | all 1 |
| `manifest-accepted` | 2 | zero | all 0 |

Both negative groups were confirmed at the command level before the runner existed:

```text
python -m tools.contract_validation contracts/workload/examples/invalid/missing-owner.yaml   -> 1
python -m tools.contract_validation contracts/workload/examples/valid/mock-llm-ci.yaml       -> 0
python -m tools.workload_policy tests/security/fixtures/workload-policy/invalid/no-network-policy.yaml -> 1
python -m tools.workload_policy charts/inferops-llm/ci/rendered/real.expected.yaml           -> 0
```

### The distribution build

```text
uv build
Successfully built dist\inferops-0.0.0.tar.gz
Successfully built dist\inferops-0.0.0-py3-none-any.whl
```

The source distribution carries exactly one `README.md` and no `docs/` tree; the wheel
carries `inferops/` and `inferops-0.0.0.dist-info/` and nothing else. Both were
inspected rather than assumed, with the same two checks the workflow runs.

### The API container image

```text
docker build -f deploy/api/Dockerfile -t inferops-api:ci .        exit 0
docker image inspect inferops-api:ci --format '{{ .Config.User }}'
65534:65534
```

The image's `tools/` directory holds `api_carrier` and `api_container` and nothing
else, which is the `.dockerignore` re-include list observed from inside the image
rather than read off the ignore file.

Nothing was pushed and nothing was loaded into a cluster. `platform-api-container-image`
is owned by the contributor's host in the ownership inventory, and this establishes
only that the Dockerfile still builds.

### The dependency scan

```text
scripts/security/scan-dependencies.sh
[vulndb] Artifact successfully downloaded
[uv] Detecting vulnerabilities...
[inferops-security] no CRITICAL,HIGH finding in uv.lock
exit 0
```

### The secret scan, and what running it found

This is the first time a secret scanner has been run against this repository, and it
found a defect in the first thing it read.

```text
gitleaks git . --config .gitleaks.toml --redact --no-banner
FTL Failed to load config  error="11 error(s) decoding: ... 'AllowList.Regexes[0]'
expected type 'string', got unconvertible type 'map[string]interface {}' ..."
exit 1
```

The committed `.gitleaks.toml` declared its allowlist patterns as a list of
`[[allowlist.regexes]]` tables carrying a `description` and a `regex`. Gitleaks
requires `regexes` to be a list of **strings**, so it refused the entire
configuration and scanned nothing. The file had been committed since `V1-S0-009`,
had a test reading it, and was wrong the whole time — because the test read it with a
regular expression and the tool had never been run. That is the `security-scan` layer
being `planned` doing its job: a configuration is not a result, and this is what the
difference looks like.

Two things were changed as a result. The configuration was rewritten to
`[[allowlists]]` blocks, one per exemption, which is the schema gitleaks accepts and
keeps each description beside the pattern it exempts. And
`test_the_secret_scan_configuration_is_committed_and_its_allowlist_resolves` now
parses the file with `tomllib` instead of matching quoted lines, asserts every
allowlist states what it exempts, asserts every exempted path exists, and compiles
every pattern — so a structure the tool would refuse is a failing test rather than an
invisible one.

The rerun is clean:

```text
gitleaks git . --config .gitleaks.toml --redact --no-banner
INF 134 commits scanned.
INF scanned ~9266485 bytes (9.27 MB) in 4m11s
INF no leaks found
exit 0
```

Two allowlisted directories and eleven published placeholder patterns remain exempt,
unchanged in substance and explained in
[the allowlist document](../../../.github/secret-scanning-allowlist.md) and as `EX-03`
in the security baseline.

**This is the first recorded run of a secret scanner against this repository**, and it
is what moves the `security-scan` layer from `planned` to `implemented` — the change
[ADR 0005](../../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)'s
own security note said should happen when, and only when, a run existed.
`secretScannerRunsRecorded` in the security baseline goes from `0` to `1`, and the
test that tied those two facts together now derives one from the other rather than
asserting both as constants.

**The claim does not move.** `no-credential-or-model-artifact-enters-public-history`
stays `planned`. One run, by hand, on one host, on one day is not a property of the
next change, and no job has executed on the service that would make it recur.

### The runtime image scan

```text
scripts/security/scan-runtime-image.sh
[ubuntu] Detecting vulnerabilities...  os_version="24.04" pkg_num=392
[inferops-security] no CRITICAL,HIGH finding in the pinned runtime image
exit 0
```

### The bills of materials

```text
scripts/security/generate-sbom.sh
wrote .artifacts/security/runtime-image.cyclonedx.json
  and .artifacts/security/python-dependencies.cyclonedx.json
exit 0
```

Both were written to `.artifacts/`, which version control ignores, and neither is
committed. The two CycloneDX documents under
[`docs/proof/security/sbom/`](../security/sbom/) are the promoted copies made by hand
in `V1-S2-006` and are untouched by this change.

### Whitespace, tabs, and links

```text
git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'        no matches
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"      no matches
git diff --check                                               no output
python -m pytest tests/testing/test_document_links.py -q       passed
```

Both whitespace checks found something the first time they were run as a gate rather
than as a habit.

The trailing-whitespace check returned twelve matches in
[the V1-S1-002-PR1 cumulative review record](../serving/v1-s1-002-pr1-cumulative-review-fixes.md),
where three runs of metadata lines used Markdown's trailing-two-space hard break.
CONTRIBUTING has published that this check returns no matches since before that record
was written. The three runs are now lists, which render as separate lines without the
trailing whitespace; no statement, result, or claim in the record is altered.

`git diff --check` is run here and is **not** a gate in the workflow. On a clean
checkout it has nothing to read, so a step running it could not fail, and a gate that
cannot fail is worse than no gate because it appears in the table. It stays where it
works: a local check before a change is opened.

The hard-tab check was drafted as `grep -nP '\t'` and failed on this host with
`-P supports only unibyte and UTF-8 locales`. That is a portability failure being
reported as a finding, which is the worst kind of gate. The workflow now uses
`grep -n "$(printf '\t')"`, which is the form CONTRIBUTING already published, so the
gate and the document run one check rather than two.

The link check failed once during this change, on
`docs/architecture/README.md`, because the ADR index row added for ADR 0012 cited
this record before it was written. It passes now that the record exists, and the
failure is recorded rather than removed: it is the gate finding the defect it exists
to find, in the change that added the gate.

## What was not run, and why

| Not run | Why |
|---|---|
| Any job on GitHub Actions | The workflow cannot execute until the branch is pushed and a pull request opens. The file is a configuration until then |
| `helm`, `kubeconform`, `terraform` gates | `V1-S4-001-PR2`'s boundary. They are still run by hand |
| `shellcheck` | Not installed on this host, and not in this lane. `bash -n` covers parsing; the static analyser is reported as not run, as every prior record here has reported it |
| Any Kubernetes operation | Out of this PR's boundary and out of this lane by construction. No cluster was contacted, no provider was selected, and no kubeconfig was read |
| Any real-runtime or model operation | Out of this PR's boundary. No model was downloaded and no runtime was started |

## The diff

The published diff was read in full. It carries no credential, no model artifact, no
generated host state, no personal filesystem path, and no content copied from a
private planning document. The two file paths it adds under `.github/` are a workflow
and nothing else; the scan output the workflow publishes is written to `.artifacts/`,
which version control already ignores, and none of it is committed.

Three counts published in prose were derived rather than typed: the nine gates in the
matrix document are compared against the data, the thirty expected-failure controls
are counted by the runner, and the four control groups are read out of the runner
rather than retyped beside it. One count was found wrong while writing this change and
corrected: the allowlist exempts **eleven** published placeholder patterns, not twelve.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Gate matrix maps every check to a V1 claim | **Met**, with the honest form: a gate names the claims it defends or records why it defends none, and a test refuses a row that does neither |
| Invalid contract and insecure manifest fixtures fail | **Met**, at the command level: 25 negative controls exit non-zero and 5 positive controls exit zero |
| Mock path runs in normal CI | **Met**. `default-lane-tests` runs the whole default lane, which includes the mock integration layer |
| Real-runtime/Kubernetes workflows are separately labelled | **Met for this boundary** by exclusion and by check: the normal lane cannot reach a cluster or the model, and both are enforced. The capable-runner workflow itself is `V1-S4-001-PR2` |
| CI does not download the full model unless explicitly scheduled | **Met**, and enforced rather than promised |

## Limitations

- **Nothing here ran on the service.** Every result is from one Windows host. The
  runner's behaviour — particularly `grep -P`, `sudo install`, and the Docker
  daemon's image inspect output — is untested on `ubuntu-24.04`.
- **Two gates are not deterministic.** The vulnerability database moves daily, so the
  dependency and image scans date rather than prove.
- **The secret scan was run from a container image**, not from the pinned release
  archive the workflow installs. The tool and version are the same; the installation
  path is not.
- **`security-scan` moved to `implemented` on the strength of one run.** That run was
  by hand, on one host, on one day, and nothing makes it recur. The two claims resting
  on the layer stay uncertified for exactly that reason; a run on the service,
  promoted into a record, is what would change that.
