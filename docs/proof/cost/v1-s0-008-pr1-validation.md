# V1-S0-008-PR1 change validation

Date: 2026-08-26

Classification: **local static evidence for the change itself.** Every result below
comes from reading and validating files in this repository and from running pytest
over them. No cluster was created, no model was downloaded, no runtime was started, no
request was served, **no cost record was computed**, and **no invoice, rate card, or
price was retrieved from anywhere**. Nothing here is evidence that this is a good cost
method, and nothing here is evidence about what running an inference workload costs.

Claim boundary: the committed cost method is internally consistent under every rule
the suite states; the worked example's amounts, shares, and unit costs recompute in
exact decimal from the declared reservations and rates and close against the capacity
they allocate; seventy-two deliberate corruptions of it — in the method data, in two
published documents, in the telemetry catalog, and in the test strategy data — are
each refused; every telemetry signal the method names appears in the catalog that
declares it; every relative link resolves; the existing suites are unchanged in
behaviour; and the published diff carries no private, generated, or overclaimed
content.

**What this record does not establish.** Nothing in this repository computes, emits,
stores, or reads a cost record, so no amount here has ever been produced by a running
system. The only rate card committed is synthetic, which makes every amount in the
worked example arithmetically correct and **economically meaningless**. No provider
invoice has ever been seen, so the `actual` basis is untested in every sense. Two of
the fourteen rules in the method are enforced by review alone and are marked as such.
The minimum denominators are declared rather than derived.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.6` |
| `pytest` | `8.3.4` |
| `jsonschema` | `4.26.0` |
| `PyYAML` | `6.0.2` |
| `ruff` | `0.16.1` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |

`jsonschema` and `PyYAML` are listed because the full-suite run below includes the
contract tests, which need them. The cost suite this change adds needs `pytest` alone,
and the arithmetic uses only the standard library's `decimal` module.

## Commands and results

### The cost suite

```text
python -m pytest tests/cost -q
286 passed
```

Seventy-two test functions, parametrised across three bases, three allocation methods,
three residual treatments, twelve units, four rate-card classes, one published rate
card, four confidence levels, six confidence rules, twenty-four inputs, ten outputs,
six missing-data reasons, twenty-nine record-shape fields, fourteen rules, three
telemetry gaps, two open questions, twelve limitations, and two worked-example
records.

### The strategy suite, which this change adds a claim and a path to

```text
python -m pytest tests/testing -q
443 passed
```

The documentation layer now names three directories — `tests/testing`,
`tests/telemetry`, and `tests/cost` — and the claim and test matrix carries one more
row.

### The telemetry suite, which this change edits two deferral reasons in

```text
python -m pytest tests/telemetry -q
408 passed
```

Unchanged in count and in behaviour. The two edits change prose inside two
`deferralReason` fields; no name, class, placement, budget, or status moves.

### The full suite, to show nothing else moved

```text
python -m pytest tests -q
1685 passed, 7 skipped
```

The seven skips are the pre-existing contract-suite skips and are unchanged by this
change. The previous total on `main` was 1,389 passed and 7 skipped: the cost suite
adds 286, and the strategy suite gains 10 parametrised cases from the new claim row.

### Formatting and lint

```text
python -m ruff check tests tools conftest.py
All checks passed!

python -m ruff format --check tests/cost tests/telemetry tests/testing tests/contracts tests/architecture
6 files already formatted
```

### JSON well-formedness

```text
python -m json.tool docs/cost/cost-method.v1alpha1.json
python -m json.tool docs/telemetry/telemetry-catalog.v1alpha1.json
python -m json.tool docs/testing/test-strategy.v1alpha1.json
(all three parse; output discarded)
```

### Whitespace

```text
git diff --check main...HEAD
(no output)

git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
(no matches)

