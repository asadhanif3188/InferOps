# V1-S0-007-PR1 change validation

Date: 2026-08-25

Classification: **local static evidence for the change itself.** Every result below
comes from reading and validating files in this repository and from running pytest
over them. No cluster was created, no model was downloaded, no runtime was started,
no request was served, and **no telemetry signal was emitted or observed**. Nothing
here is evidence that this is a good catalog, and nothing here is evidence that any
component will ever emit what it describes.

Claim boundary: the committed telemetry catalog is internally consistent under every
rule the suite states; fifty-nine deliberate corruptions of it — in the data, in two
published documents, in the proof index, in an evidence template, and in the test
strategy data — are each refused; every native runtime series the catalog names
appears in the record that measured it; every relative link resolves; the existing
suites are unchanged in behaviour; and the published diff carries no private,
generated, or overclaimed content.

**What this record does not establish.** Nothing in this repository emits a metric, a
log record, or a span, so no log line has ever been inspected and no series has ever
been scraped by this project. Every metric, attribute, and log rule specifies
behaviour for components that do not exist. Two of the fifteen rules in the catalog
are enforced by review alone and are marked as such. The cardinality budget is
arithmetic over declared bounds, not a measurement of any store. The four evidence
templates have produced no record.

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
contract tests, which need them. The telemetry suite this change adds needs `pytest`
alone.

## Commands and results

### The telemetry suite

```text
python -m pytest tests/telemetry -q
408 passed
```

Seventy-one test functions, parametrised across six placements, six sensitivity
classes, six cardinality classes, four emitters, nine signal families, thirty-two
attributes, six forbidden fields, sixteen metrics, fifteen prohibitions, four
templates, seven required evidence sections, ten limitations, fifteen native runtime
series, five required log fields, and sixteen conditional log fields.

### The strategy suite, which this change adds a claim and a path to

```text
python -m pytest tests/testing -q
433 passed
```

The documentation layer now names two directories, `tests/testing` and
`tests/telemetry`, and the claim and test matrix carries one more row.

### The full suite, to show nothing else moved

```text
python -m pytest tests -q
1389 passed, 7 skipped
```

The seven skips are the pre-existing contract-suite skips and are unchanged by this
change.

### Formatting and lint

```text
python -m ruff check tests tools conftest.py
All checks passed!

python -m ruff format --check tests/telemetry tests/testing tests/contracts tests/architecture
5 files already formatted
```

### JSON well-formedness

