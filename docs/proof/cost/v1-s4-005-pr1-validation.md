# V1-S4-005-PR1 — change validation: the V1 cost calculation

Date: 2026-09-15

Classification: **local static evidence** for the change, and **synthetic** evidence for
every figure in it. Every result below comes from reading files in this repository and
running the checks over them. No cluster was contacted, no model was loaded, no request
was served, no price was retrieved from anywhere, and **no cost record was calculated
from measured evidence**. The two committed calculation fixtures are synthetic, priced
from the synthetic rate card, and have confidence `none`.

Claim boundary: `tools/cost_calculation` applies the cost method as ADR 0007 and ADR 0014
decide to the inputs its suite gives it, and refuses the inputs its suite names; its two
fixtures regenerate byte for byte, and their figures match values worked out by hand; the
method data, its documents, and the indexes that described it agree with the amendment.

**What this record does not establish.** What anything costs. Whether a usage value in a
calculation input matches the evidence it names: every usage value is typed in by hand,
and ADR 0014 D3's rules for taking one from committed samples are review only. Anything
about the `V1-S4-004` run, which no calculation here reads.

## The conflict this change had to resolve

The story asks for an hourly figure and a cost-per-request figure on the **estimate**
basis, with the invoice and allocation bases unreachable. ADR 0007 D1, as accepted, said
the reverse: `allocated` was the only reachable basis, and `estimated` was unreachable
because no utilisation had been measured. Implementing the story as written would have
changed an accepted decision without recording it.

The work stopped and the choice was put to the maintainer, with three options: follow
ADR 0007 as accepted and record the mismatch; amend ADR 0007 so that `estimated` is the
only basis V1 calculates; or amend it so that both bases are calculated. The
recommendation was the first, as the smaller change. **The maintainer chose the second.**
[ADR 0014](../../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md)
records it as a governed amendment, on the ground that `V1-S4-004` committed measured
processor and memory use of a declared local experiment, which is the condition ADR 0007
D1 and D2 named for reaching `estimated`.

## What this change publishes

- **[ADR 0014](../../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md)**,
  amending ADR 0007 D1, D2, and D9. ADR 0007's text is kept as accepted, with pointers.
- **[`tools/cost_calculation`](../../../tools/cost_calculation/)**, with `calculate` and
  `verify`. It reads one `CostCalculationInput` and the committed method, and writes a
  `CostCalculationResult` whose records it validates against the method's record shape
  and whose lines it checks close against the node.
- **[The calculation guide](../../cost/cost-calculation.md)**: what it computes, the
  input, what it refuses, what is still supplied by hand, and the fixtures.
- **Two synthetic fixtures** under
  [`tests/cost/fixtures/cost-calculation/`](../../../tests/cost/fixtures/cost-calculation/):
  `estimate-closes`, one hour and two workloads that close against the node, and
  `estimate-incomplete`, half an hour with a missing memory integral.
- **[`tests/cost/test_cost_calculation.py`](../../../tests/cost/test_cost_calculation.py)**,
  32 test functions, 108 tests.

## The formula

For each workload, on a window of `h` hours:

```text
amount            = (cpuSeconds * cpuRate + memoryByteSeconds / 2^30 * memoryRate
                     + acceleratorSeconds * deviceRate) / 3600
                    (device term absent when no device is reserved)
amountPerHour     = amount / h
costPer1kRequests = amount / requests * 1000        (null below 100 requests)
costPer1MTokens   = amount / (input + output) * 1e6  (null below 10,000 tokens)
share             = amount / nodeCapacityAmount
nodeCapacity      = (cores * cpuRate + GiB * memoryRate + devices * deviceRate) * h
unallocated       = published nodeCapacity - sum(published workload amounts)
```

Every value is exact until it is published, then rounded once, half-even, to six places.

## What changed elsewhere

- **The method data** ([`cost-method.v1alpha1.json`](../../cost/cost-method.v1alpha1.json)):
  `estimated` is the only reachable basis; `observed-utilisation-share` is selected and
  `requested-resource-share` deferred; processor seconds, memory byte-seconds, requests,
  input tokens, and output tokens are obtainable by hand from a bounded experiment; the
  cost-record identifier is declared by an input; `computationStatus` says a repository
  tool computes a record and `publishedCostFigures` is 0; an estimated-amount output and
  an hourly output are added; the record shape gains the rate card's version and
  effective date, the confidence facts, and the usage evidence class, and its amount is
  nullable; five rules are added, each enforced by a test (nineteen in all, two by review);
  one limitation is replaced and two added (fourteen in all); two telemetry gaps and the
  ownership question are restated. The rate card and the worked example's figures are
  unchanged. The file's inline formatting is preserved.
