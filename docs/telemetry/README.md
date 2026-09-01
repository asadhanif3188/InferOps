# Telemetry and evidence

Status: entry point established; the catalog is accepted in part — six of the eight
decisions in [ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md),
with the content-capture policy and the telemetry toolchain explicitly not chosen.
The InferOps API emits eight of the thirteen active metrics and writes the specified
log records; the serving-runtime adapter, the contract validator, and every span do
not.

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
| [API instrumentation](api-instrumentation.md) | What the API actually emits: the eight metrics, a scrape, a record, the variables a deployment states its identity in, and what is still absent |
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
so the exclusion is arithmetic rather than a rule somebody applies — and, since the
API began emitting, a log record is built through an allowlist that has no name for
any of them, so the exclusion is also the absence of a key.

Eight metrics are emitted, by the API and by nothing else. The four assigned to the
serving-runtime adapter, the one assigned to the contract validator, and one
assigned to the API with no source it may read are not, and each says why in the
data.

## Running the checks

```sh
python -m pytest tests/telemetry -q
```

It reads only files in this repository and needs `pytest` alone.

## What is not here

No exporter, no collector, no store, no dashboard, and no alert. No tracer and no
propagator. A logger and a redacting sink now exist, and they write to a stream:
nothing scrapes the endpoint, nothing collects the stream, and no retention window,
shipper, or access rule is selected. The ownership inventory
[records that gap](../architecture/resource-ownership.md) rather than assigning it to
a tool by accident.

The one thing here that was measured rather than specified is the list of series the
selected serving runtime exposes. That came from
[a recorded trial](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) on one
host on one day, and a test compares every series this directory names against that
record.
