# V1-S4-003-PR1 change validation

| Field | Value |
|---|---|
| Date | 2026-09-14 |
| Scope | Versioned LLM load profile, closed-loop load generator, response classification, environment record, raw record set, and deterministic summary |
| Source branch | `feat/v1-s4-003-llm-load-generator` |
| Evidence produced here | `local-static` and `synthetic` only |
| Real load | **No real load run was performed.** Not authorized for this change, and not run |

Change: [the load profile](../../../deploy/serving/load/llm-load-profile.v1.json),
[`tools/llm_load/`](../../../tools/llm_load/),
[its suite](../../../tests/serving/test_llm_load.py),
[the guide](../../serving/llm-load-generation.md), and the
[synthetic rehearsal raw record set](v1-s4-003-pr1-rehearsal-raw.jsonl) with
[its summary](v1-s4-003-pr1-rehearsal-summary.json).

## Claim boundary

Established, on one Windows host, by running commands over this repository:

- the committed profile loads, and it agrees with the runtime profile, the chart's
  values with the real-profile values layered over them, the API's own request
  parser and request deadline, the provider contract, the model record, and the
  runtime pin. Every drift class the suite corrupts is refused at load time;
- every dispatched request receives exactly one sequence number and exactly one
  outcome. This holds under concurrency, at a request ceiling, at a duration stop,
  after a failed warm-up, at an abort, and at an interrupt, with every answer coming
  from an injected function;
- the whole tool runs end to end over real loopback HTTP against an in-process stub.
  The raw record set it writes passes the reader's accounting checks, and the
  committed summary is byte-identical to the one `summarize` regenerates from it.

**Not established.** Nothing about a real release, a real model, a real runtime, a
cluster, or any provider: no cluster was selected or contacted, no port-forward was
opened, no model was loaded, and no inference request reached a runtime. The
real-run commands in the guide are documented and unexecuted. The committed example
is **synthetic**. Its adapter is `synthetic-stub`, its latencies are a stub's 20 ms
sleep plus loopback and thread scheduling, and none of its figures, including the
rates its summary computes, describes serving, capacity, an SLO, or a benchmark. Nothing here certifies
`sustained-throughput-and-capacity-under-load`, which stays a recorded gap, and the
`capacity` lane stays unrun.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python, in the locked environment | `3.12.12` |
| `uv` | `0.9.16` |
| `pytest` | `8.4.2` |
| `PyYAML` | `6.0.3` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |
| Git | `2.45.1.windows.1` |

No Kubernetes, Helm, Docker, or model binary was used.

## Profile defaults

| Setting | Value |
|---|---|
| Fixture | `llm-load-single-turn-v1`, one `user` message, `stream: false` |
| Generation, recorded and cross-checked rather than sent | `maxOutputTokens` 128, `temperature` 0, `contextSizeTokens` 4096, `parallelSlots` 1 |
| Warm-up | 3 requests at concurrency 1 |
| Levels | `c1` = 1, `c2` = 2, `c4` = 4 |
| Level bound | 180 s or 60 requests, whichever first |
| Client request deadline | 150,000 ms, above the API's 120,000 ms |
| Worst case for a whole run | 1,460 s, identity probe included |
| Ceilings in code | 6 levels, concurrency 8, 20 warm-up requests, 500 requests per level, 900 s per level, 300,000 ms deadline, 3,600 s run |

## Output schema

A raw record set is JSON Lines:

- one `run` header: identity, evidence class and ceiling, `productionBenchmark: false`,
  `portableCapacityClaim: false`, the boundary sentence, the profile identity and
  its LF-normalized SHA-256, generation settings, execution bounds, success
  criteria, and the environment. The environment holds the generator host, the
  operator's facts, the identity the target's API reported, and a provenance split
  naming which facts were checked against the repository, which were declared only,
  and which were reported by the API;
- one `phase` record per warm-up and per level, each followed by its `request`
  records;
- one `end` record.

A request record keeps the outcome, status, plain-token error code, error condition
and finish reason,
token counts for a success only, adapter kind, model reference, worker, dispatch
offset, and latency. It never keeps the prompt, the completion, or a header. The
full field list and the reader's refusals are in [the guide](../../serving/llm-load-generation.md#outputs).

## Commands and results

Every command ran from the repository root in Git Bash, inside the locked environment
(`uv run --locked`). The results are from the tree after the review fixes described below. The first
commit recorded 182 tests in this change's suite and 8,865 in the full lane; the 14
added since are the review's new cases.

