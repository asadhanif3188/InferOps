# The reliability analysis of an experiment run

Status: **the tool is implemented, and files that the test suite builds show each definition, the ends of each interval, each refusal, and the stored form at evidence level C0. No run was analysed. No analysis of a real run is committed, no bound was compared with a figure, and no claim is registered.**

An experiment run leaves files: the caller record of the
[reliability runner](../serving/reliability-runner.md), the four
[timeline streams](../environment/experiment-timelines.md), and the
[log of operator events](../environment/experiment-operator-events.md). Each
file states instants and values. None states how long the caller failed, how
long a Service had no Ready endpoint, or when the run was stable again.

`tools/reliability_analysis` computes those figures from the files. It reads
each file with the reader of the tool that defines it, and it prints one
analysis document with the schema name `inferops.io/reliability-analysis/v1alpha1`.

**The analysis computes figures. It decides no result.** A document states no
result state, no verdict against a bound, no availability percentage, no error
rate, no percentile, and no confidence interval. A test holds that no member of
a document has such a name, and the command has no option that takes a bound.

**A value that was not read is not a value.** An open failure episode has no
duration. A reading that did not answer, a count that the API omitted, and a
stream that was not given are not zero and are not healthy. A metric with no
value states one of 17 reasons, and the document lists each such metric in
`withoutValue`. Two of the reasons are reasons of the aggregate.

## What an analysis is not

**It is not the result of a run.** The result state of a run is a member of its
[ExperimentRun manifest](../contracts/experiment-run.md), and the criteria are
those of a frozen record of the experiment. No frozen record states a bound for
one of these figures yet. A figure here is an input to that decision.

**It is not a measurement of a cluster.** The analysis reads files. It contacts
no cluster and no caller, and it writes no file.

**It is not a second source of caller truth.** The caller figures are computed
from the caller record and the window. No stream changes a caller figure. The
log changes two things, and the page states both below: a recorded abort ends
the window, and the fault event sets where the search for the first caller
impact starts. The disagreement figures compare the caller record with a
signal, and the caller record is the reference.

## The inputs

| Input | Option | Read by | Required |
|---|---|---|---|
| The declaration | `--declaration` | This tool | Yes |
| The caller record | `--caller` | `tools.reliability_runner.read_record` | Yes |
| The `endpoints` stream | `--endpoints` | `tools.experiment_timeline.read_stream` | No |
| The `pods` stream | `--pods` | `tools.experiment_timeline.read_stream` | No |
| The `deployments` stream | `--deployments` | `tools.experiment_timeline.read_stream` | No |
| The `argo` stream | `--argo` | `tools.experiment_timeline.read_stream` | No |
| The log of operator events | `--operator-events` | `tools.experiment_events.read_log` | No |

- An input that its reader refuses is refused here, and no document is printed.
  The refusal names the input and the rule of that reader. It does not repeat the
  detail of that reader, which can quote a value of the file.
- The declaration and each input name one experiment and one run. A file of
  another run is refused.
- An input that is not given is stated as `not-given` in `inputs`. Each metric
  that reads it has no value. The log of operator events must be closed.
- No input is a telemetry stream. The
  [telemetry streams](../environment/experiment-telemetry.md) are not read.

## The declaration

The declaration states what the analysis cannot read from the evidence: the
observation window, the expected state, and the signals. Its schema name is
`inferops.io/reliability-analysis-declaration/v1alpha1`.

```json
{
  "schema": "inferops.io/reliability-analysis-declaration/v1alpha1",
  "experimentId": "example-experiment",
  "runId": "run-1",
  "window": {
    "from": "2026-10-12T08:00:00.000Z",
    "to": "2026-10-12T08:02:30.000Z"
  },
  "expected": {
    "desiredRevision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "readyReplicas": {"platform-api": 2, "serving-runtime": 2},
    "runtimeReadyEndpoints": 2
  },
  "signals": [
    {
      "id": "runtime-ready-endpoints",
      "source": "endpoints-ready",
      "tier": "serving-runtime",
      "problemBelow": 2
    },
    {
      "id": "application-sync",
      "source": "application-sync-status",
      "healthyValues": ["Synced"]
    }
  ]
}
```

