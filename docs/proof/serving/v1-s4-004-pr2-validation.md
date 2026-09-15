# V1-S4-004-PR2 — change validation: performance findings and limits

Date: 2026-09-15

Classification: **analysis of committed local real evidence**, evidence class
`local-real-cpu`. This change sent no load, installed nothing, contacted no cluster, and
loaded no model. Its only input is the committed record of
[the V1-S4-004-PR1 run](v1-s4-004-pr1-validation.md) and the six files that record
regenerates from.

## What this change publishes

- [The performance findings](v1-s4-004-pr2-performance-findings.md): latency
  percentiles, completed-request rates, errors, runtime CPU and memory, tokens, collector
  queue gauges, and the dashboard's phase-end readings, compared across the baseline and
  concurrency 2 and 4 in both repetitions. They include a degradation statement bound to
  the recorded provider, host, model, runtime, release configuration, and load profile,
  the likely bottleneck with the evidence for it, why the results are not universal, and
  follow-up hypotheses. Nothing in them is implemented.
- [`v1-s4-004-pr2-findings.v1alpha1.json`](v1-s4-004-pr2-findings.v1alpha1.json): the
  figures the report computes rather than copies, as integers, with the record's SHA-256.
- [`tools/performance_findings`](../../../tools/performance_findings/): `derive` and
  `verify`. It refuses a record that does not regenerate byte for byte under
  `tools.performance_scenarios`, is not usable, has lost its boundary sentence, or does not
  carry `productionBenchmark`, `portableCapacityClaim`, and `saturationJudged` as
  `false`. The findings it writes carry the same three flags as `false`; the degradation
  statement is in the report, as ADR 0013 D4 requires.
- [`tests/serving/test_performance_findings.py`](../../../tests/serving/test_performance_findings.py):
  the refusals, the arithmetic, the committed findings regenerating, and, against the
  findings file, every row of the report's results tables, its setup table's figures, and
  the figures its prose quotes. The report's interpretation is checked by review only.

## What changed elsewhere

- [The load guide](../../serving/llm-load-generation.md) said every `dispatchOffsetMs`
  is measured from the run header's `startedAtEpochMs`. `tools.llm_load` measures it from
  its own phase's start. Placing requests on the wall clock for this analysis showed the
  difference; the sentence is corrected. No code changed.
- [The procedure](../../serving/performance-scenarios.md) points to the findings and
  documents the new commands. [The test strategy](../../testing/test-strategy.md), the
  README, CONTRIBUTING, the CHANGELOG, [the proof index](../README.md), and the
  [test inventory](../../testing/test-inventory.md) and its data are updated. The
  inventory's documentation layer and its list of modules defending no claim each go
  from twenty-seven to twenty-eight.

No product behaviour changed: no file under `src/`, `charts/`, `deploy/`, `infra/`, or
`scripts/` was modified, and `tools.performance_scenarios` and `tools.llm_load` are
unchanged. No ADR, contract, schema, or claim row changed. The `capacity` lane, the
`capacity-and-load` layer, and `sustained-throughput-and-capacity-under-load` keep their
status.

## Independent review, and what it changed

The first commit was reviewed before push by three independent reviewers: one for the
tool's and the tests' code, one for every number and claim against the committed
evidence, recomputed from the raw files, and one for scope, governance under ADR 0013,
measurement semantics, and leakage. Each finding below was checked before it was acted
on. **No leakage was found**, nothing was out of scope, and every table value in the
report matched the raw files.

**What the first commit got wrong in the report.**

- **The bottleneck overclaimed.** It named "the runtime's single parallel slot" as the
  likely bottleneck. The evidence shows requests were served one at a time, and that the
  runtime was at 99.1% of its CPU limit already at concurrency 1. The CPU limit is an
  equally supported candidate, and the report itself said more slots might only share
  the CPU. The statement now says which of the two bound is not established.
