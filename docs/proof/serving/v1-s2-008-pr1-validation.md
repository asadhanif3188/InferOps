# V1-S2-008-PR1 change validation

| Field | Value |
|---|---|
| Date | 2026-09-04 |
| Scope | A symptom-oriented local runtime troubleshooting guide, and the suite that holds it to the repository |
| Source branch | `docs/v1-s2-008-local-runtime-troubleshooting` |
| Evidence produced here | `local-static` for every command executed; **no new real-runtime evidence** |
| Real-runtime execution | **Not authorized and not run.** No container was started, no model byte was transferred, and no measurement was taken by this change |

## What this change is

[`local-runtime-troubleshooting.md`](../../serving/local-runtime-troubleshooting.md)
is one page organised by what an engineer *observed* rather than by which
component owns the fault, because the observation is the only input available on
arrival. It covers prerequisites, model acquisition and integrity, disk, ports,
memory and OOM, slow model load, readiness, timeouts, cache corruption and
staleness, API-to-runtime connectivity, shutdown and cleanup, and the case where
the honest answer is that the host cannot support the profile.

It adds no product behaviour. Nothing under `src/` or `deploy/` changed, and no
tool gained a flag, a subcommand, or a code path.

The guide is machine-checked rather than proofread.
[`tests/serving/test_local_runtime_troubleshooting.py`](../../../tests/serving/test_local_runtime_troubleshooting.py)
holds every `python -m tools.<module> <subcommand>` it prints to a module that
exists and a subcommand that module's parser accepts, every exit code it
publishes to the constant the tool returns, and every port, byte count, budget,
memory bound, cache root, ownership label, and capacity floor to the record that
owns it — never to a second copy. It also refuses a credential-shaped flag or
value anywhere in the file, requires the Kubernetes exclusion and the
one-host limitation to stay stated, and parses each inline Python diagnostic
rather than executing it.

That last decision is the one worth naming: two of the inline diagnostics read
the process environment and a platform-specific library, and a suite that
executed them would be asserting something about the machine running the suite
rather than about the document.

## Commands executed for this change

Every command below was **run**, from the repository root, on one Windows host.
The outputs are the ones the guide describes.

| Command | Result |
|---|---|
| `uv run --locked python -m tools.model_acquisition check` | `0`; `state verified (1834426016 bytes present)`, 80.00 GiB free |
| `uv run --locked python -m tools.model_acquisition verify` | `0`; 1,834,426,016 bytes, SHA-256 matched |
| `uv run --locked python -m tools.model_acquisition clean` | `0`; dry run, `retained; 1834426016 bytes found`. **`--confirm` was not run** |
| `uv run --locked python -m tools.model_lifecycle cache` | `0`; `hit`, mapping to `artifact-verified`, digest not read |
| `uv run --locked python -m tools.model_lifecycle check` | `0`; 8 states, 13 transitions, agreement with the package, model source record, and API drain budget |
| `uv run --locked python -m tools.model_lifecycle results` | `0`; the two prior observations, ready at 133,515 ms and 202,047 ms |
| `uv run --locked python -m tools.model_lifecycle clean` | `0`; preview only, 146,667 bytes. **`--confirm` was not run** |
| `uv run --locked python -m tools.runtime_packaging check` | `0`; pinned digest, container identity, loopback exposure, resources |
| `uv run --locked python -m tools.runtime_configuration check` | `0`; profile, command, model mount, health semantics |
| `uv run --locked python -m tools.local_composition check` | `0`; adapter `real`, mock fallback disabled, both loopback endpoints |
| `uv run --locked python -m tools.local_composition logs --lines 3` | `0`; three structured records, no prompt or completion present |
| `uv run --locked python -m tools.local_composition status --confirm-real-runtime` | **`5`**, not `0`; `owned=False running=False live=False ready=False`. Nothing was composed, so "composed but not ready" is the correct answer and the exit code the guide documents |
| `uv run --locked python -m tools.runtime_certification check` | `0`; prerequisites `cpus>=6`, `memory>=4294967296`, `disk>=2147483648` |
| `uv run --locked python -m tools.serving_baseline check` | `0`; registered fixture, phases, and success criteria |
| `docker version --format "{{.Server.Version}}"` | `0`; an engine is reachable on this host |
| `docker image inspect <pinned digest>` | `0`; the pinned image is local |
| `docker ps -a --filter label=io.inferops.package=llama-cpp-local-runtime` | `0`; **no owned container exists**, which is the state the guide describes as clean |
| `docker info --format "{{.NCPU}} CPUs; {{.MemTotal}} bytes"` | `0`; the engine reports its own figures, below the host's installed memory as the guide warns |
| The inline port probe | `0`; `8080 free`, `8090 free` |
| The inline disk probe | `0`; 80.00 GiB free |
| The inline AVX2 probe | `0`; `AVX2 True` on this host |
| The inline selection probe, empty environment | `0`; `refused: InvalidAdapterConfigError: INFEROPS_SERVING_ADAPTER: is required and is not set` |
| The inline selection probe, `real` with runtime variables absent | `0`; refused, naming `INFEROPS_LLAMA_SERVER_ENDPOINT` |
| The inline selection probe, complete real configuration | `0`; `accepted: real` |

