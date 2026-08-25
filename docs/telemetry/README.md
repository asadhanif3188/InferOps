# Telemetry and evidence

Status: entry point established; the catalog is accepted in part — six of the eight
decisions in [ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md),
with the content-capture policy and the telemetry toolchain explicitly not chosen.
Nothing in this repository emits a metric, a log record, or a span.

This directory answers a question that is easy to answer by accumulation: which
signals a system should emit. The failure mode is not emitting too few — it is
emitting whatever a library makes available, discovering the bill, and then removing
signals by whichever were cheapest to delete rather than by which nobody read.

So every signal here states the question it answers, and every field's placement is
derived from two declared classes rather than chosen. A prompt has nowhere it may
go. A correlation identifier is a log field and never a label. A duration is a value
and never a key. None of those is a convention anybody has to remember.

## Documents

| Document | What it covers |
|---|---|
| [Telemetry catalog](telemetry-catalog.md) | Correlation, resource and request attributes, thirteen active metrics, the cardinality budget, what the selected runtime already emits, and the log record |
| [Redaction rules](redaction.md) | What is excluded, why each exclusion is tempting, which rules are really enforced, and what would have to exist before content capture could be enabled |
| [`telemetry-catalog.v1alpha1.json`](telemetry-catalog.v1alpha1.json) | The authoritative form of both, validated by [`tests/telemetry/`](../../tests/telemetry/) |
| [Evidence records and templates](../proof/README.md) | The four templates a record is written from, and the sections every record carries |

## The short version

Seven signal families have to be covered — availability, errors, latency,
throughput, model load, tokens, and resource use — and an eighth, identity, exists
so that everything else can be pinned to a build, a model revision, and an image
digest. Thirteen metrics cover them, three more are defined and deferred with a
reason, and the whole catalog costs at most 5,519 series against a ceiling of
10,000.

Six fields are excluded outright and can be placed nowhere: a prompt, a completion,
a provider error body, a secret value, an authorization header, and any value read
out of a submitted document. Their sensitivity classes have empty placement lists,
so the exclusion is arithmetic rather than a rule somebody applies.

## Running the checks

```sh
python -m pytest tests/telemetry -q
```

It reads only files in this repository and needs `pytest` alone.

## What is not here

No exporter, no collector, no store, no dashboard, and no alert. No tracer and no
propagator. No logger and no redacting sink. Nothing scrapes anything, and the
ownership inventory
[records that gap](../architecture/resource-ownership.md) rather than assigning it to
a tool by accident.

The one thing here that was measured rather than specified is the list of series the
selected serving runtime exposes. That came from
[a recorded trial](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) on one
host on one day, and a test compares every series this directory names against that
record.
