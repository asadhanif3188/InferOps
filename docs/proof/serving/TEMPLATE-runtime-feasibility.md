# TEMPLATE — runtime and model feasibility record

This file is a **template**, not evidence. It records nothing and proves nothing.
Copy it to `v1-s0-00N-prN-<slug>.md` beside this file and fill it in; do not edit
this file to hold results.

Placeholders are written as `<...>`. A filled record must contain none of them: an
unfilled placeholder is an unanswered question, and leaving one in place publishes
it as though it were an answer.

It is the recording format for
[the runtime feasibility workflow](../../serving/feasibility-workflow.md), against
the thresholds in
[ADR 0002](../../architecture/decisions/0002-model-and-serving-runtime.md).

---

# `<work item>` runtime and model feasibility

Date: `<YYYY-MM-DD>`

Classification: `<local real runtime | documented and unexecuted | partial — stages N..M only>`.
Use the vocabulary in [CONTRIBUTING](../../../CONTRIBUTING.md) and pick the weakest
label the record actually supports.

Authorisation: `<who authorised the download and workload stages, and when — or "not obtained", with the stages that were therefore not run>`

Claim boundary: `<one paragraph: exactly what this record establishes and what it does not. If only some stages ran, say so here rather than only in the verdict table.>`

## Verdict

| Threshold | Verdict | Measured or observed | Note |
|---|---|---|---|
| T1 licence | `<met / not met / not executed>` | `<licence identifier, date read>` | |
| T2 immutable pins | `<...>` | `<image digest; model revision; file hashes verified?>` | |
| T3 memory fit | `<...>` | `<pod resident; container-VM total>` | Target: 3.0 GiB and 6.0 GiB |
| T4 disk fit | `<...>` | `<added disk; free space after>` | Target: 8 GB added, 5 GB free |
| T5 API shape | `<...>` | `<fields present in the response body>` | |
| T6 readiness semantics | `<...>` | `<not-ready observed during load? restarts during load?>` | |
| T7 metrics | `<...>` | `<series present / absent, by name>` | |
| T8 startup | `<...>` | `<cold worst case; warm worst case>` | Target: 180 s and 90 s |
| T9 latency floor | `<...>` | `<wall clock; derived decode rate>` | Target: 120 s and 2 tokens/s |
| T10 packaging and cleanup | `<...>` | `<non-root? privileged? residue after teardown?>` | |
| T11 no credential required | `<...>` | `<...>` | |
| T12 CPU path complete | `<...>` | `<...>` | |

**Overall:** `<candidate accepted / candidate rejected / trial blocked at stage N>`

A blocking threshold that is not met means the candidate is rejected, whatever the
rest of the table says. Record that plainly here.

## Environment

Repeat the environment even if another record already states it; a record must be
readable on its own.

| Component | Version or value | Source |
|---|---|---|
| Operating system | `<...>` | Measured |
| Container engine server | `<...>` | Measured |
| Cluster tool | `<...>` | Measured |
| Node image | `<digest>` | Measured, read back from the running node |
| kubectl client / server | `<...>` | Measured |
| Memory reaching the container VM | `<...>` | Measured |
| Processors reaching the container VM | `<...>` | Measured |
| CPU instruction set | `<...>` | Measured |
| Accelerator | `<...>` | Measured |
| Free space on target volume, before | `<...>` | Measured |

Host identifiers, machine names, user names, filesystem paths, and network
addresses are redacted here the same way
[the cluster smoke proof](../environment/v1-s0-002-pr2-cluster-smoke.md) redacts
them.

## Pins

| Artifact | Identifier | Verified how |
|---|---|---|
| Runtime image | `<repository@sha256:...>` | `<resolved from tag <tag> on <date>; read back from the running pod>` |
| Runtime licence | `<identifier>` | `<URL, date read>` |
| Model repository | `<publisher/name>` | |
| Model revision | `<commit revision>` | |
| Weight files | `<filename, size, sha256>` | `<hash verified after download? yes/no>` |
| Model licence | `<identifier>` | `<URL, date read>` |

If the runtime was deployed by tag rather than digest, T2 is not met. Say so;
do not describe the tag as a pin.

