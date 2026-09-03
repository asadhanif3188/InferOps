# V1-S2-005-PR1 change validation

| Field | Value |
|---|---|
| Date | 2026-09-03 |
| Scope | Registered local serving baseline experiment, capture, and summary generator |
| Source branch | `feat/v1-s2-005-baseline-experiment` |
| Evidence produced here | `local-static` and `synthetic` only |
| Real-runtime execution | Not authorized and not run |

## Implemented boundary

The committed descriptor and command register a repeatable serving experiment
against the existing local-real composition: a fixed two-message fixture, pinned
generation settings, three discarded warm-up requests, thirty measured requests at
concurrency one, a per-request timeout, a duration stop condition, and success
criteria that require an explicitly real answer naming the selected model.

Loading performs no I/O beyond committed files and cross-checks the descriptor
against the composition, the runtime profile, the runtime package, and the model
source record. A drifted fixture, generation setting, request envelope,
concurrency, duration bound, success criterion, or result path is refused at load
time.

One authorized run composes the runtime and API through `tools.local_composition`,
so readiness ordering, drain, and ownership-scoped cleanup remain owned in one
place. This change contributes the warm-up, the measured phase, periodic container
resource sampling, and the record format. Summarizing is a pure function of the
raw record set: no clock, no network, integer nearest-rank percentiles, so the
same raw file always produces the same summary.

`check`, `environment`, and `summarize` never execute the experiment. `run`
refuses without `--confirm-real-runtime` before starting anything.

## Validation results

| Command | Result | Evidence boundary |
|---|---|---|
| `uv run --locked python -m tools.serving_baseline check` | Passed; fixture, generation, execution, success criteria, result layout, and unexecuted status printed | `local-static`; contacted no runtime or Docker |
| `uv run --locked python -m tools.serving_baseline environment` | Passed; sanitized host record emitted with one `docker version` call | `local-static`; read no model byte and started no container |
| `uv run --locked ruff check .` | Passed | Repository-static |
| `uv run --locked ruff format --check .` | Passed; 241 files already formatted | Repository-static |
| `uv run --locked python -m mypy` | Passed; 138 source files checked | Repository-static |
| `uv run --locked python -m pytest tests/serving/test_serving_baseline.py -q` | Passed; 102 tests | Controlled synthetic baseline path |
| `uv run --locked python -m pytest -q` | Passed; 5,357 passed, 25 skipped, 14 deselected | Default lane; real-runtime tests remained deselected |
| `git diff --check` | Passed; no whitespace defect | Repository-static |

The focused suite covers the committed descriptor's agreement with everything it
depends on, refusal of each drift class, nearest-rank percentile arithmetic
including its order-independence and its guarantee of returning an observed value,
warm-up exclusion from every distribution, summary determinism, the raw result set
round trip, malformed-record refusals, resource-column parsing, absent samples
being absent rather than zero, and the execution gate. Every request in the suite
is answered by an injected seam.

## Real execution deliberately absent

No command carrying `--confirm-real-runtime` was run. No image was pulled, no
model was downloaded or read, no container was created, no runtime socket was
opened, and no inference was sent. Consequently this record contains no latency,
throughput, percentile, model-load, token, or resource figure, and this repository
holds no measured baseline. The pre-registered method is
[`v1-s2-005-local-baseline-experiment.md`](v1-s2-005-local-baseline-experiment.md),
whose results section records every threshold as not executed.

## The benchmark boundary

[The project boundaries](../../architecture/project-boundaries.md) forbid
publishing a benchmark, throughput figure, or capacity claim from V1. This change
holds that line in four places rather than one: the descriptor carries
`productionBenchmark: false` and the loader refuses a descriptor that says
otherwise; every raw result header carries the same field and reading one back
refuses a header claiming to be a benchmark; every summary carries the field plus
a sentence naming what it is not; and the published guide leads with the
restriction. Two tests assert each of those refusals directly.

## Public-information review

The reviewed change is confined to the public repository. It contains public
project identifiers and the immutable public model, image, and runtime pins
already present on `main`; it contains no planning path or identifier, credential,
prompt or completion from a user, personal filesystem path, model artifact, host
inventory, private URL, or runtime response body.

The environment record was reviewed specifically for this. It captures operating
system, release, architecture, logical CPU count, memory, free disk, Python
version, container engine version, accelerator, and the committed pins. It
captures no hostname, user name, network identity, or absolute path, and a test
asserts the exact field set. Generated raw and summary files remain under an
ignored, workspace-scoped path, and a test asserts that a raw result set contains
neither the fixture's prompt text nor any completion content.

## Deferred to PR2

Executing the registered experiment on an authorized capable host, analyzing the
measured latency, throughput, and resource results, promoting the raw records and
summary into a committed evidence record, and publishing the baseline report with
its limitations. This PR produces the tooling and the pre-registered method; it
produces no measurement.
