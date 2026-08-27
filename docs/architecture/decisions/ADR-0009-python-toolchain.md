# ADR 0009: InferOps Python toolchain

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date proposed | 2026-08-27 |
| Date accepted | 2026-08-27 |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | ADR 0001 D3 and ADR 0001 D4 |
| Superseded by | None |

> [!IMPORTANT]
> Every tool this record names was **run on this repository** before the record
> was written, and the exact command and result of each run are in
> [the validation record](../../proof/toolchain/v1-s0-011-pr1-validation.md).
> That is the point of it: ADR 0001 named two of these tools and neither was ever
> installed, which is why both of its decisions sat at *proposed* while
> `pytest.ini` carried a comment warning that a `pyproject.toml` would settle
> them by accident.
>
> One decision here is a **rejection**. No task runner is adopted, and that is
> recorded as a decision with an argument rather than left as an empty field.
>
> This record does **not** select a continuous-integration service. ADR 0005 D6
> stays open, no workflow file exists, no runner is labelled capable, and every
> command below is one a contributor runs by hand.

## Decision status

| ID | Decision | Status | Evidence |
|---|---|---|---|
| D1 | Packaging: `pyproject.toml`, src layout, one distribution named `inferops`, built by `hatchling` | **Accepted**, and executed | A wheel and a source distribution were built and the wheel's contents inspected |
| D2 | Dependency manager: `uv` | **Accepted**, and executed | The environment was created from the lockfile and every check below ran inside it |
| D3 | Lockfile policy: `uv.lock` committed, universal, hash-bearing; the interpreter series pinned | **Accepted**, and executed | 136 artifact hashes committed; `uv lock --check` reports the lock in sync |
| D4 | Linter: `ruff check` | **Accepted**, and executed | Run over the repository; 23 findings, all resolved, final run clean |
| D5 | Formatter: `ruff format` | **Accepted**, and executed | Run over the repository; 80 files reported already formatted and none to reformat |
| D6 | Type checker: `mypy`, strict over InferOps-owned source | **Accepted**, and executed | Run over 15 source files; 243 findings under the first configuration, 11 under the accepted one, all resolved |
| D7 | Task runner: none adopted | **Rejected**, as a decision | Nothing to execute. The argument is below, and a test refuses a task-runner file appearing without this record changing |
| D8 | The pytest configuration stays in `pytest.ini` | **Accepted**, and executed | The marker set and the default marker expression are unchanged, and the suite runs under them |
| D9 | Continuous integration is not selected here | **Accepted as a boundary.** The service itself stays **not decided** | Nothing, and nothing is claimed. ADR 0005 D6 remains open and this record does not narrow it |

## Context

Sprint 1 writes the first InferOps-owned Python package. Whoever writes it has to
create a package directory, declare a dependency, and choose where the
configuration for both lives — and unless this record exists first, those three
acts settle the packaging tool, the dependency manager, the lint rules, and the
type checker in passing, in a change whose stated subject is a domain object.

That is not hypothetical. The repository already carries three separate notes
saying so, written at three different times:

- [ADR 0001](ADR-0001-local-development-environment.md) proposed a task runner
  (D3) and a dependency-installation approach (D4) and accepted neither, because
  neither was installed and neither was run.
- [ADR 0003](ADR-0003-workload-contract-schema-tooling.md) D6 states explicitly
  that choosing `pytest` to drive contract validation did **not** select the
  repository's packaging, linting, typing, or test toolchain.
- [`pytest.ini`](../../../pytest.ini) carries a comment warning that a
  `pyproject.toml` placed beside it would quietly settle all of the above.

Two constraints come from outside this record.
[ADR 0005](ADR-0005-test-ci-and-certification-strategy.md) made the committed
marker set and the default marker expression load-bearing — they are what makes
"the default lane cannot execute a real model" a property rather than a promise —
and its consequences record that moving that configuration into a
`pyproject.toml` would reopen ADR 0001 D3 and D4. Those two are reopened here on
purpose, and the configuration still does not move. And there is no
continuous-integration lane to run anything in, so a choice that is only
reproducible inside a hosted runner is a choice this project cannot execute
today.