```text
python -m tools.llm_load check
exit 0; printed the defaults above and "execution not started"

python -m tools.llm_load rehearse
exit 0; synthetic; completed; 39 dispatched: 32 success, 4 http-error, 3 invalid-response

python -m tools.llm_load summarize --raw docs/proof/serving/v1-s4-003-pr1-rehearsal-raw.jsonl
exit 0; the regenerated summary is byte-identical to the committed one (cmp)

python -m pytest tests/serving/test_llm_load.py -q
196 passed

python -m pytest tests/testing -q
1795 passed

python -m pytest -q
8879 passed, 30 skipped, 14 deselected

ruff format --check .
387 files already formatted

ruff check .
All checks passed!

python -m mypy
Success: no issues found in 214 source files

git diff --check
(no output)                                             exit 0
```

The 14 deselected tests are the `cluster`, `realruntime`, `failure`, and `load`
layers, which the default marker expression excludes. The 30 skipped were read from
`pytest -rs`, and none is in `tests/serving/test_llm_load.py`: fixtures a domain or
contract parametrization does not apply to, tests that need a symbolic link this host
does not permit, and a drain path that needs a POSIX `SIGTERM` Windows does not
deliver.

## The committed rehearsal

The stub's answers are a fixed function of each request's sequence number, which it
reads from the request identifier: every ninth request (8, 17, 26, 35) is a canonical
`503 model-not-ready`, and every thirteenth (12, 25, 38) is a completion without usage
counts. Each level reaches its 12-request ceiling long before its 20 s bound, so the
counts below are fixed. Only the timings vary between rehearsals.

| Phase | Dispatched | `success` | `http-error` | `invalid-response` | Stop |
|---|---:|---:|---:|---:|---|
| `warmup` | 3 | 3 | 0 | 0 | `request-ceiling` |
| `c1` | 12 | 10 | 1 | 1 | `request-ceiling` |
| `c2` | 12 | 9 | 2 | 1 | `request-ceiling` |
| `c4` | 12 | 10 | 1 | 1 | `request-ceiling` |

The suite asserts these counts twice: for a fresh rehearsal it runs itself, and for
the committed example. The committed raw header records the generator host's
operating system, release, architecture, logical CPU count, total memory, and Python
version, and nothing that identifies the machine or a person. No facts, so no
provider.

## What checking it found before review

- **The chart's defaults do not carry the model.** The first profile loader read
  only `values.yaml`, where `model.identifier` is empty, and refused the committed
  profile. The real install layers `ci/real-values.yaml` over it. The loader now
  merges the two in that order, and the profile names both.
- **A refused loopback connection can look like a timeout on Windows.** The first
  transport test gave a 2 s deadline to a connection to a closed port. On this host,
  Windows retried the connection for about two seconds, and the deadline fired first.
  With a 15 s deadline the refusal arrived after about two seconds and classified as
  `transport-error`. The guide records the limit. The committed 150 s deadline is
  not affected.
- **The provenance name overstated one check.** A first draft called the provider
  "checked against committed pins". It is checked only against the providers the
  contract publishes; no cluster is asked. The list is now `checkedAgainstRepository`,
  and the guide says what that does not mean.
- **The worst case left out the identity probe.** It first counted the warm-up and
  the levels, and the guide called that 1,440 s the worst case for a whole run.
  The two identity probe requests, 10 s each, come before both. The figure is now
  1,460 s, and the 3,600 s ceiling applies to it.
- **Three published counts in the test inventory were already wrong.** Adding this
  suite meant reading them: the documentation layer said nineteen modules while
  twenty-five existed, the architecture layer said fourteen while sixteen existed,
  and the no-claim section said twenty-four suites while its table held twenty-five
  rows. Each is corrected in place with a note, and the machine-checked count moves
  to twenty-six. The suite's number-word table stopped at twenty-five and is extended.

## Independent review, and what it changed

The first commit was reviewed before push by three independent reviewers: one for
the code, one for every claim and count against the code and data, and one reading
the real InferOps API, its container carrier, and the chart for how a first real run
would go. Each finding below was checked before it was acted on.

**What the first commit got wrong about the real platform.**

- **It said a platform deadline would surface as `upstream-timeout`.** In the API
  container, the HTTP carrier's response timer and the adapter's timer share
  `requestTimeoutMs`, and the carrier's starts first
  ([`tools/api_carrier/http_server.py`](../../../tools/api_carrier/http_server.py)).
  It answers `504` with an empty body. The guide and the code comment claimed the
  opposite. Both are corrected, the summary now counts each HTTP status per level,
  and a test classifies the empty `504`. This is read from code; no real deadline
  was provoked.
- **A dead port-forward would have produced a `completed` run.** Only an identity
  refusal stopped a run. A lost forward fails each request in about a millisecond,
  so every level would have spent its whole ceiling on `transport-error` and ended
  `completed`. Five transport errors in a row now end the run as `transport-lost`,
  exit `3`. Consecutive platform refusals, such as `503` or `504`, still never stop a
  run, and a test holds that.
