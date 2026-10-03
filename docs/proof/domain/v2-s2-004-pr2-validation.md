# V2-S2-004-PR2 validation

Date: 2026-10-03

What this change executed and checked before it was committed, and how. What it publishes
is in [experiment freeze records and runs](../experiments/README.md) and
[the claim and evidence register](../../testing/claim-evidence-matrix.md); this page is
about the one run it executed and the checks run over the repository afterwards.

The change executed E01-A, E01-B, and E01-C once, as
[freeze revision 2](../experiments/v2-e01/freeze-r2.v1alpha1.json) registers them. Those
parts are static: they render, write files, and refuse in memory. The parts contacted no
cluster, runtime, registry, or model, and nothing was provisioned or published. `uv run
--locked` compares the environment with the lock before it starts Python; the run did not
record whether that step changed the environment.
The evidence is `C0` under [the evidence levels](../../testing/evidence-levels.md). E01-D
did not run.

## Why this change exists

The first collective review of Sprint 2 returned *blocked* on two findings. `V2-S2-004-PR1`
closed the first, and the freeze half of the second: it derived the two model references
the hand-written values repeated, and it registered freeze revision 2, which pins the
runner, the analysis, and the freeze checker and detects an added material file. The
execution half was left open: no run had executed under revision 2. This change executes
that run and reconciles the register with it.

## Eligibility, checked before the run

- **What it builds on is merged.** `git pull origin main` moved `main` to
  `a5b6a5db2011a68a3f27acdeaa8186c226bfedb4`, the merge of pull request 113, which is
  `V2-S2-004-PR1`. The tree of that merge commit equals the tree of the commit it merged.
- **The checkout was clean.** `git status --porcelain --untracked-files=all` printed
  nothing. The branch for this change was created at that commit, so `HEAD` was the merged
  revision when the run started.
- **The freeze records hold.** `python -m tools.experiment_freeze --check` passed over two
  records, each with its registered digest.
- **No material file differs.** `python -m tools.experiment_freeze --changes` over revision
  2 reported no file changed, absent, added, or out of scope. The inventory is 74 pinned
  inputs: the static import closure of the runner's entry module, and the data files the
  parts read.
- **No change is unclassified.** Revision 2 was prepared from `26aecfcb`. The only commits
  between that revision and the executing one are the commit of `V2-S2-004-PR1` and its
  merge. Revision 2 classifies every difference from revision 1, added files included, and
  the inventory check found nothing since. This change classified nothing.

## What executed before the run

Freeze revision 2 does not permit a full execution of the parts outside `--run`, and says
that one that happens is reported here.

- **No preview executed.** In preparing this run, no development preview, dry run, or run
  in a throwaway repository executed E01-A, E01-B, and E01-C.
- **The test suites executed.** The suites of `V2-S2-004-PR1` ran before it merged, as
  [its validation record](v2-s2-004-pr1-validation.md) states. They call the runner against
  temporary repositories. Revision 2 lists that class as not result evidence, and it was
  listed before any run under revision 2. This change did not read the hosted checks of
  pull request 113; a hosted run of the same suites is the same class.
- **The two freeze commands executed**, as the eligibility checks above. They read files
  and run no part.

No code enforces the rule against previews. This statement is the operator's.

## How the run was executed

One command, from the checkout at the merged revision:

```sh
PYTHONHASHSEED=1 PYTHONDONTWRITEBYTECODE=1 uv run --locked python -m tools.experiment_e01 --run 20261003-e01-abc-1 --prelude <preparation commands file>
```

The runner and the `inferops` package were the checkout's own. Nothing was copied outside
the tree, and no import path was set. The preparation commands file lists the operator's
commands above; the runner copies them into
[`commands.txt`](../experiments/v2-e01/runs/20261003-e01-abc-1/commands.txt), marked as
stated by the operator, and withholds the file's host path.

What the manifest,
[`run.v1alpha1.json`](../experiments/v2-e01/runs/20261003-e01-abc-1/run.v1alpha1.json),
records:

