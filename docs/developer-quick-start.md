# Sprint 1 developer quick start

Status: the mock workflow on this page was executed on one Windows development
host. The optional real-runtime API smoke is implemented but was **not** executed
by this change: it is manual, needs explicit authorization, and requires a capable
host with the pinned model and runtime already running.

This page is the shortest path from a clean checkout to two generated, validated
workload contracts and a mock inference request through the InferOps ASGI API. It
does not deploy a workload. InferOps ships no ASGI server, so the API checks drive
the application in-process and no `curl` command can reach it over a socket.

## Evidence labels

| Path | Evidence produced here | What it does not establish |
|---|---|---|
| Contract generation and validation | `local-static` | Deployment or serving |
| Mock API execution | `mock` | Runtime behavior, model quality, latency, throughput, or token accounting |
| Optional real API smoke | `local real runtime` only after a completed, recorded run | Production experience or support on another host |
| A skipped real-runtime test | `documented/unexecuted` | Any real-runtime claim |

[The mock and real serving boundary](serving/mock-and-real-boundary.md) is the
governing rule: mock evidence proves the consumer and contract, never the real
provider.

## Prerequisites

For the safe mock path, use a repository checkout, Git, `uv`, and CPython 3.12.
[`uv sync --locked`](#set-up-the-checkout) provisions the committed dependency set.
The accepted toolchain is recorded in
[ADR 0009](architecture/decisions/ADR-0009-python-toolchain.md).

The optional real path has additional measured requirements. Read both accepted
decisions before authorizing it:

- [ADR 0001](architecture/decisions/ADR-0001-local-development-environment.md)
  selects the local environment and cleanup boundary.
- [ADR 0002](architecture/decisions/ADR-0002-model-and-serving-runtime.md) selects
  the pinned `llama-server` image and Qwen3-1.7B GGUF revision.
- [Supported-host prerequisites](prerequisites.md) summarizes the one measured
  Windows host: AVX2 CPU, no accelerator required, a 3 GiB serving-pod limit,
  7.60 GiB available to the container VM in the recorded run, and about 2.0 GiB
  added for weights and the runtime image. These are observations from one host,
  not supported-platform minima.

The selected artifacts need no account, API key, or paid subscription. They still
need network, disk, compute, and an approximately 1.71 GiB model download. Do not
download or run them without the host owner's explicit authorization.

## Set up the checkout

Run every command on this page from the repository root:

```sh
uv sync --locked
```

`--locked` refuses to re-resolve the committed dependency set. If this fails,
check that `uv` is installed, the host can reach its configured package source,
and CPython 3.12 can be provisioned.

## Run the safe mock workflow

### 1. Scaffold a mock workload

```sh
uv run --locked python -m tools.workload_scaffold \
  --name quickstart-mock \
  --owner team-platform \
  --environment ci \
  --profile mock-llm \
  --runtime-profile resource-conscious \
  --cpu 250m \
  --memory 128Mi \
  --tenant demo \
  --cost-center demo-cost-center \
  --data-classification public \
  --description "Deterministic quick-start contract test; never real-runtime evidence." \
  --into .quickstart
```

Success begins with `ok generated`, lists `README.md`,
`tests/test_workload_contract.py`, and `workload.yaml`, and states that the
contract was validated from disk. The command refuses an occupied
`.quickstart/quickstart-mock` directory rather than overwriting it.

### 2. Validate and test the generated contract

```sh
uv run --locked python -m tools.contract_validation \
  .quickstart/quickstart-mock/workload.yaml
uv run --locked python -m pytest .quickstart/quickstart-mock/tests -q
```

The verified results were `ok` for the contract and `7 passed` for the generated
test. These checks establish contract conformance only; nothing was deployed or
served.

### 3. Exercise the mock API

```sh
uv run --locked python -m pytest tests/api/test_api_end_to_end_mock.py -q
```

The verified result was `31 passed`. The suite explicitly selects the `mock`
adapter, starts the ASGI application, calls all five routes, and shuts it down. Its
completion request has this user-facing shape:

```json
{
  "model": "mock-fixed-fixture",
  "messages": [
    {"role": "user", "content": "In one sentence, what is a pod?"}
  ]
}
```

The response is HTTP-shaped in memory. It carries
`_inferops.adapterKind: "mock"`, returns the committed deterministic fixture
content, and reports `usage: null` because the mock measured no tokens. See
[the inference API](serving/inference-api.md) for the full route, request, response,
health, and error contract.

## Prepare the optional real workflow

The real profile can be generated and validated safely without starting a runtime:

```sh
uv run --locked python -m tools.workload_scaffold \
  --name quickstart-real \
  --owner team-platform \
  --environment local \
  --profile synchronous-llm \
  --runtime-profile resource-conscious \
  --cpu 6 \
  --memory 3Gi \
  --tenant demo \
  --cost-center demo-cost-center \
  --data-classification internal \
  --description "Local real-runtime smoke workload; evidence requires an authorized run." \
  --into .quickstart
uv run --locked python -m tools.contract_validation \
  .quickstart/quickstart-real/workload.yaml
uv run --locked python -m pytest .quickstart/quickstart-real/tests -q
```

The verified results were `ok` and `8 passed`. The generated contract names the
accepted real model/runtime combination, but validation is not evidence that the
runtime exists or that the workload was deployed.

## Run the optional authorized real-adapter smoke

Stop here unless the host owner has explicitly authorized the model download and
runtime execution. If the pinned runtime is not already serving the hash-verified
model, use the bounded, staged
[feasibility workflow](serving/feasibility-workflow.md), including its authorization
gate and teardown. Do not substitute another model, a moving image tag, or a mock.

With the pinned runtime already reachable, set every variable documented under
[real runtime configuration](serving/real-runtime-configuration.md#required-configuration)
and the three required API variables:

| Variable | Required value or constraint |
|---|---|
| `INFEROPS_SERVING_ADAPTER` | exactly `real`; there is no default or mock fallback |
| `INFEROPS_MODEL_IDENTIFIER` | a non-mock platform identifier, such as `qwen3-1-7b-instruct` |
| `INFEROPS_REQUEST_TIMEOUT_MS` | a positive, explicitly chosen request deadline |

Then enter the real lane deliberately:

```sh
uv run --locked python -m pytest \
  tests/realruntime/test_api_real_adapter_smoke.py -m realruntime -q
```

A genuine pass runs seven checks covering explicit real-adapter selection,
readiness, runtime/model metadata, one completion, runtime-derived token counts,
identifier propagation, and the API's refusal boundary. If required variables are
unset, the result is `7 skipped`; that means **the real workflow did not run**. A
passing console session is only an input to an evidence record that also names the
runtime digest, model revision and hash, environment, authorization, exact command,
result, and limitations.

## Troubleshooting

| Symptom | Meaning and next check |
|---|---|
| `uv` reports the lock would change | Stop. Run the command with `--locked` from the repository root; do not refresh dependencies as part of this workflow |
| Scaffolding reports the destination already exists | Expected overwrite protection. Inspect or remove only the named `.quickstart` directory, then rerun |
| Contract validation reports findings | Read the field and canonical rule. Do not edit generated platform code; correct the workload declaration |
| Generated tests cannot import `inferops` or `tools` | Run them from the repository root through `uv run --locked` |
| Real smoke reports `7 skipped` | Required runtime/API variables are absent. This is an unexecuted lane, not a pass |
| Real smoke says the backend is loading or unreachable | Check the runtime endpoint and wait within the authorized startup budget; readiness remains false until the model can answer |
| A real selection fails configuration | Check all variables in the linked runtime configuration. InferOps refuses incomplete real configuration and never falls back to mock |

## Cleanup

Remove only the generated quick-start directory:

```sh
rm -rf -- .quickstart
```

On Windows PowerShell:

```powershell
Remove-Item -LiteralPath .quickstart -Recurse -Force
```

If the authorized feasibility workflow created a runtime namespace or cluster,
complete its [Stage 8 teardown](serving/feasibility-workflow.md#stage-8--teardown-and-residue)
and verify residue. A host-side model cache survives unless the host owner removes
it deliberately; never delete an unspecified cache or prune the container engine.

## Verified scope and limitations

The execution record for this page is
[V1-S1-009-PR1 change validation](proof/quickstart/v1-s1-009-pr1-validation.md).
It establishes that the documented safe commands worked against this repository
revision. It does not establish a network service, Kubernetes packaging, automated
model acquisition, real-adapter execution, performance, production readiness, or
production experience.