- **The degradation statement compared two figures wrongly.** It called the 0.021 spread
  across levels "no larger than the difference between the two runs", which is 0.019. It
  also said added callers added "no completed work", though run 1's `c4` read 1.038 of its
  baseline. Both now say what the figures say.
- **CPU was stated per request.** "Each request kept the runtime at 99.1–99.9% of its
  limit for about 1.7 s" and "serving one request, the runtime's six threads kept..." read
  a phase-averaged counter as a per-request observation. They now say averaged over each
  phase.
- **A figure was wrong.** "`c1` reads 40–50 millicores below" was 37–49. The findings file
  did not hold it, so no test could catch it; it now does, and a test checks it.
- **The prompt-cache hedge was dropped in three places:** the heading of finding 5, its
  last sentence, and "The prompt was cached. Nearly every request evaluated one prompt
  token" under the limits. The split also assumes every request evaluated at least one
  token, which was not said.
- **"Four pieces of evidence agree" overstated the support.** The fastest request's
  position is the same with one slot or several, and at `c1`; completion gaps can be
  spaced apart by several slots admitting requests at staggered times. The finding now
  separates what the configuration and gauges establish from what is only consistent
  with it.
- **Smaller corrections:** "Latency grew in proportion to concurrency" held for P50 only;
  the input-token agreement was attributed to range steps though the scheduled instant
  reads carry it too; "its item 9" pointed at the record rather than the PR1 validation
  record; the queueing was said to be visible "only" through runtime gauges; the gauge
  steps were not said to rest on 3 or 4 scrapes; the queue-wait follow-up read like a
  request for a metric; the record's rates are truncated, which was not said.

**What the first commit got wrong in the code.** None of these changes a figure the
committed findings held; the regenerated file only gains fields.

- **Five setup values were converted with a bare `int()`.** A record that regenerates can
  still carry a non-numeric `--parallel`, `--threads`, `--ctx-size`, output-token limit,
  or request deadline, and the tool raised a raw `ValueError`. They are now named
  refusals, with tests.
- **A phase with one completion crashed** on `min()` of an empty gap list. It is now a
  named refusal, with a test.
- **The input-token counter was read from 15-second range steps** when the scheduled
  instant reads the record already takes carry it. It is now read there. The values are
  unchanged.
- **A differing findings file printed `REFUSED`** while exiting `1`, a code this
  repository uses for failure, not refusal. It now prints `FAILED`.
- **The findings file did not hold several figures the prose quoted**: the CPU difference
  from baseline, the between-run latency differences, the rate spread, and the warm-up's
  first-request difference. It now does.

**What the first commit got wrong in this record, the CHANGELOG, and the inventory.**

- **"Every table in the report" is tested** was stated here, in the CHANGELOG, in the
  test inventory's document and data, and in the first commit's message. The setup table
  was checked for four strings. The tests now check its figures and the figures the prose
  quotes, and each of those sentences says what is checked.
- **"Every figure the report computes" is in the findings file** was not true, as above.
- **The acceptance row cited "Tables 1, 2, 4, and 5"**, which are finding numbers, and
  finding 2 has no table.
- **The CHANGELOG called the prompt "cached"** and set the CPU figure beside the
  single-slot finding without saying which limit bound. **The first commit's message**
  also named "one cached 35-token prompt" and a count, "2788 in the testing, security and
  performance modules", that no record held. Commit messages are not rewritten; this is
  the correction.
- **The `tests/testing` count** was recorded before this record existed and its links
  resolved.

**Not changed.** The completion-gap reasoning stays in the report, labelled as consistent
with one slot rather than proof of it. Table rows are still matched as substrings. No
throttling, slot, or prompt experiment was added; each stays a follow-up hypothesis.

## Checks run on the change

Every command ran from the repository root in Git Bash, inside the locked environment
(`uv run --locked ...`), with nothing contacted, after the review changes. The first
commit's own runs recorded 30 passed for the new suite, 1816 for `tests/testing`, and a
lane of 9060 passed with 1 failed: the proof index linked this record before it existed.
The check commands below show the last line each printed.

