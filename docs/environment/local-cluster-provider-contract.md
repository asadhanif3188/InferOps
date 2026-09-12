# Local cluster provider contract

Status: **accepted** as the V1 environment contract, in
[ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md),
and **implemented for target selection and identification on both providers**,
by every mutating workflow except one. The authoritative form is data:
[`local-cluster-provider-contract.v1alpha1.json`](local-cluster-provider-contract.v1alpha1.json).
This page explains it, and
[`tests/architecture/test_local_cluster_provider_contract.py`](../../tests/architecture/test_local_cluster_provider_contract.py)
holds the two to each other and to the repository.

Read the status before the content. Every platform workflow now takes an
explicit `INFEROPS_PROVIDER` -- `kind` or `docker-desktop`, with no default --
and, for `kind`, an explicit `INFEROPS_KIND_CLUSTER_NAME`, and re-verifies that
selection itself before its first mutation through
[`inferops::resolve_target`](../../scripts/environment/lib.sh). Both providers
now have a positive identity check. Docker Desktop's is still narrower than
kind's, and V1-S3-011 narrowed the difference rather than closing it: it confirms
a context named `docker-desktop` exists, that its nodes match the one shape this
project has observed, that the node is a container on the engine this `docker`
CLI talks to carrying kind's labels, and that the container publishes the very
API server port the verified kubeconfig dials. What it still cannot refuse is a
kind cluster the operator themselves named `desktop`, reached through a context
they named `docker-desktop`; that case is recorded in the check's own `gap` and
as an accepted exception in
[the deferred-risk register](../security/deferred-risks.md). Of the three
workflows that used to re-verify and then refuse anything but the pinned kind
target, two -- `kubernetes-certification.sh` and
`kubernetes-multi-replica-certification.sh` -- were ported by V1-S3-011-PR1 and
now certify whichever supported provider they verified.
`helm-upgrade-rollback.sh` was the last workflow that refused a verified non-kind target; V1-S3-011-PR2 ported it, and it now acts on whichever provider the guard verified.
Every row below that nothing enforces says so, and says who owes it.

## What InferOps does and does not do to a cluster

**InferOps consumes a cluster somebody else created.** It never creates, enables,
resets, reconfigures, or deletes one, and no platform workflow runs a helper that
does. The operator does all five with the provider's own tooling: the `kind` CLI,
or Docker Desktop's settings.

What InferOps does own, in order:

```text
   operator provides an existing cluster       (kind CLI, or Docker Desktop)
       |
   selection: the operator names the provider, and for kind the cluster
       |
   verification: that provider's identity checks, against the reachable
   API server, before anything is changed          -> refuse, or:
       |
   project-scoped access: one kubeconfig, one context, written only now
       |
   target facts handed on: Terraform and Helm get an address; the drivers
   and the evidence get the rest
       |
   Terraform prerequisites, then the Helm release, inside that cluster
       |
   every runtime record names the provider it ran on
```

The `kind` helper scripts — `cluster-up.sh`, `cluster-down.sh`, `proof.sh`, and
the runbook in [the local cluster page](local-cluster.md) — stay in the
repository. They are one way for an operator to create a `kind` cluster, their
evidence is valid for what it measured, and they are not part of the platform
path.

## Selecting a target

| Provider | Selection inputs | Lifecycle, and who performs it |
|---|---|---|
| `kind` | `provider`, `clusterName` | The operator, with the `kind` CLI. The helper is optional |
| `docker-desktop` | `provider` | The operator, in Docker Desktop's settings. InferOps ships nothing that could |

**No input has a default.** A default is a selection somebody else made, and the
case where it is wrong is the case where the operator did not notice. A `kind`
cluster name is required because several `kind` clusters can share one engine;
Docker Desktop takes no name because its cluster is a singleton, and a name input
would be a second way to be wrong.

**How this is invoked.** `provider` is the environment variable
`INFEROPS_PROVIDER`; for `kind`, `clusterName` is `INFEROPS_KIND_CLUSTER_NAME`.
Neither is exported by anything in this repository, so an operator sets both
explicitly, for example
`INFEROPS_PROVIDER=docker-desktop scripts/environment/helm-lifecycle.sh --values PATH`
or
`INFEROPS_PROVIDER=kind INFEROPS_KIND_CLUSTER_NAME=inferops-dev scripts/environment/terraform-prerequisites.sh apply`.
`scripts/environment/target-detect.sh` reports which providers this host can
currently see, to help choose a value for `INFEROPS_PROVIDER` -- it never sets
one itself.

**Detection may report, never select.** A workflow may say which providers it can
see. It never picks one.

**Every mutating workflow is given the selection and re-verifies.** A target
recorded by an earlier run is compared against, never trusted: the cluster a
context points at can change between two commands.

## What verification hands on

