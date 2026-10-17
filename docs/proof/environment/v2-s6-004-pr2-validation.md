# V2-S6-004-PR2 validation: the requalified chain and the first Q4 bound record

Status: **the corrected qualification path ran once, in order, and each run is kept.
[`q1-2`](../experiments/v2-q1/runs/q1-2/result.md) is `QUALIFIED` under Q1 revision 2;
[`q2-2`](../experiments/v2-q2/runs/q2-2/result.md) is `CHARACTERIZED` under Q2 revision 3
with S = 11,000 ms; [`q3-2`](../experiments/v2-q3/runs/q3-2/result.md) is
`CHARACTERIZED` under Q3 revision 2 with G = 10,113 ms; and `tools/experiment_bounds`
built the first Q4 bound record,
[`v2-q4/bounds-r1.v1alpha1.json`](../experiments/v2-q4/bounds-r1.v1alpha1.json), from
`q2-2` and `q3-2`.** Evidence level C2 for the three runs, on the docker-desktop provider
with one node; the bound record is derived from them and carries their level and their
boundary. No tool, driver, or freeze record was changed. `q1-1`, `q2-1`, and `q3-1` are
unchanged. No claim is registered. The downstream verdict is [below](#the-downstream-state).

| Property | Value |
|---|---|
| Branch | `test/v2-s6-004-requalify-q2-q3-q4` |
| Base | `ed892a4eac2ee505996f53b6d3e0da31b8e4e204`, the merge of `V2-S6-004-PR1` (pull request #151) |
| Freeze records | Q1 r2 `add73e7e4e9ed20253b0e67734d463cf27f20d685014bae57c79ce241ea48d22`, Q2 r3 `421628933641f8b7c064913c7af0b82d5f8663582e3dd1155a4ac2d8a6dc19af`, Q3 r2 `f1ebcc296ebc81f0257e6b352f707dad6e635c46dbbd046dfc893eb8fc3f77ff`, each registered by `V2-S6-004-PR1` and unchanged here |
| Provider and environment | docker-desktop, one node `desktop-control-plane`, Kubernetes `v1.36.1`; stable environment `sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c` |
| Release | `local-docker-desktop/support-assistant`, identifier `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`, at the desired revision `ed892a4` |
| Model and runtime | `Qwen/Qwen3-1.7B-GGUF` at `90862c4b…`, `Qwen3-1.7B-Q8_0.gguf`, 1,834,426,016 bytes; `ghcr.io/ggml-org/llama.cpp@sha256:100de626…` |
| Runs | `q1-2`, `q2-2`, `q3-2`, one each, in that order |
| Bound record | `docs/proof/experiments/v2-q4/bounds-r1.v1alpha1.json`, SHA-256 `542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116` |

## What the story asks of this change

`V2-S6-004-PR1` decided that the environment identity states the configuration and that
memory is a capacity fact, and froze the next qualification path. This change executes
it: the next Q1 qualification once; only if it qualifies, the compatible Q2 and Q3
characterizations once each; and only if both are characterized, the Q4 bound record from
their exact records. Every result is kept, whatever it shows. It runs no reliability
experiment and starts no part of `V2-S6-003`.

## Prerequisites, checked before an identifier was spent

| Prerequisite | State |
|---|---|
| `V2-S6-004-PR1` is merged | Yes: `ed892a4`, the merge of pull request #151, was the remote main |
| An explicit environment-identity decision | Yes: class B, [ADR 0021](../../architecture/decisions/ADR-0021-environment-identity-is-configuration-memory-is-capacity.md) |
| Every changed path input is covered by a merged registered freeze revision | Yes: `experiment_freeze --check` PASSED, 12 records; `--changes` of Q1 r2, Q2 r3, and Q3 r2 each UNCHANGED, at `ed892a4` |
| `q1-1`, `q2-1`, and `q3-1` are unchanged | Yes: each `--check` built its record again byte for byte |
| No `V2-S6-003` freeze exists | Yes: no freeze record of E02, E04, or E05 exists |
| The next identifiers | `q1-2`, `q2-2`, `q3-2`, and `bounds-r1`, none present in the tree or in a collector directory of this host; the work directories `q1run-2`, `q2run-3`, and `q3run-2` were unused |

## The sequence

All instants are UTC, on 2026-10-17. The Docker Desktop engine was stopped when the work
began and was started before the first phase, so its virtual machine booted once before
`q1-2` and did not boot again during the three runs. No tracked file was edited before a
phase `down` ended, except by the two commits named below, which added only run
directories.

1. **Branch at `ed892a4`.** The branch name existed locally from an earlier session at the
   same commit with no commit of its own; it was checked out, not recreated.
2. **`q1-2`**, under Q1 revision 2, at the executing commit `ed892a4`: phase `up q1run-2`
   14:56:11–15:05:50, phase `qualify` 15:06:05–15:10:59, phase `down` to 15:12:54. Each
   exited 0. **`QUALIFIED`**: 17 of 17 rules held; the caller completed 33 of 33 requests.
3. **Commit `28d2534`** added the directory of `q1-2` only, so that the Q2 tool, which
   reads the record of its qualification from the checkout, read it from a clean tree.
   It moved no pinned input: the three `--changes` stayed UNCHANGED.
4. **`q2-2`**, under Q2 revision 3, at `28d2534`: phase `up q2run-3` 15:14:32–15:25:40,
   phase `characterize` 15:25:49.516–15:28:43.265, phase `down` to 15:30:32. Each exited 0.
   **`CHARACTERIZED`**: 16 of 16 rules held; six intervals of 11,000 ms each;
   **S = 11,000 ms**.
5. **Commit `0dbea91`** added the directory of `q2-2` only.
6. **`q3-2`**, under Q3 revision 2, at `0dbea91`: phase `up q3run-2` 15:31:12–15:43:11,
   phase `characterize` 15:43:20.778–15:51:05.641, phase `down` to 15:53:18. Each exited 0.
   **`CHARACTERIZED`**: 14 of 14 rules held; 153 of 153 requests in 362,958 ms; the same
   4 pods Ready throughout; **G = 10,113 ms**, the nearest-rank p99 of 152 gaps.
7. **Commit `7766468`** added the directory of `q3-2` only.
8. **The bound record.** `python -m tools.experiment_bounds
   docs/proof/experiments/v2-q2/runs/q2-2/record.v1alpha1.json
   docs/proof/experiments/v2-q3/runs/q3-2/record.v1alpha1.json` exited 0, and its output is
   the committed record. `--check` builds it again with the same bytes. The output was
   first redirected to the file by a Windows shell, which wrote CRLF line ends, and the
   first draft of the pages stated the SHA-256 of those bytes, `99dbbad2…`. The file was
   rewritten with LF before the first commit, and every page states its SHA-256 with LF,
   `542b05dd…`, the digest that the bytes in the repository have. `--check` reads CRLF as
   LF, so it passed on both.
9. **Then the suites and the pages were edited**, after every phase had ended. Nothing ran
   again.

Each phase `down` ended with the namespaces and the custom resource definitions equal to
those that its phase `up` read before it installed anything, and with no persistent
volume. After the last one the cluster held only its five base namespaces.

## The chain

| Step | Identifier | Freeze record | Result | Value | Record SHA-256, LF |
|---|---|---|---|---|---|
| Q1 | `q1-2` | Q1 r2 | `QUALIFIED` | environment `sha256:6a219b3f…cd5c` | `1141cbd1c0acd7eff839395a89eba3fe116a060dafb3941128bf23c440ec1b3d` |
| Q2 | `q2-2` | Q2 r3 | `CHARACTERIZED` | S = 11,000 ms | `db0bd1579cdb93e0e8ede69e5c441006b54ed7ae7f7eee8d1f3c43ad34444531` |
| Q3 | `q3-2` | Q3 r2 | `CHARACTERIZED` | G = 10,113 ms, `p99`, 153 successes | `0a978396b5d7f15a4a6b507dda288d16dff5d937828cde2e2782a73d504ca99a` |
| Q4 | `bounds-r1` | the formulas of Q3 r1 and r2 | stated | four bounds below | `542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116` |

`q2-2` and `q3-2` each state the qualification `q1-2` with its record digest above, the
environment `sha256:6a219b3f…cd5c`, the provider docker-desktop, and the release
`b5457f49…c9db`. The bound record states the same four, and binds each source record and
each freeze record by its content digest. A test holds each of these links.

| Bound | Formula | Value |
|---|---|---|
| `runtime_start_bound_ms` | `S` | 11,000 ms |
| `caller_gap_reference_ms` | `G` | 10,113 ms |
| `reversal_recovery_bound_ms` | `(2 * S) + 30000` | 52,000 ms |
| `caller_total_unavailability_bound_ms` | `max(2 * G, 5000)` | 20,226 ms |

**Compatibility.** `q2-1` was not used: it is of the `q1-1` lineage, with the exact
identity. A test holds that the tool refuses `q2-1` with `q3-2` with
`bounds-environment-differs`. The tool was not changed.

## What the runs show beside their results

- **The memory figure of this boot.** The capacity readings of the three runs each stated
  10,429,972,480 bytes for the engine and the node, the figure that `q3-1` read, and the
  gate accepted each. Under revision 2 the figure is not identity; a test holds that the
  stable identity of the readings of `q1-1` and `q3-1` is the one that `q1-2` states.
  Nothing here establishes why the figure repeated.
- **The capacity margin** of the reading of `q1-2` was 260,882,432 bytes of memory limits
  against what was available, as small as for `q1-1`.
- **The API image digest is another one at each build.** The three phases `up` reported
  `f10c9e9b…`, `54f74884…`, and `bfb5c2b0…` for the same inputs. Each build printed the
  image manifest `bba83fa7…` and the config `cd65ca24…`, as the builds of `q1-1`, `q2-1`,
  and `q3-1` did. Each record holds the API Deployment to the digest that its own phase
  `up` declared, as the frozen rules require.
- **The seed import took 190.7 s, 236.6 s, and 305.6 s** in the three phases `up`. No rule
  reads it.
- **The Q3 watch holds 10 `MODIFIED` events** that changed only a second host address of a
  pod and its managed-fields time. No Ready condition or restart count changed.
- **G is large for a healthy run.** With two closed-loop workers and successes taking up
  to 16.7 s, the p99 gap is 10.1 s with no failed request. The run page states it.

## Edits after the runs

- **Run pages** for `q1-2`, `q2-2`, and `q3-2`, each stating what ran, the identities, what
  the files show, what is not committed, and what it does not establish.
- **Suites.** The Q1 suite holds both committed qualifications and that `q1-2` states the
  stable identity under revision 2, equal to that of the readings of `q1-1` and `q3-1`.
  The Q2 suite holds `q2-2`. The Q3 suite holds `q3-2` and recomputes G from the committed
  caller record; the test of `q3-1` now holds that no bound record names it, where it held
  that none existed. The Q2 and Q3 lineage tests held that the record of `q1-2` did not
  exist, and now hold that it does. The Q4 suite holds `bounds-r1`, recomputes each bound
  from the formulas written out, and holds the refusal of `q2-1` with `q3-2`. The layout
  suite names the three new directories, and the Argo CD guard names the five
  reconciliation samples of `q1-2`.
- **Pages.** The Q1, Q2, and Q3 pages, the experiments index, the evidence layout page,
  the root README, the architecture and proof indexes, the test inventory and its JSON,
  and the change log, each with a dated note where a statement changed. The Q2 and Q3
  pages and the architecture index also said that the characterizations run "in the
  environment that `q1-1` selected"; each now names the lineage of its revision.

## What is committed, and what is not

Each run directory is committed as its phase wrote it, with `capacity/pods.json` left out
as for every earlier qualification: it holds container paths under a home directory in
the controller's pods. Its SHA-256 with LF for each run: `q1-2`
`2257cf76fc64a08bfee1b49ab341cbd3c9065cc11a38fd5f0c3a94e39622110d`, `q2-2`
`f8a0d16c80e11f40086981accdaab7466a984f517ce57167977d9a1526d65b7f`, `q3-2`
`90589714161b4e12a7b0e250138e5d9ee23b1058a3fa28e72b0fe595d15f8aa2`. No committed file
corroborates them. Each transcript joins the three phase transcripts with three edits
only: terminal colour codes removed, the absolute host path written as `<repository>`
(two lines each), and trailing whitespace removed (six lines each). A scan of the three
directories for the host path, the account name, and home directories found none after
those edits.

## Validation

All commands ran from Git Bash in the locked environment (`uv run --locked`).

| Check | Command | Result |
|---|---|---|
| Committed qualifications | `python -m tools.environment_qualification --check` | PASSED, 2 |
| Committed Q2 characterizations | `python -m tools.runtime_startup --check` | PASSED, 2 |
| Committed Q3 characterizations | `python -m tools.caller_characterization --check` | PASSED, 2 |
| Bound records | `python -m tools.experiment_bounds --check` | PASSED, 1 |
| Freeze records | `python -m tools.experiment_freeze --check` | PASSED, 12 records |
| Freeze changes | `python -m tools.experiment_freeze --changes` for Q1 r2, Q2 r3, and Q3 r2 | UNCHANGED for each |
| Evidence layout | `python -m tools.experiment_evidence repository` | 11 run directories: 3 pre-schema, 6 qualifications with the text rules only, 2 conforming, 0 refused |
| Lint | `ruff check .` | clean |
| Format | `ruff format --check .` | clean |
| Types | `python -m mypy`, and again with `--platform linux` | clean on both, 430 source files |
| Tool suites | the Q1, Q2, Q3, and Q4 suites | 387 passed |
| Default lane | `python -m pytest -q` | 22,822 passed, 39 skipped, 14 deselected, in 66 min, on the staged tree of the first commit before this figure was written |
| Whitespace | `git diff --check` | clean |
| Hosted CI | the workflows of the pull request | Not run here: no pull request exists when this record is written |

The first run of the affected suites, before the suites were edited, failed 11 tests, each
a guard that named the committed runs by path or count: the four of the Q1 suite, two of
the Q2 suite, two of the Q3 suite, two of the layout suite, and the Argo CD guard. Each is
closed by an edit named above.

## What the independent review found

Two independent reviews read the four commits before the push: one checked every figure
of the run pages and of this record against the committed raw files, and one checked the
suites, the links of the chain, the boundaries of the commits, and the diff for private
content and host paths. The reviewers are automated sessions. Neither found a number, an
instant, or a digest that the raw files contradict, a changed tool, driver, freeze
record, or historical run, or private content. The second commit closes what they found.
It changes no run directory and no bound record, so every figure above stands.

**What the first commit got wrong, corrected in place:**

| ID | Severity | Finding | What changed |
|---|---|---|---|
| M1 | medium | The Q1 section of the experiments index still ended an item on revision 2 with "No qualification ran under revision 2." in the present tense, while the next item said that `q1-2` ran under it | The item says that `q1-2` ran under revision 2, with a dated note |
| M2 | medium | The root README kept, in the same paragraph as the new chain, "One characterization has run" twice, "one qualification has run", "in the environment that `q1-1` selected", and "No G and no bound has been stated", so the paragraph said "no G" and G = 10,113 ms at once. This record said that the "`q1-1` selected" wording was corrected on the Q2 and Q3 pages and in the architecture index; the README had been missed | The paragraph names the first run of each kind as the first, names the environment of a Q1 qualification, and its closing note states what it said until this change |
| M3 | medium | The Q2 and Q3 sections of the experiments index still said that Q2 and Q3 measure "in the environment that `q1-1` selected" | Each names the qualification of each revision: `q1-1` for Q2 revision 2 and Q3 revision 1, `q1-2` for Q2 revision 3 and Q3 revision 2 |
| L1 | low | The row of ADR 0021 in the architecture index said "No qualification ran under it" and, in the same cell, that `q1-2` ran under it | The first sentence reads "Until `V2-S6-004-PR2` no qualification ran under it" |
| L2 | low | The test of `q3-1` had held that no bound record exists; the first commit turned that into a loop that passes for any record not naming `q3-1`, and that is vacuous when none exists | It holds that exactly one record exists, `bounds-r1`, and that it names `q3-2` |
| L3 | low | The test of `q1-2` asserts that its executing commit is its desired revision, which its docstring did not say | The docstring says it: no tracked edit preceded the run |

The reviewers also confirmed what the first commit did right: each run commit touches only
its own directory; the executing commits in the headers are ancestors of the branch head;
each source and freeze digest of the bound record matches its file; G, the gaps, and the
latency figures recompute from the caller record; the 10 `MODIFIED` watch events of
`q3-2` differ only in the host address and the managed fields; and the new tests compute
S, G, the bounds, and the stable identity independently of the tool's output.

After these corrections the edited suites ran again: the Q1 and Q3 suites, the document
links, the security baseline, and the test inventory, 3,014 passed. ruff and the formatter
were clean, and `git diff --check` was clean. The full default lane did not run again;
the corrections change only Markdown and two tests.

What the reviews could not check, and this record does not claim beyond the operator's
statement: the SHA-256 and byte counts of the `capacity/pods.json` files left out, the
lines with `/home/` in them, that the virtual machine booted once, and the counts of the
default lane and of the tool suites.

## What is not established

- That a later boot of the virtual machine keeps the memory figure, or that a later
  reading passes the capacity gate; each later run is held to the gate on its own reading.
- S or G under a fault, under other load, on another node, or in another environment; the
  spread of S or G across runs; or why the starts took 11 s.
- That the bounds are right for a reliability experiment. They are the frozen formulas
  applied to one Q2 and one Q3 characterization.
- Any production availability, high availability, service level, benchmark, cost, or
  resilience to the loss of a node, a zone, or a region, and anything at C3 or C4.

## The downstream state

**`V2-S6-003` UNBLOCKED** by
[`docs/proof/experiments/v2-q4/bounds-r1.v1alpha1.json`](../experiments/v2-q4/bounds-r1.v1alpha1.json),
SHA-256 `542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116`, derived from the
matching characterized records `q2-2` and `q3-2` of the selected lineage `q1-2`, environment
`sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c`. This change starts
no part of it: no freeze record of E02, E04, or E05 is created, and no fault is injected.
Sprint 6 stays open.
