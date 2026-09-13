# V1-S4-002-PR1 change validation

Date: 2026-09-13

Change: [the inference operations dashboard record](../../telemetry/inference-operations-dashboard.v1alpha1.json)
and [its document](../../telemetry/inference-operations-dashboard.md), the Grafana
dashboard JSON generated from it at
[`deploy/grafana/inferops-inference-operations.json`](../../../deploy/grafana/inferops-inference-operations.json),
the dashboard policy in [`tools/inference_dashboard/`](../../../tools/inference_dashboard/),
[its suite](../../../tests/telemetry/test_inference_dashboard.py),
[the amendment to ADR 0004 D7](../../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
that makes the dashboard definition a repository artifact, and the
`inference-operations-dashboard` row it adds to
[the ownership inventory](../../architecture/resource-ownership.md).

Classification: **local static evidence for the change itself.** Evidence class
`local-static`. Every result below was produced on one Windows host by running
commands over files in this repository. No Grafana was started or imported into, no
Prometheus was started or queried, no cluster was selected or contacted, no model
was loaded, and no runtime was started.

Claim boundary: the dashboard is defined as data; every one of its 30 expressions
satisfies the correlation query policy; every one of the nine dashboard rules
refuses a record corrupted to break it; the four states the dashboard promises to
keep apart — zero, missing, not emitted, not answerable — come apart over the six
committed **synthetic** scenarios; and the committed Grafana JSON is what the record
generates.

**What this record does not establish.** It is not evidence that Grafana accepts the
generated JSON, that any panel renders, or that any panel returns from a real
Prometheus what the fixture evaluator returned. Eleven of the 30 expressions are new
and have never been run by an engine. It is not evidence about any cluster, provider,
runtime, or model, and it publishes no latency, throughput, or capacity figure: every
number in the scenario results below was written by hand into a fixture.

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

No Grafana, Prometheus, Helm, or Kubernetes binary was used.

## What was built

| | Count | How it was counted |
|---|---:|---|
| Operational questions | 9 | `questions` in the record, asserted as an exact ordered list |
| Panels | 29 | `panels` in the record |
| Panels by signal | 18 value, 3 scrape reachability, 4 not emitted, 4 not answerable | the `signal` field |
| Expressions | 30 | every `expr` under every panel |
| … repeating an accepted correlation query verbatim | 19 | `queryRef` set; the suite refuses any drift |
| … new in this record | 11 | `queryRef` null |
| Dashboard rules | 9 | `RULE_IDS` |
| Catalog metrics not panelled, with a reason | 4 | `notPanelled`, compared in both directions with what the panels read |

The four not-emitted panels are model readiness, queue wait P95, model load duration
P95, and API process memory. The four not-answerable panels are pod, container and
runtime readiness; restarts and pod phase; container and pod CPU and memory; and the
cluster provider.

## Commands and results

Every command ran from the repository root in Git Bash, inside the locked environment
(`uv run --locked`).

```text
python -m pytest tests/telemetry/test_inference_dashboard.py -q
53 passed

python -m pytest tests/architecture tests/telemetry -q
3079 passed, 4 skipped

python -m pytest -q
8592 passed, 31 skipped, 14 deselected in 177.78s

ruff format --check .
375 files already formatted

ruff check .
All checks passed!

python -m mypy
Success: no issues found in 207 source files

python -m tools.inference_dashboard
ok      29 panel(s) satisfy the dashboard policy        exit 0

python -m tools.telemetry_correlation
ok      23 quer(ies) satisfy the correlation query policy   exit 0

python -m tools.telemetry_collection charts/inferops-llm/ci/rendered
ok      2 file(s) satisfy the collection policy         exit 0

git diff --check
(no output)                                             exit 0
```

The first full-lane run reported `1 failed, 8589 passed`: the ownership suite checks
that an implemented row's evidence file exists, and it ran before this record was
written. The run above is the one after it was, and it is the one recorded.

`python -m tools.inference_dashboard --grafana` redirected to a file on this host
writes CRLF line endings, because Python's standard output does on Windows, so a
byte comparison in the shell differs from the committed LF file. The suite compares
the rendering in-process, where the two are identical, and parses the command's
output as JSON.

The 14 deselected tests are the `cluster`, `realruntime`, `failure`, and `load` layers,
which the default marker expression excludes. The 31 skipped were read from
`pytest -rs` rather than assumed, and none is in a suite this change adds: fixtures a
domain or contract parametrisation does not apply to, tests that need to create a
symbolic link this host does not permit, a drain path that needs a POSIX `SIGTERM`
Windows does not deliver, and the collector's `promtool` check, which skips because
the pinned collector image is not present locally. This change does not touch the
chart, so that last check has nothing new to say about it.

An earlier draft of this paragraph said the skips were tool binaries missing from
`PATH`. That was a guess written before the reasons were read, and it was wrong.

## What the scenarios showed

From `python -m tools.inference_dashboard --evaluate`, over the six committed
synthetic scenarios. Every value is a fixture value.

| Panel | `healthy-real-two-replicas` | `serving-runtime-not-discovered` | `api-target-up-without-identity` | `every-target-down` | `mock-single-replica` |
|---|---|---|---|---|---|
| `request-rate` | `3.15` | `2` | `2` | **missing** | `1` |
| `error-rate` | `0.15` | **`0`** | **missing** | **missing** | **`0`** |
| `readiness-refusals-per-second` | `0.01` | **`0`** | **missing** | **missing** | **`0`** |
| `unsuccessful-request-ratio` | `0.047619` | `0` | `0` | **missing** | `0` |
| `scrape-targets-answering-by-tier` | `1`, `1` | `1` | `1`, `1` | **`0`, `0`** | `1` |
| `model-readiness`, query A | empty | empty | empty | empty | empty |
| `model-readiness`, query B | `1` | `1` | `1` | `1` | `1` |
| `runtime-operating-identity` | one row, `2` | **missing** | one row, `1` | **missing** | not rendered |

Read the `every-target-down` column against the `mock-single-replica` one. Both show no
errors. In the mock scenario an API process published its identity and no error
series exists, so the panel reads a zero; with every target down nothing was read,
so the panel is empty and shows its missing text — while the scrape panel beside it
reads a present `0`, which is what makes that emptiness legible. In
`api-target-up-without-identity` requests are counted and the error rate is still
missing, because nothing proves the API's registry was read.

The request duration quantiles in the healthy scenario are `26.6667`, `57.5`, and
`120` seconds at P50, P95, and P99, and the suite asserts only that they are
ordered. They are interpolations over hand-written buckets.

## What checking it found before review

Three things the first draft of this change got wrong, each found by running the
checks rather than by reading:

- **A share of successful traffic came back missing rather than zero.** The first
  unsuccessful-request expression divided a sum over non-success outcomes by the
  total. When every request succeeded, the numerator selected no series and the
  panel was empty — the exact failure the dashboard exists to prevent. The
  expression now fills its numerator with zero where requests were finished, and
  the suite asserts `0` in the mock scenario.
- **The record said every zero rested on a published identity, and one did not.**
  Evaluation showed `unsuccessful-request-ratio` reading `0` in
  `api-target-up-without-identity`, where no identity exists. The `zero` state, a
  limitation, and one panel description all claimed otherwise. Each now says that a
  per-second count rests on identity and a share rests on traffic.
- **The published counts were wrong.** The first draft of the record said twelve
  accepted queries and ten new expressions; the record has nineteen and eleven. A
  test now derives both from the panels and compares them with the prose.

## What was not run, and why

| Not run | Why |
|---|---|
| Importing the JSON into Grafana | No Grafana server is selected, owned, or installed, and choosing one is the part of `telemetry-backend` this change leaves undecided |
| Evaluating any panel with Prometheus | That needs a release with its collector on a cluster. Screenshots and controlled traffic and failure states belong to the next pull request of this story |
| Grafana's own dashboard schema validation | No validator for it is a dependency of this repository |
| Any real-runtime, cluster, failure, or load lane | Out of scope, and deselected by default |

## Acceptance criteria

| Criterion | Status in this pull request |
|---|---|
| Dashboard answers the V1 operational questions | **Met as a definition.** Nine questions, each with at least one panel, enforced by a rule. Whether an operator can answer them in thirty seconds is for the next pull request, with a running release |
| Model, runtime, workload, and environment are visible | **Met as a definition** for the API tier's full identity and the runtime tier's operating identity. **Provider is not answerable** from telemetry and is shown so |
| P50, P95, P99, and throughput are correct for the selected metrics | **Met against fixtures.** Quantiles over the emitted request-duration histogram, summed across replicas before the quantile; request and token throughput from emitted counters. Queue wait and model load are shown as not emitted |
| Zero, missing, not emitted, and not answerable are distinguishable | **Met against fixtures**, and asserted scenario by scenario |
| Scrape `up` is not presented as model or workload health | **Met**, and enforced by `scrape-signal-presented-as-readiness` |
| No sensitive or high-cardinality content is shown | **Met.** Every label is derived from the catalog on every run; the pod name appears only in the four panels declared per replica; no panel names a job |
| Screenshots, the operator guide, and validation against a running release | **Deferred** to the next pull request of this story |
| Alerts | **Not in scope.** No alert is defined, and alert routing is undecided |

## Limitations

- Every scenario value is synthetic, and eleven expressions have been evaluated by
  nothing but this repository's fixture evaluator.
- The Grafana JSON is checked against the fields this repository writes, not against
  Grafana.
- A zero is not per replica. With two replicas and one not publishing, a count's zero
  is the publishing replica's alone.
- Totals sum every series in the selected store; a store holding two releases would
  add them together.
- Scrape reachability and the identity count read series that go stale rather than
  vanish, so both lag a deletion.
