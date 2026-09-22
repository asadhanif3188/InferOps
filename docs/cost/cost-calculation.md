# The V1 cost calculation

Status: **implemented as a repository tool**, under
[ADR 0007](../architecture/decisions/ADR-0007-inference-cost-method.md) as amended by
[ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md).
`tools/cost_calculation` applies [the cost method](cost-method.md) to one declared
input document and writes a result whose every record validates against the shape the
method publishes. It is run by hand, contacts nothing, and emits no telemetry.

> [!IMPORTANT]
> **No cost figure is published here, and none can be produced that means anything.**
> The only rate card committed in this repository is synthetic, so every record the
> tool writes has confidence `none`. Both committed fixtures are synthetic: no request
> in them was served and no processor second in them was measured. Usage in an input is
> typed in by hand unless `tools/cost_baseline` wrote the input from committed samples,
> as it did for [the V1 cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md):
> two records of measured use over the `V1-S4-004` runs, still at synthetic prices.

## What it computes

For one window, one node, and the workloads an input lists, on the `estimated` basis
only:

| Figure | How | Published as |
|---|---|---|
| Workload amount | `(cpuSeconds × cpu rate + memoryByteSeconds ÷ 2^30 × memory rate + acceleratorSeconds × device rate) ÷ 3600`, the device term absent when no device is reserved | `cost.amount` |
| Hourly figure | amount ÷ window hours; the rate over that window, projecting nothing | `derived.amountPerHour` |
| Cost per request | amount ÷ requests × 1,000, with the request count beside it; null below 100 requests | `derived.costPerThousandRequests` |
| Cost per token | amount ÷ (input + output tokens) × 1,000,000, with the count; null below 10,000 tokens | `derived.costPerMillionTokens` |
| Share of the node | amount ÷ node capacity amount | `derived.shareOfNodeCapacity` |
| Reservation | request × replicas × window hours, for processor, memory, and devices; carried, never priced | `reserved.*` |
| Node capacity amount | declared allocatable capacity × rates × window hours | `capacity.amount` |
| Unallocated | node capacity amount − the published workload amounts | `unallocated.amount` |
| Prerequisite | claimed gibibytes × window hours × storage rate, attributed to the prerequisite layer | `prerequisites[].amount` |

The unallocated line is capacity **no workload in the calculation was measured using**:
idle capacity, reservations left unused, the platform and control plane, and any
workload the input does not list. It is reported, never spread, and the workload lines
plus it equal the node exactly. The tool checks that on every result it writes.

Every intermediate value is exact. A published figure is rounded once, half-even, to
six places, from exact values; the unallocated line is the one taken from published
figures, so that the lines a reader sees close.

Confidence is derived from each record's `facts` by the method's rules. With the
synthetic card it is `none` whatever else is true, and `hasMeasuredUtilisation` is true
only when the input's evidence class is a measured one, it names a committed record of
that class, and processor and memory use are both present.

## Running it

```sh
python -m tools.cost_calculation calculate --input INPUT.json --result RESULT.json
python -m tools.cost_calculation verify --input INPUT.json --result RESULT.json
```

`calculate` writes the result. `verify` calculates again and exits `1` if the committed
result differs in any byte after line endings are normalized. Both exit `3` and write
nothing when the input or the method is refused.

The committed fixtures regenerate with:

```sh
python -m tools.cost_calculation verify --input tests/cost/fixtures/cost-calculation/estimate-closes.input.json --result tests/cost/fixtures/cost-calculation/estimate-closes.result.json
python -m tools.cost_calculation verify --input tests/cost/fixtures/cost-calculation/estimate-incomplete.input.json --result tests/cost/fixtures/cost-calculation/estimate-incomplete.result.json
```

## The input

An input has exactly these fields and no others:

| Field | What it holds |
|---|---|
| `schemaVersion` | `inferops.io/v1alpha1` |
| `kind` | `CostCalculationInput` |
| `classification` | The evidence class the usage values came from: `synthetic`, `local-real-cpu`, `cloud-real-cpu`, or `cloud-real-gpu` |
| `usageEvidence` | `null` for a synthetic input. For a measured class, the committed record the usage came from: a `path` under `docs/proof/` and the `sha256` of its content with line endings normalized to LF. The record must exist, match the digest, and declare the same evidence class |
| `warning` | What the input is; a synthetic input must say it is synthetic |
| `environmentId` | The environment every workload belongs to |
| `basis` | `estimated`; anything else is refused |
| `priceSourceId` | A rate card committed in the method; no other source is read |
| `window` | `start` and `end`, RFC 3339 in UTC with a `Z`, half-open, from one minute to one day; a one-hour window starts on the hour |
| `capacity` | The node's allocatable `cpuCores` and `memoryGibibytes` as decimal strings, and `acceleratorDevices` as an integer |
| `prerequisites` | Claims that outlive a release, each attributed to `prerequisite-layer` |
| `workloads` | One entry per record: `recordId`, `identity`, `declaration`, `presentForWholeWindow`, `shapeChangedInWindow`, `usage`, and `unavailable` |

A workload's `declaration` uses the workload contract's quantity pattern for
`cpuRequest` and `memoryRequest`, so `500m` is half a core, `2Gi` is 2 gibibytes, and
`2G` is 2 × 10^9 bytes. Its `usage` lists `requests`, `inputTokens`, `outputTokens`,
`cpuSeconds`, `memoryByteSeconds`, and `acceleratorSeconds`. Counts are integers and
quantities are decimal strings. A value that is not available is `null`, and
`unavailable` gives its reason from the method's list; a value set and declared
unavailable, or null without a reason, is refused. The one exception is
`acceleratorSeconds` for a workload that reserves no device: it is not applicable, so it
is `null` with **no** reason, and is not listed as unavailable.