| Item | Recorded value |
|---|---|
| Run identifier | `20261003-e01-abc-1` |
| Freeze record | `docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json`, revision 2, content SHA-256 `198f60b5133338e445b1c0fef9f9171ad3e58fe3bde66ac1e7a8d1d674730ac8`, the digest the registry pins |
| Registry | `docs/proof/experiments/registry.v1alpha1.json`, content SHA-256 `6c357892fff0f34c754f6d6a73388d402e89dd1527089178c20e96534f6411f2` |
| Executing revision | `a5b6a5db2011a68a3f27acdeaa8186c226bfedb4`, reachable from `origin/main` as the clone held it after the pull, at the same revision |
| Status before | No line |
| Material files that differ | None |
| Runner | `tools/experiment_e01/core.py`, in the checked-out tree; package `tools.experiment_e01` |
| Runner file digests | `__init__.py` `4e073f8c…`, `__main__.py` `eb945c72…`, `core.py` `df39eda6…`, each equal to its pin in revision 2 |
| `inferops` package | `src/inferops`, distribution version `1.0.0` |
| Loaded repository module files | 47 in the first process and 47 in the second, each a pinned input with its pinned content; none outside the pins |
| Second process | Exit status 0, `PYTHONHASHSEED` 2, runner in the checkout, package at `src/inferops` |
| Host | Windows 10.0.26200, Python 3.12.12, uv 0.9.16 |
| Started and finished | 2026-10-03T03:54:55Z and 2026-10-03T03:54:57Z |
| Status after | Only files under the run's evidence directory |
| Temporary directory | Removed |
| Abort conditions | None met |

## Every attempt

| Attempt | Run identifier | Freeze revision | E01-A | E01-B | E01-C |
|---|---|---|---|---|---|
| 1 | `20261002-e01-abc-1` | 1 | PASSED | PASSED | PASSED |
| 2 | `20261003-e01-abc-1` | 2 | PASSED | PASSED | PASSED |

