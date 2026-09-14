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

Claim boundary: the dashboard is defined as data, 29 panels running 30 expressions;
every expression satisfies the correlation query policy; every one of the nine
dashboard rules refuses a record corrupted to break it, including the five
corruptions independent review used to get past the first version; the four states
the dashboard promises to keep apart — zero, missing, not emitted, not answerable —
come apart over the six committed **synthetic** scenarios; and the committed Grafana
JSON is what the record generates.

**What this record does not establish.** It is not evidence that Grafana accepts the
generated JSON, that any panel renders, or that any panel returns from a real
Prometheus what the fixture evaluator returned. Nineteen of the expressions are
accepted correlation queries a real Prometheus has evaluated on one provider; eleven
are new and have never been run by an engine. Two properties of a real Prometheus the
fixture evaluator does not model — a counter series born at 1, and a rate that
outlives an outage — were found by reading, and nothing here executed them. It is
not evidence about any cluster, provider, runtime, or model, and it publishes no
latency, throughput, or capacity figure: every number in the scenario results below
was written by hand into a fixture.

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
| Panels declared per replica | 5 | `perReplica`; the suite derives the count and compares it with the sentence below |
| Expressions | 30 | every `expr` under every panel |
| … repeating an accepted correlation query verbatim | 19 | `queryRef` set; the suite refuses any drift |
| … new in this record | 11 | `queryRef` null |
| Dashboard rules | 9 | `RULE_IDS` |
| Catalog metrics not panelled, with a reason | 4 | `notPanelled`, compared in both directions with what the panels read |

The four not-emitted panels are model readiness, queue wait P95, model load duration
P95, and API process memory. The four not-answerable panels are pod, container and
runtime readiness; restarts and pod phase; container and pod CPU and memory; and the
cluster provider. The pod name appears only in the five panels declared per replica:
the rule reads a query's named labels, its legend, and a result's label set where one
can be derived, and the suite checks what every scenario returned for the rest.

## Commands and results

Every command ran from the repository root in Git Bash, inside the locked environment
(`uv run --locked`), after the review fixes described below.

