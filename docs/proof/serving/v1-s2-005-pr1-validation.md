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
| `uv run --locked ruff format --check .` | Passed; 250 files already formatted | Repository-static |
| `uv run --locked python -m mypy` | Passed; 142 source files checked | Repository-static |
| `uv run --locked python -m pytest tests/serving/test_serving_baseline.py -q` | Passed; 107 tests | Controlled synthetic baseline path |
| `uv run --locked python -m pytest -q` | Passed; 5,427 passed, 25 skipped, 14 deselected | Default lane; real-runtime tests remained deselected |
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
restriction. Three tests assert those refusals directly: one for the descriptor,
one for a raw header read back, and one for the summary's own fields.

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
ignored, workspace-scoped path. Two tests assert that a raw result set carries
neither the fixture's prompt text nor any completion content, the second by
pushing a completion carrying a unique marker through the request path first.

## Independent second-eye review

An independent review of the first commit raised one HIGH and four MEDIUM
findings, and every one that was valid was fixed in the follow-up commit on this
branch.

| Finding | Resolution |
|---|---|
| `warmupRequests` had no ceiling, and the warm-up loop ignored the duration bound, so the phase ceilings bounded only the half of a run whose numbers get published | Added `MAXIMUM_WARMUP_REQUESTS`, enforced it in the same envelope rule as the measured ceiling, and moved the stop condition into a predicate both loops check |
| `write_raw` and `write_summary` re-checked the result path after `mkdir` but discarded the result, so the call read as dead code | The re-check's return value is now the directory the write uses, with a comment naming the window it narrows and the one it does not close |
| `sample_resources`, `_engine_version`, and `total_memory_bytes` caught bare `Exception`, so a signature or protocol bug would degrade a record silently instead of failing | Narrowed to `OSError`/`RuntimePackagingError` and `AttributeError`/`OSError`/`ValueError` respectively |
| The prompt-and-completion retention test asserted the absence of text no fixture ever supplied, so it was true by construction | Replaced with a test that pushes a completion carrying a unique marker in `choices[].message.content` through the request path and asserts the marker reaches neither the record nor the raw file |
| The full-suite pass count in this record did not reproduce exactly | Re-run and corrected; both counts in the table above are from the reviewed tree |

Two further observations were accepted as accurate and addressed without a
behaviour change: the unreachable `max(1, rank)` clamp in `percentile_ms` was
removed in favour of a comment stating the invariant that makes it unreachable,
and the concurrency rule now says in code and in a comment that sequential
dispatch is what the runner actually performs, so the descriptor cannot advertise
a concurrency no run carries out.

The reviewer independently reproduced the lint, type, and test results, and
independently verified the percentile arithmetic, the throughput unit naming, the
summary's determinism, the round-trip field symmetry, and the evidence-class
labels against `docs/testing/certification.md`.

## Merge with the certification change

`V1-S2-004-PR1` merged to `main` after this branch was cut, and `origin/main` was
merged in here rather than rebased over. The two changes conflicted only in shared
indexes — `.gitignore`, `CHANGELOG.md`, `CONTRIBUTING.md`, `README.md`,
`docs/proof/README.md`, and `docs/testing/test-inventory.md` — and every conflict
was resolved by keeping both sides. No code file conflicted, because this change
builds on `tools.local_composition` and takes no dependency on
`tools.runtime_certification`.

The inventory counts were recomputed against the merged data rather than carried
over from either side: twelve modules defend no published claim and the
documentation layer holds fourteen. Every figure in the table above was re-run on
the merged tree, and both `tools.serving_baseline check` and
`tools.runtime_certification check` pass together.

## Deferred to PR2

Executing the registered experiment on an authorized capable host, analyzing the
measured latency, throughput, and resource results, promoting the raw records and
summary into a committed evidence record, and publishing the baseline report with
its limitations. This PR produces the tooling and the pre-registered method; it
produces no measurement.
