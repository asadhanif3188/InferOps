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
| Commits | The first commit: the tool, the suite, the six cases, and the pages. The second commit: the corrections of the independent review, and the record of them in this file |
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
  214 tests. It builds each input with the tool that defines it.
- [Six cases](../../../tests/domain/fixtures/reliability-analysis) of 41 files:
  zero failure, concurrency, missing signal, open episode, clock ties, and
  abort. Each is a declaration, the inputs, and the analysis document. The
  suite builds each case again and compares the files byte for byte.
  `.gitattributes` pins the directory to LF.
- [The analysis page](../../testing/reliability-analysis.md), with each
  definition, the endpoints of each figure, the clocks, the limits, and what a
  document does not establish. The tables of the rules, the reasons, the
  sources, and the metrics, and the two lists of statements, are written from
  the constants of the tool.
- The contributor guide, the README, one architecture table, the changelog, the
  index of the testing pages, the index of the proof records, and the test
  inventory each gain an entry. Four pages that said "an analysis does that"
  now name the tool and say what it does not read: the timelines page, the
  telemetry page, the operator events page, and the evidence layout page.

**No existing tool changed.** The analysis imports the reader of the
reliability runner, of the timeline tool, and of the events tool, and the two
tier names of the endpoint-state tool. No chart, manifest, schema, contract,
script, or freeze record was changed. The vocabulary of the evidence layout
already held the derived role `analysis`, so it was not changed.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The caller failure episode | Reached at C0. An episode starts at the completion of its first failed request and ends at the completion of the next successful request. The figure of a window is 0 with no failed request, the longest episode when each is closed, and no value when one is open |
| The maximum success gap | Reached at C0. The largest time between two consecutive successful completions in the window, with the two requests named. Fewer than two give no value |
| The intervals with no Ready endpoint | Reached at C0, as two figures for each interval and four for each tier. A stream is sampled, so no single figure is exact. The page states that |
| The detection lag of a signal | Reached at C0, as two bounds, for six sources of the four timeline streams. No source reads a telemetry stream |
| The false-healthy and the false-unavailable time | Reached at C0, each as an inner figure, an outer figure, and the caller time in which the signal had no value |
| The stabilized recovery | Reached at C0: 10 consecutive successful completions over 60 seconds, with each reading of three conditions held. One part of the definition is a decision of this change: how a reading shows that the expected revision is present |
| Fixtures for zero failure, concurrency, a missing signal, an open episode, clock ties, and an abort | Reached. Six committed cases, each with hand-computed assertions in the suite |
| Each metric states its endpoints | Reached. An episode and a gap name their requests. An interval names its first and last reading and the reading that bounds it on each side. A lag names its two instants |
| No availability percentage and no confidence interval | Held. A test reads each member name of each committed document and of an aggregate. The command has no option that takes a bound |

### The criteria of the parent change

| Criterion | State after this change |
|---|---|
| The analysis computes the failure episode, the maximum success gap, the zero-Ready interval, the detection lag, the false-healthy and false-unavailable time, and the stabilization exactly | Reached at C0 for files that the suite builds. A caller figure is exact to one millisecond. A figure of a sampled stream is two bounds |
| The analysis replays from raw evidence and records the code revision | Pending. The other change of this story owns it. A document states no digest of an input and no code revision. The command reads raw files and prints the same text for the same files, and a test holds that |
| Small-sample aggregation follows registered rules | Reached at C0 for one rule: the median of three counted runs, with each run listed and no interval. No frozen record registers the rule yet |
| Missing or inconclusive data cannot become a fabricated result | Reached at C0 for the cases that the suite names. The section on negative controls lists them |

## What was not done

- **No run was analysed.** No run directory of the evidence layout exists, and
  no caller record, stream, or log of a real run is committed. Each input is
  built by the suite.
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
- The analysis does not read the second instant of an event, the detection
  event, or the three reversal events. It computes no decision time and no
  reversal time.
- The analysis does not pair a deleted pod with its replacement.
- The layout check does not call the tool, and nothing computes a committed
  analysis document again.
- No cluster was contacted. This change needs none.

## Decisions taken in this change

Each is a decision that the requirement left open. Each is stated on the page.

1. **A new tool, and no change to an existing one.** The analysis imports four
   tools and changes none.
2. **The declaration is an input.** The tool registers no threshold, no
   expected count, and no window. It registers the sources that it can read
   and the two figures of the stabilization rule. A declaration is not held to
   a frozen record, because none states these values. A declaration that is
   written after the evidence is read can move a figure. The document repeats
   each declared value.
3. **A sampled state has two figures and not one.** A rule that carries a value
   from one read to the next gives one figure, and that figure states a value
   for a time in which no read gave one. The inner and the outer figure state
   only what the reads gave.
4. **Two completions of one millisecond are ordered by the position of their
   lines.** The instants do not order them. Each end of an episode states
   `tied`.
5. **The episode figure of a window is the longest closed episode.** The
   requirement defines one episode and the figure 0 for no failure. It does not
   define the figure for several episodes. The document lists each episode.
