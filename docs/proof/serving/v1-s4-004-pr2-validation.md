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
- [`v1-s4-004-pr2-findings.v1alpha1.json`](v1-s4-004-pr2-findings.v1alpha1.json): every
  figure the report computes rather than copies, as integers, with the record's SHA-256.
- [`tools/performance_findings`](../../../tools/performance_findings/): `derive` and
  `verify`. It refuses a record that does not regenerate byte for byte under
  `tools.performance_scenarios`, is not usable, has lost its boundary sentence, or does not
  carry `productionBenchmark`, `portableCapacityClaim`, and `saturationJudged` as
  `false`. The findings it writes carry the same three flags as `false`; the degradation
  statement is in the report, as ADR 0013 D4 requires.
- [`tests/serving/test_performance_findings.py`](../../../tests/serving/test_performance_findings.py):
  the refusals, the arithmetic, the committed findings regenerating, and **every table in
  the report** agreeing with the findings file.

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

## Checks run on the change

Every command ran from the repository root in Git Bash, inside the locked environment
(`uv run --locked ...`), with nothing contacted. The check commands show the last line
each printed.

```text
python -m pytest tests/serving/test_performance_findings.py -q            30 passed
python -m pytest tests/testing -q                                         1816 passed
python -m pytest -q                                                       9060 passed, 1 failed, 31 skipped, 14 deselected
python -m pytest tests/testing/test_document_links.py -q                  passed after this record was written (see below)
ruff format --check .                                                     400 files already formatted
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

The one failure in the full lane was the link check on the proof index, which already
linked this record before it was written.

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
| P50/P95/P99, throughput, errors, resource use, and tokens where available | **Met.** Tables 1, 2, 4, and 5 of the report; input tokens are now compared with the collector as well, from range series |
| The saturation statement is specific to the provider, host, model, runtime, and workload profile, and names the experiment boundary | **Met, by review.** The statement names each; no test checks prose |
| Portable capacity, production SLO, and universal benchmark readings are refused | **Met, by review.** The report refuses each explicitly; the findings file carries the flags as `false`, which the tool enforces |
| Raw evidence supports the summary | **Met and checked.** The findings derive only from a record that regenerates from its raw inputs, and every report table is tested against the findings |

## Limitations

- Every limitation of the PR1 run holds: one provider, host, release, prompt, and two
  repetitions, a shared node, a port-forward in every latency, no throttling counters.
- The report's sentences, including the degradation statement and the refusals, are
  checked by review only. The tests hold its tables, a few quoted figures, and the
  presence of the refusal wording, not its meaning.
- Collector gauges are read at 15-second steps of a 30-second scrape. A maximum can miss a
  shorter excursion; the gauges' agreement with the completion gaps is what the
  single-slot finding rests on, not either alone.
- The input-token agreement is read from range steps, not the instant reads the record
  reconciles with.