```text
python -m pytest tests/telemetry/test_inference_dashboard.py -q
68 passed

python -m pytest tests/architecture tests/telemetry -q
3094 passed, 4 skipped

python -m pytest -q
8608 passed, 31 skipped, 14 deselected in 300.32s

ruff format --check .
376 files already formatted

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

The first commit's own full-lane run recorded `8592 passed`; the 16 added since are
the suite's new corruptions, malformed-record cases, and scenario checks. Before that,
a run reported `1 failed, 8589 passed`: the ownership suite checks that an implemented
row's evidence file exists, and it ran before this record was written.

`python -m tools.inference_dashboard --grafana` redirected to a file on this host
writes CRLF line endings, because Python's standard output does on Windows, so a byte
comparison in the shell differs from the committed LF file. The suite compares the
rendering in-process, where the two are identical, and parses the command's output as
JSON.

The 14 deselected tests are the `cluster`, `realruntime`, `failure`, and `load` layers,
which the default marker expression excludes. The 31 skipped were read from
`pytest -rs` rather than assumed, and none is in a suite this change adds: fixtures a
domain or contract parametrisation does not apply to, tests that need to create a
symbolic link this host does not permit, a drain path that needs a POSIX `SIGTERM`
Windows does not deliver, and the collector's `promtool` check, which skips because
the pinned collector image is not present locally. This change does not touch the
chart. An earlier draft of this paragraph said the skips were tool binaries missing
from `PATH`; that was a guess written before the reasons were read, and it was wrong.

## What the scenarios showed

From `python -m tools.inference_dashboard --evaluate`, over all six committed
synthetic scenarios. Every value is a fixture value; counts are since the fixture's
first sample.

| Panel | `healthy-real-two-replicas` | `serving-runtime-not-discovered` | `api-target-up-without-identity` | `every-target-down` | `mock-single-replica` | `forbidden-labels-on-the-exposition` |
|---|---|---|---|---|---|---|
| `requests-since-start` | `1565` | `900` | `900` | **missing** | `450` | `900` |
| `errors-since-start` | `65` | **`0`** | **missing** | **missing** | **`0`** | `40` |
| `readiness-checks-failed-since-start` | `3` | **`0`** | **missing** | **missing** | **`0`** | **`0`** |
| `unsuccessful-request-ratio` | `0.0415335` | `0` | `0` | **missing** | `0` | `0` |
| `api-identity-not-published` | no absence | no absence | `1` | **`1`** | no absence | no absence |
| `scrape-targets-answering-by-tier` | `1`, `1` | `1` | `1`, `1` | **`0`, `0`** | `1` | `1` |
| `model-readiness`, query A | empty | empty | empty | empty | empty | empty |
| `model-readiness`, query B | `1` | `1` | `1` | `1` | `1` | `1` |
| `runtime-operating-identity` | one row, `2` | **missing** | one row, `1` | **missing** | not run | **missing** |

Read the `every-target-down` column against the `mock-single-replica` one. Both show no
errors. In the mock scenario an API process publishes its identity and no error series
exists, so the count reads a zero; with every target down nothing was read, so the
count is empty and shows its missing text — while the scrape panel reads a present
`0`, which is what makes that emptiness legible, and the identity-absence panel reads
`1` although no target answered. In `api-target-up-without-identity` requests are
counted, which proves the API was read, and the error count is still missing: its
zero fill is keyed to a published identity and to nothing else. In
`forbidden-labels-on-the-exposition` the share reads `0` beside 40 errors, because in
that fixture every request's outcome is success and the error counter is a separate
series.

The request duration quantiles in the healthy scenario are `26.6667`, `57.5`, and
`120` seconds at P50, P95, and P99, and the suite asserts only that they are ordered.
They are interpolations over hand-written buckets.

## What checking it found before review

Three things the first draft got wrong, each found by running the checks:

- **A share of successful traffic came back missing rather than zero.** The first
  unsuccessful-request expression divided a sum over non-success outcomes by the
  total. When every request succeeded the numerator selected nothing and the panel was
  empty. It now fills its numerator with zero where requests were counted.
- **The record said every zero rested on a published identity, and one did not.**
  Evaluation showed the share reading `0` in `api-target-up-without-identity`. The
  `zero` state, a limitation, and one panel description were corrected.
- **The published counts were wrong.** The first draft said twelve accepted queries
  and ten new expressions; the record has nineteen and eleven.

## Independent review, and what it changed

The first commit was reviewed before push by three independent reviewers — one for the
checker's code, one for every claim and count against the record and the repository,
one for how a real Prometheus and a real Grafana would treat each panel. Each finding
below was verified before it was acted on.

**What the first commit got wrong about Prometheus.**

- **Its zeros could hide a real first failure.** The API creates a labelled counter
  series on its first event (`src/inferops/telemetry/registry.py`, `_slot`), so the
  series first appears already at 1, and a rate never sees that event. (Later
  observed on a real collector to be a lower bound: a series first appears at
  whatever it counted before its first scrape. See
  [the V1-S4-002-PR2 record](v1-s4-002-pr2-dashboard-validation.md).) The first
  commit's four zero-filled panels were rates: after the recovery run's single
  readiness refusal, "readiness checks failed per second" would have read `0` under a
  zero meaning "counted no failed readiness check". They are now counts since the API
  processes started, `requests-since-start`, `errors-since-start`,
  `readiness-checks-failed-since-start`, and a cumulative share, and a test refuses a
  zero fill over `rate(` or `increase(`. The fixture evaluator agreed with the first
  commit because every fixture counter starts at 0; the defect was found by reading.
- **An idle latency window was described as missing.** Once bucket series exist, a
  window with no request makes every quantile NaN, drawn as gaps. The panel's texts
  now say so.
- **A replica with no request was said to read 0.** The in-flight series is created by
  a replica's first request.
- **A rate outlives an outage.** After every target stops answering a five-minute rate
  keeps the pre-outage figure for up to five minutes. The first commit's scenario
  claim that the request rate was empty with every target down was true only of the
  fixture evaluator. It is now a limitation, and the counts that replaced those rates
  disappear at once.
- **The identity-absence panel claimed a target had answered.** Its recorded absence
  does not read `up`, and the scenario the document used to show "missing" is one
  where it reads `1` with no target answering. It is renamed
  `api-identity-not-published` and titled for what it reads. **Not changed:** the
  accepted query it repeats is still named `identity-absent-on-a-target-that-answered`,
  and the chart's rule comment still says the same. Both belong to earlier accepted
  records and the chart render, and are carried forward rather than edited here.
- **The runtime identity table hid the count it exists to show.** The render hid
  `Value` from every table. It now hides it only from the build identity table, whose
  value is always 1.

**What the first commit's checker let through.** Each was reproduced against the
first commit, and each is now a corruption in the suite.

- A **not-emitted panel carrying a live query** beside its absent one passed. A
  not-emitted panel may now carry only the metric that is not emitted and its
  recorded absence.
- A **zero fill spelled `* -0`** passed, because the detector read only a bare
  literal. Constant operands are now folded; `* (1 - 1)` is refused too.
- A **scrape title saying "operational"** passed. The list is longer, and the suite
  commits a synonym it still accepts, because a list is a list.
- A **bare selector returning `instance`** in a panel not declared per replica passed,
  because the rule read only named labels and legends. It now reads a result's label
  set where one can be derived — which immediately refused `model-readiness`, whose
  query A would carry the pod name if the metric were ever emitted; that panel is now
  declared per replica — and the suite checks every scenario's results for the rest.
- A **wrong-typed record field** raised an `AttributeError` out of the gate. The shape
  is now checked first and refused as a finding.
- A `__name__="up"` matcher was not recognised as a scrape signal. The correlation
  policy already refused it, so this was not a live bypass; the scrape rule now reads
  it anyway.

**What the first commit's documents got wrong.**

- The evidence said the pod name appeared only in panels declared per replica, and
  called it met; nothing enforced it for a bare selector. Enforced now, as above.
- The reason given for the error count being missing without an identity — that
  nothing proved the API was read — was wrong: requests were counted in that very
  scenario. The fill is keyed to identity, and the text now says that.
- The scenario table covered five of six scenarios under a heading that said six.
- The test said to compare published counts with prose read only the record and two
  phrases of the document; it now reads the document, this record, and the changelog.
- Four documents the first commit did not touch still said dashboards were unowned:
  the contributing guide, the repository governance page, and one sentence each in
  the collection and catalog documents. All four now say a dashboard server is.
- "Go stale rather than vanish" was wrong about Prometheus, where a series marked stale
  does vanish from an instant query. The lag is discovery and scrape timing.

**Left as it is, and why.** Module docstrings in `src/inferops/telemetry/`,
`src/inferops/api/metrics.py`, `tools/telemetry_collection/`, and
`tools/telemetry_correlation/`, and two older test docstrings, say no collector,
store, dashboard, or alert exists. They were already stale about the collector before
this change, they describe what those modules observe rather than the platform, and
correcting them is not this pull request's scope. The historical text of the
2026-09-09 amendment in ADR 0004 is annotated rather than rewritten.

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
| P50, P95, P99, and throughput are correct for the selected metrics | **Met against fixtures**, with two limits a fixture cannot show: an idle window is NaN, and a rate misses a series' first event. Queue wait and model load are shown as not emitted |
| Zero, missing, not emitted, and not answerable are distinguishable | **Met against fixtures**, and asserted scenario by scenario. Every zero is a count, so a first event is never read as none |
| Scrape `up` is not presented as model or workload health | **Met**, and enforced by `scrape-signal-presented-as-readiness` against a word list whose limit is committed as a test |
| No sensitive or high-cardinality content is shown | **Met.** Every label is derived from the catalog on every run; the pod name appears only in panels declared per replica, enforced by the rule and by the suite over every scenario; no panel names a job |
| Screenshots, the operator guide, and validation against a running release | **Deferred** to the next pull request of this story |
| Alerts | **Not in scope.** No alert is defined, and alert routing is undecided |

## Limitations

- Every scenario value is synthetic, and eleven expressions have been evaluated by
  nothing but this repository's fixture evaluator, which models neither a counter born
  at 1 nor a rate outliving an outage.
- The Grafana JSON is checked against the fields this repository writes, not against
  Grafana, and it is not profile-aware: a runtime query against a mock release returns
  an empty result.
- A zero is not per replica, and a since-start count starts again when a process
  restarts. Nothing checks what a zero fill is keyed to, only that a panel filling one
  says what its zero means.
- Totals sum every series in the selected store; a store holding two releases would
  add them together.
- The readiness and health word list is a list.
- Scrape reachability and the identity count follow discovery and scrape timing, so
  both lag a deletion.
