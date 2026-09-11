# V1-S3-010-PR1 validation — the external local-cluster provider contract

Change: [ADR 0011](../../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md),
which moves Kubernetes cluster lifecycle out of InferOps and accepts a provider
contract for consuming an existing `kind` or Docker Desktop cluster; the contract
itself as data and prose; the ownership inventory, ADR 0001, ADR 0004, and the
architecture documents amended to match; and a suite that holds all of it to the
repository. This record is what was run, what it found, and what none of it
supports.

**Evidence class.** Everything asserted here is `local-static`: files read,
compared, formatted, linted, type-checked, and driven through a test suite that
contacts nothing. **No cluster was contacted.** No `kind` cluster was created, no
Docker Desktop context was read, no `terraform apply` ran, and no Helm release was
installed. Every Docker Desktop fact in the contract is quoted from a record made
earlier, and names that record. No claim in
[the matrix](../../testing/claim-test-matrix.md) gains evidence from this change.

**This is a decision and documentation change.** No product behaviour was
modified. The environment scripts, the Terraform configuration, the chart, the
certification descriptors, and every tool under `tools/` are byte-for-byte
unchanged.

## What the change is

**The cluster stops being InferOps's.** Under ADR 0001 the environment scripts
created `inferops-dev` and deleted it, and D5's first rule was that *"the project
creates its own cluster"*. Under ADR 0011 the operator provides an existing
cluster through one of two supported providers, `kind` or `docker-desktop`,
selects it explicitly, and InferOps verifies and consumes it. Nothing on the
platform path creates, enables, resets, reconfigures, or deletes a cluster.

**It is a decision, not an implementation, and every row says which.** The only
identity guard is the `kind` one in `lib.sh`, and it accepts one name,
`inferops-dev`. Nothing can identify a Docker Desktop cluster, so every script
still refuses one. The contract describes that as the correct failure and not as
support.

| | Implemented | Not implemented |
|---|---|---|
| Identity checks | 3, all `kind`, all for the pinned name only | 3 `docker-desktop` checks: 2 specified, 1 undecided |
| Refusals | 4 of 9, for `kind` only, all by `inferops::target_cluster_problem` | 5, owed by `V1-S3-010-PR2` |
| Rules | 5 by a test in the new suite, 1 by the ownership suite, 3 by a `kind`-only shell guard | 3 by nothing, 2 by review alone |
| Capability answers | `kind`: 7 of 7 answered. `docker-desktop`: 4 of 7 observed | `docker-desktop`: image preparation, capacity, and whole-cluster cleanup recorded as unknown |

**Decisions amended and superseded.**

| Record | Change |
|---|---|
| ADR 0001 D2 | Superseded in part. `kind` stays as a supported provider and as the helper's target; that InferOps creates it, and the rejection of Docker Desktop's cluster on ownership grounds, do not |
| ADR 0001 D5 | Superseded in part. *"The project creates its own cluster"* and the requirement to disable Docker Desktop's Kubernetes bind the helper only; every other rule stands |
| ADR 0001 D6 | Superseded in part. Deleting `inferops-dev` is the helper's operation and the operator's choice, not platform cleanup |
| ADR 0004 D3 | Amended. The third prohibition binds the whole platform path, and the inventory gives the cluster to its operator |

None of their sections was rewritten. Each carries a note saying which sentences
ADR 0011 replaces, and the D3 and D4 rows of ADR 0001 — which another suite pins —
are untouched.

**The ownership inventory splits its cluster row.** `local-kubernetes-cluster`
became `kind-cluster`, `implemented` on `kind` evidence, and
`docker-desktop-cluster`, `planned`, because the two have different lifecycles and
different evidence and a single `implemented` row had to average them. Both
belong to a new owner, `cluster-operator`, with a new lifecycle,
`operator-provided`. `node-image-cache` moved with them, as a by-product of
creating a `kind` cluster. `project-kubeconfig` stays with `contributor-host`,
because the `kind` helper is still what writes it.

**The evidence ledger says something easy to miss.** Of the four records that ever
contacted a real cluster, the two `kind` ones are ADR 0001's, and the two Docker
Desktop ones are ADR 0002's runtime feasibility trial and the NetworkPolicy
experiment. So ADR 0001's cluster evidence exists only for `kind`, ADR 0002's
in-cluster runtime evidence exists only for Docker Desktop, and neither certifies
the other. None of the four records was edited.

## What the suite checks

[`tests/architecture/test_local_cluster_provider_contract.py`](../../../tests/architecture/test_local_cluster_provider_contract.py),
211 checks, in seven groups:

1. **Shape.** Identity and version; referenced documents exist; the providers are
   exactly `kind` and `docker-desktop`; the reference provider is one of them; the
   five lifecycle operations are the operator's; identifiers are well formed and
   unique.
2. **Selection and hand-on.** No selection input has a default; `kind` takes a
   cluster name and `docker-desktop` takes none; Terraform and Helm receive
   exactly `kubeconfigPath` and `kubeContext`; a fact is in evidence exactly when
   evidence consumes it; the kubeconfig path never is; no fact is credential
   material.
3. **Identity and refusals.** A check or refusal claimed as implemented names a
   function `lib.sh` really defines; one that is not says who owes it; no provider
   is identified by a context name alone; the refusals are the nine ADR 0011 D6
   names.
4. **Capabilities.** Both providers answer the same seven questions; every answer
   carries one of five evidence labels, and an observation cites a record under
   `docs/proof/` about the provider it was made on. The one permitted crossing —
   `kind`'s NetworkPolicy answer, inferred from the Docker Desktop measurement —
   has to name the provider it was measured on.
5. **Rules.** A rule claiming a test names a function that exists in the module it
   names; a rule claiming a shell guard names a `lib.sh` function; at least one
   rule admits review alone and one admits nothing; and the document's sentence
   counting the rules is recomputed from the data.
6. **The repository.** Every environment script is classified as a platform
   workflow or a `kind` helper; no platform workflow contains a cluster create,
   a cluster delete, a Docker Desktop CLI call, or an invocation of a helper; a
   control case shows the same pattern does catch the helper that does each; the
   Terraform module names no provider; each provider's cluster is owned by
   `cluster-operator` in the inventory.
7. **Documents.** The contract document publishes every identifier the data
   declares and none it lacks; every relative link in it and in ADR 0011 resolves;
   the ADR has the sections this project requires; ADR 0001's header and the
   architecture index point at ADR 0011.

**Four of those checks pin gaps rather than properties**: the Terraform
environment root still validates `kube_context` against `^kind-inferops-`; no
Docker Desktop identity check or refusal is implemented; three Docker Desktop
capabilities are unknown; and `docker-desktop-cluster` is `planned`. Each is true
today and each should stop being true. When one does, its test fails and the
contract has to change in the same commit.

## Files changed

New:

- `docs/architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md`
- `docs/environment/local-cluster-provider-contract.v1alpha1.json` — the contract.
- `docs/environment/local-cluster-provider-contract.md` — its document.
- `tests/architecture/test_local_cluster_provider_contract.py` — 211 checks.
- `docs/proof/architecture/v1-s3-010-pr1-validation.md` — this record.

Changed:

- `docs/architecture/decisions/ADR-0001-local-development-environment.md` — header,
  banner, three status rows, and a note in each of D2, D5, and D6.
- `docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md` — D3
  status row and an amendment note.
- `docs/architecture/resource-ownership.v1alpha1.json`,
  `docs/architecture/resource-ownership.md` — the owner, lifecycle, and row changes
  above.
- `docs/architecture/system-architecture.md` — the cluster bullet, the deployment
  flow, the teardown order, and the B2 diagram and row.
- `docs/architecture/README.md` — the index row, the status count, and the
  partial-status paragraph.
- `docs/environment/local-cluster.md` — a banner: this is now an optional helper's
  runbook.
- `docs/testing/test-inventory.v1alpha1.json`, `docs/testing/test-inventory.md` —
  the new module inventoried, and the counts corrected.
- `README.md`, `CHANGELOG.md`.

No file under `charts/`, `deploy/`, `infra/`, `scripts/`, `src/`, or `tools/` is
touched.

## Validation performed