These are the fields of the verified target. A consumer receives only the fields
naming it.

| Fact | Terraform | Helm | kubectl workflows | Certification | In evidence |
|---|:---:|:---:|:---:|:---:|:---:|
| `provider` | | | Yes | Yes | Yes |
| `clusterName` | | | Yes | Yes | Yes |
| `kubeconfigPath` | Yes | Yes | Yes | Yes | **No** |
| `kubeContext` | Yes | Yes | Yes | Yes | Yes |
| `serverVersion` | | | | Yes | Yes |
| `nodeNames` | | | | Yes | Yes |
| `containerRuntime` | | | | | Yes |
| `networkPlugin` | | | | | Yes |
| `networkPolicyEnforcement` | | | | Yes | Yes |
| `defaultStorageClass` | | | | Yes | Yes |
| `imagePreparation` | | | Yes | Yes | Yes |
| `nodeContainer` | | | Yes | Yes | Yes |
| `engineCapacity` | | | | Yes | Yes |
| `verifiedAt` | | | | Yes | Yes |
| `verifiedRevision` | | | | | Yes |

**Terraform and Helm receive an address and never a provider.** A module that
knows which provider it is on starts accreting provider-specific lifecycle logic,
which is exactly what this contract moved out of InferOps. The prerequisite
module names no provider, and its environment root's `kube_context` validation
now accepts a kind context of any selected cluster name or `docker-desktop`,
rather than only `kind-inferops-dev` -- a name check, same as before, that stops
an apply following a context left selected from other work without claiming to
establish identity itself.

**The kubeconfig is a credential.** For `kind` it holds the client certificate and
key the helper wrote; for `docker-desktop` it would hold a copy of Docker Desktop's.
Its path never enters a record and the file never enters the repository. Nor do
the API server's address, any certificate, key, or token, the operator's own
kubeconfig or its path, any context other than the verified one, or host names,
user accounts, and filesystem paths.

## How each provider is identified

Positive identification is the whole of the safety argument, so each check says
whether anything performs it.

| Check | Provider | Status | Enforced by |
|---|---|---|---|
| `the-project-kubeconfig-names-the-kind-context` | `kind` | Implemented, for the selected cluster name | `inferops::_kind_target_problem` |
| `every-node-is-a-container-kind-labelled-for-the-cluster` | `kind` | Implemented, for the selected cluster name | `inferops::_kind_target_problem` |
| `kind-reports-the-selected-cluster` | `kind` | Implemented; called by `inferops::resolve_target`, the helper, and `cluster-verify.sh` | `inferops::_kind_cluster_matches` |
| `the-docker-desktop-context-exists` | `docker-desktop` | Implemented | `inferops::_docker_desktop_target_problem` |
| `every-node-has-an-observed-docker-desktop-shape` | `docker-desktop` | Implemented, for the one shape observed | `inferops::_docker_desktop_target_problem` |
| `the-nodes-are-bound-to-the-local-engine` | `docker-desktop` | Implemented, by name rather than by filter | `inferops::_docker_desktop_target_problem` |

The `kind` check is the one [ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md)
D5 describes and that was attacked with a real foreign cluster wearing this
project's context name. It binds every node the API server reports to a container
`kind` labelled on the local engine. **That binding is what makes it more than a
name check.**

Docker Desktop now has that binding too. V1-S3-011 established what had been
recorded here as undecided: Docker Desktop provisions its Kubernetes *with kind*,
and `desktop-control-plane` is an ordinary container on the same engine the
operator's own `docker` CLI talks to, carrying
`io.x-k8s.kind.cluster=desktop` and `io.x-k8s.kind.role=control-plane`. The guard
reads those labels and refuses a node the local engine does not hold, and refuses
a node belonging to any kind cluster other than Docker Desktop's own — so
selecting `docker-desktop` cannot reach a kind cluster the operator created
themselves, even one whose node they named `desktop-control-plane`.

**The two guards are still not identical, and the difference is how the question
is asked.** `kind` asks the engine for a list — `docker ps --filter
label=io.x-k8s.kind.cluster=<name>` — and can therefore notice a node it was not
told about. Docker Desktop's API proxy filters its own containers out of
`docker ps`, so that filter returns nothing here and the same question has to be
asked by name, with `docker inspect <node>`. Asking by name can only confirm the
names the API server already reported. What fixes those names is the node-count
and node-name check above it, which accepts one node called
`desktop-control-plane` and nothing else; the two checks are relied on together
rather than either alone.

The node shape accepted is still only the one this project has observed — a
single node, `desktop-control-plane`, running `kindest/kindnetd` — and any other
shape is refused until somebody observes and records it. The cluster label value
is likewise Docker Desktop's own, `desktop`, observed on the V1 reference host; a
Docker Desktop release naming its cluster otherwise is refused rather than
accepted because it might be legitimate.

