# V2-S2-003-PR2 validation

Date: 2026-10-02

This change executed the static parts of V2-E01, E01-A, E01-B, and E01-C, once, under the
merged [E01 family freeze record](../experiments/README.md), and recorded the result. This
page says how the run was prepared, what it found, why its record is `C0`, what the change
added to the repository and the register, which checks ran, and what an independent review
found.

The run contacted no cluster, runtime, registry, network, or model. It rendered, wrote
files, and refused inputs in memory, on one Windows host. No release was installed, and
nothing was provisioned, deployed, or published; the one installation was the locked
Python environment `uv sync --locked` built in a temporary checkout. **E01-D did not run**:
its environment identity is pending, and the runner never starts it.

## Eligibility, checked before the run

- **The freeze record is merged.** `git checkout main && git pull origin main` brought
  `main` to `707e29f4a0ff31ea90fa33f6b8cf2ec883cfb6a3`, the merge of `V2-S2-003-PR1`,
  which holds `docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json` with content
  SHA-256 `fcb19502d1d8350395b88293f4e3e2bf92076591e3fa8ecfc814defa46267fa9`, the digest
  `FROZEN_RECORDS` pins.
- **The record holds every rule.** `python -m tools.experiment_freeze --check` printed
  `PASSED: 1 freeze record(s), every rule held`.
- **No pinned input moved.** `python -m tools.experiment_freeze --changes` over the record
  printed `UNCHANGED`. The record's last edit is `4e92d6c`. After it, one commit merged
  before `707e29f`, `ec36a30`, and `git diff --stat 4e92d6c 707e29f` lists four files:
  `CHANGELOG.md`, `docs/domain/helm-values-renderer.md`, this story's first validation
  record, and `tests/domain/test_generated_release_drift.py`. None of them is a pinned
  input, so no experiment-path change needed a freeze revision, and this change
  classified none.
- **The gate and the pack before the change.** `python -B -m tools.evidence_index --gate`
  at `707e29f` exited 0 with `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` with the set
  `1d40b33f…` and the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack
  `0c2f2508…`.

## How the run was executed

The freeze's preconditions require the merged commit and a clean working tree. The runner,
`tools/experiment_e01`, is new in this change, so it is not in that commit. It ran from
outside the tree:

1. A detached worktree was created at `707e29f4a0ff31ea90fa33f6b8cf2ec883cfb6a3`, with
   `core.longpaths` set because the first attempt, under a long temporary path, could not
   create two fixture files. That worktree was removed before anything else ran.
2. The three runner files were copied byte for byte to a directory outside the worktree,
   as the package `experiment_e01`. Their SHA-256 values are in the run manifest's
   `runner.files`, and they are the files this change's first commit holds. The review
   fixes below changed them afterwards.
3. In the worktree, `uv sync --locked` built the environment the lockfile pins. Before the
   run, `python -c` printed the location of the imported `inferops` package, inside the
   worktree's own `src`. That was observed and not transcribed: the command is not in
   `commands.txt`, and the runner as it ran did not record the location; the review added
   that. `--changes` printed `UNCHANGED`, and `git status --porcelain
   --untracked-files=all` printed nothing.
4. The run: `PYTHONHASHSEED=1 uv run --locked python -m experiment_e01 --run
   20261002-e01-abc-1 --root . --prelude <file>`, with the runner copy on `PYTHONPATH`.
   The runner rechecked every precondition it then had, executed the three parts, started
   the second E01-A render in a second process with `PYTHONHASHSEED=2`, and wrote the
   evidence directory inside the worktree.
5. The evidence directory was copied into this change byte for byte: the SHA-256 of all ten
   files matched on both sides. The worktree and the runner copy were then removed.

[`commands.txt`](../experiments/v2-e01/runs/20261002-e01-abc-1/commands.txt) holds the
operator's preparation commands, marked as stated by the operator, then every command the
runner executed in order. Host paths are withheld by the runner, and written as
placeholders by the operator.

**Executions before the run.** Before the run, the runner executed the three parts in
temporary Git repositories built from the pinned inputs, never at the merged commit: its
test suite, which also does so on every default lane, and one development preview, run once
to read the evidence format, which showed every part PASSED. Neither is result evidence.
The freeze record's `notResultEvidence` names the repository's suites and checks before it
merged; it does not name a preview after it, so the preview is disclosed here and in the
record's limitations instead. The run of record is the only execution at the merged commit
and the only one recorded as a run, and it was not repeated.

## What the run found

[`result.md`](../experiments/v2-e01/runs/20261002-e01-abc-1/result.md) gives each criterion,
its verdict, and its evidence, with the limitations first. In short:

| Part | Outcome | Criteria |
|---|---|---|
| E01-A | PASSED | E01-AC1 to E01-AC5 held |
| E01-B | PASSED | E01-AC6 held |
| E01-C | PASSED | E01-AC7 held |

