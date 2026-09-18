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
and [its document](../../testing/test-inventory.md), the script's entry in the three
script lists the lifecycle and provider-contract suites read -- `ENTRY_POINTS`,
`PLATFORM_WORKFLOWS`, and `MUTATING_PLATFORM_WORKFLOWS` -- the implementation and
test references the planned clean-clone claim gains in
[the claim and evidence register](../../testing/claim-evidence-matrix.v1alpha1.json)
with [its document](../../testing/claim-evidence-matrix.md) and the
[regenerated proof dashboard](../dashboard.md), and the entry point the page gains
in [the README](../../../README.md).

Classification: **local static evidence.** Evidence class `local-static`. Every
result below was produced on one Windows host by running commands over files in this
repository, and by running the committed workflow inside temporary sandboxes in
which every sibling workflow and every external tool but `git`, `bash`'s own
utilities, and the interpreter the ledger tool runs on was a recording stub. No
cluster was selected or contacted, no model was downloaded or loaded, no runtime
or container was started, no image was built or pulled, and no job ran on the
continuous-integration service.

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
| Workflows the steps run | 9 existing scripts under `scripts/environment/` (and `lib.sh`, which it sources), 4 existing tool modules it runs and 1 it imports for the runtime image's reference, none of them modified, plus the new `tools.clean_clone` |
| Workflow subcommands | `plan`, `prerequisites`, `run`, `note`, `status`, `cleanup` |
| Ledger tool subcommands | `check`, `plan`, `checkout`, `begin`, `resume`, `pending`, `cleanable`, `requires`, `record`, `note`, `summary`, `values`, `runtime-image` |
| New test modules | 2, both `architecture-inventory`, both defending no published claim |

## Decisions this change had to make

