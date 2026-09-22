# Cost

Status: the method is accepted in
[ADR 0007](../architecture/decisions/ADR-0007-inference-cost-method.md) and amended
by [ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md), and a repository tool calculates it
by hand. No platform component computes a cost record, no invoice has ever been read,
and the only rate card committed here is synthetic.

A cost model is easy to build and hard to keep honest. The failure is not arithmetic
— it is that a number produced by applying an invented rate to a declared
reservation, on a machine nobody was charged for, ends up in a sentence beginning
"running this costs". Nothing in the number itself resists that. The separation has
to be structural.

So every amount here carries a basis, and the basis says whether an invoice was
involved. Every unit cost carries the count it was divided by. Confidence is the
lowest ceiling among the rules that apply to a record's own inputs, recomputed rather
than typed — and because the only rate card is synthetic, every figure this project
can produce today lands on `none`.

## Documents

| Document | What it covers |
|---|---|
| [The cost method](cost-method.md) | Basis, allocation, idle and shared cost, windows, prices, units and precision, missing data, confidence, inputs, outputs, the record shape, and the rules |
| [A worked synthetic example](worked-example.md) | One hour, one node, two workloads, and the residual, on the allocated basis, with every figure recomputed by the suite |
| [The cost calculation](cost-calculation.md) | `tools/cost_calculation`: the estimated basis applied to one declared input, what it refuses, what is still typed by hand, and two synthetic fixtures |
| [The V1 cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md) | `tools/cost_baseline`: use taken from the `V1-S4-004` samples, two estimated records at synthetic prices, and how far to trust them |
| [`cost-method.v1alpha1.json`](cost-method.v1alpha1.json) | The authoritative form of both, validated by [`tests/cost/`](../../tests/cost/) |
| [The V1 cost and capacity method](cost-capacity-method.md) | How V1 turns measured use into an estimate and how far that estimate, and the load behind it, says anything about capacity: billing against estimate against allocation, the formula, the price basis, inputs and window, idle and shared cost, outputs and the record shape, the link to the measured run, confidence, exclusions, dashboard hooks, and the capacity questions V1 defers, with what is implemented kept apart from what is not |
| [`cost-capacity-method.v1alpha1.json`](cost-capacity-method.v1alpha1.json) | The authoritative form of that method, checked against the cost method, the claim register, the workflow, and the committed results its figures are read from by [`tests/testing/test_published_methods.py`](../../tests/testing/test_published_methods.py) |
| [The telemetry catalog](../telemetry/telemetry-catalog.md) | Where every usage input would come from, and which ones have no source |

## The short version

Three bases exist and V1 calculates one. `actual` needs an invoice this project has
never received. `allocated` is specified and demonstrated by the worked example, and a
V1 calculation does not produce it, so that an allocation and an estimate of one window
never sit side by side. `estimated` prices what a workload was measured using, and since
the `V1-S4-004` scenario matrix committed measured processor and memory use, it is the
one V1 calculates. Usage is typed into an input by hand, or taken from committed samples
by `tools/cost_baseline`, which produced the baseline's two records.

Capacity no workload in a calculation was measured using is reported as its own line
rather than spread or dropped, and the workload lines plus that line are required to
close against the machine exactly. What each workload reserved is carried beside its
measured use and never priced.

## Running the checks

```sh
python -m pytest tests/cost -q
```

It reads only files in this repository and needs `pytest` alone. Every figure in the
worked example is recomputed in exact decimal from the declared inputs and rates, so
a number typed into a document that the arithmetic does not produce is a failing
test. The calculation's fixtures regenerate byte for byte, and their figures are held
to values worked out by hand.

## What is not here

No platform component that computes or emits a cost record, no schema for one under
[`contracts/`](../../contracts/README.md), no provider rate card, no invoice, no usage
read from a running system, no dashboard or query over cost, and no figure for what
running an inference workload costs. The last of those is a boundary
rather than a gap: ADR 0007 D11 publishes the method and synthetic examples and no cost
figure, and [ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md),
which allows a bounded traffic figure, leaves that decision untouched.
