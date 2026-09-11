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
217 checks, in seven groups:

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
   a cluster delete, a Docker Desktop CLI call, or an invocation of a helper.
   Control cases show the pattern does catch each form — against the helper
   scripts that really contain one, and against literal lines for the forms no
   committed script uses, such as a Docker Desktop CLI call — and negative controls
   show it ignores a refusal message that names the helper and a `kind load`. The
   Terraform module names no provider; each provider's cluster is owned by
   `cluster-operator` in the inventory.
7. **Documents.** The contract document publishes every identifier the data
   declares and none it lacks; every relative link in it and in ADR 0011 resolves;
   the ADR has the sections this project requires; ADR 0001's header and the
   architecture index point at ADR 0011.

**Five of those checks pin four gaps rather than properties**: the Terraform
environment root still validates `kube_context` against `^kind-inferops-`; no
Docker Desktop identity check is implemented, and no refusal is either — one test
each; three Docker Desktop capabilities are unknown; and
`docker-desktop-cluster` is `planned`. Each is true
today and each should stop being true. When one does, its test fails and the
contract has to change in the same commit.

## Files changed

New:

- `docs/architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md`
- `docs/environment/local-cluster-provider-contract.v1alpha1.json` — the contract.
- `docs/environment/local-cluster-provider-contract.md` — its document.
- `tests/architecture/test_local_cluster_provider_contract.py` — 217 checks.
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
| `uv run --locked python -m pytest tests/architecture/test_local_cluster_provider_contract.py -q` | 217 passed |
| `uv run --locked python -m pytest tests/architecture/test_resource_ownership.py tests/architecture/test_cluster_lifecycle_safety.py tests/security/test_security_baseline.py -q` | all passed |
| `uv run --locked python -m pytest -q` | 7,655 passed, 31 skipped, 14 deselected, **2 failed** — both the committed-render checks explained below, which fail identically on `main` |
| `uv run --locked python -m ruff check .` | `All checks passed!` |
| `uv run --locked python -m ruff format --check .` | `338 files already formatted` — 185 Python files and 153 Markdown files, which ruff `0.16.4` also formats. The first commit's message says 337 because it was measured before this record existed |
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
- **The security records worded against the old design were not restated.** Four
  accepted security documents describe the cluster guard in terms of a cluster this
  project created: threat `T-13`, *"a platform action reaches a cluster this
  project did not create"*, in `docs/security/threat-model.md` and in
  `docs/security/security-baseline.v1alpha1.json`, which also carries the same
  premise in an asset's worst case; the control
  `refuse-to-act-on-a-cluster-this-project-did-not-create` in that baseline and in
  `docs/security/control-matrix.md`; and exception `EX-02` in
  `docs/security/deferred-risks.md`, which names a second *kind* cluster. Under
  ADR 0011 no cluster is ever this project's, so their premise has become the
  universal case rather than the exception. What they describe is still what runs,
  because the guard is unchanged, so they are restated with the guard — where the
  new threat wording, control identifier, and exception can be written against a
  check that exists. They are accepted architecture, unlike the runbooks below,
  which is why the first answer under the acceptance criteria is qualified.
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

## What two independent reviews found

Both ran against the first commit of this change, and both are reflected above
rather than summarised and set aside.

The first re-derived every function's behaviour, every quoted fact, every count,
and every cross-reference from its source — the four guard functions in `lib.sh`,
`preflight.sh`'s skew comparison, all four proof records, and the rule, refusal,
capability, module, and decision-status counts — and found **one MEDIUM**:

| | Finding | Fix |
|---|---|---|
| MEDIUM | The first acceptance answer said no accepted architecture record still made the cluster InferOps's, and this record said "two security records" were left unrestated without naming them. Four accepted security documents — the threat model's `T-13`, the baseline's control and worst case, the control matrix, and `EX-02` — still frame the guard around a cluster this project created, and the architecture index lists the security baseline as an architecture document | All four named, here and in ADR 0011's security considerations and `R7`, and the acceptance answer qualified |

The second checked the change against the decisions and acceptance criteria it
was written for, and for scope, test quality, security, and privacy, and found
**two MEDIUM**:

| | Finding | Fix |
|---|---|---|
| MEDIUM | The acceptance table read as a transcription of a requirements list rather than an assessment in this record's own voice, where every other section restates the same ideas in its own words | Rewritten as five questions and answers |
| MEDIUM | The lifecycle pattern's `docker desktop` alternative had no control case. No committed script contains one, so nothing showed it could ever match | Four literal lines now show each alternative matches, and two negative controls show that a refusal message naming the helper, and a `kind load`, do not |

**What the first draft also got wrong**, found while fixing those. It said four
checks pinned gaps; it is five checks pinning four gaps, because the Docker Desktop
identity and refusal gaps are pinned by one test each. It said the suite had 211
checks; the control cases above made it 217. And ADR 0011's context attributed a
statement about the NetworkPolicy experiment to a review, when the experiment's own
record makes it first.

## Acceptance criteria

Five questions this change had to be able to answer, and where each stands:

| Question | Answer |
|---|---|
| Does any accepted architecture record still make the cluster InferOps's to create or delete? | **No decision or ownership record does. The security baseline still reads as though one did.** ADR 0001's D2, D5, and D6 carry superseded-in-part notes, ADR 0004's D3 is amended, and the inventory, the system architecture, and the index all give the cluster to its operator. The four security documents named above still frame a threat, a control, and an exception around a cluster this project created; none of them requires InferOps to own a cluster, and none has been restated yet. The operational runbooks still describe the helper, because the helper still does what they say |
| Can a reader tell from the contract alone how a cluster is chosen, identified, handed on, refused, and labelled? | **Yes, with one question left open on purpose.** Every part is committed data with a check behind it. How a Docker Desktop cluster would be bound to the local engine is **undecided**, which is why ADR 0011 is accepted in part |
| Did the boundary inside the cluster move? | **No.** Terraform's set and Helm's set are still disjoint, asserted by the ownership suite and carried into the contract as a rule |
| Was anything historical rewritten? | **No.** No proof record was edited, and the four that contacted a real cluster are labelled by provider in the ledger instead |
| Are the two providers presented as interchangeable? | **No.** Each of seven questions is answered per provider with how the answer is known; three Docker Desktop answers are recorded as unknown; and the inventory gives the two clusters different statuses |

Parent story `V1-S3-010`: the ADR and ownership amendment and the machine-checked
contract are delivered here. Provider verification, the Docker Desktop
verification record, `kind` verification evidence, and negative refusal records
belong to `V1-S3-010-PR2`, and none of them is claimed.