6. **The first caller impact is a completion instant.** It is the completion of
   the first failed request at or after the first fault event. The request was
   sent earlier, and the document states that instant.
7. **The fault is one pair of events with one code.** Any other combination is
   `ambiguous`, and the metrics that read the fault then have no value.
8. **A recorded abort ends the window.**
9. **A caller record that does not cover the window gives no caller metric.**
10. **The expected revision is present when a reading reports the declared
    commit as `resolvedRevision` and a `syncStatus` of `Synced`.** The
    requirement says "present" and names no field. A resolved commit alone
    does not show that the live state is that commit.
11. **A stabilization span holds at least one reading of each condition, and
    starts after the last reading that did not hold or had no value.** The
    search starts when the fault command returned.
12. **A request is failed when the caller record states `success` as false.**
    No outcome is left out or weighted.
13. **The aggregate is in this change, with one rule.** The median is stated
    for exactly three counted runs. A run in the state `PASSED` or `FAILED` is
    counted.
14. **The six cases are committed files, and the suite builds them again.**
    The builder is in the test module, and the module writes the files when it
    is run as a script.

## The negative controls

Each row is a property and the case that would show it is false.

| Property | Control |
|---|---|
| An open episode has no duration | The last episode of `open-episode` and of `abort` states no end and no figure, and `callerFailureEpisodeMs` is null. It is not the time to the end of the window |
| No failed request is 0, and not no value | `zero-failure` states 0 and no episode |
| Fewer than two successes give no gap | Zero and one successful completion each give no value. Neither gives 0 |
| A record that does not cover the window gives no caller metric | A record that starts one millisecond late, and one that ends one millisecond early |
| The line order decides only a tie | Two tied lines in both orders give 0 ms and 3,000 ms. Three lines that are not tied give one result in two orders |
| A read that did not answer is not a reading of zero | Two such reads between two reads of a count give no interval. A tier with no read of a count is `not-observed` and has no count |
| A reading with no value does not bound an interval | An interval between two such readings is bounded by the readings beyond them |
| An omitted Deployment count is not zero | A reading with no `readyReplicas` is `not-observed` for both Deployment sources, and the first indication is the next reading |
| A pod with no Ready condition is not counted as not Ready | The pod count of that reading has no value |
| A missing field of the Application is not healthy | A reading with no sync status, no health status, and no Application each give `not-observed` |
| The order of a lag is stated only when both bounds agree | Three placements of the first problem reading give `signal-first`, `caller-first`, and `not-established` |
| A problem that predates the fault is not a first indication | The lag has no value |
| A run is not stabilized at nine successes, or at 59,999 ms | Each gives `stabilized: false`. Ten successes over 60,000 ms give true |
| A reading that does not hold moves the span | Five changes of one reading, one for each condition and its parts, each move the start |
| A reading with no value is not a reading that holds | Three such readings each move the start to after the next read. With no next read the run is not stabilized |
| A span with no reading inside is not stabilized | One read before the span, with each condition held |
| Without a stream the recovery is not computable | Each of the three streams left out gives `stabilized: null`, not false |
| A counted run with no value is not dropped | The aggregate then has no median |
| The median is for three counted runs | One, two, and four runs, and three runs with one excluded, give no median |
| A value that is not a whole number is no value | A boolean, a fraction, a text, a list, and an object |
| Each rule refuses | 38 changed declarations, 5 texts that are not one object, 5 inputs that their own reader refuses, 6 inputs of another run, 2 misnamed inputs, and 7 aggregates |
| A refusal does not repeat a value of the file | A caller line with an added member is refused by the rule of the runner, and the added text is not in the refusal |
| A document names no request and no pod | Each committed document is read for a request identifier of its run, a pod name, and a pod UID |

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
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ. `V2-S5-003-PR2` recorded the same number on its base |
| `uv run --locked python -m tools.experiment_evidence repository` | 3 run directories, each pre-schema and not checked. No change |
| `python tests/domain/test_reliability_analysis.py`, and then `git status` | The six cases are written again, and no file differs |
| `git diff --cached --check` | No whitespace error |

The default lane was not run at the first commit. It ran once, on the tree of
the second commit, and its result is below.

## Privacy and publicability

- No file of this change holds a credential, a prompt, a completion, a model
  file, a path of a personal directory, or the name of a person.
- The caller records of the six cases are built by the suite. Each states
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
  defines it, and each figure states the request or the reading at each end.
- A value that the files do not hold gives a metric with no value and one of
  13 reasons, for each case in the table of negative controls.
- An input that its own reader refuses, a file of another run, and a
  declaration outside its form are refused with nothing printed.
- The same files give the same text.

**It does not establish:**

- Any figure of a real run. No run was analysed.
- That a caller record, a stream, or a log of a real run has the form that the
  suite builds. The inputs are written by the three tools that define them.
- That a declared threshold, an expected count, or a window is the one that an
  experiment freezes.
- The difference between the clock of the runner's pod, the clock of the
  collecting host, and the clock of the recording host. Each figure that
  compares two of them holds that difference.
- The result of a run, an availability figure, or a production SLO.
