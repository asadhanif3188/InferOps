# The V1 observability method

Status: **published method over an accepted-in-part catalog.** This document says how
V1 observes inference, topic by topic, and keeps two lists apart in every topic: what
is emitted, collected, panelled, and alerted on, with the test, gate, and record
behind it, and what is specified and not emitted, not kept, or not routed to anybody.
It adds no signal and moves no status. Whether a metric is emitted is
[the telemetry catalog's](telemetry-catalog.v1alpha1.json) statement, and every
certification level is read from
[the claim and evidence register](../testing/claim-evidence-matrix.md).

> [!IMPORTANT]
> The API emits eight metrics and writes structured records; nothing else in V1 emits
> anything. A release-scoped collector keeps what it scrapes for two hours inside its
> own pod. No durable store, no dashboard server, and no alert routing exist, and no
> component produces a span. Every real observation here comes from one Windows host,
> on CPU, on the `docker-desktop` provider, with one replica serving.

The authoritative form is
[`observability-method.v1alpha1.json`](observability-method.v1alpha1.json).
[`tests/testing/test_published_methods.py`](../../tests/testing/test_published_methods.py)
holds the two in agreement, resolves every test, gate, and record the data names, puts
each metric on the side of the line the catalog's emission field allows, and requires
every catalog metric and every alert to appear.

The companion for security, including how prompts and responses are handled, is
[the V1 security method](../security/security-method.md).

## How to read it

Each topic has two tables, read the way
[the security method](../security/security-method.md#how-to-read-it) describes.
**Implemented** rows name what verifies them, the committed record they rest on, and an
evidence label. **Not implemented** rows name what carries the gap — a metric the
catalog says nothing emits, a claim the register does not certify, a security register
entry, or one of the six observability gaps listed in section 8 — and what may not be
claimed while it stands.

Three labels matter most here, because the same signal carries very different weight
under each: `local-static` is a check over committed files, `mock` is the API driven
against the labelled mock adapter and never says anything about a runtime, and
`local-real-cpu` is a real release on one host. A row does not become stronger by
sitting next to one that is.

## 1. Resource and AI attributes

Nine resource attributes are attached once per process and never varied per request.
The AI-specific ones name what produced an answer: the model identifier and its
immutable revision, the serving runtime and its image digest, the adapter kind, the
token direction, and the finish reason. The full table, with the question each answers
and its sensitivity and cardinality class, is in
[the catalog](telemetry-catalog.md#3-resource-attributes).

**Implemented**

| What | Signal and claim | Verified by | Record | Label |
|---|---|---|---|---|
| The build, capability, release, model revision, runtime image digest, and adapter kind reach metrics through one identity series per process, never as an operational label | `inferops_build_info`; claim `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label` | `test_identity_attributes_appear_only_on_an_identity_metric`, `test_an_identity_metric_emits_one_series_per_process`; gate `default-lane-tests` | [v1-s0-007-pr1](../proof/telemetry/v1-s0-007-pr1-validation.md) | `local-static` |
| The adapter kind is derived from the adapter selection rather than configured beside it, and a mock deployment's metrics body says it describes a fixture replay | claim `the-api-emits-catalog-metrics-and-structured-request-records` | `test_the_metrics_body_says_the_deployment_behind_it_is_a_mock`, `test_a_real_selection_with_a_mock_labelled_identity_refuses` | [v1-s1-008-pr1](../proof/telemetry/v1-s1-008-pr1-validation.md) | `mock` |

**Why identity is one series.** Putting a version, a revision, and a digest on every
operational series multiplies each series by the release history. One series per
process whose labels carry identity is the difference between recording immutable
versions and paying for them on every request.

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| The AI attributes are this project's own names. No mapping to the OpenTelemetry generative-AI semantic conventions is recorded, and no attribute is emitted under one | gap `no-generative-ai-convention-mapping` | No conformance with any published semantic convention |

## 2. Logs, correlation, and redaction

A record is one JSON object per line, built through an allowlist of the attribute names
the catalog publishes. There is no free-form message field, because prose that varies
per request is the field a caller's data eventually arrives in. Seven event types are
the whole value set of `inferops.event`. What is excluded, and why each exclusion is
tempting, is in [the redaction rules](redaction.md).

**Implemented**

| What | Claims | Verified by | Record | Label |
|---|---|---|---|---|
| A field outside the allowlist is refused and named without its value; six fields — a prompt, a completion, a provider error body, a secret value, an authorization header, and a value read out of a document — have no name at all | `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label`, `the-api-emits-catalog-metrics-and-structured-request-records` | `test_a_forbidden_field_is_allowed_nowhere`, `test_a_record_has_no_free_form_message_field`, `test_a_record_the_catalog_forbids_still_raises_when_the_sink_is_fine`, `test_no_record_or_series_repeats_the_prompt` | [v1-s1-008-pr1](../proof/telemetry/v1-s1-008-pr1-validation.md) | `mock` |
| A correlation identifier is assigned at the edge before anything can fail, echoed on every response including a refusal, carried by every record, and never a metric label | `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label` | `test_a_log_record_carries_a_correlation_identifier_from_the_start`, `test_no_metric_label_is_a_request_scoped_identifier`, `test_the_response_headers_and_body_carry_the_same_identifiers` | [v1-s1-008-pr1](../proof/telemetry/v1-s1-008-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| No tracer, propagator, or exporter is selected; trace context headers are neither read nor written, and trace and span identifiers are fields nothing populates | gap `no-span-is-produced` | No distributed tracing |
| Every record a suite reads for content comes from the mock. Records the API wrote with the real adapter are quoted in three committed files from two runs and no test reads one; the serving-runtime adapter, closest to a runtime's own error text, emits nothing | DR-12; claim `no-prompt-response-or-secret-reaches-a-log-or-a-metric` stays planned | That no prompt, response, or secret reaches a log or a metric is not certified |

## 3. Metrics and cardinality

Thirteen active metrics cover the signal families V1 must answer for, and three more are
defined and deferred. Every metric names the question it answers and the most series it
can produce. Placement is derived, not chosen: a field's sensitivity class and its
cardinality class each permit a set of places, and the field may go only where both
agree. That is why a tenant identifier is a log field and never a label, and why a
duration is a value and never a key.

**Implemented**

| What | Signals and claim | Verified by | Record | Label |
|---|---|---|---|---|
| The API emits eight of the thirteen active metrics | `inferops_build_info`, `inferops_inference_requests_total`, `inferops_inference_errors_total`, `inferops_inference_request_duration_seconds`, `inferops_inference_requests_in_flight`, `inferops_inference_tokens_total`, `inferops_readiness_check_failures_total`, `inferops_process_cpu_seconds_total`; claim `the-api-emits-catalog-metrics-and-structured-request-records` | `test_the_catalog_says_exactly_what_emits_and_what_does_not`, `test_the_exposition_carries_no_duration_or_workload_version_label` | [v1-s1-008-pr1](../proof/telemetry/v1-s1-008-pr1-validation.md) | `mock` |
| Placement follows both classes, no operational label is unbounded or request-scoped, and the declared series total is recomputed against 2,000 per metric and 10,000 overall | claim `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label` | `test_every_placement_is_allowed_by_both_classes`, `test_no_operational_metric_label_is_unbounded`, `test_the_active_catalog_stays_inside_the_total_budget`, `test_instance_is_the_only_unbounded_label_and_says_what_it_costs` | [v1-s0-007-pr1](../proof/telemetry/v1-s0-007-pr1-validation.md) | `local-static` |

The one unbounded label anywhere is `instance`, which the collector attaches as the pod
name so a per-replica question can be asked. It grows once per restart, and
[the collection document](kubernetes-telemetry-collection.md) says what it costs.

**Not implemented**

| What | Signals | Not claimed |
|---|---|---|
| Four active metrics belong to emitters that are not instrumented, and one is assigned to the API with no source it may read | `inferops_inference_queue_duration_seconds`, `inferops_model_load_duration_seconds`, `inferops_model_ready`, `inferops_workload_document_rejections_total`, `inferops_process_resident_memory_bytes` | No queue wait, model load time, model readiness, document rejection rate, or process memory |
| Defined and deferred: V1 has no streaming path, no retry path, and no component that emits a cost record | `inferops_inference_time_to_first_token_seconds`, `inferops_inference_retries_total`, `inferops_cost_records_total` | No time to first token, retry count, or cost; a cost figure is not something this telemetry produces |
| The budget is arithmetic over declared bounds; no store has been tested against it | gap `no-durable-store` | No measured series count or store capacity |

## 4. Collection

**Implemented**

| What | Claim | Verified by | Record | Label |
|---|---|---|---|---|
| A chart-owned, release-scoped Prometheus discovers and scrapes the API and the serving runtime, drops every label the catalog bars, and attaches none the API already emits | `a-release-scoped-collector-scrapes-both-inferops-jobs-on-the-reference-provider` | `test_every_job_drops_every_label_the_catalog_bars`, `test_the_api_job_attaches_no_label_the_api_already_emits`; gate `helm-chart` | [telemetry during recovery](../proof/telemetry/v1-s3-011-pr2-telemetry-during-recovery.md) | `local-real-cpu` |

Scrape reachability is not readiness. `up` says the collector reached a process;
[the recovery run](../proof/telemetry/v1-s3-011-pr2-telemetry-during-recovery.md)
recorded a deleted serving pod still reading up for fifteen seconds.

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| The runtime exposes no cumulative request counter, and no metrics server, kube-state-metrics, or cAdvisor scrape is installed | gap `no-cluster-resource-source` | No container, node, restart, or pod-phase figure |

## 5. Dashboard semantics

The question an operator asks first during an incident is whether a number is real. A
Prometheus panel with no data looks the same whether the system is idle, the target is
gone, or the metric was never emitted, so every panel of
[the dashboard](inference-operations-dashboard.md) declares which of four states it is
in, and the four look different:

| State | What the panel shows |
|---|---|
| zero | The number 0, only from a count that proves a reading happened, never over a rate |
| missing | The panel's own text saying what an empty result from that expression can mean. Never a number |
| not emitted | A title saying so, and text naming the component that is not instrumented |
| not answerable | A text panel with no query, saying what would have to exist first |

**Why a zero is a count and never a rate.** A rate never sees the events before a
series' first scrape. The validation run observed ten refused requests reading 0 per
second while the since-start count rose by ten, so a zero filled over a rate would sit
beside a real failure. [The operator guide](inference-operations-dashboard-operator-guide.md)
says, for every panel, the conclusion it cannot support.

**Implemented**

| What | Claim | Verified by | Record | Label |
|---|---|---|---|---|
| Every panel declares one of the four states, no zero fill takes a rate, an empty count stays missing, model readiness reads as not emitted rather than ready, and a scrape panel says scrape | `the-inference-operations-dashboard-was-asked-of-a-real-prometheus-and-rendered` | `test_the_four_states_are_declared`, `test_no_zero_filled_expression_takes_a_rate`, `test_a_count_is_missing_rather_than_zero_when_nothing_was_read`, `test_model_readiness_says_not_emitted_rather_than_ready` | [v1-s4-002-pr2](../proof/telemetry/v1-s4-002-pr2-dashboard-validation.md) | `local-real-cpu` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| The definition was imported once into a throwaway Grafana against one single-replica release; which Grafana runs it, who owns it, and where it is exposed are undecided | gap `no-dashboard-server` | No dashboard is running, and a screenshot is not a published figure |

## 6. Alerts

An alert exists here only when there is something to do about it. Each of the six in
[the alert record](inference-alerts.md) carries an owner, a severity, a caller impact,
an accepted evidence query repeated verbatim, an operator action, a runbook section, a
threshold basis, and what it cannot see — because an alert that never states its blind
spot is one whose silence gets read as health. Every threshold is zero, a value the
chart declares, or a bucket boundary of the latency histogram; none is a figure this
project measured.

**Implemented**

| What | Alerts and claims | Verified by | Record | Label |
|---|---|---|---|---|
| Six alerts, driven across eight committed scenarios, five replayed over three real captures, and both rendered rule files loaded by the pinned collector's `promtool` | `inference-callers-refused`, `inference-serving-nothing`, `readiness-refusals-sustained`, `inference-latency-past-half-the-request-budget`, `runtime-defers-requests`, `platform-api-scrape-job-absent`; claims `six-v1-alerts-carry-an-owner-a-severity-an-evidence-query-and-a-runbook-link`, `the-v1-alerts-were-replayed-over-the-telemetry-three-real-experiments-recorded` | `test_every_alert_names_an_owner_a_severity_and_a_runbook_section`, `test_no_threshold_is_a_figure_this_project_measured`, `test_every_alert_does_what_the_record_says_over_every_scenario`, `test_the_pinned_collector_loads_the_rule_file_this_repository_renders` | [v1-s4-008-pr1](../proof/telemetry/v1-s4-008-pr1-alert-validation.md) | `local-static` |

The `promtool` check runs the binary out of the image the chart pins and skips where
that image is not present locally, which includes a continuous-integration runner.

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| No receiver, routing tree, Alertmanager, or on-call rotation exists; no Prometheus in a cluster has loaded these rules, and no alert has told anybody anything | gap `no-alert-routing`; claim `an-alert-reaches-somebody` is not claimed | No alert reaches a person, and a silent alert is not evidence of health |

## 7. Retention assumptions

Three lifetimes, and the distinction matters more than the durations.

**Implemented**

| What | Claims | Verified by | Record | Label |
|---|---|---|---|---|
| The collector's series live in an `emptyDir` bounded to two hours and 512 MB; a restart or an uninstall loses them | `a-release-scoped-collector-scrapes-both-inferops-jobs-on-the-reference-provider` | `test_the_collectors_storage_is_ephemeral_and_bounded` | [telemetry during recovery](../proof/telemetry/v1-s3-011-pr2-telemetry-during-recovery.md) | `local-real-cpu` |
| A lane's raw output expires — 30 days for the default lane's uploaded scan and bill-of-materials artifacts — and nothing may cite it; a record that certifies a claim is committed and kept for as long as the claim stands | `the-published-strategy-and-its-data-cannot-drift-apart` | `test_evidence_retention_is_defined`, `test_a_claim_cites_evidence_exactly_when_it_is_certified` | [v1-s0-006-pr1](../proof/testing/v1-s0-006-pr1-validation.md) | `local-static` |

A committed evidence record is the strictest surface of the three rather than the
loosest: it is public and permanent, which is why a tenant identifier may go into a log
field and never into a record.

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| Records go to the stream the composition point supplies and no further; no log store, shipper, retention window, or access rule is selected | DR-12; gap `no-durable-store` | No retention period, deletion guarantee, or access control for any log or metric |

The catalog requires a retention window to be stated before content of any kind is
written, and it is unstated. That is one of the reasons content capture has no switch.

## 8. Deferred observability risks

**Implemented**

| What | Claim | Verified by | Record | Label |
|---|---|---|---|---|
| Every metric that is not emitted, every deferred alert condition, and every question with no answer says why in the data | `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label` | `test_a_metric_that_is_not_emitted_says_why`, `test_every_deferred_condition_says_what_would_be_needed_and_what_not_to_use`, `test_every_metric_with_no_query_says_why_it_has_none` | [v1-s0-007-pr1](../proof/telemetry/v1-s0-007-pr1-validation.md) | `local-static` |

**Not implemented.** Six gaps, each named in the data and none scheduled. The security
register entry DR-12 carries the first from the security side, because a record nothing
keeps reconstructs nothing, and the claim `an-alert-reaches-somebody` is not claimed.

| Gap | What is missing |
|---|---|
| `no-durable-store` | No log store, metric store, shipper, retention window, or access rule; the `telemetry-backend` ownership row is deferred |
| `no-dashboard-server` | No Grafana server is owned, run, or exposed |
| `no-alert-routing` | No receiver, routing tree, Alertmanager, or on-call rotation |
| `no-span-is-produced` | No tracer, propagator, exporter, or SDK |
| `no-cluster-resource-source` | No metrics server, kube-state-metrics, or cAdvisor scrape, and no permitted source for process memory |
| `no-generative-ai-convention-mapping` | No mapping of the AI attributes to the OpenTelemetry generative-AI conventions; recording one is a catalog decision under ADR 0006 and is not taken here |

No incident-reconstruction, paging, or long-term trend property is claimed while any of
these stands.

## 9. Production-oriented design is not production certification

The signals, panels, and alerts are shaped the way an operated platform would use them:
identity on one series, a budget before a store, four panel states, an owner and a
runbook on every alert. **Shaped for it is not operated with it.** Every real observation
comes from one host, on CPU, on one provider, with one replica serving, and the
`production-experience` label is unreachable from this repository.

**Implemented**

| What | Claim | Verified by | Record | Label |
|---|---|---|---|---|
| No alert threshold is a measured figure, and no metric borrows the credibility of the runtime | `six-v1-alerts-carry-an-owner-a-severity-an-evidence-query-and-a-runbook-link` | `test_no_threshold_is_a_figure_this_project_measured`, `test_no_metric_borrows_the_credibility_of_the_runtime` | [v1-s4-008-pr1](../proof/telemetry/v1-s4-008-pr1-alert-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| Nothing has been operated in anyone's production | claim `an-alert-reaches-somebody` is not claimed | No availability, service-level objective, error budget, or operational history |

Latency, throughput, and capacity signals exist to operate the platform, and V1
publishes no figure derived from any of them. A dashboard screenshot is a publication.

## What publishing this corrected

Two statements in this directory had stopped being true, and both are corrected in
place:

- **The telemetry index said the two rendered rule files were something nothing had
  loaded.** The pinned collector's `promtool` loads both, and a test runs it. What
  stays true is that no Prometheus in a cluster has loaded them and nothing routes them.
- **The redaction rules and the API instrumentation document said no record had been
  produced against a real runtime.** Three committed files, from two runs, quote records
  the API wrote with the real adapter. What stays true is narrower, and it is the part that
  matters: no suite reads one for content.

## Related records

| Topic | Document |
|---|---|
| The decision this method is published under | [ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md) |
| Every attribute, metric, and budget | [Telemetry catalog](telemetry-catalog.md) |
| What is excluded, and what capture would need | [Redaction rules](redaction.md) |
| What the API emits | [API instrumentation](api-instrumentation.md) |
| What the collector scrapes | [Collecting telemetry in Kubernetes](kubernetes-telemetry-collection.md) |
| What can be asked of it | [Correlated telemetry queries](telemetry-correlation-queries.md) |
| The dashboard, and how to read it | [Dashboard](inference-operations-dashboard.md), [operator guide](inference-operations-dashboard-operator-guide.md) |
| The alerts | [The V1 alerts](inference-alerts.md) |
| The security half | [The V1 security method](../security/security-method.md) |