## Decision criteria

In order, because they conflicted and the order is what resolved them:

1. **Executable now, by hand, on the one host this project has measured.** A tool
   that needs a runner this project has not selected cannot be accepted here; it
   can only be proposed, and this repository already has enough proposals.
2. **One tool per role, and as few roles as possible.** Every additional binary
   is another version to pin, another install to document, and another thing a
   contributor can be missing.
3. **Cross-platform without a shell contract.** The measured host is Windows; the
   intended hosts include Linux and macOS; none of the three has been used to run
   the other's checks.
4. **Reproducible inputs.** A check whose dependency set is resolved fresh on
   every run measures the index as much as it measures the repository.
5. **Adoption cost paid in this change, not deferred.** A rule set that leaves
   findings behind is a rule set that gets suppressed rather than obeyed.

## Decision

### D1 — Packaging: `pyproject.toml`, src layout, one distribution, hatchling

**Accepted, and executed.** InferOps-owned importable code lives under `src/`, in
a single distribution named `inferops`, described by a PEP 621 `[project]` table
in [`pyproject.toml`](../../../pyproject.toml) and built by `hatchling`.

`src/inferops/__init__.py` exists and is deliberately empty. It is there so that
this decision is a built artifact rather than a described intention: the layout,
the backend, and the wheel were all exercised before the record was written. The
first InferOps-owned module belongs there, and Sprint 1 adds it rather than
deciding where it goes.

Two directories stay **outside** the distribution, and that is a decision rather
than an oversight:

- `tools/` is repository tooling. The contract validator is run against files in
  this repository by a contributor or by a test; nothing that installs `inferops`
  should acquire it.
- `tests/` is not packaged, and the root [`conftest.py`](../../../conftest.py)
  continues to put the repository root on `sys.path` so that `tools.*` resolves
  when the suite runs from the repository root.

The distribution is built locally and is **not** published to any package index
in V1. The `Private :: Do Not Upload` classifier is what refuses an upload that
tried, and it is a guard rather than a policy statement.

The version is `0.0.0` and is declared once, in `pyproject.toml`. It is not
repeated in `__init__.py`, because two places to change a version is one place to
forget. No release has been made and [the release process](../../releases.md) is
unchanged by this record.

### D2 — Dependency manager: `uv`

**Accepted, and executed.** `uv` creates the project environment, resolves the
dependency groups, and runs every check. This is ADR 0001 D4's proposal executed
rather than restated: the environment was created, the tools were installed into
it, and the checks in this record ran inside it.

Development inputs are PEP 735 dependency groups — `test`, `checks`, and a `dev`
group that includes both — rather than optional-dependency extras. The difference
matters in one direction: a group is not part of the distribution's published
metadata, so nothing that depends on `inferops` inherits a linter.

`uv` itself is **not** pinned by anything in this repository. It is a single
binary a contributor installs, as `kubectl`, `shellcheck`, and `kubeconform`
already are, and like those it is recorded with the version that was used rather
than vendored.

### D3 — Lockfile policy

**Accepted, and executed.** [`uv.lock`](../../../uv.lock) is committed. Four
rules travel with it:

1. **The lock is universal.** It is resolved across environment markers rather
   than for whichever platform happened to run the resolver, so the same file
   describes the Windows host this was executed on and the Linux and macOS hosts
   that have never run it.
2. **Every distribution in it carries a hash.** 136 of them are committed.
3. **The interpreter series is pinned and the patch release is not.**
   `requires-python = ">=3.12,<3.13"` in `pyproject.toml`, and `3.12` in
   [`.python-version`](../../../.python-version). `uv` provisions its own
   redistributable interpreter build; it does not adopt whichever interpreter is
   already on the host, and the build it provisions is not byte-identical to a
   system one.
4. **A check runs with `--locked`.** `uv run --locked` and `uv sync --locked`
   fail if the lockfile would have to change, so a run that would silently
   re-resolve stops instead. Changing a dependency is `uv lock`, deliberately, in
   its own diff.

