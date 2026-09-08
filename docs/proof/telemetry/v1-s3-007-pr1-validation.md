# V1-S3-007-PR1 validation — Kubernetes telemetry collection configuration

Change: the `inferops-llm` chart renders the `telemetry-scrape-configuration` row of
the ownership inventory. It is a ConfigMap holding a Prometheus scrape configuration
for the platform API and, under the real profile, the serving runtime, plus recording
rules that map the native runtime series the accepted catalog maps and publish the
absence of the signals nothing emits. A record and a document describe what a
collector would find; a checker and a test suite refuse a configuration that would
collect what the catalog bars.

**Evidence class.** Everything asserted here is `local-static`: files rendered,
parsed, compared, formatted, linted, type-checked, and driven through documents that
already exist. **Nothing has been collected.** No collector, store, dashboard, or
alerting path is selected, no Prometheus has loaded this configuration, nothing
scrapes either InferOps endpoint, this chart has never been installed, and no
InferOps API image is published for it to install. The maximum certification a
`local-static` result may carry is `C0`, and that is what this carries.

## What this record does not establish

- That anything collects a metric. The ConfigMap is read by nothing: neither
  Deployment mounts it, and no collector exists to read it from the API server.
- That the scrape configuration works. It has been rendered and parsed as YAML and
  compared against the catalog and the runtime feasibility record. It has not been
  loaded by a Prometheus, and no target has been discovered.
- That the relabelling produces the labels described. The reasoning about
  `honor_labels`, `exported_*` renaming, and target-label collision is Prometheus's
  documented behaviour applied to a configuration that has never run.
- That the network-policy allowance opens anything. The accepted local cluster's
  network plugin was tested and does not enforce a NetworkPolicy at all (`DR-04`,
  `EX-05`), so on this cluster the allowance changes nothing because nothing was
  denied.
- That the series multiplier is real. It is arithmetic over declared bounds
  multiplied by a replica count. No store has held one of these series.
- That the runtime mapping still holds. The native series it maps were observed in
  one scrape, on one host, on 2026-08-24, from one runtime image digest.

## Environment

| Item | Value |
|---|---|
| Repository | `InferOps`, branch `feat/v1-s3-007-kubernetes-telemetry` |
| Host | Windows 11, single node, no cluster contacted |
| Python | 3.12, through `uv run --locked` |
| Helm | v3.19.0 |
| kubeconform | present on `PATH`; manifests validated against Kubernetes 1.34.0 |
| Cluster | none. No `kubectl` command was run against anything |
| Model | none. No weights were read and no runtime was started |

## Files changed

### Added

| File | What it is |
|---|---|
| [`charts/inferops-llm/templates/telemetry-scrape-config.yaml`](../../../charts/inferops-llm/templates/telemetry-scrape-config.yaml) | The ConfigMap. Rendered under both profiles when `telemetry.collection.enabled` |
| [`docs/telemetry/kubernetes-telemetry-collection.v1alpha1.json`](../../telemetry/kubernetes-telemetry-collection.v1alpha1.json) | The authoritative record: jobs, target labels and their declared cost, the drop list, the runtime mapping, the missing-signal rules, the signals with no source, the network path, eight limitations |
| [`docs/telemetry/kubernetes-telemetry-collection.md`](../../telemetry/kubernetes-telemetry-collection.md) | The same in prose, compared against the record in both directions |
| [`tools/telemetry_collection/`](../../../tools/telemetry_collection/) | The checker: `core.py`, `__main__.py`, `__init__.py`. Six rules, derived from the catalog |
| [`tests/telemetry/test_kubernetes_telemetry_collection.py`](../../../tests/telemetry/test_kubernetes_telemetry_collection.py) | The suite. 62 tests |
| this record | |

### Changed

