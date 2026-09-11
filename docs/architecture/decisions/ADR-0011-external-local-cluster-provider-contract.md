# ADR 0011: Local Kubernetes clusters are external, explicitly selected provider targets

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-09-11 |
| Date accepted | 2026-09-11, for every decision except the Docker Desktop half of D5 |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | ADR 0001 D2, D5, and D6, in part; amends ADR 0004 D3 |
| Superseded by | None |

> [!IMPORTANT]
> This record moves the Kubernetes cluster out of InferOps's ownership. InferOps
> now consumes an existing cluster that the operator created, through one of two
> supported providers, `kind` and `docker-desktop`, selected explicitly. It never
> creates, enables, resets, reconfigures, or deletes one.
>
> **It is a decision, not an implementation.** No script changed with it. The only
> identity guard that exists is the `kind` one, for the one cluster name the
> environment scripts pin, and nothing can yet identify a Docker Desktop cluster —
> so every script still refuses one. That refusal is the correct behaviour until a
> positive check exists, and this record does not describe it as support.
>
> **It rewrites no history.** ADR 0001's `kind` lifecycle was executed and its
> evidence stands for what it measured. What changes is that creating and deleting
> that cluster stops being something the platform does.
>
> The contract itself is committed as data,
> [`local-cluster-provider-contract.v1alpha1.json`](../../environment/local-cluster-provider-contract.v1alpha1.json),
> explained in [the provider contract](../../environment/local-cluster-provider-contract.md),
> and checked by `tests/architecture/test_local_cluster_provider_contract.py`.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Cluster lifecycle is outside InferOps | **Accepted** | The ownership inventory gives every cluster to its operator, and a test reads every platform workflow for a cluster create, delete, or helper invocation |
| D2 | The supported providers are exactly `kind` and `docker-desktop` | **Accepted** as scope | A test on the contract data. Supported means the contract covers it; only `kind` has a guard |
| D3 | Selection is explicit; detection is advisory; every mutation re-verifies | **Accepted** as a rule | Nothing implements selection. The re-verification half exists for `kind` |
| D4 | Verification hands on normalised target facts; Terraform and Helm receive an address and never a provider | **Accepted** | The data, checked. The prerequisite module names no provider; the environment root's `kind` pin is a recorded gap |
| D5 | Each provider has a positive identity check | **Accepted for `kind`**, on ADR 0001's executed evidence. **For `docker-desktop` the requirements are accepted and the engine-binding mechanism is not decided** | See D5 |
| D6 | Refusals happen before any mutation, for nine named cases | **Accepted** | Four of the nine are implemented, for `kind` only |
| D7 | Access is project-scoped: one kubeconfig, one verified context | **Accepted** | Implemented for `kind` by the wrappers ADR 0001 D5 describes |
| D8 | Provider differences are recorded per provider, with how each answer is known | **Accepted** | The data, checked |
| D9 | `docker-desktop` is the reference provider for the current re-certification | **Accepted** as a choice of host | Review alone |
| D10 | Every runtime record names its provider; no provider certifies another | **Accepted** as a rule | The existing records are labelled; nothing writes the field yet |
| D11 | The `kind` helper scripts are optional, not the platform path | **Accepted** | The same test as D1 |

## Context

ADR 0001 selected `kind` and made the cluster a named, project-owned object:
`scripts/environment/cluster-up.sh` created `inferops-dev`, `cluster-down.sh`
deleted it, and ADR 0001 D5's first rule was that *"the project creates its own
cluster"*. That was executed and evidenced twice, and ADR 0004 then drew every
ownership boundary inside a cluster whose creator was this repository's scripts.

Three things have changed the cost of that arrangement since.

**The reference host no longer has the `kind` CLI.** The Sprint 3 troubleshooting
validation recorded `cluster-verify.sh` and `verify-clean.sh` refusing with
`'kind' is not on PATH`, and every other environment script needs `kind` before it
does anything.

**Docker Desktop's Kubernetes has already produced two of this project's four
real-cluster records.** ADR 0002's runtime feasibility trial ran in it — *"not in
`inferops-dev`"*, as that record says before anything else — and so did the
NetworkPolicy enforcement experiment. Neither could be counted as evidence for the
accepted environment, and the Sprint 3 completion review said so about the
second.

**ADR 0001's objection to Docker Desktop's cluster was ownership.** Its D2 table
rejected it because *"the cluster is a machine-global singleton owned by the
desktop application, not an object this project may create, name, or delete"*.
That was the right objection to a design in which InferOps owns the cluster. It is
not an objection to a design in which InferOps owns no cluster at all — which is
the design this record adopts. The other facts in that row stay true and become
limitations: the version is bound to the desktop release and cannot be pinned, and
the cluster is shared by anything else that uses it.

