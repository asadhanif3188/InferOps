# V1-S1-006-PR2 — The workload scaffolding command, change validation

The record behind the command half of
[the workload template](../../scaffolding/workload-template.md). It records what
was run, on what, and what it may be used to claim — which is less than a reader
skimming a green session would assume. **Nothing here deployed a workload, served
one, started a runtime, or generated a workload anybody kept.** Workloads were
generated into pytest's own temporary directories, validated, run, and discarded
with the run. The [limitations](#limitations) and
[acceptance criteria](#acceptance-criteria) sections are the parts that say so.

> [!NOTE]
> **Post-record resolution (2026-09-02):** an independent Codex reviewer later
> executed the published mock and synchronous workflows from a clean detached
> worktree without editing generated output. The commands and results are in the
> [independent walkthrough](v1-s1-006-independent-walkthrough.md). The original
> run and its evidence status below are retained as historical evidence.

## Classification

| | |
|---|---|
| Evidence class | `local-static` for every check here |
| Ceiling | `C0` |
| What ran | The committed test suites, the linter, the formatter, the type checker, a distribution build, and the scaffolding command itself, from a checkout |
| What did not run | Any real model, runtime image, container engine, cluster, HTTP server, socket, paid service, or scanner |
| Claims certified by this record | none |

`local-static` is the weakest label these checks support and it is the correct
one. Every check reads files from this repository, writes into a temporary
directory, and compares what came out against documents also in this repository.
No result here says anything about serving, about a runtime, or about a workload
that was deployed.

**No claim moves to `certified` in this change**, and no layer's status changes.
`contract-and-schema` already covered `tests/scaffolding/`; this change adds a
third suite to that path rather than a new path or a new layer.

## Provenance

| Input | Value |
|---|---|
| Repository revision at branch point | `bf55d5d` |
| Branch | `feat/v1-s1-006-workload-scaffolder` |
| Repository tooling added | `tools/workload_scaffold/{__init__,__main__,arguments,generation}.py` |
| Distribution code added | none |
| Distribution code changed | `src/inferops/scaffolding/{__init__,template}.py` — two docstrings that said the writing half did not exist yet. **No behaviour changed**, and the diff carries no executable line |
| Tests added | `tests/scaffolding/test_workload_scaffolder.py` |
| Tests changed | none. The two `V1-S1-006-PR1` suites and the shared case module are untouched |
| Documents changed | [the template document](../../scaffolding/workload-template.md), [`CONTRIBUTING.md`](../../../CONTRIBUTING.md), [the changelog](../../../CHANGELOG.md), [the evidence index](../README.md) |
| Documents added | this record |
| Accepted records **not** changed | Every ADR, the workload contract schema, the compatibility matrix, every committed fixture, the telemetry catalog, the security baseline, the cost method, the test strategy and its data, `pytest.ini`, `pyproject.toml`, and `uv.lock`. **No row of the contract, and no fixture, was edited** |
| Dependencies added | none. The command uses `PyYAML` and `jsonschema`, which the `test` group already pins because `tools/contract_validation` already needs them |

### Why the command is repository tooling rather than part of the distribution

`tools/workload_scaffold/` sits beside `tools/contract_validation/` and outside
`src/inferops/`. Two accepted rules decide that, and neither is a preference.

**Nothing under `src/inferops` reads a path**, checked by
`tests/architecture/test_domain_dependency_boundary.py`, so that a domain object
is constructible from a wheel with no repository around it. Validating a
generated project needs the published JSON Schema — a file — and a YAML loader.

**The distribution declares no runtime dependency.** Putting the writer inside it
would have made `PyYAML` and `jsonschema` runtime dependencies of everything that
installs `inferops`, or would have forced the command to validate something
weaker than the document it wrote.

The consequence is stated rather than hidden: **the command needs a checkout**,
run through `uv run --locked`. That is the same prerequisite a generated
workload's own quick start already carries for
`python -m tools.contract_validation`.

## Environment

| | |
|---|---|
| Host | One Windows 11 development host |
| Interpreter | CPython 3.12.12, provisioned by `uv` from the committed [`.python-version`](../../../.python-version) |
| Dependency resolution | [`uv.lock`](../../../uv.lock), unchanged by this work; every command run with `--locked` |
| Network | Not used by any check |
| Model, runtime image, cluster | Not present, not required, not started |

## Method

Every command below was run from a checkout at the branch head, through
`uv run --locked` so that the versions are the committed ones rather than
whatever the host had.

The command was exercised from the same four representative parameter sets the
rendering suite uses — a minimal real workload, a minimal mock, and one of each
with every optional parameter supplied — held in
`tests/support/workload_template_cases.py` and shared by all three suites, so
they argue about the same inputs.

Each case was generated into a temporary directory, read back off that directory,
validated, and executed. Failures were injected rather than waited for: a write
was made to fail at its second file, a read-back was made to disagree, and the
contract validator was made to refuse — before the write and again from disk — so
that every guard is exercised by a check rather than described by a comment.

Three of those guards were then **mutation-tested by hand**: each was disabled in
turn and the suite re-run, to establish that the check fails when the guard is
gone. Disabling the pre-write contract gate failed
`test_a_contract_that_does_not_validate_is_refused_before_the_write` and
`test_the_command_exits_four_when_the_generated_contract_is_refused`; disabling
the read-back gate failed
`test_a_contract_that_does_not_validate_on_disk_is_rolled_back`. The source was
restored and the suite re-run green before the numbers above were taken. A check
that cannot fail is a check that proves nothing, and that is worth ten minutes.

## Results

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked ruff format --check .` | `191 files already formatted` |
| `uv run --locked python -m mypy` | `Success: no issues found in 104 source files` |
| `uv run --locked python -m pytest -q` | `4248 passed, 25 skipped, 14 deselected` |
| `uv run --locked python -m pytest tests/scaffolding -q` | `369 passed` |
| `uv run --locked python -m pytest tests/contracts -q` | `191 passed, 7 skipped` |
| `uv run --locked python -m pytest -m contract -q` | `560 passed, 7 skipped, 3720 deselected` |
| `uv run --locked python -m pytest tests/testing tests/architecture tests/domain -q` | `1352 passed, 18 skipped` |
| `uv run --locked python -m pytest tests/security -q` | `605 passed` |
| `uv build` | Wheel and source distribution built. The wheel carries the `inferops` package and its metadata and nothing else — **`tools/` and `tests/` are absent**, which is the point of putting the command there |
| `git diff --check` | No output |
| Markdown trailing-whitespace and hard-tab checks | No match in any file this change touches |
| Relative-link check over every committed Markdown file | No broken link introduced by this change; the four pre-existing ones in `docs/proof/domain/v1-s1-001-pr2-validation.md` are unchanged and out of scope |

The `realruntime`, `cluster`, `failure`, and `load` markers were deselected by
the default expression, which is what the default lane is for. None was invoked.

The scaffolding suite added 82 checks to `tests/scaffolding/`, taking it from 287
to 369.

**Every count above was taken at the branch head, with this record already
committed to the tree.** An earlier draft of this table was written before that,
and five of its nine rows were one short as a result — this file is itself a
formatted file, a collected security check, and a deselected contract check. A
result table that does not reproduce from the revision it names is not a result
table, so the numbers here were re-taken rather than adjusted.

## What the added checks establish

### A generated workload validates as a file, not as a string

`V1-S1-006-PR1` established that the *rendered text* passes the published schema
and the semantic rules. That is not the same sentence as the acceptance
criterion, which is about generated output. Every "validates" in this change
reads the document back off the directory the command wrote it to.

The command itself validates twice: once against the rendered contract, before it
plans a write, and once against the file, after it wrote one. The first is why
nothing invalid reaches a disk. The second is why the success it reports is a
statement about files. Both go through `tools.contract_validation.validate` — the
same function every committed fixture goes through — and the suite adds
`inferops.domain.workload`'s own pipeline on top, with the committed
compatibility matrix handed to it.

A separate check compares every written file to the rendered text **byte for
byte**, line endings included, so "what was validated is what was written" is
checked rather than assumed.

### The generated project runs, unedited, under a real pytest

The rendering suite imports the generated skeleton and calls its functions. That
proves the module is importable. It does not prove that the command a generated
quick start prints does anything, because it is not that command.

So this suite runs `python -m pytest <workload>/tests -q` as a subprocess, from a
working directory that is not this repository, against the directory the command
created, with no file edited in between. Four cases, four subprocesses, four
green runs. `inferops` is put on the subprocess's path explicitly rather than
relied on being installed, so the check measures the generated project rather
than the host's site-packages.

### Nothing is written before a refusal

The order is refuse, render, validate, plan, write, read back. An invalid
parameter set is refused with every reason at once, and the check asserts that
the destination directory **was never created** — not that it is empty, which a
`mkdir` followed by a rollback would also satisfy.

The mock-profile rules are checked the same way: a `mock-llm` name without the
`-mock` suffix is a refusal, and there is no file on disk afterwards. A
scaffolder that quietly appended the suffix would teach nobody the rule.

### A failure leaves what it found

Two injected failures, both rolled back:

| Injected | What the check asserts |
|---|---|
| A write that fails at its second file | Everything created is removed, `unremoved` is empty, and the destination is exactly as it was found |
| A read-back that disagrees with what was written | The same, and the refusal says the output did not verify |

A third check puts a pre-existing file beside the destination and asserts it is
still there, byte-identical, after a rolled-back write. A directory that was
already there was never the command's to remove, and a rollback that used
`rmtree` on the destination would have failed this one.

### Nothing is overwritten

An occupied destination is refused, and the file already in it is byte-identical
afterwards — including when the destination directory is *empty*, because a rule
that only refuses a non-empty directory is a rule with a case in it. There is no
`--force`, and the absence is deliberate rather than unimplemented: a generated
workload is an ordinary committed directory the moment it exists.

### The command line cannot drift from the parameter set

The parser is generated from a published option table, and checks compare that
table to the template's own parameter set in both directions — which parameters
exist, which are required, and what each default is. A parameter added to the
template and not reachable from the command is a failure rather than something a
reader has to notice.

A closed vocabulary is deliberately not handed to `argparse` as `choices=`. A
check supplies four mistyped vocabulary values at once and asserts they come back
as four aggregated refusals with exit status 1, rather than as one usage error
with exit status 2.

## Evidence produced

| Artifact | Class | Kept? |
|---|---|---|
| Four generated workloads per parametrised check | `local-static` | No. Written into pytest's temporary directory and discarded with the run |
| The subprocess pytest results for the generated skeletons | `local-static` | No. Asserted in-run |
| This record | `documented-unexecuted` for its prose, `local-static` for the command results in it | Yes |

**No generated workload is committed anywhere in this repository**, and a check
in the rendering suite asserts that no `.tmpl` file appears beside the
distribution either. There is no example workload directory to go stale.

## Limitations

What this record does **not** establish:

- **That a generated workload serves anything.** Nothing here started a runtime,
  loaded a model, bound a socket, or reached a cluster. A generated workload is a
  document, a quick start, and a test.
- **That a generated workload deploys.** No controller, chart, or reconciler in
  this repository acts on a WorkloadContract. The command writes no Kubernetes
  manifest, and a check asserts the absence.
- **That a second engineer succeeded with it.** The story asks for a
  second-engineer walkthrough as evidence. That is a person doing something, and
  it has not happened. It is recorded here as not done rather than substituted
  for by a passing suite.
- **That the command behaves the same on a non-Windows host.** Every result here
  is from one Windows 11 host. The line-ending question that raises is answered
  by construction — files are written with an explicit `\n` and compared byte for
  byte — but "answered by construction" is not "executed on Linux".
- **That a rollback survives a hostile file system.** The injected failures are
  `OSError`s raised at a known point. A permission change made by another process
  mid-write, a full disk, and a network file system are untested.
- **That every destination problem is caught while planning.** Only the
  destination directory itself is type-checked before a write. An *ancestor* of
  it that is a regular file is not, and surfaces as an `OSError` during the write
  instead. The guarantee still holds — the rollback runs and the destination is
  left as it was found, which a check asserts — but the refusal arrives from the
  writer rather than from the planner, and the planning-stage refusal message
  reads as though it caught everything.
- **That `# type: ignore` is absent from this repository**, which
  [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) claims. Independent review found
  six live directives under `tests/api/` and `tests/support/`. None is in this
  change, none of this change's files carries one, and correcting the claim is
  outside this pull request's boundary — it is recorded here so the discrepancy
  is not lost.
- **Anything about the mock's fidelity.** A generated mock replays a committed
  fixture. Nothing it produces may be cited as evidence of real serving
  behaviour.

## Independent review

The change was reviewed independently before it was pushed, against the diff and
by re-executing every command in the results table. It raised one issue of
substance and three notes.

| Finding | Response |
|---|---|
| **High** — `GeneratedContractRefusedError` and exit status 4 were unreachable from any check, and they back the module's central claim that nothing invalid reaches a disk | Four checks added: the pre-write refusal, the read-back refusal and its rollback, exit status 4 through the command, and the non-directory-ancestor case below. All three guards were then mutation-tested |
| **Medium** — five rows of the results table did not reproduce from the revision they named | Correct, and the cause was this record itself: the numbers were taken before it was written, and it is a formatted file, a collected security check, and a deselected contract check. Re-taken at the branch head, with the note above |
| **Low** — only the destination directory is type-checked while planning, not its ancestors | Confirmed, checked, and recorded as a limitation rather than changed. The guarantee holds through the rollback; tightening the planner is a behaviour change this pull request has no reason to make |
| **Low** — `CONTRIBUTING.md`'s repository-wide "no `# type: ignore`" claim is false | Confirmed, six pre-existing directives, none in this change. Out of this boundary; recorded as a limitation so it is not lost |

The review found no critical issue, and confirmed the domain boundary, the
zero-runtime-dependency rule, the wheel contents, the refusal-message rule, the
mock and real distinctness, and the absence of scope creep and of path leakage.

## Authorisation

Not required. No command in this record cost money, downloaded a large artifact,
provisioned infrastructure, or touched anything outside the contributor's own
machine and this repository.

## Acceptance criteria

The parent story's criteria, and the honest status of each after this change.

| Criterion | Status | Where |
|---|---|---|
| User supplies workload name, owner, environment, model/runtime profile, resources, and attribution | **Met** | Eleven required options and six optional ones, generated from a table the suite compares to the template's parameter set in both directions |
| Generated output validates without source edits | **Met** | Validated twice — before the write and from the written file — through the validator every committed fixture uses, and again through the contract package's own pipeline |
| No stale placeholder survives | **Met** | Substitution refuses a placeholder it has no value for; the written files are then scanned, and every file is compared byte for byte to what was rendered |
| Mock and real commands are distinct | **Met** | Asserted on the written quick starts in both directions: the mock offers no real-runtime command, and the real one does |
| Invalid name/profile/resources fail before files are written or leave recoverable output | **Met**, both clauses | Nothing is created before a refusal — the destination directory is asserted uncreated — and an injected write failure and an injected read-back failure both roll back to what was found |

The story's evidence list is met in two of three parts:

| Evidence the story asks for | Status |
|---|---|
| Generated example workload | Produced by every run of the suite, into a temporary directory, and **deliberately not committed**. A committed example is a document nothing regenerates and everything drifts from |
| Generated-project test report | The suite's subprocess run of the generated skeleton, recorded above |
| Second-engineer walkthrough | **Not done.** It needs a second engineer, and this record does not claim one |