| File | Change |
|---|---|
| [`charts/inferops-llm/values.yaml`](../../../charts/inferops-llm/values.yaml) | `telemetry.collection`: `enabled`, scrape interval and timeout, the runtime metrics path, and the collector the network policy would admit |
| [`charts/inferops-llm/values.schema.json`](../../../charts/inferops-llm/values.schema.json) | The schema for it, and a `collectorPodSelector` definition that permits empty because empty means "no collector named" rather than "every pod" |
| [`charts/inferops-llm/templates/_helpers.tpl`](../../../charts/inferops-llm/templates/_helpers.tpl) | The ConfigMap name, the derived runtime identifier, the derived drop list, the scrape configuration, the recording rules, and the collector ingress rule |
| [`charts/inferops-llm/templates/_validate.tpl`](../../../charts/inferops-llm/templates/_validate.tpl) | Five refusals: collection without telemetry, a timeout that is not shorter than its interval, a collector namespace without a selector, a selector without a namespace, a collector without collection, and a collector without a network policy |
| [`charts/inferops-llm/templates/networkpolicy.yaml`](../../../charts/inferops-llm/templates/networkpolicy.yaml) | The optional collector ingress rule on the API and runtime policies, and the prose that accounts for it |
| [`charts/inferops-llm/Chart.yaml`](../../../charts/inferops-llm/Chart.yaml) | `telemetry-scrape-configuration` moves from the deferred list to the owned list; version 0.2.0 → 0.3.0 |
| [`charts/inferops-llm/README.md`](../../../charts/inferops-llm/README.md) | The rendered-resource table, and what the two telemetry switches each do |
| [`charts/inferops-llm/ci/rendered/*.expected.yaml`](../../../charts/inferops-llm/ci/rendered/) | Regenerated |
| [`docs/architecture/resource-ownership.md`](../../architecture/resource-ownership.md) and [`.v1alpha1.json`](../../architecture/resource-ownership.v1alpha1.json) | The row's kind becomes `v1/ConfigMap` and its handoff says what is rendered. It stays `planned`, with `evidenceRef: null`, for the same reason `workload-network-policy` does: nothing has installed it |
| [`docs/telemetry/README.md`](../../telemetry/README.md) | The two new documents, and a paragraph saying the scrape configuration changes none of "what is not here" |
| [`docs/telemetry/telemetry-catalog.md`](../../telemetry/telemetry-catalog.md) | The `no collector` limitation points at the collection document and repeats that a configuration is not a collector |
| [`docs/testing/test-inventory.v1alpha1.json`](../../testing/test-inventory.v1alpha1.json) | The new module, defending the catalog's own claim one layer further out |
| [`tests/architecture/test_helm_chart.py`](../../../tests/architecture/test_helm_chart.py) | Object counts 11 → 12 and 7 → 8, a `ROW_FOR_RENDERED` entry, and five tests replacing `test_no_scrape_resource_is_rendered` |
| [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) | What the third telemetry suite checks, and the checker's command |
| [`CHANGELOG.md`](../../../CHANGELOG.md) | Two entries under Added |