Two runs of the static parts exist, and both stay recorded. The first carries
[an audit limitation](../experiments/README.md#audit-of-the-first-run-2026-10-03): it is
not evidence that its execution was governed by its freeze. The second was started once.
No attempt under revision 2 was REFUSED, ABORTED, INCONCLUSIVE, or FAILED, and none was
discarded. The command was not started a second time.

## What the run found

The order below is the order the work was done in: the raw evidence was checked for
completeness, the versioned analysis computed the verdicts, the verdicts were compared
with the frozen criteria, the outcome states were assigned, and the limitations were
written before this summary.

1. **The raw evidence is complete.** The run directory holds the files revision 2 names:
   the manifest, `commands.txt`, `render-a/`, `render-b/`, `mutation/`, `refusals.json`,
   and `result.md`. The manifest records the SHA-256 of eight of the ten files, and each has
   it. The other two are the manifest itself and `result.md`: `--check` generates the page
   again from the manifest and the files and compares it, and the evidence index binds both
   by SHA-256.
2. **The analysis is the frozen one.** `python -m tools.experiment_e01 --check` judged the
   run by revision 2's analysis and the first run by revision 1's, and printed
   `PASSED: 2 run(s), each agrees with its own evidence`. The analysis is
   `tools/experiment_e01/core.py`, a pinned input of revision 2.
3. **Each criterion, against its evidence:**

| Criterion | Part | Verdict | Raw evidence |
|---|---|---|---|
| E01-AC1 | E01-A | Held | `render-a/` and `render-b/`: both files byte-identical, SHA-256 `1849af0c…` for the values file and `b1670298…` for the release; `metadata.releaseId` `acedf5ac…` in both; second process exit status 0 with another hash seed |
| E01-AC2 | E01-A | Held | The release's `source.contract.sha256` and the manifest's `contractDigest`, both `56f73f78…` |
| E01-AC3 | E01-A | Held | The release's binding name, version, and digest `1a6c9e9f…`, and the manifest's `binding` |
| E01-AC4 | E01-A | Held | The release's `output.helmValues.sha256` and the bytes of the values file beside it; its renderer and platform-defaults revisions equal the executing revision |
| E01-AC5 | E01-A | Held | The manifest's `admission` (admitted, no finding), `workloadIntentTargets` (22 values, none absent from the generated file), `restatedPins` (none), and `mergedDifferences` (one, `telemetry.deploymentEnvironment`) |
| E01-AC6 | E01-B | Held | `mutation/` against `render-a/`: `runtime.replicaCount` 1 to 2, and three release fields; `source.contract.sha256` equals the manifest's `mutatedContractDigest`, `b3b3f6fd…` |
| E01-AC7 | E01-C | Held | `refusals.json`: seven cases, two executions each, every refusal the registered one, no output directory written |

4. **Outcome states.** E01-A PASSED, E01-B PASSED, E01-C PASSED.
5. **Limitations** are in [the result page](../experiments/v2-e01/runs/20261003-e01-abc-1/result.md),
   which lists them before the outcome, and in the register record.

**What differs from the first run, and why.** Revision 2 states E01-AC5 without the
exception revision 1 had. The run found 22 workload-intent chart values where the first
found 20: the two added ones are `model.artifact.sourceUrl` and `model.license.reference`,
which the renderer now derives. The run searched every hand-written string for a generated
workload-intent value of eight characters or more and found none. E01-C has seven cases
where it had six: the seventh is a hand-written download URL, which admission refused as
`render-manual-value-generated`. The release identifier and the values digest differ from
the first run's because the generated values hold two more entries and the executing
revision is another one.

## Why the record is `C0`

The claim is about the committed evidence of the run: the renders and refusals as
recorded, which a repository tool reads again. Freeze revision 2 registers `C0` for these
parts. The renderer that wrote the evidence is product code, and it executed. A claim that
the renderer renders deterministically at any revision would be `C2`, and the register
makes no such claim. This is the reasoning the first run's record used, and this change
does not alter it.

## What changed

- **The run.** [`20261003-e01-abc-1`](../experiments/v2-e01/runs/20261003-e01-abc-1/result.md),
  ten files, as the runner wrote them.
- **The register.** An eighth ledger,
  [the corrected E01 static proof ledger](../testing/v2-s2-004-pr2-e01-corrected-static-proof.v1alpha1.json),
  makes three register changes and one correction:
  - it adds the claim
    `the-second-e01-static-run-recorded-its-frozen-path-identical-renders-and-every-registered-refusal`,
    certified at `C0` on the one record it adds with it, appended to the register;
  - it appends a dated audit limitation to the first run's claim, and keeps that claim's
    earlier text, statement, status, and record;
  - it replaces the evidence index's reason, which named seven ledgers;
  - it writes one correction beside the first run's result page. The page is unchanged.
- **The evidence index and the dashboard** are regenerated. The index holds 67 records
  under 61 claims. The released pack is unchanged.
- **The tool.** `tools/evidence_index` names the eighth ledger. No file on the E01
  experiment path changed: `--changes` over revision 2 still reports none after this
  change.
- **The suites.** The E01 suite expects two committed runs and holds the second to the
  execution identity revision 2 requires. The post-release suite holds the eighth ledger.
- **The documents.** The experiments page, the proof index, the register page, the
  evidence index page, the test inventory, the contribution guide, the changelog, and the
  README counts.

The first run's claim is still `certified`. Its statement is about what that run's
committed files hold, and the audit found those files intact. The audit limitation says
what the run is not evidence of. The status of the new claim follows the decision the
maintainer made for the first run's claim.

## What was not touched

- Freeze revision 1, freeze revision 2, and the registry.
- The first run's directory. Each of its ten files, and freeze revision 1, has the Git
  blob it had at the executing revision. A test compares them where the clone holds that
  revision, and skips where it does not, as a shallow clone would. In every clone, the
  evidence index binds the first run's cited files by SHA-256, and `--check` holds the
  rest to the digests its manifest records.
- Every pinned input of revision 2, the runner and the freeze checker among them.
- The released `v1.0.0` pack, the release notes, the tag, and every accepted decision.

## Commands

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked python -m mypy
uv run --locked python -m tools.generated_release --check
uv run --locked python -m tools.experiment_freeze --check
uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json
uv run --locked python -m tools.experiment_e01 --check
uv run --locked python -B -m tools.evidence_index --check
uv run --locked python -B -m tools.evidence_index --gate
uv run --locked python -m tools.proof_dashboard --check
uv run --locked python -m tools.ci_gates no-skips helm
uv run --locked python -m pytest -q -rs
git diff --check
```

All ran from Git Bash on Windows.

## Results

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 610 files formatted, no lint finding, no type error in 336 source files |
| `tools.generated_release --check` | The reference release is what its declared sources derive |
| `tools.experiment_freeze --check` | 2 freeze records, every rule held |
| `tools.experiment_freeze --changes` on revision 2, before the run and after this change | No material file differs from the record |
| `tools.experiment_freeze --changes` on revision 1 | 4 files differ, the ones revision 2 classifies. The first run is judged by its own files, not by today's tree |
| `tools.experiment_e01 --check` | 2 runs, each agrees with its own evidence |
| `tools.evidence_index --check` | The index is what the register and ledgers produce |
| `tools.evidence_index --gate` | Exit 0; released `v1.0.0` set `1d40b33f…` and pack `652e9051…`, recomputed by undoing the four post-release ledgers and unchanged. The current pair moved, as a register change moves it |
| `tools.proof_dashboard --check` | The dashboard is what the register produces |
| `tools.ci_gates no-skips helm` | The chart suite ran 203 tests with none skipped, with Helm `v3.19.0` |
| The default lane, `pytest -q -rs` | 17,670 passed, none failed, 35 skipped, 14 deselected, in 10 minutes 33 seconds. The 35 skips are the ones the lane had before this change: host symlink privileges, POSIX signals on Windows, an absent collector image, and fixtures a test does not apply to. The 14 deselected tests are the lanes that need a cluster or a runtime |
| The same gates and the default lane, after the review's fixes | Every gate above gave the same result. 17,670 passed, none failed, 35 skipped, 14 deselected, in 9 minutes 39 seconds |
| `git diff --check` | Clean |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it over the full history |

One suite failed once before the lane: the index page's count of corrected files is spelled
as a word, and the suite's word list stopped at eleven. The list gained twelve, and the
lane above ran after that.

## What the independent review found

An independent review read the first commit, `c24fda4`, against the run's raw files and
the freeze record. It found no defect in the run, the ledger, or the frozen files, and it
confirmed the counts and digests above. It found these, and each is what the first commit
got wrong:

| Finding | What the first commit said | Correction |
|---|---|---|
| This page claimed more file digests than the manifest holds | "Each file has the SHA-256 the manifest records", over a list that included the manifest and `result.md` | The manifest records eight of the ten files. The page now says which two it does not, and what holds them |
| The records page said no run was INCONCLUSIVE, beside its own account of previews that were | "No run under either revision was REFUSED, ABORTED, INCONCLUSIVE, or FAILED" | The sentence is about committed runs, and it points to the previews in the audit |
| The test inventory's description of the post-release suite was out of date | "the one record and the one claim", and one later ledger | Three records, two claims, and three later ledgers. The first phrase was already out of date before this change |
| The register page still introduced "the E01 row" and "one run" | Singular, above a paragraph that says there are two | "The first E01 row" |
| A new test pinned the eighth ledger as the last one | The last position in the list of post-release ledgers | Its own position, so the next ledger does not fail it for a wrong reason |
| The test that the first run's files are unchanged skips in a shallow clone, and two texts did not say so | No caveat in the inventory or on this page | Both say it, and this page says what holds those files in every clone |
| Two statements went beyond what the run records | "nothing was installed", and "no network was contacted" in the register record | Both are now about the parts. This page says what `uv run --locked` does before Python starts |
| The audit texts in the register omitted one disclosure the records page carries | No mention that the committed runner files are not the ones the first run executed | The correction beside the first run's result page states it, with its basis |

The review could not verify the operator-stated commands in `commands.txt`, the statement
that no preview executed, or this page's lane figures. The first two are statements of the
operator, and this page marks them so.

## Gates that do not apply

- **Terraform.** Not applicable: this change touches no file under `infra/`.
- **Argo CD.** Not applicable: the repository holds no Argo CD configuration yet, and
  E01-D, which needs it, did not run.

## Privacy and publicability

The diff was read for private planning text, local paths, credentials, and later story
identifiers. The run's files name files by repository path; the one host path the command
received is withheld in `commands.txt`. The one later story identifier in the changed
files is the pending owner of E01-D's environment identity, `V2-S3-004-PR1`, which freeze
revision 2 already publishes.

## What this does not establish

- **That the release input deploys or serves.** E01-D owns that, and it did not run.
- **That the first run's execution boundary was valid.** The second run answers revision
  2 only.
- **That the renderer gives the same result at another revision,** or for another
  contract, binding, or workload shape.
- **That either derived URL resolves.** Nothing fetches it.
- **That the rule against previews holds.** It is a procedure, and the statement above is
  the operator's.
- **Reliability under failure, or production readiness.**
- **That Sprint 2 is approved.** The collective review is run again after this change
  merges, and later work stays unauthorized until that review is approved.
