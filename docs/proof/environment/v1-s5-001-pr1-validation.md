# V1-S5-001-PR1 change validation

Date: 2026-09-18

Change: [the clean-clone workflow](../../../scripts/environment/clean-clone.sh), the
[checklist](../../environment/clean-clone.v1alpha1.json) it runs, the
[ledger tooling](../../../tools/clean_clone/) that decides what a run may record,
[the operator page](../../environment/clean-clone.md), the two test modules that
drive them --
[the workflow executed against stubs](../../../tests/architecture/test_clean_clone_workflow.py)
and [the ledger and checklist rules](../../../tests/architecture/test_clean_clone_ledger.py)
-- the two rows those modules add to [the test inventory](../../testing/test-inventory.v1alpha1.json)
and [its document](../../testing/test-inventory.md), the script's entry in the two
script lists the lifecycle and provider-contract suites read, the implementation and
test references the planned clean-clone claim gains in
[the claim and evidence register](../../testing/claim-evidence-matrix.v1alpha1.json)
with [its document](../../testing/claim-evidence-matrix.md) and the
[regenerated proof dashboard](../dashboard.md), and the entry point the page gains
in [the README](../../../README.md).

Classification: **local static evidence.** Evidence class `local-static`. Every
result below was produced on one Windows host by running commands over files in this
repository, and by running the committed workflow inside temporary sandboxes whose
every external tool was a recording stub. No cluster was selected or contacted, no
model was downloaded or loaded, no runtime or container was started, no image was
built or pulled, and no job ran on the continuous-integration service.

**The workflow has not been run.** Nothing in this record is evidence that the V1
journey completes from a clean clone, that any step's own workflow works, or how
long the journey takes. `a-reviewer-can-reproduce-v1-from-a-clean-clone` stays
`planned` and cites no record. The run, the record of its manual steps and elapsed
time, and any fix it forces are `V1-S5-001-PR2`'s.

## Environment

| Component | Version |
|---|---|
| Windows | 11 Enterprise 10.0.26200 |
| Shell | GNU bash 5.2.26(1)-release (x86_64-pc-msys), Git Bash |
| Python, host | 3.12.6 |
| Python, locked environment | 3.12.12 |
| `uv` | 0.9.16 (a63e5b62e 2025-12-06) |
| `pytest` | 8.4.2 |
| `ruff` | 0.16.4 |
| `mypy` | 2.3.1 (compiled: yes) |
| Git | 2.45.1.windows.1 |
| Branch | `feat/v1-s5-001-clean-clone-automation` |
| Base | `main` at `dcf8f1deda02ddab6a1be0977a6e745ed1d5c739` |

No Docker engine, Helm, Terraform, `kubectl`, or `kind` was invoked. `shellcheck` is
not installed on this host, so the new script was checked with `bash -n` and by the
executed suite, and shellcheck is recorded as **not run** rather than as passing.

## What the change adds

| Fact | Value |
|---|---|
| Checklist steps | 18: 2 checks, 3 preparation steps, 11 real steps, 1 cleanup, 1 check after cleanup |
| Consent flags | 4: `--confirm-downloads`, `--confirm-real-runtime`, `--confirm-real-kubernetes`, and cleanup's `--confirm` (`--confirm-cleanup` on `run`) |
| Workflows the steps run | 9 existing scripts under `scripts/environment/` and 5 existing tool modules, none of them modified, plus the new `tools.clean_clone` |
| Workflow subcommands | `plan`, `prerequisites`, `run`, `note`, `status`, `cleanup` |
| Ledger tool subcommands | `check`, `plan`, `checkout`, `begin`, `resume`, `pending`, `requires`, `record`, `note`, `summary`, `values`, `runtime-image` |
| New test modules | 2, both `architecture-inventory`, both defending no published claim |

## Decisions this change had to make