Not one of these opened a network connection to a model source, started a
container, or wrote outside an ignored workspace path.

## A reproduced defect the guide now documents

The selection probe was executed with a complete, correct real configuration and
**refused** with `modelPath: must be an absolute path inside the serving
container`, naming a path nobody typed.

The cause is Git Bash on Windows, which rewrites a leading `/` in an environment
value into a Windows path before the process sees it.
`INFEROPS_LLAMA_SERVER_MODEL_PATH=/models/Qwen3-1.7B-Q8_0.gguf` arrived as
`C:/Program Files/Git/models/Qwen3-1.7B-Q8_0.gguf`, which is not
container-absolute, and the adapter settings correctly refused it.

Confirmed in both directions on this host: the value was printed back as the
rewritten path, and with `MSYS_NO_PATHCONV=1` set the same configuration was
accepted and reported `real`.

This is a **host tooling behaviour, not a defect in this repository**, and no
code was changed for it. It is exactly the class of thing this story exists to
publish: a second engineer following the documented configuration on the shell
the quick start recommends for Windows hits a refusal that names a value they
never entered.

## What independent review found, and what changed because of it

The guide and its suite were reviewed independently before this branch was
pushed. Four findings, all accepted; three corrected here, one already true and
now defended.

**One was a genuine overclaim in the guide, and it is the reason a second pass
exists.** The timeout table presented `INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS`
as having a 300,000 ms **default**, in explicit contrast to the request timeout
beside it. It does not. `settings.py` reads it through `_required_int`, the same
refusing accessor as the request timeout, and lists it in
`REQUIRED_ENVIRONMENT_VARIABLES`; only the drain budget has a code fallback. The
error was verified rather than accepted on assertion: a real configuration with
that one variable omitted was executed and produced
`INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS: is required and is not set`.

A reader who trusted that row would have omitted the variable expecting a
five-minute fallback and got a refusal at startup instead. The table now reads
`Required. No default` for both, and says that the 300,000 ms and 120,000 ms
figures elsewhere on the page are values the descriptors *select* rather than
values the distribution supplies.

Nothing caught it, because **every individual number on the page was correct** —
the check compared the figure with the record that owned it and never asked
whether the sentence around the figure was true. `test_the_timeout_table_says_required_exactly_where_the_code_requires`
now reads the requirement claim out of each row and compares it with the set of
variables the code refuses to run without, derived from the two modules that read
the environment. Reverting the row to the old wording fails it.

**One diagnostic the guide prints had not been executed.**
`local_composition status --confirm-real-runtime` was absent from the table
above while the page claimed every diagnostic on it had been run. It has now been
run, and it is the more useful result for having been: it exited **`5`**, not
`0` — "composed but not ready", the exact distinction the guide tells a reader to
draw from the exit code rather than the message.

**One test was weaker than its name.** The readiness check asserted only that
`503` and `200` each appeared somewhere in the prose. Swapping the two rows of
the readiness table — so the page claimed a `200` during load meant loading and a
`503` meant ready — left both tokens present and the test passing, while
reversing the most safety-critical fact on the page. It now reads the row each
status sits in.