## Decision criteria

In order:

1. **Nothing InferOps runs can destroy a cluster.** A cluster is the one object on
   an operator's machine whose loss takes everything else with it.
2. **The wrong cluster is refused, not guessed.** An operator's kubeconfig
   routinely holds contexts for clusters that matter more than a local one.
3. **Differences between providers are visible.** Two providers that share a
   network plugin and a node shape invite the assumption that they share
   everything.
4. **Evidence stays attributable.** A record must say where it ran.
5. **The ownership boundary inside the cluster does not move.** Terraform and
   Helm keep what ADR 0004 gave them.

## D1 — Cluster lifecycle is outside InferOps

**Accepted.**

No platform workflow creates, enables, resets, reconfigures, or deletes a
Kubernetes cluster, or runs a helper that does. The operator performs all five
with the provider's own tooling. In the ownership inventory the cluster now
belongs to a new owner, `cluster-operator`, with a new lifecycle,
`operator-provided`, and no InferOps tool or script owns one.

| Alternative | Assessment |
|---|---|
| **The operator provides the cluster; InferOps verifies and consumes it** | **Selected.** Criterion 1 holds by construction rather than by a guard, and it is the only arrangement under which Docker Desktop's cluster can be used at all |
| InferOps keeps owning a `kind` cluster, and adds Docker Desktop as a second owned target | Docker Desktop's cluster cannot be owned: it is created, reset, and removed by the desktop application. Owning one provider and borrowing the other would make ownership a per-provider accident |
| InferOps owns lifecycle for `kind` only, and the operator owns Docker Desktop | Two answers to "who may delete this cluster" depending on which one it is. That is the per-provider ambiguity ADR 0004 exists to prevent |

## D2 — The supported providers are exactly `kind` and `docker-desktop`

**Accepted as scope.**

A third provider is a decision record, not a new row: each provider brings its own
identity check, and a provider without one is exactly the unidentified target D6
refuses. *Supported* means the contract covers the provider. It does not mean a
guard exists: see D5.

## D3 — Selection is explicit; detection is advisory; every mutation re-verifies

**Accepted as a rule. Nothing implements selection.**

Every mutating workflow is given the provider, and for `kind` the cluster name, by
the operator. **No input has a default**: a default is a selection somebody else
made. A workflow may report which providers it can see and never picks one.

Every mutating workflow re-runs the selected provider's identity checks
immediately before its first mutation. A target recorded by an earlier run is
compared against and never trusted, because the cluster a context points at can
change between two commands. That half exists for `kind` today: every mutating
script calls `inferops::assert_target_cluster` before it changes anything.

## D4 — Normalised target facts, and an address rather than a provider

**Accepted.**

Verification produces one record of fourteen facts, and each consumer receives
only the facts naming it. **Terraform and Helm receive the kubeconfig path and the
context, and nothing else.** A module that knows which provider it is on starts
accreting provider-specific lifecycle logic, which is the ownership D1 removes.

The prerequisite module already complies and a test keeps it that way. The
environment root does not: `infra/terraform/environments/local/variables.tf`
validates `kube_context` against `^kind-inferops-`. That is recorded as a gap
rather than fixed here, because fixing it is the provider-aware implementation,
and a test pins it so that whoever closes it has to update the contract too.

The kubeconfig path never enters a record. Neither do the API server's address,
any credential, the operator's own kubeconfig, or any context but the verified
one.

## D5 — Each provider has a positive identity check

**Accepted for `kind`. For `docker-desktop` the requirements are accepted and the
engine-binding mechanism is not decided.**

For `kind` the check is the one ADR 0001 D5 describes: every node the API server
reports must be a container on the local engine that `kind` labelled for the
selected cluster. It was attacked with a real foreign cluster wearing this
project's context name and refused it. Its limit is unchanged: it accepts one
name, `inferops-dev`, and accepting a selected name is implementation work.

For `docker-desktop` three checks are required:

1. the operator's kubeconfig holds a `docker-desktop` context — necessary and
   never sufficient;
2. every node the API server reports matches a Docker Desktop node shape this
   project has observed and recorded — today one, a single `desktop-control-plane`
   node running `kindest/kindnetd` — and any other shape is refused until it is
   observed;
3. the nodes are bound to this machine's Docker Desktop virtual machine, the way
   `kind`'s check binds nodes to labelled containers.

