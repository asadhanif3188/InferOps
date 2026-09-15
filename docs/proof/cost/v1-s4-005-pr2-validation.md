# V1-S4-005-PR2 — change validation: the V1 cost baseline

Date: 2026-09-15

Classification: **local static evidence** for the change. The use in
[the baseline](v1-s4-005-pr2-cost-baseline.md) is **local real CPU** evidence taken from
files `V1-S4-004-PR1` committed; every price in it is **synthetic**. This change sent no
load, installed nothing, contacted no cluster, loaded no model, and retrieved no price.

Claim boundary: `tools/cost_baseline` applies ADR 0014 D3 to the committed `V1-S4-004`
performance record's samples and raw records, refuses the evidence its suite names, and
writes inputs from which the unchanged `tools/cost_calculation` produces two estimated
records; all five committed files regenerate byte for byte; every usage value and
published figure is recomputed by a second route; the baseline report quotes only figures
the results hold; and the documents that said no reader exists say what is now true.

**What this record does not establish.** What anything costs. That the baseline's
attribution of the collector to the unallocated line is the only defensible one. Anything
about another host, release, prompt, or load.

## What this change publishes

- **[The V1 cost baseline](v1-s4-005-pr2-cost-baseline.md)**: the two records, the price
  source, version, and date, the basis and allocation method, the windows, the attribution,
  what the unallocated line holds, the excluded costs, how to read the hourly figure and
  the cost per thousand requests, confidence, uncertainty, limitations, and why no
  dashboard or query hook is added.
- **[`tools/cost_baseline`](../../../tools/cost_baseline/)**, with `derive` and `verify`.
  It reads a performance record through `tools.performance_findings.checked_record`, which
  refuses one that does not regenerate from its inputs, and adds its own refusals: an
  evidence class other than `local-real-cpu`, a failed check, samples that are not the
  ones the record names, and a values file whose digest is not the one the experiment
  executed.
- **Five committed files** under `docs/proof/cost/`: an input and a result for each run,
  and [the derivation record](v1-s4-005-pr2-baseline-derivation.v1alpha1.json).
- **[`tests/cost/test_cost_baseline.py`](../../../tests/cost/test_cost_baseline.py)**,
  43 test functions, 56 tests.

## The independent check of the calculation

The calculation is checked three ways, none of which calls the functions it checks:

1. **Usage, from the committed lines.** For each run it finds the bounding samples in the
   JSONL itself, sums the API and runtime counter increases as integers, and sums
   `elapsed ms × (reading + next reading)` as integers before dividing by 2,000. Both equal
   the input's values exactly. Requests and tokens are counted from the raw record lines and
   from the performance record's phase summaries, and agree with both.
2. **Figures, in `Decimal`.** From those usage values and rates written into the test by
   hand, it recomputes the amount, the hourly figure, the cost per thousand requests, the
   share, the node's amount, the unallocated line, and the window's hours, rounding
   half-even, and each equals the published six-place string.
3. **Against the performance record.** The runtime's average over each window, 5,929 and
   5,902 millicores, is compared with the figures the performance record computed
   independently for each phase from the samples inside it, 5,944 to 5,993 and 5,952 to
   5,994. The window sits just below the phases because it opens a couple of seconds
   before the load. The suite requires it within 1% of the lowest phase and no higher
   than the highest.

The derivation record's unallocated use also closes: capacity equals the workload, the
collector, the node outside the release, and idle, to the nanosecond and the byte, and
priced at the card it reproduces the published unallocated line to within the two
roundings the method allows.

A hand check of run 1, for a reader without the suite:

```text
1952.1241704 × 0.040000                    = 78.084966816
188050670049.28 ÷ 2^30 × 0.005000          =  0.875679...
(78.084966816 + 0.875679...) ÷ 3600        =  0.0219335...   → 0.021934
0.0219335... ÷ (328.754 ÷ 3600)            =  0.240182
0.0219335... ÷ 183 × 1000                  =  0.119855
(12 × 0.040000 + 9.716056... × 0.005000) × 328.754 ÷ 3600 = 0.048270
0.048270 − 0.021934                        =  0.026336
```

## What changed elsewhere