- **E01-A.** Both files of `render-a` and `render-b` are byte-identical, with the values
  digest `137a97b9…` and the release digest of each equal, and the same release
  identifier. The release records the contract digest, the binding `local-kind` with its
  version and digest, the values file's digest, and the executing revision as both its
  renderer and platform-defaults revision; each equals the value computed apart from it.
  `admit_manual_values` admitted the hand-written file with no finding, all 20
  workload-intent chart values are in the generated file, and the merged V2 and V1 values
  differ only at `telemetry.deploymentEnvironment`, `local` against `dev`.
- **E01-B.** The replica range set to two moved `runtime.replicaCount` from 1 to 2 and no
  other value, and moved only `metadata.releaseId`, `output.helmValues.sha256`, and
  `source.contract.sha256` in the release, the last equal to the mutated contract's digest.
- **E01-C.** Each of the six cases was refused at its registered step with exactly its
  registered refusal, left its output directory absent, and was refused identically the
  second time. Five refusals carry a rule, a category, and a code; E01-C-4 comes from the
  binding parser and carries a code and a field, as the freeze record registers it.

`python -m tools.experiment_e01 --check` derives every verdict again from the committed
renders, the recorded refusals, and the observations the manifest records, and prints
`PASSED: 1 run(s), each agrees with its own evidence`. It does not recompute the contract,
binding, or mutated-contract digests, the admission, or the V1 merge: those are the run's
observations. The fact-check below recomputed each of them independently, and each matched.

## Why the record is `C0`

The claim is about the run's committed evidence: two renders that are byte-identical and
record their sources, a mutated render that differs only where the mutation owns, and
twelve recorded refusals that match the registered ones. That is a claim about committed
documents a repository tool reads, which is the line the register's two contract rows sit
on at `C0`. The freeze record registers `C0` for these parts as well. The renderer and the
parsers that produced the evidence ran, recorded as tools, the way three existing `C0`
records name `helm template` as a tool, under Kubernetes diagnosis, security controls, and
ownership.

**What is not claimed, and why.** The renderer is product code in `src/`, and it executed.
A claim that the renderer renders deterministically, at any revision, would be about
`src/` doing what it says, and by the register's parser row, whose record is `C2`, it would
be `C2`. This change makes no such claim, and the claim's limitation and `doesNotEstablish`
say so. The first draft of this section argued the other way, from the E01 hypothesis
rather than the claim, and the review found the argument circular; it is replaced.
[The claim and evidence matrix](../../testing/claim-evidence-matrix.md) says the same beside
the row.

## What changed

- **The runner and the judge.** `tools/experiment_e01` runs the static parts once and
  checks a committed run. It reads every input, edit, and expected refusal from the freeze
  record. It refuses an identifier that is not today's UTC date, an evidence directory that
  exists, and a start without `PYTHONHASHSEED=1`, and it records a failed precondition as a
  run with every part REFUSED. The render-boundary suite exempts it by name, beside the
  generated-release check, from "no tool imports the render package", and from "nothing on
  a delivery path names a repository check".
- **The run's evidence.** [`runs/20261002-e01-abc-1/`](../experiments/v2-e01/runs/20261002-e01-abc-1/result.md),
  with the files the freeze record's `evidencePaths` names. `.gitattributes` pins it to LF,
  because the manifest records the SHA-256 of each file as written.
- **A new suite.** [`tests/testing/test_experiment_e01.py`](../../../tests/testing/test_experiment_e01.py)
  checks the committed run against its evidence, plants each kind of tampering in a copy,
  holds the judge to each outcome state, and executes the runner end to end in a temporary
  repository. No test requires a fresh execution to pass.
- **The register.** One claim,
  `the-first-e01-static-run-recorded-identical-renders-and-every-registered-refusal`,
  certified at `C0` on one record of the run, through a seventh ledger,
  [`v2-s2-003-pr2-e01-static-proof.v1alpha1.json`](../testing/v2-s2-003-pr2-e01-static-proof.v1alpha1.json).
  It is the first ledger to add a claim: the evidence index gained an `add-claim`
  operation, undone only when the claim at its position is exactly the one added, and
  refused when the claim already exists or its position is outside the claims. The claim
  is appended, so no existing JSON pointer into the register moves. The ledger also
  replaces the evidence index's reason, which named six ledgers. The claim's status was
  the maintainer's decision for this change.
