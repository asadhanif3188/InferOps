# V2-S5-003-PR2 validation

Status: **the telemetry of an experiment run can be captured as two streams, and
the operator events of a run can be recorded in one log. The collector script
and the two tools are checked at evidence level C0, against collections and logs
that the suites build and against stand-ins for `kubectl`. No cluster and no
telemetry collector was read, no run recorded an event, no stream and no log of
a real run is committed, and no claim was registered.**

| Property | Value |
|---|---|
| Date | 2026-10-12 |
| Base | `99716a4`, the merge of pull request #140 |
| Branch | `feat/v2-s5-003-telemetry-operator-events` |
| Commits | The first commit: the two tools, the collector script, the three suites, and the pages. The second commit: the corrections of the independent review, and the record of them in this file |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv`; kubectl client `v1.36.1`. `shellcheck` and `gitleaks` are not installed |
| Evidence level | C0. Every check reads committed files, reads a directory or a file that a suite wrote, or executes the script against stand-ins for `kubectl`, `kind`, `docker`, and `git`. A fifth stand-in records each call of `python` and passes it to the interpreter of the suite |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or freeze record was added or changed |

## What changed

- [`scripts/environment/experiment-telemetry.sh`](../../../scripts/environment/experiment-telemetry.sh)
  asks the telemetry collector of the release the registered instant queries a
  bounded number of times and writes one collection directory. A sample is one
  read of the collector's Service and one read for each query, through the
  Service proxy of the API server. Each kubectl call that the script holds is a
  `get` with a request timeout. The script holds no query: it asks the tool for
  each request.
- [`tools/experiment_telemetry`](../../../tools/experiment_telemetry/__init__.py)
  registers eleven queries, reads a collection, prints the streams `telemetry`
  and `resources`, and checks a stored stream against eleven rules of form.
- [`tools/experiment_events`](../../../tools/experiment_events/__init__.py)
  opens a log, appends one event with the instant that it takes itself, closes
  the log, and checks a stored log against ten rules of form.
- Three suites:
  [`tests/domain/test_experiment_telemetry.py`](../../../tests/domain/test_experiment_telemetry.py),
  [`tests/domain/test_experiment_events.py`](../../../tests/domain/test_experiment_events.py),
  and
  [`tests/architecture/test_experiment_telemetry_collector.py`](../../../tests/architecture/test_experiment_telemetry_collector.py).
  None commits a collection or a log.
- [The telemetry page](../../environment/experiment-telemetry.md) and
  [the operator events page](../../environment/experiment-operator-events.md),
  each with the clocks, the states, the limits, and what its file does not
  establish. Each page is written from the constants of its tool.
- **One existing tool changed.**
  [`tools/experiment_evidence`](../../../tools/experiment_evidence/core.py) gains
  the raw role `operator-events`, in five lines. The vocabulary of the evidence
  layout goes from 13 roles to 14. Its page, its suite, and the index of the
  testing pages state the new count.
- Two architecture suites name the new script: the two lists of entry points and
  the list of read-only scripts.
- The timelines page said that a later change owns the metrics and the operator
  events. It now names the two tools. The contributor guide, the README, the two
  architecture tables, the changelog, and the test inventory each gain an entry.

No chart, manifest, schema, contract, script library, or freeze record was
changed. `tools/experiment_timeline` was not changed: the two new tools import
its instant forms and its read states.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| A bounded query and export of a registered set of metrics | Reached as a script and a tool, at C0, with one stated gap. The set is closed: eleven instant queries, at most 720 samples, a pause of 5 to 120 seconds, a timeout of 10 seconds for each read, and at most 32 series for each reading. The export is the two stream files. **The gap: no frozen record of an experiment registers the metrics.** The set is what the tool registers, with a name and a digest that a frozen record can pin |
| The missing-series semantics are preserved | Reached at C0. An answer with no series is the result `no-series` with no value. A read that did not answer has no result. A release with no collector states each read as `absent`. A sample that was not taken is `not-taken`. A sum that the collector answers as zero is a value of zero, and a test holds that the two readings differ |
| No request identifier is a metric label | Reached at C0. Each query aggregates and registers each label that a series can state. A test compares the registered labels with the telemetry catalog, which bars a request identifier and a correlation identifier from a metric. A series with a label that is not registered leaves its reading with no series, in the builder and in the check of a stored stream |
| Structured operator events for a fault injection, a reviewed detection, a reversal decision and acceptance, an abort, and a manual action | Reached as a tool, at C0. Eight kinds. A fault injection is two events, before and after the command. A reversal is three: decided, created, and accepted |
| Redaction and privacy tests | Reached for the values that the tests name. The telemetry suite gives the tool an address, a node name, a pod name, a request identifier in a label, and an error text, and holds that none reaches a stream. The events suite gives the tool a sentence, an address of a person, a path, a line break, and an address with a credential, and holds that each is refused. Neither is a scan for every secret |
| No general tracing or logging platform | Held. The telemetry tool takes no query from an argument, reads no log and no trace, and stores no series. The events tool appends one line to one file |
| The caller record stays independent | Held as text. Neither tool imports the reliability runner or the load tool, and a test reads the imports of each module. Neither reads a caller record. No option and no member takes a request identifier |

### The criteria of the parent change

| Criterion | State after this change |
|---|---|
| Endpoint changes are timestamped | Reached by `V2-S5-003-PR1` at C0. Not changed here |
| Pod and Deployment readiness, revision, deletion, and replacement are captured | Reached by `V2-S5-003-PR1` at C0, with the limit that no reading pairs a pod that left with a pod that entered. Not changed here |
| The Application state is captured independently | Reached by `V2-S5-003-PR1` at C0. Not changed here |
| Prometheus preserves missing and zero as two things | Reached here at C0, for the tool. What a running collector answers was not read |
| Operator fault, detection, and reversal events are aligned to UTC | Reached here at C0. The instant of each record is the host clock in UTC to one millisecond, in the form that the timeline streams and the telemetry streams use. An instant of another clock is normalised to UTC and names its clock. The difference between two clocks is not measured |

The parent change also names a bounded integration capture as evidence. **It is
still owed.** No capture of a real cluster was made by either change of the
parent: see below.

## What was not done

- **No cluster and no telemetry collector was read.** The local cluster refused
  connections on 2026-10-12, as it did for `V2-S5-003-PR1`. So no collection of
  a real release exists, and the form of a collector's answer is the one that
  the query API documents. No answer of a running collector was read by the
  tool.
- **No run observed that the Service proxy path reaches the collector.** The
  network policy of the chart selects the pod of the collector and admits no
  connection to its port. Whether a cluster applies that policy to a connection
  from the API server is a property of its network plugin. The collection
  verification of V1 reached the collector through a forwarded port instead.
- No run recorded an event, and no procedure calls the events tool.
- No frozen record of an experiment names the query set or registers a code of
  an event.
- No query reads the resource use of the serving runtime, of a container, or of
  a node. The release has no source for them.
- The resident memory of the API process has no series: the telemetry catalog
  records the metric as not emitted. The stream states `no-series` for it.
- The layout check of the evidence layout does not call either tool.
- Nothing starts the timeline collector and the telemetry script together, and
  nothing aligns their samples.
- Neither tool computes a rate, a detection lag, a decision time, or a verdict.

## Decisions taken in this change

Each was a choice of this change, and each can be changed by a later one.

1. **Two new tools, and the timeline tool untouched.** The proof record of
   `V2-S5-003-PR1` describes that tool as it was merged. The two new tools
   import its instant forms and its read states, so the three have one form of
   instant.
2. **The collector is reached through the Service proxy of the API server, and
   not through a forwarded port.** A read is then one `kubectl get --raw`: the
   script starts no process that outlives a read and opens no local port, and
   the test that each kubectl call is a `get` holds for it. The cost is the
   unobserved network path that is stated above.
3. **The script holds no query.** It asks the tool for each request and holds
   each one to a form: `api/v1/query?query=` and a percent-encoded expression.
   So one file registers the queries, and the script cannot be given a path to
   another API of the collector.
4. **A query set has a name and a digest.** The header of a collection states
   both, and the tool reads only a collection of its own set. A stream therefore
   names the queries that were asked.
5. **Each query aggregates.** `sum`, `count`, and `min` drop each label that a
   `by` clause does not name. So no series names a pod, a target, or a scrape
   job, and the scrape state of a tier is two counts and not one series for each
   pod.
6. **The instant of the oldest scrape of each tier is a query.** A value of an
   instant query can be older than its read. The two `oldest-scrape` queries
   state by how much, for the scrape state.
7. **Sampling, and not one range query at the end of a run.** The series of the
   collector go when its pod goes. A read during the run keeps what was read,
   and it gives each reading two instants on the host clock.
8. **The end line states two bounds of the clock difference.** The collector
   takes its evaluation instant while the read is open, so the two instants of
   the read bound the difference. The header still states the skew as not
   measured.
9. **The events tool takes the instant, and no argument states it.** An instant
   of another clock is a second field.
10. **An event holds no free text.** A code is a word of a fixed form. The tool
    does not register the codes: the frozen record of an experiment does.
11. **A judgement states the actor `operator`.** A reviewed detection, a
    reversal decision, and a manual action are refused from the control process.
12. **The evidence layout gains the role `operator-events`.** Its vocabulary is
    closed, and no role could name a log of operator events.
13. **No `changes` command for the two streams.** The timeline tool has one. A
    difference of two counter readings is the start of a rate, and an analysis
    owns that.

## The negative controls

Each is a test that fails when the property is removed.

| Property | Control |
|---|---|
| No series is not zero | An answer with no series gives `no-series` and no number. A sum of `0` gives a value of zero. The two readings are compared |
| A read that did not answer is not a result | A query with no answer file, a release with no collector, a sample with no status file, and an answer that is not an instant vector each give no result |
| A read of one query does not change another | A query that fails leaves each other reading of the sample as it was, in the tool and in an executed run of the script |
| A label that is not registered does not reach a stream | A series with a request identifier label, a target label, a name label, and a label of another query each leave the reading with no series, and neither the name nor the value is in the stream |
| A stored stream is held to its labels | A stored series with a request identifier label is refused by the check, and the refusal does not repeat the value |
| A value has the form of its kind | 28 stated values over the three kinds: a value that is not a number, an infinity, a count with a fraction, a negative count, a JSON number in place of text, and digits that are not ASCII are each `malformed` |
| The script gives kubectl no text that it did not hold to a form | Twelve outputs of the tool that are not usable each stop the script before any kubectl call. Among them are a path to an admin API, a path to another proxy, a second parameter, and a shell separator |
| The script changes nothing | An executed capture makes no kubectl call that is not a known read. Each raw path is under the proxy path of the one Service |
| The instant of an event is the tool's | The function and the command have no argument for it, and `--recorded-at` exits 2 |
| An event holds no free text | 33 events are refused with nothing written: a sentence, an address of a person, a path, and a line break as a code; a node, a secret, and an address with a credential as a subject |
| A log is appended to | Each event leaves each earlier byte as it was. A closed log, an existing file, a full log, and a file whose last line is not whole take no event |
| Each rule of form refuses | 53 changed streams and 50 changed logs. Each of the 11 and of the 10 rules has a case |

## Validation at the first commit

Each command ran on the tree of the first commit, before it was committed.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 733 files already formatted |
| `uv run --locked python -m mypy` | No issue in 406 source files |
| `uv run --locked python -m mypy --platform linux` | No issue in 406 source files |
| `uv run --locked python -m pytest tests/domain/test_experiment_telemetry.py -q` | 204 passed |
| `uv run --locked python -m pytest tests/domain/test_experiment_events.py -q` | 134 passed |
| `uv run --locked python -m pytest tests/architecture/test_experiment_telemetry_collector.py -q` | 49 passed |
| `uv run --locked python -m pytest tests/testing -q` | 8,372 passed, 3 skipped. It ran before the changelog entry and this record were written |
| `uv run --locked python -m pytest -q` | See the default lane below |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ. `V2-S5-003-PR1` recorded the same number on its base |
| `bash -n scripts/environment/experiment-telemetry.sh` | No syntax error |
| `git diff --cached --check` | No whitespace error |

`shellcheck` is not installed on this host, and no workflow runs it over
`scripts/`. So the new script was not linted. `gitleaks` is not installed on
this host either, so no secret scan ran here. The hosted workflow did not run
before the push, so no hosted result is stated here.

**Five defects were found before the first commit, and none by a reviewer.** The fifth is the failure of the default lane, which is described below.

- **A page said that the delivered release has no collector, and it has one.**
  The first draft of the telemetry page read the default of the chart and the
  generated values, and concluded that the release that the Application delivers
  installs no collector. The hand-written values of the Application set
  `telemetry.collection.collector.deploy`. The section now says which release
  has a collector, and a test reads the two files.
- **The script held a request to a form that the shell could not evaluate.** A
  repetition bound of 512 is above what the regular expressions of the shell
  admit, so the form matched nothing and each executed test refused. The form
  now has no bound, and a second test of the length follows it.
- **A test said that a binary fraction reads an instant one millisecond low.**
  It does not for the instants that were tried. The tool reads the instant as a
  decimal, and the test now holds that a finer fraction is cut and not rounded.
- **A function name was read as a barred label.** `timestamp` is a label that
  the catalog bars and also a function of the query language. The test now
  reads a name that an opening bracket follows as the function.

## The default lane

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 21,703 passed, 42 skipped, 14 deselected, 1 failed, in 55 minutes |

The lane ran once, on the tree of the first commit before one correction. It ran
on one Windows host. The skipped tests are the ones that this host cannot run,
and the deselected tests need a cluster or a model.

**One test failed in the lane, and the cause was in this change.**
`test_no_committed_file_carries_a_personal_filesystem_path` in
`tests/security/test_security_baseline.py` found a path under a user directory
in two of the new suites. Each was an invented value that a test gives the tool
to show that the tool refuses it. Each is now built from two parts, so no
committed file holds the path as text. After the correction,
`uv run --locked python -m pytest tests/security tests/domain/test_experiment_telemetry.py tests/domain/test_experiment_events.py -q`
gave 1,421 passed. The lane was not run again, so no run of the whole lane with no failure
is stated here. The hosted workflow did not run before the push.

## Privacy and publicability

The suites build every collection and every log with invented names and
addresses, in a temporary directory. No collection, no stream, and no log is
committed. The changed files hold no personal path, no credential, no account
identifier, and no host name. The diff against the base was read for each.

## What the evidence establishes

- The telemetry tool gives one text for one collection. It states a read state
  and no result for each read that did not answer, and `no-series` for each
  answer with no series, in the cases that the suite names.
- The script, as committed, asks a cluster for one read of one Service and one
  read for each registered query with `get` and no other verb, and writes what
  the stand-ins answer.
- The events tool writes the instant that its clock states, appends without a
  change to an earlier byte, and refuses each event and each stored log that the
  suite names.
- Each page, its tool, and the script agree on the names, the bounds, the rules,
  the limitations, and the boundaries that the suites compare.

## What the evidence does not establish

- What a telemetry collector answers, or that the tool reads the answer of a
  running one.
- That the Service proxy path reaches a collector on any provider.
- That the read timeout ends a read that hangs.
- That a stream or a log of a real run is correct. None exists.
- The difference between the host clock and the clock of a collector on any
  environment.
- That the allowlist of a stream or the forms of an event exclude every secret.
  The tests name the values that they cover.
- Anything about a caller. A stream and a log are not a caller's result.
- Anything about an experiment. No run started, and no criterion was read.
