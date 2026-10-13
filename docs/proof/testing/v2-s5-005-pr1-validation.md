# V2-S5-005-PR1 validation

Status: **an aggregate of runs leaves a run out of the median only for a reason
that the freeze record of the run registers, and it states that reason. The
change is checked at evidence level C0, against run directories, freeze
records, and registries that the suite builds from synthetic files. No run was
aggregated, no committed freeze record registers an exclusion reason, and no
claim was registered or changed.**

> **This change corrects a defect of an earlier change, and the record says
> so.** [`V2-S5-004-PR1`](v2-s5-004-pr1-validation.md) added the aggregate, and
> [`V2-S5-004-PR2`](v2-s5-004-pr2-validation.md) added the aggregate of run
> directories. The second record states, under "Noted, and not changed", that a
> manifest changed from `FAILED` to `INCONCLUSIVE` with a reason is no longer
> counted, and that no rule holds the reason to one that was registered before
> the run. A review of the sprint on 2026-10-13 reported that as a defect, with
> a probe. It was reported to the author, and no file in this repository records
> that review. The two earlier records are not edited.

| Property | Value |
|---|---|
| Date | 2026-10-13 |
| Base | `900a4548fcb0c0319d26ca1126411739cde4f496`, the merge of pull request #143 |
| Branch | `fix/v2-s5-005-preregistered-exclusion-reasons` |
| Commits | The first commit, `2f48ce9`: the two tools, the two suites, the pages, the driver, and its two outputs. The second commit: the corrections of two independent reviews, and the record of them in this file |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv`. `gitleaks` is not installed |
| Evidence level | C0. Every check reads committed files or reads a file that a suite or the driver built. No check contacts a cluster, a caller, or a telemetry collector |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, freeze record, run directory, or raw evidence file was added or changed. The committed evidence index is unchanged |

## The defect

The aggregate of `tools/reliability_analysis` decided whether a run is counted
from its result state alone. A run in the state `INCONCLUSIVE`, `REFUSED`, or
`ABORTED` was not counted, and the document stated `result-state-inconclusive`,
`result-state-refused`, or `result-state-aborted` for it. The aggregate of
`tools/analysis_replay` read the state from the manifest of the run and gave it
to the first. Neither read the reason that the manifest states, and neither
held that reason to anything.

**The probe.** Three synthetic runs have a figure, and a fourth, `FAILED`, has
an open episode and so no figure. The manifest of the fourth run alone is then
changed to `INCONCLUSIVE`, with the reason
`Excluded after inspection. No preregistered reason exists.`

| | At the base, `900a454` | At this change |
|---|---|---|
| Before the edit | 4 counted runs, `not-computable`, no median | 4 counted runs, `not-computable`, no median |
| After the edit | 3 counted runs, `computed`, median 20,900 ms | Refused |
| Each other byte of the run | Unchanged | Unchanged |
| A replay of the edited run | `replayed` | `replayed` |
| The reason of the manifest in the document | Absent | No document is printed |

The run stayed listed at the base. The defect was that one edit of one manifest
changed the number, and that the document did not show the reason.

## What changed

- [`tools/reliability_analysis`](../../../tools/reliability_analysis/core.py):
  the aggregate takes the result of each run as a state alone or as a
  `RunResult`, which holds the state, the reason, the exclusion reasons of a
  freeze record, and how a manifest names that record. A run in a state that
  is not counted is held to those exclusion reasons. Two rules are added,
  `analysis-exclusion-reasons-unsupported` and `analysis-exclusion-unregistered`,
  so the tool has 10. The `exclusion` member of a run is `null` or an object
  with `reasonId`, `reason`, and `preregistration`. The schema name of the
  document is `inferops.io/reliability-aggregate/v1alpha2`.
- [`tools/analysis_replay`](../../../tools/analysis_replay/core.py): the
  aggregate of run directories reads the reason from the manifest, and it reads
  the `exclusionReasons` member of the freeze record that the manifest names.
  It holds that record to the freeze registry of the tree, and it requires that
  each run of an aggregate that leaves a run out names that one record. Three
  rules are added, `replay-exclusion-record-unpinned`,
  `replay-exclusion-record-differs`, and `replay-exclusion-refused`, so the tool
  has 17. The first commit added two and had 16. Each run of the document states
  how its manifest names its freeze record. The schema name is `inferops.io/run-aggregate/v1alpha2`. The tool
  imports the reader of the registry from `tools/experiment_freeze`, which is
  not edited.
- [`tests/domain/test_reliability_analysis.py`](../../../tests/domain/test_reliability_analysis.py),
  286 tests from 129 test functions. The base held 229 from 115.
- [`tests/testing/test_analysis_replay.py`](../../../tests/testing/test_analysis_replay.py),
  175 tests from 119 test functions. The first commit held 165 from 115, and
  the base held 134 from 95.
- [The replay page](../../testing/analysis-replay.md#a-run-that-is-not-counted)
  states the member, the comparison, each refusal, and what the check does not
  do. [The analysis page](../../testing/reliability-analysis.md#the-aggregate-of-three-runs)
  states the two rules and what the command of that tool no longer does.
- The README, the contributor guide, the ExperimentRun page, the index of the
  testing pages, the index of the proof records, the test inventory, and the
  changelog each gain a statement.
- [The driver](v2-s5-005-pr1-exclusion-probe-driver.txt) and its two outputs,
  [at the base](v2-s5-005-pr1-exclusion-probe-at-base.json) and
  [at this change](v2-s5-005-pr1-exclusion-probe.json).

**What did not change.** No freeze record, no freeze registry, no run
directory, no raw evidence file, no manifest, no contract schema, no chart, and
no file under `scripts/`. The ExperimentRun schema is not changed: the `result` of a manifest
has the two members that it had. `tools/experiment_freeze` is not edited, and
the three committed freeze records pass its check as before. `analyze` gives
the bytes that it gave. `bind` gives the same figures and statements with
another `analysisCode`: four source files changed, so the source digest and
four source rows differ. `verify` still replays the committed example, and it
now prints `code differs` with those four files. The six committed cases and
the committed replay example are not written again.

## Where the reason is registered

**The freeze record that the manifest names.** A manifest names its freeze
record in `metadata.spec`, by path, revision, and content digest, and the
layout check already holds the record to the revision and the digest. A freeze
record is the document that fixes an experiment before its first
result-bearing run. So this change reads the exclusion reasons from that
record, and it adds no other authority.

The record states them in one top-level member, `exclusionReasons`. The freeze
check accepts a top-level member that it does not name, so no committed record
and no rule of the freeze check is changed. The freeze check does not read the
member. The aggregate holds it to its form when it reads it.

**The registry.** A file that a manifest names is a frozen record only when the
freeze registry pins it. The aggregate therefore requires, for a run that is
not counted, that `docs/proof/experiments/registry.v1alpha1.json` under the
root pins the record with the digest that the manifest states.

**One record for one aggregate.** When a run is not counted, each run of the
aggregate must name the same record, and the record must have the name of its
revision. So a run that is not counted does not choose the record that
registers its reason.

**The check reads files and no time.** It does not establish when a reason
was registered. It establishes that the record which each manifest names, and
which the registry pins, registers the reason.

**No experiment registers a reason here.** Each exclusion reason of the suites
and of the driver is synthetic text. The reasons of the builders say so. No reason, bound, or abort
condition of an experiment that has not been frozen is stated.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The aggregate reads and states the actual reason, and makes none from the result state | Reached at C0. The reason is read from the manifest, and the document states it with the identifier of the registered reason. The text `result-state-<state>` is no longer written |
| Each run that is not counted is held to the registered authority | Reached at C0. The authority is the freeze record that the manifest of the run names, pinned by the registry of the tree |
| A reason that is absent, changed, stale, unrelated, unregistered, or substituted after the run is refused | Reached at C0, with the exceptions that the next section states. An absent reason, a reason that differs by one character, a reason that no record registers, a reason of another state, another run, or another experiment, a reason that only an earlier revision registers, a reason added to the record while the registry pins the earlier content, and one manifest alone that names another record each refuse the aggregate |
| `PASSED` and `FAILED` stay counted, and an unfavourable counted run is not made an exclusion | Reached at C0 for what the tool can hold. A counted state is counted whatever reason the manifest states. A manifest that is changed to a state that is not counted needs a registered reason. **Not reached:** the tool does not decide that a registered reason is true of the run |
| A counted run with no value stays conservative | Reached at C0. Three counted runs, one with no value, and one excluded run give no median with the reason `counted-run-without-value` |
| A mutation of a reason, an input, or an output is detected | Reached at C0 for an input. A changed freeze record is refused by the layout check, and with each manifest restated it is refused by the registry. A substituted registered reason gives another document. **Not reached:** no check holds a stored aggregate document, as before. A stored copy is held by running the command again |
| No completed run, freeze record, raw evidence file, result state, evidence level, or claim is rewritten | Reached. `git diff --stat` against the base names no such file |
| No experiment executes, and the evidence is C0 | Reached |

## What the check does not do

- **It does not decide that a reason is true.** The manifest is the authority
  for the result state and for the reason. A person can change the manifest of
  a `FAILED` run to `ABORTED` with a reason that the record registers, and the
  aggregate accepts that manifest. The document then states that reason, the
  record, and another manifest digest. The history of the manifest in Git and
  the review of the run hold the classification.
- **It reads one tree and not Git.** A freeze record, each manifest that names
  it, and the registry, replaced together, are accepted. A test states that.
  `python -m tools.experiment_freeze --check` holds a committed record to its
  pin, and the history of the registry is in Git.
- **The freeze check does not read the member.** A committed record with an
  `exclusionReasons` member that is not in its form passes the freeze check.
- **A new record, added to the registry, with each manifest restated to name
  it, is accepted.** That is the same limit: one tree and not Git.
- **It does not hold the manifests to the latest revision.** When each manifest
  names an earlier revision that the registry pins, each run is held to that
  revision.
- **It does not establish when a reason was registered.** It reads no time.
- **It does not hold the record to the freeze check**, and it does not compare
  the experiment identifier of the exclusion reasons with another member of
  the record.
- **It has no rule for runs of two revisions with a run left out.** Such an
  aggregate is refused, also when a run was aborted under an earlier revision
  for a reason that the earlier revision registers. Runs that are all counted
  are aggregated whatever records they name.
- **It compares text as it is.** It applies no normalisation.
- **No check holds a stored aggregate document.** That limit is the one of
  `V2-S5-004-PR2`.
- **No experiment of two runs has a rule.** The one aggregate is the median of
  three counted runs, as before.

## Decisions taken in this change

- **The reason is compared as text, character for character.** A reason in a
  manifest is free text. A comparison that reads two texts as near would admit
  a reason that was not registered. So a manifest states the registered text
  itself, and a detail of one run belongs in the limitations of its manifest.
- **A reason can be registered for named runs.** The optional member `runIds`
  holds a reason to those runs. With no such member the reason is for each run
  of the experiment.
- **The exclusion reasons state the experiment identifier of the manifests.** A
  freeze record of another experiment, put beside the runs and pinned,
  registers no reason for them.
- **A registry is required for an exclusion alone.** An aggregate of counted
  runs reads no registry, so it is not refused for a missing registry. Its
  document has the new schema name, the `preregistration` member of each run,
  and nine rules where the base stated six.
- **Each run of an aggregate that leaves a run out names one record.** The
  first commit held each run to the record of its own manifest, and a review
  showed that one manifest alone could then name a record that registers its
  reason. The cost is stated above: no aggregate of runs of two revisions
  leaves a run out.
- **The command of the reliability analysis refuses a state that is not
  counted.** It reads no manifest and no freeze record, and a reason of the
  command line would be a reason that nothing registered.
- **The two schema names are `v1alpha2`.** One member changed its type. No
  document with the earlier names is committed.
- **The all-run rule is held before a reason is read.** A run that was left out
  is stated first.
- **The committed replay example is not written again.** No figure and no
  statement of a run analysis changed. The example states the source files of
  the commit that wrote it, so `verify` now prints `code differs` for it and
  names four files, and the replay holds.

## The negative controls

Each row is a property and the case that would show it is false.

| Property | Control |
|---|---|
| A result state alone leaves no run out | A run is given in each of the three states with no exclusion reasons, with a record that has no member, and with an empty list. Each refuses. The same through the command of the reliability analysis, which exits 3 and takes no `--reason` |
| The probe no longer gives a median | The probe above, with no registry and with a pinned record that does not hold the reason. Each refuses, and the refusal names the run and repeats no reason |
| A reason is compared character for character | A space at an end, another letter case, one character removed, two spaces for one, and text added. Each refuses |
| A reason of another result state is not a reason | The reason that is registered for `ABORTED`, stated by an `INCONCLUSIVE` run. Refused. One text that is registered for two states is accepted for a run in the second state |
| A reason of another run is not a reason | A reason with `runIds` that do not hold the run. Refused. With the run among them it is accepted |
| A reason of another experiment is not a reason | Exclusion reasons that state another experiment identifier. Refused |
| A reason that only an earlier revision registers is stale | Revision 1 registers the reason and revision 2 does not. With each run restated to revision 2, the aggregate is refused |
| A run does not go back to an earlier revision for its reason | From that state, the manifest of the run that is not counted is restated to revision 1 alone. Refused with `replay-exclusion-record-differs` |
| A record that is written after the runs gives one run no reason | A second record with the reason of the probe is added to the registry, no pin is changed, and one manifest alone names it. Refused with `replay-exclusion-record-differs` |
| A file without the name of its revision registers no reason | `notes.json`, a second file of revision 1, and `freeze-r2` with revision 1, each pinned and named by each manifest. Each refuses |
| A reason that is added to the record is refused while the registry pins the earlier content | The reason is written into the record. The layout check refuses each run. With each manifest restated, the registry does not pin the record. Refused |
| A registry is read in one way | A registry with `records`, `kind`, or `path` stated twice, which its own reader accepts, and two registries of 100,000 nested values. Each refuses with `replay-exclusion-record-unpinned` |
| A file that is not pinned registers no reason | No registry, a registry that cannot be read, and a registry that pins no record. Each refuses |
| Exclusion reasons in another form register nothing | 24 forms of the member, and 4 values that are no object. Each refuses with `analysis-exclusion-reasons-unsupported` |
| A counted run is counted whatever reason it states | A `FAILED` run with the worst figure and a registered reason is counted with its value, and no registry is read |
| An exclusion does not hide a counted run with no value | Three counted runs, one with an open episode, and one excluded run. No median |
| A substituted reason does not give the earlier document | One registered reason is replaced by another. The aggregate is accepted, and it states the other reason, its identifier, and another manifest digest |
| A run that was left out is stated before a reason is | Three of four runs are given, and one of the three has an unregistered reason. The refusal is `replay-aggregate-run-omitted` |
| A refusal repeats no text of a manifest or of a record | A marker in a stated reason, in a registered reason, in an experiment identifier, and in a member name. No refusal holds it |
| No committed freeze record registers a reason | The three committed records and the record of the example are read for the member |

**Two controls that do not hold.** A test states each.

- A freeze record, each manifest that names it, and the registry, replaced
  together, are accepted, and the document states another record digest.
- One registered reason replaced by another registered reason is accepted.

## The driver

[The driver](v2-s5-005-pr1-exclusion-probe-driver.txt) builds four synthetic
run directories for each of six cases, with the builders of the replay suite of
the tree that it runs in. It ran once in a second working tree at the base and
once in this working tree. It edits no committed file, and its output states no
path of the host.

| Case | At the base | At this change |
|---|---|---|
| `probe-no-registry` | 3 counted, median 20,900 ms, `result-state-inconclusive` | `replay-exclusion-record-unpinned` |
| `probe-reason-not-registered` | 3 counted, median 20,900 ms, `result-state-inconclusive` | `replay-exclusion-refused`, `analysis-exclusion-unregistered` |
| `probe-reason-of-another-state` | 3 counted, median 20,900 ms, `result-state-inconclusive` | `replay-exclusion-refused`, `analysis-exclusion-unregistered` |
| `registered-reason-aborted` | 3 counted, median 20,900 ms, `result-state-aborted`. The reason is not in the document | 3 counted, median 20,900 ms, `fixture-aborted`. The reason is in the document |
| `registered-reason-inconclusive` | 3 counted, median 20,900 ms, `result-state-inconclusive`. The reason is not in the document | 3 counted, median 20,900 ms, `fixture-inconclusive`. The reason is in the document |
| `failed-run-with-a-registered-reason-is-counted` | 4 counted, no median | 4 counted, no median |

The driver writes the freeze record after it builds the run directories, and it
restates the digest in each manifest. The builders of the tree at the base
write the freeze record themselves, so the driver cannot write it first there.
A figure of 20,900 ms is the figure of a committed synthetic case. It is the
figure of no run.

## Validation at the first commit

Each command ran on the files of the first commit, on the host above, before
the commit was made.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 746 files already formatted. **This run was before this record existed.** With the record the command counts 747 |
| `uv run --locked python -m mypy` | No issue in 414 source files |
| `uv run --locked python -m mypy --platform linux` | No issue in 414 source files |
| `uv run --locked python -m pytest tests/domain/test_reliability_analysis.py tests/testing/test_analysis_replay.py -q` | 451 passed: 286 and 165. The base holds 363: 229 and 134 |
| `uv run --locked python -m pytest tests/testing tests/security tests/contracts/test_experiment_run_v1alpha1.py tests/domain/test_reliability_analysis.py tests/domain/test_renderer_input_boundary.py tests/architecture/test_argocd_bootstrap.py -q -rs` | 10,510 passed, 3 skipped, with the files of the change staged. The three skips: this host does not let the suite create a symbolic link, its file system holds no line break in a file name, and one test of the freeze suite skips because a pinned file of E01 revision 3 changed before this change |
| `uv run --locked python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `uv run --locked python -m tools.evidence_index --gate` | Exit status 0 |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ. The base gives the same number, so this change moves no pinned file of that record |
| `uv run --locked python -m tools.experiment_evidence repository` | 3 run directories, each pre-schema and not checked |
| `uv run --locked python -m tools.analysis_replay repository` | 3 run directories, each pre-schema and not replayed, 0 with no analysis, 0 replayed, 0 refused |
| `uv run --locked python -m tools.analysis_replay verify` of the example, with its `--root` | `replayed`, 6 input files, `code differs` with four files of the two tools, and `revision  not-checked` |
| The driver, in a second working tree at the base and in this working tree | The results of the table above |