git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
(no matches)
```

### Links

The relative-link check from CONTRIBUTING, run over every tracked Markdown file:

```text
(no BROKEN lines)
```

Every relative link in the five new documents and the eleven modified ones resolves
from the directory of the file containing it. No external link was added by this
change.

### Kubernetes manifests and shell scripts

Not run, and not applicable: this change touches no file under `deploy/` or
`scripts/`.

### Secret scan

`gitleaks` is not installed on this host and no run of it is recorded. The
security-scan layer remains `planned` in the test strategy for exactly this reason,
and this change does not alter that. The diff was reviewed by hand instead, and what
that review covered is in the section below.

## The arithmetic the suite performs

This is the part that would otherwise be a set of typed numbers, so it is restated in
full. Every figure below is recomputed by the suite in exact decimal from the declared
reservations and the declared rates, rounded half-even once at a scale of six.

Rate card `synthetic-illustrative-v1`, effective 2026-08-26, **entirely invented**:
0.040000 per core-hour, 0.005000 per memory gibibyte-hour, 1.200000 per
accelerator device-hour, 0.000100 per storage gibibyte-hour.

| Line | Reserved | Computed | Declared |
|---|---|---:|---:|
| Node capacity | 8 cores, 16 GiB, 0 devices, 1 hour | 0.400000 | 0.400000 |
| `example-cost-0001` | 2.000000 core-hours, 4.000000 GiB-hours | 0.100000 | 0.100000 |
| `example-cost-0002` | 0.500000 core-hours, 1.000000 GiB-hours | 0.025000 | 0.025000 |
| Unreserved capacity | — | 0.275000 | 0.275000 |
| **Workloads + residual** | — | **0.400000** | node 0.400000 |
| Prerequisite claim | 5 GiB, 1 hour | 0.000500 | 0.000500 |
| Environment total | — | 0.400500 | 0.400500 |

| Derived figure | Denominator | Computed | Declared |
|---|---:|---:|---:|
| `example-cost-0001` share of node | — | 0.250000 | 0.250000 |
| `example-cost-0001` per thousand requests | 1,200 | 0.083333 | 0.083333 |
| `example-cost-0001` per million tokens | 576,000 | 0.173611 | 0.173611 |
| `example-cost-0002` share of node | — | 0.062500 | 0.062500 |
| `example-cost-0002` per thousand requests | 40 | null | null |
| `example-cost-0002` per million tokens | none | null | null |
| Unreserved share of node | — | 0.687500 | 0.687500 |

Three properties are checked rather than asserted, and each would otherwise be a
claim:

**The lines close.** The two workload amounts plus the residual equal the node
capacity amount exactly, at the record scale. A workload amount raised without a
matching change to the residual fails, and so does a residual set to zero.

**Confidence is recomputed.** For each record the suite evaluates every confidence
rule against the record's own declared facts and takes the lowest ceiling. Both
records derive `none` — the `allocated` basis caps at `low` and the synthetic rate
card caps at `none` — and a declared confidence that differs from the derived one
fails.

**No binary float exists.** The suite walks every scalar in the committed method and
fails on any `float`, and separately requires every monetary key to be a decimal
string of exactly six places.

## Deliberate corruptions, each refused

Seventy-two mutations were applied one at a time to a working copy, the suite was run,
and the file was restored. Every one failed the suite. None survived.

### Basis and the vocabulary of a bill — 6

- a record's basis becomes an invoice
- a record gains an invoice reference
- a record's note calls the amount spend
- two records carry different bases
- the invoice basis is marked reachable
- the allocation basis is marked unreachable

### Allocation and the residual — 7

- two allocation methods are selected
- no allocation method is selected
- a deferred allocation method stops saying why
- two residual treatments are selected
- the residual is discarded
- the residual is spread and the lines stop closing
- a prerequisite line is charged to a workload

### The arithmetic — 13

- a reserved quantity is altered
- a record's amount is quietly raised
- the node capacity amount is altered
- a share is altered
- a cost per thousand requests is altered
- a cost per million tokens is altered
- a rate changes and the amounts do not
- the window length changes and the reservations do not
- a memory quantity is written in decimal gigabytes
- a replica count changes and the reservation does not
- an amount becomes a binary float
- the prerequisite amount is altered
- the environment total stops including the prerequisite line

### Prices — 6

- a price source is fetched rather than committed
- a price source points at a retrieval URL
- a synthetic rate card stops saying it is synthetic
- a synthetic rate card is declared publishable
- a priced unit loses its rate
- the synthetic card claims to be a provider list price

### Confidence — 5

- a record's confidence is raised by hand
- a confidence rule's ceiling is raised
- a confidence rule names a fact no record carries
- a basis claims more confidence than its rules allow
- a record's declared facts stop matching its basis

### Missing data — 6

- an unavailable input is given a zero
- an available input is listed as unavailable
- a null unit cost loses the reason that explains it
- a unit cost is published below the minimum sample
- a unit cost loses its denominator
- a common missing-data reason stops being used anywhere

### Telemetry, sensitivity, and leakage — 7

- an input names a signal the catalog does not declare
- a usage input claims it is available today
- a tenant field is allowed into a committed record
- a worked-example record gains a tenant identifier
- an operational field is marked uncommittable
- the method stops using the name the catalog reserved
- a record field is classed as user content

### Overclaiming — 8

- the method claims something computes it
- the method claims a cost record was produced
- the method claims an invoice was read
- a review-only rule is promoted to tested
- a rule names a test that does not exist
- every rule claims a test
- the worked example stops calling itself synthetic
- the limitations lose the one saying nothing computes

### Structure — 5

- two inputs share an identifier
- an output declares a precision the method does not
- a declared input is required by nothing
- a document reference points nowhere
- a gap names an input that does not exist

### Documents against data — 9

- the method document drops a rule
- the method document drops an input
- the method document drops a missing-data reason
- the method document publishes an identifier the data lacks
- the worked example drops a record
- the worked example publishes a number the data does not have
- the worked example stops publishing a declared amount
- the strategy stops naming the cost test directory
- the catalog stops declaring the signal an input names

One mutation in the first pass was **written wrongly rather than survived**, and it is
recorded here because the distinction matters. "A declared input is required by
nothing" originally removed a telemetry gap in order to orphan the accelerator input;
that input is also named by the deferred allocation method, so nothing was orphaned
and the suite correctly passed. Rewritten to add an input that genuinely nothing
references, it fails with the expected message. The seventy-two above are the counts
after that correction.

The mutation harness itself is not committed. It reads and restores files in the
working tree and produces no artifact this repository keeps; the list above is the
record of what it found.

## What a second review found

The change was reviewed independently after the first commit, against the diff and the
files it touches, with the reviewer asked to hunt for overclaim, contradiction, tests
that do not bite, and leakage. What it found and what was done about it is recorded in
the second commit and summarised here after that review completed.

## What the diff was reviewed for

| Checked for | Result |
|---|---|
| Credentials, tokens, keys | None. No credential appears in any new file |
| Private planning content, prompts, or unpublished strategy | None. No planning document is quoted, summarised, or referenced, and no sprint, backlog, or roadmap vocabulary appears |
| Personal filesystem paths, hostnames, usernames | None. Every path in the diff is repository-relative |
| Generated files or host state | None. Cache directories remain ignored |
| Model artifacts | None |
| Real prices, provider names, account identifiers, or invoice data | None. The only rate card is labelled synthetic and every rate in it is invented |
| Tenant identifiers in a committed record | None, and a test now refuses one |
| Capability claims not supported by evidence | None found. Every document states that nothing computes a cost record |
| Scope beyond this pull request | None. No component, schema, collector, or price fetcher is added |

Four additions deserve naming explicitly because they touch files this change does not
own:

- `docs/testing/test-strategy.v1alpha1.json` gains one path and one command on the
  existing documentation layer, and one claim row. No layer, lane, marker, evidence
  class, or certification level changes.
- `docs/telemetry/telemetry-catalog.v1alpha1.json` has two `deferralReason` strings
  corrected, because this change makes the old reasons false. Both signals remain
  deferred; no name, class, placement, budget, or status moves.
- `docs/architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md` has the
  same correction applied to one sentence, with the amendment stated in the sentence
  rather than made silently.
- `docs/contracts/README.md` gains one paragraph recording that a cost record's shape
  is now published as part of the method and still has no schema, which is the
  directory's existing rule applied rather than an exception to it.

## Limitations

- **No cost record was computed.** This suite reads documents. The check that would
  matter — that a producer applies these rules to a real reservation — needs a
  component that does not exist.
- **Every price is invented.** The arithmetic is verified; the inputs to it are not
  measurements of anything. No amount in this change may be cited as a cost.
- **The `actual` basis is untested in every sense.** No invoice, billing export, or
  provider account exists, so the rules about one are specification only.
- **The mutation set is not exhaustive.** Seventy-two corruptions were chosen because
  each represents a mistake somebody would plausibly make. A corruption nobody thought
  of is a corruption that was not tested, and the first pass produced one mutation that
  was written wrongly rather than one that survived.
- **The minimum denominators are arbitrary.** One hundred requests and ten thousand
  tokens are declared, not derived, and the method says so in its own limitations.
- **Node capacity is declared, not read.** Nothing in this repository reads allocatable
  capacity from a cluster, so the example allocates a machine that does not exist.
- **No secret scanner was run.** `gitleaks` is not installed here, and a committed
  configuration file is not a result.
- **Two rules are enforced by review alone**, and a review is enforced only when the
  reviewer remembers it.
