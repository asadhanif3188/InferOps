# TEMPLATE — raw result record

This file is a **template**, not evidence. It records nothing and proves nothing.
Copy it to a filled record beside the results it describes and fill it in. Do not
edit this file to hold results.

Placeholders are written as `<...>`. A filled record contains none of them.

This template describes a **machine-readable result set** — the output of a run,
rather than a person's summary of it. Its job is to make that output citable: what
it contains, what shape it is in, what was removed from it before it was committed,
and how a reader knows the file they are holding is the file that was produced.

Raw output that a claim depends on is promoted into a committed record, redacted,
before the producing lane's retention window closes. A lane artifact that has
expired cannot be cited, and this record is how it stops being a lane artifact.

The section headings below are required and are checked by
[`tests/telemetry/`](../../../tests/telemetry/). Add sections freely; do not remove
one, and do not repeat one.

---

# `<work item>` raw results

Date produced: `<YYYY-MM-DD>`

## Classification and certification

Evidence class: `<mock | synthetic | estimated | local-real-cpu | cloud-real-cpu | cloud-real-gpu>`

Ceiling this class carries: `<C0 | C1 | C2 | none>`.

Claim boundary: `<what these results are, and what they are not. A result set
produced against a mock is a mock result set however real its shape.>`

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `<git commit sha>` |
| Producing command | `<the exact invocation>` |
| Container image | `<name@sha256:...>` |
| Model artifact | `<repository, revision, per-file hash>` |
| Result file | `<path, size in bytes, sha256>` |

The result file's hash is what makes it the same file later. A result set without
one is a file somebody says came from a run.

## Environment

Either fill this in or cite an environment record that has:

`<link to the environment record, or the table from it>`

A result set with no environment behind it can be read but cannot be reproduced or
compared.

## Method

Schema of the result set:

| Field | Type | Units | Meaning |
|---|---|---|---|
| `<...>` | `<...>` | `<...>` | `<...>` |

Format: `<JSON Lines | CSV | JSON>`, `<encoding>`, `<one record per what>`.

Collection procedure:

```text
<warm-up, concurrency, duration or request count, timeout, and what counted as a
success — exactly as configured, not as intended>
```

What was removed before committing, and how:

```text
<prompts, responses, tenant identifiers, hostnames, absolute paths, credentials>
```

Redaction is a step with a command behind it. "Nothing sensitive was present" is a
finding, not a method — say how that was established.

## Results

| Summary | Value |
|---|---|
| Records | `<count>` |
| Successes / failures | `<...>` |
| Span covered | `<start and end timestamp, UTC>` |
| Aggregates | `<only those the project is permitted to publish>` |

> [!WARNING]
> V1 publishes no throughput, latency, capacity, or benchmark figure. A raw result
> set may be committed; a headline number drawn from it may not be published. See
> [the project boundaries](../../architecture/project-boundaries.md).

## Limitations

- `<what the run did not cover>`
- `<what varied between repetitions, and by how much>`
- `<known measurement error, clock skew, or warm-up contamination>`
- `<which claims must not cite this result set>`

## Authorisation

Required: `<yes / no>`.

Granted by: `<who, and when>`.

Retention: `<how long the unredacted source output is kept, where, and who may read
it>`. If unredacted output no longer exists, say so — that is the safer answer and
it needs to be on the record.