The default lane was not run at the first commit.

## What the independent reviews found

Two reviews read the first commit, `2f48ce9`. One executed inputs against the
code. The other compared each sentence of the pages, of this record, and of the
suites with the code. Each was an automated session, and neither edited a file.

### What the code got wrong

- **A run that is not counted could choose its record.** The first commit held
  each run to the record of its own manifest. A second record with the reason
  of the probe, added to the registry with no pin changed, and named by one
  manifest alone, gave a median of 20,900 ms. So did a file named `notes.json`,
  and a second file with revision 1. Each run of an aggregate that leaves a run
  out must now name one record, and the record must have the name of its
  revision.
- **A stale reason was accepted through one manifest.** With each run on
  revision 2, which does not register the reason, the manifest of one run alone
  was restated to revision 1, and the aggregate gave a median. The same rule
  refuses it now.
- **A registry of deep nesting was no refusal.** The reader of the registry left
  a `RecursionError`. The command exited 1 and printed a traceback with paths
  of the host. It is now a refusal with exit status 3.
- **A registry with a member stated twice was accepted.** Its reader keeps the
  last of two members. The aggregate now reads the registry first with no
  member stated twice.
- **A `preregistration` that is no mapping left an error that is no refusal** in
  the aggregate of the reliability analysis. It is refused.

