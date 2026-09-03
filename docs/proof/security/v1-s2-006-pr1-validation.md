# V1-S2-006-PR1 change validation

Date: 2026-09-03

Classification: **local real evidence, one host, one day.** The vulnerability scans
and the SBOM generation below were executed against the pinned runtime image already
cached on this host and against the committed dependency lockfile, using Trivy
`0.74.0` and its vulnerability database as of `2026-09-03`. Nothing here is a
continuous result: no continuous-integration service is selected (ADR 0005 D6 stays
undecided), so a finding recorded below is current only as of the run that produced
it. No cluster was created, no model was downloaded, and no assessment by an outside
party was performed.

Claim boundary: the two new controls this change adds — a script-guard scan of the
pinned runtime image and a script-guard scan of the committed dependency lockfile —
are each backed by a shell function that exists, were each executed for real against
this repository's actual pinned image and actual lockfile, and each produced the
result recorded below. The security-baseline suite confirms the new controls'
shape, that both name a committed evidence record, that the scripts read the pinned
image from the runtime contract rather than a second hardcoded copy, and that every
count the existing documents state in prose is recomputed from the data.

**What this record does not establish.** It does not establish that the pinned image
or the pinned dependency set stays free of a `CRITICAL` or `HIGH` finding tomorrow —
Trivy's vulnerability database changes daily, and nothing here reruns the scan on a
schedule. It does not verify a build signature or attestation for the image; `DR-08`
still carries that gap. It does not close `DR-07`: nothing observes that any check's
own environment was actually resolved from the scanned lockfile, and the non-Python
tools this repository depends on remain pinned by prose rather than by that file.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.6` |
| `pytest` | `8.4.2` |
| `PyYAML` | `6.0.3` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |
| `uv` | `0.9.16` |
| Trivy | `0.74.0` |
| Trivy vulnerability database | version `2`, downloaded `2026-09-03T16:25:46Z` |
| Docker Engine | `29.7.2` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |

`shellcheck` is not installed on this host. That check is recorded as **not run**
below rather than skipped silently.

## What was scanned

| Target | How it is pinned |
|---|---|
| The runtime image, `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` | By digest, in [`deploy/serving/runtime/container-package.v1.json`](../../../deploy/serving/runtime/container-package.v1.json) and in [`deploy/serving/feasibility/llama-server.yaml`](../../../deploy/serving/feasibility/llama-server.yaml). The image was already present on this host from prior local-composition work; nothing was downloaded to run this scan. |
| The committed dependency lockfile, [`uv.lock`](../../../uv.lock), including its `test` and `checks` groups | The published distribution declares no runtime dependency (`dependencies = []` in `pyproject.toml`), so the dev and check tool groups are the only Python dependencies pinned anywhere in this repository. |

No InferOps-owned container image exists in V1. No `Dockerfile` or build step is
committed anywhere in this repository, and the only container image any manifest
references is the third-party runtime image above, owned by an external publisher.
The acceptance criterion "InferOps-owned image is non-root unless an ADR documents
incompatibility" is therefore **not applicable** rather than satisfied: there is no
InferOps-owned image for it to describe. What non-root, read-only-root-filesystem,
dropped-capabilities, and the rest of the container security defaults already apply
to is the same third-party image, over every manifest that runs it — enforced by the
pre-existing `run-as-non-root`, `read-only-root-filesystem`,
`forbid-privilege-escalation`, and `drop-all-capabilities` controls this change does
not touch.

## Commands and results

### The runtime-image guard, at the committed threshold

```text
bash scripts/security/scan-runtime-image.sh
[inferops-security] scanning ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384 for CRITICAL,HIGH findings
...
[inferops-security] no CRITICAL,HIGH finding in the pinned runtime image
exit code: 0
```

### The dependency guard, at the committed threshold

```text
bash scripts/security/scan-dependencies.sh
[inferops-security] scanning uv.lock (including dev and check groups) for CRITICAL,HIGH findings
...
[inferops-security] no CRITICAL,HIGH finding in uv.lock
exit code: 0
```

### The rejection path, demonstrated against real data rather than a fixture

Every fixture available would have had to be invented, and this project treats an
invented vulnerability the same way it treats an invented severity score: as an
overclaim. The real image already carries findings below `CRITICAL`/`HIGH`, so the
guard's failure path was exercised by passing a real, lower threshold instead of
fabricating one:

```text
bash scripts/security/scan-runtime-image.sh MEDIUM
[inferops-security] scanning ghcr.io/ggml-org/llama.cpp@sha256:...15ad384 for MEDIUM findings
...
[inferops-security] FAILED: ghcr.io/ggml-org/llama.cpp@sha256:...15ad384 carries a MEDIUM
finding with no recorded exception; see .artifacts/security/runtime-image-scan.json
exit code: 1
```

The guard refuses to report success once a real finding at or above the requested
threshold exists, and reports success once none does — the property the control
claims.

### SBOM generation

```text
bash scripts/security/generate-sbom.sh
[inferops-security] generating an SBOM for ghcr.io/ggml-org/llama.cpp@sha256:...15ad384
[inferops-security] generating an SBOM for uv.lock (including dev and check groups)
[inferops-security] wrote .artifacts/security/runtime-image.cyclonedx.json and .../python-dependencies.cyclonedx.json
```

Both outputs were checked for a personal filesystem path (none found) and promoted,
unmodified, into this repository:

| SBOM | Format | Components | Committed at |
|---|---|---|---|
| Runtime image | CycloneDX `1.7` JSON | 393 | [`sbom/v1-s2-006-pr1-runtime-image.cyclonedx.json`](sbom/v1-s2-006-pr1-runtime-image.cyclonedx.json) |
| Python dependencies (dev and check groups) | CycloneDX `1.7` JSON | 24 | [`sbom/v1-s2-006-pr1-python-dependencies.cyclonedx.json`](sbom/v1-s2-006-pr1-python-dependencies.cyclonedx.json) |

An SBOM lists what a target is built from; it carries no vulnerability data, which is
why `trivy`'s own output above notes that `--format cyclonedx` disables vulnerability
scanning. The vulnerability results below come from the guard commands, not from
these files.

### Full-severity findings, for the record

Recorded here because a dated, itemised finding is evidence; an unqualified
vulnerability count is the durable posture claim `no-vulnerability-figure-is-published`
refuses. Both counts below are from a scan run against the database version stated in
Environment and are not current beyond that day.

| Target | CRITICAL | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| Runtime image (392 OS packages, Ubuntu 24.04) | 0 | 0 | 622 | 59 |
| `uv.lock`, dev and check groups | 0 | 0 | 1 | 0 |

The one dependency finding: `CVE-2025-71176` in `pytest 8.4.2` (denial-of-service or
privilege escalation via insecure temporary-directory handling), fixed in `9.0.3`.
`MEDIUM`, so it does not cross the committed blocking threshold and no exception was
recorded. It is not fixed by this change: `pyproject.toml` pins `pytest>=8.3.4,<9`,
and widening that pin is dependency-version work outside this PR's stated scope
(container security defaults, scanning, SBOM generation, and an explicit severity
policy) — it is named here rather than silently left out of the record.

No `CRITICAL` or `HIGH` finding exists in either target as of this run, so no
exception was recorded in the security baseline for this change.

### The security suite

```text
python -m pytest tests/security -q
649 passed
```

Run without `uv` and passing on this host; `uv sync --locked` was also run
separately and reported nothing to change.

### The full suite, to show nothing else moved

```text
uv run --locked python -m pytest -q
5452 passed, 25 skipped in 35.59s
```

The twenty-five skips are the pre-existing ones: layers whose markers are
deselected by default because they need a cluster or a model. This change
registers no new marker and deselects nothing.

### Formatting, linting, and typing

```text
uv run --locked ruff check .
All checks passed!