**The third is the part that is not decided**, because whether Docker Desktop's
nodes are observable from the local engine has not been established. If no
mechanism can be established, the Docker Desktop guard is a name-and-shape check,
weaker than `kind`'s, and it must be recorded as a security exception beside
`EX-02` rather than presented as equal. This is why the record is accepted in part
rather than accepted: the check that would make the two providers' guards
comparable is a runtime question, and no runtime has answered it.

## D6 — Refusals

**Accepted.**

Nine cases refuse before any Terraform, Helm, or kubectl mutation and before any
image is loaded: `no-provider-selected`, `unsupported-provider`,
`ambiguous-target`, `target-missing`, `target-unreachable`, `unexpected-context`,
`provider-mismatch`, `capability-unknown-or-insufficient`, and
`client-outside-skew`.

Four are implemented, for `kind` only, by `inferops::target_cluster_problem`.
`provider-mismatch` holds in one direction: a Docker Desktop cluster reached where
`kind` is expected is refused, because its node carries no `kind` label.
`client-outside-skew` is not implemented even for `kind`, in the sense this
contract means: `preflight.sh` compares the client with the minor version the
pinned node image should produce, not with the version the selected cluster's
server reports.

## D7 — Project-scoped access

**Accepted.**

Every kubectl and helm invocation names a project-scoped kubeconfig holding exactly
the verified context, so neither `KUBECONFIG` nor the operator's current context
can redirect it. Reading the operator's own kubeconfig to detect a provider is
allowed; acting through it is not.

For `kind` this is `inferops::kubectl` and `inferops::helm` over the file the helper
writes. For `docker-desktop` the file would be written by verification and would
hold a copy of Docker Desktop's client credential, which puts it under the same
obligations as the `kind` one: ignored by version control, never quoted in a
record.

## D8 — Differences are recorded per provider

**Accepted.**

Seven capability questions — image preparation, default storage, NetworkPolicy
enforcement, capacity, whole-cluster cleanup, Kubernetes version, and node
topology — are answered separately for each provider, each labelled *observed*,
*inferred*, *implemented but not executed*, *documented*, or *unknown*. An unknown
is never borrowed from the other provider.

Three Docker Desktop answers are unknown today: whether an engine-built image is
visible without a load step, what share of the virtual machine the node may use,
and what a reset removes. The first two have to be established before the
re-certification can rely on them; the third is not needed by any V1 workflow and
is recorded so that `kind`'s answer is never read across.

## D9 — The reference provider

**Accepted as a choice of host.**

`docker-desktop` is the provider the current re-certification runs on, because the
reference host has it and does not have the `kind` CLI, and because two of the four
real-cluster records already ran there. **That is not a claim that Docker Desktop
is better, closer to production, or equivalent to `kind`.** `kind` remains
supported, and whatever is not executed on it will be recorded as not executed.

## D10 — Evidence identity

**Accepted as a rule. Nothing writes the field yet.**

Every runtime record states the provider and cluster it ran on, and a result on one
provider is never presented as a result on the other. The four existing
real-cluster records are labelled in the contract's evidence ledger without being
edited. Read across, they say: **ADR 0001's cluster evidence exists only for
`kind`, and ADR 0002's in-cluster runtime evidence exists only for Docker
Desktop.** No InferOps release has been installed on either.

## D11 — The `kind` helper is optional

**Accepted.**

`cluster-up.sh`, `cluster-down.sh`, `cluster-verify.sh`, `verify-clean.sh`,
`smoke.sh`, and `proof.sh` stay. They are a convenient way for an operator to
create a `kind` cluster to the pinned definition, and their evidence is valid for
what it measured. No platform workflow calls any of them, which the D1 test
checks.

## What this supersedes, precisely

In ADR 0001, and nothing else there:

- **D2**, in part. `kind` stays, as one of two supported providers and as the
  helper's target. The premise that InferOps creates it does not, and neither does
  the rejection of Docker Desktop's cluster on ownership grounds.
- **D5**, in part. *"The project creates its own cluster"* and the requirement to
  disable Docker Desktop's Kubernetes become rules for the helper only. The
  project-scoped kubeconfig, the namespace prefix, the project label, and the
  identity guard stand, and are carried into D5 and D7 here.
- **D6**, in part. Full teardown by deleting `inferops-dev` becomes the helper's
  operation and the operator's choice. It is no longer platform cleanup. The
  prohibitions on whole-engine pruning and on deleting contexts the project did
  not create stand.