- **The method data** ([`cost-method.v1alpha1.json`](../../cost/cost-method.v1alpha1.json)):
  `computationStatus.measuredRecordsProduced` goes from 0 to 2 and its meaning names
  `tools/cost_baseline`; the coverage notes of processor seconds, memory byte-seconds,
  requests, input tokens, and output tokens, two telemetry gap consequences, and the
  limitations `no-utilisation-source` and `measured-use-is-typed-in-by-hand` say usage is
  typed in by hand or taken from committed samples by that tool. No rule, rate, input,
  output, or decision changed, and the file's inline formatting is preserved.
- **[`tests/cost/test_cost_method.py`](../../../tests/cost/test_cost_method.py)**: the
  computation-status test no longer pins the measured count at 0; it counts the records of
  every committed result under `docs/proof/`, as it already counted the synthetic fixtures.
- **[ADR 0014](../../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md)**:
  D3's status row now says the integration half is enforced for inputs the reader writes
  and review only for a typed input, and names the suite. Dated implementation notes are
  added after the summary, D3's enforcement paragraph, the evidence, and the hand-typed
  risk. No decision's text changed, and the accepted paragraphs are kept as accepted.
  [ADR 0007](../../architecture/decisions/ADR-0007-inference-cost-method.md) gains dated
  implementation notes after its amendment summary and its D9 pointer.
- **[The calculation guide](../../cost/cost-calculation.md)**, [the method
  document](../../cost/cost-method.md), and [the cost README](../../cost/README.md) stop
  saying that every usage value is typed in by hand, that no reader exists, and that no
  calculation has run over measured evidence. The guide's supplied-by-hand table gains a
  column for inputs the reader writes.
