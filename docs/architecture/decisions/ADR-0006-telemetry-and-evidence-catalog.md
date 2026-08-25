# ADR 0006: Telemetry and evidence catalog

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-08-25 |
| Date accepted | 2026-08-25, for D1 through D6 only |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | None |

> [!IMPORTANT]
> This record decides which signals V1 emits, where each field is allowed to be
> placed, and what an evidence record has to contain. It does **not** implement any
> of it. No component in this repository emits a metric, a log record, or a span;
> no collector, store, dashboard, or alert exists; and no tracer, exporter, or
> logging library is selected.
>
> One half of it is machine-checked. The catalog is committed as data and validated
> by `tests/telemetry/test_telemetry_catalog.py`, which derives every field's
> permitted placement from its two declared classes, recomputes every metric's
> series count from its labels, and compares every native runtime series named here
> against the record that measured it. The other half — whether the components that
> would emit this will emit it faithfully — has no check, because those components
> do not exist.
>
> D7 is **not decided**: no content-capture policy exists, and there is no
> configuration flag that could enable capture. D8 is **not decided here**, on
> purpose: the telemetry toolchain and the ownership of a collector belong to
> ADR 0004's open question, and re-answering it in passing is exactly the leak this
> record is meant to avoid.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Correlation propagates over W3C Trace Context, with a business correlation identifier assigned at the edge and reused across retries | **Accepted** as a rule | Review, and the request-flow design in ADR 0004. Nothing propagates anything |
| D2 | Placement is derived from a sensitivity class and a cardinality class, never chosen per field | **Accepted** | Enforced by a test over the committed catalog, in both directions |
| D3 | Thirteen active metrics cover seven required signal families, plus one identity metric | **Accepted** | A committed catalog, with family coverage enforced by a test |
| D4 | A per-metric and total cardinality budget, recomputed from labels rather than asserted | **Accepted** | Arithmetic the suite performs; it is not a measurement of a store |
| D5 | Structured logs with a required field set, a bounded event identifier, and no free-form message | **Accepted** as a rule | Review, plus tests that every named field is declared and permitted in a log |
| D6 | Four versioned evidence templates with seven mandatory sections | **Accepted** | The templates exist and a test reads each one for every required section |
| D7 | What would allow prompt and response capture: classification, redaction, retention, access, lawful basis | **Not decided** | Nothing. Capture is disabled and there is no flag to change that |
| D8 | Which telemetry SDK, exporter, collector, and store, and who owns them | **Not decided, and not this record's to decide** | ADR 0004 leaves the collector unowned; this record does not fill that in |

## Context

Five decisions are accepted, one contract is published, two suites run, and one
serving runtime has been proven once. What does not exist is any statement of what a
running InferOps would say about itself.

[The system architecture](../system-architecture.md) fixed three rules for
telemetry — nothing in a cluster writes evidence, prompts and responses are not
telemetry by default, and high-cardinality request data does not belong in a metric
label — and then deliberately deferred the catalog itself, on the grounds that
pre-empting it would produce a list nobody had reviewed. This is that review.

The gap is not neutral, and it closes itself in a predictable direction. The first
component that needs to be observable will reach for whatever its metrics library
exposes by default, and the defaults are generous: a label per route, a label per
status, a label per instance, and — the one that actually costs — a label carrying
whatever identifier was nearest to hand. By the time anybody counts the series, the
dashboards are built on them.

The second predictable failure is worse and cheaper to make. During an incident, the
fastest way to understand a bad answer is to log the prompt that produced it. That
change is one line, it is obviously useful, and it moves data the project does not
own into a store with a retention window nobody was tracking. Deleting the line
afterwards does not undo it.

Two constraints come from outside. The selected serving runtime exposes native
metrics and **no cumulative request counter** — a threshold
[ADR 0002](ADR-0002-model-and-serving-runtime.md) records as failed rather than
smoothed over — so the catalog has to say which signals come from the runtime and
which the platform must produce itself. And
[the project boundaries](../project-boundaries.md) forbid V1 publishing any
throughput, latency, capacity, or benchmark figure, which makes the latency and
throughput metrics operational instruments rather than material for a claim.

## Decision criteria

| Criterion | Why it matters |
|---|---|
| Content cannot leak by default | The failure that is unrecoverable once it happens, and the one a hurried change makes most easily |
| Cardinality is a number, not an intuition | An unbounded label is discovered by a bill or an outage, and by then the dashboards depend on it |
| Every signal has a reader | A catalog assembled from what a library exposes is a permanent cost with no owner |
| A rule survives inattention | A rule enforced only by review is enforced only when the reviewer remembers it |
| Nothing overclaims | A specified metric is not an emitted one, and a mapping table is not a scrape |
| No decision leaks into an adjacent one | Choosing what to measure must not silently choose a vendor, an SDK, or a cost model |

## D1 — Correlation over W3C Trace Context, assigned at the edge

