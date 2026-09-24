# V1-S5-006-PR2: the domain, API, and API-telemetry suites, run at a named revision

Date: 2026-09-24

Three certified claims rested on records that name only the branch point their
working tree started from, not the tree that ran:
[the domain parser's](../domain/v1-s1-001-pr1-validation.md) names `b2f1bee`,
[the API's](../serving/v1-s1-005-pr1-validation.md) name `eccc5fe` and `8786620`, and
[the API telemetry record](../telemetry/v1-s1-008-pr1-validation.md) names `aadf4c5`.
Nothing committed says what those trees held, and
[the V1 evidence index](../v1-evidence-index.md) lists all three among the records
whose code revision is not recorded. Each of the three claims is about code in `src/`
that its suites drive in process, so the gap closes the honest way: the same suites,
run again, in a checkout whose revision is exact.

**This record is one run of three suites, cited by three register records.** Each
claim has its own section below, with its own level, results, and limitations, and a
reader of one should not carry another's over to it. The levels are project-defined,
under [the evidence-level specification](../../testing/evidence-levels.md); they are
not an ISO, NIST, regulatory, or industry certification standard.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `e145a6e6fe2417a18e6d77a7f14751ec71786888`, the merge of `V1-S5-006-PR1`, checked out as a detached worktree created for this run. `git status --porcelain --untracked-files=all` printed nothing before the first command and nothing after the last, so no tracked change and no untracked file was present while the suites ran |
| Python | `3.12.12`, provisioned by `uv` `0.9.16` from the lockfile |
| pytest | `8.4.2` |
| Supporting records | The three records named above, which this run repeats |

The worktree's revision is the revision that ran, not a base the run started from:
nothing was edited in it.

## Environment

| Field | Value |
|---|---|
| Environment | `local-process` |
| Provider | `not-applicable` |
| Hardware class | `cpu` |

One Windows 11 Enterprise 10.0.26200 host, commands run in Git Bash from the
worktree's root. No container, cluster, model, or runtime was started; every suite
drove the code it tests inside the pytest process.

## Method

| Command | Started (UTC) | Result |
|---|---|---|
| `uv run --locked python -m pytest tests/domain -q` | `2026-09-24T10:03:40Z` | `398 passed, 18 skipped` |
| `uv run --locked python -m pytest tests/api -q` | `2026-09-24T10:04:06Z` | `373 passed` |
| `uv run --locked python -m pytest tests/serving -q` | `2026-09-24T10:04:15Z` | `1028 passed, 2 skipped` |
| `uv run --locked python -m pytest -m mockintegration -q` | `2026-09-24T10:05:01Z` | `373 passed, 14336 deselected` |
| `uv run --locked python -m pytest tests/api/test_api_observability.py tests/telemetry/test_api_telemetry_agreement.py -q` | `2026-09-24T10:05:56Z` | `171 passed` |

Each command was then repeated per module, to say which module supports which claim:

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/domain/test_workload_domain.py -q` | `108 passed` |
| `uv run --locked python -m pytest tests/domain/test_workload_schema_agreement.py -q` | `163 passed` |
| `uv run --locked python -m pytest tests/domain/test_workload_validation.py -q` | `94 passed, 18 skipped` |
| `uv run --locked python -m pytest tests/api/test_api_adapter_selection.py -q` | `44 passed` |
| `uv run --locked python -m pytest tests/api/test_api_observability.py -q` | `41 passed` |
| `uv run --locked python -m pytest tests/telemetry/test_api_telemetry_agreement.py -q` | `130 passed` |

Every skip was read with `-rs`. The 18 in `tests/domain` are all in
`test_workload_validation.py`, and each gives the reason that its invalid fixture
"is not a semantic layer fixture" — the fixture belongs to the structural layer, which
the schema suites cover, and the semantic rules are not asked of it. The 2 in
`tests/serving` are in `test_model_lifecycle.py`, because "this host does not permit
creating a symbolic link"; neither bears on any claim below.

What would have falsified each claim is the same thing the earlier records would have
shown: a failing test in the modules named under it.

## The workload domain parses a contract document into typed objects

| Field | Value |
|---|---|
| Claim supported | `the-workload-domain-parses-a-contract-document-into-typed-objects` |
| Evidence level | `C2` |
| Why this level and not the next | The workload domain package executed, called directly by the suites, and the claim declares nothing else material; nothing was substituted. Nothing representative was declared and no criterion was registered before the run, so it is not `C3` |
| Components that executed | the workload domain package in `src/inferops/domain/workload`, called in process; pytest |
| Substitutions | none |
| Workload | operator-issued: the committed valid and invalid contract fixtures and documents written into the suites |

Results: `test_workload_domain.py` reported 108 passed, `test_workload_schema_agreement.py`
163 passed, and `test_workload_validation.py` 94 passed and 18 skipped, at
`e145a6e6fe2417a18e6d77a7f14751ec71786888`. The whole of `tests/domain` reported 398
passed and 18 skipped; the other 33 are the serving adapter conformance and test-double
modules that share the directory and do not bear on this claim.

## The inference API serves five routes with explicit adapter selection

| Field | Value |
|---|---|
| Claim supported | `the-inference-api-serves-five-routes-with-explicit-adapter-selection` |
| Evidence level | `C1` |
| Why this level and not the next | The API executed in process, but the claim declares the serving runtime material, and no runtime was reached: route checks ran against the labelled mock adapter or controlled doubles, and the real selection composed the real adapter over a transport that answers nothing |
| Components that executed | the InferOps ASGI application, driven through its own calling convention; the mock serving adapter; the real adapter, constructed by the selection tests; pytest |
| Substitutions | the serving runtime, by a stub transport and the mock adapter — claim-material; the model, by the mock's fixture — not material to a claim about routes and selection |
| Workload | operator-issued: fixed requests written into the committed suites |

Results: `tests/api` reported 373 passed, `tests/serving` 1028 passed and 2 skipped,
and the `mockintegration` marker 373 passed, at
`e145a6e6fe2417a18e6d77a7f14751ec71786888`. The adapter-selection module, which holds
the refusal of an unset, empty, misspelled, or incomplete selection, reported 44 passed.

## The API emits catalog metrics and structured request records

| Field | Value |
|---|---|
| Claim supported | `the-api-emits-catalog-metrics-and-structured-request-records` |
| Evidence level | `C1` |
| Why this level and not the next | The API and its telemetry executed in process, composed with the labelled mock adapter; the claim declares the real adapter, the runtime, and the model material, and all three were substituted |
| Components that executed | the InferOps ASGI application with its telemetry registry and structured-record sink; the mock serving adapter; pytest |
| Substitutions | the real adapter, the serving runtime, and the model, by the mock adapter replaying a fixture — all claim-material |
| Workload | operator-issued: fixed requests written into the two suites |

Results: `test_api_observability.py` reported 41 passed and
`test_api_telemetry_agreement.py` 130 passed, 171 together, at
`e145a6e6fe2417a18e6d77a7f14751ec71786888`.

## Limitations

- One run, on one Windows host, on 2026-09-24. It says what these suites report for
  the tree at `e145a6e6fe2417a18e6d77a7f14751ec71786888`, and nothing about any other
  tree.
- **It does not recover what the earlier records ran.** The suites have grown since
  those records were written, which is why every count here is larger than theirs, and
  nothing here says the trees they ran were the same as this one. What this run adds is
  a record of the same behaviour at a revision that is exact.
- Every suite ran in process. Nothing crossed a socket, no runtime or model was
  started, and the API was driven through its own calling convention.
- The mock adapter answered every API check that needed a backend, which is why two of
  the three records are `C1`.

Does not establish:

- That the API answers a network request, or that a real runtime's answers pass through
  the API or its telemetry as the mock's did.
- That the suites pass on Linux, on macOS, or in continuous integration.
- That the earlier records' results were obtained from the tree named here.

## Authorisation

Required: no. The run executed committed tests in process, in a detached worktree of
this repository, and started no model, runtime, container, or cluster.

Granted by: not required.

Review: read by an independent reviewer before this change was pushed; what the review
found is in [the change's validation record](v1-s5-006-pr2-validation.md).
