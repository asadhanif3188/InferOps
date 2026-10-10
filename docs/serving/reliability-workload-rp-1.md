# The RP-1 reliability workload

Status: **defined and checked by `V2-S5-001-PR1`. No run has executed under it, and no
runner reads it yet.** The versioned profile
[`rp-1-profile.v1.json`](../../deploy/serving/reliability/rp-1-profile.v1.json) states
what one caller request is, how many callers send it, and what counts as a success.
The [`tools.reliability_profile`](../../tools/reliability_profile/) command loads the
profile and compares it with the
[V1 load profile](../../deploy/serving/load/llm-load-profile.v1.json) that it pins.
This is static evidence at C0. It registers no claim. The validation record is
[`v2-s5-001-pr1-validation.md`](../proof/serving/v2-s5-001-pr1-validation.md).

> [!WARNING]
> **RP-1 is a reliability workload. It is not a representative production workload,
> an overload test, or a benchmark.** The profile carries this sentence in its
> `boundary` member, and the loader refuses a profile that states another one:
>
> RP-1 is a reliability workload: one fixed public request, sent by two closed-loop workers. It is not a representative production workload, an overload test, or a benchmark. Concurrency 2 is a fixed choice and not a measured threshold. No figure from a run under it is a portable capacity figure or a production SLO.

## What RP-1 is for

A reliability experiment asks what a caller sees while something fails and recovers.
The answer needs a caller workload that is the same in each run. RP-1 is that
workload. It fixes the request, the number of callers, the deadline, and the success
rule, so that two runs differ only in what the experiment changes.

RP-1 does not ask how much load a release can serve. It has one concurrency and no
rising levels. It compares nothing with another level.

## What the profile fixes

| Setting | Committed value | Origin |
|---|---|---|
| Profile | `RP-1`, revision 1 | This change |
| Fixture | `llm-load-single-turn-v1`: one `user` message | The V1 load profile, unchanged |
| Request | `POST /v1/chat/completions`, `Content-Type: application/json`, model `qwen3-1-7b-q8-0`, `stream: false` | The V1 load profile and the V1 load harness, unchanged |
| Request headers | `X-InferOps-Request-ID`, one value for each request, and `X-InferOps-Correlation-ID`, one value for each run | The V1 load harness, unchanged. The profile fixes the header names and not the values |
| Generation | `maxOutputTokens` 128, `temperature` 0, `contextSizeTokens` 4096, `parallelSlots` 1 | The V1 load profile, unchanged |
| Sampling seed | `not-set` | No committed record sets one |
| Client deadline | 150,000 ms for each request | The V1 load profile, unchanged |
| Success | HTTP 200, adapter `real`, model `qwen3-1-7b-q8-0`, usage counts present, answer within the deadline | The V1 load profile and the V1 classification. The V1 runtime-name rule is not carried |
| Connection | A new connection for each request, no redirect followed, no proxy variable read, no retry | The V1 transport, unchanged |
| Concurrency | 2 | A fixed choice. It is the concurrency of the V1 level `c2` |
| Loop | Closed: each worker sends, waits for the answer, and sends again | The V1 load harness, unchanged |
| Caller location | Inside the cluster | Changed. The V1 harness runs on the operator host |
| Target | The API Service, over plain HTTP. Not a pod address and not a port-forward | Changed. The V1 harness targets a loopback forward |
| Evidence level ceiling | `C2` | The V1 load profile, unchanged |
| Results | No prompt text and no completion text | The V1 raw record, unchanged |

`python -m tools.reliability_profile check` prints the same values from the file.

### The prompt

The fixture sends this one message in each request:

> You are a terse assistant. Answer in at most two sentences. Name three things a Kubernetes readiness probe is for.

The text is public: it is committed in the V1 load profile. It holds no personal
data and no secret. A result under RP-1 does not repeat it: a result names the
fixture identifier.

### Why the generation settings are not sent

The API accepts only `model`, `messages`, and `stream`. The output token limit and
the temperature belong to the release and not to the request. The profile records
them, and it states `sentInRequest: false`. The V1 loader compares the same four
values with [the runtime profile](runtime-profile.local.v1.json) and with the chart
values, and this profile is compared with the V1 profile. So a drift in the chart
defaults refuses this profile through the V1 loader.

### What the randomness setting is

The committed runtime arguments set `--temp 0`. No committed runtime argument and
no chart file sets a sampling seed, so the profile states `samplingSeed: not-set`.
The suite holds both facts against
[the runtime profile](runtime-profile.local.v1.json) and the chart files. **This repository has not
checked that two completions of the fixture are the same text.** RP-1 fixes the
settings. It does not establish a deterministic output.

### Why the deadline is 150,000 ms

