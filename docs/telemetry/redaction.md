# Redaction rules and the content-capture boundary

Status: **accepted rule, and now enforced in code as well as in the catalog**, in
[ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md).
The exclusions below are checked against the committed catalog by
[`tests/telemetry/`](../../tests/telemetry/), and — since the InferOps API began
emitting — against the two places a signal is actually created: a metric is refused
at declaration if it names a label the catalog forbids, and a log record is built
through an allowlist that has no name for anything on the list below.

That distinction is the whole reason this document exists separately from
[the catalog](telemetry-catalog.md). A catalog says what is emitted. This says what
is not, and why the absence has to be structural rather than remembered.

## The default

Prompts, responses, chat histories, and provider error bodies are **not captured**.
Not sampled, not truncated, not hashed into a field a determined reader could
attack — absent.

This is the default because the alternative default cannot be undone. A metric label
or a log field that should not have been written is not fixed by deleting the code
that wrote it; it is fixed by finding every store that received it, within a
retention window nobody was tracking, before anyone reads it. A capture that never
happened needs none of that.

## What is excluded, and why each one is tempting

An exclusion list made of things nobody wanted to log is not a control. These are
the six that somebody will have a good reason to add.

| Field | Class | Why it is tempting |
|---|---|---|
| `prompt` | `user-content` | It is the single most useful thing to have when reproducing a bad answer, which is exactly why it ends up in a log line during an incident and stays there afterwards |
| `completion` | `user-content` | A truncated response looks harmless and is not: a prefix of a customer's data is a customer's data, and truncation is not redaction |
| `provider-error-body` | `user-content` | It is the surface most likely to be logged, pasted into a ticket, and kept — and a runtime that echoes the offending input into its error text turns a pass-through into a content capture nobody decided on |
| `secret-value` | `secret` | A debugging session wants to know whether the credential was the right one, and the fastest way to answer that is the one that publishes it |
| `authorization-header` | `secret` | Whole-header logging is a one-line change that captures this without anyone choosing to |
| `document-value` | `user-content` | Quoting the offending value makes an error message clearer, and it is how a secret placed in the wrong field gets copied into a log store |

The last one already has a precedent in this repository. The workload contract
validator refuses to repeat a value read out of a document back to the caller: it
publishes the field location and the rule identifier, never the value. A log record
is the same surface with a longer memory, and the same rule applies to it.

## How the exclusions hold

The two content classes have an empty placement list. Not a short one — an empty
one. Because a field's placement is the intersection of what its sensitivity class
and its cardinality class permit, a field in either class has nowhere it may be
written, and adding one to the catalog with any placement at all fails the suite.

That is the mechanism in the catalog. It replaces the thing that does not work,
which is a list of forbidden fields that a reviewer has to remember at the moment
somebody adds a seventh.

**The same mechanism now holds one layer lower down.** A log record is built through
an allowlist of the attribute names the catalog publishes, and none of the six above
is one of them — so there is no key a prompt could be written under, no free-form
message field to hide one in, no `extra` mapping, and no pass-through to the
encoder. A field name outside the allowlist is refused, and the refusal names the
field and never the value beside it: the rejected field is by definition the one most
likely to be carrying something that may not be repeated. A metric is the same story
in the other direction — a label name outside the set the catalog permits is refused
when the metric is declared, before a single series exists.

Neither of those is a filter over a value. A filter is a list of patterns, a list of
patterns is the forbidden-field list again, and this time it runs at the moment of
writing rather than at review. What is here instead is an absence: the field has no
name, so there is nothing to filter.

## Every rule, and whether it is really enforced

Sixteen rules are enforced by a test. Thirteen of them read the committed catalog;
three read what the distribution declares and what it refuses. Two are enforced by
review alone, and are marked as such rather than quietly promoted.

| Rule | Enforced by |
|---|---|
| `no-user-content-is-telemetry` | a test |
| `no-secret-is-telemetry` | a test |
| `no-unbounded-value-is-a-metric-label` | a test |
| `no-request-identifier-is-a-metric-label` | a test |
| `no-tenant-identifier-is-a-metric-label-or-evidence-field` | a test |
| `identity-belongs-on-an-identity-metric` | a test |
| `placement-follows-sensitivity-and-cardinality` | a test |
| `every-signal-answers-a-stated-question` | a test |
| `every-metric-stays-inside-the-cardinality-budget` | a test |
| `every-required-family-is-covered` | a test |
| `a-deferred-signal-says-why` | a test |
| `no-runtime-series-is-claimed-that-was-not-measured` | a test |
| `content-capture-requires-a-policy-that-does-not-exist` | a test |
| `an-emitted-signal-agrees-with-this-catalog` | a test |
| `an-emitted-label-is-one-this-catalog-permits` | a test |
| `an-emitted-record-carries-only-published-fields` | a test |
| `no-provider-error-body-is-passed-through` | **review only** |
| `no-figure-here-is-a-published-benchmark` | **review only** |

The two review-only rules stay review-only. One is about what a person puts in a
document or a slide, which no test can reach. The other is about an upstream error
body, and it is worth being exact about why the API being instrumented does not
promote it: the API already refuses to forward an adapter's own message to a caller,
and a test holds that. What is not tested is the whole rule — that no upstream body
is logged verbatim anywhere, including by an adapter that is not instrumented yet.
Marking it as tested on the strength of the half that is would be the more
comfortable and less true option.

Each rule's test is named in the catalog data, and the suite fails if a rule names a
test that does not exist. A rule cannot claim enforcement it does not have.

## Enabling content capture

There is no flag. Capture is not a configuration option that defaults to off,
because a flag would be the entire decision, taken by whoever set it during an
incident.

Five artifacts have to exist first, and none does:

1. a data classification for what would be captured, written by someone entitled to
   classify it;
2. a redaction specification naming what is removed and what survives;
3. a stated retention window, shorter than the metric store's;
4. an access control naming who may read it;
5. a documented lawful basis and a subject-deletion path.

The fifth is the one that decides the shape of the other four, and it is not a
question this repository can answer for a deployment it does not run.

## Evidence records

A committed record under [`docs/proof/`](../proof/) is public and permanent, which
makes it a stricter surface than a log store rather than a looser one. Two rules
follow:

- A tenant identifier is a log field and a span attribute and is **not** written
  into an evidence record. The catalog enforces this through the sensitivity class,
  not through the author's judgement.
- Raw output that a claim depends on is promoted into a record **redacted**, before
  the lane's retention window closes. The retention boundary itself is
  [the test strategy's](../testing/test-strategy.md); what this document adds is
  that promotion is a redaction step and not a copy.

## What this does not establish

A record written by the API is now inspected: the suites drive the application, read
the records it wrote, and assert that a prompt, a completion, and a response body
appear in none of them. That is a real check against a real record, and it is the
check this document previously recorded as absent.

Three things it still does not establish, in the order they matter.

**Nothing has been checked against a store.** Records go to a stream and metrics wait
on an endpoint nobody scrapes. No log store, shipper, retention window, or access
rule is selected, so the retention the catalog requires to be stated before content
of any kind is written is still unstated.

**Only one emitter has been checked this way.** The serving-runtime adapter emits
nothing, so the rule about an upstream error body is a rule about code that has not
been written. The adapter is the component closest to a runtime's own words, which
makes it the one where that rule will matter most.

**No record has been produced against a real runtime.** Every record inspected so far
came from a deployment serving the committed mock, whose responses are a fixture. A
real runtime's error text is the input the pass-through rule exists for, and it has
not been through this code.
