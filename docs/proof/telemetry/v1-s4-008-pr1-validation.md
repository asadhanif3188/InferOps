# V1-S4-008-PR1 change validation

Date: 2026-09-17

Change: [the V1 alert record](../../telemetry/inference-alerts.v1alpha1.json) and
[its document](../../telemetry/inference-alerts.md), the two Prometheus alerting-rule
files generated from it at
[`deploy/prometheus/`](../../../deploy/prometheus/inferops-inference-alerts.real.yaml),
the alert policy in [`tools/inference_alerts/`](../../../tools/inference_alerts/),
[its suite](../../../tests/telemetry/test_inference_alerts.py) and
[the eight scenario fixtures](../../../tests/telemetry/fixtures/alerts/) it drives,
[the ownership and loadability suite](../../../tests/architecture/test_inference_alert_rules.py),
[the amendment to ADR 0004 D7](../../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
that makes the alert definition a repository artifact, the
`inference-alert-definitions` row it adds to
[the ownership inventory](../../architecture/resource-ownership.md), and
[the alert-validation report](v1-s4-008-pr1-alert-validation.md).

Classification: **local static evidence for the change itself.** Evidence class
`local-static`. Every result below was produced on one Windows host by running
commands over files in this repository. No Prometheus was started, loaded with a rule
file, or queried; no Alertmanager or receiver exists; no cluster was selected or
contacted; no model was loaded; no runtime was started; and no alert was ever routed
to anybody.

Claim boundary: six alerts are defined as data, each with an owner, a severity, a
condition, a window, a declared threshold source, a caller impact, an operator action
and a runbook section that exists and names something to run; every expression
satisfies the correlation query policy under **each profile it declares**; each of the
twelve alert rules refuses a record corrupted to break it; each of the eight refused
alerts is refused when spliced into the record; every alert fires and stays silent
across the eight committed **synthetic** scenarios exactly as the record declares;
three of the six were **replayed over the telemetry two real failure experiments
recorded**, where one fires over one capture and nothing fires over the other; and
both committed rule files are what the record generates.

**What this record does not establish.** It is not evidence that a Prometheus accepts
the rendered rule files — that control exists and **did not run here**; see *What was
not run* below. No alerting rule existed during either failure experiment, so the
replay is this repository's own evaluator over a reconstruction it declares, not a
rule a collector ran. It is not evidence that any alert has fired in a cluster, that
anybody would be told if one did, or that any threshold is right for an installation
other than this chart's defaults. It publishes no latency, throughput, or capacity
figure of its own: every number in the scenario results was written by hand into a
fixture, and the measured figures it quotes — a client-measured 95th percentile of
8 614 ms, and deferrals of 0, 1 and 3 — are quoted to say what the thresholds are
*not* and what the windows are for.

## Environment

| Component | Version |
|---|---|
| Windows | 11 Enterprise 10.0.26200 |
| Python | 3.12.6 |
| `uv` | the repository's locked toolchain (`uv sync --locked`) |
| `pytest` | 8.4.2 |
| Docker engine | **not running on this host** |

## What was built

| File | What it is |
|---|---|
| `docs/telemetry/inference-alerts.v1alpha1.json` | The record: 6 alerts, 5 deferred conditions, 8 refused alerts, 8 scenarios, 2 owners, 2 severities, 3 threshold bases, 5 gaps, 6 limitations |
| `docs/telemetry/inference-alerts.md` | The document that publishes it |
| `deploy/prometheus/inferops-inference-alerts.real.yaml` | The rule file for the real profile: 6 rules |
| `deploy/prometheus/inferops-inference-alerts.mock.yaml` | The rule file for the mock profile: 5 rules |
| `tools/inference_alerts/replay.py` | The replay over the two committed experiment captures, and the reconstruction it declares |
| `tools/inference_alerts/` | The policy, the fixture-window evaluator, the renderer, and the command |
| `tests/telemetry/fixtures/alerts/*.yaml` | Eight scenarios on a 60-second grid |
| `tests/telemetry/test_inference_alerts.py` | The suite |
| `tests/architecture/test_inference_alert_rules.py` | The ownership row, and the `promtool` control |

The policy reuses `tools.telemetry_correlation` rather than deriving the catalog a
second time: the same parser, the same vocabulary, the same refusals. An alert reading
a metric nothing emits is refused there before any rule here sees it.

## Commands and results

```text
uv run --locked ruff format --check .
439 files already formatted

uv run --locked ruff check .
All checks passed!

uv run --locked python -m mypy
Success: no issues found in 247 source files

uv run --locked python -m tools.inference_alerts
ok      6 alert(s) satisfy the alert policy

uv run --locked python -m tools.inference_alerts --evaluate
(48 cells, no DISAGREES; the matrix is published in the alert-validation report)

uv run --locked python -m tools.inference_alerts --replay
(six verdicts per capture; the matrix is published in the alert-validation report)

uv run --locked python -m pytest tests/telemetry/test_inference_alerts.py -q
91 passed

uv run --locked python -m pytest -q
9709 passed, 33 skipped, 14 deselected
```

`git diff --check` reports nothing.

One full-lane run before this one reported a single failure in
`tests/serving/test_performance_scenarios.py`, a `ConnectionAbortedError` from a
loopback stub this change does not touch. It passes in isolation, passes with its own
module, and passes on `main` with this branch stashed; the run above is a clean repeat.
It is recorded here rather than left out, because a flake nobody wrote down is a flake
somebody rediscovers.

## What the scenarios showed

The full matrix is in [the alert-validation report](v1-s4-008-pr1-alert-validation.md).
Four results are worth repeating here because each changed the design:

1. **A single scrape interval of trouble must not page.** The condition is true at
   five fixture instants after one minute of refusals, and every rate alert's `for` is
   the range window, so six consecutive are needed and nothing fires. An earlier draft
   used a two-minute window and fired. The rule
   `alert-window-is-shorter-than-its-range-window` exists because of that draft, and
   the suite re-runs the alert with the short window to prove the fixture still bites.
2. **A release that has never served cannot fire `InferOpsInferenceServingNothing`.**
   The success counter series does not exist until the first success, so a rate over
   it is empty rather than zero. The V1-S4-007-PR1 telemetry records exactly that. The
   gap is written into the alert's own `whatItCannotSee` and covered by the other two
   availability alerts, both of which fire in that scenario.
3. **When the platform-api job discovers nothing, all five workload alerts go
   silent.** That is the entire argument for the sixth, and the suite holds it as a
   property rather than a sentence.
4. **Over the real captures, one of the two runs raises nothing.** The pod-loss
   run's outage was 31 960 ms against five- and ten-minute windows, and its
   `capability-unavailable` counter series was born at 40 and never incremented, so a
   rate over it reads no increase. Both are recorded as gaps rather than left implied.
   Over the unready-model capture the readiness alert fires and the caller-refusal
   alert misses by one evaluation because the recording stopped first.
5. **The chart key was wrong in the first draft.** The latency rationale named
   `serving.requestTimeoutMs`; the chart declares `api.requestTimeoutMs`. The test
   that reads the threshold back out of `values.yaml` caught it. A rationale that
   names a configuration key and a number that drifted from it is worse than a number
   with no rationale at all.

## What checking it found before review

- The first readiness threshold was `> 0`, which fired on the healthy fixture: one
  refusal every five minutes is what a rollout produces. It became `> 0.05`, derived
  from `api.probes.readiness.periodSeconds`.
- The first saturation alert was `> 0` on the deferral gauge with a two-minute window,
  which fires on any momentary queueing. The threshold stayed at zero — the chart
  declares `runtime.parallelSlots: 1`, so any deferral is demand past the
  configuration — and the window became ten minutes.
- The first draft rendered one rule file. The deferral alert reads a recorded series
  the chart renders only under the real profile, so a mock release would have received
  an expression that can only ever be empty: an alert that never fires. The render is
  now one file per profile, and a test asserts the mock file omits that alert.
- The checker returned no findings for a record whose `alerts` was a string or absent,
  which reads as "valid". `alert-record-is-malformed` was added, and the six malformed
  records in the suite are what hold it.

## What was not run, and why

- **`promtool check rules` did not run.** The control exists in
  `tests/architecture/test_inference_alert_rules.py` and would run the pinned
  collector's own binary over both rendered files. The Docker engine is not running on
  this host and the pinned image is not present, so both parametrisations **skipped,
  loudly**, with the pull command in the skip reason. Nothing in this record therefore
  establishes that a Prometheus accepts these files; it establishes that this
  repository's own subset parser accepts every expression and that the YAML is a rule
  group with the fields the format requires.
- No collector, cluster, release, model, or runtime was started. No experiment was
  executed; the two failure shapes the fixtures take were measured by V1-S4-006-PR1
  and V1-S4-007-PR1 and are read from their committed records.
- Nothing was committed, pushed, tagged, or published by any command in this record.

## Acceptance criteria

Applied to this PR's boundary only.

| Criterion | Status |
|---|---|
| Each alert has owner, severity, condition, evidence query, and runbook link | **Met.** Every alert carries all five, plus the window, the threshold's declared source, the caller impact, the operator action, what an empty result means, and what the alert cannot see. The runbook link's file *and* heading are checked, and the section has to name something to run |
| Alerts are validated against failure experiments | **Met, with its class stated.** Three of the six alerts were replayed over the telemetry V1-S4-006-PR1 and V1-S4-007-PR1 actually recorded: `InferOpsReadinessRefusalsSustained` fires over the unready-model capture, nothing fires over the pod-loss capture, and the three alerts whose series neither experiment asked for are reported `not-in-the-capture` rather than silent. No alerting rule existed during either run, so this is a replay and not a rule a collector evaluated. The two fixtures shaped from those runs are synthetic and carry none of their durations |
| No alert exists solely because a metric is available | **Met.** Eight such alerts are recorded as refused with the rule that refuses each, and the suite splices each into the record and fails if it is accepted. Five conditions are deferred rather than approximated, and each carries a `doNotApproximate` field naming the nearby signal somebody would reach for |
| Local proof thresholds are not presented as universal production thresholds | **Met.** No threshold is a measured figure; a `thresholdBasis` of `measurement` is refused by the policy. The one measured figure quoted anywhere is quoted to say what the threshold is not |
| No alert claims to detect a condition the accepted telemetry cannot observe | **Met.** The correlation policy refuses an expression reading a metric nothing emits, and the suite re-asserts it directly so removing that refusal there does not remove it here |
| Scrape health is not equated with model/workload health | **Met.** One alert may read a scrape signal; it declares `scrape-reachability`, is owned by the collection owner, and the policy refuses it if its name, condition, or impact describes the workload. The word list is a list, and the suite pins one synonym it still accepts |

Two parent-story criteria are **not** met by this PR and are not this PR's:

- *Alerts validated against failure experiments executed with the alert rules loaded.*
  That needs a collector evaluating these rules during an experiment, which needs an
  evaluator and a decision about who owns it. Recorded as the `nothing-evaluates-these`
  gap.
- *An operator is told.* No receiver, routing tree, Alertmanager, or on-call rotation
  is selected. Recorded as the `nothing-routes-these` gap and left with
  `telemetry-backend`.

## Limitations

- The fixtures step at 60 seconds and a release would evaluate every 30. A `for`
  satisfied here is satisfied at the instants the fixture carries.
- The evaluator is not Prometheus; the differences are declared in the correlation
  query document and apply unchanged, because it is the same evaluator.
- Six of eight scenarios are constructed rather than shaped from a run. The
  saturation one constructs a *duration* rather than a value: the measured
  performance matrix reached a deferral of 3 at concurrency 4 and never held one for
  ten minutes.
- The `capability-unavailable` selector is the code both recorded experiments
  produced, and not the only one either produced: the pod-loss run also counted one
  `internal-error`. A failure producing a different code reaches
  `InferOpsInferenceServingNothing` only once nothing at all is succeeding.
- The replay reconstructs a store from query results. `sum` and `sum by` are read
  back as the metric; two captured expressions are refused rather than approximated.
  A replay verdict is a statement about that reconstruction, and the three alerts
  reported `not-in-the-capture` are not evidence of silence.
- The owners are roles, not people. Nothing pages either of them, because there is
  nobody and no path.