- **The tool registers no threshold.** The window, each expected count, and the
  `problemBelow` count or the `healthyValues` of each signal are values of the
  declaration. The tool registers the sources that it can read, and the figures
  of the stabilization rule.
- **The declaration is not held to a frozen record.** A frozen record of an
  experiment is the place for these values, and none states them yet. Until
  one does, a person writes the declaration. A declaration that is written
  after the evidence is read can move a figure. The document repeats the
  window, the expected state, and what each signal declared, so a reader can
  see each value that was used.
- A declaration has exactly its six members. A count is a whole number from 1
  to 64. A declaration states at most 16 signals.

## The window

Each metric reads the evidence inside the declared window, and the two edges
are inside it.

- A request is inside the window when its completion instant is.
- A reading is inside the window when its read starts and finishes inside it.
  A reading that crosses an edge is not read.
- **A recorded abort ends the window.** When the log holds a `run-aborted`
  event that was recorded before the declared end, the window ends at that
  instant. The document states the declared end, `effectiveTo`, and `endedBy`.
  With several such events the earliest instant is taken, and not the first
  line: the events tool accepts a log whose instants are not in the order of
  its lines. An abort that was recorded at or before the start of the window
  is refused.
- **The caller record must cover the window.** A record that starts after the
  window starts, or ends before it ends, says nothing about the rest of the
  window. Each caller metric then has no value. A window with no failed request
  in the record is not a window in which no request failed.
- **A window with no completion gives no caller metric.** A record can cover a
  window in which no request completes. The figure of such a window is not 0.
- `requests.largestTimeWithNoCompletionMs` is the longest time of the window
  with no completion, with the two edges of the window as ends. A caller that
  completes nothing for a time is visible there. The analysis sets no limit for
  it.

## The order of completions

Completed requests are ordered by finishedAt. Two requests with one finishedAt
are ordered by the position of their lines in the record.

The runner writes `finishedAt` to one millisecond. Two workers can complete
two requests in one millisecond, and the instants then do not order them. The
position of the lines is the order in which the runner wrote them. The
difference matters when one of the two requests failed. With the failed line
first, the episode ends at the same instant and lasts 0 ms. With the
successful line first, the episode lasts until the next successful completion.
The document counts the completions that share an instant, and each end of an
episode states `tied` when a completion of the other outcome has its instant.

## Caller failure episodes

An episode is a run of failed completed requests with no successful completed
request between them.

| Member | What it holds |
|---|---|
| `start` | The first failed request of the run: its sequence number and its completion instant |
| `end` | The first successful request that completes after it: its sequence number and its completion instant. Null for an open episode |
| `ms` | The end instant minus the start instant. Null for an open episode |
| `failedRequests` | The number of failed requests in the run |
| `open` | True when no successful request completes after the run inside the window |
| `successAfterWindow` | For an open episode: the first successful request of the record that completes after the window, or null. It is stated, and it does not close the episode |

`callerFailureEpisodeMs` is one figure for the window:

- It is 0 when no request failed.
- It is the `ms` of the longest episode when each episode is closed.
- It has no value when an episode is open. An open episode is not counted as
  lasting to the end of the window.
- It has no value when the window starts inside an episode: the last completion
  of the record before the window is a failed one. The window then holds the
  end of an episode and not its start. `startsBeforeWindow` states that.
- `reason` states why the figure has no value.

A request is failed when the caller record states `success` as false. The six
outcomes of the record are not weighted, and no status is left out.

## The maximum success gap

`maxSuccessGap` is the largest time between two consecutive successful
completions inside the window. It names the two requests. The first of several
equal gaps is the one that is named.

- An edge of the window is not an end of a gap. The time from the start of the
  window to the first successful completion is not a gap.
- With fewer than two successful completions the metric has no value. It is
  not 0.

## The first caller impact

