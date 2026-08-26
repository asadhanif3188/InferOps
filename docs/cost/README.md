# Cost

Status: entry point established; the method is accepted in
[ADR 0007](../architecture/decisions/ADR-0007-inference-cost-method.md). Nothing in
this repository computes a cost record, no invoice has ever been read, and the only
rate card committed here is synthetic.

A cost model is easy to build and hard to keep honest. The failure is not arithmetic
— it is that a number produced by applying an invented rate to a declared
reservation, on a machine nobody was charged for, ends up in a sentence beginning
"running this costs". Nothing in the number itself resists that. The separation has
to be structural.

So every amount here carries a basis, and the basis says whether an invoice was
involved. Every unit cost carries the count it was divided by. Confidence is the
lowest ceiling among the rules that apply to a record's own inputs, recomputed rather
than typed — and because the reachable basis is an allocation and the only rate card
is synthetic, every figure this project can produce today lands on `none`.

## Documents

| Document | What it covers |
|---|---|
| [The cost method](cost-method.md) | Basis, allocation, idle and shared cost, windows, prices, units and precision, missing data, confidence, inputs, outputs, the record shape, and the rules |
| [A worked synthetic example](worked-example.md) | One hour, one node, two workloads, and the residual, with every figure recomputed by the suite |
| [`cost-method.v1alpha1.json`](cost-method.v1alpha1.json) | The authoritative form of both, validated by [`tests/cost/`](../../tests/cost/) |
| [The telemetry catalog](../telemetry/telemetry-catalog.md) | Where every usage input would come from, and which ones have no source |

## The short version

Three bases exist and V1 can reach one. `actual` needs an invoice this project has
never received; `estimated` needs utilisation telemetry that no component emits and
no collector reads; `allocated` needs a rate card and a validated workload document,
which is why it is the only one available.

Allocation is by what a workload reserved, not by what it used, because reserved
capacity is what the scheduler withholds from everything else and because it is the
only quantity that can be obtained from a document. Capacity nobody reserved is
reported as its own line rather than spread or dropped, and the workload lines plus
that residual are required to close against the machine exactly.

## Running the checks

```sh
python -m pytest tests/cost -q
```

It reads only files in this repository and needs `pytest` alone. Every figure in the
worked example is recomputed in exact decimal from the declared inputs and rates, so
a number typed into a document that the arithmetic does not produce is a failing
test.

## What is not here

No component that computes a cost record, no schema for one under
[`contracts/`](../../contracts/README.md), no provider rate card, no invoice, no
utilisation measurement, and no figure for what running an inference workload costs.
The last of those is a boundary rather than a gap: a cost per thousand requests is an
hourly reservation divided by an hour of traffic, and
[the project boundaries](../architecture/project-boundaries.md) forbid V1 publishing
a throughput figure.