uv run --locked ruff format --check .
255 files already formatted

uv run --locked python -m mypy
Success: no issues found in 142 source files
```

### JSON well-formedness

```text
python -m json.tool docs/security/security-baseline.v1alpha1.json
python -m json.tool docs/proof/security/sbom/v1-s2-006-pr1-runtime-image.cyclonedx.json
python -m json.tool docs/proof/security/sbom/v1-s2-006-pr1-python-dependencies.cyclonedx.json
(all three parse; output discarded)
```

### Shell scripts

```text
bash -n scripts/environment/*.sh scripts/security/*.sh
(no output; all eleven scripts parse)
```

`shellcheck -x -S style scripts/environment/*.sh scripts/security/*.sh` was **not
run**: `shellcheck` is not installed on this host, matching the existing gap this
repository already records for it. The four new scripts follow the same
`set -Eeuo pipefail`, `inferops::` namespacing, and guard-function shape as
`scripts/environment/lib.sh`, by inspection rather than by a static analyser.

### Whitespace and links

```text
git diff --check main...HEAD
(no output)

git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
(no matches)

git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
(no matches)
```

The relative-link check from `CONTRIBUTING.md`, run over every tracked Markdown file:
no `BROKEN` line.

## What the diff was reviewed for

| Checked for | Result |
|---|---|
| Credentials, tokens, keys | None. No SBOM or scan output was inspected to contain a credential-shaped string before it was committed |
| Private planning content, prompts, or unpublished strategy | None. No sprint, backlog, or roadmap vocabulary appears; nothing from `InferOps-Planning` is copied |
| Personal filesystem paths, hostnames, usernames | None in either committed SBOM, checked by pattern before promotion; none in any new or edited Markdown file |
| Generated files or host state | None committed. Raw scan output stays under `.artifacts/security/`, which was already ignored before this change |
| Model artifacts | None |
| Scope beyond this pull request | None. No `Dockerfile`, chart, admission policy, or continuous-integration workflow is added — ADR 0005 D6 stays undecided, and this change does not decide it |
| Reserved vocabulary | Every new and edited sentence in Markdown and in the baseline data was written to avoid `secure`, `hardened`, `audited`, `compliant`, `production-ready`, and the rest outside a denial; the existing suite is the check that actually holds this |

## Limitations

- **One host, one day.** Every finding above was produced on the machine and the
  vulnerability-database version named in Environment. A rerun tomorrow, against a
  newer database, can find something today's run did not.
- **No provenance is verified.** `DR-08` still carries the gap between "the digest
  that ran" and "who built it and how."
- **No continuous-integration lane runs either guard.** ADR 0005 D6 remains
  undecided; both scripts are run by a contributor, by hand, the way every other
  check in this repository is.
- **The dependency scan covers Python distributions only.** `shellcheck`,
  `kubeconform`, `kind`, `kubectl`, and the container engine are pinned by prose,
  not by `uv.lock`, and Trivy was not asked to look for them.
- **A scanner is a detector, not a proof of absence.** A vulnerability Trivy's
  database does not yet carry is not a vulnerability this scan can report, in either
  target.
