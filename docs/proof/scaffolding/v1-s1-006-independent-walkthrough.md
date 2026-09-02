# V1-S1-006 independent clean-checkout walkthrough

Date: 2026-09-02

This record closes the independent walkthrough evidence requested by
`V1-S1-006`. A reviewer other than the implementation author followed the
published developer quick start from a clean detached worktree, without editing
the generated output. The executor was a Codex agent operating under the user's
explicit request to close the Sprint 1 blockers; this record does not represent
the executor as a human.

## Classification

| Field | Value |
|---|---|
| Evidence class | `local-static` for scaffolding and validation; `mock` for the API end-to-end suite |
| Ceiling | `C0` for local-static results; `C1` for the mock-backed API result |
| What ran | Locked dependency setup, both documented scaffold commands, both offline validations, both generated-project suites, and the mock API end-to-end suite |
| What did not run | A real model, runtime image, container engine, cluster, network API request, paid service, or scanner |
| Claims supported | A clean checkout can generate, validate, and test both documented workload profiles without source edits; the mock API workflow passes independently |

## Provenance

| Input | Value |
|---|---|
| Repository revision | `96503868fcbcbf3e473f136989708ebc94892504` |
| Source branch | `main` |
| Review environment | Clean detached Git worktree created for this walkthrough and removed afterwards |
| Instructions followed | `docs/developer-quick-start.md` |
| Dependency resolution | Committed `uv.lock`, consumed with `--locked` |
| Executor | Independent Codex reviewer, not the implementation author |

## Environment

The walkthrough ran on a contributor-owned Windows workstation using CPython
3.12.12, pytest 8.4.2, and the dependency versions in the committed lockfile.
Generated workloads were placed only in the temporary worktree's `.quickstart`
directory. No hostname, username, personal path, credential, prompt, completion,
or environment-variable value is retained in this record.

## Method

The reviewer performed the quick start in its published order:

1. provision the locked environment with `uv sync --locked`;
2. generate the `quickstart-mock` workload with every documented argument;
3. validate its on-disk contract and execute its generated test suite;
4. execute `tests/api/test_api_end_to_end_mock.py`;
5. generate the `quickstart-real` synchronous workload with every documented
   argument; and
6. validate its on-disk contract and execute its generated test suite.

Neither generated workload was edited. The temporary worktree was removed after
the results were collected.

## Results

| Check | Result |
|---|---|
| `uv sync --locked` | Passed; 23 locked packages installed and the lockfile was unchanged |
| Mock scaffold | Passed; three files generated and the contract validated from disk |
| Mock offline validation | `ok` |
| Mock generated-project suite | 7 passed |
| Mock API end-to-end suite | 31 passed |
| Synchronous scaffold | Passed; three files generated and the contract validated from disk |
| Synchronous offline validation | `ok` |
| Synchronous generated-project suite | 8 passed |

No stale placeholder, source edit, overwrite, mock-to-real fallback, or retained
generated workload was observed.

## Limitations

- The executor was an independent Codex agent rather than a human second
  engineer. The result establishes repeatability from a clean checkout; the user
  remains the authority for accepting that distinction at the Sprint review gate.
- The synchronous profile was generated and validated but not deployed.
- The mock API was driven in process through ASGI; no network socket was opened.
- This record supplies no real-runtime evidence and makes no serving, latency,
  throughput, model-quality, capacity, or production claim.
- The run covered one Windows host and does not certify another operating system.

## Authorization

The user explicitly requested correction of all outstanding Sprint 1 blockers.
This walkthrough used only a temporary local checkout and the repository's locked
dependencies. It downloaded no model, started no runtime, provisioned no paid
capacity, and modified no external service.
