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
calculation input matches the committed record a measured input names: every usage value
is typed in by hand, the tool checks only that the record exists, matches its digest, and
declares the class claimed, and ADR 0014 D3's rules for taking a value from committed
samples are review only. Anything
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
  34 test functions, 124 tests.

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
  input tokens, and output tokens are obtainable by hand from a bounded experiment, and
  processor seconds and memory byte-seconds name no catalog signal; the cost-record
  identifier is declared by an input; `computationStatus` says a repository tool computes
  a record, with 3 synthetic records, 0 measured records, and 0 published figures; an
  estimated-amount output and an hourly output are added and three output questions
  reworded; the record shape gains the rate card's version and effective date, the
  confidence facts, and the usage evidence class, and its amount is nullable; five rules
  are added, each enforced by a test (nineteen in all, two by review), and one review
  rule's rationale gains a sentence; one limitation is replaced, two are added, and two
  are rewritten (fourteen in all); all three telemetry gaps and the ownership question are
  restated; the description is corrected. The rates and the worked example's figures are
  unchanged; the synthetic rate card's `scope` now names the calculation fixtures. The
  file's inline formatting is preserved.
- **[The method document](../../cost/cost-method.md)**, the
  [cost README](../../cost/README.md), and the
  [worked example's](../../cost/worked-example.md) framing follow the data. The worked
  example now says it demonstrates a basis V1 no longer produces.
- **[`tests/cost/test_cost_method.py`](../../../tests/cost/test_cost_method.py)**: four
  tests that pinned the old decisions now pin the amended ones — the reachable basis, the
  selected method, the usage inputs marked obtainable, and the computation status, whose
  synthetic record count is now counted from the fixtures. The rule-to-test check also
  looks in the calculation suite, and the limitation check looks for "no platform
  component computes" and "typed in by hand".
- **Statements that nothing computes a cost record** were corrected where they were
  unqualified: the telemetry catalog's two cost deferral reasons in its data and
  document, the dashboard document's row, the contracts README, the claim matrix, the
  architecture index, the README, and CONTRIBUTING. ADR 0006 gains a parenthetical
  pointer. "No component computes or emits a cost record" in the correlation queries'
  document and data and in the dashboard record now says "no platform component"; the
  generated Grafana dashboard does not carry that text and is unchanged.
- **[The test inventory](../../testing/test-inventory.md)** and its data list the new
  module against the existing cost claim; the documentation layer goes from twenty-eight
  modules to twenty-nine. The count of modules defending no claim is unchanged.
- The CHANGELOG and [the proof index](../README.md) point here.

ADR 0007 gains pointers beside D1, D2, D3, D9, and D13, and the architecture index's
0007 summary notes that ADR 0013 narrowed the throughput rule it describes.

No file under `src/`, `charts/`, `deploy/`, `infra/`, `scripts/`, or `contracts/` changed.
No claim row, lane, layer, or evidence class changed.

## Checks run on the change

Every command ran from the repository root in Git Bash, inside the locked environment
(`uv run --locked ...`), with nothing contacted, on the tree after the review changes
and with this record in place.

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
python -m pytest tests/cost -q                                            434 passed
python -m pytest tests/cost/test_cost_calculation.py -q                   124 passed
python -m pytest -q                                                       9233 passed, 1 failed, 31 skipped, 14 deselected
python -m pytest tests/security/test_security_baseline.py tests/cost -q   1185 passed, after the fix below
ruff format --check .                                                     408 files already formatted
ruff check .                                                              All checks passed!
python -m mypy                                                            Success: no issues found in 227 source files
python -m tools.cost_calculation verify --input tests/cost/fixtures/cost-calculation/estimate-closes.input.json --result tests/cost/fixtures/cost-calculation/estimate-closes.result.json
                                                                          ok  the committed result regenerates from its input and the committed method
python -m tools.cost_calculation verify --input tests/cost/fixtures/cost-calculation/estimate-incomplete.input.json --result tests/cost/fixtures/cost-calculation/estimate-incomplete.result.json
                                                                          ok  the committed result regenerates from its input and the committed method
python -m tools.inference_dashboard                                       ok  29 panel(s) satisfy the dashboard policy
git diff --check                                                          (no output)
```

The one lane failure was this change's own: a refusal test used a home-directory path with a user segment, which
the security baseline refuses as a personal path even in a test sample. The sample is
now `/home/x`, which the calculation still refuses and the baseline does not flag, and
the two affected modules then passed.

The first commit's own runs recorded 418 passed for the cost suite, 108 for the new
module, and a lane of 9214 passed, 31 skipped, and 14 deselected. That lane started
before this record existed, and so did a rerun of the link, inventory, and cost suites
this record then described as run "after this record existed" (1381 passed); the
formatter count, 407, was also taken before it. Review reran them on the committed tree:
1382, 408 files, and a lane of 9218 passed. The corrected runs are the ones above.

**Private-information inspection of the diff.** Every added line was searched for drive
paths, user or home directories, IPv4 addresses, e-mail addresses, host names, kubeconfig
references, and names from outside this repository. The only matches are deliberate:
`https://example.invalid`, `C:\work\owner`, `/home/x`, and `10.1.2.3`, which tests
use to prove the tool refuses them, and the tool's own URL check. A measured test input
names a committed record under `docs/proof/serving/` by repository-relative path.

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
each workload's reservation, replicas, and presence; the window; the evidence class; and,
for a measured class, the committed record's path and digest. The tool checks their
shape, that measured use and reserved devices fit the node, and that a named record
exists, matches, and declares the class. It cannot check the values against that record.

## Limitations and risks

- **Hand-typed usage.** A wrong number typed in with a measured class and a real record
  produces a record that says its utilisation was measured. The class is checked against
  the named record; the number is not checked against anything but the node's capacity.
- **The integration rules are unexecuted.** How processor seconds and memory byte-seconds
  are taken from samples is written in ADR 0014 D3 and applied by nothing.
- **A working set and a cgroup counter** measure what the kernel charged the pod,
  including file-backed pages and every thread, not what a request needed.
- **Idle reservations move to the unallocated line.** The estimated basis does not charge
  them to the workload that reserved them, by design.
- **The fixtures are the only records.** They exercise the arithmetic, the refusals, and
  the null path. They are not a sample of anything.

## Independent review, and what it changed

The first commit was reviewed before push by three independent reviewers: one for the
tool's and the tests' code, one for every number and claim against the committed files,
recomputed, and one for scope, ADR governance, cost semantics, and leakage. Each finding
below was checked before it was acted on. **No leakage was found**, nothing was out of
scope, and every figure in the fixtures and the calculation guide was recomputed by hand
and matched.

**What the first commit got wrong in the code.**

- **Device use was never bounded by the node.** ADR 0014 D4, the calculation guide, the
  CHANGELOG, CONTRIBUTING, and the inventory all said measured use beyond the node's
  capacity is refused. Only processor and memory were checked. A workload reserving a
  device on a node declaring none, reporting 99,999,999 device seconds, was accepted. The
  tool now refuses device seconds beyond capacity per workload and in total, and devices
  reserved across replicas beyond the node's, with tests.
- **Measured utilisation rested on a class the preparer typed.** Setting
  `classification` to `local-real-cpu` made synthetic numbers "measured", which is the
  asserted confidence ADR 0014's own criteria refuse. A measured class must now name a
  committed record under `docs/proof/` by path and LF-normalized SHA-256, and that record
  must declare the same class. This establishes that the evidence exists and is of that
  class, and still not that the typed values match it; the documents say so.
- **`hasMeasuredUtilisation` depended on the accelerator term.** A workload with measured
  processor and memory use and a reserved device whose seconds were unavailable was
  marked unmeasured, against ADR 0014 D3. It now depends on processor and memory only.
- **A CPU-only record reported missing telemetry.** With no device reserved, the tool
  demanded a reason for null accelerator seconds, so every complete record listed
  `no-telemetry-source`. ADR 0014 D4 said the term is absent, not missing. Device seconds
  are now not applicable when no device is reserved: null, no reason, not listed. Both
  fixtures regenerate; no amount changed.
- **Smaller:** `check_record` accepted any non-empty string as an instant; the method's
  rule that a one-hour window starts on the hour was not applied. Both now are, tested.

**What the first commit got wrong in the method data and the documents.**

- **The method data still said "Nothing in this repository computes a cost record"** in
  its own description, while its computation status said a tool does. Three output
  questions still spoke of reservation, and a gap said the API emits the readiness gauge,
  which it does not.
- **Processor seconds and memory byte-seconds still named the catalog's process metrics**,
  so ADR 0007 D9's signal comparison passed on signals that never supply them. They now
  name no catalog signal.
- **ADR 0014 misquoted ADR 0007.** It put in quotation marks a sentence from the method
  data that this change deleted, attributed an honest cost to ADR 0007's text that exists
  only in the data, and a limitation did the same for D2. Each now cites what is there.
- **ADR 0014 understated what it amends.** It said ADR 0007 D3 and D13 were unchanged. D3's
  line now means capacity no workload was measured using, and D13's "No component computes
  one" is no longer literally true. Both are now declared as amended and clarified, with
  pointers in ADR 0007.
- **"The container's cgroup counter" was wrong.** The committed samples are per pod.
  ADR 0014 also said they are "on one clock"; each carries the host's and the node's.
- **The computation status swapped a count for a zero.** `costRecordsProduced` became
  `publishedCostFigures: 0`, avoiding a true non-zero count. The status now also carries
  3 synthetic records, counted from the fixtures by a test, and 0 measured.
- **The privacy refusal was described as "network addresses"**; it recognizes IPv4 only.
  The published shares of a fixture add to a millionth over one while its table showed
  the node at 1, and an hourly figure over a short window reads as a run rate; both are
  now stated. The architecture index still said a cost-per-request figure is barred by the
  throughput rule without noting ADR 0013. The correlation queries and dashboard record
  still said "No component computes or emits", which this record had said was left only
  where it read "no platform component".

**What the first commit got wrong in this record and its message.** The counts it gave for
the formatter, the rerun suites, and the lane were taken before this record existed, and
the rerun was described as coming after it; the rate card was called unchanged though its
`scope` changed; two rewritten limitations were not mentioned. The first commit's message
repeats the 9214 lane figure. Commit messages are not rewritten; this is the correction.

**Not changed.** The restated acceptance criteria stay in the table, as earlier proof
records carry them. The integration rules in ADR 0014 D3 stay review only. No reader of
committed samples was added; that and the baseline belong to the next change.