A correlation identifier is assigned by the first InferOps component to see a
request, before anything downstream can fail. A retry reuses it and takes a new
span. Across an asynchronous boundary, producer and consumer spans are linked rather
than nested and the identifier travels in the message envelope. None of the three
propagation headers is required of a caller: an absent trace context starts a new
trace rather than refusing the request.

The alternative was to mint the identifier where the work happens, inside the
handler. It was rejected because of which requests it fails to cover. A request
refused at the edge — an unsupported contract version, a malformed document, a model
that is not ready — is exactly the request a caller will ask about, and an identifier
created inside a handler the request never reached does not exist for it. A refusal
has to be as traceable as a success or the tracing is for the easy half.

A second alternative was to use the span identifier as the correlation identifier and
carry one concept instead of two. It was rejected because the two answer different
questions — *what happened to this piece of work* versus *what happened on this
attempt* — and a retry makes them diverge. One identifier cannot answer both without
losing the retry or losing the work.

**Not decided:** every part of the implementation. No tracer, propagator, exporter,
or SDK is selected, and nothing reads or writes these headers.

## D2 — Placement is derived, not chosen

Every field declares a sensitivity class and a cardinality class. Its permitted
placements are the intersection of what those two classes allow, and a placement
outside that intersection fails the suite.

Six sensitivity classes and six cardinality classes cover the catalog. Two
sensitivity classes — `user-content` and `secret` — have an **empty** placement list,
which is what makes "no prompt in telemetry" arithmetic rather than a convention.

The alternative was the usual one: a list of forbidden fields, in a document, that a
reviewer applies. It was rejected because it fails in exactly one predictable way. A
list catches the six fields somebody thought of; the seventh arrives in a change
whose author has a good reason for it, and the reviewer either remembers the rule or
does not. Deriving placement from a declared class means the seventh field has to be
classified before it can be placed, and a misclassification is visible in a way a
missing list entry is not.

Three consequences are worth stating because each is a field somebody will
reasonably propose as a metric label and each is refused:

- A **tenant identifier** is bounded and is still barred from metrics and from
  evidence records. A metrics store labelled by tenant is a customer list with a
  retention window; an evidence record is public and permanent.
- A **pod name** and a **workload version** are classed unbounded, because the set
  grows once per restart and once per deployment and nothing retires old values. They
  are bounded at any instant and unbounded over the store's retention window, which
  is the window that pays for them.
- A **duration** is a measurement and never a key. A duration used as a label
  produces one series per distinct millisecond.

## D3 — Thirteen metrics for seven required families, plus identity

Seven signal families are required — availability, errors, latency, throughput, model
load, tokens, and resource use — and each must be covered by at least one metric that
is not deferred. An eighth family, identity, is carried by a single `_build_info`
gauge whose labels are the immutable versions.

The alternative was to emit identity as labels on every metric, which is what makes
"record immutable versions" and "keep the cardinality budget" look like conflicting
requirements. They are not: one identity series answers the question once, and every
other metric joins to it. Putting the release identifier on the request counter
multiplies that counter by the release history for information that is constant
within a process.

Three more metrics are defined and deferred with reasons rather than omitted, because
an omitted metric gets reinvented under a different name. Time to first token is
deferred because V1 has no streaming path and it would be the same measurement as
request duration; a retry counter is deferred because there is no retry path and a
counter that can only read zero looks like a healthy system rather than an absent
feature; a cost-record counter is deferred because no cost method exists, and defining one
is a separate decision that has not been taken.

Two structural choices carry the reasoning that generalises:

**Two counters instead of one.** Requests are counted by outcome; errors are counted
by canonical code. Carrying both dimensions on one counter multiplies to tens of
thousands of series to answer two questions that are never asked simultaneously —
first how much is broken, then what is broken.

**No outcome label on the latency histogram.** A histogram's series count is its
label product multiplied by its bucket count, which makes it the most expensive
instrument on the endpoint. The budget buys bucket resolution rather than a
breakdown the error counter already provides.

## D4 — A cardinality budget that is recomputed, not asserted

Each metric declares a maximum series count. The suite recomputes it from the
declared bound of each label, multiplied by bucket count plus two for a histogram,
and fails if the declared and computed numbers disagree, if a metric exceeds 2,000
series, or if the active catalog exceeds 10,000.

The alternative was a written guideline — "keep labels bounded" — which is what every
project has and what no project checks. Recomputation makes adding a label a visible
number in a diff instead of a line of code.

Its honest limit: this is arithmetic over declared bounds, not a measurement. It
establishes that the catalog is internally affordable on the single-node environment
this project targets. No store has been tested with it, and the declared bounds are
estimates — the error-code bound in particular, because the canonical error
vocabulary for inference is not published yet.

## D5 — Structured logs with no free-form message field

A log record is one JSON object per line with a required field set and a bounded
`inferops.event` identifier. There is **no** message field.

