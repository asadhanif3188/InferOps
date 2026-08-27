# V1-S0-011-PR1 change validation

Date: 2026-08-27

Classification: **local static evidence for the change itself.** Every result below
comes from running a tool over files in this repository. No cluster was created, no
model was downloaded, no runtime was started, no request was served, and **no secret
scanner, image scanner, or dependency scanner was run**. Nothing here is evidence
that InferOps does anything; it is evidence that the toolchain
[ADR 0009](../../architecture/decisions/ADR-0009-python-toolchain.md) decided was
executed rather than described.

Claim boundary: the packaging layout builds a distribution and the distribution's
contents were inspected; the project environment was created from the committed
lockfile and every check ran inside it; the linter, the formatter, and the type
checker each ran over this repository and each reports no finding; the default test
lane passes with its marker set and default marker expression unchanged; no task
runner file exists; and the published diff carries no private, generated, or
overclaimed content.

**What this record does not establish.** It does not establish that any of these
checks pass anywhere else. One Windows host ran them, by hand, once. No Linux or
macOS host has run any of them and no continuous-integration service exists to run
them, which is
[ADR 0005](../../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
D6 and is still open. It does not establish that a contributor resolves from the
committed lockfile — nothing here observes that, which is why `DR-07` stays in
[the deferred-risk register](../../security/deferred-risks.md) in narrowed form and
the control it carries stays `deferred`. And it establishes nothing at all about
dependency vulnerabilities: no scanner is configured and none was run.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| `uv` | `0.9.16 (a63e5b62e 2025-12-06)` |
| Python, provisioned by `uv` into `.venv` | `3.12.12 (main, Dec  5 2025, 21:31:16) [MSC v.1944 64 bit (AMD64)]` |
| Python, already on the host | `3.12.6` |
| `hatchling`, resolved inside the isolated build environment | `1.32.0` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1 (compiled: yes)` |
| `pytest` | `8.4.2` |
| `jsonschema` | `4.26.0` |
| `PyYAML` | `6.0.3` |
| `types-jsonschema` | `4.26.0.20260518` |
| `types-PyYAML` | `6.0.12.20260815` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |
| Branch base | `main` at `46d0390` |

Two of those versions are worth separating, because conflating them is the mistake
this table exists to prevent. The `3.12.6` on the host is **not** what the checks
ran on; `uv` provisioned its own `3.12.12` redistributable build into `.venv/` and
every command below ran against that. The host interpreter is recorded because it is
what a contributor who ignores `uv` would get.

`hatchling` is recorded from the built wheel's own `WHEEL` metadata rather than from
an installed package, because a PEP 517 build resolves its backend in an isolated
environment that no committed file pins. That is why ADR 0009 lists it as a
constraint (`hatchling>=1.27,<2`) and not as a locked version.

## Commands and results

Every command was run from the repository root. Output is reproduced as it was
printed, trimmed only where a progress line repeats.

### The environment, created from the committed lockfile

```text
$ uv lock
Using CPython 3.12.12
Resolved 22 packages in 2.57s

$ uv sync --locked
Using CPython 3.12.12
Creating virtual environment at: .venv
Resolved 22 packages in 7ms
   Building inferops @ file:///<repository root>
      Built inferops @ file:///<repository root>
Prepared 10 packages in 1m 40s
Installed 22 packages in 6.20s
 + ast-serialize==0.8.0
 + attrs==26.1.0
 + colorama==0.4.6
 + inferops==0.0.0 (from file:///<repository root>)
 + iniconfig==2.3.0
 + jsonschema==4.26.0
 + jsonschema-specifications==2025.9.1
 + librt==0.15.0
 + mypy==2.3.1
 + mypy-extensions==1.1.0
 + packaging==26.3
 + pathspec==1.1.1
 + pluggy==1.6.0
 + pygments==2.21.0
 + pytest==8.4.2
 + pyyaml==6.0.3
 + referencing==0.37.0
 + rpds-py==2026.6.3
 + ruff==0.16.4
 + types-jsonschema==4.26.0.20260518
 + types-pyyaml==6.0.12.20260815
 + typing-extensions==4.16.0
```

The absolute path `uv` printed is elided above; it is a personal filesystem path and
does not belong in a committed record.

The `inferops` line is the packaging decision executing: `uv` built and installed
this repository's own distribution as part of creating the environment, which it
could not do if the src layout, the `[project]` table, or the build backend were
wrong.

```text
$ uv sync --locked
Resolved 22 packages in 1ms
Audited 22 packages in 1ms

$ uv lock --check
Resolved 22 packages in 1ms
```

`uv lock --check` exits non-zero if the lockfile would have to change. It did not.

### The distribution, built and inspected

```text
$ uv build
Building source distribution...
Building wheel from source distribution...
Successfully built dist\inferops-0.0.0.tar.gz
Successfully built dist\inferops-0.0.0-py3-none-any.whl
```

Wheel contents, listed from the archive:

```text
inferops-0.0.0.dist-info/METADATA
inferops-0.0.0.dist-info/RECORD
inferops-0.0.0.dist-info/WHEEL
inferops-0.0.0.dist-info/licenses/LICENSE
inferops/__init__.py
```

Source distribution contents:

```text
inferops-0.0.0/.gitignore
inferops-0.0.0/CHANGELOG.md
inferops-0.0.0/LICENSE
inferops-0.0.0/PKG-INFO
inferops-0.0.0/README.md
inferops-0.0.0/pyproject.toml
inferops-0.0.0/src/inferops/__init__.py
```

The wheel carries the package and its metadata and nothing else — no `tools/`, no
`tests/`, no documentation. That is D1's claim, checked rather than asserted. The
`.gitignore` in the source distribution is added by the build backend, which
includes the version-control ignore file so that a rebuild from the source
distribution behaves the same way.

Both `dist/` and `.venv/` were removed from the working tree before the diff was
reviewed. Both are ignored by version control, and this change adds both — along
with `build/` — to the set of directories the publication-boundary check treats as
generated host state.

```text
$ uv run --locked python -c "import inferops, importlib.metadata as m; print(inferops.__name__, m.version('inferops'))"
inferops 0.0.0
```

### The linter

The first run, before anything was changed:

```text
$ uv run --locked ruff check . --output-format concise
tests\architecture\test_resource_ownership.py:201:89: E501 Line too long (89 > 88)
tests\cost\test_cost_method.py:698:9: SIM108 Use ternary operator ...
tests\security\test_security_baseline.py:389:48: RUF005 Consider `(*path, key)` instead of concatenation
tests\security\test_security_baseline.py:394:48: RUF005 Consider `(*path, str(index))` instead of concatenation
... 19 further E501 findings ...
Found 23 errors.
```

Twenty of the twenty-three were `E501` on string literals the formatter is not
allowed to split. `E501` was switched off, for the reason ADR 0009 D4 records. The
remaining three were fixed in the source. The final run:

```text
$ uv run --locked ruff check .
All checks passed!
```

### The formatter

The first run, before this change touched a Python file:

```text
$ uv run --locked ruff format --check .
80 files already formatted
```

Nothing needed reformatting. The repository was already written in this style, which
is the strongest argument for the selection and is recorded here rather than in the
decision, because it is a measurement. The final run, after this change added two
files:

```text
$ uv run --locked ruff format --check .
83 files already formatted
```

The count is larger than the number of Python files in this repository because
`ruff format` also formats fenced Python in Markdown. Fifteen of the eighty-three
are Python modules; the rest are documents — including the three this change adds —
and all of them were already formatted too.

### The type checker

The first run, under `strict` with no per-module relaxation:

```text
$ uv run --locked python -m mypy
... 243 findings ...
Found 243 errors in 8 files (checked 14 source files)
```

Most were `no-untyped-def` and `type-arg` findings in the test suites, which read
committed JSON documents into bare `dict`s. Five strict-only rules were relaxed for
`tests.*`, for the reason ADR 0009 D6 records. That left eleven, all of which were
fixed rather than suppressed:

| File | Finding | Fix |
|---|---|---|
| `tools/contract_validation/workload.py` | Four `no-any-return` from `json.loads` and from indexing a `dict[str, Any]` | Annotated the local the value is read into |
| `tools/contract_validation/workload.py` | `arg-type`: the validator library types `ValidationError.validator` as possibly unset, and it was used as a dictionary key | An explicit branch. Both paths reach the same rule, so behaviour is unchanged and the reasoning is now stated |
| `tests/cost/test_cost_method.py` | A generator function annotated as returning `object`, producing four downstream findings | Annotated as `Iterator[tuple[str \| None, object]]`, which is what it always yielded |
| `tests/cost/test_cost_method.py` | Two `arg-type` from `sum()` over a `Decimal` generator, whose empty result is `int` | A `Decimal(0)` start value |

The final run:

```text
$ uv run --locked python -m mypy
Success: no issues found in 15 source files
```

One diagnostic worth recording because it cost time: `uv run --locked mypy` fails on
this host with `Failed to spawn: mypy / Access is denied. (os error 5)`, while
`uv run --locked python -m mypy` works. The console entry point is what fails, not
the type checker, so the module form is the one the contribution guide records.

### The test suites

The default lane, which is what a change is checked against:

```text
$ uv run --locked python -m pytest -q
2326 passed, 7 skipped in 3.27s
```

The seven skips are the contract suite's pre-existing conditional skips. Each suite
individually:

```text
$ uv run --locked python -m pytest tests/contracts -q
191 passed, 7 skipped in 0.85s

$ uv run --locked python -m pytest tests/architecture -q
357 passed in 0.21s

$ uv run --locked python -m pytest tests/testing -q
496 passed in 0.32s

$ uv run --locked python -m pytest tests/telemetry -q
408 passed in 0.33s

$ uv run --locked python -m pytest tests/cost -q
288 passed in 0.25s

$ uv run --locked python -m pytest tests/security -q
586 passed in 1.32s
```

Before this change the default lane reported `2281 passed, 7 skipped`. The 45
additional tests are the 43 in `tests/testing/test_toolchain.py`, plus two in the
security suite: its reserved-vocabulary check is parametrised over every Markdown
document committed here, and this change adds two of those. No existing test changed
its result, and no test was removed or renamed.

### The contract validator, run the recorded way

```text
$ uv run --locked python -m tools.contract_validation contracts/workload/examples/valid/synchronous-llm-local.yaml
ok      contracts/workload/examples/valid/synchronous-llm-local.yaml
```

`tools.contract_validation` still resolves from the repository root through the root
`conftest.py`, which is what D1 promised when it left `tools/` outside the
distribution.

### Whitespace, links, and shape

```text
$ git diff --check main...HEAD
(no output)

$ git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
(no matches)

$ git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
(no matches)
```

Every relative Markdown link, checked with the POSIX variant of the loop in the
contribution guide:

```text
$ git ls-files -z '*.md' | while IFS= read -r -d '' f; do ... done
(no BROKEN lines)
```

The TOML and JSON files this change adds or edits parse:

```text
$ uv run --locked python -c "import tomllib; [tomllib.load(open(p,'rb')) for p in ('pyproject.toml','uv.lock')]"
(no output, exit 0)

$ uv run --locked python -c "import json; json.load(open('docs/security/security-baseline.v1alpha1.json'))"
(no output, exit 0)
```

### Checks that were not run, and why

| Check | Why not |
|---|---|
| `shellcheck -x -S style scripts/environment/*.sh` | Not installed on this host, and no shell script is changed by this PR |
| `kubeconform -strict ... deploy/smoke/*.yaml` | No manifest is changed by this PR. The security suite still parses every YAML document under `deploy/` and passed |
| A secret scanner | `gitleaks` is not installed on this host. `DR-11` records that no scanner run exists, and this change does not alter that |
| A dependency vulnerability scanner | None is configured. `DR-07` and `DR-08` both record the gap, and adopting a lockfile did not close it |
| Any capable-host lane | `cluster`, `realruntime`, `failure`, and `load` are deselected by the default marker expression and nothing in this PR needs them |

## What the machine check establishes

`tests/testing/test_toolchain.py` reads the two tables ADR 0009 publishes and
compares them against the files they describe. Twenty-one of its assertions are
parametrised over those tables, which is why the suite grew by 43 tests. What it
refuses:

- a package declared in a dependency group that the record does not publish, and a
  constraint the record publishes that no group declares;
- a version typed into the record that `uv.lock` does not pin, in either direction;
- an interpreter series that disagrees between `pyproject.toml`, `uv.lock`, and
  `.python-version`;
- a `[tool.pytest.ini_options]` table in `pyproject.toml`, or a default marker
  expression that stops deselecting a capable-host lane;
- a wheel or source-distribution target that would ship `tools/` or `tests/`, and an
  unanchored source-distribution include pattern;
- a `__version__` in `src/inferops/__init__.py`, which would be a second place to
  change a version;
- a `Taskfile`, `Taskfile.yml`, `Taskfile.yaml`, `Taskfile.dist.yml`, `justfile`,
  `Justfile`, `.justfile`, `Makefile`, `makefile`, `GNUmakefile`, `noxfile.py`, or
  `tasks.py`;
- an ADR 0001 whose D3 and D4 rows do not say they are superseded, which is what
  stops two accepted records disagreeing after this change.

Seven deliberate corruptions were applied, run, and reverted. Each one is a mistake
somebody would plausibly make, and each was confirmed to fail before the file was
restored:

| Corruption | Result |
|---|---|
| Published a `ruff` version in the record that `uv.lock` does not pin | Refused. `test_every_version_the_record_publishes_is_the_version_the_lock_pins[ruff]` fails and names both sides |
| Published a `mypy` constraint in the record that no dependency group declares | Refused twice, once from each direction: the constraint has no group, and the group's constraint is not published |
| Added `[tool.pytest.ini_options]` to `pyproject.toml` | Refused, with the message naming ADR 0005 and ADR 0009 D8 |
| Created an empty `Taskfile.yml` | Refused by `test_no_task_runner_file_is_committed[Taskfile.yml]` |
| Removed `not realruntime` from the default marker expression | Refused by this suite, and by the pre-existing strategy suite beside it |
| Added a `__version__` to `src/inferops/__init__.py` | Refused |
| Changed the ADR 0001 D3 row back to `**Proposed**` | Refused |

An eighth was attempted and did not reach the suite, which is worth recording
because it changes what the suite can be said to defend. Editing the `ruff` version
inside `uv.lock` directly is rejected by `uv` before any test runs — it notices that
the pinned version disagrees with the wheel filenames beside it and refuses to parse
the file at all. So the lockfile is defended against a hand edit by `uv`, and the
record is defended against drifting from the lockfile by this suite. Neither
defends the other's job.

## What the diff was reviewed for

| Checked for | Result |
|---|---|
| Credentials, tokens, keys | None. `uv.lock` carries 136 SHA-256 artifact digests and no credential; the index it names is the public one |
| Private planning content, prompts, or unpublished strategy | None. No planning document is quoted, summarised, or referenced, and no sprint, backlog, or roadmap vocabulary appears |
| Personal filesystem paths, hostnames, usernames | None. The one place a build printed an absolute path, this record elides it, and the pre-existing test that scans every file in the working tree for a personal path passes |
| Generated files or host state | None committed. `.venv/`, `build/`, and `dist/` are ignored and are now named in the publication-boundary check |
| Model artifacts | None |
| A capability claim not supported by evidence | None found. Every tool named was run and its output is above; the task runner is recorded as rejected rather than as pending; and the continuous-integration gap is stated in the decision, the contribution guide, and the prerequisites |
| Scope beyond this pull request | None. No Sprint 1 capability, no component, no workflow file, no scanner configuration, and no schema change |

Eight changes touch files this PR does not own, and each is named here because a
reviewer should see them deliberately rather than find them:

- **`docs/architecture/decisions/ADR-0001-local-development-environment.md`** — D3
  and D4 are marked superseded, in the header, the callout, the status table, their
  own sections, the consequence that counted them, and the validation section that
  explained why they were left open. No accepted decision in that record changes.
- **`docs/architecture/decisions/ADR-0003-workload-contract-schema-tooling.md`** —
  D6 gains an amendment note. The boundary it draws is unchanged; what changed is
  that the toolchain on the other side of it is now decided.
- **`docs/architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md`** —
  one consequence bullet gains the note that its condition was met and that the
  permission it guarded was not taken. D6 is untouched and still undecided.
- **`docs/architecture/decisions/ADR-0008-v1-security-baseline.md`,
  `docs/security/security-baseline.v1alpha1.json`, and
  `docs/security/deferred-risks.md`** — `DR-07` is narrowed rather than retired, and
  `pin-every-dependency-with-a-committed-lockfile` keeps its `deferred` status. No
  count changes: twelve risks, ten of them blocking production use, thirty-two
  controls, twenty-two enforced by something. The control
  `ignore-and-refuse-generated-host-state` gains three directories in its statement.
- **`tests/security/test_security_baseline.py`** — three entries added to the list
  of generated-state prefixes. The suite's 586 tests all pass, and the change
  narrows what the walk reads to files this project could actually publish.
- **`tests/cost/test_cost_method.py`** and **`tools/contract_validation/workload.py`**
  — the linter and type-checker fixes tabulated above. Each is behaviour-preserving
  and both suites pass with unchanged counts.
- **`docs/governance/repository.md`** replaces one row. It listed the task runner and
  the dependency installation together as "Not selected", citing ADR 0001 D3 and D4 as
  still proposed. Both halves are now decided and they are decided in opposite
  directions, so one row cannot carry them: the task runner is rejected and the
  toolchain is accepted and executed.
- **`.gitattributes`** gains one rule, for the same reason the existing `*.sh` rule
  is there. `uv` writes the lockfile with LF on every platform; under `text=auto` a
  Windows checkout would receive CRLF and the next `uv lock` would rewrite the whole
  file, turning a no-op into a diff. `.gitignore` gains a trailing slash on `.venv`
  so that the publication-boundary check can name the directory exactly.

## What a second review found

An independent review of the first commit re-ran every command in this record,
measured the pre-change baseline in a disposable worktree at `main`, and tested the
`tests.*` type-check relaxation by experiment rather than by reading it. It confirmed
every number above except one, and found four defects. All four are fixed in the
second commit on this branch.

| Defect | What was wrong | Fix |
|---|---|---|
| The security baseline disagreed with itself | `DR-07` was narrowed and the threat that references it, `T-19`, was not. Its `abuseCase` still said "There is no lockfile and no packaging manifest" and its `residualRisk` still said "the dependency-installation decision is proposed and not accepted", both false as of this change. No test cross-checks a threat's prose against the risk it links to, so nothing caught it | Both fields rewritten to the narrowed risk: the input exists, the resolution is unobserved, and the non-Python tools are outside the lockfile |
| This record disagreed with its own transcript | The command output above reports the security suite at 586 tests; a paragraph 140 lines later said 585 | Corrected to 586, which is also what `584 + 2` gives |
| The architecture index disagreed with its own table | Its status line said "one accepted" while the table it introduces now lists two fully accepted records | Corrected to "two accepted" |
| The governance index reported a superseded fact as current | One row said ADR 0001 D3 and D4 "remain proposed; neither has been run" | Replaced with two rows, because the two halves are now decided in opposite directions |

A fifth item was raised at low confidence and is worth recording because the
resolution went the other way. ADR 0009's status is `Accepted` while its D9 was
labelled "**Not decided**", which looks like the condition under which
[the architecture index](../../architecture/README.md) requires `Accepted in part`.
It is not: that status is defined for a record with a decision that **remains
proposed**, and ADR 0009 has none — seven decisions are accepted and executed, one is
a rejection, and D9 is a scope boundary of the kind ADR 0003 D6 already established
and was itself labelled `Accepted as a boundary` for. D9 is relabelled to match that
precedent and says why in its own section; the status stays `Accepted`, and the
service behind D9 stays undecided. A corruption confirms the test still refuses a D9
row that stops saying so.

One further inconsistency was found in `docs/governance/repository.md` and is
**deliberately not fixed here**: its "Runtime host for serving" row still says no
model runtime is selected, which ADR 0002 made false before this story existed. It
predates this change, it belongs to the serving decision rather than the toolchain
one, and fixing it inside this PR would widen a diff that already reaches further
than a reader expects. It is recorded here so that it is not mistaken for something
this change introduced.

What the review verified independently and found correct: every command result above,
every per-suite count, the 136 lockfile hashes, the 43 tests in the new module, the
2281 pre-change baseline measured in a worktree at `main` rather than inferred, the
agreement of `requires-python`, `uv.lock`, and `.python-version`, the absence of any
`# type: ignore`, the absence of any task-runner file, the unchanged security counts,
the reserved-vocabulary scan over both new documents, the leakage grep over the whole
diff, and that the four behaviour-preserving source edits change no behaviour. It
also proved by experiment that the `tests.*` mypy override is a real relaxation
rather than a pattern that silently matches nothing: an untyped function added under
`tests/` produced no finding, and the same function added under `tools/` produced
`no-untyped-def`.

## Limitations

- **One host, one run, by hand.** Windows 11, one interpreter, one afternoon. No
  Linux or macOS host has run any of this, and the cross-platform claim in ADR 0009
  D3 rests on `uv`'s universal resolution rather than on a second machine.
- **No automated lane.** Nothing runs on a push, and every result here has to be
  reproduced by hand by the next contributor. ADR 0005 D6 stays open.
- **A lockfile is an input, not an observation.** Nothing in this repository records
  which inputs a given check actually resolved. `uv run --locked` refuses a run that
  would change the lock, and that refusal happens on a contributor's machine where
  nothing here can see it.
- **The lockfile covers Python distributions only.** `shellcheck`, `kubeconform`,
  `kind`, `kubectl`, and the container engine are pinned by prose in the
  prerequisites document, and `uv` itself is pinned by nothing.
- **No dependency was scanned.** Twenty-two packages are now pinned in public
  history and nothing has looked at any of them for a vulnerability. No count,
  severity, or scan result is published here, and none may be.
- **The machine check compares a record to a configuration, not to reality.** It can
  tell that ADR 0009 and `uv.lock` agree about a version. It cannot tell that the
  version was ever installed, and it would pass unchanged on a machine where no tool
  is present.
- **The type checker is not uniformly strict.** Five strict-only rules are relaxed
  for `tests.*`. A test that would have needed an annotation does not need one, and
  the findings those rules would have produced are not produced.
- **`E501` is off.** A long line the formatter cannot break is reported by nothing.
- **The empty package proves the layout, not the code.** `src/inferops/__init__.py`
  contains a docstring. The build, the wheel contents, and the install are real; what
  they carry is not.
- **The corruption set is not exhaustive.** Each corruption represents a mistake
  somebody would plausibly make. A corruption nobody thought of is one that was not
  tested.
- **Prose in the security baseline is not cross-checked against the prose it
  references.** A threat and the deferred risk it links to can disagree, and the
  suite will pass. That is how `T-19` survived the first commit saying the opposite
  of the `DR-07` beside it, and the fix here corrects the text without adding the
  check that would have caught it.

## Authorisation

Not required. No infrastructure was provisioned, no cluster was created, no model
was downloaded, no paid resource was consumed, and nothing outside this repository
and the local machine was modified. Network access was used to resolve and download
22 Python distributions and one redistributable interpreter build from public
indexes, which is the same class of access the contribution guide already assumes
for cloning this repository.