In ADR 0004, **D3** is amended rather than superseded: its third prohibition,
*"neither tool creates, reconfigures, or deletes a cluster"*, now binds InferOps's
platform path as a whole, and the inventory it accepts gives the cluster to its
operator.

## Consequences

- **Nothing in InferOps can delete the cluster it runs in.** The helper still can,
  when an operator runs it deliberately.
- **Docker Desktop becomes usable, and not yet.** The design admits it; the guard
  that would let a workflow act on it does not exist, so every workflow still
  refuses it.
- **Two providers are two sets of evidence.** Anything certified on
  `docker-desktop` is certified there. Whatever `kind` runs will be recorded as
  its own, and whatever it does not run will be recorded as not run.
- **The Docker Desktop guard may end up weaker than `kind`'s.** If D5's third check
  cannot be established, that becomes a named exception rather than an unstated
  difference.
- **The Kubernetes version stops being pinnable on the reference provider.** The
  `kind` node image is pinned by digest; Docker Desktop's version is whatever its
  release ships, so a record made on it is dated to a release rather than to a pin.
- **Three documents change shape.** The ownership inventory gains an owner and a
  lifecycle and splits its cluster row by provider; the system architecture's
  deployment flow starts from a provided cluster; and the `kind` runbook becomes a
  helper's runbook.

## Compatibility impact

No published contract, schema, or API changes. The ownership inventory is
repository data rather than a contract, but it is read by tests, and one of its
identifiers is removed: `local-kubernetes-cluster` becomes `kind-cluster` and
`docker-desktop-cluster`, because the two have different lifecycles and different
evidence and a single row had to average them. No script, chart, descriptor, or
Terraform file changes.

## Security considerations

This record asserts no new security property, and the one it most affects is
unchanged in behaviour.

- **Trust boundary B2 is still enforced by the `kind` guard alone.** A Docker
  Desktop target is refused, which fails closed. Nothing about B2 improves until a
  Docker Desktop check exists, and D5 says it may be weaker when it does.
- **Two security records are now worded against a design this record replaces.**
  The control `refuse-to-act-on-a-cluster-this-project-did-not-create` and exception
  `EX-02` are stated in terms of a cluster this project created. The guard behind
  them checks identity, not provenance, and is unchanged here, so what they
  describe is still what runs. They are restated when the guard changes, not
  before, so that the security baseline never describes a guard that does not exist.
- **The Docker Desktop kubeconfig would be a credential.** D7 puts it under the
  same rules as the `kind` one.
- **Detection reads the operator's kubeconfig.** It may list contexts; it may not
  act through one, and it may not record any but the verified one.

## Evidence

`local-static`, on 2026-09-11. **No cluster was contacted.** Every Docker Desktop
fact in the contract is quoted from a record made earlier, and the contract says
which. The full record is
[the V1-S3-010-PR1 change validation](../../proof/architecture/v1-s3-010-pr1-validation.md).

What the suite establishes: that the contract, its document, the ownership
inventory, the guard functions in `lib.sh`, and the Terraform module agree; that no
platform workflow creates or deletes a cluster; and that every implemented claim
names something that exists. What it establishes about whether any cluster is
correctly identified or refused: **nothing**. That needs a cluster.

## Risks, assumptions, and open questions

| ID | Item | Status | Impact |
|---|---|---|---|
| R1 | Docker Desktop's nodes may not be observable from the local engine | Open | The Docker Desktop guard would be a name-and-shape check, weaker than `kind`'s, and a new security exception |
| R2 | Whether an engine-built image is visible to Docker Desktop's cluster without a load step is unknown | Open | The API and model-seed image steps assume `kind load`. Until this is answered, no release can be installed on the reference provider |
| R3 | The reference host's bundled kubectl was measured at `v1.36.1`, and both providers' servers here report 1.34 | Open | The skew rule refuses that client on either provider. A supported client is needed before any run, exactly as ADR 0001 R8 already says for `kind` |
| R4 | Docker Desktop's Kubernetes version follows its release | Accepted | Evidence on the reference provider is dated to a release, not pinned |
| R5 | The `kind` path will be largely unexecuted in V1 | Accepted | The reference host has no `kind` CLI. Implemented and tested `kind` checks will be reported as such, and unexecuted runs as not run |
| R6 | A Docker Desktop cluster provisioned differently from the one observed may appear | Mitigated by design | Its node shape fails D5's second check and it is refused until observed and recorded |
| R7 | Two security records are worded against the superseded design | Open, deliberately | Restated with the guard, so that neither describes a guard that does not exist |
| R8 | No public maintainer roster exists | Open | This record has no named decision owner |