### What the tests got wrong

- The test of a refusal that repeats no text reached an exclusion refusal in
  one of its three steps. The other two set the state `REFUSED` on a manifest
  with an injected fault, which the layout check refuses first. The steps now
  use `INCONCLUSIVE`, and each asserts its rule.
- The test of a superseded revision changed one manifest and never tried the
  earlier revision. It is two tests now.
- One test name said that a reason added after the run is refused, and the test
  ends with the accepted case. The name now states the condition.

### What the pages got wrong

- **"Registered before the run" was not what the check establishes.** The
  changelog, the replay page, and one comment of the code said it. The check
  reads no time.
- This record and the changelog listed "a superseded revision" and "added after
  the run" among the refusals without their conditions.
- This record said that `analyze`, `bind`, and `verify` give the bytes that they
  gave. That is true of `analyze` alone.
- The ExperimentRun page said that the validator does not read the text of a
  reason. It reads it for the shape of a credential and for a host path.
- This record said that each synthetic reason says that it is synthetic. The
  reasons of the builders do, and some reasons of single tests do not.
- This record stated 746 formatted files for a run that was before the record
  existed.
- The analysis page said that the document lists the freeze record. The
  function repeats what its caller gives.
- This record said "no script", and the change adds a driver.

### Noted, and not changed