## When a workflow must refuse

Every refusal happens before any Terraform, Helm, or kubectl mutation and before
any image is loaded.

| Refusal | When | Implemented for |
|---|---|---|
| `no-provider-selected` | A mutating workflow gets no provider | `kind`, `docker-desktop` |
| `unsupported-provider` | The provider is neither `kind` nor `docker-desktop` | `kind`, `docker-desktop` |
| `ambiguous-target` | The selection is not exactly one cluster: `kind` with no name, a name `kind` does not list exactly once, or a kubeconfig holding more than one context | `kind`, `docker-desktop` |
| `target-missing` | No project kubeconfig, no such `kind` cluster, or no `docker-desktop` context | `kind`, `docker-desktop` |
| `target-unreachable` | The API server does not answer, or reports no nodes | `kind`, `docker-desktop` |
| `unexpected-context` | The project kubeconfig's context is not the verified one | Nothing (see below) |
| `provider-mismatch` | The reachable cluster fails the selected provider's checks, including when it is the other provider's cluster | `kind`, `docker-desktop` |
| `capability-unknown-or-insufficient` | The workflow needs a capability the target lacks, or one recorded below as unknown | `kind`, `docker-desktop` |
| `client-outside-skew` | kubectl is more than one minor version from the server the target reports | `kind`, `docker-desktop` |

Six of the nine are performed by one dispatcher, `inferops::_target_problem`,
which validates the provider itself and then hands off to
`inferops::_kind_target_problem` or `inferops::_docker_desktop_target_problem`.
`capability-unknown-or-insufficient` is `inferops::require_target_capability`,
called by a workflow that depends on a specific capability, and
`inferops::target_load_image`, which dispatches on the verified provider's
`imagePreparation` mechanism and refuses a value it has no branch for rather than
falling through to whichever branch happens to be last. Before V1-S3-011 that
refusal was what `api-image.sh load` and `model-seed-image.sh load` did on Docker
Desktop, because its `imagePreparation` was `not-established`; both providers now
have an implemented mechanism and the refusal is reserved for a third.
`client-outside-skew` is checked inside `inferops::resolve_target` itself,
against the version the *selected* cluster's server actually reports rather than
against a pin: `preflight.sh`'s own skew check, unaffected by this contract,
still compares the client to the minor version the kind helper's pinned node
image should produce.

`unexpected-context` is not implemented as a runtime check because
`inferops::resolve_target` makes its condition impossible by construction: it
rewrites the project-scoped kubeconfig from the operator's kubeconfig on every
call, naming the expected context explicitly, rather than writing it once and
comparing a later read against an expectation. There is no separately
long-lived file whose context could have drifted.

## Where the providers differ

Every answer states how it is known: **observed** on this provider and recorded;
**inferred** from a component the two share; **implemented, not executed**;
**documented** by the provider or by this repository's configuration; or
**unknown**. An unknown is written as unknown and never borrowed from the other
column.

| Question | `kind` | `docker-desktop` |
|---|---|---|
| `imagePreparation` | `kind load docker-image --name <cluster>`, then resolved in the node with `crictl inspecti`. *Implemented, not executed* | `docker save` piped into `ctr --namespace=k8s.io images import --all-platforms -` inside `desktop-control-plane`, then `ctr images tag` for the `repository@digest` name, then resolved with `crictl inspecti`. The engine's image store is **not** shared with this cluster, by tag or by digest; `kind load` does nothing here because the kind CLI finds nodes through the filtered `docker ps`. *Observed* |
| `defaultStorage` | kind's local-path StorageClass; the helper's node declares no `extraMounts`, so bytes live in the node container. *Documented* | A local-path provisioner under `/var/local-path-provisioner/`, reclaiming on delete. Class name not recorded. *Observed once* |
| `networkPolicyEnforcement` | Not enforced by kindnetd. *Inferred* from the Docker Desktop measurement, which ran the same plugin | Not enforced by the kindnetd build tested. *Observed* |
| `capacity` | The node shares the engine VM; preflight measures it. *Observed* | The node is given effectively the whole VM: allocatable 12 cpu and 10188020Ki against an engine allocation of 12 processors and 10432532480 bytes on the V1 reference host. A gate must read the node's own allocatable and what is already requested on it, not the engine total, because the engine figure counts memory other workloads in the same cluster already hold. *Observed* |
| `wholeClusterCleanup` | `kind delete cluster --name <cluster>` removes the node and its volumes; the `kind` network and node image survive. *Observed* | *Unknown.* What a reset or disable removes has not been observed, and no V1 workflow performs either |
| `kubernetesVersion` | Chosen by the node image; the helper pins 1.34.8. *Observed* | Bound to the Docker Desktop release, not pinnable. `v1.34.3` both times it was read. *Observed* |
| `nodeTopology` | `<cluster>-control-plane`, one node in the helper's definition. *Observed* | One node, `desktop-control-plane`, running kindest/kindnetd. *Observed* |