`firstImpact` is the first failed request that completes at or after the
search start. The search starts at the instant of the `fault-injection-started`
event when the fault is stated and that instant is inside the window. It starts
at the start of the window when no log is given, when the log states no fault,
when the fault is `ambiguous`, and when the event is before the window. The
document states `searchedFrom`, the sequence number, both instants of the
request, and its outcome.

The impact instant that the other metrics use is the completion instant. The
request was sent earlier, and the document states that instant too.

## The fault

The fault is stated when the log holds exactly one `fault-injection-started`
event and one `fault-injection-finished` event after it, with the same code.
The document then states `notBefore` and `notAfter`: the two instants at which
the events tool recorded them. Any other combination of the two kinds is
`ambiguous`, and the detection lag and the stabilized recovery then have no
value. The document also lists each `run-aborted` and each `manual-action`
event with its instant and its code.

## A sampled state has two figures

A caller instant is exact to one millisecond. A reading is a sample: a stream
states a value at a read and states nothing between two reads. The analysis
does not carry a value from one read to the next.

For a run of consecutive readings that gave one state, the analysis states two
figures.

```text
reads:    A         B         B         B         A
          |---|     |---|     |---|     |---|     |---|
                        ^               ^
                        inner: finish of the first B read to start of the last,
                        when no read between them has no value
          ^                                           ^
          outer: start of the read before to finish of the read after
```

- **The inner figure** is the time between consecutive reads that both gave
  the state: from the finish of the first to the start of the last. One read
  has an inner figure of 0. It assumes that the state did not change between
  two consecutive reads that both gave it.
- **The outer figure** is the time from the start of the nearest read before
  the run that gave another state to the finish of the nearest read after it
  that gave another state. With no such read on a side, the edge of the window
  bounds the figure, and the interval states `boundedBefore` or `boundedAfter`
  as null.
- **A reading with no value does not end a run and does not bound one. It
  divides the run.** The inner figure is the sum of the parts on each side of
  such a reading, so it holds no time across a reading with no value. The outer
  figure holds that time. An interval counts such readings in
  `notObservedReadingsInside`.

Neither figure is the exact time. The state held for at least the reads that
gave it, and it did not hold at the reads on each side.

## Zero-Ready-endpoint intervals

`zeroReadyEndpoints` reads the `endpoints` stream. For each of the two tiers
it states each interval in which the Service had no Ready endpoint, with the
readings at each end, and four figures: `totalInnerMs`, `maxInnerMs`,
`totalOuterMs`, and `maxOuterMs`. The total outer figure counts a read that two
intervals share once.

- A tier with a reading of a count and no reading of zero has a `count` of 0.
- A tier with no reading of a count is `not-observed` and has no count. It is
  not a tier that had an endpoint.
- `notObservedMs` is the sum of three times: the time before the first read of
  a count, the time after the last one, and each time between two reads of a
  count that holds a reading with no value. With no read of a count it is the
  whole window. The time between two consecutive reads of a count is not in
  it.

## Signals

A signal is one value of one stream, reduced at each reading to one of three
states: `healthy`, `problem`, or `not-observed`.

| Source | Stream | Declared members | What is read |
|---|---|---|---|
| `endpoints-ready` | `endpoints` | `tier`, `problemBelow` | The number of Ready endpoints of the Service of one tier. |
| `pods-ready` | `pods` | `tier`, `problemBelow` | The number of listed pods of one tier whose Ready condition is True. |
| `deployment-ready-replicas` | `deployments` | `tier`, `problemBelow` | The readyReplicas count of the Deployment of one tier. |
| `deployment-available-replicas` | `deployments` | `tier`, `problemBelow` | The availableReplicas count of the Deployment of one tier. |
| `application-sync-status` | `argo` | `healthyValues` | The syncStatus that the delivery controller reported. |
| `application-health-status` | `argo` | `healthyValues` | The healthStatus that the delivery controller reported. |

- A count source states `problem` when the count is below `problemBelow`, and
  `healthy` otherwise.
- A value source states `healthy` when the reported word is one of
  `healthyValues`, and `problem` for any other reported word.