## Commands and results

Record each stage that ran, with the exact command and its actual output. Redact
host-specific values, and mark every redaction so a reader can see something was
removed.

### Stage 1 — pins

```text
<command>
<output>
```

### Stage 2 — acquisition

```text
<command>
<output>
```

Elapsed: `<...>`. Bytes transferred: `<...>`. Free space after: `<...>`.

### Stage 3 — deployment

```text
<command>
<output>
```

Resolved image digest as the cluster reports it: `<...>`
Security context as applied: `<runAsNonRoot, allowPrivilegeEscalation, capabilities>`
Requests and limits as applied: `<...>`

### Stage 4 — load and readiness

| Run | Kind | Container start to first ready | Not-ready observed during load | Restarts during load |
|---:|---|---:|---|---:|
| 1 | Cold | `<...>` | `<yes/no, and the response body seen>` | `<...>` |
| 2 | Cold | `<...>` | `<...>` | `<...>` |
| 3 | Cold | `<...>` | `<...>` | `<...>` |
| 4 | Warm | `<...>` | `<...>` | `<...>` |
| 5 | Warm | `<...>` | `<...>` | `<...>` |
| 6 | Warm | `<...>` | `<...>` | `<...>` |

Worst case cold: `<...>`. Worst case warm: `<...>`.

Model identity as the runtime reports it: `<...>`
Does it match the pinned revision? `<yes / no — and if no, that is the finding>`

### Stage 5 — inference

Requested from inside the cluster, through cluster DNS and the Service:
`<yes / no — if no, the platform path was not proven>`

Request, verbatim:

```text
<...>
```

Response, verbatim:

```text
<...>
```

| Run | Wall clock | Completion tokens reported | Derived decode rate |
|---:|---:|---:|---:|
| 1 | `<...>` | `<...>` | `<...>` (derived) |
| 2 | `<...>` | `<...>` | `<...>` (derived) |
| 3 | `<...>` | `<...>` | `<...>` (derived) |

The decode rate is derived from reported token counts and measured wall clock. It
is not a benchmark and must not be published as one.

Response shape against T5: `choices[0].message.content` `<present/absent>`;
`model` `<present/absent>`; `usage` token counts `<present/absent>`.

### Stage 6 — metrics

```text
<exposition, verbatim or a faithful excerpt>
```

| Required series | Present | Exact name |
|---|---|---|
| Request counter | `<yes/no>` | `<...>` |
| Prompt token counter | `<yes/no>` | `<...>` |
| Completion token counter | `<yes/no>` | `<...>` |

Series required but absent: `<... or "none">`

### Stage 7 — resources

| Measurement | Idle | After inference |
|---|---:|---:|
| Pod memory | `<...>` | `<...>` |
| Pod CPU | `<...>` | `<...>` |
| Container-VM memory in use | `<...>` | `<...>` |

Runtime image size as stored by the engine: `<...>`
Weights on disk: `<...>`
Free space on the target volume, after: `<...>`
Net disk change across the whole cycle: `<...>`

### Stage 8 — teardown and residue

```text
<commands and output for cluster list, context list, engine container list, engine volume list>
```

Residue found: `<none / describe it>`
Surviving by design: `<cached node image; cached weights; shared container network — with sizes>`

## Step-down

Did any step-down threshold fail? `<no / yes>`

If yes, record **both** attempts rather than replacing the first:

| Attempt | Model or quantisation | Failed threshold | Measured value |
|---:|---|---|---|
| 1 | `<...>` | `<...>` | `<...>` |
| 2 | `<...>` | `<...>` | `<...>` |

## Failures, surprises, and corrections

Record what went wrong, what the first attempt got wrong, and what was changed as a
result. A record with an empty section here is usually an incomplete record rather
than a flawless trial.

`<...>`

## Limitations

At minimum, state that this is one host, one architecture, one model revision, one
runtime digest, one point in time; that it is single-request throughout and
establishes nothing about throughput, concurrency, or model quality; and that a
local cluster is not a production environment.

`<any further limitation specific to this run>`

## What remains unproven

`<thresholds not executed, stages not run, and the authorisation or hardware needed to close them>`