- **Indexes**: the README, CONTRIBUTING (which gains the baseline's `verify` command), the
  architecture index's 0014 row, the claim matrix's cost paragraph, [the proof
  index](../README.md), the CHANGELOG, and [the test inventory](../../testing/test-inventory.md)
  and its data, whose documentation layer goes from twenty-nine modules to thirty against
  the existing cost claim. The count of modules defending no claim is unchanged.

No file under `src/`, `charts/`, `deploy/`, `infra/`, `scripts/`, or `contracts/` changed.
`tools/cost_calculation`, `tools/performance_findings`, `tools/performance_scenarios`, and
`tools/llm_load` are unchanged, and so is every `V1-S4-004` file. No claim row, lane, layer,
evidence class, or telemetry signal changed.

## Checks run on the change

Every command ran from the repository root in Git Bash, inside the locked environment
(`uv run --locked ...`), with nothing contacted, on the tree with this record in place.

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
python -m pytest -q                                                       9303 passed, 31 skipped, 14 deselected
python -m pytest tests/cost -q                                            490 passed
python -m pytest tests/cost/test_cost_baseline.py -q                      56 passed
ruff format --check .                                                     414 files already formatted
ruff check .                                                              All checks passed!
python -m mypy                                                            Success: no issues found in 231 source files
python -m tools.cost_baseline verify --record-dir docs/proof/serving --record-prefix v1-s4-004-pr1- --dir docs/proof/cost --prefix v1-s4-005-pr2-
                                                                          ok  5 committed baseline file(s) regenerate from a record that regenerates from its inputs
python -m tools.cost_calculation verify --input docs/proof/cost/v1-s4-005-pr2-baseline-run-1.input.json --result docs/proof/cost/v1-s4-005-pr2-baseline-run-1.result.json
                                                                          ok  the committed result regenerates from its input and the committed method
python -m tools.cost_calculation verify --input docs/proof/cost/v1-s4-005-pr2-baseline-run-2.input.json --result docs/proof/cost/v1-s4-005-pr2-baseline-run-2.result.json
                                                                          ok  the committed result regenerates from its input and the committed method
python -m tools.cost_calculation verify (both PR1 fixtures)               ok  both regenerate, unchanged
python -m tools.performance_findings verify --dir docs/proof/serving --record-prefix v1-s4-004-pr1- --findings docs/proof/serving/v1-s4-004-pr2-findings.v1alpha1.json
                                                                          ok  the committed findings regenerate
python -m tools.inference_dashboard                                       ok  29 panel(s) satisfy the dashboard policy
git diff --check                                                          (no output)
```

**Private-information inspection of the diff.** Every added line was searched for drive paths, user or home directories, IPv4 addresses, e-mail addresses, host and node names, pod names and UIDs, kubeconfig references, local image references, and names from outside this repository. Nothing matched except `@pytest.mark` decorators, which the e-mail pattern catches. The baseline's committed files name the performance record by repository-relative path, and carry none of the node name, pod names, or pod UIDs the `V1-S4-004` environment record holds.

## Independent review, and what it changed

The first commit was reviewed before push by three independent reviewers: one for the
tool's and the tests' code, one for every number and claim, recomputed from the raw
sample, raw record, and performance record files rather than from the tool's output, and
one for scope, ADR governance, cost semantics, and leakage. Each finding below was
checked before it was acted on. **No leakage was found**, no product file was touched,
and every headline figure in the baseline, every table value, and every line of the hand
check recomputed correctly.

**What the first commit got wrong in the report.**

- **The idle baseline was said to lie outside both windows.** Run 1's window opens on a
  sample 1,307 ms before its load generator launched, so it holds the last 1,057 ms of
  the idle baseline. The excluded-costs list and the hourly figure's "busy for the whole
  window" now say so.
- **A real rate card was said to raise confidence to `medium`.** A card's class caps it:
  an amortised-hardware card, the kind a local host would have, allows `low`, and only a
  provider list price or negotiated price reaches `medium`. The same error was in this
  record's deferred work. The confidence paragraph also named three of the six rules and
  called the synthetic card's "the only rule that binds", though the invoice rule holds
  too; it now names both rules that hold and why the others do not.
- **It set a priced reservation beside the estimate.** "Larger than a price on the
  reservation would have been; an allocation would have understated this workload's use
  about fivefold" is the side-by-side reading ADR 0014 D1 exists to prevent, though no
  amount was printed. The comparison is now in core-hours only, and a test refuses the
  wording.
- **"No cost figure is published" was asserted, not argued.** These are the first records
  combining measured use and published traffic with a price. A section now says why they
  are consistent with ADR 0007 D11: the divisor is public under ADR 0013, and the prices
  are invented and confidence is `none`. It also says the reading is the record's, not a
  decision's.
- **The collector's attribution was presented as the method's rule.** It is a choice: the
  collector is Helm-owned and release-scoped (ADR 0004 D7), and a reader could count it as
  the workload's. The report now says so, and says the summed declaration is no workload
  document's shape.
- **Smaller:** the dashboard record and correlation queries were said to defer
  `inferops.cost.record.id`, which only the catalog does; the node's 0.52 cores outside
  the release were attributed to "12 pods", though they include the system and the
  sampler and the idle baseline read 0.28; memory outside the working set was called
  capacity "nothing used"; "the tool writes files by hand".

**What the first commit got wrong in the ADRs and the method data.**

- **ADR 0014's D3 update decided attribution.** It stated the workload and collector
  choices inside an accepted decision. The note now says which pods are the workload is not
  decided there, and points to the record that states its own choice.
- **ADR text was left inconsistent.** ADR 0007's D9 pointer said "typed into a calculation
  input by hand" and, in the same sentence, that the reader applies D3; its summary still
  said usage "is typed in by hand". ADR 0014's header ("half of it enforced"), its
  consequence counting no measured record, and its compatibility note naming one tool were
  left stale without a note. A parenthetical was spliced into an accepted risk bullet, and
  two notes described as dated carried no date. The accepted sentences are now restored as
  accepted, and separate dated notes say what changed.
- **The method document still said measured use reaches a calculation "by hand"** in its
  gaps table, which this record claimed was corrected.
- **Found in addressing the review, not by it:** the synthetic card's own `scope` named
  "the worked example and the calculation fixtures, and nothing else", and the baseline
  used it anyway. The scope now names the baseline, and a test checks it. The computation
  status's `state` stays `synthetic-only`, and its meaning now says that describes the
  prices.
- The claim matrix said the baseline's suite certifies "that the use is the samples'",
  which the cost row does not claim. It now says the suite checks that, and what the row
  certifies.

**What the first commit got wrong in the code and tests.**

- **A second parse sat outside the refusal.** `read_sources` parsed the samples and raw
  records again after the regeneration check, outside any `except`, so a parse error would
  have been a traceback rather than a refusal. It could not happen while both parses used
  the same texts, and relied on that. Both parses now use the same readers, inside a
  refusal.
- **A test could not fail.** `test_the_raw_set_parser_is_the_load_tools_own` asserted an
  `isinstance` that holds by construction. It is replaced by a test that the warm-up lies
  inside each window and its requests are counted, which the reviewer flagged as a domain
  point to state.
- **Smaller:** an unused `RECORD_KIND` constant, and node capacity read twice per run.

**What the first commit got wrong in this record.** It said the method document and ADR
0007 no longer said usage is typed in by hand, which was untrue in three places, and that
dated notes were added where two were undated. It opened a section by citing a requirement
rather than stating the check, which is now plain. Its counts described the first commit's suite: 41 functions and 53
tests, 487 in the cost suite, and a lane of 9300 passed. The counts above are for the tree
after these changes. The first commit's message repeats the first counts. Commit messages
are not rewritten; this is the correction.

**Not changed.** The window stays snapped outward to samples: the reviewers agreed it
matches D3 and is disclosed. `computationStatus.state` keeps its value. The per-phase and
whole-hour windows stay uncalculated, for the reasons above.

## What was not run, and why

| Not run | Why |
|---|---|
| Any load, cluster, model, or new experiment | The baseline reads the committed `V1-S4-004` evidence; nothing needed a new run, and none was authorized |
| A calculation over a whole-hour or per-phase window | A run's load span is the window its samples bound; a phase holds 60 requests, below the method's minimum of 100, so its unit cost would be null |
| A provider rate card | ADR 0007 D12 is not decided; the only card is synthetic |
| A dashboard panel or collector query for cost | Nothing emits a cost record; a query over `inferops_cost_records_total` would read a series no component produces |
| Pricing the model cache claim | Its size is not in the performance record, and it is not typed in |

## Acceptance criteria

| Criterion | Status |
|---|---|
| An hourly figure and a cost-per-request figure, on the estimate basis only | **Met.** Both records carry `derived.amountPerHour` and `derived.costPerThousandRequests` on the `estimated` basis, computed from measured use; `actual` and `allocated` stay refused. The per-request figure is per thousand (ADR 0014 D6) |
| The record validates against the output shape published with the cost method, not a contract | **Met and tested.** Both results are written by `tools/cost_calculation`, which validates every record against `recordShape.fields`, and a test recalculates each from its committed input |
| The price source is synthetic, versioned, dated, and says so in its own contents; no cost figure is published | **Met.** `synthetic-illustrative-v1`, version `1`, effective 2026-08-26, self-identifying; every result carries `publishedCostFigure: false`, and the report says no cost figure is published. Publication is still review only |
| Estimate, allocation, and invoice values cannot be confused; a missing input is null with a reason, not zero | **Met and tested.** One basis; the reservation is carried unpriced; the token unit cost is null with `below-minimum-sample`; a counter reset and a disagreeing reconciliation are tested to produce nulls with `input-conflict` |
| Price source and version, time window, idle and shared treatment, and confidence are explicit | **Met.** Each record names the card, version, and date; the report and derivation record state the windows, attribution, the unallocated line's contents, the excluded costs, and confidence derived as `none` |
| Deterministic fixtures | **Met.** The five baseline files regenerate byte for byte from committed evidence, and the two PR1 fixtures are unchanged |

For the parent story, `V1-S4-005`: the calculation (PR1) and the baseline, methodology,
confidence, and limitations (this change) are in place. The dashboard or query hook is
**not** added, because it does not fit the telemetry boundary; it stays deferred with the
platform component that would emit a cost record. No real price and no cost figure exist,
by decision.

## Deferred, and follow-up dependencies

- A **real rate card** needs ADR 0007 D12 decided. Its class caps confidence: an
  amortised-hardware card allows `low`, and a provider list price or negotiated price
  `medium`, which an estimate never exceeds.
- A **platform component that computes and emits a cost record** needs ADR 0007 D13 and
  ADR 0004's ownership question; the dashboard and query hook depend on it.
- **Checking a hand-typed input against its samples** stays open: `tools/cost_calculation`
  does not read samples.
- **The model cache claim** is unpriced until its size is recorded as evidence.

## Limitations and risks

- **One host, one release, one prompt, two runs.** Nothing generalizes.
- **The attribution of the collector** follows the method's shared-cost rule, and is a
  choice; it moves under a thousandth of either amount.
- **The owner is declared** by the executed values file, not observed.
- **Input tokens are not reconciled** against a counter.
- **The reservation and capacity are read once**, from the environment captured before
  the experiment; a resize in place would not be seen.
- **cgroup v1 readings** are the kernel's accounting of a pod, including file-backed
  pages and every thread.
