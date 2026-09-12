# Telemetry and evidence

Status: entry point established; the catalog is accepted in part — six of the eight
decisions in [ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md),
with the content-capture policy and the telemetry toolchain explicitly not chosen.
The InferOps API emits eight of the thirteen active metrics and writes the specified
log records; the serving-runtime adapter, the contract validator, and every span do
not. A release-scoped collector now exists and has scraped both InferOps jobs on the
`docker-desktop` reference provider; its series are ephemeral, and no durable
backend, dashboard, or alerting path is selected.

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
| [Collecting telemetry in Kubernetes](kubernetes-telemetry-collection.md) | What the collector scrapes from an installed release: two jobs, the labels it attaches and the ones it deliberately does not, what `instance` costs, the native runtime mapping, and the signals that have no source |
| [`kubernetes-telemetry-collection.v1alpha1.json`](kubernetes-telemetry-collection.v1alpha1.json) | The authoritative form of that document, compared against the committed chart renders by [`tests/telemetry/`](../../tests/telemetry/) |
| [Correlated telemetry queries](telemetry-correlation-queries.md) | What an operator can ask of the release's own collector, and what a durable store would add: twenty-three questions, the vocabulary a query may use, the identity join, ten deliberately wrong queries and the rule that refuses each, and the six questions with no answer |
| [`telemetry-correlation-queries.v1alpha1.json`](telemetry-correlation-queries.v1alpha1.json) | The authoritative form of that document, checked against the catalog and the collection record and evaluated against fixtures by [`tests/telemetry/`](../../tests/telemetry/) |
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

No exporter, no durable store, no dashboard, and no alert. No tracer and no
propagator. A logger and a redacting sink now exist, and they write to a stream:
nothing collects that stream, and no retention window, shipper, or access rule is
selected. The ownership inventory
[records what is still missing](../architecture/resource-ownership.md) — a durable
`telemetry-backend`, deferred — rather than assigning it to a tool by accident.

A collector, by contrast, is no longer missing. The chart renders the scrape
configuration **and** owns the release-scoped Prometheus that reads it, and
`V1-S3-011` installed one: it discovered and scraped both InferOps jobs on the
`docker-desktop` reference provider. [The collection document](kubernetes-telemetry-collection.md)
records what it found. Its series live in an `emptyDir` and go with its pod, so it
answers questions about the release running now and is not a store anything may
depend on.

The queries have been run against it. Every one was first parsed, checked against the
catalog's placement rules, and evaluated against synthetic fixtures by this
repository's own evaluator, and a real Prometheus has since parsed, loaded, and
evaluated every one against a real scrape — on one provider, on one host.
[The query document](telemetry-correlation-queries.md) publishes what each returns,
what an empty result would mean, and the four things that cannot be correlated at
all. Nobody is told when an answer changes: there is no dashboard and no alerting
path.

The one thing here that was measured rather than specified is the list of series the
selected serving runtime exposes. That came from
[a recorded trial](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) on one
host on one day, and a test compares every series this directory names against that
record.