What this does **not** establish: nothing here verifies that a given contributor
resolved from the lock rather than from an index, because there is no lane to
verify it in. The committed lockfile is a reproducible input that is available,
not an enforced one, and
[the deferred-risk register](../../security/deferred-risks.md) carries that gap
as `DR-07` rather than treating a committed file as a result.

### D4 — Linter: `ruff check`

**Accepted, and executed.** The selected rule sets are `E` and `W` (pycodestyle),
`F` (pyflakes), `I` (import sorting), `UP` (pyupgrade), `B` (bugbear), `SIM`
(simplify), and `RUF`. `E501` is switched off: the formatter owns line length,
and the only lines `E501` can still reach after `ruff format` has run are string
literals the formatter is not allowed to split, where the usual response is a
suppression comment that buys nothing.

The first run over this repository produced 23 findings. All 23 are resolved in
the change that adopts the linter — three by editing accepted code, twenty by
switching `E501` off — and the final run is clean. That is criterion 5 being paid
rather than deferred.

### D5 — Formatter: `ruff format`

**Accepted, and executed.** The same binary, in its formatter role, at
`line-length = 88`. One tool covering two roles rather than two tools, which is
criterion 2.

The first `ruff format --check` over this repository reported **80 files already
formatted and none to reformat**. The repository was already being written in
this style; this record turns a habit into a check.

That count is larger than the number of Python modules here because `ruff format`
also formats fenced Python inside Markdown. Fifteen of them are modules and the rest
are documents, and once this change adds three files the count is 83.

### D6 — Type checker: `mypy`

**Accepted, and executed.** `mypy` runs over `src/`, `tools/`, `tests/`, and
`conftest.py` — 15 source files — in `strict` mode, with `warn_unreachable` on
and `ignore_missing_imports` off, so a missing stub is a finding rather than a
silence.

The test suites are checked and are **not** held to `strict`. Strict mode's
demands there — a type argument on every `dict` read out of a JSON document, an
annotation on every parameter — buy little in suites whose subject is committed
data, and the price is annotating several hundred lines of accepted code inside
the change that adopts the checker. Five strict-only rules are relaxed for
`tests.*`; everything that finds a real defect stays on. The measured difference
was 243 findings under the first configuration and 11 under the accepted one, and
the 11 were fixed rather than suppressed. Two of them were worth having: a
generator annotated as returning `object`, and a keyword that the validator
library types as possibly unset being used as a dictionary key.

No `# type: ignore` appears anywhere in this repository, and no rule is
suppressed at a call site. When the first one is needed it should carry a reason.

### D7 — Task runner: none

**Rejected.** This supersedes ADR 0001 D3, which proposed `Task` (go-task) and
never installed it. No task runner is adopted in V1, and no `Taskfile`,
`justfile`, `Makefile`, `noxfile.py`, or `tasks.py` is committed.

The argument, which is not "it was inconvenient":

- **ADR 0001 D3 argued itself out of its own conclusion.** It recorded that
  `just` reaches a comparable result and that "the margin between them is a
  preference for one fewer implicit dependency, not a capability gap". A choice
  whose own record says the margin is preference is a choice with nothing behind
  it.
- **D2 already supplies the command prefix a task runner would have wrapped.**
  `uv run --locked <tool>` is reproducible, cross-platform, and pinned by a file
  in this repository. A task runner on top of that adds a second indirection
  whose only content is the first.
- **A task runner does not ship the utilities its recipes call.** ADR 0001 D3
  said this itself. A recipe that calls `rm`, `sed`, or `mkdir -p` still depends
  on per-platform binaries, several of which are absent on a bare Windows host —
  which is the host this project has actually measured.
- **The check set is small and is documented where a contributor reads it.**
  [The contribution guide](../../../CONTRIBUTING.md) lists each command against
  the paths that require it. Those commands do not need a runner; they need a
  list.
- **There is nothing to bootstrap.** A task runner earns its place when it
  sequences a build, a generation step, and a deployment. None of those exists
  here.