- **Published pages.** The proof dashboard and the evidence index are regenerated; the
  README, the matrix document, the evidence index page, the experiments page, the proof
  index, the test inventory, the contributor guide, and the change log state the new
  counts and the run. Stale statements were corrected where they stood: "no E01 part has
  executed", on the proof index and in the freeze suite's inventory note; the matrix
  paragraph saying the chart's values are written by an operator and deployment rendering
  does not exist, out of date since `V2-S2-001-PR2`; and, after the review, the proof
  index calling the release record the only one the register had gained, every page and
  docstring naming six ledgers, and four pages describing the drift check and the
  render-boundary exemption as they were before this change.

No pinned input of the freeze record changed: `pyproject.toml`, `uv.lock`, the renderer,
and `tools/generated_release` are untouched, and `--changes` still prints `UNCHANGED` on
this change's tree.

## What the checks caught before the first commit

- **A host path in the recorded command line.** The first draft of the runner wrote
  `sys.argv` into `commands.txt`, which would have carried the absolute path of the
  `--prelude` file. Found before the run by reading a preview's output; the runner now
  withholds an absolute value of `--prelude` or `--root`, and a test holds it to that.
- **The claim's position.** Inserting the claim beside the planned deployment claim
  moved every later claim's index, and the release suite reads the current register by
  the released index. The claim is appended instead.
- **Tests that assumed two post-release ledgers, or a `field` on every change.** The
  post-release, index, and matrix suites were extended to a third post-release ledger and
  to the `add-claim` operation, and the index suite's grounding check now reads a record
  that arrives inside an added claim; without that, the new record would have escaped it.
- **The first full lane** printed 12 failed, 17,485 passed, 35 skipped, 14 deselected.
  Ten failures were the evidence index read while this page was being edited during the
  lane, and passed once the index was regenerated. Two were real. The generated-release
  suite requires every committed `values.generated.yaml` and
  `rendered-workload-release.yaml` to be in a declared release directory, and the run's
  six renders are not; that check now also admits a render a committed E01 run's manifest
  records, because a run's renders are bound to the commit that ran them and are held to
  their own bytes by `--check`, not derived again from today's sources. And the security
  baseline refused the POSIX home-directory path a test of the redaction used as its
  example; the example is now a path under `/srv`.
- **The second full lane** printed 1 failed, 17,496 passed, 35 skipped, 14 deselected.
  The failure was the item above: its first wording quoted that home-directory path, and
  the security baseline refused this page for it. The item was reworded, and the security
  and documentation suites passed on the reworded tree.
- **A miscount here and in the matrix.** The first draft said two `C0` records read
  `helm template`; three do.

## What the independent review found

Two reviewers read the first commit, `89418e4`, independently: one reviewed the code and
the tests, and one fact-checked every figure and sentence against the data. Neither found
a defect in the run's data. The fact-check recomputed the contract, binding, and
mutated-contract digests, the 20 workload-intent values, the V1 merge, the mutation's
differences, and all twelve refusals, and each matched; every manifest digest matched its
file; the three runner files in the first commit hash to the manifest's `runner.files`.
None of the defects below changed a verdict of the run: `--check` passes on it under the
corrected judge. What the first commit got wrong:

- **The claim was worded about the renderer, not the evidence**, and its `C0` argument
  swapped the claim's behaviour for the E01 hypothesis's. The claim is renamed and
  reworded to be about the run's committed evidence, and this page says that a claim about
  the renderer itself would be `C2` and is not made. The first draft also cited an
  unpublished document for the level; that sentence is removed.
- **The claim overstated E01-C.** It said every refusal carried a rule, a category, and a
  code, and that nothing was written. E01-C-4 carries a code and a field, and the run
  checked only that each case's output directory is absent. Its `doesNotEstablish` also
  omitted a later revision and invalid inputs beyond the six; both are added.
- **`--check` was described as recomputing every verdict from the files.** It derives
  verdicts from the renders, the refusals, and the run's recorded observations. Every
  page that said otherwise now says which values are observations.
- **This page contradicted itself about executions before the run**, calling the run the
  only execution while a preview had run the command. It now names the preview, its
  outcome, and where it ran, and the record's limitations do too.
- **A FAILED part could be reported as INCONCLUSIVE**, which the repetition rule would
  let a run repeat: the judge checked for an unanswered criterion before a failed one, and
  E01-AC1 was unanswered rather than failed when the renders differed but the second
  process's seed report was missing. A failed criterion now makes its part FAILED.
- **The merge could be self-attested.** A hidden `--merged-ref` option replaced
  `origin/main`, and `--check` did not read which reference a run used. The option is
  removed from the command, and `--check` refuses a run naming another reference, or one
  whose recorded precondition findings are not the ones its recorded observations give.
- **Nothing recorded which `inferops` package the run imported.** A run now records it and
  refuses to start when it is not the checkout's own. The run of record predates this,
  and step 3 above says what was observed instead.
- **A crash after the evidence directory existed could leave no manifest**, and an
  unreadable render or manifest raised a traceback in `--check`. The judge now answers
  nothing for a file it cannot read, a judge that raises is recorded as the run's
  `error`, and a malformed manifest is a finding.