## Validation performed

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked ruff format --check .` | 307 files already formatted |
| `uv run --locked python -m mypy` | Success: no issues found in 165 source files |
| `uv run --locked python -m pytest -q` | 6,596 passed, 28 skipped, 14 deselected |
| `python -m pytest tests/telemetry -q` | 653 passed, of which 62 are this change's |
| `python -m pytest tests/architecture/test_helm_chart.py -q` | 164 passed |
| `python -m pytest tests/testing -q` | 1,107 passed |
| `helm lint --strict charts/inferops-llm --values charts/inferops-llm/ci/mock-values.yaml` | 1 chart linted, 0 failed |
| `helm lint --strict charts/inferops-llm --values charts/inferops-llm/ci/real-values.yaml` | 1 chart linted, 0 failed |
| `helm template … mock-values.yaml \| kubeconform -strict -summary -kubernetes-version 1.34.0 -` | 9 resources, 9 valid |
| `helm template … real-values.yaml \| kubeconform -strict -summary -kubernetes-version 1.34.0 -` | 13 resources, 13 valid |
| `python -m tools.workload_policy charts/inferops-llm/ci/rendered` | ok, 2 files satisfy the workload policy |
| `python -m tools.telemetry_collection charts/inferops-llm/ci/rendered` | ok, 2 files satisfy the collection policy |
| `git diff --check` | no whitespace error |

The default lane deselects `cluster`, `realruntime`, `failure`, and `load`. **No
cluster test was run and none could have been**: no cluster was created, and the
14 deselected tests are the ones that would need one.

### Negative validation

Every refusal was provoked rather than assumed. The template refusals were driven
with `helm template --set`, and each produced its own message and a non-zero exit:

| Override | Refused |
|---|---|
| `telemetry.collection.scrapeTimeoutSeconds=30` | timeout is not shorter than the 30-second interval |
| `telemetry.enabled=false telemetry.scrapeAnnotations=false` | collection requires telemetry |
| `telemetry.collection.collector.namespace=observability` | a namespace with no pod selector admits every pod in it |
| `…collector.podSelector.app=prom` with `security.networkPolicy.enabled=false` | there is no policy to add the allowance to |
| `…collector.*` with `telemetry.collection.enabled=false` | a path opened for a scrape that has not been described |

The checker's six rules were each driven against a deliberately tampered copy of the
real render, one mutation per rule, and each produced its own finding and exit
status 1. Those six mutations are committed as a parametrized test rather than left
as a manual step, because a rule nobody has watched refuse anything is a rule nobody
has tested.

### The suite caught three defects in this change

- The record declared `inferops.runtime.id` with a bound of five distinct values.
  The catalog declares three. A collector may not widen an attribute's cardinality
  by relabelling, and the test that compares a borrowed label against the catalog's
  own bound refused it.
- A target label named `job` was declared in the record and published in neither
  document. The both-directions comparison refused it, and the document now says
  that Prometheus sets `job` and `instance` itself.
- A recording-rule comment naming the serving-runtime adapter put the string
  `serving-runtime` into the **mock** render. `test_the_mock_render_carries_no_real_pin_and_no_runtime`
  refused it — correctly: a mock render that mentions the runtime is exactly what
  that test exists to catch, and the comment was reworded rather than the test
  exempted.

## What the suite establishes, and what it cannot

**It establishes** that the rendered configuration attaches no label the catalog bars
from a metric; that every job drops every one of them, from a list recomputed out of
the catalog rather than copied into the chart; that no recorded name could collide
with a metric the catalog declares; that every mapped `llamacpp:` series appears in
the record that measured it, and that the mapped and the unmapped together are
exactly that record's set; that every scrape job has an `absent()` rule; that the
declared series arithmetic recomputes; that the chart's derived runtime identifier is
the adapter's own constant; that the ConfigMap is rendered once per profile and
mounted by nothing; and that the record, the document, and both renders publish the
same jobs, labels, and rules.

**It cannot establish** anything about a collection. It reads files. The distance
between a correct scrape configuration and a metric in a store is a collector, a
cluster, and an installed release, and this change adds none of the three.

## Deferred, and depended on

`V1-S3-007-PR2` verifies correlated platform telemetry: queries, correlation checks,
missing-signal tests, and evidence. Nothing in this PR anticipates it — no query is
written, no correlation is exercised, and the recording rules here are configuration
rather than verification.

Four catalog metrics stay unemitted because their emitter is uninstrumented, and
instrumenting the serving-runtime adapter is not in this PR's boundary. Container,
pod, and node resource use, pod phase, restart counts, and declared requests and
limits as series all need a cluster add-on this chart does not own. Each is recorded
in `unavailableSignals` with what would provide it, rather than left to a reader.

## Acceptance criteria

### This PR

| Criterion | Status |
|---|---|
| API and runtime metrics are collected | **Configured, not collected.** Two jobs are rendered — the API under both profiles, the runtime under `real` — with discovery, port selection, pacing, and relabelling. Nothing scrapes them, and the record says so in a boolean |
| Workload, version, environment, model, runtime, and pod/replica context are available | **Available, by design rather than by duplication.** The API publishes workload, model, environment, version, capability, release, model revision, image digest, and adapter kind itself; the collector adds Kubernetes namespace, tier, and pod, and adds the operating dimensions to the runtime's bare series where nothing else can. Replica context is `count by (job) (up)`. Deliberately not restated on the API job, because a duplicate target label renames the emitter's |
| Missing scrape/readiness is detectable | **Scrape: yes.** `up`, plus `absent()` per job for the case `up` cannot see, plus an identity-absence rule for a target that is up and published nothing. **Model readiness: no, and the absence is published** — `inferops_model_ready` is the adapter's and is not emitted, so the rule reads 1 rather than an empty series |
| High-cardinality/sensitive fields are excluded | **Yes, by derivation.** Nineteen label names are dropped on every job, derived from the catalog's placement rules and recomputed by a test. No prompt, response, error body, secret, or authorization header has a label name to drop, because none has an attribute. `instance` is the one unbounded label, is required by Prometheus's data model, and is declared with its cost and its rejected alternative |

### The parent story, V1-S3-007

| Criterion | Status |
|---|---|
| API and runtime metrics are collected | Configuration complete. Collection deferred to a collector nobody owns |
| Workload, version, environment, model, runtime, and pod/replica context are available | Complete in configuration |
| Missing scrape/readiness is detectable | Scrape complete; model readiness recorded as absent |
| High-cardinality/sensitive fields are excluded | Complete, and enforced by a checker as well as a document |
| Query samples (evidence) | **Deferred to PR2** |
| Correlation verification (evidence) | **Deferred to PR2** |
