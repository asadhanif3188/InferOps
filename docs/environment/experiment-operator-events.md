# The operator events of an experiment run

Status: **the tool is implemented, and logs that the test suite writes show each kind of event, each refusal, and the stored form at evidence level C0. No result-bearing run recorded an event. Since `V2-S5-006-PR1` the logs of the two attempts of [a non-result integration validation](../proof/experiments/README.md#the-sprint-5-integration-validation) are committed: in each, the control process recorded one `fault-injection-started` and one `fault-injection-finished`, and no operator recorded an event. No claim is registered.** (Until `V2-S5-006-PR1` this status said that no run recorded an event and that no log of a real run is committed.)

An experiment run has events that no cluster object and no metric holds. The
program that controls the run injects a fault. An operator reviews the signals
and judges that the problem is present. An operator decides to reverse a change,
a commit that reverses it is created, and the commit is accepted. A run is
aborted. An operator acts on the environment by hand. An analysis needs the
instant of each one, on a clock that it can compare with the other streams of
the run.

`tools/experiment_events` writes one log of those events for one run, and it
holds a stored log to its form. The log is a text file of JSON lines with the
schema name `inferops.io/experiment-operator-events/v1alpha1` and the stream name `operator-events`.

**A log states what was recorded and when. It does not judge.** It does not say
whether a detection was correct, whether a reversal was fast, or whether a run
passed. The tool computes no interval and gives no verdict.

## What a log is not

**A log is not caller truth.** An event is a record of the control of the run or
of an operator. It is not a request that a caller sent and had answered. The
caller record of a run has a separate source, the
[reliability runner](../serving/reliability-runner.md). No event is derived from
it. The tool imports no caller tool, and no option takes a request identifier:
a test holds those two.

**A log is not a detection.** The event `detection-reviewed` states that an
operator recorded a judgement. The signals that the operator read are in
[the timeline streams](experiment-timelines.md) and in
[the telemetry streams](experiment-telemetry.md). Whether a signal showed the
problem before the operator saw it is a figure that an analysis computes.

**A log is not a transcript and not an audit trail.** An event holds no command
line, no output of a command, no note, and no name of a person. The header of a
log repeats texts of the tool, and the check refuses a stored header with any
other text. A log is not a record of who did what on a system that needs one.

**This is not a logging platform.** The tool appends one line to one file. It
ships no line anywhere, it reads no log of a pod, and it holds at most
500 events.

## The kinds of event

| Kind | What it records | What it must state |
|---|---|---|
| `fault-injection-started` | The control of the run is about to issue the command that injects the fault. Record it before the command. | A code |
| `fault-injection-finished` | The command that injects the fault returned. Record it after the command. | A code |
| `detection-reviewed` | An operator reviewed the signals and judged that the declared problem is present. | The actor `operator` |
| `reversal-decided` | An operator decided to reverse the change. | The actor `operator` |
| `reversal-created` | The commit that reverses the change exists. | The commit of the reversal |
| `reversal-accepted` | The commit that reverses the change was accepted into the branch that the delivery path follows. | The commit of the reversal |
| `run-aborted` | The run was aborted. | A code |
| `manual-action` | An operator acted on the environment by hand, outside the procedure of the run. | The actor `operator`. A code |

- **A fault injection is two events.** The control of the run records
  `fault-injection-started`, issues the command that injects the fault, and
  records `fault-injection-finished` when the command returned. The `record`
  command takes each instant on the host that runs it. When the control of the
  run runs both commands on one host, and waits for the first before it issues
  the fault command, the fault is not before the first instant and the command
  did not return after the second. No instant inside that interval is
  established, and nothing checks that the two events were recorded in that
  order.
- **A reversal is three events.** `reversal-decided` is the decision of an
  operator. `reversal-created` and `reversal-accepted` each state the commit of
  the reversal. The time that an operator took to decide is then separate from
  the time that the system took to recover.
- **The actor is a role.** It is `operator` or `control-process`. It names no
  person. A kind that is a judgement or an act of a person states the actor
  `operator`: a program does not review a detection.
- **The code is a registered word, not a sentence.** It names the fault, the
  reason of an abort, or the manual action. Its form is 1 to 63 lowercase
  letters, digits, and hyphens, with a letter or a digit first and last. This
  tool holds a code to that form and to nothing else. The frozen record of an
  experiment registers the codes that its runs may use, and no such record
  exists yet.

## The members of an event

| Member | What it holds |
|---|---|
| `index` | The number of the event in the log, from 1 |
| `kind` | One of the eight kinds |
| `actor` | `operator` or `control-process` |
| `recordedAt` | The instant at which the tool recorded the event, on the clock of the recording host |
| `occurredAt` | An instant on another clock, with its resolution and the clock. It is null when the event states none |
| `code` | The code of the event, or null |
| `subject` | A resource kind and a name, or null. The kind is one of `pod`, `deployment`, `service`, `application`. The name has the form of a Kubernetes name |
| `commit` | The full commit identifier of the reversal, or null |

An event has these members and no other. A stored event with a member such as a
note or a request identifier is refused.

## The clocks

**The tool takes the instant of the record.** `recordedAt` is the wall clock of
the host that ran the `record` command, in UTC, to one millisecond, in the form
`2026-10-12T08:00:00.000Z`. The command has no option that states it, and a test
holds that. The function `record` takes a clock, `now`, which the suite
replaces, and the command passes none. It is the form of `read.startedAt` in the timeline
streams and in the telemetry streams. So the events and the readings have one
time basis when one host writes them.

**An instant from another clock is a second field.** Some events happen on
another system. The acceptance of a commit has an instant on the Git host. The
`record` command takes that instant with `--occurred-at` and the clock that it
is on with `--clock`. The tool normalises the instant to UTC. An instant with no
fraction of a second keeps a resolution of one second. An instant with a
fraction is cut to one millisecond and is not rounded. `occurredAt` states the
value, the resolution, and the clock. It does not replace `recordedAt`.

| Clock | What it names |
|---|---|
| `recording-host` | The host that ran the command, at an earlier instant. |
| `cluster` | A component of the cluster. |
| `git-host` | The host of the Git repository. |
| `other-host` | Another host that the page of the run names. |

**The difference between two clocks is not measured.** The header of a log
states `skew` as `not-measured`. An interval between a `recordedAt` and an
`occurredAt` on another clock holds that difference, and no order under one
second is established for an `occurredAt` with a resolution of one second.

**A clock that was set back is named.** The end line states
`instantsOutOfOrder`: each event that was recorded at an earlier instant than
the event before it.

## A log is appended to

```sh
uv run --locked python -m tools.experiment_events open FILE --experiment ID --run ID
uv run --locked python -m tools.experiment_events record FILE --kind KIND --actor ACTOR \
  [--code CODE] [--subject KIND/NAME] [--commit SHA] \
  [--occurred-at INSTANT --clock CLOCK]
uv run --locked python -m tools.experiment_events close FILE
uv run --locked python -m tools.experiment_events check FILE [FILE ...]
```

- `open` writes the header: the two identifiers, the instant at which the log
  was opened, the clocks, the kinds, what is left out, the limitations, and what
  the log does not establish. It refuses a file that exists. A log is one run,
  and the tool does not write into an earlier one.
- `record` reads the log, holds it to its form, and appends one line. An event
  that does not hold a rule is refused, and nothing is written for it. Each
  earlier byte of the file stays as it was, and a test holds that.
- `close` appends the end line: the number of events, the number of each kind,
  the instant at which the log was closed, and `instantsOutOfOrder`. A closed
  log takes no event.
- `check` holds stored logs to their form. It refuses a log that is open.

| Exit status | Meaning |
|---|---|
| 0 | The command did what it was asked for |
| 2 | The arguments are not usable. A kind, an actor, and a clock that are not registered are refused here |
| 3 | A file is not a log, a log cannot be written to, or an event was refused |

**Exit status 0 does not say that a fault took effect, that a detection was
correct, or that a reversal reached a cluster.**

### What a stored log is held to

`check` holds each log to 10 rules.

| Rule | Statement |
|---|---|
| `events-log-unreadable` | A log is UTF-8 text, and each line ends with a line feed. Each line is one JSON object with no member stated twice. |
| `events-header-unsupported` | The first line is the header. It states the schema, the stream name, an experiment identifier, and a run identifier, each in its form. Its clocks, its kinds, what it leaves out, its limitations, and what it does not establish are the texts of this tool. |
| `events-members-unsupported` | Each line has exactly the members of its record. |
| `events-event-out-of-sequence` | Each line between the header and the end line is an event, the events are numbered from 1 with no gap, and a log holds at most 500. |
| `events-vocabulary-unregistered` | Each event states a registered kind and a registered actor. A kind that is a judgement or an act of a person states the actor operator. A subject states a registered resource kind, and an occurredAt states a registered clock. |
| `events-instant-invalid` | Each recordedAt, the openedAt, and the closedAt is UTC to one millisecond in the one registered form. Each occurredAt is UTC with a resolution of one second or of one millisecond. |
| `events-value-malformed` | A code, a name of a subject, and a commit identifier each have their form. No member of an event holds any other text. |
| `events-member-required` | An event of a kind that needs a code states one, and an event of a kind that needs the commit of the reversal states one. An event of another kind states no commit. |
| `events-end-missing` | The last line of a closed log is the end line, and no line follows it. A log with no end line is open, and the check refuses it. |
| `events-counts-differ` | The end line states the number of events, the number of each kind, and each event that was recorded at an earlier instant than the event before it, as this tool computes them from the events. |

**The check reads the form of a log.** It does not show that an event happened,
that a commit exists, or that a code is one that an experiment registers. It
does not compare the instant at which a log was opened or closed with the
instants of its events.

**A command that refuses to write names the nearest rule.** `open` refuses a
file that exists with `events-header-unsupported`. `record` and `close` refuse
a closed log with `events-end-missing`, and a file that cannot be written to
with `events-log-unreadable`. `record` refuses an `--occurred-at` with no
`--clock` with `events-instant-invalid`. The statement of each rule above is
about a stored log.

## What a log leaves out

A log leaves these out, on purpose:

- The name, the account, and the address of a person. An actor is one of two
  roles.
- Each note and each description. An event states a code and no sentence.
- The command line of a fault and the text that a command printed.
- Each request identifier and each correlation identifier of a caller.
- The address of a repository and the name of a branch.

No member of an event takes free text. The test suite gives the tool a sentence,
an address of a person, a path, a line break, and an address with a credential,
each in the place of a code or of a name, and it holds that each is refused and
that the refusal does not repeat the value. That test covers the values it
names. A code and a name are free within their form, and the form is not a check
for a secret.

## Limitations

- The instant recordedAt is the wall clock of the host that ran the record
  command, in UTC, to one millisecond. It is the instant at which the event was
  recorded. It is not the instant at which the event happened.
- A wall clock can be set while a run is in progress. The end line names each
  event that was recorded at an earlier instant than the event before it.
- A fault is injected between the event fault-injection-started and the event
  fault-injection-finished, when the control of the run recorded the first
  before the command and the second after it. Nothing checks that order, and no
  instant inside that interval is established.
- The instant occurredAt is what the person or the program that recorded the
  event stated. It is on the clock that the event names, it keeps the resolution
  that it was stated with, and nothing compares it with that clock.
- The difference between the clock of the recording host and any other clock is
  not measured.
- An event of an operator is recorded when the operator runs the command. The
  time between a judgement and its record is not measured.
- A code and a name are free within their form. The form is not a check for a
  secret, and it does not show that the frozen record of an experiment registers
  the code.
- One process appends to a log. Two processes that append at one time are not
  ordered, and the tool does not lock the file.
- A log holds at most 500 events.

## What a log does not establish

- That a caller obtained or lost a completion at any instant. An event is a
  record of the control of the run or of an operator. It is not a request that a
  caller sent and had answered.
- That a fault took effect, or when. An event states that a command was about to
  be issued and that it returned.
- That a detection was correct. The event detection-reviewed states that an
  operator recorded a judgement.
- That a reversal reached the cluster. The event reversal-accepted states that
  an acceptance was recorded, and a commit identifier is what the recorder
  stated.
- That no other action was taken. A log holds each event that was recorded, and
  an action that nobody recorded is in no log.
- A detection lag, a decision time, a recovery time, or any other metric of an
  experiment. A log is evidence that an analysis reads. This module computes no
  metric and gives no verdict.

## A log in a run directory

The [evidence layout](../testing/experiment-evidence-layout.md) registers the
raw role `operator-events` for a log. This change added the role: until it, the
vocabulary had no role for a log of operator events. Give a log the suffix
`.jsonl`, which the evidence index hashes as text. The tool does not hold the
file name to it. A run manifest can then name the file under the role, and the
layout check holds the file to its digest.

The layout check does not call this tool. Until a later change joins the two,
run `python -m tools.experiment_events check` on the log of a run. Close a log
before the manifest names it: a log that is open is refused by the check, and a
log that takes one more event has another digest.

## What is not done

- No result-bearing run recorded an event. The suite wrote each log in a
  temporary directory. The two committed logs are of the attempts of the
  integration validation. (Until `V2-S5-006-PR1` this item said that no run
  recorded an event.)
- One procedure calls the tool:
  [the driver of the integration validation](../proof/experiments/v2-s5-integration/procedure/run-driver.txt)
  opens the log, records the fault injection, and closes the log. No procedure
  records an event of an operator. (Until `V2-S5-006-PR1` this item said that no
  procedure calls the tool.)
- No frozen record of an experiment registers a code, so no check holds a code
  to a registered set.
- Nothing checks the order of the kinds: a `fault-injection-finished` with no
  `fault-injection-started` before it is accepted.
- Nothing compares a commit identifier with a repository, or an `occurredAt`
  with the clock that it names.
- The tool does not merge a log with a caller record or with a stream, and it
  computes no detection lag, no decision time, and no recovery time. An
  analysis does that. Since `V2-S5-004-PR1`
  [the reliability analysis](../testing/reliability-analysis.md) reads the
  fault, the abort, and the manual-action events of a log. It reads no
  detection and no reversal event, and it computes no decision time.
- The layout check does not hold a log to its form.
- The tool does not lock the file. One process appends to a log.

## Tests

[`tests/domain/test_experiment_events.py`](../../tests/domain/test_experiment_events.py)
writes each log in a temporary directory and holds the tool to the kinds, the
instants, the forms, the refusals, and the stored form that this page states. It
compares the kinds, the clocks, the rules, the limitations, and the boundaries
on this page with the tool's.
