# The V1 cost and capacity method

Status: **published method over an accepted cost method.** This document says how V1
turns measured use into an estimated cost, and how far that cost, and the load it was
measured under, can be read as a statement about capacity. It keeps two lists apart in
every topic: what is calculated and checked, with the test, gate, and record behind it,
and what is specified and not calculated, not enforced by a test, or not known. It adds
no rule, basis, price, or figure and moves no claim. The rules are
[the cost method's](cost-method.md), decided in
[ADR 0007](../architecture/decisions/ADR-0007-inference-cost-method.md) and amended by
[ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md),
and every certification level is read from
[the claim and evidence register](../testing/claim-evidence-matrix.md).

> [!IMPORTANT]
> **No amount in this repository is a bill, and none says what anything costs.** V1
> calculates one kind of amount, an *estimate*: a price applied to measured use. The
> use in the two committed estimates is real, measured on one host. Every price is
> invented, so every amount has confidence `none`. No provider account, invoice, or
> billing export exists, no platform component computes a cost record, and no capacity
> figure is published.

The authoritative form is
[`cost-capacity-method.v1alpha1.json`](cost-capacity-method.v1alpha1.json).
[`tests/testing/test_published_methods.py`](../../tests/testing/test_published_methods.py)
holds the two in agreement, resolves every test, gate, file, and record the data names,
puts each cost rule on the side of the line its enforcement allows and each basis on the
side its reachability allows, requires every rule, basis, limitation, and open question
of the cost method to appear, and reads every figure below back out of the committed file
it came from.

The companions are [the V1 security method](../security/security-method.md) and
[the V1 observability method](../telemetry/observability-method.md).

## How to read it

Each topic has two tables, read the way
[the security method](../security/security-method.md#how-to-read-it) describes.
**Implemented** rows name what verifies them, the committed record they rest on, and an
evidence label. **Not implemented** rows name what carries the gap — a cost rule
enforced by review alone, a basis V1 cannot reach, a limitation or open question of the
cost method, an uncertified claim, or one of the nine gaps listed with this method — and
what may not be claimed while it stands.

Three kinds of number appear in a cost record, and each has its own evidence class.
Reading one with another's class is the mistake this method exists to prevent:

| Number | Evidence class | What it can support |
|---|---|---|
| Processor seconds, memory byte-seconds, requests, and tokens in the baseline | `local-real-cpu`, measured on one host during `V1-S4-004` | What that release used while serving that load, and nothing about another host, release, or prompt |
| Every rate | `synthetic`: invented, and labelled so in its own contents | Nothing about any price |
| Every amount, and every figure divided from one | `estimated`: a synthetic price applied to measured use | That the arithmetic closes; not a cost |
| An invoice | none exists; `production-experience` is unreachable from this repository | — |

The worked example and the calculation's two fixtures are `synthetic` throughout: no
request in them was served and no processor second measured.

## 1. Actual billing, estimated cost, and allocated cost

| Basis | What it means | In V1 |
|---|---|---|
| `actual` | Taken from a provider's invoice or billing export for the period it covers | Unreachable |
| `allocated` | A price applied to the capacity a workload reserved, used or not | Specified, not calculated |
| `estimated` | A price applied to the use a workload was measured making | The only basis V1 calculates |

**Why the words are tested.** An allocation described as spend, a total headed billed, a
column called charges: each turns a model of a cost into a claim about one, and none of
them changes a number. So the vocabulary of a bill is refused on any record whose basis
is not `actual`, not merely discouraged.

**Implemented**

| What | Rules and claim | Verified by | Record | Label |
|---|---|---|---|---|
| Every amount carries one basis; V1 calculates `estimated` only and refuses the other two before writing anything; amounts on different bases are never summed; a non-`actual` amount carries no invoice reference and no invoice word | `no-estimate-is-a-bill`, `an-estimate-and-an-allocation-are-never-summed`, `v1-calculates-the-estimated-basis-only`, `a-calculation-refuses-a-basis-v1-does-not-reach`; claim `a-cost-figure-cannot-be-presented-as-a-bill` | `test_only_an_actual_basis_may_reference_an_invoice`, `test_every_total_is_computed_within_one_basis`, `test_the_only_basis_v1_can_reach_is_an_estimate`, `test_a_basis_v1_does_not_reach_is_refused`, `test_the_report_prices_no_reservation_beside_the_estimate`; gate `default-lane-tests` | [v1-s0-008-pr1](../proof/cost/v1-s0-008-pr1-validation.md), [v1-s4-005-pr1](../proof/cost/v1-s4-005-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| `actual` needs an invoice. No provider account exists and nothing has been billed | limitation `no-invoice-has-ever-been-read`; claim `what-running-an-inference-workload-costs-on-a-provider` is not claimed | No amount here is what anybody was charged |
| `allocated` is specified and demonstrated by the worked example, whose traffic is chosen rather than served; a V1 calculation does not produce it, so an allocation and an estimate of one window never sit side by side | limitations `allocation-overcharges-idleness`, `the-example-is-not-a-measurement` | No allocated amount is calculated in V1, and a reservation is never priced beside an estimate |

## 2. Formula, units, and precision

For one workload over one window, on the estimated basis:

```text
amount = ( cpuSeconds × core-hour rate
         + memoryByteSeconds ÷ 2^30 × gibibyte-hour rate
         + acceleratorSeconds × device-hour rate ) ÷ 3,600
```

The device term is absent when no device is reserved. Processor quantities are
millicores, memory is binary (a gibibyte is 2^30 bytes; reading it as 10^9 would
understate every memory line by 7.4 per cent), and devices are whole. Arithmetic is
exact; money is a decimal string at six places, rounded half-even **once**, at the end.
The full table of units is in [the cost method](cost-method.md#6-units-and-precision).

**Implemented**

| What | Rule and claim | Verified by | Record | Label |
|---|---|---|---|---|
| The formula above, exact conversions, exact arithmetic, and one half-even rounding at six places, in `tools/cost_calculation` | `money-is-decimal-never-binary-float`; claim `a-cost-figure-cannot-be-presented-as-a-bill` | `test_every_amount_recomputes_independently_in_decimal`, `test_rounding_is_half_even_once_at_six_places`, `test_a_kubernetes_quantity_converts_exactly`, `test_memory_is_binary_and_a_decimal_suffix_is_not_read_as_binary`, `test_every_amount_and_rate_is_a_decimal_string`; gate `default-lane-tests` | [v1-s4-005-pr1](../proof/cost/v1-s4-005-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| The device term is tested on a synthetic fixture only. No accelerator has been reserved or used, and no accelerator metric exists | gap `no-accelerator-was-used` | No accelerator line has been calculated from measured use |

## 3. Price source, version, and date

Every record names its rate card by identifier, version, and effective date. One card is
committed: `synthetic-illustrative-v1`, version `1`, effective 2026-08-26, in USD, at
0.040000 per core-hour and 0.005000 per gibibyte-hour. **Every rate on it is invented**,
and it says so in its own contents, where a label cannot be lost by copying the file
somewhere else.

**Implemented**

| What | Rules and claim | Verified by | Record | Label |
|---|---|---|---|---|
| A price is read only from a card committed in the method, versioned, dated, and decimal, and never fetched while computing; a synthetic card identifies itself and names in its own scope what may use it | `no-price-is-fetched-at-runtime`, `a-synthetic-rate-card-declares-its-class-in-its-own-contents`, `a-price-source-is-refused-unless-committed-versioned-dated-and-decimal`; claim `a-cost-figure-cannot-be-presented-as-a-bill` | `test_every_price_source_is_committed_rather_than_fetched`, `test_a_synthetic_price_source_identifies_itself`, `test_the_only_published_price_source_is_synthetic`, `test_an_invalid_price_source_is_refused`, `test_a_price_source_not_committed_in_the_method_is_refused`, `test_the_synthetic_card_names_the_baseline_in_its_own_scope`; gate `default-lane-tests` | [v1-s4-005-pr1](../proof/cost/v1-s4-005-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| No provider, negotiated, or amortised-hardware card is committed; a contributor's own machine has no honest hourly price; no exchange rate exists | limitations `the-only-rate-card-is-synthetic`, `no-local-host-rate-is-honest`, `no-currency-conversion`; open question `which-provider-price-sources`; gap `no-real-rate-card` | No price here is a provider's, a contract's, or a machine's |

## 4. Workload and resource inputs, and the measurement window

| Input | Where the baseline's value came from |
|---|---|
| Processor seconds | Each request-path pod's cgroup counter increase between the two samples bounding the run, API plus runtime |
| Memory byte-seconds | Each pod's working set, integrated trapezoidally between consecutive samples inside the window |
| Requests and tokens | The run's raw records, every one required to lie inside the window |
| Window | Opens on the last sample at or before the first phase and closes on the first sample at or after the last: run 1's is 0.091321 hours |
| Reservation and node capacity | The environment the experiment captured: declared, not read from the samples |
| Accelerator seconds | Not applicable: no device was reserved |

The processor increase and the memory integral therefore cover exactly the same
interval, and neither borrows a reading from outside it. The rules are
[ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md)
D3's, and the full input table is [the cost method's](cost-method.md#9-inputs).

**Implemented**

| What | Rules and claim | Verified by | Record | Label |
|---|---|---|---|---|
| `tools/cost_baseline` takes use from the committed `V1-S4-004` samples and raw records, refuses a performance record that does not regenerate, is not local real evidence, or failed its own checks, and names it in every input by path and digest | `measured-use-names-its-evidence-class`, `every-required-input-names-a-source-or-records-that-none-exists`; claim `the-cost-method-was-applied-to-use-taken-from-a-measured-run` | `test_usage_recomputes_from_the_jsonl_lines_by_integer_sums`, `test_traffic_recomputes_from_the_raw_lines`, `test_the_window_is_bounded_by_samples_on_both_sides`, `test_processor_seconds_are_the_increase_between_the_bounding_samples`, `test_memory_is_integrated_trapezoidally_and_never_extrapolated`, `test_a_record_that_does_not_regenerate_is_refused`, `test_a_measured_class_must_name_matching_committed_evidence`, `test_every_input_names_a_declared_signal_or_no_source_at_all`; gate `default-lane-tests` | [the V1 cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md), [v1-s4-005-pr2](../proof/cost/v1-s4-005-pr2-validation.md) | `local-static` |
| A window is half-open, UTC, and between a minute and a day; a declared change of reservation inside one is refused rather than averaged | claim `a-cost-figure-cannot-be-presented-as-a-bill` | `test_a_window_outside_the_method_rules_is_refused`, `test_a_window_of_exactly_one_minute_and_one_day_is_accepted`, `test_a_declared_shape_change_is_refused_rather_than_averaged`; gate `default-lane-tests` | [v1-s4-005-pr1](../proof/cost/v1-s4-005-pr1-validation.md) | `local-static` |

The label is `local-static` because what the claim certifies is a file-reading
operation over committed samples. The samples themselves are `local-real-cpu`, and
their measurement is certified by a different claim, in section 7.

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| No metrics server and no durable utilisation series: use reaches a calculation only from a committed experiment's files, a hand-typed input is as good as its typist, and capacity and the reservation are declarations | limitations `no-utilisation-source`, `measured-use-is-typed-in-by-hand`, `capacity-is-declared-not-read`; gap `no-utilisation-series` | No usage value is read from telemetry or a running cluster |
| A change of reservation the input does not declare is caught by review alone | rule `a-window-in-which-the-shape-changed-is-split` | No check detects an undeclared change of reservation |

## 5. Allocation, idle, and shared cost

The allocation method is `observed-utilisation-share`: a workload is priced for what it
was measured using. Everything else on the node is one line, reported and never spread:

| On the unallocated line | Why it is there |
|---|---|
| Idle capacity | Nobody was measured using it |
| Reservation a workload made and left idle | The estimate prices use, not reservation |
| The platform, the control plane, and other pods on the node | Shared environment cost; dividing it makes a workload's figure move when the workload count changes |
| The release's own collector | A stated choice, not a measurement of whose it is; counting it as the workload's would change neither run's amount by a thousandth |

A prerequisite, such as the model cache that outlives the release, is attributed outside
every workload, because a cost that survives the workload is not the workload's. In run
1 the workload's share of the node was 0.454390: 0.021934 of the node's 0.048270, with
0.026336 on the unallocated line, and the lines close exactly.

**Implemented**

| What | Rules and claim | Verified by | Record | Label |
|---|---|---|---|---|
| What no workload was measured using is its own line, the lines close against the node, and a prerequisite is attributed outside every workload | `unreserved-capacity-is-reported-not-spread`, `the-model-cache-is-a-prerequisite-cost`; claim `a-cost-figure-cannot-be-presented-as-a-bill` | `test_the_workload_lines_and_the_residual_close_against_the_node`, `test_a_prerequisite_line_is_attributed_outside_every_workload`, `test_the_workload_lines_and_the_unallocated_line_close_against_the_node`, `test_the_unallocated_use_closes_and_prices_to_the_unallocated_line`, `test_the_collector_is_measured_and_left_on_the_unallocated_line`; gate `default-lane-tests` | [v1-s0-008-pr1](../proof/cost/v1-s0-008-pr1-validation.md), [the V1 cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| An idle reservation is not charged to the workload that made it; it is carried, unpriced, on its record | limitation `an-estimate-leaves-reserved-idle-capacity-unattributed` | No workload line includes capacity it reserved and did not use |

## 6. Outputs, and how they map to a cost record

| Output | Record field | Run 1 | Run 2 |
|---|---|---|---|
| Estimated amount, USD | `cost.amount` | 0.021934 | 0.021775 |
| The rate over the window, projecting nothing | `derived.amountPerHour` | 0.240182 | 0.239127 |
| Per thousand requests, of 183 | `derived.costPerThousandRequests` | 0.119855 | 0.118988 |
| Per million tokens | `derived.costPerMillionTokens` | null: 9,516 tokens is below the minimum | null, the same |
| Share of the node | `derived.shareOfNodeCapacity` | 0.454390 | 0.452395 |
| Confidence | `cost.confidence` | `none` | `none` |

Dividing two published figures by hand does not reproduce a third: 0.021934 over
0.048270 gives 0.454402, not 0.454390. Every figure is divided from the exact values and
rounded once, at the end, so each six-place figure is correct on its own and none is
derived from another's rounding.

Every one of those is read back by the suite from
[the run 1 result](../proof/cost/v1-s4-005-pr2-baseline-run-1.result.json) and
[the run 2 result](../proof/cost/v1-s4-005-pr2-baseline-run-2.result.json).

A cost record carries its own audit trail: `period`, `identity` (workload, owner,
environment, model, runtime), `reserved`, `usage`, `cost` (amount, currency, basis,
allocation method, price source with version and date, confidence), `derived` with each
denominator beside its unit cost, `completeness`, the `facts` its confidence is derived
from, and `evidence` naming the assumptions and the class the use came from. The
tenant field exists in the shape and may not appear in any committed record. The full
field list is [the cost method's](cost-method.md#11-the-record-shape).

**Implemented**

| What | Rules and claim | Verified by | Record | Label |
|---|---|---|---|---|
| Every unit cost is divided from the exact amount and carries its denominator, and is null below 100 requests or 10,000 tokens; a missing input is null with a reason; every calculated record validates against the shape; no committed record carries a tenant | `a-unit-cost-carries-its-denominator`, `an-unavailable-input-is-null-with-a-reason`, `a-calculated-record-validates-against-the-published-shape`, `a-committed-record-carries-no-tenant-identifier`; claim `a-cost-figure-cannot-be-presented-as-a-bill` | `test_every_unit_cost_carries_its_denominator_or_is_null`, `test_a_null_output_carries_a_reason_and_a_reason_carries_a_null`, `test_no_committed_record_carries_a_tenant_identifier`, `test_every_calculated_record_validates_against_the_published_shape`, `test_a_unit_cost_is_divided_from_the_exact_amount_not_the_rounded_one`, `test_the_token_unit_cost_is_null_below_the_minimum_and_says_so`; gate `default-lane-tests` | [v1-s4-005-pr1](../proof/cost/v1-s4-005-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| The shape is part of the method; no cost record schema is published under [`contracts/`](../../contracts/README.md) | gap `no-cost-record-contract` | No cost record contract is published, and nothing consumes one |
| The minimum denominators are declared, not derived, and a cost per thousand requests is a throughput figure in the units of a price | limitations `minimum-samples-are-arbitrary`, `a-unit-cost-is-a-throughput-figure` | No unit cost here is a price per request or per token |

## 7. Cost against the measured load and resource profile

An amount is only as general as the load it was measured under, so the baseline is tied
to the run rather than to the release:

- **The same span.** Each record covers one run's whole load span, the warm-up included,
  and divides by that run's 183 requests. The window is a load span, not an accounting
  hour: an hour on the hour would hold idle time these do not, and a different amount.
- **The same profile.** Every request carried one fixed 35-token prompt and returned 17
  tokens. Completed requests stayed between 0.554 and 0.575 per second at every
  concurrency, and the runtime used 99.1% to 99.9% of its six-core limit at every level,
  the baseline included ([the performance findings](../proof/serving/v1-s4-004-pr2-performance-findings.md)).
- **Why the amount is almost all processor.** The request path used 1952.124170 processor
  seconds in run 1, against a reservation of 0.100453 core-hours: it used about five times
  what it reserved, because the runtime requests one core and is limited to six. The
  estimate prices the use, not the reservation.
- **What the hourly figure is.** The amount divided by the window, 0.091321 hours: the rate
  while serving this load. It projects nothing, because nobody measured an hour of it.

So a cost per thousand requests here is a figure about **one single-slot runtime serving
one cached prompt on one host**, priced at invented rates. A different prompt, output
length, slot count, replica count, or host would change it by an amount nobody measured.

**Implemented**

| What | Claims | Verified by | Record | Label |
|---|---|---|---|---|
| The baseline covers each run's whole load span and divides by its own traffic; its average processor use agrees with the performance record's own phase figures; the findings regenerate from the committed record | `the-cost-method-was-applied-to-use-taken-from-a-measured-run`, `a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed` | `test_the_window_average_agrees_with_the_records_own_phase_figures`, `test_the_warm_up_is_inside_the_window_and_its_requests_are_counted`, `test_the_committed_findings_regenerate_from_the_committed_record`, `test_the_resource_table_matches_the_findings`; gate `default-lane-tests` | [the performance findings](../proof/serving/v1-s4-004-pr2-performance-findings.md), [the V1 cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md) | `local-real-cpu` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| ADR 0007 D11 publishes no figure for what running an inference workload costs. The baseline is consistent with it because every price is invented and its confidence is `none`; that reading is the baseline record's own, and no test enforces the rule | rule `no-cost-figure-is-published-from-v1`, enforced by review; claim `what-running-an-inference-workload-costs-on-a-provider` is not claimed | No amount in this repository is a published cost figure |

## 8. Confidence and uncertainty

Confidence is derived, never typed: the lowest ceiling among the rules that hold for a
record's own facts. For the baseline, two hold — no invoice caps an estimate at `medium`,
and the synthetic card caps everything at `none` — so the card alone decides it. Measured
use raises the ceiling of the basis, not of the card.

| Uncertainty in the measured use | Size | Direction |
|---|---|---|
| Window edges with no load in flight | 0.8% and 1.3% of the two windows | The hourly figure sits a little below the load's own rate |
| Host and node clocks | Under 0.05% of a window | Negligible |
| Sample read time | Up to about two seconds a read, placed at its midpoint | Inside the window's edges |
| The kernel's working set | Includes file-backed pages charged to the pod | Memory prices what the kernel reported, not what the process allocated |
| Background on the node | 12 other pods, the system, and the sampler | Not in the workload's figures; it competes for the same cores |

The sizes are the baseline record's, derived there from the committed samples.

**Implemented**

| What | Rule and claim | Verified by | Record | Label |
|---|---|---|---|---|
| Confidence is recomputed from each record's facts; synthetic usage never counts as measured; a synthetic card caps every record at `none` | `confidence-is-derived-not-asserted`; claim `a-cost-figure-cannot-be-presented-as-a-bill` | `test_declared_confidence_equals_derived_confidence`, `test_a_synthetic_rate_card_caps_every_example_record_at_no_confidence`, `test_confidence_on_the_estimated_basis_is_derived_from_its_facts`, `test_synthetic_usage_never_counts_as_measured_utilisation`; gate `default-lane-tests` | [v1-s4-005-pr1](../proof/cost/v1-s4-005-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| Every record has confidence `none`; it rises only with a real card, and an estimate stops at `medium` even then | gap `no-real-rate-card` | No record carries confidence above `none` |
| Two repetitions on one host; the sources are listed and no interval is computed | gap `no-uncertainty-interval` | No confidence interval, variance, or error bound is claimed |

## 9. Excluded costs

Nothing below is in any amount, and none of it is on the unallocated line either,
because the node's capacity amount prices only processor and memory:

- the model cache claim, whose size the performance record does not carry;
- the node's disk and images, and the virtual machine's overhead outside the node's
  allocatable capacity;
- network, the port-forward the load travelled over, and the load generator's host;
- the time before and between runs: model loading, most of the idle baseline, and the
  settle intervals.

**Implemented**

| What | Claim | Verified by | Record | Label |
|---|---|---|---|---|
| An absent input is null with a declared reason and never a zero; a measured zero is priced as one; every gap in the method's telemetry mapping carries a limitation | `a-cost-figure-cannot-be-presented-as-a-bill` | `test_the_incomplete_fixture_is_null_with_a_reason_and_never_zero`, `test_a_missing_input_must_be_null_with_a_declared_reason`, `test_a_measured_zero_is_a_measurement_and_is_priced_as_one`, `test_the_method_declares_a_limitation_for_every_gap_it_has`; gate `default-lane-tests` | [the V1 cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| Storage, network, the host outside the node, and the time outside each window are not priced | limitation `no-egress-or-network-cost`; gap `unpriced-resources` | No amount here is a total cost of running anything |

## 10. Dashboard and query hooks

**None is added, and that is the hook.** Nothing emits a cost record, so a panel or a
query would read a series no component produces, and an empty panel reads as a quiet
system rather than an absent capability. Every record that could carry a hook says so
instead: [the telemetry catalog](../telemetry/telemetry-catalog.md) defers the cost
record attribute and counter with a reason, and [the dashboard](../telemetry/inference-operations-dashboard.md)
and [the correlation queries](../telemetry/telemetry-correlation-queries.md) each list
the counter as having no panel and no query, with the reason. The cost records
themselves are files a person regenerates:

```sh
python -m tools.cost_baseline verify --record-dir docs/proof/serving --record-prefix v1-s4-004-pr1- --dir docs/proof/cost --prefix v1-s4-005-pr2-
python -m tools.cost_calculation verify --input docs/proof/cost/v1-s4-005-pr2-baseline-run-1.input.json --result docs/proof/cost/v1-s4-005-pr2-baseline-run-1.result.json
python -m tools.cost_calculation verify --input docs/proof/cost/v1-s4-005-pr2-baseline-run-2.input.json --result docs/proof/cost/v1-s4-005-pr2-baseline-run-2.result.json
```

**Implemented**

| What | Claim | Verified by | Record | Label |
|---|---|---|---|---|
| The catalog defers the cost signals with a reason, the dashboard and the queries each say why the counter has no panel and no query, and the method's deferred attribute is the catalog's | `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label` | `test_a_metric_that_is_not_emitted_says_why`, `test_every_catalog_metric_is_panelled_or_says_why_not`, `test_every_metric_with_no_query_says_why_it_has_none`, `test_the_deferred_cost_attribute_is_the_one_this_method_names`; gate `default-lane-tests` | [v1-s0-007-pr1](../proof/telemetry/v1-s0-007-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| No platform component computes, emits, stores, or reads a cost record, and which one would is undecided | signal `inferops_cost_records_total`, not emitted; limitation `only-a-repository-tool-computes`; open question `who-computes-a-cost-record`; gap `no-cost-producer` | No dashboard panel, query, or alert over cost exists |

## 11. Capacity: what the evidence supports, and what is deferred

**What the evidence supports** is one statement about one setup: for one single-replica
release on `docker-desktop`, with a one-slot runtime at a six-core limit serving one fixed
prompt, driven twice, the observed degradation point is concurrency 2. Completed requests
stayed flat while median latency rose about twofold and fourfold. That is a bounded local
observation under
[ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md),
and it is not InferOps's capacity, the chart's, the model's, or the runtime's.

**Capacity questions deferred to later versions**, none of which V1 answers:

- how many requests a release sustains, and at what latency, under sustained or
  open-arrival load;
- how that changes with more slots, threads, processor, replicas, or an accelerator;
- how it changes with a varied or uncached prompt mix, or outputs nearer the token limit;
- what a unit of capacity costs on a provider, and how a local estimate compares with it;
- how many replicas a node of a given size holds, beyond the one refusal recorded below.

**Implemented**

| What | Claim | Verified by | Record | Label |
|---|---|---|---|---|
| One bounded run and its degradation point, computed by `tools/performance_findings`, which refuses a record claiming a benchmark, a capacity figure, or saturation | `a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed` | `test_a_record_claiming_a_benchmark_capacity_or_saturation_is_refused`, `test_the_runtime_never_read_more_than_one_request_processing`, `test_the_report_refuses_the_readings_adr_0013_forbids`; gate `default-lane-tests` | [the performance findings](../proof/serving/v1-s4-004-pr2-performance-findings.md), [v1-s4-004-pr1](../proof/serving/v1-s4-004-pr1-validation.md) | `local-real-cpu` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| A stated throughput and capacity under load is deferred out of V1, and the capacity layer declares no test paths | claim `sustained-throughput-and-capacity-under-load` is deferred; gap `no-capacity-experiment` | No capacity figure, sizing rule, or scaling curve |
| Which limit bound the rate, the single slot or the processor limit, is not established: throttling counters were not sampled and no run varied the slot count | gap `no-bottleneck-attribution` | The single slot is not claimed as the bottleneck, and the processor limit is not either |
| The multi-replica workflow refused at its capacity gate on the reference host, about 165 MiB of memory short, before installing anything; the gate was not weakened | claim `multi-replica-serving-is-certified` is not claimed | No figure for two serving replicas exists |

## Gaps

Nine gaps, each named in the data and none scheduled:

| Gap | What is missing |
|---|---|
| `no-real-rate-card` | Any provider, negotiated, or amortised-hardware price |
| `no-accelerator-was-used` | Any accelerator use, and any accelerator metric |
| `no-utilisation-series` | A metrics server or a durable utilisation series |
| `no-cost-record-contract` | A cost record schema under `contracts/` |
| `no-uncertainty-interval` | More than two repetitions, and any interval computed from them |
| `unpriced-resources` | A price for storage, network, and the host outside the node |
| `no-cost-producer` | A platform component that computes and emits a cost record |
| `no-capacity-experiment` | Any sustained-load, multi-replica, other-host, accelerator, or open-arrival experiment |
| `no-bottleneck-attribution` | Throttling counters, and a run that varied the slot count |

## What publishing this corrected

One statement had stopped being true, and it is corrected in place:

- **The cost calculation document's limits called every figure synthetic.** Since
  `V1-S4-005-PR2`, two committed records carry use measured on a real host and taken
  from its samples by tool. What is synthetic is every price, and so every amount priced
  from it.

## Related records

| Topic | Document |
|---|---|
| The decisions this method is published under | [ADR 0007](../architecture/decisions/ADR-0007-inference-cost-method.md), [ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md), [ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md) |
| Every basis, rule, input, output, and limitation | [The cost method](cost-method.md) |
| The tool, and what it refuses | [The cost calculation](cost-calculation.md) |
| The two estimated records, read in full | [The V1 cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md) |
| The load and resource profile behind them | [The performance findings](../proof/serving/v1-s4-004-pr2-performance-findings.md) |
| A synthetic example on the allocated basis | [The worked example](worked-example.md) |
| The security and observability halves | [The V1 security method](../security/security-method.md), [the V1 observability method](../telemetry/observability-method.md) |