It is the V1 value. The API's own deadline is `api.requestTimeoutMs`, 120,000 ms,
and the V1 loader refuses a client deadline that is not above it. A client deadline
below the API's would end a slow completion at the client, and the answer of the
platform at its own deadline would not be seen.
[The load generation guide](llm-load-generation.md#why-the-deadline-is-above-the-apis)
states what that answer usually is.

An answer that arrives after the deadline is not a success, whatever it says. The
V1 classification gives it the outcome `timeout`, and the suite holds that.

### Why concurrency 2

- Two requests can be in flight at one time, so one slow request does not stop
  every caller observation.
- One concurrency keeps a run from becoming a measurement of concurrency scaling.
- The V1 load harness already ran this concurrency as its level `c2`.

**Concurrency 2 is not a measured threshold.** No overload point is derived from it.
The profile does not establish that two requests reach two runtime pods: a Service
selects the pod, and the profile does not.

Each runtime replica has one parallel slot. With one runtime replica, the second
request waits in the runtime, and its latency includes that wait. With two runtime
replicas, a request can also wait when both requests reach one replica.

The value is a constant in `tools.reliability_profile.core`. The profile cannot
choose another value. A change of the concurrency is a new revision of the profile,
a new registered digest, and a change to that constant.

## What RP-1 does not carry from the V1 load profile

The profile gives each member of the V1 file one disposition, in
`sourceDisposition`. The loader refuses a profile that leaves one out.

| V1 member | Disposition | Reason |
|---|---|---|
| `schemaVersion` | reused | The same schema version string |
| `profileId` | pinned | Stated in `source`, beside the content digest of the V1 file |
| `profileVersion` | pinned | Stated in `source`, beside the content digest of the V1 file |
| `evidenceClass` | not-carried | A profile names no environment. A run states the environment it executed in |
| `evidenceLabel` | not-carried | A profile names no environment. A run states the environment it executed in |
| `certificationCeiling` | reused | The same level, C2, in `evidenceLevelCeiling`. The workload is not representative, so a run under it cannot support C3 |
| `productionBenchmark` | reused | The same value, `false` |
| `portableCapacityClaim` | reused | The same value, `false` |
| `boundary` | changed | The V1 sentence bounds a load observation. RP-1 states its own sentence, which also denies a representative workload and an overload test |
| `boundariesRef` | reused | The same document |
| `providerContractRef` | not-carried | A profile names no provider. A run states the provider it executed on |
| `release` | not-carried | The V1 loader compares the V1 profile with the chart and the runtime profile. RP-1 is compared with the V1 profile, and it repeats no chart reference |
| `target` | changed | The V1 profile targets a loopback forward, which reaches one selected pod. RP-1 targets the API Service from inside the cluster. The V1 identity probe is part of the shape of a V1 run, and it is not carried |
| `fixture` | reused | The same fixture identifier, request path, model, stream flag, and messages |
| `generation` | reused | The same four values |
| `warmup` | not-carried | RP-1 has no warm-up phase. Each request that a caller sends is a caller result |
| `levels` | changed | The V1 profile rises through concurrency 1, 2, and 4. RP-1 has one fixed concurrency, 2 |
| `measured` | not-carried | RP-1 states no duration and no request ceiling. The experiment that selects the profile bounds its run |
| `timeouts` | reused | The same client deadline |
| `success` | reused-in-part | The same status, adapter kind, model reference, and usage rule. `requiredRuntimeName` is not carried: the V1 harness requires it of the identity probe, and not of an answer |
| `results` | not-carried | RP-1 states no result layout and no percentile. It states only that a result holds no prompt text and no completion text |

Two rules of the V1 harness are in its code and not in its profile. RP-1 carries
neither, and this page says so because the profile has no member for them:

- **The transport-lost stop.** The V1 harness ends a run after five transport errors
  in a row. A reliability experiment can delete a pod on purpose, and transport
  errors are then part of what a caller sees. RP-1 states no stop rule. The
  experiment that selects the profile states its abort conditions.
- **The outcome names.** The V1 harness gives each request one of six outcomes.
  RP-1 fixes what a success is. It does not fix the names of the failures or the
  format of a caller result.

## If the V1 load profile changes

The profile pins the V1 file by the SHA-256 of its bytes, with each CRLF replaced by
LF:

| File | Content digest |
|---|---|
| [`deploy/serving/load/llm-load-profile.v1.json`](../../deploy/serving/load/llm-load-profile.v1.json), version `1.0.0` | `4dc0fe4a4217f035875fcddbdb99b75246f3a74188d5eca8b4dbbec8f57081c5` |
| [`deploy/serving/reliability/rp-1-profile.v1.json`](../../deploy/serving/reliability/rp-1-profile.v1.json), revision 1 | `853b6e92c8ef45790a80756fffa4d5001fcc572dac95fc86625613eda70deb22` |

A change of one byte of the V1 file refuses RP-1, with the rule
`rp1-source-pin-differs`. The V1 file at the `v1.0.0` tag has the pinned digest.

To accept a changed V1 file, or to change a value of RP-1:

1. Edit the profile, and add 1 to `profileRevision`.
2. State the difference from the earlier revision on this page.
3. Add the new revision and its digest to `REGISTERED_REVISIONS` in
   `tools.reliability_profile.core`. Do not change the digest of an earlier revision.
4. Do this before a run uses the revision. A run that used an earlier revision
   keeps that revision.

**The registered digest is a tripwire and not a lock.** A change that edits the
profile and the registered digest together passes the check. The digest makes such
a change visible in two files, and a reviewer reads both.

No experiment freeze record selects RP-1 yet. A
[freeze record](../proof/experiments/README.md) that selects it states the revision
in its `callerProfileRevision` field.

## The rules

The loader applies 16 rules in this order, and it stops at the first rule that
refuses. The message starts with the rule.

| Order | Rule | Refuses |
|---:|---|---|
| 1 | `rp1-profile-unreadable` | A file that is absent, is not JSON, or is not an object |
| 2 | `rp1-members-unsupported` | A member that is missing, is unknown, or has another type, in each section |
| 3 | `rp1-identity-unsupported` | Another schema version, kind, or profile identifier, or a revision that the tool does not register |
| 4 | `rp1-purpose-overstated` | A workload class other than `reliability`, a ceiling other than `C2`, one of the four flags set to `true`, another boundary sentence, or another boundaries document |
| 5 | `rp1-source-refused` | A V1 load profile that its own loader refuses |
| 6 | `rp1-source-pin-differs` | A V1 load profile whose path, identifier, version, or content digest is not the pinned one |
| 7 | `rp1-concurrency-not-fixed` | A caller that is not two closed-loop workers inside the cluster, or a V1 profile with no level at that concurrency |
| 8 | `rp1-target-not-api-service` | A target that is not the API Service over plain HTTP, or that allows a pod address or a port-forward |
| 9 | `rp1-request-differs` | A fixture identifier, method, path, content type, header name, or body that is not what the V1 harness sends |
| 10 | `rp1-generation-differs` | A generation value that is not the V1 value, a sampling seed, or a statement that the request sends the settings |
| 11 | `rp1-connection-differs` | A connection behaviour that is not the V1 transport's |
| 12 | `rp1-timeout-differs` | A client deadline that is not the V1 value, or an answer after the deadline stated as a success |
| 13 | `rp1-success-differs` | A status, adapter kind, model reference, or usage rule that is not the V1 value |
| 14 | `rp1-results-hold-content` | A statement that a result holds prompt text or completion text |
| 15 | `rp1-disposition-incomplete` | A V1 member with no disposition, with two, or with one that is not registered, and a disposition for a member the V1 file does not state |
| 16 | `rp1-revision-digest-differs` | A profile whose content digest is not the digest registered for its revision |

Rules 8, 11, and 14 compare the profile with constants in the tool. They hold the
statement of the profile. They do not inspect a runner, because no runner exists
yet. The suite holds the constants of rule 11 against the V1 transport over
loopback HTTP.

## Commands

From the repository root, inside the locked environment
(`uv run --locked python -m ...`).

```text
python -m tools.reliability_profile check
```

The command reads committed files and writes nothing. It sends no request, it
contacts no cluster, and it reads no model byte. Exit status `0` says that each rule
accepted the profile. Exit status `3` says that one rule refused it. Exit status `2`
says that the arguments are not usable.

The suite is
[`tests/serving/test_reliability_profile.py`](../../tests/serving/test_reliability_profile.py).

## What this does not establish

- Nothing about a caller. No request was sent under RP-1.
- Nothing about a runner. No tool sends RP-1 yet. The target, the caller location,
  and the connection behaviour are statements that a runner must meet. No check
  inspects a runner.
- Nothing about the values a delivered release receives. The V1 loader compares the
  generation settings and the API deadline with the chart defaults and the
  real-profile values. It does not read the values of an environment's desired
  state, and an overlay can change them.
- Nothing about deterministic output. The settings are fixed. The text of two
  completions was not compared.
- Nothing about varied prompts. Each request sends the same fixture, so the prompt
  cache of the runtime can make prompt processing nearly free after the first
  request.
- Nothing about capacity, overload, or a threshold. Concurrency 2 is a choice.
- Nothing about a representative workload. A run under RP-1 cannot support C3.
- Nothing about how a Service spreads two requests across pods.