- **[The method document](../../cost/cost-method.md)**, the
  [cost README](../../cost/README.md), and the
  [worked example's](../../cost/worked-example.md) framing follow the data. The worked
  example now says it demonstrates a basis V1 no longer produces.
- **[`tests/cost/test_cost_method.py`](../../../tests/cost/test_cost_method.py)**: four
  tests that pinned the old decisions now pin the amended ones — the reachable basis, the
  selected method, the usage inputs marked obtainable, and the computation status. The
  rule-to-test check also looks in the calculation suite, and the limitation check looks
  for "no platform component computes" and "typed in by hand".
- **Statements that nothing computes a cost record** were corrected where they were
  unqualified: the telemetry catalog's two cost deferral reasons in its data and
  document, the dashboard document's row, the contracts README, the claim matrix, the
  architecture index, the README, and CONTRIBUTING. ADR 0006 gains a parenthetical
  pointer. Statements that **no platform component** computes or emits one are still
  true and were left, including the generated dashboard and correlation-query data.
- **[The test inventory](../../testing/test-inventory.md)** and its data list the new
  module against the existing cost claim; the documentation layer goes from twenty-eight
  modules to twenty-nine. The count of modules defending no claim is unchanged.
- The CHANGELOG and [the proof index](../README.md) point here.

No file under `src/`, `charts/`, `deploy/`, `infra/`, `scripts/`, or `contracts/` changed.
No claim row, lane, layer, or evidence class changed.

## Checks run on the change

Every command ran from the repository root in Git Bash, inside the locked environment
(`uv run --locked ...`), with nothing contacted.

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.12` |
| `pytest` | `8.4.2` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |

```text
python -m pytest tests/cost -q                                            418 passed
python -m pytest tests/cost/test_cost_calculation.py -q                   108 passed
python -m pytest -q                                                       9214 passed, 31 skipped, 14 deselected
python -m pytest tests/testing/test_document_links.py tests/testing/test_test_inventory.py tests/cost -q
                                                                          1381 passed (rerun after this record existed; the lane above started before it did)
ruff format --check .                                                     407 files already formatted
ruff check .                                                              All checks passed!
python -m mypy                                                            Success: no issues found in 227 source files
python -m tools.cost_calculation verify --input tests/cost/fixtures/cost-calculation/estimate-closes.input.json --result tests/cost/fixtures/cost-calculation/estimate-closes.result.json
                                                                          ok  the committed result regenerates from its input and the committed method
python -m tools.cost_calculation verify --input tests/cost/fixtures/cost-calculation/estimate-incomplete.input.json --result tests/cost/fixtures/cost-calculation/estimate-incomplete.result.json
                                                                          ok  the committed result regenerates from its input and the committed method
git diff --check                                                          (no output)
```

**Private-information inspection of the diff.** Every added line was searched for drive
paths, user or home directories, IPv4 addresses, e-mail addresses, host names, kubeconfig
references, and names from outside this repository. Three matches, each deliberate: a
`https://example.invalid` URL and a `C:\work\owner` value that tests use to prove the tool
refuses them, and the tool's own URL check.

## What was not run, and why

| Not run | Why |
|---|---|
| A calculation over the `V1-S4-004` evidence | No reader takes usage from committed samples, and a baseline result belongs to the next change |
| A reader integrating cgroup samples under ADR 0014 D3 | Not in this change's scope; D3's integration rules are recorded as review only |
| Any cluster, model, or load run | Nothing here needs one, and none was authorized |
| A provider rate card | ADR 0007 D12 is not decided; the only card is synthetic |
| A dashboard or query hook for cost | Not in this change's scope; nothing emits a cost record to query |

## Acceptance criteria for this change

| Criterion | Status |
|---|---|
| An hourly figure and a cost-per-request figure, on the estimate basis only | **Met, by amendment.** `derived.amountPerHour` and `derived.costPerThousandRequests` on `estimated` records; `actual` and `allocated` are refused. ADR 0007 D1 as accepted said the opposite, and ADR 0014 amends it at the maintainer's choice. The per-request figure is quoted per thousand, as ADR 0014 D6 explains |
| The record validates against the output shape published with the cost method, not a contract | **Met and tested.** Every record is validated against `recordShape.fields`; no schema is added under `contracts/` |
| The price source is synthetic, versioned, dated, and says so in its own contents; no cost figure is published | **Met and tested** for the source. No figure is published: the fixtures are synthetic and every result carries `publishedCostFigure: false` and its boundary; publication is still review only |
| Estimate, allocation, and invoice values cannot be confused; a missing input is null with a reason, not zero | **Met and tested.** One basis per calculation, billing vocabulary refused in every record, null and reason checked in both directions |
| Price source and version, time window, idle and shared treatment, and confidence are explicit | **Met.** Each record names the card, version, and date; the result names the window, the residual treatment, the unallocated line's meaning, and the prerequisite attribution; confidence is derived from carried facts |
| Deterministic fixtures | **Met.** Two committed synthetic fixtures regenerate byte for byte |

For the parent story, the baseline result, the published confidence and limitations for
it, and the dashboard or query hook remain for the next change.

## Inputs still supplied manually

Processor seconds, memory byte-seconds, requests, and tokens; node allocatable capacity;
each workload's reservation, replicas, and presence; the window; and the evidence class.
The tool checks their shape and that measured use fits the node. It cannot check them
against evidence.

## Limitations and risks

- **Hand-typed usage.** A wrong number typed in with a measured class produces a record
  that says its utilisation was measured. The class is checked; the number is not.
- **The integration rules are unexecuted.** How processor seconds and memory byte-seconds
  are taken from samples is written in ADR 0014 D3 and applied by nothing.
- **A working set and a cgroup counter** measure what the kernel charged the container,
  including file-backed pages and every thread, not what a request needed.
- **Idle reservations move to the unallocated line.** The estimated basis does not charge
  them to the workload that reserved them, by design.
- **The fixtures are the only records.** They exercise the arithmetic, the refusals, and
  the null path. They are not a sample of anything.