- **A value that the reading does not report is `not-observed`.** A read that
  did not answer, a tier that the timeline tool refused, a count in the state
  `missing`, a pod with no Ready condition, and an Application with no such
  field are each such a value.
- A signal with no value in any reading of the window is not computable.

For each signal the document states the number of readings in each state,
whether the signal changed, and three metrics.

### Detection lag

The detection lag is the time from the first caller impact to the first
reading in which the signal states the problem. The first indication is the
first `problem` reading that finishes at or after the search start. The search
start is the one of the first caller impact.

The signal changed between two reads, so the lag has two bounds:

- `notAfter` is the finish of the first `problem` read, and `lagNotAboveMs` is
  that instant minus the impact instant.
- `notBefore` is the start of the read before it that gave `healthy`, and
  `lagNotBelowMs` is that instant minus the impact instant. With no such read,
  both are null.
- A negative bound says that the recorded instant of the signal is before the
  recorded instant of the impact.
- `order` is `signal-first` when the upper bound is negative, `caller-first`
  when the lower bound is stated and positive, and `not-established` otherwise.
  It is the order of the recorded instants of two clocks, and the difference
  between the clocks is not measured.

### False-healthy and false-unavailable time

The caller record gives three kinds of time:

- **The caller fails** from the start of an episode to its end. An open episode
  lasts to the end of the window.
- **The caller succeeds** between two consecutive completions that are both
  successful.
- The time from a successful completion to the failed one after it is in
  neither.

`falseHealthy` is the time in which the caller fails and the signal states
`healthy`. `falseUnavailable` is the time in which the caller succeeds and the
signal states `problem`. Each states `callerMs`, the inner figure, the outer
figure, and `signalNotObservedMs`: the caller time in which no read gave the
signal a value. The inner figure holds none of that time. The outer figure can
hold it, because a reading with no value does not bound a run and the edge of
the window bounds a run with no read beyond it. Each of the four is a sum, and
names no reading.

An open episode has no duration, and `callerFailureEpisodeMs` has no value. For
these two figures alone the caller is counted as failing from the start of an
open episode to the end of the window. `callerMs` states that time.

## Stabilized recovery

A run is stabilized at the first completion that ends a span with these
properties:

- The span is consecutive successful completions, with no failed completion
  between them.
- It holds at least 10 consecutive successful completions.
- Its first and its last completion are at least 60 seconds apart.
- Each reading of the expected state that overlaps the span holds, and the span
  holds at least one reading of each of the three conditions.

| Condition | Stream | A reading holds when |
|---|---|---|
| `desiredRevision` | `argo` | It reports a `resolvedRevision` that is the declared commit and a `syncStatus` of `Synced` |
| `readyReplicas` | `deployments` | The Deployment of each tier reports a `readyReplicas` count that is the declared count |
| `runtimeReadyEndpoints` | `endpoints` | The runtime Service reports a Ready endpoint count that is the declared count |

A reading of the argo stream holds the expected revision when it reports a
resolvedRevision that is the declared commit and a syncStatus of Synced.

- The search starts at the instant of the `fault-injection-finished` event
  when the fault is stated and that instant is inside the window. Otherwise it
  starts at the start of the window. With no stated fault a recovery that is
  found can be a state that no fault disturbed.
- **The rule sets no limit for the time between two readings.** One reading of
  each condition inside the span is enough. `largestTimeWithNoReadingMs` states,
  for each condition, the longest time of the span in which no read was in
  progress, with the two ends of the span as ends.
- A reading that does not hold moves the start of the span to after the finish
  of its read.
- **A reading with no value is not a reading that holds.** It moves the start
  of the span to after the start of the next read with a value. With no such
  read, the run is not stabilized.
- Without one of the three streams the metric is not computable, and
  `stabilized` is null. It is not false.
- A span of consecutive successful completions holds no failed request, so it
  holds no error of the platform.

The document states `stabilizedAt`, both ends of the span, the number of
readings of each condition inside it, and the longest run of successes that the
search found. With a stated fault it also states the time from each of the two
fault instants, and the number of failed requests from the first fault instant
to `stabilizedAt`.

The two figures of the rule are a definition for an experiment. They are not a
production SLO.