**"Local cluster creation" is provider verification.** The story this change
belongs to lists local cluster creation among the journey's steps.
[ADR 0011](../../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
D1 forbids any platform workflow to create, enable, reset, or delete a cluster, and
the story's acceptance asks for verification against a local cluster that is
already available. The workflow follows the ADR: the step is
`provider-verification`, which runs the advisory `target-detect.sh` and then `inferops::resolve_target` against the
cluster the operator selected. It runs no kind helper, and the provider-contract
suite, which now reads it as a platform workflow, would refuse one.

**What "not run" may mean.** The story allows an explicit not-run status for
preparation only. The ledger reads that as: a certification run may never record a
step as not run; a preparation run may, only for a step that needs consent it was
not given, only with a reason, and a preparation ledger never summarises as
`complete`. A real step is never skipped in a certification run, quietly or
otherwise.

**Consent is given, not remembered.** Every existing workflow takes its consent as a
flag on the command line, never from the environment. The workflow keeps that shape:
a workflow that takes a consent flag is handed its own, a step whose consent was not
given is never run, and a certification run needs every forward-path flag on every
invocation, including one that resumes. `--confirm-downloads` is the workflow's own,
because neither step it covers belongs to a workflow that takes one. The ledger
records what a run began with and is never read back as consent.

**Cleanup's safety comes from what was absent.** The run refuses a cluster that
already holds `inferops-release`, and records the cluster's namespaces -- and the
UID of its `kube-system` namespace, which a cluster reset or recreated under the
same name does not keep -- before its first change. Everything cleanup later removes is inside a namespace that was not
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
| `uv run --locked python -m pytest tests/architecture/test_clean_clone_workflow.py -q` | `51 passed in 466.54s` on the final tree; the first commit's 46 read `129 passed in 349.73s` together with its 83 ledger cases |
| `uv run --locked python -m pytest tests/architecture/test_clean_clone_ledger.py -q` | `88 passed` on the final tree |
| `uv run --locked python -m pytest tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py -q` | `372 passed`, with `clean-clone.sh` among the scripts both suites read |
| `uv run --locked python -m pytest tests/testing tests/security tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py tests/architecture/test_clean_clone_ledger.py -q` | `5147 passed, 7 skipped` on the final tree; on the first commit `tests/testing` read `3843 passed, 7 skipped` and `tests/security` `843 passed` |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `uv run --locked ruff format --check .` | `459 files already formatted` on the final tree |
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked python -m mypy` | `Success: no issues found in 259 source files` |
| `uv run --locked python -m pytest -q` | `11830 passed, 37 skipped, 14 deselected in 1132.15s` on the final tree. The same command on the first commit's tree, before this record existed, read `11818 passed, 37 skipped, 14 deselected in 1085.21s` |
| `git diff --check main...HEAD` | no output, exit 0 |

**What the executed suite runs.** Each scenario copies `lib.sh`, `clean-clone.sh`,
the checklist, and the `tools.clean_clone` package byte for byte into a sandbox that
is its own committed git repository, and puts recording stubs for every sibling
workflow and for `kubectl`, `helm`, `kind`, `docker`, `uv`, `terraform`, and `df` on
a closed `PATH` beside the real `git`; `python` is a stub that hands only the ledger
tool and version checks to the real interpreter. Terraform's apply and destroy add and remove
the release namespace in a state file the `kubectl` stub reads back. The provider
throughout is `kind`, whose identity check stubs can satisfy. The script branches on
the provider in two places -- `kind` is a required tool only when it is selected, and
only `kind` passes a cluster name to the ledger -- and the `docker-desktop` side of
both is not executed by the suite. Whether a complete run certifies anything is
provider-specific and is tested on the ledger directly.

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

## What an independent review found after the first commit

Two reviews ran against the first commit: one read the script, the tool, and the
tests for defects; the other held every document in the change to the code and to
the repository. Neither found a way the workflow could create or delete a cluster,
reach one before `inferops::resolve_target`, or remove something the run did not
create, and every count in the first draft recomputed correctly. What they did find
is below, and everything in it is corrected in the second commit.

### One bug, and five gaps in guarantees the change claims

| Found | What was wrong | Now |
|---|---|---|
| A standalone `cleanup --include-model-cache` | It ran `python -m tools.model_acquisition clean` with whichever `python` was first on the operator's `PATH`. That tool imports the platform package, which only the locked environment carries, so on a normal host it would have failed to import. The executed suite could not see it: its stub `python` answered either way | Cleanup puts the locked environment first before removing the cache, and a test gives `.venv` an interpreter of its own and asserts it is the one that ran |
| The cluster-identity comparison | It compared the provider and the cluster name. Docker Desktop's cluster is always called `docker-desktop`, so a cluster reset or recreated between verification and cleanup would have passed, and been cleaned up and judged against a snapshot of a different cluster | The snapshot records the UID of the cluster's `kube-system` namespace, every later verification compares it, and a test refuses cleanup on a cluster whose UID changed |
| `run --restart` | It moved the ledger aside and left the previous run's cluster snapshot in place, so a restarted run's provider verification took the "resumed" path: no refusal of an existing release namespace and no new snapshot, and survival judged against the old run's cluster. Nothing tested `--restart` | Both snapshot files are moved aside beside the old ledger, and a test asserts it |
| A second cleanup, and a survival check out of order | Cleanup and the survival check skip the forward path's ordering so that they can follow a failure. Nothing then stopped a second cleanup after one that passed, or a survival check recorded with no cleanup in front of it -- which would say a cluster survived a teardown that never happened | The ledger refuses both; the workflow refuses a second cleanup before touching anything; five ledger tests and one executed test drive them |
| A ledger that refuses a record | A step's record was written as a plain statement under `errexit`. If the ledger refused it -- a wall clock stepped backwards during a long step is the realistic case -- the orchestrator ended before saying what the step itself had done | The refusal is caught, the step's own exit status is reported beside it, and the run stops. Not exercised by a test |
| A host with no `python` | The checkout check that opens a run is itself a python command, so such a host was told its checkout could not stand for a clean clone | The script asks for `python` before anything else, and a test runs it on a `PATH` without one where the host allows that to be staged |

### What the first draft's prose said, and what was true

- **"It is an orchestrator and nothing more. Every step runs a workflow that already
  exists."** Six steps carry logic this change wrote -- the host prerequisites, the
  runtime image pull, the namespace snapshot, the values merge, the survival check,
  and cleanup, whose release uninstall is a mutation this script makes directly. The
  page, the script's header, and the CHANGELOG now name them.
- **"The default-checks lane", "the four commands the continuous-integration lane
  runs, in the order it runs them."** The lane is eleven gates; the step runs the
  commands of two of them, `code-quality` and `default-lane-tests`, which run in
  parallel on the service.
- **"The defect `V1-S4-006-PR1` published twice."** That change's first attempt
  produced two negative intervals and was never committed; nothing negative was
  published.
- **"The load and failure experiments are the longest steps."** Nothing had timed
  the journey. The page now cites the two measured figures there are -- 16 min 56 s
  for the one recorded load run, and this record's 1 085 s for the default-lane
  suite -- as scale only.
- **"The workflow reads this file for nothing but its step order."** It reads each
  step's consent, whether it resumes, and whether it may run after a failure.
- **"The orchestrator does not branch on the provider."** It branches twice, and only
  the `kind` side of each is executed by the suite.
- **"A preparation ledger is always `preparation-only`, whatever it holds."** A
  preparation ledger holding a failed step summarises as `failed`.
- **"Every external tool was a recording stub"**, and the stub lists that left out
  `python`. The real `git`, `bash`'s utilities, and the interpreter the ledger tool
  runs on were real; `python` itself was stubbed for everything else.
- **"The two script lists"** that the new script joined. It joined three, across two
  suites.
- **"Three of the workflows it runs need bash 5."** Two of the workflows it runs use
  `EPOCHREALTIME`; the third that does, `unready-model-recovery.sh`, is not one of
  them.
- **The claim register row gave the new modules no gate.** Both run in
  `default-lane-tests`, and every other row with default-lane modules names it; the
  row now does too.
- Smaller corrections: the host-prerequisites title said "every tool" and did not
  check `sha256sum`, which the model seed build needs (it now does); the page's
  table of written paths missed the merged values file, `.venv/`, the target
  kubeconfig, Terraform's state, and moved-aside ledgers; it presented
  `--include-model-cache` as available to `run`, which refuses it; it linked a
  troubleshooting command that names the `kind` helper's kubeconfig without saying
  a `docker-desktop` operator must name the verified target's instead; and the
  checklist's `$id` did not follow the `https://inferops.io/<area>/` form every
  other descriptor uses.

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
  in `lib.sh` has its own executed tests. The orchestrator's two provider branches --
  the `kind` tool requirement and the cluster name passed to the ledger -- are
  executed on their `kind` side only.
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