What would reopen this: a check set that grows past what a contributor can be
expected to run by hand, a build or generation step with real ordering between
its stages, or a selected continuous-integration service whose configuration
would otherwise duplicate the command list. The first two are Sprint 1 and later
questions; the third is ADR 0005 D6, which stays open.

### D8 — The pytest configuration stays in `pytest.ini`

**Accepted, and executed.** [`pytest.ini`](../../../pytest.ini) remains the
pytest configuration. `pyproject.toml` declares no `[tool.pytest.ini_options]`
table, and a test refuses one.

ADR 0005's consequences named this exact risk: a `pyproject.toml` arriving later
and absorbing the marker configuration, which is the mechanism behind "the
default lane cannot execute a real model". Reopening ADR 0001 D3 and D4 is the
condition that record set for adding a `pyproject.toml`, and it is met here. The
permission it did **not** grant — that the marker set may move — is not taken.

The eleven registered markers, `--strict-markers`, `--strict-config`, and the
default marker expression that deselects `cluster`, `realruntime`, `failure`, and
`load` are unchanged by this record.
`tests/testing/test_test_strategy.py` compares that file against the committed
strategy in both directions and would fail if any of it moved.

### D9 — Continuous integration is not selected here

**Accepted as a boundary**, in the sense ADR 0003 D6 uses: what this record accepts
is that it does not decide the question, and the question itself stays **not
decided**. No continuous-integration service is selected, no workflow file exists,
and no runner is labelled capable.

This is why the record's status is `Accepted` rather than `Accepted in part`. That
status is reserved for a record with a decision that **remains proposed**, and there
is none here: seven decisions are accepted and executed, one is a rejection, and this
one is a scope boundary.
[ADR 0005](ADR-0005-test-ci-and-certification-strategy.md) D6 remains open, and
every command in this record and in the contribution guide is one a contributor
runs by hand and records the result of.

This is stated rather than left implicit because a record that adopts a linter, a
formatter, a type checker, and a lockfile is exactly the record a reader will
assume also turned on a pipeline. Nothing here runs on a push.

## What is pinned, and where

Every constraint below is committed in `pyproject.toml`.
[`tests/testing/test_toolchain.py`](../../../tests/testing/test_toolchain.py)
compares this table against that file and fails if they disagree.

| Role | Package | Constraint in `pyproject.toml` |
|---|---|---|
| Build backend | `hatchling` | `hatchling>=1.27,<2` |
| Linter and formatter | `ruff` | `ruff>=0.16.1,<0.17` |
| Type checker | `mypy` | `mypy>=2.3,<3` |
| Test framework | `pytest` | `pytest>=8.3.4,<9` |
| Schema validator | `jsonschema` | `jsonschema>=4.23,<5` |
| YAML reader | `PyYAML` | `PyYAML>=6.0.2,<7` |
| YAML stubs | `types-PyYAML` | `types-PyYAML>=6.0.12,<7` |
| Schema-validator stubs | `types-jsonschema` | `types-jsonschema>=4.23,<5` |

## What the committed lockfile resolved

These are the versions `uv.lock` pins today, and the versions every result in
this record was produced by. The same test compares this table against the
lockfile, so a re-resolution that moves a version fails until this record is
updated with it.

| Package | Version in `uv.lock` |
|---|---|
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |
| `pytest` | `8.4.2` |
| `jsonschema` | `4.26.0` |
| `pyyaml` | `6.0.3` |
| `types-jsonschema` | `4.26.0.20260518` |
| `types-pyyaml` | `6.0.12.20260815` |

Three versions are **not** pinned by anything committed here, because they are
properties of the host rather than of the repository. They are recorded in
[the validation record](../../proof/toolchain/v1-s0-011-pr1-validation.md)
beside the run that used them: `uv` `0.9.16`, the `hatchling` `1.32.0` that the
build resolved inside its isolated build environment, and the CPython `3.12.12`
that `uv` provisioned.

## Alternatives considered

### Dependency manager