**One link check saw only half of each link.** Fragments were stripped before the
existence check, so a heading renamed in another document would silently strand a
reader at the top of a long page. All five cross-document fragments were correct;
a check now keeps them so.

The three corrections were verified by mutation — the old wording, the swapped
readiness rows, and a renamed anchor each fail the new checks — rather than by
observing that the suite still passes.

## Validation results

| Command | Result | Evidence boundary |
|---|---|---|
| `uv run --locked ruff check .` | Passed; all checks passed | Repository-static |
| `uv run --locked ruff format --check .` | Passed; 265 files already formatted | Repository-static |
| `uv run --locked python -m mypy` | Passed; 147 source files checked | Repository-static |
| `uv run --locked python -m pytest tests/serving/test_local_runtime_troubleshooting.py -q` | Passed; 107 tests | Repository-static; reads files only |
| `uv run --locked python -m pytest tests/testing -q` | Passed; 1,034 tests | Repository-static; inventory and strategy agreement |
| `uv run --locked python -m pytest -q` | Passed; 5,652 passed, 27 skipped, 14 deselected | Default lane; real-runtime tests remained deselected. The 27 skips are pre-existing and unchanged by this branch |
| `git diff --check main...HEAD` | No trailing-whitespace or hard-tab match | Repository-static |
| Markdown trailing-whitespace and hard-tab sweep | No match in any file this change touches | Repository-static |
| Relative Markdown link sweep | No broken target | Repository-static |
| `gitleaks detect --config .gitleaks.toml --no-banner` | **Not run**; `gitleaks` is not installed on this host | Reported, not claimed |

## Acceptance criteria

| Criterion | Status | Where |
|---|---|---|
| Covers download/integrity, port, memory, model-load, readiness, timeout, and cache issues | **Met** | One section each, plus prerequisites, API-to-runtime connectivity, shutdown and cleanup, and a hardware section. The suite does not assert that a section is *good*, only that what it quotes is true |
| Commands are safe and tested | **Met for every command executed**; **stated, not executed**, for the authorisation-gated recoveries | Every diagnostic in the table above was run and exited `0`. `acquire`, `start`, `smoke`, `certify`, `measure`, and `run` are described and were **not** run. Both `clean` commands were run in their preview form only |
| Troubleshooting does not expose secrets or sensitive prompts | **Met** | The guide instructs against pasting prompts, completions, or runtime bodies; a test refuses a credential-shaped flag or value in the file; the tooling it points at prints states, counts, statuses, and durations only |

## Parent story status

`V1-S2-008` has one PR and this is it. The story's evidence obligation — a
documentation command-check log — is the executed table above.

## Deferred, and reported rather than implemented

- **No recovery that costs bytes or starts a process was executed.** A real
  acquisition is a 1.71 GiB transfer and a real start operates a container;
  neither was authorised for this change. The guide labels each as such.
- **The Linux branch of the AVX2 probe has never been run here.** It reads
  `/proc/cpuinfo` and is documented rather than executed, in a repository where
  no Linux host has ever run any of this.
- **No Kubernetes troubleshooting exists, deliberately.** No chart exists and no
  documented workflow deploys a manifest, so a section for it would be advice
  rather than documentation. The brief excludes it and the guide states the
  exclusion as a decision.
- **The startup budget is not raised.** One recorded run on the measured host
  exceeded 300,000 ms. Raising the budget would hide that finding; the guide
  publishes it as an unresolved limitation instead.
- **`gitleaks` was not run.** It is not installed on this host, and this record
  reports that rather than claiming a clean scan.

## Limitations

- **One host.** Every executed result here is from a single Windows 11 machine
  with Docker Desktop. Nothing is a supported-platform claim, and the guide says
  so where it quotes a number.
- **A passing suite is not a working guide.** The tests establish that the
  document's commands, codes, and constants match this repository. Whether
  following a recovery resolves a fault is not established by anything here, and
  cannot be until someone follows one on a broken host and records it.
- **Every measured figure quoted is borrowed.** The latency, model-load, and
  cold/warm numbers come from `V1-S2-005` and `V1-S2-007`, each linked at the
  point of use. This change measured nothing and may not be cited for any of
  them.
