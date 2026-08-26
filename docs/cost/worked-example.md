# A worked synthetic example

> [!IMPORTANT]
> **Every number on this page is invented.** The machine, the reservations, the
> traffic, and above all the prices correspond to no host, no provider, and no
> measurement this project has ever taken. Nothing in this repository computes a cost
> record, and no request counted here was served.
>
> The example exists to demonstrate two things: that the arithmetic closes, and that a
> missing input produces a null rather than a zero. It is not evidence of what
> anything costs, and its confidence is `none` for exactly that reason.

The inputs and every figure below are committed in
[`cost-method.v1alpha1.json`](cost-method.v1alpha1.json) and recomputed in exact
decimal by [`tests/cost/`](../../tests/cost/). A number typed here that the
arithmetic does not produce is a failing test, and so is a number here that the data
does not declare.

The method itself is in [cost-method.md](cost-method.md).

## The setup

A single-node cluster, one accounting hour, and a rate card nobody should believe.

| Item | Value |
|---|---|
| Window | 2026-08-26T00:00:00Z to 2026-08-26T01:00:00Z, half-open |
| Window length | 1.000000 hours |
| Node allocatable processor | 8.000000 cores |
| Node allocatable memory | 16.000000 gibibytes |
| Node allocatable accelerators | 0.000000 devices |
| Rate card | `synthetic-illustrative-v1`, effective 2026-08-26, USD |
| Basis | `allocated` |
| Allocation method | `requested-resource-share` |

The rate card, repeated here so the arithmetic can be followed without a second file:

| Unit | Rate per hour |
|---|---|
| `cpu-core-hour` | 0.040000 |
| `memory-gibibyte-hour` | 0.005000 |
| `accelerator-device-hour` | 1.200000 |
| `storage-gibibyte-hour` | 0.000100 |

## What the machine costs for the hour

```text
8.000000 x 0.040000  +  16.000000 x 0.005000  +  0.000000 x 1.200000  =  0.400000
```

That is the whole number to be accounted for. Everything below either allocates part
of it to a workload or reports it as unreserved.

## Two workloads

| Record | Workload | Reservation | Replicas |
|---|---|---|---|
| `example-cost-0001` | `support-assistant`, environment `dev` | 1 core, 2Gi memory, no accelerator | 2 |
| `example-cost-0002` | `mock-llm-ci`, environment `ci` | 500m, 1Gi memory, no accelerator | 1 |

Neither record carries a tenant identifier. The field exists in the record shape and
is populated at runtime; it is classed `tenant-attributable` in the telemetry
catalog, which has no permitted placement in a committed record, and a test refuses
one that appears here anyway.

### `example-cost-0001`

Reserved across the window: 2.000000 core-hours, 4.000000 gibibyte-hours, 0.000000
device-hours.

```text
2.000000 x 0.040000  +  4.000000 x 0.005000  +  0.000000 x 1.200000  =  0.100000
```

| Figure | Value | Denominator |
|---|---|---|
| Amount | 0.100000 USD | — |
| Share of the machine | 0.250000 | — |
| Cost per thousand requests | 0.083333 USD | 1,200 requests |
| Cost per million tokens | 0.173611 USD | 576,000 tokens |

```text
0.100000 / 1200 x 1000     = 0.083333
0.100000 / 576000 x 1000000 = 0.173611
```

Three inputs are unavailable — processor seconds, memory byte-seconds, and
accelerator seconds — each with the reason `no-telemetry-source`. They are exactly
the inputs an `estimated` basis would need, which is why this record is `allocated`
and why no relabelling could make it anything else.

### `example-cost-0002`

Reserved across the window: 0.500000 core-hours, 1.000000 gibibyte-hours, 0.000000
device-hours.

```text
0.500000 x 0.040000  +  1.000000 x 0.005000  +  0.000000 x 1.200000  =  0.025000
```

| Figure | Value | Denominator |
|---|---|---|
| Amount | 0.025000 USD | — |
| Share of the machine | 0.062500 | — |
| Cost per thousand requests | null, `below-minimum-sample` | 40 requests |
| Cost per million tokens | null, `no-telemetry-source` | none |

This record exists to exercise the two missing-data paths. Forty requests is below
the declared minimum of one hundred, so the request unit cost is **null rather than a
rate** — the arithmetic would have produced a number, and the number would have been
a statement about forty requests wearing the units of a rate. No token telemetry
exists for this profile, so the token unit cost is **null rather than zero**.

The amount itself is unchanged by either. An allocation does not depend on traffic,
which is the property that makes it computable here and the property that makes it
useless as an efficiency measure.

## What nobody reserved

```text
0.400000 - 0.125000 = 0.275000
```

| Line | Amount | Share |
|---|---|---|
| `example-cost-0001` | 0.100000 | 0.250000 |
| `example-cost-0002` | 0.025000 | 0.062500 |
| Unreserved capacity | 0.275000 | 0.687500 |
| **Node total** | **0.400000** | 1 |

Sixty-nine per cent of the machine was reserved by nobody, and it is the largest
number on the page. Spreading it across the two workloads would have raised the
first workload's amount from 0.100000 to 0.320000, and its cost per thousand requests
with it, without anything about that workload changing; discarding it would have left the two
workload lines summing to 0.125000 against a machine costing 0.400000, with nothing
to name the gap.

The three lines close against the node exactly, and a test requires them to.

## The prerequisite line

| Resource | Claim | Amount | Attributed to |
|---|---|---|---|
| Model cache claim | 5.000000 gibibytes | 0.000500 USD | the prerequisite layer |

```text
5.000000 x 1.000000 x 0.000100 = 0.000500
```

The model cache outlives every release that mounts it, deliberately, so that
uninstalling does not force a re-download over a transport whose downloader does not
validate certificates. Its cost therefore belongs to the environment's prerequisite
layer and to no workload: charging it to a workload would make deleting that workload
look like a saving that does not occur, because the claim would still be there.

```text
0.400000 + 0.000500 = 0.400500
```

The environment costs 0.400500 for the hour. The node accounts for 0.400000 of it and
the prerequisite claim for the rest.

## What this example is not

- It is **not a measurement**. No request was served, no token was generated, and no
  quantity here was read from a running system.
- It is **not a price**. Every rate is invented, so the confidence of both records is
  `none` and no amount here may be read as what anything costs.
- It is **not a bill**. Neither record is `actual`, neither references an invoice, and
  a test fails if either uses the vocabulary of one.
- It is **not a throughput figure**, and the traffic counts must not be extracted as
  one. They exist to give two divisions a denominator; publishing them as a rate would
  cross [the project boundary](../architecture/project-boundaries.md) that forbids V1
  publishing any throughput figure.