| Alternative | Assessment |
|---|---|
| `uv` | Selected. Present on the measured host, a single binary, a universal hash-bearing lock, and it provisions its own interpreter. Younger than the alternatives, which is the cost. |
| `pip` with `venv` and a requirements file | Universally available, produces no hash-pinned universal lock by default, and manages no interpreter. It is the escape hatch rather than the mechanism: `uv export` produces a `pip`-consumable file, resolved for a target platform, so the hatch may need one file per platform. |
| Poetry | Mature, and its lock is likewise universal and hash-bearing. An extra install where `uv` is already present, with no advantage that outweighs that here. |
| PDM | Credible; no decisive advantage over `uv` at this scope. |
| pixi | The strongest alternative if InferOps later needs conda-forge-resolved accelerator runtimes in a contributor's own environment. Deferred rather than rejected, on the reasoning that accelerator toolchains are pinned inside container images here. |
| conda | Valuable when native toolchains must be resolved as dependencies. Its default channels carry organisation-size licensing terms that would need review before it could be made mandatory. |

### Build backend

| Alternative | Assessment |
|---|---|
| `hatchling` | Selected. A PEP 517 backend that needs no plugin for a src layout, with explicit control over what enters the wheel and the source distribution. |
| `setuptools` | The most widely understood, and the one whose default file discovery most often puts something unexpected into a distribution. Rejected on that, not on maturity. |
| `flit-core` | Smaller and adequate here, with less control over distribution contents once a repository has directories that must stay out of the wheel — which this one already does. |
| `poetry-core` | Would pull the Poetry model in beside `uv` for no gain. |
| `maturin` | For distributions with a compiled Rust component. There is none. |

### Linter and formatter

| Alternative | Assessment |
|---|---|
| `ruff` for both | Selected. One binary, two roles, and the repository was already written in its formatter's style — 80 files, none to reformat. |
| `flake8` plus `black` plus `isort` | Three installs, three configurations, and two of the three are subsumed by the selection. |
| `black` for formatting, `ruff` for lint | A defensible split, and one more pinned binary for an output difference this repository has not encountered. |
| `pylint` | Finds more, argues more, and needs per-project suppression to be usable. Rejected against criterion 5. |

### Type checker

| Alternative | Assessment |
|---|---|
| `mypy` | Selected. The reference implementation of the typing specification, with per-module strictness — which is exactly the control needed to check tests and source at different levels. |
| `pyright` | Fast and strict, and it brings a Node.js runtime into a Python project's required tooling. Rejected against criterion 2. |
| `ty` | From the authors of `ruff`, and it would collapse the type checker into the same binary as D4 and D5. Too young to be the only type check over a contract validator today, and the most likely reason to revisit this record. |
| No type checker | The status quo. `tools/contract_validation` is annotated throughout already, so this would discard work the repository had already done. |

### Task runner

Covered in D7. `Task`, `just`, GNU Make, `mise`, and Python `invoke` or `nox`
were each assessed in ADR 0001 D3, and that assessment is not repeated here. What
changed is the conclusion, and what changed it is that D2 supplies the
reproducible command prefix the runner was wanted for.

## Consequences

- Sprint 1 adds a module under `src/inferops/` and a dependency to a group in
  `pyproject.toml`. It decides neither where the package goes nor how the
  dependency is pinned, which is what this record exists to prevent.
- Running the checks the recorded way now needs `uv`. A contributor who has only
  Python and `pip` can still run `python -m pytest` and will get whatever
  versions are on their machine, which is why a recorded result always names the
  command that produced it.
- `uv.lock` will appear in diffs. A lockfile change is reviewable and should be
  reviewed: it is the file that decides what every check actually ran against.
- Adding a dependency is two steps — edit `pyproject.toml`, run `uv lock` — and
  the second cannot be skipped, because `--locked` fails instead of re-resolving.
- Three files in accepted test suites and one under `tools/` were edited to
  satisfy the linter and the type checker. Every change is behaviour-preserving,
  and the suite passes with the same test count.
- `.venv/`, `build/`, and `dist/` are now generated host state that the
  publication boundary knows about. Before this record the security suite walked
  them as candidates for publication, and a project virtual environment would
  have failed two of its checks on files belonging to third-party packages.