Every command was run from the repository root on 2026-09-11, in Git's POSIX
shell.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/architecture/test_local_cluster_provider_contract.py -q` | 211 passed |
| `uv run --locked python -m pytest tests/architecture/test_resource_ownership.py tests/architecture/test_cluster_lifecycle_safety.py tests/security/test_security_baseline.py -q` | all passed |
| `uv run --locked python -m pytest -q` | 7,649 passed, 31 skipped, 14 deselected, **2 failed** — both the committed-render checks explained below, which fail identically on `main` |
| `uv run --locked python -m ruff check .` | `All checks passed!` |
| `uv run --locked python -m ruff format --check .` | `337 files already formatted` |
| `uv run --locked python -m mypy` | `Success: no issues found in 185 source files` |
| `git diff --check` | no whitespace errors |
| A scan of the diff and every new file for local paths, account names, workspace names, host cache paths, and private planning identifiers | no match |

### Two things this host does that are not this change

**Which shell runs the suite matters.** Run from Windows PowerShell, `bash`
resolves to the WSL launcher in the system directory, and
`tests/architecture/test_terraform_destroy_guard.py` — which executes the real
wrapper under stubbed tools — fails all 20 of its tests with `execvpe /bin/bash
failed`. Run from Git's POSIX shell, the same module passes 20 of 20. Nothing in
this change touches that module or the script it runs. The results above are from
Git's shell for that reason.

**Two committed-render checks fail, and they fail on `main` too.**
`test_the_committed_render_matches_what_helm_produces[mock]` and `[real]` in
`tests/architecture/test_helm_chart.py` fail on this branch, and they fail
identically on an untouched checkout of `origin/main` at `a043b8b`, with Helm
`v3.19.0`. This change touches nothing the chart renders from.

**The cause is this checkout's line endings, and the committed renders are
correct.** Here `core.autocrlf` is `true`, so the chart's templates and the
committed renders are both CRLF in the working tree while the repository stores
them as LF. With carriage returns ignored, what still differs is only the
`inferops.io/configuration-checksum` annotation — one line in the mock render and
three in the real one — because that checksum hashes rendered template text, and
the text now carries carriage returns. Exporting the chart from `HEAD` with LF
line endings and rendering that produced output **byte-identical** to both
committed renders. So this is a Windows-checkout artefact rather than a stale
render, it is not fixed here, and the fix belongs to whoever decides whether the
repository should pin line endings for the chart with a `.gitattributes` rule.

## What was not done

- **No cluster was contacted**, on either provider. The Docker Desktop
  verification record the parent story requires belongs to the implementation.
- **No script was changed.** The kind-only guard, the Terraform environment
  root's `kind-inferops-` validation, the `kind load` image steps, and the
  certification descriptors' pinned cluster name are all as they were.
- **The two security records worded against the old design were not restated.**
  The control `refuse-to-act-on-a-cluster-this-project-did-not-create` and exception
  `EX-02` describe the guard that still runs. They are restated with the guard, so
  that the baseline never describes a guard that does not exist.
- **Operational documents were not reconciled.** The troubleshooting guide, the
  prerequisite guide, the certification procedures, and the Helm lifecycle
  documents still name `cluster-up.sh` and `cluster-down.sh` as the way the cluster
  comes and goes. They describe what the scripts do today, which this change did
  not alter, and reconciling them belongs to the re-certification that changes
  what is run.

## Limitations

- **The suite cannot read prose.** It checks identifiers, statuses, sources, and
  the files a row names. A description that has drifted from the behaviour it
  describes will not fail a check.
- **The lifecycle check is a static read.** A platform workflow that deleted a
  cluster by a route the pattern does not describe — a command assembled from
  variables, say — would pass. The control case shows the pattern catches the
  forms this repository uses, and no more.
- **The evidence ledger is not proven complete.** It lists the four records known
  to have contacted a real cluster. Nothing checks that a fifth does not exist.
- **Every Docker Desktop fact is dated.** They come from records made on
  2026-08-24 and 2026-09-06, and Docker Desktop's version follows its release.

## Acceptance criteria

This PR's boundary:

| Criterion | Status |
|---|---|
| No accepted architecture document requires InferOps to own cluster lifecycle | **Met.** ADR 0001 D2, D5, and D6 are superseded in part, ADR 0004 D3 amended, and the ownership inventory, system architecture, and index say the cluster is the operator's. Operational documents are not accepted architecture and are listed above as not yet reconciled |
| The provider contract, explicit selection, normalised facts, safety and refusal semantics, and evidence labelling are unambiguous | **Met, with one question deliberately left open.** Everything is data and checked. How a Docker Desktop cluster would be bound to the local engine is **undecided**, and the record is accepted in part for that reason |
| Terraform and Helm ownership remains disjoint | **Met.** Asserted by the ownership suite and named as a rule in the contract |
| Existing history and evidence are preserved and accurately labelled | **Met.** No proof record edited; four real-cluster records labelled by provider in the ledger |
| Docker Desktop and `kind` differences are not hidden behind false equivalence | **Met.** Seven questions answered per provider with evidence labels, three Docker Desktop unknowns recorded as unknown, and separate `implemented` and `planned` inventory rows |

Parent story `V1-S3-010`: the ADR and ownership amendment and the machine-checked
contract are delivered here. Provider verification, the Docker Desktop
verification record, `kind` verification evidence, and negative refusal records
belong to `V1-S3-010-PR2`, and none of them is claimed.