## What it refuses

Before writing any figure, the tool refuses:

- a basis other than `estimated`, with the reason the method gives;
- a price source that is not committed in the method, or one that is fetched, carries a
  URL, has no version, has an effective date that is not a real `YYYY-MM-DD` date, has a
  currency that is not a three-letter code, names an undeclared class, claims a
  confidence ceiling above its class, prices a unit twice or not at all, prices an
  unpriced unit, or writes a rate that is not a non-negative decimal at six places;
- a synthetic rate card that does not self-identify, is marked publishable, caps
  confidence above `none`, or does not say its rates are invented;
- any binary float, `NaN`, or duplicate key anywhere in the input;
- a window that is not UTC with a `Z`, is not a real instant, runs backwards, is
  shorter than a minute or longer than a day, or lasts one hour without starting on the
  hour;
- a workload that declares a change of reservation inside the window — split the window
  instead;
- a tenant identifier, and any value shaped like a Windows drive path, a `/Users` or
  `/home` directory, or an IPv4 address other than loopback (host names and IPv6
  addresses are not recognized);
- measured processor, memory, or device use that exceeds the node's declared capacity
  for the window, for one workload or all of them together; more devices reserved across
  a workload's replicas than the node declares; and device seconds, or a reason for
  missing them, for a workload that reserves no device;
- an evidence class that cannot supply usage, such as `mock`; a measured class that names
  no committed record, one outside `docs/proof/`, one whose digest does not match, or one
  that declares a different class; and a synthetic input that names any record.

## What is still supplied by hand

| Input | Where it would come from | Typed input | Written by `tools/cost_baseline` |
|---|---|---|---|
| Processor seconds | Each pod's cgroup processor counter, increase between the samples bounding the window, summed over the workload's pods (ADR 0014 D3) | Typed in by hand | Taken from the samples |
| Memory byte-seconds | Each pod's cgroup working set, integrated trapezoidally between samples inside the window (ADR 0014 D3) | Typed in by hand | Taken from the samples |
| Requests and tokens | The experiment's raw records, reconciled with the collector's counters | Typed in by hand | Counted from the raw records |
| Node capacity | The node's allocatable resources | Declared by hand; nothing reads a cluster | Read from the environment the experiment captured |
| Reservation and replicas | The workload document and the release | Declared by hand | Read from the environment the experiment captured |
| Window | The experiment's phase boundaries | Declared by hand | The samples bounding a run's phases |
| Identity | The workload document and the release | Declared by hand | The collector's labels; the owner from the executed values file |

`tools/cost_calculation` itself still reads no samples. For a typed input it can check
that a value is well formed and fits within the node, and that a measured class names a
committed record of that class; it cannot check that the value matches that record. An
input `tools/cost_baseline` wrote is checked by that tool's `verify`, which refuses a
record that does not regenerate from its inputs and regenerates the input byte for byte.
The tool and its rules are described in [the cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md).

## The committed fixtures

Both fixtures use the synthetic card: 0.040000 per core-hour, 0.005000 per gibibyte-hour,
1.200000 per device-hour, and 0.000100 per stored gibibyte-hour.

**`estimate-closes`** — one hour, a node of 8 cores and 16 gibibytes, two workloads.

| Record | Measured use | Amount | Per hour | Per thousand requests | Per million tokens | Share |
|---|---|---|---|---|---|---|
| `example-estimate-0001` | 2,160 processor seconds; 3 GiB held for the hour | 0.039000 | 0.039000 | 0.032500 of 1,200 | 0.067708 of 576,000 | 0.097500 |
| `example-estimate-0002` | 300 processor seconds; half a GiB held for the hour | 0.005833 | 0.005833 | null: 40 requests, below the minimum | null: no token source | 0.014583 |
| Unallocated | — | 0.355167 | — | — | — | 0.887918 |
| **Node** | — | **0.400000** | — | — | — | 1 |

The first workload reserved 2.000000 core-hours and was measured using 0.6 of a
core-hour; the rest of its reservation is on the unallocated line, not on its record. The unallocated share is
0.8879175 exactly, a tie at the sixth place, and rounds half-even to 0.887918. The
amounts close against the node exactly; the shares are each rounded on their own, so the
three published shares add to a millionth over one, and only the amounts are required
to close. With the 0.000500 model cache claim the environment comes to 0.400500.

**`estimate-incomplete`** — half an hour, one workload present for part of it, and no
memory integral. Its amount, hourly figure, share, and both unit costs are null with the
reason `no-telemetry-source`; the request and token counts are still carried. The
unallocated line is null for the same reason, and the node's own amount, 0.200000, is
still stated, because it does not depend on use.

## Limits

- **Every price is synthetic**, so every amount demonstrates the arithmetic and says
  nothing about a price. The use is synthetic in both fixtures and measured in the two
  baseline records. (Until 2026-09-22 this line called every figure synthetic, which
  stopped being true when `V1-S4-005-PR2` committed records of measured use.)
- **Hand-typed usage** is as good as whoever typed it. Usage taken from samples is as
  good as the samples, which were read every few seconds on one host.
- **A working set counts file-backed pages** the kernel charges to a pod, and a cgroup
  processor counter counts every thread in it; both are what the kernel reported, not
  what a request needed.
- **The hourly figure over a short window** is the amount scaled up, and reads like a
  run rate; it means nothing apart from the window it carries.
- **Idle reservations are not charged to the workload** that reserved them; they are on
  the unallocated line.
- **Nothing here is a contract.** The record shape is part of the method (ADR 0007 D10),
  and no schema is published under [`contracts/`](../../contracts/README.md).