## A metric with no value

| Reason | Statement |
|---|---|
| `caller-record-does-not-cover-window` | The caller record starts after the window starts, or it ends before the window ends. The record says nothing about the rest of the window. |
| `no-completion-in-window` | No request completes inside the window. A window with no completion is not a window with no failure. |
| `episode-open` | A failure episode has no successful completion after it inside the window, so it has no duration. |
| `episode-starts-before-window` | The last completion before the window is a failed one, so the window starts inside a failure episode whose start it does not hold. |
| `fewer-than-two-successes` | The window holds fewer than two successful completions, so it holds no gap between two. |
| `no-count-in-window` | No reading in the window states a Ready endpoint count for the tier. |
| `stream-not-given` | A stream that the metric reads was not given. |
| `no-reading-in-window` | No reading of the stream is inside the window. |
| `readings-out-of-order` | A reading starts before the reading before it finishes. The stream has no usable order. |
| `signal-never-observed` | No reading in the window states a value for the signal. |
| `caller-not-computable` | The caller metrics have no value, and the metric reads them. |
| `fault-ambiguous` | The log does not hold one fault-injection-started event and one fault-injection-finished event after it with the same code. |
| `no-caller-impact` | No request failed in the window at or after the fault, so no first caller impact exists. |
| `never-indicated` | No reading in the window at or after the search start states the declared problem. |
| `indicated-before-search-start` | The signal already stated the declared problem at the reading before its first reading at or after the search start, so no first indication is inside the search. |
| `not-three-counted-runs` | The aggregate does not count three runs, and no rule is registered for another number. |
| `counted-run-without-value` | A counted run has no value for the figure. The run is not dropped. |

## The aggregate of three runs

`python -m tools.reliability_analysis aggregate` reads analysis documents, each
with the result state of its run, and prints one figure of each run.

The median of three runs is the one aggregate. Three observations do not support
a confidence interval or a statistical significance, and the document states
neither. Each run is listed with its own value.

| Metric | Path in an analysis document |
|---|---|
| `caller-failure-episode-ms` | `caller.failureEpisodes.callerFailureEpisodeMs` |
| `max-success-gap-ms` | `caller.maxSuccessGap.ms` |
| `requests-failed-in-window` | `caller.requests.failed` |
| `requests-failed-since-fault` | `stabilizedRecovery.requestsFailedSinceFault` |
| `stabilized-since-fault-started-ms` | `stabilizedRecovery.sinceFault.fromFaultStartedMs` |

- The one registered rule is `median-of-three`.
- A run in the state `PASSED` or `FAILED` is counted. **A run that worsens the
  figure is not dropped.**
- **A result state alone leaves no run out.** A run in the state
  `INCONCLUSIVE`, `REFUSED`, or `ABORTED` is not counted only when its reason
  is one that its exclusion reasons register for the experiment, the state,
  and the run. The document then lists the run with its value, that reason,
  the identifier of the registered reason, and the freeze record. With no
  registered reason the aggregate is refused.
- **A counted run with no value leaves the aggregate with no median.** An open
  episode in one run does not become a run that is left out.
- The median is stated for exactly three counted runs. For any other number the
  document lists each run and states no aggregate.
- An aggregate document repeats the result state that the command was given
  for each run. It decides none.
- The command does not compare the windows or the declarations of the
  documents.