```text
python -m pytest tests/serving/test_performance_findings.py -q            39 passed
python -m pytest tests/testing -q                                         1818 passed
python -m pytest -q                                                       9073 passed, 31 skipped, 14 deselected
ruff format --check .                                                     401 files already formatted
ruff check .                                                              All checks passed!
python -m mypy                                                            Success: no issues found in 223 source files
python -m tools.performance_scenarios verify --dir docs/proof/serving --prefix v1-s4-004-pr1-
                                                                          ok  the committed record regenerates from its inputs; usable=True
python -m tools.performance_findings verify --dir docs/proof/serving --record-prefix v1-s4-004-pr1- --findings docs/proof/serving/v1-s4-004-pr2-findings.v1alpha1.json
                                                                          ok  the committed findings regenerate from a record that regenerates from its inputs
python -m tools.performance_scenarios check                               claim  bounded observations; not capacity, an SLO, or a benchmark; saturation not judged
python -m tools.llm_load check                                            execution  not started (offline profile validation only)
scripts/environment/performance-scenarios.sh check                        [inferops] the descriptor validated. Nothing was contacted and no release was installed.
python -m tools.inference_dashboard                                       ok  29 panel(s) satisfy the dashboard policy
git diff --check                                                          (no output)
```

Private-information inspection of the diff: searched every added line for drive paths,
user or home directories, IPv4 addresses other than loopback, host names, e-mail
addresses, and kubeconfig references. None was found; the kernel release matched
the address pattern and is the one the PR1 record already publishes. Pod names,
the namespace, and image digests are reproduced as the committed PR1 record emits them.

## What was not run, and why

| Not run | Why |
|---|---|
| Any new load, cluster, or model run | This PR analyses committed evidence; no execution was authorized or needed |
| CPU throttling analysis | The PR1 sampler did not read `cpu.stat`; it cannot be recovered from the inputs |
| Any follow-up hypothesis in the report | Each needs a changed descriptor or profile and an authorized run; out of this PR's scope |
| A comparison with the V1-S2-005 local baseline | A different composition outside Kubernetes; ADR 0013 D2 refuses reading one setup's figures as another's |

## Acceptance criteria

| Criterion | Status |
|---|---|
| A baseline and at least one higher load are compared | **Met.** `c1` against `c2` and `c4`, in both runs, with ratios to each run's own baseline |
| P50/P95/P99, throughput, errors, resource use, and tokens where available | **Met.** Findings 1, 2, 4, and 5 of the report; input tokens are now compared with the collector's scheduled counter reads as well |
| The saturation statement is specific to the provider, host, model, runtime, and workload profile, and names the experiment boundary | **Met, by review.** The statement names each. Tests check the figures it quotes, not its meaning |
| Portable capacity, production SLO, and universal benchmark readings are refused | **Met, by review.** The report refuses each explicitly; the findings file carries the flags as `false`, which the tool enforces |
| Raw evidence supports the summary | **Met and checked.** The findings derive only from a record that regenerates from its raw inputs, and every report table is tested against the findings |

## Limitations

- Every limitation of the PR1 run holds: one provider, host, release, prompt, and two
  repetitions, a shared node, a port-forward in every latency, no throttling counters.
- The report's interpretation, including the degradation statement, the attribution, and
  the refusals, is checked by review only. The tests hold its tables, the figures its
  prose quotes, and the presence of the refusal wording, not its meaning. A table row is
  matched as a substring, so a stale extra row or a changed header would not fail.
- Collector gauges are read at 15-second steps of a 30-second scrape, about 3 or 4
  scrapes a phase. A maximum can miss a shorter excursion. The single-slot finding rests
  on the runtime's configuration and those gauges; the completion gaps are consistent
  with it and do not prove it alone.
- The runtime prompt-token counter is read from range steps, since the record reads it at
  no scheduled moment.
- Which limit bound the completed rate, the single slot or the CPU, is not established.
