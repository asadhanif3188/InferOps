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
> in them was served and no processor second in them was measured. Every usage value
> in an input is typed in by hand. No calculation has been run over the `V1-S4-004`
> evidence.

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
only when the input's evidence class is a measured one and processor and memory use
are both present.

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

An input is a `CostCalculationInput` at `inferops.io/v1alpha1`, with exactly these
fields and no others:

| Field | What it holds |
|---|---|
| `classification` | The evidence class the usage values came from: `synthetic`, `local-real-cpu`, `cloud-real-cpu`, or `cloud-real-gpu` |
| `warning` | What the input is; a synthetic input must say it is synthetic |
| `environmentId` | The environment every workload belongs to |
| `basis` | `estimated`; anything else is refused |
| `priceSourceId` | A rate card committed in the method; no other source is read |
| `window` | `start` and `end`, RFC 3339 in UTC with a `Z`, half-open, from one minute to one day |
| `capacity` | The node's allocatable `cpuCores` and `memoryGibibytes` as decimal strings, and `acceleratorDevices` as an integer |
| `prerequisites` | Claims that outlive a release, each attributed to `prerequisite-layer` |
| `workloads` | One entry per record: `recordId`, `identity`, `declaration`, `presentForWholeWindow`, `shapeChangedInWindow`, `usage`, and `unavailable` |

A workload's `declaration` uses the workload contract's quantity pattern for
`cpuRequest` and `memoryRequest`, so `500m` is half a core, `2Gi` is 2 gibibytes, and
`2G` is 2 × 10^9 bytes. Its `usage` lists `requests`, `inputTokens`, `outputTokens`,
`cpuSeconds`, `memoryByteSeconds`, and `acceleratorSeconds`. Counts are integers and
quantities are decimal strings. A value that is not available is `null`, and
`unavailable` gives its reason from the method's list; a value set and declared
unavailable, or null without a reason, is refused.

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
- a window that is not UTC with a `Z`, is not a real instant, runs backwards, or is
  shorter than a minute or longer than a day;
- a workload that declares a change of reservation inside the window — split the window
  instead;
- a tenant identifier, and any value shaped like a host path, a user directory, or a
  network address;
- measured use that exceeds the node's declared capacity for the window, for one
  workload or all of them together, and device seconds for a workload that reserves no
  device;
- an evidence class that cannot supply usage, such as `mock`.

## What is still supplied by hand

| Input | Where it would come from | Today |
|---|---|---|
| Processor seconds | The container's cgroup processor counter, increase between the samples bounding the window (ADR 0014 D3) | Typed in by hand |
| Memory byte-seconds | The container's working set, integrated trapezoidally between samples inside the window (ADR 0014 D3) | Typed in by hand |
| Requests and tokens | The experiment's raw records, reconciled with the collector's counters | Typed in by hand |
| Node capacity | The node's allocatable resources | Declared by hand; nothing reads a cluster |
| Reservation and replicas | The workload document and the release | Declared by hand |
| Window | The experiment's phase boundaries | Declared by hand |

The integration rules in that table are written and not executed: no reader in this
repository takes a usage value from committed samples. The tool can check that a value
is well formed and fits within the node; it cannot check that it matches the evidence
its input names.

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
0.8879175 exactly, a tie at the sixth place, and rounds half-even to 0.887918. With the
0.000500 model cache claim the environment comes to 0.400500.

**`estimate-incomplete`** — half an hour, one workload present for part of it, and no
memory integral. Its amount, hourly figure, share, and both unit costs are null with the
reason `no-telemetry-source`; the request and token counts are still carried. The
unallocated line is null for the same reason, and the node's own amount, 0.200000, is
still stated, because it does not depend on use.

## Limits

- **Every figure is synthetic.** It demonstrates the arithmetic and says nothing about a
  price.
- **Hand-typed usage** is as good as whoever typed it.
- **A working set counts file-backed pages** the kernel charges to a container, and a
  cgroup processor counter counts every thread in it; both are what the kernel reported,
  not what a request needed.
- **Idle reservations are not charged to the workload** that reserved them; they are on
  the unallocated line.
- **Nothing here is a contract.** The record shape is part of the method (ADR 0007 D10),
  and no schema is published under [`contracts/`](../../contracts/README.md).