- **A manifest that is changed to a state that is not counted, with a registered
  reason, is accepted.** This is the limit that "It does not decide that a
  reason is true" states. Each aggregate document now states it as one of its
  rules.
- A registered reason can end with a character of zero width. The comparison is
  of text as it is.
- The page of the freeze records is not edited, because a freeze record of E01
  names that page. The member is stated on the replay page and in the
  contributor guide.
- Two checks in the read of a freeze record are behind the layout check, and no
  test reaches them alone.
- The reader of the registry in `tools/experiment_freeze` is not edited. The
  aggregate reads the registry a first time itself.

## Validation at the second commit

Each command ran on the files of the second commit, on the host above, before
the commit was made.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 747 files already formatted |
| `uv run --locked python -m mypy` | No issue in 414 source files |
| `uv run --locked python -m mypy --platform linux` | No issue in 414 source files |
| `uv run --locked python -m pytest tests/domain/test_reliability_analysis.py tests/testing/test_analysis_replay.py -q` | 461 passed: 286 and 175. The first commit holds 451 |
| `uv run --locked python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `uv run --locked python -m tools.evidence_index --gate` | Exit status 0 |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ, as at the base |
| `uv run --locked python -m tools.analysis_replay repository` | 3 run directories, each pre-schema and not replayed |
| `uv run --locked python -m tools.analysis_replay verify` of the example, with its `--root` | `replayed`, 6 input files, `code differs` with four files, and `revision  not-checked` |
| The driver, in this working tree | The committed output, byte for byte |
| The inputs of the first review, as tests of the suite | The record that is written after the runs, the earlier revision named by one manifest, the three registries with a member twice, and the two nested registries each refuse |
| `git diff --check` against the base | No whitespace error |

## The default lane

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 22,272 passed, 42 skipped, 14 deselected, no failure, in 40 minutes |

The lane ran on the staged files of the second commit, from Git Bash, before this
table held its result. The command also had `-rs -p no:cacheprovider`. The base
recorded 22,172 passed and 42 skipped.

**A first run of the lane is not a result.** It was started from PowerShell,
where `bash` is the one of WSL and not Git Bash. 362 tests failed and 18 had an
error, each in a suite that runs a shell script, with a WSL error in the output.
No file was changed between the two runs.

## Privacy and publicability

- No file of this change holds a credential, a prompt, a completion, a model
  file, a path of a personal directory, or the name of a person.
- Each exclusion reason in the suites, the pages, and the driver output is
  synthetic text. No reason, bound, or abort condition of an experiment that
  has not been frozen is stated.
- The two driver outputs hold run identifiers of the synthetic cases, digests,
  rule names, and the synthetic reasons. They hold no path of the host: a
  freeze record is named by its path under the root of a case.
- A refusal of an exclusion names a run and a rule. It repeats no reason of a
  manifest or of a freeze record, and two tests hold that.
- An aggregate document repeats the reason of a manifest. The statement rules
  of the manifest apply to that text: it is not a place for a prompt, a
  completion, a credential, or a host path.
- `gitleaks` is not installed on this host, so no secret scan ran here. No
  pull request exists yet, and its scan has not run.

## What the evidence establishes

The evidence is static, at level C0.

**It establishes:**

- For run directories, freeze records, and registries that the suite builds,
  the aggregate refuses a run that is not counted and whose reason the freeze
  record of its manifest does not register for the experiment, the result
  state, and the run.
- For the probe that showed the defect, the aggregate that stated a median of
  20,900 ms at the base is refused at this change.
- For a registered reason, the aggregate lists the run with that reason, its
  identifier, and the path, the revision, and the content digest of the record.
- A run in the state `PASSED` or `FAILED` is counted whatever reason its
  manifest states.

**It does not establish:**

- Any figure of a real run. No run was aggregated, and no real run was left
  out of an aggregate.
- That a registered reason is true of a run that states it.
- That a freeze record, its manifests, and the registry were not replaced
  together in a tree.
- Which reasons an experiment will register. No committed freeze record states
  the member.
- A claim status or an evidence level. This change registers no claim.
- That the sprint of this change is accepted. Two other findings of the same
  review are owned by other changes.