That is the unusual part and it is deliberate. Prose that varies per request is the
field into which a caller's data eventually arrives — it is where an exception's
string representation goes, and where "request failed for prompt: ..." is one
formatting change away. It is also the field no query can match on reliably, so its
removal costs less than it appears to.

The alternative was a message field with a redaction filter over it. It was rejected
because a filter is a list of patterns, a list of patterns is the forbidden-field
list again, and this time it runs at the moment of writing rather than at review.

**Not decided, and not claimed:** there is no logger, no formatter, and no redacting
sink. No log line has ever been inspected, because none has been written.

## D6 — Four evidence templates with seven mandatory sections

An experiment template, an environment template, a raw-result template, and a
claim-and-evidence template, each carrying classification, provenance, environment,
method, results, limitations, and authorisation. A test reads each template and
fails if a section is missing or duplicated.

The experiment template does one thing the others do not: sections 1 to 4 are written
**before** the run. That ordering is what separates a measurement from a search for a
number that supports what was already believed, and this project has already been in
the position it protects against — ADR 0002 narrowed a threshold after seeing the
measurement, recorded that it had done so, and is weaker for it.

The alternative was one general template. It was rejected because the four record
different things at different times: what will be measured, what it ran on, what came
out, and what may therefore be claimed. Collapsing them produces a document where the
method is written after the results.

A template has produced no record, the catalog records that count as zero, and a test
refuses any attempt to cite a template path as evidence.

## D7 — Content capture: not decided

Prompts, responses, chat histories, and provider error bodies are not captured, and
there is no configuration flag to enable capture. Five artifacts would have to exist
first: a data classification, a redaction specification, a stated retention window
shorter than the metric store's, an access control, and a documented lawful basis
with a subject-deletion path.

None exists. A flag with none of them behind it is not a configuration option — it is
the whole decision, delegated to whoever sets it during an incident.

## D8 — The telemetry toolchain: not decided here

No SDK, exporter, collector, store, dashboard, or alerting path is selected.
[ADR 0004](ADR-0004-component-and-ownership-boundaries.md) already records that
nobody owns a telemetry collector and defers the question deliberately. This record
does not answer it, and the catalog is written against no vendor's conventions except
the OpenTelemetry attribute names, which are used because they cost nothing to adopt
and would cost a rename to avoid.

## Consequences

- The first component that emits anything has a list to emit from, a budget to stay
  inside, and a classification step it cannot skip.
- A field with no declared classes cannot be placed anywhere, which makes adding a
  signal slower on purpose.
- Three signals are deferred with reasons, so reinstating one means deleting a
  deferral rather than adding a metric quietly.
- The runtime's missing request counter is now recorded in two places — the
  feasibility record and this catalog — with the platform metric that covers it named
  in both.
- The claim and test matrix gains one claim, certified at `C0` by the documentation
  layer: that the catalog cannot admit a prompt, a secret, or an unbounded metric
  label. It certifies the catalog, and nothing about a running system.
- Nothing here reduces the work of the first real telemetry change. It reduces the
  number of decisions that change is allowed to make on its own.

## Compatibility impact

None to any published interface. The workload contract, the rejection interface, and
the ownership inventory are unchanged. The test strategy gains one claim row and one
path on an existing layer; no layer, lane, marker, or certification level changes.

Attribute and metric names are published here for the first time and are versioned
as `v1alpha1`. Renaming one after a component emits it would be a breaking change for
any dashboard or query built on it; today nothing emits and nothing queries, which is
the cheapest moment there will ever be to get the names wrong and fix them.

## Security considerations

This record is mostly a security decision wearing an operations hat.

The two content classes have empty placement lists, so a prompt, a response, a
provider error body, a secret value, an authorization header, and any value read out
of a submitted document have nowhere they may be written. The workload contract
validator already refuses to repeat a document's value back to the caller; the same
rule now covers logs, metrics, spans, and committed records.

Two rules are enforced by **review alone** and are marked as such: that an upstream
error body is not passed through verbatim, and that no operating figure is published
as a benchmark. Both need code or human judgement that no test can supply, and
labelling them as tested would have been the more comfortable and less true option.

The residual risk is stated plainly: none of this is enforced at runtime, because
there is no runtime. A redacting sink, a field allowlist in code, and a test that
inspects a real log line are all future work, and no claim here should be read as
covering them.

## Evidence

[The change validation record](../../proof/telemetry/v1-s0-007-pr1-validation.md),
which is local static evidence for this change: the catalog is internally consistent
under every rule the suite states, deliberate corruptions of it are each refused,
every runtime series named here appears in the record that measured it, every
relative link resolves, and the existing suites are unchanged.

The native runtime series come from
[the runtime feasibility record](../../proof/serving/v1-s0-003-pr2-runtime-feasibility.md),
executed on 2026-08-24 on one host — `local-real-cpu` evidence for what that runtime
exposes, and evidence for nothing else here.

There is no evidence that any signal in this catalog has ever been emitted, because
none has.