```text
python -m json.tool docs/telemetry/telemetry-catalog.v1alpha1.json
python -m json.tool docs/testing/test-strategy.v1alpha1.json
(both parse; output discarded)
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

Every relative link in the eight new documents and the eight modified ones resolves
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

Two of the checks are worth restating because they are the ones that would otherwise
be assertions.

**Series counts are recomputed, not trusted.** For each metric the suite multiplies
the declared bound of every label and, for a histogram, multiplies again by the
bucket count plus two. A declared `maxSeries` that disagrees with the computed value
fails, as does one above the per-metric ceiling of 2,000 or a total above 10,000.

| Metric | Computed | Declared |
|---|---:|---:|
| `inferops_build_info` | 25 | 25 |
| `inferops_inference_requests_total` | 500 | 500 |
| `inferops_inference_errors_total` | 300 | 300 |
| `inferops_inference_request_duration_seconds` | 1,750 | 1,750 |
| `inferops_inference_queue_duration_seconds` | 1,500 | 1,500 |
| `inferops_inference_requests_in_flight` | 125 | 125 |
| `inferops_inference_tokens_total` | 250 | 250 |
| `inferops_model_load_duration_seconds` | 720 | 720 |
| `inferops_model_ready` | 125 | 125 |
| `inferops_readiness_check_failures_total` | 150 | 150 |
| `inferops_workload_document_rejections_total` | 24 | 24 |
| `inferops_process_resident_memory_bytes` | 25 | 25 |
| `inferops_process_cpu_seconds_total` | 25 | 25 |
| **Total, active metrics** | **5,519** | ceiling 10,000 |

**Placement is derived, not read.** For each attribute the suite intersects the
placement lists of its sensitivity class and its cardinality class, and fails if the
declared placements are not a subset. The two content classes have an empty list, so
the intersection for anything in them is empty and no placement is possible.

## Deliberate corruptions, each refused

Fifty-nine mutations were applied one at a time to a working copy, the suite was run,
and the file was restored. Every one failed the suite. None survived.

### Content and sensitivity — 8

- a prompt is given a log field placement
- a secret class is given any placement at all
- the prompt is registered as an ordinary attribute
- the correlation identifier becomes a metric label
- the tenant identifier becomes a metric label
- the tenant identifier is allowed into an evidence record
- the pod name becomes a metric label
- a duration becomes a metric label

### Cardinality and budget — 8

- the release identifier is put on an operational metric
- an identity attribute is quietly made an ordinary metric label
- a label is added without updating the series count
- a metric's declared series count is quietly raised
- a metric exceeds the per-metric ceiling
- the total budget is exceeded
- an attribute's bound escapes its cardinality class
- the rule-identifier budget falls below the published rules

### Purpose, coverage, and deferral — 6

- a metric loses the question it answers
- an attribute's question stops being a question
- a required family loses its only active metric
- a deferred metric stops saying why
- an active metric acquires a deferral reason
- an unbounded attribute is given a bound

### Overclaiming — 8

- a runtime series nobody measured is published
- a metric is assigned to the runtime whose series are already evidence
- the missing request counter is quietly dropped
- a runtime series claims to be an InferOps metric
- the catalog claims something emits it
- a review-only rule is promoted to tested
- a rule names a test that does not exist
- a template records that it has produced evidence

### Content capture — 2

- content capture is switched on by default
- the content-capture prerequisites are thinned out

### Logs and correlation — 5

- a required log field is not a declared attribute
- a deferred attribute is made a required log field
- a conditional log field loses its condition
- a propagation header is made mandatory for callers
- the correlation rules lose the async boundary rule

### Structural consistency — 9

- the identity metric is turned into an ordinary one
- a histogram forgets its buckets
- an emitter is declared and never used
- a metric names an emitter that is not declared
- two attributes share a name
- a template path stops existing
- the limitations section drops the collector gap
- the runtime evidence reference points nowhere
- a document reference points nowhere

### Documents against data — 13

- the catalog document drops a metric
- the catalog document mislabels a field as identity-only
- the catalog document claims a field may be a metric label when it may not
- the catalog document invents an attribute
- the catalog document renames a runtime series
- the redaction document drops a rule
- the redaction document drops a forbidden field
- the proof index drops a template
- the proof index drops a required section
- a template loses its limitations section
- a template repeats a section
- a template stops saying it is a template
- the strategy stops naming the telemetry test directory

The mutation harness itself is not committed. It reads and restores files in the
working tree and produces no artifact this repository keeps; the list above is the
record of what it found.

## What a second review found

The change was reviewed independently after the first commit, against the diff and
the files it touches, with the reviewer asked to hunt for overclaim, contradiction,
tests that do not bite, and leakage. It found three defects, all real, all fixed in
the second commit:

| Severity | Defect | Fix |
|---|---|---|
| High | A test named `test_no_metric_is_claimed_to_be_emitted_by_a_component_that_exists` asserted the same condition twice and could not fail for the reason its name gave | Replaced with a check that bites: no metric may be assigned to the emitter whose series are recorded as measured evidence |
| High | The catalog document said the last four resource attributes were identity-only; `k8s.pod.name` is not one, and reaches no metric at all | The table gained an explicit column, the prose was corrected, and two tests now compare that column and the metric-label column against the data |
| Medium | The new claim's statement said a tenant identifier, a request identifier, and an unbounded value have "no permitted placement", when each is permitted in logs and traces and excluded only from a metric label | Statement and matrix prose reworded to separate the two cases |

The first is the one worth recording. A vacuous test is worse than a missing one,
because it appears in the count and in the list of rules that claim enforcement. The
suite already refuses a rule that names a test which does not exist; it cannot refuse
a rule that names a test which exists and asserts nothing, and this repository has now
had one.

Four mutations were added to cover the two new checks, which is why the corruption
count is fifty-nine rather than the fifty-five in the first commit.

## What the diff was reviewed for

| Checked for | Result |
|---|---|
| Credentials, tokens, keys | None. No credential appears in any new file |
| Private planning content, prompts, or unpublished strategy | None. No planning document is quoted, summarised, or referenced |
| Personal filesystem paths, hostnames, usernames | None. Every path in the diff is repository-relative |
| Generated files or host state | None. Cache directories remain ignored |
| Model artifacts | None |
| Capability claims not supported by evidence | None found. Every document states that nothing emits |
| Scope beyond this pull request | None. No component, adapter, exporter, or collector is added |

Two additions deserve naming explicitly because they touch files this change does
not own:

- `docs/testing/test-strategy.v1alpha1.json` gains one path on the existing
  documentation layer and one claim row. No layer, lane, marker, evidence class, or
  certification level changes.
- `docs/architecture/system-architecture.md` has its telemetry deferral paragraph
  replaced by a pointer to the catalog that resolves it. The three telemetry rules
  it states are unchanged.

## Limitations

- **No signal was emitted or observed.** This suite reads documents. The check that
  would matter — that a real log record carries only permitted fields — needs a logger
  that does not exist.
- **The mutation set is not exhaustive.** Fifty-nine corruptions were chosen because
  each represents a mistake somebody would plausibly make. A corruption nobody thought
  of is a corruption that was not tested.
- **The cardinality budget is not measured.** No metrics store has been tested with
  this catalog, and the declared bounds are estimates. The error-code bound in
  particular is a guess, because the canonical error vocabulary for inference is not
  published.
- **The runtime series list is one scrape on one host on one day.** It is
  `local-real-cpu` evidence for what that runtime exposed under that configuration,
  and it is evidence for nothing else in this change.
- **No secret scanner was run.** `gitleaks` is not installed here, and a committed
  configuration file is not a result.
- **Two rules are enforced by review alone**, and a review is enforced only when the
  reviewer remembers it.