- **It called three identity fields observed.** The model revision and runtime name
  the API reports are values it was built or configured with, and its runtime version
  is the pinned digest unless something asked the runtime. The provenance list was
  `observedFromApi` and the guide said **Observed**. It is now `reportedByApi`, and
  the guide says what those fields are not.
- **Refusals sharing a code were indistinguishable.** A draining API and an
  unreachable runtime both answer `503 capability-unavailable`. Request records now
  keep the `conditionId` from a canonical error's details as `errorCondition`.

**What the first commit got wrong about itself.**

- **The guide said the profile carried the boundary sentence and the loader refused
  one without it.** The profile had no such member and nothing checked it. The
  profile now carries it, and the loader refuses a profile whose sentence differs.
- **Its latencies had 15.6 ms resolution on this host.** It timed requests with
  `time.monotonic`, which ticks every 15.625 ms on Windows. The first committed
  example held only the values 15, 16, 31, 32, and 47 ms, and ten of its 39 latencies
  were below the stub's 20 ms sleep, which this record then described as "a 20 ms
  sleep plus loopback". The tool now uses `time.perf_counter`, and the regenerated
  example's latencies run from 24 to 49 ms.
- **The worst case was presented as a bound it is not.** The deadline is a socket
  timeout, not a wall-clock limit, so a slowly sending server can hold a request past
  it. The guide now says so.
- **A late mock answer did not stop the run.** An answer past the deadline was
  classified `timeout` before its adapter was read. Identity is now read first.
- **The release install was attributed to the wrong record.** The guide pointed at
  the Sprint 3 paved-road record, whose certification workflow uninstalls the
  release it installs. It now points at the dashboard validation run, which
  installed the release from the three values files and left it running, and it
  gives the command.
- **Smaller statements.** Exit code `3` covers refusals after load as well as before.
  The interrupt message claimed no record was written when one could have been.
  `accounting.balanced` could never be false once the reader had accepted a set, and
  it is removed. `summarize` writes under `.cache/inferops/load/`, not beside the file
  it reads. The success row listed the runtime name, which is checked once, by the
  identity probe. The CHANGELOG said the tool refuses a target "that is not a
  loopback forward" and one whose answers "are not the real release"; it can check
  only for a loopback URL and for the identity the API reports. The CHANGELOG and
  this record paraphrased the project boundaries as forbidding a "throughput or
  latency figure"; they name a benchmark, a throughput figure, and a capacity claim.
  The facts commands gave a string revision and desired rather than ready replicas,
  without saying so.

**Test coverage the review asked for.** A worker failure under concurrency 4 now
has a test showing its siblings stop rather than run to the ceiling. The command
line's exit code is tested for every end state, using the end-state constants
rather than string literals.

**Reported and not changed.**

- Whether the pinned runtime abandons a job when the API closes the connection at
  its deadline is unchecked. If it does not, timeouts at the highest level can
  compound. The guide says so and gives the queueing arithmetic.
- The environment record does not capture the Docker Desktop VM's resources,
  container limits, the `kubectl` client version, or the deployed request deadline
  and output limit. It also does not tie the forward to the release the facts name.
  Collecting them needs the cluster. The guide lists each as a limitation.
- Every request repeats one fixture, so the runtime's prompt cache makes prompt
  processing nearly free after the first. The guide records it.
- The interrupt test counts calls to the wait function rather than mocking time.
  It relies on a three-request warm-up finishing inside one 0.25 s poll.

## Deferred, and why

| Not done here | Why |
|---|---|
| A real load run on `docker-desktop` | Not authorized for this change. Executing scenarios and capturing resource telemetry beside them is later work |
| Collecting environment facts from the cluster | This tool contacts no cluster. The facts are the operator's, and the record labels six of them as declared only |
| Any comparison of levels, saturation point, or bottleneck | Analysis, not load generation |
| Resource sampling of pods during a run | Needs the cluster; it belongs with executing scenarios |
| Connection reuse | Every request opens a new loopback connection. Recorded as a limitation, not changed |

## Risks and assumptions

- The public architecture records still refuse these figures.
  [The project boundaries](../../architecture/project-boundaries.md) say no
  benchmark, throughput figure, or capacity claim may be published from V1. The
  `capacity` lane in [the test strategy](../../testing/test-strategy.v1alpha1.json)
  says V1 may publish no throughput, latency, capacity, or benchmark figure. This
  change does not edit either record. The rates in its committed summary describe a
  synthetic stub and are labelled that way; no figure from a real release is
  published. Before
  real figures from a load run are published, those records need a governed
  amendment naming the bounded, provider-labelled measurements they may carry.
- The documented real-run commands name objects the committed chart renders. They
  have not been executed as written.
- A Service port-forward reaches one selected pod and adds its own cost to every
  latency. A run through one says nothing about how load is spread.