**"Local cluster creation" is provider verification.** The story's step list names
local cluster creation. [ADR 0011](../../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
D1 forbids any platform workflow to create, enable, reset, or delete a cluster, and
the parent story's own acceptance names "an already available local Kubernetes
cluster". The workflow follows the ADR: the step is `provider-verification`, which
runs the advisory `target-detect.sh` and then `inferops::resolve_target` against the
cluster the operator selected. It runs no kind helper, and the provider-contract
suite, which now reads it as a platform workflow, would refuse one.

**What "not run" may mean.** The brief allows an explicit not-run status for
preparation only. The ledger reads that as: a certification run may never record a
step as not run; a preparation run may, only for a step that needs consent it was
not given, only with a reason, and a preparation ledger never summarises as
`complete`. A real step is never skipped in a certification run, quietly or
otherwise.

**Consent is given, not remembered.** Every existing workflow takes its consent as a
flag on the command line, never from the environment. The workflow keeps that shape:
its flags are passed to each workflow unchanged, and a certification run needs every
forward-path flag on every invocation, including one that resumes. The ledger
records what a run began with and is never read back as consent.

**Cleanup's safety comes from what was absent.** The run refuses a cluster that
already holds `inferops-release`, and records the cluster's namespaces before its
first change. Everything cleanup later removes is inside a namespace that was not
there, so nothing it removes can be another party's; and the survival check compares
against that snapshot rather than inferring survival from not having run a delete.

**Two manual steps became steps.** The C2 certification never pulls its image, so
`runtime-image` pulls the pinned digest. Six release workflows take one `--values`
file and a second silently replaces the first, so `release-images` composes the
committed real values and the two image overlays into one file, layered as `helm -f`
layers them, rather than leaving the merge to whoever runs it.

## Commands, and what they returned

Run from the repository root, in Git Bash.

| Command | Result |
|---|---|
| `python -m tools.clean_clone check` | `OK       18 steps; every workflow they name exists` |
| `bash scripts/environment/clean-clone.sh plan` | the 18 steps, exit 0 |
| `bash scripts/environment/clean-clone.sh prerequisites --prepare-only` | `REFUSED` on this working tree's uncommitted changes, exit 3 -- the check refusing what it exists to refuse |
| `bash -n scripts/environment/clean-clone.sh` | no output, exit 0 |
| `uv run --locked python -m pytest tests/architecture/test_clean_clone_workflow.py tests/architecture/test_clean_clone_ledger.py -q` | `129 passed in 349.73s` -- 46 executed scenarios and 83 ledger and checklist cases |
| `uv run --locked python -m pytest tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py -q` | `372 passed`, with `clean-clone.sh` among the scripts both suites read |
| `uv run --locked python -m pytest tests/testing -q` | `3843 passed, 7 skipped` |
| `uv run --locked python -m pytest tests/security -q` | `843 passed` |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `uv run --locked ruff format --check .` | `458 files already formatted` |
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked python -m mypy` | `Success: no issues found in 259 source files` |
| `uv run --locked python -m pytest -q` | `11818 passed, 37 skipped, 14 deselected in 1085.21s`, on the tree before this record existed and before two test samples were shortened to satisfy the security baseline's personal-path shape; every suite either change touches was rerun above |
| `git diff --check main...HEAD` | no output, exit 0 |

**What the executed suite runs.** Each scenario copies `lib.sh`, `clean-clone.sh`,
the checklist, and the `tools.clean_clone` package byte for byte into a sandbox that
is its own committed git repository, and puts recording stubs for every sibling
workflow and for `kubectl`, `helm`, `kind`, `docker`, `uv`, `terraform`, and `df` on
a closed `PATH` beside the real `git`. Terraform's apply and destroy add and remove
the release namespace in a state file the `kubectl` stub reads back. The provider
throughout is `kind`, whose identity check stubs can satisfy; whether a complete run
certifies anything is provider-specific and is tested on the ledger directly.

The control case is a complete certification run with cleanup: every step in the
checklist's order, every sibling workflow in the order the checklist implies, every
outcome `passed`, the namespaces afterwards exactly the namespaces before, and a
summary of `complete` that certifies nothing because the provider is `kind`. Every
negative result below it would be vacuous without it.

## What the first draft got wrong

Three defects in the workflow's first draft, all fixed before the first commit and
all invisible to `bash -n` and a lint. The second was found by the executed suite;
the first and third were found by reading the draft while writing that suite, and
the suite now holds all three:

1. **A step's failure would not have stopped the step.** The first draft called each
   step as `attempt "${step}" || rc=$?`. Bash ignores `errexit` for every command a
   function runs when the function is called where its status is tested -- inside a
   subshell too -- so a step would have carried on past its first failing command and
   been recorded by whatever its last command returned. A step is now only ever
   called as a plain statement and its status is carried in a variable.
2. **A cluster answering in CRLF read as a changed cluster.** The survival check
   compared the namespace snapshot with `comm` on raw lines; with a carriage return
   on each, every namespace was "gone". Every namespace read now strips carriage
   returns and sorts in the C locale that `comm` needs, and a test drives the whole
   run with a `kubectl` answering in CRLF.
3. **A failed listing would have ended the wait for the namespace to go.** Asked as a
   `while` condition, a `kubectl` that failed would have read exactly as a namespace
   that had gone. The listing is now made as its own statement and a failure fails
   the step.

## A count this change found wrong

`docs/testing/test-inventory.md` opens its table of modules that defend no published
claim with a written count. On `main` it said thirty while the table held thirty-one
rows and the machine-checked sentence in the opening section said thirty-one. This
change adds the thirty-second and thirty-third and corrects the sentence, and records
the drift in the paragraph that already records the earlier ones. The per-layer
count for `architecture-inventory` moves from nineteen to twenty-one; that one is
machine-checked.

## Acceptance criteria

This PR's boundary is the automation. The run is the next PR's.

| Criterion | Status |
|---|---|
| A scripted path from prerequisites through testing, model acquisition, local real inference, scaffolding, provider verification, Terraform, Helm, real Kubernetes inference, telemetry, load and failure, and cleanup | **Met as automation.** All 18 steps exist and run in order against stubs. None has run against a real host, runtime, or cluster in this change |
| Steps resumable where safe, diagnostics actionable | **Met as automation.** A passed resumable step is skipped; checks, the checkout, and the cluster's identity are asked on every invocation; a failure names the step, its exit code, and the two ways forward |
| Required real steps never silently skipped; not-run only for preparation | **Met.** Enforced by the ledger and driven over inputs built to break it |
| Lightweight tests for orchestration and safe cleanup | **Met.** Two modules; the cleanup boundary is driven over a failed listing, a foreign release, another cluster, a pre-existing namespace, a lost namespace, and a node that is not Ready |
| Parent: a clean clone completes the journey | **Not met; `V1-S5-001-PR2`.** Nothing was run |
| Parent: every manual step and the elapsed time recorded | **Mechanism only.** The ledger records every attempt's timing and every manual action given to `note`; no run has produced one |
| Parent: no local uncommitted or configuration state required | **Mechanism only.** A fresh certification run refuses uncommitted changes and previous-run state, and composes every values file from committed files and its own steps' output. Whether a real run needs anything else is what the run will find |
| Parent: cleanup is safe and leaves the operator's cluster | **Mechanism only**, against stubs. Proven on a real cluster only by a run |

## Steps that need explicit authorization

Every one of these is refused without its flag, and none was run by this change:

- `model-acquisition` and `runtime-image`: `--confirm-downloads` -- about 1.71 GiB of
  weights, and the pinned runtime image;
- `local-real-inference`: `--confirm-real-runtime`;
- `provider-verification` through `failure`: `--confirm-real-kubernetes` -- images
  loaded into the operator's cluster, the Terraform prerequisites applied, releases
  installed, real load, and a deliberate pod deletion;
- `cleanup`: `--confirm`, or `--confirm-cleanup` on `run` -- a release uninstall, a
  Terraform destroy that reclaims the model weights in the claim, and this run's
  scaffolds; the workspace model cache only with `--include-model-cache`.

## Limitations

- **Stubs answer every question the suite asks.** It establishes order, consent, the
  ledger's rules, and the cleanup boundary as the script implements them. It cannot
  establish that a real `helm list`, a real Docker Desktop node, or a real Terraform
  state behaves as the stubs do.
- **`docker-desktop`'s identity path is not driven by the executed suite.** Its guard
  in `lib.sh` has its own executed tests; the orchestrator does not branch on the
  provider.
- **The host prerequisites are not exhaustive.** Tool presence, CPython 3.12, bash 5,
  and the ADR 0001 tier's engine figures are checked; tool versions against the
  versions the executed records name are not, and `kubectl`'s skew is left to
  `inferops::resolve_target`.
- **A survival check after a run that never verified a cluster passes vacuously**,
  and says so in its output. Such a run's summary is never `complete`.
- **The executed suite is slow on Windows**, where every orchestrator run starts
  dozens of processes; the expensive runs are made once per module and copied.

## Authorisation

Not required. No command in this record contacts a network beyond the locked
toolchain's own resolution, selects or mutates a cluster, downloads or loads a model
artifact, builds, pulls, or starts a container, or provisions anything that costs
money. The workflow this change adds requires explicit, per-step authorization for
every one of those, and was not given any.

Sensitive values: none. No host name, user account, absolute path, kubeconfig,
credential, or content from outside this repository appears in the change.
