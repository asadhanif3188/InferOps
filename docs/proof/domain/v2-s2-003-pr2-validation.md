# V2-S2-003-PR2 validation

Date: 2026-10-02

This change executed the static parts of V2-E01, E01-A, E01-B, and E01-C, once, under the
merged [E01 family freeze record](../experiments/README.md), and recorded the result. This
page says how the run was prepared, what it found, why its record is `C0`, what the change
added to the repository and the register, and which checks ran.

The run contacted no cluster, runtime, registry, network, or model. It rendered, wrote
files, and refused inputs in memory, on one Windows host. Nothing was installed,
provisioned, deployed, or published. **E01-D did not run**: its environment identity is
pending, and the runner never starts it.

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
   `runner.files`, and they are the files this change commits.
3. In the worktree, `uv sync --locked` built the environment the lockfile pins; the
   `inferops` package imported from the worktree's own `src`. `--changes` printed
   `UNCHANGED`, and `git status --porcelain --untracked-files=all` printed nothing.
4. The run: `PYTHONHASHSEED=1 uv run --locked python -m experiment_e01 --run
   20261002-e01-abc-1 --root . --prelude <file>`, with the runner copy on `PYTHONPATH`.
   The runner rechecked every precondition itself, executed the three parts, started the
   second E01-A render in a second process with `PYTHONHASHSEED=2`, and wrote the evidence
   directory inside the worktree.
5. The evidence directory was copied into this change byte for byte: the SHA-256 of all ten
   files matched on both sides. The worktree and the runner copy were then removed.

[`commands.txt`](../experiments/v2-e01/runs/20261002-e01-abc-1/commands.txt) holds the
operator's preparation commands, marked as stated by the operator, then every command the
runner executed in order. Host paths are withheld by the runner, and written as
placeholders by the operator.

**The runner was exercised before the run.** Its test suite executes it end to end in
temporary Git repositories built from the pinned inputs, and one development preview did
the same to read the evidence format. Those executions are not E01 runs and are not result
evidence, as the freeze record's `notResultEvidence` says of the repository's suites. The
run of record is the only execution of the run command, and it was not repeated.

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
  registered refusal, wrote no output directory, and was refused identically the second
  time.

`python -m tools.experiment_e01 --check` computes every verdict again from the committed
files and prints `PASSED: 1 run(s), each agrees with its own evidence`.

## Why the record is `C0`

The freeze record registers `C0` for the static parts, and the V2 requirements name
deterministic rendering as `C0` work. Under [the evidence levels](../../testing/evidence-levels.md),
a `C0` record states that the behaviour its claim is about did not run, and runs only tools
and validators. The record reads the run the way three existing `C0` records read
`helm template`, under Kubernetes diagnosis, security controls, and ownership: a generator
ran as a tool, and what it wrote was inspected by a validator, here `--check`. The behaviour E01's hypothesis is about, a release that
deploys and serves, did not run. E01-D owns it, at `C2`.

**The tension is stated, not resolved.** The renderer is product code in `src/`, and it
ran. The register's parser claim, whose record is `C2`, draws its line at exactly that:
product code that ran. The E01 claim is about the release input the renderer writes, which
places it on the other side of the line, but a reader who weighs the two rows should know
where each sits. [The claim and evidence matrix](../../testing/claim-evidence-matrix.md) says
the same beside the row. Recording `C2` instead would contradict the merged freeze record
without a revision of it, and would label as runtime evidence a run that executed no
runtime component.

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
  `identical-validated-inputs-render-identical-release-input-and-invalid-inputs-are-refused`,
  certified at `C0` on one record of the run, through a seventh ledger,
  [`v2-s2-003-pr2-e01-static-proof.v1alpha1.json`](../testing/v2-s2-003-pr2-e01-static-proof.v1alpha1.json).
  It is the first ledger to add a claim: the evidence index gained an `add-claim`
  operation, undone only when the claim at its position is exactly the one added, and
  refused when the claim already exists. The claim is appended, so no existing JSON pointer
  into the register moves; the first draft inserted it beside the planned deployment claim
  and moved every later claim's position. The ledger also replaces the evidence index's
  reason, which named six ledgers. The claim's status was the maintainer's decision for
  this change.
- **Published pages.** The proof dashboard and the evidence index are regenerated; the
  README, the matrix document, the evidence index page, the experiments page, the proof
  index, the test inventory, and the change log state the new counts and the run. Two
  stale statements were corrected where they stood: "no E01 part has executed", on the
  proof index and in the freeze suite's inventory note, and the matrix paragraph saying the
  chart's values are written by an operator and deployment rendering does not exist, out of
  date since `V2-S2-001-PR2`.

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
  six renders are not; that check now also admits a file a committed E01 run's manifest
  records, because a run's renders are bound to the commit that ran them and are held to
  their own bytes by `--check`, not derived again from today's sources. And the security
  baseline refused the POSIX home-directory path a test of the redaction used as its
  example; the example is now a path under `/srv`.
- **The second full lane** printed 1 failed, 17,496 passed, 35 skipped, 14 deselected.
  The failure was the item above: its first wording quoted that home-directory path, and
  the security baseline refused this page for it. The item was reworded, and the security
  and documentation suites passed on the reworded tree; the lane was not run a third time.
- **A miscount here and in the matrix.** The first draft said two `C0` records read
  `helm template`; three do.

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

## Privacy and publicability

The run's files, the ledger, and this page name repository paths only. The runner withholds
absolute paths from the command line it records; the operator wrote the worktree and the
runner copy as placeholders; and a test refuses a drive letter, a home or temporary
directory, and an address in any file of the run. The host is named by its operating
system, its version, and its Python and uv versions, and by nothing else. No credential,
model artifact, prompt, or completion was read or written.

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
contract change that moves only its own output, deterministic refusal of invalid and
conflicting inputs, and static evidence held at `C0` without a runtime claim are met here.
E01-D's criteria are not reachable in this change: E01-D has not run, and its environment
identity is pending on `V2-S3-004-PR1`, as the freeze record names it.

## What this does not establish

- That the release input deploys through Git and Argo CD, or serves a completion.
- That another workload shape, contract, or binding renders deterministically: one
  contract on one binding ran.
- That the platform-defaults revision a release records names the defaults it was
  rendered from: the revision is asserted, not reconstructed.
- That the download URL and the licence reference agree with the contract: nothing checks
  them.
- That today's code would give the same result: the run is bound to `707e29f`, and nothing
  compares a committed run with a later tree.
- Reliability under failure, or production readiness.