- **Stale pages.** The proof index called the release record the only record the register
  had gained since the release; five pages and docstrings named six ledgers, and three
  lists of the index's inputs omitted the seventh; the
  experiments page said no test runs an experiment, while the suite runs the parts end to
  end on every lane; and four pages described the drift check and the render-boundary
  exemption as they were before this change.
- **Smaller items.** A JSON Patch `add` with no value raised a bare `KeyError`; an
  `add-claim` position outside the claims was not refused; the drift check admitted any
  generated file a run's manifest names, where it now admits only `render-a`, `render-b`,
  and `mutation`; the contributor guide stated a rule against editing a run as if it were
  enforced; and this page said nothing was installed.

The first fix introduced a defect the suite caught before this commit: the runner's new
package-location variable reused the name of the runner's own package parameter, so the
second render was started as the wrong module and E01-AC1 went unanswered in the
end-to-end test.

**Not changed, and why.**

- The judge still requires only that some workload-intent values were listed, not that
  there were 20; holding the count would add a criterion the freeze record does not state.
- The merge of values files stores a null where Helm would delete the key. No input of the
  run holds a null, and the fact-check confirmed that the merge matches Helm here.
- The status check sees what `git status` sees, so a write to an ignored path or outside
  the repository is not detected. The experiments page says so.
- The compatibility matrix the run sets stays set when none was set before, as the
  generated-release reader leaves it.
- A pinned input is a listed file, so a new file added under the pinned directories moves
  no pin. That is a property of the freeze record, recorded when it merged.

## Commands

```text
uv run --locked python -m tools.experiment_freeze --check
uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json
uv run --locked python -m tools.experiment_e01 --check
uv run --locked python -B -m tools.evidence_index --write
uv run --locked python -B -m tools.evidence_index --gate
uv run --locked python -B -m tools.proof_dashboard --write
uv run --locked python -B -m tools.proof_dashboard --check
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked python -m mypy
git diff --cached --check
uv run --locked python -m pytest -q
```

After the change, `--gate` exits 0 with the released pair unchanged, the set `1d40b33f…` and
the pack `652e9051…`. The current pair moved, as it does for any change to a cited file or
a ledger; [the evidence index page](../v1-evidence-index.md) states it, and this page cannot,
because it is one of the files the pair covers.

## Privacy and publicability

The run's files, the ledger, and this page name repository paths only. The runner withholds
absolute values of `--prelude` and `--root` from the command line it records; the operator
wrote the worktree and the runner copy as placeholders; and a test refuses, in any file of
the run, a drive letter, a home, user, or temporary directory, a scratch or planning
directory, and an e-mail address. The host is named by its operating system, its version,
and its Python and uv versions, and by nothing else. No credential, model artifact, prompt,
or completion was read or written.

## Acceptance

| Criterion | State |
|---|---|
| The E01 freeze record is merged before the run, and the run records the merged revision | Met. `707e29f` recorded in the manifest, the record, and here |
| Every experiment-path change merged since the freeze is listed, and none is unclassified | Met. None of the four files changed since `4e92d6c` is a pinned input |
| E01-A, E01-B, and E01-C execute under the frozen criteria, with revision, digests, commands, outputs, limitations, and result state | Met. One run, every part PASSED |
| `C0` evidence is added through the evidence model and register | Met. One claim and one record, through the seventh ledger |
| Failed or inconclusive attempts are preserved where material | None occurred. The failed worktree creation ran no part and wrote no evidence |
| The real deploy and serve path is not certified | Met. E01-D did not run; the claim's limitation and `doesNotEstablish` say so |
| The freeze record and its criteria are not edited | Met. `--check` passes with the pinned digest |

For the story as a whole: rendering the V1 synchronous workload through V2, and merging the
freeze record before any run, were met by `V2-S2-003-PR1`. Two clean renders that match, a
contract change that moves only its own output, deterministic refusal of the registered
invalid and conflicting inputs, and static evidence held at `C0` without a runtime claim
are met here. E01-D's criteria are not reachable in this change: E01-D has not run, and its
environment identity is pending on `V2-S3-004-PR1`, as the freeze record names it.

## What this does not establish

- That the release input deploys through Git and Argo CD, or serves a completion.
- That the renderer is deterministic at any revision other than `707e29f`, or for another
  workload shape, contract, or binding: one contract on one binding ran, once.
- That any invalid input beyond the six registered cases is refused.
- That the platform-defaults revision a release records names the defaults it was
  rendered from: the revision is asserted, not reconstructed.
- That the download URL and the licence reference agree with the contract: nothing checks
  them.
- That today's code would give the same result: nothing compares a committed run with a
  later tree.
- Reliability under failure, or production readiness.