- There is still no automated lane. Every result in this record is a command a
  human ran and recorded, and the next contributor has to run them again.

## Compatibility impact

**No published contract, schema, error code, or identifier changes.** This record
adds build and check configuration and edits four Python files without altering
what any of them does. The WorkloadContract schema, its canonical rejection
matrix, the telemetry catalog, the cost method, and the security baseline's
controls and threats are untouched by it.

One compatibility statement is worth making precisely, because the obvious
reading of it is wrong: `requires-python = ">=3.12,<3.13"` is a constraint on the
distribution, not a claim that InferOps has been run on 3.12 across platforms. It
has been run on one Windows host, on the interpreter `uv` provisioned there.

## Security considerations

- **A committed lockfile is an input, not a result.** It pins what a check
  resolves; it does not establish that any contributor resolved from it, and it
  scans nothing. `DR-07` in
  [the deferred-risk register](../../security/deferred-risks.md) is narrowed by
  this record rather than retired, and the control
  `pin-every-dependency-with-a-committed-lockfile` stays `deferred`, because
  nothing here verifies that the resolution actually happened that way.
- **No dependency vulnerability scanner has been run**, and none is configured.
  No vulnerability count, severity distribution, or scan result is published
  here, and none may be.
- **Nothing in this record defends a running system.** It configures checks over
  files in a repository. No control in the security baseline moves from
  unenforced to enforced because of it.
- **The publication boundary gained three ignored directories** — `.venv/`,
  `build/`, and `dist/`. That is not a widening of what may be published: all
  three are ignored by version control, no file under any of them may be
  committed, and the test that says so now covers them.
- **`uv` and the interpreter it provisions are fetched over the network**, from
  the index and from `uv`'s own distribution channel. Nothing in this repository
  verifies that transport, and the artifact hashes in the lock are what the
  integrity argument rests on.

## Evidence

| Claim | Evidence | Class |
|---|---|---|
| The packaging layout builds | A wheel and a source distribution were built; the wheel contains `inferops/__init__.py` and metadata and nothing else | `local-static` |
| The environment is created from the lock | `uv sync --locked` installed 22 packages; `uv lock --check` reports the lock in sync | `local-static` |
| The linter runs clean | `uv run --locked ruff check .` — `All checks passed!` | `local-static` |
| The formatter runs clean | `uv run --locked ruff format --check .` — 83 files already formatted | `local-static` |
| The type checker runs clean | `uv run --locked python -m mypy` — no issues in 15 source files | `local-static` |
| The default test lane is unchanged | `uv run --locked python -m pytest -q` — 2326 passed, 7 skipped, against 2281 before this change | `local-static` |
| No task runner is present | No `Taskfile`, `justfile`, `Makefile`, `noxfile.py`, or `tasks.py` in the tree, checked by a test | `local-static` |

Every command, its output, the host it ran on, and the failures that preceded the
passing runs are in
[the validation record](../../proof/toolchain/v1-s0-011-pr1-validation.md).

What none of it establishes: these results come from **one Windows host**, run by
hand, once. No Linux or macOS host has run any of them, no continuous-integration
service has run any of them, and a check that passes here has demonstrated
nothing about the same check running anywhere else.

## What this record does not decide

- **The continuous-integration service, and what labels a capable runner.**
  ADR 0005 D6, still open.
- **Test framework selection and coverage policy.** ADR 0005, unchanged. This
  record decides where pytest is configured, not what it asserts.
- **The schema language, authoring form, or validator.** ADR 0003, unchanged.
- **A container image build, a base image, or a release artifact.** Nothing here
  builds an image, and [the release process](../../releases.md) is unchanged.
- **A published distribution.** Nothing is uploaded to an index, and the
  classifier refuses an upload that tried.
- **A dependency vulnerability scanner, or an update cadence.** `DR-08` is
  untouched; no scanner is configured and no cadence is set.
- **Whether `tools/contract_validation` eventually moves into the distribution.**
  It stays outside it here. Moving it would change a path that this repository's
  documentation and ADR 0003 both name, and that is a change with its own diff.
