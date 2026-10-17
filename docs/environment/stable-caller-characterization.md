# Q3: the stable caller characterization, and the Q4 bounds

Status: **the Q3 workflow and the Q4 formulas are frozen. One characterization has run,
[`q3-1`](../proof/experiments/v2-q3/runs/q3-1/result.md), and it is `REFUSED`: on
2026-10-16, at the commit `0307f7f`, its capacity reading was not of the environment of
`q1-1`, so the driver started no caller. No G has been measured, and no bound record
exists.** The engine's virtual machine had booted again since `q2-1`, and the memory that
it reports differed from `q1-1` by 12,288 bytes; [the run page](../proof/experiments/v2-q3/runs/q3-1/result.md)
states the reads. The synthetic directories of the suite show each refusal at C0.

Merging `V2-S6-002-PR2` keeps `q3-1` as a valid `REFUSED` attempt. It does not complete
`V2-S6-002`: G and the Q4 bounds are absent, the parent story's Q3 and Q4 criteria remain
open, and `V2-S6-003` is blocked until Sprint 6 change control decides the environment
identity and a matching chain of Q1, Q2, Q3, and Q4 exists. [The validation
record](../proof/environment/v2-s6-002-pr2-validation.md#merge-disposition) states the
disposition.

**Since `V2-S6-004-PR1`, the environment identity is decided, and revision 2 holds the
next characterization to `q1-2`.** [ADR 0021](../architecture/decisions/ADR-0021-environment-identity-is-configuration-memory-is-capacity.md) decides that the identity states
the configuration and that memory is a capacity fact. [Revision 2](../proof/experiments/v2-q3/freeze-r2.v1alpha1.json)
holds a characterization to the qualification `q1-2` of revision 2 of the Q1 freeze
record, compares the stable identity of its capacity reading with the one `q1-2` states,
and still requires the capacity gate to have accepted that reading. The rule of G and the
four formulas of Q4 are unchanged. No characterization has run under it, `q1-2` has not
run, G and the Q4 bounds are still absent, and `V2-S6-003` stays blocked. `q3-1` stays a
`REFUSED` record of revision 1.

Before a V2 reliability experiment runs, Q3 measures what the caller sees when the
topology of the release is healthy and no fault is injected. It runs the [RP-1 caller runner](../serving/reliability-runner.md)
once, for 360 s, against the API Service of the release that [the Q1 qualification
`q1-1`](environment-qualification.md) qualified, in the environment that `q1-1`
selected. It records the successful requests, the latency distribution, the gaps
between successive successes, and the canonical errors. **G is the p99 of those gaps.**
When fewer than 100 requests succeeded, G is the maximum gap. The result is
`CHARACTERIZED`, `INCONCLUSIVE`, or `REFUSED`.

Q4 then computes four bounds from S, which [Q2](runtime-startup-characterization.md)
states, and from G, by formulas that this freeze fixes before any Q3 characterization
runs. A later freeze record of a reliability experiment holds its runs to those bounds.

Q3 is a qualification and not a reliability experiment. It injects no fault. G is not a
throughput figure, a capacity figure, a latency target, or a service level, and no claim
cites it. **The Q4 bounds are experiment bounds, not production SLOs.**

| Property | Value |
|---|---|
| Freeze record | [`freeze-r2.v1alpha1.json`](../proof/experiments/v2-q3/freeze-r2.v1alpha1.json), experiment `v2-q3-stable-caller-characterization`, part `Q3`, criteria `Q3-AC1` to `Q3-AC14`. It also freezes the rule of G and the four formulas of Q4, unchanged from [revision 1](../proof/experiments/v2-q3/freeze-r1.v1alpha1.json), which governed `q3-1` and which it supersedes |
| Driver | [`q3-driver.txt`](../proof/experiments/v2-q3/procedure/q3-driver.txt), a pinned input of the freeze record, with the phases `up`, `characterize`, and `down` |
| Q3 tool | [`tools/caller_characterization`](../../tools/caller_characterization/core.py): `python -m tools.caller_characterization DIRECTORY`, `--preconditions DIRECTORY`, and `--check` |
| Q4 tool | [`tools/experiment_bounds`](../../tools/experiment_bounds/core.py): `python -m tools.experiment_bounds STARTUP_RECORD CALLER_RECORD` and `--check`. A pinned input of the Q3 freeze record |
| Tests | [`tests/domain/test_caller_characterization.py`](../../tests/domain/test_caller_characterization.py) and [`tests/domain/test_experiment_bounds.py`](../../tests/domain/test_experiment_bounds.py) |
| Target | Under revision 2, the release that `q1-2` qualifies, in the stable environment identity that `q1-2` states: key `local-docker-desktop/support-assistant`, 2 API replicas, 2 runtime replicas, provider `docker-desktop`. Under revision 1, the release that `q1-1` qualified, environment `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461` |
| Caller | RP-1, revision 1: two closed-loop workers inside the cluster, one fixed request, to the API Service. Duration 360 s, request ceiling 2000 |
| Runs | One: [`q3-1`](../proof/experiments/v2-q3/runs/q3-1/result.md), `REFUSED` on `environment-qualified`, no caller started. A characterization is committed under `docs/proof/experiments/v2-q3/runs/q3-N/` |
| Bound records | None: no Q3 record is `CHARACTERIZED`. A bound record is committed as `docs/proof/experiments/v2-q4/bounds-rN.v1alpha1.json` |
| Validation records | [`v2-s6-002-pr2-validation.md`](../proof/environment/v2-s6-002-pr2-validation.md); [`v2-s6-004-pr1-validation.md`](../proof/environment/v2-s6-004-pr1-validation.md), revision 2 |

## Healthy is a state of the topology

**The caller does not decide whether the release is healthy.** The topology does, by
readings that the caller does not make:

- Before the caller starts, both Deployments state and report 2 Ready replicas at their
  current generation, and exactly 2 API pods and 2 runtime pods exist, each Ready and
  none being deleted. These are preconditions: when one is not held, the driver starts
  no caller.
- While the caller runs, a watch of the API pods and the runtime pods records every pod
  event. A rule holds that the stream shows no pod added, no pod deleted, and no pod that
  is not Ready or is being deleted.
- After the caller, the same 4 pods are Ready, each container states the restart count
  it stated before, and both Deployments report 2 Ready replicas at the generation that
  they stated before.

**A request that does not succeed is a caller result.** It is counted, its canonical
error code is counted, and it lengthens a gap. It is not a reason to refuse or to repeat
the characterization. A run in which the topology held and requests failed is
`CHARACTERIZED`, and its G is larger.

The watch reads the two tiers of the caller path. It does not read the telemetry
collector of the release, the delivery controller, or the node.

## What is measured

**A gap is from one success to the next.** The successful requests of the caller record
are ordered by their completion instant, `finishedAt`, and two of one instant by their
sequence number. A gap is the time from the completion of one to the completion of the
next. The time before the first success and after the last one is not a gap. A failed
request between two successes is inside the gap between them.

**The clock is the runner pod's wall clock, to one millisecond.** Each gap is a
difference of two instants of that one clock. No instant of the runner is compared with
an instant of the host or of the cluster.

**G is the nearest-rank p99.** The gaps are sorted in ascending order, and G is the gap
at rank `ceil(0.99 * n)` of the `n` gaps. With fewer than 100 successful requests, G is
the maximum gap, and the record states `percentileMeaningful: false`. A record that is
not `CHARACTERIZED` states no G.

**The record also states what the caller saw**: the number of requests, of successes,
and of each outcome; the count of each canonical error code; the nearest-rank p50, p90,
and p99, the minimum, and the maximum of the latency of the successful requests, from the
runner's monotonic clock; and the same figures of the gaps. It states no rate and no
throughput.

## The Q4 formulas

The Q3 freeze record fixes these formulas before any Q3 characterization runs, and
`tools/experiment_bounds`, a pinned input of that record, computes them:

| Bound | Formula |
|---|---|
| `runtime_start_bound_ms` | `S` |
| `caller_gap_reference_ms` | `G` |
| `reversal_recovery_bound_ms` | `(2 * S) + 30000` |
| `caller_total_unavailability_bound_ms` | `max(2 * G, 5000)` |

The tool reads one committed Q2 record and one committed Q3 record. It states the bounds
only when each source record is in its committed directory, names that characterization,
is `CHARACTERIZED` with each rule held, states its bound as a whole number of
milliseconds, and names a registered freeze record of its kind whose content the checkout
holds; and when the two state the same provider, environment digest, release identifier,
and qualification record. Otherwise it prints no record and exits 5, with one of five
rules:

| Rule | Statement |
|---|---|
| `bounds-source-unreadable` | Each source record is a committed file that holds one JSON object. |
| `bounds-source-misplaced` | Each source record is the record of its committed characterization directory, and it names that characterization. |
| `bounds-source-not-characterized` | Each source record is of its schema, CHARACTERIZED with each rule held, and states its bound as a whole number of milliseconds. |
| `bounds-source-unfrozen` | Each source record names a registered freeze record of its kind, with the content that the checkout holds. |
| `bounds-environment-differs` | The two source records state the same provider, environment digest, release identifier, and qualification record. |

The bound record states each bound with its formula and value, the path and the content
digest of each source record and of its freeze record, the executing commit of each
characterization, the shared environment, a boundary sentence, and what it does not
establish. `--check` builds each committed bound record again from the two source records
that it names, and compares the bytes. So a change of a source record, or of a freeze
record that one names, fails the check.

**A bound can rest on the maximum gap.** When fewer than 100 requests succeeded, G is
the maximum gap, as the freeze record of Q3 states, and the bound record
states `percentileMeaningful: false` beside G. The Q4 tool does not refuse such a G. It
states it, and a reader of the bound record sees it.

## A refusal is a result

**The first seven rules are preconditions.** When one is not held, the result is
`REFUSED`, and the driver starts no caller. They hold that the phase `up` completed, that
the working tree was clean, that the frozen inputs are at their pins, that the delivery
paths equal the desired revision, that the environment, the release, and the runtime image
are those of `q1-1`, that the API Deployment runs the API image that the phase `up`
declared, and that the topology is Ready. The driver asks the tool for the preconditions,
with `--preconditions`, before it starts the caller.

**The other rules decide the measurement.** When each precondition is held and one of
them is not, the result is `INCONCLUSIVE`, and the record states no G.

**Every characterization is kept.** A characterization is never repeated for a lower or
a higher G. A later characterization runs only after the environment or a frozen input
changes, and it takes the next identifier. When a frozen input changes, a new revision
of the freeze record comes first.

**A read that was not made is not a value.** A source that is absent gives the state
`not-observed` to each rule that reads it. A source of another form gives `not-held`.

## The procedure

The driver runs from the committed tree with a clean working tree. It writes only under
`.artifacts/`.

1. **`up RUN`** runs the phase `up` of [the Q1 driver](../proof/experiments/v2-q1/procedure/q1-driver.txt)
   without a change, as Q2 does.
2. **`characterize RUN q3-N`** reads the executing commit, the working tree, the remote
   main as the desired revision, whether the chart, the desired-state tree, and the
   controller manifests equal those of that revision, and whether the freeze tool lists a
   changed material file of the Q3 or of the Q1 record, and it copies the capacity
   collection that the phase `up` read before the apply. When the phase `up` refused, or
   one of these is not at its state, it reads no cluster state and starts no caller.
   Otherwise it resolves the provenance of the target release, reads the Deployments and
   the API pods and runtime pods, and asks the tool for the preconditions. When each is
   held, it starts the watch of the two tiers and waits until it lists 4 pods, at most
   30 s; starts the caller run; waits for its Job, at most 900 s; collects the caller
   record; removes the objects of the run; waits 10 s more and stops the watch; and reads
   the Deployments and the pods again. It then writes the header and runs the tool. It
   keeps the record when the tool exits 0, 5, or 6.
3. **`down RUN`** runs the phase `down` of the Q1 driver without a change.
4. **The bound record** is built after a `CHARACTERIZED` record is committed:
   `python -m tools.experiment_bounds` with the path of the Q2 record and of the Q3 record,
   written to the next `bounds-rN.v1alpha1.json`.

**The driver states no result and no G.** The tool states them.

**The wait for the watch does not stop the driver.** When the watch lists fewer than 4
pods after 30 s, the driver starts the caller anyway, and `stream-complete` reads what the
watch recorded. The driver stops its watch when it ends early, with a trap. It does not
remove the objects of an interrupted caller run: the `cleanup` action of the runner script
does.

## The directory

The phase `characterize` writes one directory, `.artifacts/v2-q3/RUN-driver/q3-N/`. A
committed characterization adds `transcript.txt` and its page, `result.md`.

| File | What it holds | Written by |
|---|---|---|
| `run.json` | The header. Schema `inferops.io/caller-characterization-collection/v1alpha1` | The driver |
| `started-at` | The start instant of the characterization, which the header restates | The driver |
| `capacity/record.v1alpha1.json` | The capacity record of the reading that the phase `up` took before the apply, in its collection; a committed characterization omits `capacity/pods.json` | [The capacity gate](capacity-preflight.md) |
| `provenance.json` | A list of one provenance record of the target release at the desired revision | [The provenance tool](desired-state-provenance.md) |
| `deployments.json`, `before.pods.json` | The Deployments of the release, and the API pods and runtime pods, before the caller | The driver |
| `watch.jsonl` | Every event of the watch of the API pods and the runtime pods, one on each line, in the order received | `kubectl` |
| `caller-run.json` | The host instants of the request, of the end of the Job, and of the start and stop of the watch, the state of the Job, and the exit status of the start, the collection, and the cleanup. Schema `inferops.io/caller-characterization-run/v1alpha1` | The driver |
| `plan.json`, `caller.jsonl` | The plan of the caller run, and the caller record that the runner script accepted. A refused record is kept as `caller.refused.jsonl` | [The runner script](../serving/reliability-runner.md) |
| `after.deployments.json`, `after.pods.json` | The Deployments and the pods after the caller | The driver |
| `record.v1alpha1.json` | The Q3 record. Schema `inferops.io/caller-characterization/v1alpha1` | This tool |

The header states exactly the members of the Q2 header, with `characterizationId`
`q3-N`. A header with another member, an absent member, or an unusable value is not a
header: the command prints no record and exits 1.

## The record

| Member | What it states |
|---|---|
| `result` | `CHARACTERIZED` when every rule is held, `REFUSED` when a precondition is not held, and `INCONCLUSIVE` otherwise |
| `notHeld` | The categories of the rules that are not held, in the order below, and the rules |
| `collection` | The header |
| `target` | The release key, the two replica counts, the provider, the caller duration and ceiling, and the least run length |
| `identities` | The executing commit, the desired revision, the release key and identifier, the API image digest, the runtime image, the provider, the server version, the environment digest, the caller profile, the digests of the runner file and of the plan, the record of the qualification with its digest (`q1-1` under revision 1, `q1-2` under revision 2), and the freeze record that the header names, with its digest |
| `environment` | The environment identity, computed from the capacity record as the Q1 tool computes it for the Q1 revision of the lineage: exact under revision 1, stable under revision 2 |
| `measurement` | The gap, the clock, the latency, and the percentile method |
| `caller` | What the caller saw, when the runner's reader accepts the record: counts, outcomes, canonical errors, latency and gap figures, and the first and last success. Null otherwise |
| `bound` | G: the symbol, the rule (`p99` or `maximum`), `valueMs`, the percentile, the method, the least number of successes, whether the percentile is meaningful, and the numbers of successes and gaps. Null values unless the result is `CHARACTERIZED` |
| `files` | The name and the SHA-256, with CRLF read as LF, of each file of the directory that the tool read |
| `findings` | The state of each rule, with its criterion, its category, and a detail |
| `doesNotEstablish` | What no record establishes |

The command exits 0 when the result is `CHARACTERIZED`, 5 when it is `REFUSED`, and 6
when it is `INCONCLUSIVE`. It exits 1 when the directory is not a characterization
directory, and 2 when the arguments are not usable. `--check` builds the record of each
committed directory again and compares it with the committed record.

**A record is built under the revision that its header names.** `procedure-frozen`
accepts each revision of the Q3 freeze record that the tool registers, in
`FREEZE_RECORDS`, and compares the header with the content of that revision. So a later
revision that registers itself does not refuse a characterization of revision 1 when
`--check` builds it again. Since revision 2 the tool also takes the qualification, its Q1
revision, and the rules from the revision that the header names, so `q3-1` is built
again under revision 1, with `q1-1` and the exact identity, and stays `REFUSED`. (Until
`V2-S6-004-PR1` the Q2 tool compared with its one revision, and its page stated that
gap. Revision 3 of Q2 closes it.)

## The rules

14 rules. Each is required, and each is one acceptance criterion of the freeze record,
with the same identifier and statement. A rule is `held`, `not-held`, or `not-observed`.
The categories are `preparation`, `desired-state`, `environment`, `release-identity`,
`topology`, `caller`, `measurement`, and `evidence`, in that order. The table states
revision 2. Under revision 1, which governed `q3-1`, `environment-qualified` and
`release-qualified` name `q1-1`, and `environment-qualified` compares the environment
identity that the Q1 tool computed then, which holds memory to the byte.

| Rule | Criterion | Category | Refuses | Statement |
|---|---|---|---|---|
| `preparation-completed` | Q3-AC1 | `preparation` | yes | The phase up of the Q1 driver completed: it states no refusal, the target check refused nothing, and it ran at the executing commit of the characterization. |
| `working-tree-clean` | Q3-AC2 | `desired-state` | yes | The working tree was clean when the characterization started. |
| `procedure-frozen` | Q3-AC3 | `desired-state` | yes | The driver names a registered revision of the Q3 freeze record, that revision has the content that the checkout holds, and the freeze tool listed no changed material file of it or of the Q1 record when the characterization started. |
| `desired-revision-known` | Q3-AC4 | `desired-state` | yes | The desired revision is one full commit identifier, and the chart, the desired-state tree, and the controller manifests of the executing commit equal those of that revision. |
| `environment-qualified` | Q3-AC5 | `environment` | yes | The qualification q1-2 is QUALIFIED under revision 2 of the Q1 freeze record, the capacity gate accepted the target release key with 2 API replicas and 2 runtime replicas, and the stable environment identity of that capacity record has the digest that q1-2 states. |
| `release-qualified` | Q3-AC6 | `release-identity` | yes | The provenance record resolves the target release key at the desired revision to the release identifier that q1-2 states, the API Deployment runs the API image digest that the phase up declared, and the runtime Deployment runs the runtime image that q1-2 states. |
| `topology-ready` | Q3-AC7 | `topology` | yes | Before the caller started, the API Deployment and the runtime Deployment each state 2 replicas and report 2 replicas, 2 Ready, 2 available, and 2 updated at their current generation, and exactly 2 API pods and 2 runtime pods exist, each Ready and none being deleted. |
| `caller-run-completed` | Q3-AC8 | `caller` | no | The start of the caller run exited 0, its Job succeeded within the wait bound, the runner script collected its record, and the cleanup exited 0. |
| `caller-record-accepted` | Q3-AC9 | `caller` | no | The runner's reader accepts the caller record with its plan, in the mode in-cluster, for the Q3 experiment and the characterization identifier, with the release identifier of the provenance record declared, a duration of 360 s, and a request ceiling of 2000. |
| `five-minutes-run` | Q3-AC10 | `measurement` | no | The caller run ended at its duration of 360 s, not at its ceiling or at a stop request, and it lasted at least 300,000 ms. |
| `gaps-observed` | Q3-AC11 | `measurement` | no | The caller record holds at least 2 successful requests, so at least one gap between successive successes. |
| `stream-complete` | Q3-AC12 | `evidence` | no | The watch stream is a sequence of pod events of the API tier and the runtime tier with no ERROR event, it opens with one ADDED event for each pod of the reading before the caller, and the watch was started before the caller run was requested and stopped after the driver saw its Job end. |
| `topology-held` | Q3-AC13 | `topology` | no | While the caller ran, the watch stream shows no pod that the reading before does not list, no deleted pod, and no pod that is not Ready or is being deleted; after it, the same 4 pods are Ready with the restart count of each container that they had before, and both Deployments report 2 Ready replicas at the generation that they stated before. |
| `readings-in-order` | Q3-AC14 | `evidence` | no | The phase up started before the characterization, the caller run was requested after the characterization started, and the driver saw its Job end after it was requested and before the characterization finished. |

**`release-qualified` holds the API image to the digest that the phase `up` declared**,
as Q2 revision 2 does, for the same reason: the phase `up` builds the API image again, and
a build of unchanged inputs reports another manifest-list digest.

**`caller-run-completed` reads exit statuses that the driver wrote.** The cleanup action
of the runner script fails when an object of the run is still present, so its exit status
0 says that none was left when it looked.

**Two host instants are taken by the driver, not by the cluster.** `jobEndedAt` is the
instant at which the driver's poll, every 15 s, first saw the Job succeed or fail, so it
can be up to 15 s after the Job ended. `watchStartedAt` is the instant at which the
driver started `kubectl`, before the watch had listed a pod; `stream-complete` holds the
opening events of the stream to the pods of the reading before.

**`five-minutes-run` holds more than five minutes.** The runner's reader already refuses
a record that ends at its duration with less than the 360 s of its plan, so a record that
holds the rule lasted at least 360,000 ms. The rule states the least run length of Q3,
300,000 ms.

**`stream-complete` compares host instants only.** The watch instants and the caller run
instants are the host's. No rule compares the runner pod's clock with the host clock, so
no rule shows that every request of the caller record lies inside the watch. The order of
the driver's steps does: the watch starts before the runner `start`, and stops after the
Job ended and the cleanup returned.

## Measured gaps of the tool

These were found by the independent review of `V2-S6-002-PR2`, after the run of `q3-1`.
The tools and the driver are pinned inputs of revision 1, so each is stated here and left
for a later revision.

- **The environment is decided after the phase `up`.** `environment-qualified` reads the
  capacity reading that the phase `up` took before the apply, so a characterization in
  another environment is refused only after the release was prepared and applied. `q3-1`
  cost a full phase `up` and a full phase `down`. No step reads the environment before
  the phase `up`.
- **The environment identity compares memory exactly.** The identity that the Q1 tool
  computes holds each memory figure in bytes, and the digest compares it with no
  tolerance. On this host the figure changed at each of the two boots of the engine's
  virtual machine that were observed. [The Q1 page](environment-qualification.md#the-selected-environment)
  states the reads. **Decided by [ADR 0021](../architecture/decisions/ADR-0021-environment-identity-is-configuration-memory-is-capacity.md)** (`V2-S6-004-PR1`): revision 2
  compares the stable identity, which holds no memory figure, and the capacity gate
  decides memory for each reading. Revision 1 keeps the exact comparison for `q3-1`.
- **A reused identifier is refused per work directory.** The driver refuses a
  characterization identifier whose directory exists under the work directory of the
  phase `up` it is given. Under another run name, `q3-1` could be given again, and
  `--check` does not detect two directories that state one identifier. The rule that a
  characterization is never repeated is a procedure, not a check.
- **A failure of the tool reads as a refusal in the transcript.** The driver starts the
  caller only when `--preconditions` exits 0, and prints "The tool refused a precondition"
  for any other exit status, also 1 or 2, which mean that the tool printed no state.
  The record built after it states the result.
- **The wait for the watch is not observed in Q3.** The driver counts the lines of the
  watch output and waits until there are 4. `q2-1` showed one event on each line for the
  same command, but no Q3 watch has started, because `q3-1` was refused before it.
  `stream-complete` holds the opening events in either case.
- **`upStartedAt` is the start file of the phase `up`.** The header states the instant
  that the Q1 driver wrote to its start file, which is a moment after the first instant it
  printed. For `q3-1` they are 07:26:19 and 07:26:17.

## What a record does not establish

- A throughput, a rate, a capacity figure, or a benchmark. One closed-loop workload of
  two callers ran for six minutes on one node.
- A service level, an availability, or a latency that a caller can expect.
- What a caller sees while something fails or recovers. By the rules of the record, no
  API pod or runtime pod was added, deleted, not Ready, or restarted while the caller
  ran. The Service endpoints, the path from the API to the runtime, and the node were
  not read, and requests can fail in a `CHARACTERIZED` record.
- That a percentile of fewer than 100 successes is meaningful.
- That the clock of the runner pod agrees with another clock.
- That a source record is what its collection gives.
- A result of a reliability experiment. The bounds derived from G are stated by the bound
  record, and they are experiment bounds.
- Production availability, high availability, or resilience to the loss of a node, a
  zone, or a region.
- Anything about another provider, node, Kubernetes version, release, model, or caller
  workload.

## Limitations

- One provider, one node, one Kubernetes version, one release, one model, and one caller
  workload. The request is the same fixed prompt in every request, so the prompt cache of
  the runtime can make the prompt processing of later requests nearly free.
- The caller runs inside the cluster, on the node that runs the release. Its own
  resource use is not counted by the capacity gate.
- The gaps depend on the latency of a request and on the two workers: with two closed-loop
  workers and two runtime replicas of one slot each, a gap is close to half a latency when
  the Service spreads the two requests. No record shows how the Service spread them.
- The watch reads the API pods and the runtime pods. The telemetry collector, the delivery
  controller, and the node are not read during the caller.
- The direct `kubectl` commands of the driver name the context `docker-desktop` and run
  no target check of their own. The phase `up` of the Q1 driver and the runner script run
  the target check.
