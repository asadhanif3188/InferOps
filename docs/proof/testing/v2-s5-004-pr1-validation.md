# V2-S5-004-PR1 validation

Status: **the reliability metrics of an experiment run can be computed from its
stored evidence. The tool is checked at evidence level C0, against caller
records, streams, and logs that the suite builds. No run was analysed, no
analysis of a real run is committed, no figure was compared with a bound, and
no claim was registered.**

| Property | Value |
|---|---|
| Date | 2026-10-12 |
| Base | `54b7c0b`, the merge of pull request #141 |
| Branch | `feat/v2-s5-004-reliability-analysis` |
| Commits | The first commit, `df524a8`: the tool, the suite, the six cases, and the pages. The second commit: the corrections of two independent reviews, and the record of them in this file |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv`. `gitleaks` is not installed |
| Evidence level | C0. Every check reads committed files or reads a file that the suite built. No check contacts a cluster, a caller, or a telemetry collector |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or freeze record was added or changed |

## What changed

- [`tools/reliability_analysis`](../../../tools/reliability_analysis/__init__.py)
  reads a declaration, a caller record, the four timeline streams, and the log
  of operator events, and prints one analysis document. A second command prints
  one figure of several analysis documents and the median of three counted
  runs.
- [`tests/domain/test_reliability_analysis.py`](../../../tests/domain/test_reliability_analysis.py),
  229 tests from 115 test functions. The first commit held 214 from 100.
- [Six cases](../../../tests/domain/fixtures/reliability-analysis) of 41 files:
  zero failure, concurrency, missing signal, open episode, clock ties, and
  abort. Each is a declaration, the inputs, and the analysis document. The
  suite builds each case again and compares the files byte for byte.
  `.gitattributes` pins the directory to LF.
- [The analysis page](../../testing/reliability-analysis.md), with each
  definition, the ends of each interval, the clocks, the limits, and what a
  document does not establish. The tables of the rules, the reasons, the
  sources, and the metrics, and the two lists of statements, are written from
  the constants of the tool.
- The contributor guide, the README, one architecture table, the changelog, the
  index of the testing pages, the index of the proof records, and the test
  inventory each gain an entry. Four pages that said "an analysis does that"
  now name the tool and say what it does not read: the timelines page, the
  telemetry page, the operator events page, and the evidence layout page.

**No existing tool changed.** The analysis imports five tools and changes none:
the reader of the reliability runner, of the timeline tool, and of the events
tool, the tier names and one tier state of the endpoint-state tool, and the
result states of the ExperimentRun tool. No chart, manifest, schema, contract,
script, or freeze record was changed. The vocabulary of the evidence layout
already held the derived role `analysis`, so it was not changed.

**How the inputs of the suite are made.** The timeline tool builds each stream
from a collection that the suite invents, and the events tool writes each log.
The suite writes each caller record itself, with invented digests of a plan and
of a runner, and the runner's reader accepts it. No runner wrote one.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The caller failure episode | Reached at C0. An episode starts at the completion of its first failed request and ends at the completion of the next successful request. The figure of a window is 0 with no failed request, the longest episode when each is closed, and no value when one is open, when the window starts inside one, or when the window holds no completion |
| The maximum success gap | Reached at C0. The largest time between two consecutive successful completions in the window, with the two requests named. Fewer than two give no value |
| The intervals with no Ready endpoint | Reached at C0, as two figures for each interval and four for each tier. A stream is sampled, so no single figure is exact. The page states that |
| The detection lag of a signal | Reached at C0, as two bounds, for six sources of the four timeline streams. No source reads a telemetry stream |
| The false-healthy and the false-unavailable time | Reached at C0, each as an inner figure, an outer figure, and the caller time in which the signal had no value. The first commit computed the inner figure wrongly, and the section on the reviews states how |
| The stabilized recovery | Reached at C0: 10 consecutive successful completions over 60 seconds, with each reading of three conditions held. Two parts are decisions of this change: how a reading shows that the expected revision is present, and that one reading of each condition inside the span is enough |
| Fixtures for zero failure, concurrency, a missing signal, an open episode, clock ties, and an abort | Reached. Six committed cases, each with hand-computed assertions in the suite |
| Each metric states its endpoints | Reached for an episode, a gap, an interval, a detection lag, and a stabilization span: each names the request or the reading at each end. Not applicable to the false-healthy time, the false-unavailable time, and the totals: each is a sum and names no end |
| No availability percentage and no confidence interval | Held. A test reads each member name of each committed analysis document and of an aggregate document. The command has no option that takes a bound |

### The criteria of the parent change

| Criterion | State after this change |
|---|---|
| The analysis computes the failure episode, the maximum success gap, the zero-Ready interval, the detection lag, the false-healthy and false-unavailable time, and the stabilization exactly | Reached at C0 for files that the suite builds. A caller figure is computed from instants of one millisecond. A figure of a sampled state is an inner and an outer figure, and neither is the exact time. A detection lag is two bounds |
| The analysis replays from raw evidence and records the code revision | Pending. The other change of this story owns it. A document states no digest of an input and no code revision. The command reads raw files and prints the same text for the same files, and two tests hold that, one of them in two processes with two hash seeds |
| Small-sample aggregation follows registered rules | Reached at C0 for one rule: the median of three counted runs, with each run listed and no interval. No frozen record registers the rule yet |
| Missing or inconclusive data cannot become a fabricated result | Reached at C0 for the cases that the suite names, after the corrections of the second commit. The section on negative controls lists them. Two limits stay: no limit holds the time between two readings of a stabilization span, and none holds the time with no completion of a caller. The document states both times |

## What was not done

- **No run was analysed.** No run directory of the evidence layout exists, and
  no caller record, stream, or log of a real run is committed.
- **No figure was compared with a bound, and no result state was decided.** No
  frozen record states a bound, a window, an expected state, or a signal.
- **The document does not state the digest of an input or the revision of the
  code.** The other change of this story owns both, and the replay of a
  committed document from committed raw files.
- **No signal is read from a telemetry stream.** A rate of errors and the
  reachability of a scrape target have no source. A threshold on a rate is a
  larger decision than a threshold on a count, and no frozen record states one.
- **A Deployment count of zero is not read.** The timeline stream states an
  omitted count as `missing`, and the API omits a count of zero. A signal of a
  Deployment count has no value in such a reading. It does not state the
  problem.
- **No limit holds the time between two readings.** A stabilization span needs
  one reading of each condition. A collector that stops after the first seconds
  of a span does not prevent a stabilized recovery. The document states the
  longest time of the span with no reading, and no rule reads it.
- The analysis does not read the second instant of an event, the detection
  event, or the three reversal events. It computes no decision time and no
  reversal time.
- The analysis does not pair a deleted pod with its replacement.
- The aggregate does not compare the windows or the declarations of its
  documents, and it does not read a manifest for a result state.
- The layout check does not call the tool, and nothing computes a committed
  analysis document again.
- No cluster was contacted. This change needs none.

## Decisions taken in this change

Each is a decision that the requirement left open. Each is stated on the page.

1. **A new tool, and no change to an existing one.**
2. **The declaration is an input.** The tool registers no threshold of a
   signal, no expected count, and no window. It registers the sources that it
   can read, the two figures of the stabilization rule, and the sync status
   `Synced`. A declaration is not held to a frozen record, because none states
   these values. A declaration that is written after the evidence is read can
   move a figure. The document repeats each declared value.
3. **A sampled state has two figures and not one.** A rule that carries a value
   from one read to the next gives one figure, and that figure states a value
   for a time in which no read gave one.
4. **Two completions of one millisecond are ordered by the position of their
   lines.** The instants do not order them. Each end of an episode states
   `tied`.
5. **The episode figure of a window is the longest episode when each is
   closed, and no value when one is open.** The requirement defines one episode
   and the figure 0 for no failure. It does not define the figure for several
   episodes. The document lists each episode.
6. **The first caller impact is a completion instant.** It is the completion of
   the first failed request at or after the first fault event. The request was
   sent earlier, and the document states that instant.
7. **The fault is one pair of events with one code.** Any other combination is
   `ambiguous`. The detection lag and the stabilized recovery then have no
   value, and the search for the first impact starts at the start of the
   window.
8. **The earliest recorded abort ends the window.**
9. **A caller record that does not cover the window, and a window with no
   completion, give no caller metric.**
10. **A window that starts inside an episode has no episode figure.** The
    second commit added this.
11. **The expected revision is present when a reading reports the declared
    commit as `resolvedRevision` and a `syncStatus` of `Synced`.** The
    requirement says "present" and names no field. A resolved commit alone
    does not show that the live state is that commit.
12. **A stabilization span holds at least one reading of each condition, and
    starts after the last reading that did not hold or had no value.** The
    search starts when the fault command returned. No limit is set for the time
    between two readings, because no frozen record states one.
13. **A request is failed when the caller record states `success` as false.**
    No outcome is left out or weighted.
14. **For the two disagreement times alone, an open episode is counted as
    failing to the end of the window.** The episode itself has no duration.
15. **The aggregate is in this change, with one rule.** The median is stated
    for exactly three counted runs. A run in the state `PASSED` or `FAILED` is
    counted.
16. **The six cases are committed files, and the suite builds them again.**
    The builder is in the test module, and the module writes the files when it
    is run as a script.

## The negative controls

Each row is a property and the case that would show it is false.

| Property | Control |
|---|---|
| An open episode has no duration | The last episode of `open-episode` and of `abort` states no end and no duration, and `callerFailureEpisodeMs` is null with the reason `episode-open`. It is not the time to the end of the window. A success after the window is stated and does not close the episode |
| No failed request is 0, and not no value | `zero-failure` states 0 and no episode |
| A window with no completion is not 0 | A record that covers the window, with no completion inside it, gives no caller metric |
| A window that starts inside an episode has no figure | A failure before the window and a success inside it. The same record with the whole window gives 4,000 ms |
| Fewer than two successes give no gap | Zero and one successful completion each give no value. Neither gives 0 |
| A record that does not cover the window gives no caller metric | A record that starts one millisecond late, and one that ends one millisecond early |
| The line order decides only a tie | Two tied lines in both orders give 0 ms and 3,000 ms. Three lines that are not tied give one result in two orders |
| The earliest abort ends the window | Two abort events whose instants are not in line order |
| A read that did not answer is not a reading of zero | Two such reads between two reads of a count give no interval. A tier with no read of a count is `not-observed`, has no count, and states the reason `no-count-in-window` |
| The inner figure holds no time across a reading with no value | An interval of five readings of zero with one such reading between them has the sum of two parts. A signal that is healthy on both sides of two such readings has an inner false-healthy time of 5,000 ms, where the first commit stated 35,000 ms |
| A reading with no value does not bound an interval | An interval between two such readings is bounded by the readings beyond them |
| An omitted Deployment count is not zero | A reading with neither count is `not-observed` for both Deployment sources, and the first indication is the next reading |
| A pod with no Ready condition is not counted as not Ready | The pod count of that reading has no value |
| A missing field of the Application is not healthy | A reading with no sync status, no health status, and no Application each give `not-observed` |
| The order of a lag follows its bounds | Four placements of the first problem reading give `signal-first`, `caller-first`, `not-established`, and `signal-first` with no lower bound |
| A problem that predates the fault is not a first indication | The lag has no value |
| A run is not stabilized at nine successes, or at 59,999 ms | Each gives `stabilized: false`. Ten successes over 60,000 ms give true |
| A reading that does not hold moves the span | Five changes of one reading, one for each condition and its parts, each move the start |
| A reading with no value is not a reading that holds | Three such readings each move the start to after the next read. With no next read the run is not stabilized |
| A span with no reading inside is not stabilized | One read before the span, with each condition held |
| Without a stream the recovery is not computable | Each of the three streams left out gives `stabilized: null`, not false |
| A counted run with no value is not dropped | The aggregate then has no median |
| The median is for three counted runs | One, two, and four runs, and three runs with one excluded, give no median |
| A value that is not a whole number is no value | A boolean, a fraction, a text, a list, and an object |
| Each rule refuses | 38 changed declarations, 5 texts that are not one object, 5 inputs that their own reader refuses, 6 inputs of another run, 2 misnamed inputs, 3 aborts at or before the window start, and 7 aggregates |
| A refusal does not repeat a value of the file | A caller line with an added member is refused with the rule `caller-record-members-unsupported`, and the added text is not in the refusal |
| A document names no request and no pod | Each committed document is read for a request identifier of its run, and for each pod name, ReplicaSet name, and UID that the builder invents |
| The tool reaches no network and writes no file | The imports of the three modules are read for seven modules, and their text for six calls |

**A control that does not hold.** A stabilization span with two readings in its
first seconds and none after them is stabilized. A test states that, with the
57 seconds of the span that have no reading. The rule sets no limit, and this
change does not invent one.

## Validation at the first commit

Each command ran on the tree of the first commit, on the host above.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 740 files already formatted |
| `uv run --locked python -m mypy` | No issue in 410 source files |
| `uv run --locked python -m mypy --platform linux` | No issue in 410 source files |
| `uv run --locked python -m pytest tests/domain/test_reliability_analysis.py -q` | 214 passed |
| `uv run --locked python -m pytest tests/testing tests/security tests/domain/test_renderer_input_boundary.py tests/domain/test_reliability_analysis.py tests/architecture/test_argocd_bootstrap.py -q` | 9,940 passed, 3 skipped |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ. `V2-S5-003-PR2` recorded the same number |
| `uv run --locked python -m tools.experiment_evidence repository` | 3 run directories, each pre-schema and not checked. No change |
| `python tests/domain/test_reliability_analysis.py`, and then `git status` | The six cases are written again, and no file differs |
| `git diff --cached --check` | No whitespace error |

The default lane was not run at the first commit.

## What the independent reviews found

Two reviews read the first commit. Neither changed a file. One read the code
and executed inputs against it. The other compared each sentence of the pages,
of this record, and of the commit message with the code and the suite. Each
finding below was reproduced before it was corrected.

**The message of the first commit is not corrected, because a commit is not
rewritten.** It says "one of 13 reasons", "The tool registers no threshold",
and "A document holds no result". The second, the third, and the count are
corrected below.

### What the code got wrong

- **The inner figure counted time with no reading as the state.** A reading
  with no value did not end a run, and the inner figure ran from the first to
  the last read of the run across it. A signal that was healthy before and
  after two reads that did not answer had an inner false-healthy time of
  35,000 ms, of which about 29,800 ms had no read. The page said that such time
  is in neither figure. That is a value that was not read, counted as healthy.
  A reading with no value now divides a run, and the inner figure is the sum of
  the parts. The same change applies to an interval with no Ready endpoint. One
  figure of the six committed cases changed: the inner false-healthy time of
  the Deployment signal of `missing-signal` went from 23,200 ms to 2,800 ms.
- **A window with no completion gave an episode figure of 0.** The record
  covered the window, no request completed in it, and the document stated 0 ms
  and 0 failed requests. Such a window now gives no caller metric, with the
  reason `no-completion-in-window`. The document also states the longest time
  of the window with no completion.
- **A window that started inside an episode gave 0.** A failure before the
  window and a success inside it left no episode in the window. The figure now
  has no value, with the reason `episode-starts-before-window`.
- **The first abort by line ended the window, and not the earliest.** The
  events tool accepts a log whose instants are not in the order of its lines.
- **An open episode stated no reason, and a tier with no count stated none.**
  Both are listed in `withoutValue`. Each now states a reason. The reasons went
  from 13 to 17.
- **A stabilized recovery did not show how little of its span was read.** The
  span now states the longest time with no reading for each condition. The rule
  is not changed, and the control above states what that leaves open.

### What the tests got wrong

- The test that a reading with no value is not counted as healthy asserted the
  not-observed time and not the inner figure. It passed while the inner figure
  counted that time.
- The test that each metric with no value states a registered reason read only
  the members in the state `not-computable`. It did not read the episode figure
  or a tier.
- The test of the same text for the same files ran in one process. A second
  test now runs the command in two processes with two hash seeds.
- The test that a document names no pod read one pod name and one UID of four
  each. It now reads each name and UID that the builder invents.
- The test that a refusal does not repeat a value did not assert the rule.
- The test of the order of a lag was named for a property that another test
  contradicts: a lag with no lower bound states `signal-first`.
- No test covered an ambiguous fault or a fault before the window as the search
  start, an abort exactly at the window start, or the abort case's last
  episode.
- No test held that the tool writes no file and reaches no network. The page
  and the command said so.

### What the pages got wrong

- **This record described a second commit and a result of the default lane
  that did not exist.** It was written before either.
- **"Each input is built by the tool that defines it" was false for the caller
  record,** in this record, the page, the test inventory, and two docstrings.
  The suite writes the record and the runner's reader accepts it.
- **"Each metric with no value states one of 13 reasons" was false** for the
  episode figure and for a tier, and two of the reasons belong to the
  aggregate.
- **"That time is in neither figure" was false,** as the first code finding
  states. After the correction the inner figure holds none of it, and the page
  says that the outer figure can.
- **"Each figure states its ends" was broader than the document.** The
  disagreement times and the totals are sums.
- **"The analysis imports four tools" was a wrong count.** It imports five.
- **The contributor guide forbade what the tool does:** counting an open
  episode to the end of the window, which the two disagreement times do.
- **"The order is stated only when both bounds agree" was wrong** in this
  record and in the test inventory. The page was right.
- **The search start of the first impact was misstated** for an ambiguous
  fault and for a fault before the window.
- **"A document holds no result state" was false for an aggregate document,**
  which repeats the state that it was given for each run.
- **"The tool registers no threshold" was unqualified** in the changelog and
  the contributor guide. The tool registers the two figures of the
  stabilization rule and one sync status.
- The README said "from those files" after a sentence about the telemetry
  streams, which the analysis does not read.
- "A figure of a sampled stream is two bounds" was stronger than the page.
- The layout page said that the tool computes a file with the role
  `analysis`. The tool prints a document and writes no file.
- Three rows of the negative controls were stronger than their tests.
- The rule of the window said "not before" where the code refuses "at or
  before". Exit status 3 was described as printing nothing, and one line goes
  to standard error. The lead sentence of `notObservedMs` was broader than its
  list. One page wrote the work-item identifier in lower case.

### Noted, and not changed

- With no stated fault a stabilized recovery can be a state that no fault
  disturbed. The document states the state of the fault and the search start,
  and the page and the limitations say so.
- The false-healthy and the false-unavailable time are `computed` with 0 when
  the signal had no value for the whole caller time. `signalNotObservedMs`
  shows it.
- The aggregate accepts documents with different windows or declarations.
- The search for a stabilization span is quadratic in the number of
  completions. One reviewer measured 12 seconds for 8,000 completions with no
  span found. The runner's ceiling is 10,000 requests.
- A negative Ready endpoint count in a stored stream is read as not zero. The
  timeline tool does not write one.

## Validation at the second commit

Each command ran on the tree of the second commit, on the host above.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 740 files already formatted |
| `uv run --locked python -m mypy` | No issue in 410 source files |
| `uv run --locked python -m mypy --platform linux` | No issue in 410 source files |
| `uv run --locked python -m pytest tests/domain/test_reliability_analysis.py -q` | 229 passed. The first commit held 214 |
| `uv run --locked python -m pytest tests/testing tests/security tests/domain/test_renderer_input_boundary.py tests/domain/test_reliability_analysis.py tests/architecture/test_argocd_bootstrap.py -q` | 9,955 passed, 3 skipped. The first commit held 9,940 |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `python tests/domain/test_reliability_analysis.py`, and then `git status` | The six cases are written again, and no file differs |
| `git diff --check` against the base | No whitespace error |

Each analysis document of the six cases changed in the second commit. Each
gained the new members, and one figure of one document changed, as the first
code finding states. No input file of a case changed.

## The default lane

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 22,025 passed, 42 skipped, 14 deselected, no failure, in 52 minutes |

The lane ran once, on the tree of the second commit, before this table held its
result. The reasons of the 42 skipped tests were not read. None is a test of
this change: its suite ran alone with 229 passed and none skipped.

## Privacy and publicability

- No file of this change holds a credential, a prompt, a completion, a model
  file, a path of a personal directory, or the name of a person.
- The caller records of the six cases are written by the suite. Each states
  `promptText` and `completionText` as false and holds no text of a request.
- The streams of the six cases are built by the timeline tool from objects that
  the suite invents. They hold invented pod names and UIDs, and the one
  Application name that the Application procedure already publishes.
- An analysis document holds sequence numbers of requests and indexes of
  readings. It holds no request identifier, no pod name, and no pod UID, and a
  test holds that for each committed document.
- `gitleaks` is not installed on this host, so no secret scan ran here. The
  scan of the pull request is the check.

## What the evidence establishes

The evidence is static, at level C0.

**It establishes:**

- For files that the suite builds, the tool computes each figure as the page
  defines it. An episode, a gap, an interval, a lag, and a stabilization span
  state the request or the reading at each end.
- For each case in the table of negative controls, a value that the files do
  not hold is not read as zero, as healthy, or as held.
- An input that its own reader refuses, a file of another run, and a
  declaration outside its form are refused with no document printed.
- The same files give the same text, in one process and in two.

**It does not establish:**

- Any figure of a real run. No run was analysed.
- That a caller record of a real run has the form that the suite writes. No
  runner wrote a record of the suite.
- That a declared threshold, an expected count, or a window is the one that an
  experiment freezes.
- That a stabilized recovery was read over its whole span.
- The difference between the clock of the runner's pod, the clock of the
  collecting host, and the clock of the recording host. Each figure that
  compares two of them holds that difference.
- The result of a run, an availability figure, or a production SLO.