The two providers share a network plugin and a node shape. That is exactly what
makes it tempting to assume they share everything else, and it is why this table
exists.

## Evidence

**Every runtime record states the provider and cluster it ran on, and a result on
one provider is never presented as a result on the other.** Nothing writes a
provider into a record yet; that belongs to the implementation.

The records that have contacted a real cluster so far, labelled here without
editing them — they are history rather than documentation:

| Record | Provider | What it establishes |
|---|---|---|
| [Cluster smoke proof](../proof/environment/v1-s0-002-pr2-cluster-smoke.md) | `kind`, `inferops-dev` | Creation from the pinned image, a hello-world Service answering, teardown without residue |
| [Runtime feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) | `docker-desktop` | The selected runtime serving real inference in a pod through a Service — from trial manifests, not from this project's chart |
| [Cluster lifecycle result](../proof/environment/v1-s3-001-pr1-cluster-lifecycle.md) | `kind`, `inferops-dev` | Repeatable create, verify, smoke, and teardown by the helper, and its refusals |
| [NetworkPolicy enforcement result](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md) | `docker-desktop` | That the network plugin there enforced none of a default-deny's rules |

Read across, that says something easy to miss. **The cluster evidence behind
ADR 0001 exists only for `kind`; the in-cluster runtime evidence behind ADR 0002
exists only for Docker Desktop.** An InferOps release has been installed,
certified, upgraded, rolled back, had a pod replaced under it, and removed — on
the Docker Desktop column only. Neither column certifies the other.

## The rules, and which of them anything enforces

| Rule | Enforced by |
|---|---|
| `the-platform-path-never-changes-a-cluster-lifecycle` | A test reading every platform workflow for a cluster create, delete, or helper invocation |
| `the-cluster-belongs-to-its-operator` | A test reading the ownership inventory |
| `exactly-two-providers-are-supported` | A test |
| `selection-is-explicit` | `inferops::_target_problem`, for both providers |
| `detection-never-selects` | A test reading `target-detect.sh` for a mutating command |
| `verification-precedes-every-mutation` | `inferops::resolve_target`, for both providers |
| `a-context-name-is-never-identity` | `inferops::_target_problem`, for both providers |
| `access-never-inherits-an-ambient-context` | `inferops::target_kubectl` and `inferops::target_helm`, for both providers |
| `terraform-and-helm-receive-an-address-never-a-provider` | A test on the module, and the environment root's own validation |
| `terraform-and-helm-ownership-stays-disjoint` | The ownership inventory's own test |
| `a-provider-difference-is-recorded-not-averaged` | A test on the capability table |
| `evidence-names-its-provider` | **Nothing yet** |
| `no-provider-certifies-another` | Review alone |
| `the-reference-provider-is-a-choice-of-host-not-a-ranking` | Review alone |

Fourteen rules: six enforced by a test, four by a shell guard, one by nothing,
one by another suite's test, and two by review alone. The data records who owes
the one still unimplemented: `kubernetes-certification.sh`,
`kubernetes-multi-replica-certification.sh`, and `helm-upgrade-rollback.sh` still
write `cluster.name`/`cluster.context` into their evidence from the kind-pinned
constants rather than from the verified target, which is V1-S3-011's to fix
alongside porting those three workflows to a provider-neutral target.

**The reference provider is `docker-desktop`.** The current re-certification runs
there because the reference host has it and does not have the `kind` CLI, and
because two of the four real-cluster records above already ran there. That is a
choice of host. It is not a claim that Docker Desktop is better, closer to
production, or equivalent to `kind`.

## What this implementation does not do

- **It does not bind Docker Desktop's nodes to the local engine.** That check
  remains undecided, and the Docker Desktop guard is a name-and-shape check
  rather than kind's stronger one until it exists.
- **It does not port the certification and experiment scripts.**
  `kubernetes-certification.sh`, `kubernetes-multi-replica-certification.sh`, and
  `helm-upgrade-rollback.sh` now require an explicit provider and re-verify it,
  but their descriptors and evidence tooling are still specific to the kind
  cluster this repository pins; a Docker Desktop target passes the target
  verification above and is refused immediately afterward, by name, rather than
  silently certified against a descriptor that does not describe it. Porting
  them is V1-S3-011.
- **It contacted no cluster.** Every Docker Desktop capability answer above is
  still quoted from a record made earlier, with the date of that record rather
  than today's: this PR verifies identity, not the capability questions
  themselves.
- **It cannot read prose.** The suite checks identifiers, statuses, sources, and
  the files a row names. A row whose description has drifted from the behaviour it
  describes will not fail a check.