- The result state of each run is an argument of the command. The command does
  not read a manifest, so it does not check that the state is the one that the
  manifest of the run states. (Since `V2-S5-004-PR2`
  [the replay tool](analysis-replay.md#the-aggregate-of-the-runs-of-an-experiment)
  has an aggregate command of its own. It reads each result state from the
  manifest of the run, and it refuses when a run of the experiment is not
  given.)
- **The command has no registered reason to give.** It reads no manifest and
  no freeze record. So a run that is given in the state `INCONCLUSIVE`,
  `REFUSED`, or `ABORTED` refuses the command with
  `analysis-exclusion-unregistered`, and the command has no option that states
  a reason. Until `V2-S5-005-PR1` the command did not count such a run and
  stated `result-state-inconclusive` for it. The
  [aggregate command of the replay tool](analysis-replay.md#a-run-that-is-not-counted)
  reads the reason from the manifest and the exclusion reasons from the freeze
  record that the manifest names. The schema name of the document is now
  `inferops.io/reliability-aggregate/v1alpha2`, because the `exclusion` member
  of a run changed from text to an object.

## Rules of refusal

| Rule | Statement |
|---|---|
| `analysis-declaration-unreadable` | A declaration is one JSON object with no member stated twice. |
| `analysis-declaration-unsupported` | A declaration has exactly its members, its schema name, two identifiers, and an expected state in its form. |
| `analysis-window-invalid` | The window states two instants in UTC to one millisecond, and it ends after it starts. Each recorded abort is after the window starts. |
| `analysis-signal-unsupported` | Each signal has its own identifier, a registered source, and the members of that source in their form. A declaration states at most 16 signals. |
| `analysis-input-refused` | Each input is accepted by the reader of the tool that defines it. The analysis names the input and the rule of that tool. |
| `analysis-input-misnamed` | A stream is given under the name that its header states. |
| `analysis-identity-differs` | The declaration and each input name one experiment and one run. |
| `analysis-aggregate-unsupported` | An aggregate is asked for a registered metric of analysis documents of one experiment, each of another run, each with a registered result state. |
| `analysis-exclusion-reasons-unsupported` | The exclusion reasons of a freeze record are one object with exactly an experiment identifier and a list of reasons. Each reason has its own identifier, one of the result states INCONCLUSIVE, REFUSED, and ABORTED, a reason as text, and, when it is for named runs alone, their run identifiers. No result state has one reason text twice. A record states at most 32 reasons. |
| `analysis-exclusion-unregistered` | A run in the state INCONCLUSIVE, REFUSED, or ABORTED states a reason that the freeze record of its manifest registers, character for character, for the experiment, the result state, and the run. |

| Exit status | Meaning |
|---|---|
| 0 | The command printed a document |
| 2 | The arguments are not usable |
| 3 | An input was refused. No document is printed, and one `REFUSED` line goes to standard error |

**Exit status 0 does not say that each metric has a value, and it does not say
that a run passed.**

## Limitations

- A caller instant is on the clock of the runner's pod. A reading is on the
  clock of the collecting host. An event is on the clock of the recording host.
  The difference between the clocks is not measured. Each figure that compares a
  caller instant with a reading or an event holds that difference.
- A request is counted at its completion. A request that fails after a long time
  is counted at the end of that time. The first caller impact is the completion
  of the first failed request, and the request started earlier.
- A failure episode ends at the first successful completion after it, from any
  worker. With two workers, a request that was sent before the failure can end
  the episode.
- A stream states a value at a read and states nothing between two reads. The
  inner figure of an interval holds no change that no read gave. The outer
  figure holds each read on both sides. Neither is the exact time.
- The stabilization rule needs one reading of each condition inside the span,
  and it sets no limit for the time between two readings. A span can hold a long
  time with no reading. The document states the longest such time for each
  condition.
- With no stated fault the search for the first caller impact and for the
  stabilized recovery starts at the start of the window. A recovery that is
  found then can be a state that no fault disturbed.
- A reading whose value was not read is not healthy and is not a problem. A
  Deployment count that the API omitted is such a value, and the API omits a
  count of zero. So a signal of a Deployment count has no value in a reading in
  which the count is zero.
- The analysis reads the instant at which the tool recorded an event. It does
  not read the second instant that an event can state for another clock.
- The declaration is an input. The analysis does not hold a threshold, an
  expected count, or a window to a frozen record of an experiment.
- The document does not state the digest of an input, and it does not state the
  revision of the code that computed it.
- No signal is read from a telemetry stream.

## What an analysis does not establish

- The result state of a run. No figure here is compared with a bound.
- An availability percentage, an error rate, a percentile, a confidence
  interval, or a statistical significance.
- A production SLO. The stabilization rule is a definition for an experiment.
- The cause of a failure, of a gap, or of a recovery.
- An order of two instants from two clocks that are less than one second apart.
- That a signal detects a problem in another run, on another topology, or in
  another environment.
- That the inputs are the evidence of a real run. The analysis reads the files
  that it is given.

## The six cases

[`tests/domain/fixtures/reliability-analysis`](../../tests/domain/fixtures/reliability-analysis)
holds six cases. Each is a directory with a declaration, the inputs, and the
analysis document. Each file is synthetic: the suite builds it, and no file is
evidence of a run.

| Case | What it holds |
|---|---|
| `zero-failure` | One runtime pod is lost and no request fails. The episode figure is 0, the Service never has zero Ready endpoints, and the run is stabilized after the readings hold again |
| `concurrency` | Both runtime pods are lost with two workers. A request that was sent before the first failure ends the first episode |
| `missing-signal` | The same outage with the `argo` stream not given, one read that did not answer, and a Deployment count that the API omitted. The signals have no value in those readings, and the stabilized recovery is not computable |
| `open-episode` | No request succeeds again. The last episode is open and has no duration |
| `clock-ties` | A failed and a successful request complete at one instant, twice, with the lines in both orders |
| `abort` | The run is aborted. The window ends at the abort, and the episode is open |

The timeline tool builds the streams of a case from a collection that the suite
invents, and the events tool writes the log. The suite writes the caller record
itself, and the runner's reader accepts it. No runner wrote one. The suite
builds each case again and compares it with the committed files, byte for
byte. To write the
files again, run `python tests/domain/test_reliability_analysis.py`.

## An analysis in a run directory

The [evidence layout](experiment-evidence-layout.md) registers the derived role
`analysis` for figures that are computed from raw files. An analysis document
is such a file. Give it the suffix `.json`. The layout check holds the file to
its digest. It does not call this tool, and it does not compute the document
again.

Since `V2-S5-004-PR2` [the replay tool](analysis-replay.md) reads a run directory and
prints a run analysis: the document of this tool with the digest of each input
and the code that computed it. A replay computes a stored run analysis again. A
document of this tool alone, stored under the role `analysis`, is bound to no
evidence, and the replay refuses it.

## Commands

```sh
uv run --locked python -m tools.reliability_analysis analyze \
  --declaration FILE --caller FILE [--endpoints FILE] [--pods FILE] \
  [--deployments FILE] [--argo FILE] [--operator-events FILE]
uv run --locked python -m tools.reliability_analysis aggregate \
  --metric NAME FILE=STATE [FILE=STATE ...]
```

Both commands print one JSON document with sorted members and LF line endings.

## What is not done

- No run was analysed. Each input of the suite is built by the suite.
- The document does not state the digest of an input or the revision of the
  code, and nothing computes a committed document again from committed raw
  files of a run. A later change owns both. (Since `V2-S5-004-PR2`
  [the replay tool](analysis-replay.md) does both, in a document of its own.
  The document of this tool is unchanged.)
- No frozen record of an experiment states a window, an expected state, a
  signal, or a bound, so no check holds a declaration to one.
- No signal is read from a telemetry stream. A rate of errors and the
  reachability of a scrape target have no source here.
- A Deployment count of zero is not read as zero, because the timeline stream
  states an omitted count as `missing`. A signal of a Deployment count
  therefore has no value while the count is zero.
- The analysis does not read the second instant of an event, and it does not
  compute a decision time or a reversal time from the reversal events.
- The analysis does not pair a deleted pod with its replacement.
- No limit holds the time between two readings of a stabilization span, or the
  time with no completion of a caller. The document states both times.
- The layout check does not call the tool.

## Tests

[`tests/domain/test_reliability_analysis.py`](../../tests/domain/test_reliability_analysis.py)
builds the inputs and holds the analysis to each definition, the ends of each
interval, each state with no value, each refusal, and the stored form that this
page states. It reads the imports of the tool for a module that reaches a
network or a process, and its text for a call that writes a file. It compares the rules, the reasons, the
sources, the metrics, the limitations, and the boundaries on this page with
the tool's.
