# V1-S1-009-PR1 developer quick-start validation

Date: 2026-09-01

This record supports the
[Sprint 1 developer quick start](../../developer-quick-start.md). It records the
commands executed while writing the page, the evidence class each result can carry,
and the real-runtime work that was deliberately not performed.

> [!NOTE]
> **Post-record resolution (2026-09-02):** the authorization-gated real command
> was executed during Sprint 1 completion remediation, after this documentation
> PR merged and before the Sprint 1 review gate. The final combined adapter/API
> lane passed all 14 checks twice; see the
> [Sprint 1 real-runtime closure record](../serving/v1-s1-real-runtime-closure.md).
> The original pre-merge command record below remains unchanged historical
> evidence, and the timing difference is disclosed rather than rewritten.

## Classification

| Result | Evidence class | Ceiling |
|---|---|---|
| Workload scaffolding, validation, and generated tests | `local-static` | `C0` |
| API end-to-end suite against the committed mock adapter | `mock` | `C1` |
| Real-adapter smoke invoked with no runtime configuration | `documented-unexecuted`; all tests skipped | none |

No result in this record is local-real, cloud-real, estimated, synthetic, or
production experience. No model was downloaded, no runtime or cluster was started,
no socket was opened, and no paid service was used.

## Provenance

| Input | Value |
|---|---|
| Base revision | `aadf4c5` |
| Branch | `docs/v1-s1-009-developer-quickstart` |
| Dependency resolution | committed `uv.lock`, unchanged; commands used `uv run --locked` |
| Product behavior changed | none |
| Contracts, ADRs, schemas, fixtures, and deployment files changed | none |

## Environment

The safe commands ran from Windows PowerShell on one Windows development host with
`uv 0.9.16`, CPython `3.12.12`, and Git `2.45.1.windows.1`. Multiline POSIX examples
were entered as equivalent single-line PowerShell commands. The results are
statements about this checkout and this dependency lock, not cross-platform
certification. The model/runtime hardware requirements remain the one-host
measurements linked from the quick start.

## Method and results

Both generated workloads were written under `.quickstart`, validated from disk,
tested without edits, and removed after the run.

| Command | Result | Classification |
|---|---|---|
| `uv sync --locked` | resolved and checked 23 packages; lock unchanged | `local-static` |
| `uv run --locked python -m tools.workload_scaffold ... --profile mock-llm ... --into .quickstart` | generated three files and validated the contract from disk | `local-static` |
| `uv run --locked python -m tools.contract_validation .quickstart/quickstart-mock/workload.yaml` | `ok` | `local-static` |
| `uv run --locked python -m pytest .quickstart/quickstart-mock/tests -q` | `7 passed` | `local-static` |
| `uv run --locked python -m pytest tests/api/test_api_end_to_end_mock.py -q` | `31 passed` | `mock` |
| `uv run --locked python -m tools.workload_scaffold ... --profile synchronous-llm ... --into .quickstart` | generated three files and validated the contract from disk | `local-static` |
| `uv run --locked python -m tools.contract_validation .quickstart/quickstart-real/workload.yaml` | `ok` | `local-static` |
| `uv run --locked python -m pytest .quickstart/quickstart-real/tests -q` | `8 passed` | `local-static` |
| `uv run --locked python -m pytest tests/realruntime/test_api_real_adapter_smoke.py -m realruntime -q` | `7 skipped`; required runtime settings were absent | `documented-unexecuted` |
| Scoped removal of `.quickstart` followed by an existence check | removed; no generated workload remains | `local-static` |
| `uv run --locked ruff check .` | `All checks passed!` | `local-static` |
| `uv run --locked ruff format --check .` | `199 files already formatted` | `local-static` |
| `uv run --locked python -m mypy` | no issues in 108 source files | `local-static` |
| `uv run --locked python -m pytest -q` | `4876 passed, 25 skipped, 14 deselected` | evidence classes remain those assigned to the selected test layers |
| `git diff --check` and changed-Markdown whitespace/tab checks | no findings | `local-static` |
| Repository-wide relative Markdown link check | four pre-existing broken links in `docs/proof/domain/v1-s1-001-pr2-validation.md`; no link introduced by this change is broken | `local-static` |

The real-runtime command was invoked to verify its safe no-configuration behavior.
A skipped session is not a successful smoke run and is not evidence that a real
adapter can reach a runtime.

The four repository-wide link findings are unchanged from the base revision and
outside this change. They are reported rather than repaired because doing so would
widen a documentation-only quick-start PR into unrelated historical-record edits.

## Limitations

- The repository ships an ASGI application and no server. Mock API requests were
  driven in-process; no network request was made.
- The generated synchronous workload was validated, not deployed.
- The real adapter, pinned runtime, and pinned model were not executed.
- The documented port-forward was not started. A future host-side real smoke using
  it proves the adapter path through a tunnel, not the in-cluster Service path.
- No latency, throughput, concurrency, quality, capacity, or cost was measured.
- The page documents both POSIX shell and Windows PowerShell cleanup, but only the
  Windows workflow was executed for this record.
- Kubernetes packaging, automated model acquisition, and production operation are
  outside this change and are not described as complete.

## Authorization

No authorization-gated action was taken. The real-runtime lane was allowed to skip;
no model artifact was downloaded and no runtime process, container, namespace, or
cluster was created.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Commands are executed before merge | met for every safe command; the hardware/model-dependent real run is explicitly not executed |
| Mock and real evidence limitations are explicit | met in the quick start and this record |
| Required model/runtime prerequisites link to the ADR | met; the quick start links ADR 0001, ADR 0002, and the measured prerequisite summary |
| Cleanup is included | met for generated files and linked for an authorized runtime trial |

The developer quick-start documentation criterion is met by this change. Parent
Sprint acceptance that requires a local real-runtime run or later packaging remains
unchanged; this documentation record cannot satisfy it.

## Independent review

An independent post-commit review found five documentation defects and no private
information leakage or product-scope change. The follow-up corrected cleanup to
remove only the two generated workloads, added the missing host-to-ClusterIP tunnel
and its limitation, made the Windows/POSIX shell distinction explicit, adopted the
canonical `documented-unexecuted` evidence label, and corrected the real suite from
one to three completion requests. The review also questioned the recorded package
count; the console output was rechecked and confirms both operations covered 23
packages, so that result remains unchanged.

The first full-suite rerun after those edits reported `1 failed, 4875 passed, 25
skipped, 14 deselected`: the security documentation guard rejected a reserved term
in the package-check result. After the wording was corrected, the targeted guard
reported `91 passed` and the final full default lane again reported `4876 passed,
25 skipped, 14 deselected`.
